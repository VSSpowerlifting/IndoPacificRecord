"""Thin bridge from authenticated Vietnam captures into the shared corpus.

One Daily step per ministry source family:

  1. replay the private state commit with the existing admission adapter
     (core.vietnam_official_link_admission.prepare) and authenticate its tip
     and collection attempts against GitHub (authenticate); nothing is
     recrawled. After the private-first cutover (#831) the Ministry of Public
     Security runs with PrivateCustody instead: the archive/ ref of the
     private evidence repository, authenticated by authenticate_private,
     whose pre-cutover versions stay bound to their public attempts;
  2. re-export the same commit to read each current version's preserved body;
  3. skip versions already in the corpus, hold material changes;
  4. apply the family's source-use policy before any model call;
  5. analyse with the shared Analyzer and the family's ScreeningProfile;
  6. run the exception-based QA gate (core.vietnam_daily_qa);
  7. write a passing record to `articles` with its provenance row, in one
     BEGIN IMMEDIATE transaction, projecting only the fields the policy
     allows into public storage.

A held or screened-out record writes nothing to the database. Its state
(attempts, failure codes) lives in a private JSON ledger outside this
repository, so a retry does not re-spend a screened record and a repeated
retryable failure escalates. Under the standing policy (no owner decision)
every record is held for rights before any model call: the bridge then makes
no model call and no database write.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from analysis.vietnam_prompts import terminology_version
from core import vietnam_daily_qa as qa
from core import vietnam_official_link_admission as vn
from core.collection.vietnam_sources import SOURCES
from core.retired_article_urls import is_retired, next_available_article_id
from core.vietnam_source_use import SourceUse
from processing.screening import profile_for_source
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal

LEDGER_SCHEMA = "ipr-vietnam-daily-ledger/1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DUPLICATE = "duplicate"
SETTLED = "settled"  # screened out or escalated earlier; not re-spent

_INSTITUTIONS = {
    "vn_mps": ("Ministry of Public Security", "Bộ Công an"),
    "vn_moit": ("Ministry of Industry and Trade", "Bộ Công Thương"),
}


class BridgeError(RuntimeError):
    """The run cannot continue (bad ledger path, unauthenticated source)."""


def desk_promoted(desk) -> bool:
    """Whether the registry lets Vietnam records reach the public corpus.

    A sealed source-use decision grants rights; it does not promote the desk.
    Promotion is the separate owner act of declaring the registry entry live
    with production records (desks/registry.json), which the renderer checks
    too, so a granted family cannot publish under a page that says it is shadow.
    """
    return bool(desk is not None and desk.is_collecting and desk.has_production_records)


# ── Private ledger ───────────────────────────────────────────────────────────

def _check_ledger_path(path: Path) -> Path:
    path = Path(path).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        return path
    raise BridgeError("vietnam_ledger_must_be_outside_public_repository")


def load_ledger(path: Path, family: str) -> dict:
    path = _check_ledger_path(path)
    if not path.exists():
        return {"schema": LEDGER_SCHEMA, "source_family": family, "items": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != LEDGER_SCHEMA or data.get("source_family") != family \
            or not isinstance(data.get("items"), dict):
        raise BridgeError("vietnam_ledger_malformed")
    return data


def save_ledger(path: Path, ledger: dict) -> None:
    path = _check_ledger_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".vn-ledger-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


# ── Source replay ────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class PrivateCustody:
    """Ministry of Public Security records held in the private evidence repository.

    `public_frozen_tip` is the last public shadow commit, whose history stays
    authenticated against the public collector; `private_api` reads the private
    repository's ref, attempt receipts and Actions attempts. Originals never
    leave the local private clone except through the source-use projection.
    """
    public_frozen_tip: str
    private_api: object


def _state_ref(family: str, private: bool) -> str:
    ref = SOURCES[family].state_branch
    if not private:
        return ref
    # The same derivation as vn.prepare(private=True), checked against #831's ref.
    ref = ref.replace("shadow/", "archive/", 1)
    if ref != vn.PRIVATE_REF:
        raise BridgeError("vietnam_private_ref_mismatch")
    return ref


def preserved_versions(state_repo, commit: str, family: str, *,
                       private: bool = False) -> Dict[tuple, dict]:
    """Each preserved version of the commit, keyed (identity, content_sha256)."""
    repo = formal.resolve_state_repo(state_repo)
    formal.verify_state_commit(repo, commit, _state_ref(family, private))
    with tempfile.TemporaryDirectory(prefix="ipr-vn-bridge-") as tmp:
        state = formal.export_state_tree(repo, commit, Path(tmp) / "state")
        evidence = ministry.review(state, family)
    return {(v["source_identity"], v["content_sha256"]): v for v in evidence["versions"]}


# ── Corpus writes ────────────────────────────────────────────────────────────

def _ensure_source(conn: sqlite3.Connection, family: str) -> int:
    """The family's sources row; created inactive at the first publication.

    The private collector, not the shared scraper, collects these sources, so
    the row is never enabled for scraping. The desk row is created 'shadow';
    making the desk public is a separate owner decision.
    """
    row = conn.execute("SELECT id, desk_id FROM sources WHERE slug=?", (family,)).fetchone()
    if row is not None:
        if row[1] != "vietnam":
            raise BridgeError("vietnam_source_row_belongs_to_another_desk")
        return row[0]
    if conn.execute("SELECT 1 FROM desks WHERE desk_id='vietnam'").fetchone() is None:
        conn.execute(
            "INSERT INTO desks (desk_id, display_name, jurisdiction_code, default_timezone,"
            " default_calendar, supported_language_tags, active, public_status)"
            " VALUES ('vietnam', 'Vietnam Desk', 'VN', 'Asia/Ho_Chi_Minh', 'gregorian',"
            " '[\"vi\", \"en\"]', 1, 'shadow')")
    institution = vn.ISSUERS[family]
    if conn.execute("SELECT 1 FROM institutions WHERE institution_id=?",
                    (institution,)).fetchone() is None:
        name, original = _INSTITUTIONS[institution]
        conn.execute("INSERT INTO institutions (institution_id, desk_id, display_name,"
                     " name_original, institution_type) VALUES (?, 'vietnam', ?, ?, 'other')",
                     (institution, name, original))
    src = SOURCES[family]
    cur = conn.execute(
        "INSERT INTO sources (slug, display_name, base_url, language, is_active, desk_id,"
        " institution_id, language_tag, timezone, calendar, authority_tier, source_type,"
        " originality, access_method, enabled, listing_endpoints, notes)"
        " VALUES (?, ?, ?, 'vi', 0, 'vietnam', ?, 'vi', 'Asia/Ho_Chi_Minh', 'gregorian',"
        " 'A', 'official_news', 'original', 'private_collector', 0, ?, ?)",
        (family, "%s — %s" % (src.publisher, src.family), "https://" + src.host,
         institution, json.dumps([src.listing]),
         "Collected by the private Vietnam collector; admitted by core.vietnam_corpus_bridge"))
    return cur.lastrowid


def _existing(conn: sqlite3.Connection, identity: str):
    return conn.execute("SELECT article_id, content_sha256 FROM vietnam_article_provenance"
                        " WHERE source_identity=?", (identity,)).fetchone()


def _insert(conn: sqlite3.Connection, family: str, record: dict, row: dict,
            provenance: dict) -> tuple:
    """Write one record; returns (outcome, article_id, failure code or None)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-check under the write lock: a concurrent run may have committed it.
        prior = _existing(conn, record["source_identity"])
        if prior is not None:
            conn.rollback()
            if prior[1] == record["content_sha256"]:
                return DUPLICATE, prior[0], None
            return qa.HELD_SOURCE, prior[0], "E_MATERIAL_CHANGE"
        url = record["canonical_official_url"]
        if conn.execute("SELECT 1 FROM articles WHERE url=?", (url,)).fetchone():
            conn.rollback()
            return qa.HELD_SOURCE, None, "E_URL_CONFLICT"
        if is_retired(conn, url):
            conn.rollback()
            return qa.HELD_SOURCE, None, "E_RETIRED_URL"
        source_id = _ensure_source(conn, family)
        article_id = next_available_article_id(conn)
        cols = dict(row, id=article_id, url=url, source_id=source_id)
        conn.execute("INSERT INTO articles (%s) VALUES (%s)" % (
            ", ".join(cols), ", ".join("?" * len(cols))), list(cols.values()))
        prov = dict(provenance, article_id=article_id)
        conn.execute("INSERT INTO vietnam_article_provenance (%s) VALUES (%s)" % (
            ", ".join(prov), ", ".join("?" * len(prov))), list(prov.values()))
        conn.commit()
        return qa.PUBLISHED, article_id, None
    except sqlite3.IntegrityError:
        conn.rollback()
        prior = _existing(conn, record["source_identity"])
        if prior is not None and prior[1] == record["content_sha256"]:
            return DUPLICATE, prior[0], None
        raise
    except BaseException:
        conn.rollback()
        raise


# ── Second pass ──────────────────────────────────────────────────────────────

def model_second_pass(analyzer, family: str) -> Callable[[dict, str, str, dict], dict]:
    """The bounded QA second pass on the shared client, budget and telemetry.

    It is billed under the summary task: it is one more call about the summary.
    It runs under the family's Vietnam system prompt, never the China default.
    """
    from analysis.analyzer import ANALYSIS_MODEL
    from analysis.usage import TASK_SUMMARY
    system = [{"type": "text", "text": profile_for_source(family).analysis_system_prompt}]

    def run(record, title, body, result):
        raw = analyzer._call(qa.second_pass_messages(title, body, result), max_tokens=300,
                             temperature=0.0, system=system, task=TASK_SUMMARY)
        data = analyzer._parse_task_json(raw, TASK_SUMMARY, ANALYSIS_MODEL)
        if not isinstance(data, dict) or not isinstance(data.get("ok"), bool):
            return {"ok": None, "error": "malformed_second_pass"}
        return {"ok": data["ok"], "reason": str(data.get("reason") or "")[:300]}
    return run


# ── One run ──────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_family(conn: sqlite3.Connection, state_repo, commit: str, family: str, *,
               api, as_of_utc, source_use: SourceUse, analyzer, ledger_path: Path,
               run_id: str, second_pass: Optional[Callable] = None,
               max_second_pass: int = 5, now: Callable[[], str] = _utc_now,
               desk=None, custody: Optional[PrivateCustody] = None) -> dict:
    """Process every current version of one family's authenticated commit.

    `desk` is the registry's Vietnam entry; None reads desks/registry.json.
    `api` always reads the public repository. With `custody`, `commit` is on
    the private archive ref of `state_repo` and is authenticated there; there
    is no public fallback.
    """
    if source_use.source_family != family:
        raise BridgeError("vietnam_source_use_family_mismatch")
    if custody is not None and family != vn.MPS:
        raise BridgeError("vietnam_private_custody_is_mps_only")
    if desk is None:
        from core.desk_registry import load_registry
        desk = load_registry().get("vietnam")
    if source_use.allows("public_ipr_analysis") and not desk_promoted(desk):
        # Checked before authentication or any model call: nothing is spent.
        raise BridgeError("vietnam_desk_not_promoted")
    ledger = load_ledger(ledger_path, family)
    private = custody is not None
    packet = vn.prepare(state_repo, commit, family, private=private)
    if private:
        proof = vn.authenticate_private(packet, state_repo, custody.public_frozen_tip,
                                        api=custody.private_api, public_api=api)
        custody_report = {"mode": "private", "source_ref": vn.PRIVATE_REF,
                          "public_frozen_tip": custody.public_frozen_tip,
                          "private_attempts_verified": proof["private_attempts_verified"],
                          "latest_run": proof["latest_run"]}
    else:
        vn.authenticate(packet, api, as_of_utc)
        custody_report = {"mode": "public", "source_ref": SOURCES[family].state_branch}
    versions = preserved_versions(state_repo, commit, family, private=private)
    budget = qa.SecondPassBudget(max_second_pass)
    base_profile = profile_for_source(family)
    outcomes: List[dict] = []

    for record in packet["records"]:
        identity, sha = record["source_identity"], record["content_sha256"]
        prior_item = ledger["items"].get(identity) or {}
        item = {"source_identity": identity, "content_sha256": sha}

        def done(outcome, failures=(), article_id=None, details=None, qa_json=None):
            item.update(outcome=outcome, failures=list(failures), article_id=article_id)
            if details:
                item["details"] = details
            outcomes.append(dict(item))
            if outcome not in (DUPLICATE, SETTLED):
                same = prior_item.get("content_sha256") == sha
                attempts = (prior_item.get("attempts", 0) if same else 0) + (
                    1 if outcome in (qa.HELD_RETRYABLE, qa.HELD_ESCALATED) else 0)
                ledger["items"][identity] = {
                    "content_sha256": sha, "outcome": outcome, "failures": list(failures),
                    "attempts": attempts, "updated_utc": now(), "run_id": run_id,
                    "qa": qa_json}

        prior = _existing(conn, identity)
        if prior is not None:
            if prior[1] == sha:
                done(DUPLICATE, article_id=prior[0])
            else:
                done(qa.HELD_SOURCE, ["E_MATERIAL_CHANGE"], prior[0])
            continue
        if prior_item.get("content_sha256") == sha and prior_item.get("outcome") in (
                qa.SCREENED_OUT, qa.HELD_REVIEW, qa.HELD_ESCALATED):
            # Settled earlier; do not re-spend a model call on the same version.
            done(SETTLED)
            continue
        version = versions.get((identity, sha))
        if version is None:
            done(qa.HELD_SOURCE, ["E_SOURCE_BODY"])
            continue
        source_fails = qa.source_failures(record, version, packet["logical_date"])
        if source_fails:
            done(qa.decide(source_fails, passed_relevance=None, attempts=0), source_fails)
            continue
        if not (source_use.allows("external_model_transmission", identity)
                and source_use.allows("public_ipr_analysis", identity)):
            reason = (source_use.reason("external_model_transmission", identity)
                      or source_use.reason("public_ipr_analysis", identity))
            done(qa.HELD_RIGHTS, ["E_RIGHTS_WITHHELD"], details={"E_RIGHTS_WITHHELD": reason})
            continue

        translate = source_use.allows("public_full_translation", identity)
        profile = (base_profile if translate else
                   dataclasses.replace(base_profile, build_translation_messages=None))
        title, body = version["title_original"], version["text_original"]
        result = analyzer.analyze_record(title, body, profile)  # FatalAPIError aborts the run
        permissions = source_use.snapshot(identity)
        show_title = permissions["public_title_display"]
        projection = {
            "title_original": title if show_title else None,
            "text_original": body if permissions["public_original_storage"] else None,
            "title_english": (result or {}).get("title_english") if translate else None,
            "text_english": (result or {}).get("text_english") if translate else None,
            "summary_english": (result or {}).get("summary_english"),
        }
        same = prior_item.get("content_sha256") == sha
        attempts = (prior_item.get("attempts", 0) if same else 0) + 1
        verdict = qa.review(record, version, result, logical_date=packet["logical_date"],
                            translation_required=translate, permissions=permissions,
                            projection=projection, attempts=attempts,
                            second_pass=second_pass, budget=budget)
        if verdict.outcome != qa.PUBLISHED:
            done(verdict.outcome, verdict.failures, details=verdict.details,
                 qa_json=verdict.as_json())
            continue

        processed = now()
        row = {
            "content_hash": sha,
            "title_original": projection["title_original"],
            "text_original": projection["text_original"],
            "published_date": record["publisher_posted_date"],
            "relevance_score": result["relevance_score"],
            "relevance_reasoning": result["relevance_reasoning"],
            "passed_relevance": 1,
            "title_english": projection["title_english"],
            "text_english": projection["text_english"],
            "summary_english": projection["summary_english"],
            "analyzed_at": processed,
            "is_significant": 1 if result.get("is_significant") else 0,
            "significance_reasoning": result.get("significance_reasoning"),
            "model_id": result["model_id"],
            "prompt_version": result["prompt_version"],
        }
        provenance = {
            "source_family": family, "source_identity": identity,
            "canonical_official_url": record["canonical_official_url"],
            "publisher_posted_date": record["publisher_posted_date"],
            "content_sha256": sha, "capture_sha256": record["capture_sha256"],
            "source_git_commit": commit, "collector_commit": record["collector_commit"],
            "rights_policy_version": source_use.policy_version,
            "rights_decision_sha256": source_use.decision_sha256,
            "attribution_text": source_use.attribution_text,
            "license_terms": source_use.license_terms,
            "permissions_json": json.dumps(permissions, sort_keys=True),
            "qa_rubric_version": verdict.rubric_version,
            "qa_json": json.dumps(verdict.as_json(), sort_keys=True, ensure_ascii=False),
            "event_type": result["categories"][0],
            "terminology_version": terminology_version(),
            "translation_prompt_version": (profile.translation_prompt_version
                                           if translate else None),
            "original_withheld": 0 if projection["text_original"] else 1,
            "translation_published": 1 if projection["text_english"] else 0,
            "published_by_run": run_id, "processed_utc": processed,
        }
        outcome, article_id, code = _insert(conn, family, record, row, provenance)
        done(outcome, [code] if code else [], article_id, qa_json=verdict.as_json())

    save_ledger(ledger_path, ledger)
    counts: Dict[str, int] = {}
    for o in outcomes:
        counts[o["outcome"]] = counts.get(o["outcome"], 0) + 1
    return {
        "schema": "ipr-vietnam-daily-run/1", "run_id": run_id, "source_family": family,
        "source_git_commit": commit, "logical_date": packet["logical_date"],
        "custody": custody_report,
        "rights_policy_version": source_use.policy_version,
        "rights_decision_sha256": source_use.decision_sha256,
        "qa_rubric_version": qa.RUBRIC_VERSION, "second_pass_used": budget.used,
        "counts": counts, "outcomes": outcomes,
    }
