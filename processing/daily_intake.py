"""Shared private-source Daily lane. Originals stay in private Git custody.

The queue is a small processing ledger, not another article corpus. Private
collectors supply immutable Git snapshots; this module never collects a URL.
The public projection contains only separately permitted machine explanations.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from core import processing_state
from core.crossdesk_official_metadata_candidates import canonical
from processing.screening import PHILIPPINES_PROFILE

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/philippines_daily_policy.json"
PRIVATE_REPO = "VSSpowerlifting/ipr-source-evidence-private"
REFS = {"ph_afp_articles": "archive/ph-afp",
        "ph_nsc_official_statements": "archive/ph-nsc"}
SHA = re.compile(r"[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
DOMAIN = b"ipr-shared-daily-machine-output/1\n"
PUBLIC_FIELDS = (
    "source_family", "source_identity", "metadata_version_sha256",
    "content_sha256", "capture_sha256", "source_git_commit", "source_run",
    "summary", "categories", "model_flagged", "flag_reason", "model_id",
    "prompt_version", "quality_sha256", "policy_sha256",
)


class IntakeHold(ValueError):
    """Fixed diagnostic only: no originals or model responses in logs."""


def need(ok, reason):
    if not ok:
        raise IntakeHold(reason)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_policy(path=POLICY_PATH):
    value = json.loads(Path(path).read_text())
    need(set(value) == {"schema", "sources"}
         and value["schema"] == "ipr-daily-source-policy/1"
         and set(value["sources"]) == set(REFS), "daily_policy_invalid")
    for p in value["sources"].values():
        need(set(p) == {"private_model_processing", "public_machine_explanation",
                       "unattended_release", "owner_decision",
                       "max_records_per_run", "max_input_characters",
                       "max_estimated_cost_usd_per_run", "excluded_source_identities"}, "daily_policy_invalid")
        need(all(type(p[k]) is bool for k in (
            "private_model_processing", "public_machine_explanation", "unattended_release")),
            "daily_policy_invalid")
        need(type(p["max_records_per_run"]) is int and p["max_records_per_run"] == 1
             and type(p["max_input_characters"]) is int
             and 100 <= p["max_input_characters"] <= 16000, "daily_spend_bound_invalid")
        need(type(p["max_estimated_cost_usd_per_run"]) in (int, float)
             and 0 < p["max_estimated_cost_usd_per_run"] <= 0.35,
             "daily_spend_bound_invalid")
        excluded = p["excluded_source_identities"]
        need(type(excluded) is list and len(excluded) <= 100
             and all(type(v) is str and 0 < len(v) < 120 for v in excluded)
             and len(set(excluded)) == len(excluded), "daily_policy_invalid")
        need(not any(p[k] for k in ("private_model_processing", "public_machine_explanation",
                                   "unattended_release"))
             or (type(p["owner_decision"]) is str and len(p["owner_decision"].strip()) >= 10),
             "daily_owner_decision_missing")
    return value


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True).stdout


def verified_source(repo, commit, family):
    """Reuses capture/history validators; returns private in-memory originals."""
    need(family in REFS and type(commit) is str and bool(COMMIT.fullmatch(commit)),
         "daily_source_pin_invalid")
    remote = git(repo, "remote", "get-url", "origin").decode().strip()
    remote = remote[:-4] if remote.endswith(".git") else remote
    need(remote in ("https://github.com/" + PRIVATE_REPO,
                    "git@github.com:" + PRIVATE_REPO), "daily_custody_mismatch")
    need(git(repo, "cat-file", "-t", commit).strip() == b"commit", "daily_source_pin_invalid")
    # The pin must be on the source's actual custody branch, not another family.
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", commit,
                    REFS[family]], check=True, capture_output=True)
    if family == "ph_afp_articles":
        from core.ph_afp_release_validator import verify_history, candidate_packet
        verify_history(repo, commit)
        packet = candidate_packet(repo, commit)
        # Metadata candidate builder uses `records` for the public-safe links.
        links = packet["records"]
    else:
        from core.ph_nsc_official_link_admission import prepare
        packet = prepare(repo, commit, REFS[family])
        links = packet["links"]
    with tempfile.TemporaryDirectory(prefix="ipr-private-daily-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(git(repo, "show", commit + ":state/shadow.db"))
        with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = {r["source_identity"]: dict(r) for r in conn.execute(
                "SELECT * FROM shadow_records WHERE source_slug=?", (family,))}
    result = []
    for link in links:
        r = rows[link["source_identity"]]
        need(r["url"] == link["canonical_official_url"]
             and r["published_date"] == link["publisher_posted_date"]
             and r["language_tag"] == "en"
             and hashlib.sha256(r["text_original"].encode()).hexdigest() == r["content_sha256"],
             "daily_source_version_mismatch")
        result.append({**link, "source_family": family, "source_git_commit": commit,
                       "content_sha256": r["content_sha256"],
                       "capture_sha256": r["capture_sha256"],
                       "source_run": r["first_seen_run"],
                       "title": r["title_original"], "body": r["text_original"]})
    return sorted(result, key=lambda r: (r["publisher_posted_date"], r["source_identity"]), reverse=True)


def bound_private_calls(analyzer, policy):
    """Guard the shared Analyzer's two English calls before dispatch."""
    from config import ANALYSIS_MODEL, RELEVANCE_MODEL, RELEVANCE_TOOL_OUTPUT_ENABLED
    from analysis.pricing import estimate_usage_cost_usd
    need(not RELEVANCE_TOOL_OUTPUT_ENABLED, "daily_private_tool_route_not_authorized")
    call = analyzer._call
    remaining, calls = policy["max_estimated_cost_usd_per_run"], 0
    expected = (("relevance", RELEVANCE_MODEL, 500), ("summary", ANALYSIS_MODEL, 2200))

    def guarded(messages, *, model=None, max_tokens=1000, task=None, **kwargs):
        nonlocal remaining, calls
        used_model = model or ANALYSIS_MODEL
        need(calls < 2 and (task, used_model, max_tokens) == expected[calls],
             "daily_private_call_bound")
        # UTF-8 bytes bound text tokens; reserve request framing and the more
        # expensive cache-write rate, rather than guessing chars per token.
        size = len(json.dumps([messages, kwargs], ensure_ascii=False).encode()) + 2048
        cost = estimate_usage_cost_usd(used_model, 0, max_tokens, size, 0)
        need(cost is not None and cost <= remaining, "daily_private_spend_bound")
        remaining -= cost
        calls += 1
        return call(messages, model=model, max_tokens=max_tokens, task=task, **kwargs)

    analyzer._call = guarded
    analyzer._client = analyzer._client.with_options(max_retries=0)


def quality_check(record, reading):
    """Conservative exact-fact checks; no model confidence is accepted as proof.

    These checks cannot certify arbitrary paraphrase semantics. Each sentence
    must carry a verbatim evidence span; novel numerical/name/rank tokens and
    unsupported completion language hold. Evidence spans stay private.
    """
    need(type(reading) is dict and reading.get("passed_relevance") is True
         and reading.get("requires_translation") is False, "daily_analysis_incomplete")
    summary = reading.get("summary_english")
    need(type(summary) is str and 5 <= len(summary.split()) <= 90,
         "daily_summary_invalid")
    facts = reading.get("facts")
    need(type(facts) is list and 2 <= len(facts) <= 3, "daily_evidence_incomplete")
    need(all(type(f) is dict and type(f.get("sentence")) is str for f in facts),
         "daily_evidence_invalid")
    need(" ".join(f["sentence"] for f in facts) == summary,
         "daily_summary_coverage_incomplete")
    source = record["title"] + "\n" + record["body"]
    attribution = "AFP" if record["source_family"] == "ph_afp_articles" else "NSC"
    flagged = reading.get("is_significant")
    flag_reason = reading.get("significance_reasoning") if flagged else ""
    need(type(flag_reason) is str and len((summary + " " + flag_reason).split()) <= 90,
         "daily_explanation_word_limit")
    checked_facts = list(facts)
    if flagged:
        checked_facts.append({"sentence": reading.get("significance_reasoning"),
                              "evidence": reading.get("flag_evidence")})
    for fact in checked_facts:
        need(type(fact) is dict and set(fact) == {"sentence", "evidence"},
             "daily_evidence_invalid")
        sentence, evidence = fact["sentence"], fact["evidence"]
        need(type(sentence) is str and type(evidence) is str
             and 20 <= len(evidence) <= 500 and evidence in source,
             "daily_evidence_not_in_original")
        need(attribution in sentence or
             ("Armed Forces of the Philippines" if attribution == "AFP" else
              "National Security Council") in sentence, "daily_attribution_missing")
        numeric = r"(?<!\w)[+-]?\d+(?:[.,:/-]\d+)*(?:%)?"
        source_numbers = set(re.findall(numeric, evidence))
        for number in re.findall(numeric, sentence):
            need(number in source_numbers, "daily_quantity_or_date_unsupported")
        # Exact proper-name/office/rank components must occur in source evidence.
        institutional_words = ({"Armed", "Forces", "Philippines"} if attribution == "AFP"
                               else {"National", "Security", "Council"})
        for token in re.findall(r"\b[A-Z][A-Za-z'-]+\b", sentence):
            if token not in {"The", "According", "It", "This", attribution} | institutional_words:
                need(token in evidence, "daily_name_or_office_unsupported")
        for word in ("completed", "delivered", "signed", "acquired", "agreed", "deployed"):
            if re.search(r"\b" + word + r"\b", sentence, re.I):
                need(re.search(r"\b" + word + r"\b", evidence, re.I) is not None,
                     "daily_completed_action_unsupported")
                if re.search(r"\b(will|plans?|planned|intends?|proposed|not|never|denied)\b", evidence, re.I):
                    need(re.search(r"\b(will|plans?|planned|intends?|proposed|not|never|denied)\b", sentence, re.I) is not None,
                         "daily_modality_or_contradiction_hold")
        # No copied sentence or long excerpt in the output, even with attribution.
        words = re.findall(r"\w+", sentence.casefold())
        source_words = " " + " ".join(re.findall(r"\w+", source.casefold())) + " "
        need(all(" " + " ".join(words[i:i+12]) + " " not in source_words
                 for i in range(max(0, len(words) - 11))), "daily_original_excerpt_prohibited")
        normalized = " " + " ".join(words) + " "
        for original_sentence in re.split(r"(?<=[.!?])\s+", record["body"]):
            original_words = re.findall(r"\w+", original_sentence.casefold())
            if len(original_words) >= 6:
                need(" " + " ".join(original_words) + " " not in normalized,
                     "daily_original_sentence_prohibited")
    cats, flagged = reading.get("categories"), reading.get("is_significant")
    need(type(cats) is list and cats and all(c in PHILIPPINES_PROFILE.categories for c in cats)
         and type(flagged) is bool and (not flagged or
             (type(reading.get("significance_reasoning")) is str
              and reading["significance_reasoning"].strip())), "daily_analysis_incomplete")
    if "south_china_sea" in cats:
        need(re.search(r"\b(?:South China Sea|West Philippine Sea)\b", source, re.I) is not None,
             "daily_topic_unsupported")
    need(type(reading.get("model_id")) is str and bool(reading["model_id"])
         and reading.get("prompt_version") in ("ph-relevance-v1+ph-analysis-v10",
                                              "ph-relevance-v1+ph-analysis-v11",
                                              "ph-relevance-v1+ph-analysis-v12",
                                              "ph-relevance-v1+ph-analysis-v13"),
         "daily_model_provenance_incomplete")
    return digest({"source": record["content_sha256"], "facts": facts, "version": "ph-quality-v1"})


def bind_admitted_metadata(records, conn, *, source_repo):
    """Bind a later private custody pin to an unchanged public link version.

    AFP's metadata digest includes the snapshot commit. Recollection alone is
    not a changed article; compare actual identity/date/attribution before using
    the already-released metadata version. No new link authority is created.
    """
    bound, snapshots = [], {}
    fields = ("canonical_official_url", "publisher_posted_date", "official_issuer",
              "official_publisher", "official_republisher", "first_seen_run")
    for r in records:
        link = conn.execute("SELECT " + ",".join(fields) + ",metadata_version_sha256,source_git_commit "
            "FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
            (r["source_family"], r["source_identity"])).fetchone()
        if link and tuple(link[:6]) == tuple(r[k] for k in fields):
            commit = link[7]
            if commit not in snapshots:
                with tempfile.TemporaryDirectory(prefix="ipr-private-version-") as tmp:
                    path = Path(tmp) / "shadow.db"
                    path.write_bytes(git(source_repo, "show", commit + ":state/shadow.db"))
                    with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as original:
                        snapshots[commit] = {row[0]: row[1:] for row in original.execute(
                            "SELECT source_identity,title_original,content_sha256,capture_sha256 FROM shadow_records")}
            if snapshots[commit].get(r["source_identity"]) != (r["title"], r["content_sha256"], r["capture_sha256"]):
                continue  # changed original stays out of paid processing
            bound.append({**r, "metadata_version_sha256": link[6]})
    return bound


def process(records, state, *, family, policy, analyzer_factory=None, reading_observer=None):
    """Bounded shared Analyzer dispatch, reversible retries, isolated item holds.

    `state` is a private JSON processing ledger persisted by the private runner.
    No originals are serialized. A new immutable version holds for review.
    """
    from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
    need(family in REFS and all(type(r) is dict and r.get("source_family") == family for r in records),
         "daily_processing_source_family_mismatch")
    p = policy["sources"][family]
    result = json.loads(json.dumps(state))
    used, analyzer = 0, None
    present = {family + ":" + r["source_identity"] for r in records}
    for key, entry in result.items():
        if key.startswith(family + ":") and key not in present:
            entry.update(status="held", reason="source_missing_or_metadata_changed")
    for r in records:
        key = family + ":" + r["source_identity"]
        version = digest({k: r[k] for k in ("metadata_version_sha256", "content_sha256",
                                           "capture_sha256")})
        prior = result.get(key, {})
        if r["source_identity"] in p["excluded_source_identities"]:
            result[key] = {**prior, "status": "held", "reason": "owner_excluded_source_identity"}
            continue
        if prior.get("version") not in (None, version):
            result[key] = {**prior, "status": "held", "reason": "source_version_changed"}
            continue
        if prior.get("status") == "complete" and p["private_model_processing"]:
            prior["output"]["policy_sha256"] = digest(p)
        if prior.get("status") in ("complete", "not_selected", "paused", "held"):
            # Rights holds can resume automatically after an actual policy change.
            if not (prior.get("reason") == "model_rights_held" and p["private_model_processing"]):
                continue
        entry = {"version": version, "attempts": prior.get("attempts", 0)}
        result[key] = entry
        if not p["private_model_processing"]:
            entry.update(status="held", reason="model_rights_held")
            continue
        if family == "ph_afp_articles" and not (
                r.get("official_issuer") == r.get("official_publisher") == "ph_afp"
                and r.get("official_republisher") is None):
            entry.update(status="held", reason="source_rights_not_first_party")
            continue
        if family == "ph_nsc_official_statements":
            from core.ph_nsc_official_link_admission import load_policy as nsc_policy
            if not nsc_policy()["category_anomaly_resolved"]:
                entry.update(status="held", reason="nsc_category_anomaly")
                continue
        if not r["body"].strip() or len((r["title"] + r["body"]).encode("utf-8")) > p["max_input_characters"]:
            entry.update(status="held", reason="original_input_bound")
            continue
        if used >= p["max_records_per_run"]:
            entry.update(status="pending")
            continue
        if analyzer is None:
            analyzer = (analyzer_factory or Analyzer)()
            if analyzer_factory is None:
                # Queue attempts, not hidden SDK retries, govern private spend.
                bound_private_calls(analyzer, p)
        used += 1
        try:
            reading = analyzer.analyze_record(r["title"], r["body"], PHILIPPINES_PROFILE)
            if reading_observer is not None:
                reading_observer(r["source_identity"], reading)
            if reading and reading.get("passed_relevance") is False:
                entry.update(status="not_selected")
                continue
            quality = quality_check(r, reading)
            entry.update(status="complete", output={
                **{k: r[k] for k in PUBLIC_FIELDS[:7]},
                "summary": reading["summary_english"], "categories": reading["categories"],
                "model_flagged": reading["is_significant"],
                # Explanation must pass the same output non-disclosure gate.
                "flag_reason": reading.get("significance_reasoning") if reading["is_significant"] else None,
                "model_id": reading["model_id"], "prompt_version": reading["prompt_version"],
                "quality_sha256": quality, "policy_sha256": digest(p),
            })
        except FatalAPIError:
            entry.update(status="pending", reason="account_blocked")
            break
        except (AnalysisError, IntakeHold) as exc:
            disposition = processing_state.classify(
                attempts_before=entry["attempts"], has_body=True,
                failure=processing_state.ANALYSIS_INCOMPLETE)
            entry.update(status=disposition.state, attempts=disposition.attempts,
                         reason="analysis_or_quality_failed")
            if isinstance(exc, IntakeHold):
                entry["quality_hold"] = str(exc)  # fixed diagnostic, never source text
    usage_record = None
    if analyzer is not None:
        from analysis.usage import build_run_record
        from config import ANALYSIS_MODEL, RELEVANCE_MODEL
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        usage_record = build_run_record(analyzer.usage, run_date=now.date().isoformat(),
            recorded_at=now.isoformat(), run_status="private_source_processing",
            analysis_model=ANALYSIS_MODEL, relevance_model=RELEVANCE_MODEL,
            articles_queued=used,
            articles_fully_analyzed=sum(1 for k, v in result.items()
                if k.startswith(family + ":") and v.get("status") == "complete"
                and state.get(k, {}).get("status") != "complete"))
    return result, usage_record or []


def sign_outputs(state, *, family, policy, key):
    p = policy["sources"][family]
    need(p["private_model_processing"] and p["public_machine_explanation"]
         and p["unattended_release"], "daily_output_rights_held")
    need(type(key) is str and len(key) >= 32, "daily_bridge_key_invalid")
    outputs = [v["output"] for k, v in sorted(state.items())
               if k.startswith(family + ":") and v.get("status") == "complete"
               and v["output"]["source_identity"] not in p["excluded_source_identities"]
               and v["output"]["policy_sha256"] == digest(p)]
    packet = {"schema": "ipr-shared-daily-machine-output/1", "family": family,
              "source_repository": PRIVATE_REPO, "source_ref": REFS[family],
              "processor_commit": git(ROOT, "rev-parse", "HEAD").decode().strip(), "records": outputs,
              "held": [k[len(family)+1:] for k, v in sorted(state.items())
                       if k.startswith(family + ":") and v.get("status") in ("held", "paused")]}
    raw = canonical(packet)
    need(len(raw) <= 512000, "daily_envelope_too_large")
    return {"packet": packet, "mac": hmac.new(key.encode(), DOMAIN + raw, hashlib.sha256).hexdigest()}


def admit(conn, envelope, *, family, policy, key):
    """Atomic public admission; pinned policy and existing source metadata win."""
    need(family in REFS and type(key) is str and len(key) >= 32 and type(envelope) is dict
         and set(envelope) == {"packet", "mac"}, "daily_envelope_invalid")
    packet = envelope["packet"]
    need(type(packet) is dict, "daily_envelope_invalid")
    raw = canonical(packet)
    need(len(raw) <= 512000 and type(envelope["mac"]) is str
         and hmac.compare_digest(hmac.new(key.encode(), DOMAIN + raw, hashlib.sha256).hexdigest(),
                                 envelope["mac"]), "daily_envelope_mac_invalid")
    p = policy["sources"][family]
    need(p["private_model_processing"] and p["public_machine_explanation"] and p["unattended_release"],
         "daily_output_rights_held")
    need(set(packet) == {"schema", "family", "source_repository", "source_ref", "processor_commit", "records", "held"}
         and packet["schema"] == "ipr-shared-daily-machine-output/1"
         and packet["family"] == family and packet["source_repository"] == PRIVATE_REPO
         and packet["source_ref"] == REFS[family] and type(packet["records"]) is list
         and type(packet["held"]) is list and all(type(s) is str for s in packet["held"]),
         "daily_envelope_source_mismatch")
    need(type(packet["processor_commit"]) is str and COMMIT.fullmatch(packet["processor_commit"]),
         "daily_processor_pin_invalid")
    from core.indonesia_kemhan_release_validator import _is_ancestor
    need(_is_ancestor(ROOT, packet["processor_commit"], "HEAD"), "daily_processor_not_in_public_history")
    if family == "ph_nsc_official_statements":
        from core.ph_nsc_official_link_admission import load_policy as nsc_policy
        need(nsc_policy()["category_anomaly_resolved"], "nsc_category_anomaly")
    from migrations.versions.m0015_daily_machine_records import is_already_applied
    need(is_already_applied(conn), "daily_migration_required")
    accepted, held = 0, []
    with conn:
        for ident in packet["held"]:
            conn.execute("UPDATE daily_machine_records SET publication_state='held' "
                         "WHERE source_family=? AND source_identity=? AND publication_state!='held'", (family, ident))
        for r in packet["records"]:
            try:
                validate_output(r, family, p)
                link = conn.execute("SELECT metadata_version_sha256,first_seen_run FROM "
                    "regional_official_source_links WHERE source_family=? AND source_identity=?",
                    (family, r["source_identity"])).fetchone()
                need(link is not None and link[0] == r["metadata_version_sha256"]
                     and link[1] == r["source_run"], "daily_admitted_source_version_mismatch")
                prior = conn.execute("SELECT summary,content_sha256,capture_sha256,metadata_version_sha256,policy_sha256 FROM daily_machine_records "
                    "WHERE source_family=? AND source_identity=?", (family, r["source_identity"])).fetchone()
                if prior:
                    need(tuple(prior[:4]) == (r["summary"], r["content_sha256"], r["capture_sha256"],
                                          r["metadata_version_sha256"]), "daily_released_version_changed")
                    if prior[4] != r["policy_sha256"]:
                        conn.execute("UPDATE daily_machine_records SET policy_sha256=? "
                                     "WHERE source_family=? AND source_identity=?",
                                     (r["policy_sha256"], family, r["source_identity"]))
                    continue
                values = [canonical(r[k]).decode() if k == "categories" else r[k] for k in PUBLIC_FIELDS]
                columns = ["categories_json" if k == "categories" else k for k in PUBLIC_FIELDS]
                conn.execute("INSERT INTO daily_machine_records (" + ",".join(columns) + ") VALUES (" + ",".join("?" for _ in values) + ")", values)
                accepted += 1
            except IntakeHold as exc:
                held.append(str(exc))
    return {"admitted": accepted, "holds": held}


def resume(state, key):
    """Explicit reversible exception recovery; changed versions require review."""
    need(key in state and state[key].get("status") != "complete", "daily_resume_invalid")
    disposition = processing_state.resume(state[key].get("attempts"))
    state[key].update(status="pending", attempts=disposition.attempts)
    state[key].pop("reason", None)
    return state


def validate_output(r, family, p):
    need(type(r) is dict and set(r) == set(PUBLIC_FIELDS)
         and r["source_family"] == family and r["policy_sha256"] == digest(p),
         "daily_output_schema_or_policy_invalid")
    need(r["source_identity"] not in p["excluded_source_identities"],
         "daily_owner_excluded_source_identity")
    need(all(type(r[k]) is str and SHA.fullmatch(r[k]) for k in (
        "metadata_version_sha256", "content_sha256", "capture_sha256", "quality_sha256", "policy_sha256"))
         and type(r["source_git_commit"]) is str and COMMIT.fullmatch(r["source_git_commit"]),
         "daily_output_provenance_invalid")
    need(type(r["summary"]) is str and 5 <= len(r["summary"].split()) <= 90
         and type(r["model_flagged"]) is bool
         and ((not r["model_flagged"] and r["flag_reason"] is None) or
              (r["model_flagged"] and type(r["flag_reason"]) is str and bool(r["flag_reason"].strip())))
         and type(r["categories"]) is list and r["categories"]
         and all(type(c) is str and c in PHILIPPINES_PROFILE.categories for c in r["categories"])
         and type(r["model_id"]) is str and bool(r["model_id"])
         and r["prompt_version"] in ("ph-relevance-v1+ph-analysis-v10",
                                     "ph-relevance-v1+ph-analysis-v11",
                                     "ph-relevance-v1+ph-analysis-v12",
                                     "ph-relevance-v1+ph-analysis-v13"), "daily_output_incomplete")
    need(len((r["summary"] + " " + (r["flag_reason"] or "")).split()) <= 90,
         "daily_explanation_word_limit")
