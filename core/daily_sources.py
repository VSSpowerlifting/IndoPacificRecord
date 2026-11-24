"""One definition per source family in the shared private-source Daily lane.

The lifecycle (`processing/daily_intake.py`), the public projection
(`core/daily_machine_records.py`) and screening dispatch
(`processing/screening.py`) read source identity, custody, language, attribution
and source-specific checks from here instead of branching on a family name.

Grants and limits are not recorded here. Retention, model input, public
explanation, spending and exclusions stay in `config/philippines_daily_policy.json`,
which `processing.daily_intake.load_policy` validates against this registry; its
per-family object is hashed into every released output, so it must not change
shape. Collection adapters keep their own validators, referenced below by
`module:function` and resolved when called so this module imports nothing heavy.

Adding a family means one entry here, one policy object, an adapter for its
evidence and a screening profile for its desk. Unknown families are never mapped
to another desk's profile.
"""
from __future__ import annotations

import importlib
import os
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

_PH_PROMPTS = ("ph-relevance-v1+ph-analysis-v10",
               "ph-relevance-v1+ph-analysis-v11",
               "ph-relevance-v1+ph-analysis-v12",
               "ph-relevance-v1+ph-analysis-v13",
               "ph-relevance-v1+ph-analysis-v14")
_THIRD_PARTY_CREDIT = re.compile(r"(?im)^\s*(?:sumber|source|credit)\s*:")


# Attended-pilot gate. A family listed here is never handled by scheduled or
# ordinary manual Daily runs, whatever its source-policy flags say. The gate is
# open only for a deliberately dispatched run that names the one identity; the
# identity then bounds both the envelope fetch and governed admission.
# Empty since Singapore MINDEF recurring activation (DECISION_LOG 2026-11-22):
# no family is attended-only now; the mechanism stays for a future pilot.
ATTENDED_PILOT_ENV = {}
_PILOT_IDENTITY = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")


def attended_pilot_gate(family: str, environ=None) -> Tuple[bool, Optional[str]]:
    """(gated, identity): gated False means the family is not attended-only;
    gated True with identity None means the gate is closed."""
    import os
    env = os.environ if environ is None else environ
    name = ATTENDED_PILOT_ENV.get(family)
    if name is None:
        return False, None
    value = env.get(name, "")
    event = env.get("GITHUB_EVENT_NAME", "workflow_dispatch")
    if event != "workflow_dispatch" or not _PILOT_IDENTITY.fullmatch(value or ""):
        return True, None
    return True, value


def attended_only(family: str) -> bool:
    """True while a family may run only as an attended one-item pilot.

    The one-item limits in the private runner, the signer and public admission
    key on this, so ending a pilot is one reviewed edit to ATTENDED_PILOT_ENV
    (with the policy switches), not a hunt for family names.
    """
    return family in ATTENDED_PILOT_ENV


def _call(ref: str) -> Callable:
    module, _, attr = ref.partition(":")
    return getattr(importlib.import_module(module), attr)


@dataclass(frozen=True)
class DailySource:
    family: str
    desk_id: str
    custody_ref: str          # private-custody branch that holds this family
    language: str             # language tag of the preserved original
    label: str                # short public attribution, e.g. "AFP"
    publisher: str            # public institution name used in attribution
    public_issuer: Optional[str]
    prompt_versions: Tuple[str, ...]   # every pair a NEW output may carry (admission)
    identity_max_length: int  # bound for policy exclusion identifiers
    links: str                # adapter: (repo, commit) -> verified link dicts
    quality: str              # adapter: (record, reading) -> quality digest
    first_party: bool = False  # require the link record's first-party binding
    reject_credit_line: bool = False
    release_gate: Optional[str] = None  # adapter: () -> hold reason | None
    known_hold: Optional[str] = None    # adapter: record -> bool
    output_check: Optional[str] = None  # adapter: output -> hold reason | None
    # Apply output_check in private processing too, before signing, so an output
    # admission would hold for attribution is a retriable QA hold rather than a
    # signed item that never publishes. Opt-in per family.
    output_check_before_signing: bool = False
    # Families whose candidate builder narrows the original to an approved prose
    # scope: (private link fields, shadow row) -> model input body. Unset, the
    # whole preserved original is the input, as before.
    approved_input: Optional[str] = None
    # Families whose public link parent is not regional_official_source_links:
    # (conn, identity) -> normalized parent dict | None (see _dapa_parent).
    parent: Optional[str] = None
    # Extra schema the family's admission needs beyond m0015, as module:check.
    admission_migration: Optional[str] = None
    # False until the family is declared in its desk manifest. The pipeline only
    # dispatches manifest-registered manual slugs, so an undeclared family gets
    # no governed admission and no run-result row. Declaring a source on a live
    # desk changes public source listings, so it is an activation step.
    desk_registered: bool = True
    # Pairs that stay valid for an already-RELEASED record only: read and
    # rendered under the pinned policy, never accepted for a newly submitted
    # output. Distinct from prompt_versions on purpose; empty means none.
    released_prompt_versions: Tuple[str, ...] = ()
    # Owner variable that must equal "true", in addition to the source policy,
    # before the public Daily fetches or admits this family's machine-output
    # envelope. Turning it off is a rollback switch: nothing further is
    # admitted, even against a parent that is already admitted. It does not
    # withdraw records that are already public. Unset means the policy alone
    # gates the family.
    public_switch: Optional[str] = None
    # adapter: record -> the known hold's specific reason. Unset, every known
    # hold is recorded as a source semantic anomaly, as before.
    known_hold_reason: Optional[str] = None
    # Known-hold reasons that come from source-wide evidence, not from the item
    # (a failed or missing capture of the publisher's terms). The queue keeps
    # the entry's attempts, output and prior state through such a hold and
    # restores them once the hold clears; the signer neither releases nor
    # withdraws the identity meanwhile. Item-specific holds never resume.
    resumable_holds: Tuple[str, ...] = ()
    # Queue order within one private processing run. False keeps newest-first.
    # True tries never-attempted entries before retriable ones (newest-first
    # within each group), so a one-record-per-run cap cannot keep a fresh
    # version waiting behind a version still spending its retry budget. It
    # changes order only: no attempt count, budget, hold or check changes.
    first_attempts_first: bool = False
    # adapter: intake_dir -> (run-result status, fixed detail) | None. Lets a
    # family report source-wide evidence (a refused terms page) on its own
    # run-result row when the envelope alone would read as "nothing new".
    evidence_report: Optional[str] = None
    # UTC HH:MM of the private collector's scheduled cron, mirrored from its
    # workflow (cited beside each value below). With the grace window it fixes
    # which target date a healthy collection must have reached; None means no
    # cadence is declared, so no staleness verdict is applied.
    collection_cron_utc: Optional[str] = None
    # Hours after the cron slot during which the previous slot is still the
    # expected one. Observed cron-to-finish lags are 4 to 10.5 hours.
    collection_grace_hours: int = 14
    # Receipt directories (at the custody commit) holding "<run_id>.json" files
    # with the collector's exit status, written even when no ledger is.
    collection_receipt_dirs: Tuple[str, ...] = ()
    # Cutover floor for a family whose custody holds ledgers written before its
    # collector adopted the shared schema: ledger file names that sort at or
    # below it are not read (core.collection.attempts.read_custody). None reads
    # every ledger.
    collection_ledger_after: Optional[str] = None

    def collection_expectation(self) -> Tuple[Optional[str], int]:
        """(cron, grace hours) for the freshness verdict; no cron for an
        attended pilot, whose collection is operator-run, not scheduled."""
        if attended_only(self.family):
            return None, self.collection_grace_hours
        return self.collection_cron_utc, self.collection_grace_hours

    def signs_collection(self) -> bool:
        """True when the private signer emits schema /2 with a signed
        collection block: exactly the families with a declared, unattended
        cadence. Others (attended pilot, no cadence) keep signing /1."""
        return self.collection_expectation()[0] is not None

    def collection_attempt(self, repo, commit) -> dict:
        """Signed-facts block read from custody at ``commit``; never raises."""
        from core.collection import attempts
        return attempts.read_custody(repo, commit, self.family,
                                     receipt_dirs=self.collection_receipt_dirs,
                                     ledger_after=self.collection_ledger_after)

    def evidence_outcome(self, intake_dir) -> Optional[Tuple[str, str]]:
        return _call(self.evidence_report)(intake_dir) if self.evidence_report else None

    def public_switch_on(self, environ=None) -> bool:
        env = os.environ if environ is None else environ
        return self.public_switch is None or env.get(self.public_switch) == "true"

    @property
    def key_env(self) -> str:
        return "DAILY_" + self.family.upper() + "_KEY"

    def verified_links(self, repo, commit) -> List[dict]:
        return _call(self.links)(repo, commit, self)

    def quality_check(self, record, reading):
        return _call(self.quality)(record, reading)

    def release_hold(self) -> Optional[str]:
        """Source-wide gate that currently blocks processing and publication."""
        return _call(self.release_gate)() if self.release_gate else None

    def rights_hold(self, record) -> Optional[str]:
        """Per-record first-party binding, from the regional link family table."""
        if not self.first_party:
            return None
        from core.crossdesk_official_metadata_candidates import FAMILIES
        want = FAMILIES[self.family]
        issuer = record.get("official_issuer")
        first_party = (
            record.get("official_publisher") == want["publisher"]
            and (issuer == want["issuer"] if want["issuer"]
                 else issuer in (None, want["publisher"]))
            and record.get("official_republisher") is None
            and not (self.reject_credit_line
                     and _THIRD_PARTY_CREDIT.search(record["body"])))
        return None if first_party else "source_rights_not_first_party"

    def is_held_source(self, record) -> bool:
        return bool(self.known_hold and _call(self.known_hold)(record))

    def held_source_reason(self, record) -> Optional[str]:
        """The known hold's reason, or None when the record is not held."""
        if not self.is_held_source(record):
            return None
        if self.known_hold_reason:
            return _call(self.known_hold_reason)(record) or "source_semantic_anomaly"
        return "source_semantic_anomaly"

    def output_hold(self, output) -> Optional[str]:
        return _call(self.output_check)(output) if self.output_check else None

    def model_input(self, private, row) -> str:
        return _call(self.approved_input)(private, row) if self.approved_input else row["text_original"]

    def parent_link(self, conn, identity) -> Optional[dict]:
        return _call(self.parent)(conn, identity)

    def admission_ready(self, conn) -> bool:
        return _call(self.admission_migration)(conn) if self.admission_migration else True


def _afp_links(repo, commit, source):
    from core.ph_afp_release_validator import verify_history, candidate_packet
    verify_history(repo, commit)
    return candidate_packet(repo, commit)["records"]


def _kemhan_links(repo, commit, source):
    from core.indonesia_kemhan_release_validator import verify_history, candidate_packet
    verify_history(repo, commit)
    return candidate_packet(repo, commit)["records"]


def _nsc_links(repo, commit, source):
    from core.ph_nsc_official_link_admission import prepare
    return prepare(repo, commit, source.custody_ref)["links"]


def _nsc_category_gate() -> Optional[str]:
    from core.ph_nsc_official_link_admission import load_policy
    return None if load_policy()["category_anomaly_resolved"] else "nsc_category_anomaly"


def _kemhan_known_hold(record) -> bool:
    from core.indonesia_kemhan_release_validator import HELD_IDENTITY
    return record["source_identity"] == HELD_IDENTITY or bool(record.get("semantic_exception_hold"))


def _kemhan_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and "Kemhan" in output["summary"]
    return None if ok else "daily_indonesia_flag_or_attribution_held"


def _dapa_links(repo, commit, source):
    """Every pinned DAPA row, each with its candidate-builder disposition.

    The builder authenticates the page's Type 0 text mark, the page-to-HWPX
    binding, sole DAPA issuance and the prose screens from the exact
    hash-bound bytes at this commit (owner option A, standing eligibility,
    7 Nov 2026). Binding the HWPX to the marked page does not prove the two
    texts equivalent; that limit is accepted, not verified. Held and refused
    rows are returned with fixed reason codes so the lifecycle records them.
    Approved paragraphs travel only under ``_`` keys, which the lifecycle
    strips before anything is persisted.
    """
    import hashlib
    import json
    import sqlite3
    import subprocess
    import tempfile
    from pathlib import Path
    from core.korea_dapa_private_to_production import version_hash
    from core.korea_dapa_record_candidate import CandidateHold, build_candidate

    def show(path):
        return subprocess.run(["git", "-C", str(repo), "show", commit + ":" + path],
                              check=True, capture_output=True).stdout

    links = []
    with tempfile.TemporaryDirectory(prefix="ipr-private-dapa-") as tmp:
        tmp = Path(tmp)
        db = tmp / "shadow.db"
        db.write_bytes(show("state/shadow.db"))
        db_sha = hashlib.sha256(db.read_bytes()).hexdigest()
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            rows = conn.execute(
                "SELECT source_identity,url,published_date,first_seen_run,capture_sha256,"
                "content_sha256,metadata_json FROM shadow_records WHERE source_slug=? "
                "ORDER BY source_identity", (source.family,)).fetchall()
        for ident, url, day, run, page_sha, text_sha, meta in rows:
            link = {"source_identity": ident, "canonical_official_url": url,
                    "publisher_posted_date": day, "official_issuer": "kr_dapa",
                    "official_publisher": None, "official_republisher": "kr_policy_briefing",
                    "first_seen_run": run}
            try:
                hwpx_sha = json.loads(meta or "{}").get("document_capture_sha256")
                if type(hwpx_sha) is not str or len(hwpx_sha) != 64:
                    raise CandidateHold("document_capture_missing")
                # The same version hash the private-to-production packet binds
                # into the admitted link-only parent (candidate_version_sha256).
                link["metadata_version_sha256"] = version_hash({
                    "source_identity": ident, "canonical_official_url": url,
                    "publisher_posted_date": day, "original_text_sha256": text_sha,
                    "publisher_html_sha256": page_sha, "original_hwpx_sha256": hwpx_sha})
                hwpx, page = tmp / (hwpx_sha + ".hwpx"), tmp / (page_sha + ".html")
                hwpx.write_bytes(show("state/captures/" + hwpx_sha + ".bin"))
                page.write_bytes(show("state/captures/" + page_sha + ".bin"))
                receipt, private = build_candidate(db, db_sha, ident, hwpx,
                                                   page_capture_path=page)
                link.update(dapa_status=receipt["status"],
                            dapa_reasons=sorted(receipt.get("reason_codes") or []))
                if receipt["status"] == "CANDIDATE" and private:
                    link["_paragraphs"] = private
            except CandidateHold as exc:
                link.update(dapa_status="HOLD", dapa_reasons=[str(exc)])
            except subprocess.CalledProcessError:
                link.update(dapa_status="HOLD", dapa_reasons=["capture_missing_at_pin"])
            links.append(link)
    return links


# Lead and body only. Annotations (*, ※) and quotations whose speaker
# attribution needs human review are excluded from model input.
_DAPA_INPUT_ROLES = ("lead", "body")


def _dapa_approved_input(private, row) -> str:
    paragraphs = private.get("_paragraphs") or []
    return "\n\n".join(p["text"] for p in sorted(paragraphs, key=lambda p: p["index"])
                         if p["role"] in _DAPA_INPUT_ROLES)


def _dapa_known_hold(record) -> bool:
    from core.korea_dapa_record_candidate import REFUSED_IDENTITIES
    if record["source_identity"] in REFUSED_IDENTITIES:
        return True
    # Output records carry no candidate status; they exist only for versions
    # that were CANDIDATE when processed, and admission re-binds the parent.
    return "dapa_status" in record and record["dapa_status"] != "CANDIDATE"


def _dapa_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and re.search(r"\bDAPA\b", output["summary"]) is not None
    return None if ok else "daily_dapa_flag_or_attribution_held"


def _dapa_parent(conn, identity) -> Optional[dict]:
    """The admitted DAPA official link, link-only scope, in shared field names.

    korea_official_source_records keeps no first-seen run; the candidate
    version hash and the text/page hashes bind the version instead.
    """
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='korea_official_source_records'").fetchone():
        return None
    row = conn.execute(
        "SELECT canonical_official_url,publisher_posted_date,candidate_version_sha256,"
        "original_text_sha256,publisher_html_sha256,original_title_sha256 "
        "FROM korea_official_source_records WHERE source_identity=? "
        "AND official_issuer='kr_dapa' AND public_scope='official_link_only'",
        (identity,)).fetchone()
    if row is None:
        return None
    keys = ("canonical_official_url", "publisher_posted_date", "metadata_version_sha256",
            "content_sha256", "capture_sha256", "title_sha256")
    return dict(zip(keys, row))


def _sg_links(repo, commit, source) -> list:
    """Singapore MINDEF release identities in the pinned private custody checkout.

    ``verified_source`` reconciles every row to the pinned bytes; the link rows
    carry hashes of the private original, never its text.
    """
    from core import singapore_mindef_links
    return singapore_mindef_links.links_from_custody(repo, commit, source.family)


def _sg_known_hold(record) -> bool:
    """The two speech releases that source review excluded stay held."""
    from core import singapore_mindef_links
    return record["source_identity"] in singapore_mindef_links.HELD_IDENTITIES


def _sg_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and re.search(r"\bMINDEF\b", output["summary"]) is not None
    return None if ok else "daily_singapore_flag_or_attribution_held"


def _sg_parent(conn, identity) -> Optional[dict]:
    """The admitted MINDEF official link (link-only scope) in shared field names."""
    from core import singapore_mindef_links
    return singapore_mindef_links.read_parent(conn, identity)


def _jcg_links(repo, commit, source) -> list:
    """JCG English release identities in the pinned private custody checkout.

    Each link carries hashes of the private original, never its text, and a
    scope hold when the row is not the published HTML text alone.
    """
    from core import japan_jcg_links
    return japan_jcg_links.links_from_custody(repo, commit, source.family)


def _jcg_known_hold(record) -> bool:
    """A row outside the standing HTML-text family is never model input."""
    return bool(record.get("jcg_scope_hold"))


def _jcg_known_hold_reason(record) -> Optional[str]:
    return record.get("jcg_scope_hold") or None


# Source-wide policy-evidence holds from core.japan_jcg_rights. A changed or
# conflicting policy text is not here: it needs a reviewed decision.
JCG_RESUMABLE_HOLDS = (
    "jcg_rights_policy_capture_failed",
    "jcg_rights_policy_capture_missing",
    "jcg_rights_policy_capture_not_authenticated",
    "jcg_rights_policy_capture_hash_mismatch",
    "jcg_rights_policy_replay_failed",
    "jcg_rights_standing_license_missing_changed_or_stale",
)


def _jcg_evidence_report(intake_dir) -> Optional[Tuple[str, str]]:
    """The latest JCG run's failed terms evidence, from the signed link envelope.

    Only an authenticated envelope counts; a missing or refused one is
    reported by the link-admission step itself. Codes only, never content.
    """
    import json
    from pathlib import Path
    from core import japan_jcg_links
    from core.collection import status as st
    path = Path(intake_dir) / (japan_jcg_links.FAMILY + ".links.json")
    if not path.is_file() or path.stat().st_size > japan_jcg_links.MAX_ENVELOPE_BYTES:
        return None
    try:
        packet = japan_jcg_links.authenticated_packet(
            json.loads(path.read_text()), key=os.environ.get(japan_jcg_links.KEY_ENV, ""))
    except (japan_jcg_links.LinkRefused, ValueError):
        return None
    evidence = packet.get("source_evidence")
    if evidence is None or evidence["site_terms"] in (st.OK, "not_recorded"):
        return None
    terms = evidence["site_terms"]
    refused = terms in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED)
    status = terms if terms in (st.AUTH_FAILURE, st.ACCESS_CHALLENGED, st.TIMEOUT,
                                st.FETCH_FAILURE) else st.FETCH_FAILURE
    return status, "%s: site terms %s, listing %s; queued outputs held, public records unchanged" % (
        "jcg_site_terms_access_refused" if refused else "jcg_site_terms_unavailable",
        terms, evidence["listing"])


def _jcg_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and re.search(
        r"\bJCG\b|\bJapan Coast Guard\b", output["summary"]) is not None
    return None if ok else "daily_japan_jcg_flag_or_attribution_held"


def _jcg_parent(conn, identity) -> Optional[dict]:
    """The admitted JCG official link (link-only scope) in shared field names."""
    from core import japan_jcg_links
    return japan_jcg_links.read_parent(conn, identity)



def _uscc_links(repo, commit, source) -> list:
    """USCC press-release identities in the pinned private custody checkout.

    Every row is re-qualified against its own pinned capture under the
    standing-family assessment; eligible rows carry the unquoted Commission
    narrative privately, held rows a hold code and no prose.
    """
    from core import uscc_press_links
    return uscc_press_links.links_from_custody(repo, commit, source.family)


def _uscc_approved_input(private, row) -> str:
    # Only the qualifier's included narrative paragraphs: never the stored
    # body, whose quotations, boilerplate and linked-work notices are excluded.
    return private.get("_narrative") or ""


def _uscc_known_hold(record) -> bool:
    from core.uscc_offline_input import HELD_IDENTITIES
    return bool(record.get("uscc_hold")) or record["source_identity"] in HELD_IDENTITIES


def _uscc_known_hold_reason(record) -> Optional[str]:
    from core.uscc_offline_input import HELD_IDENTITIES
    if record.get("uscc_hold"):
        return record["uscc_hold"]
    return "uscc_identity_held_individually" if record["source_identity"] in HELD_IDENTITIES else None


def _uscc_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and re.search(r"\bUSCC\b", output["summary"]) is not None
    return None if ok else "daily_us_uscc_flag_or_attribution_held"


def _uscc_parent(conn, identity) -> Optional[dict]:
    """The admitted USCC official press-release link (link-only scope)."""
    from core import uscc_press_links
    return uscc_press_links.read_parent(conn, identity)

# Cutover floor for archive/uscc-press: the lead-verified basename of the last
# pre-schema ledger in custody at release time. Pre-schema ledgers carry result
# "success"/"hold" and no target_date, target_date_source or health, so
# read_custody would report the whole custody unreadable. Shared-schema ledgers
# (named "%Y%m%dT%H%M%SZ-<run_id>.json") sort after it and are read as usual.
# If the pre-schema collector writes another ledger before the first
# shared-schema ledger lands, the lead moves this floor to that ledger.
USCC_LEDGER_AFTER = "20261122T183844Z-45056204824-1.json"

SOURCES: Dict[str, DailySource] = {s.family: s for s in (
    DailySource(
        family="ph_afp_articles", desk_id="philippines", custody_ref="archive/ph-afp",
        language="en", label="AFP", publisher="Armed Forces of the Philippines",
        public_issuer="Armed Forces of the Philippines", prompt_versions=_PH_PROMPTS,
        identity_max_length=120, first_party=True,
        # private afp_private_first_collector.yml: cron '40 6 * * *'
        collection_cron_utc="06:40", collection_receipt_dirs=("private_attempts",),
        links="core.daily_sources:_afp_links",
        quality="processing.daily_intake:english_official_quality"),
    DailySource(
        family="ph_nsc_official_statements", desk_id="philippines",
        custody_ref="archive/ph-nsc", language="en", label="NSC",
        publisher="National Security Council", public_issuer=None,
        prompt_versions=_PH_PROMPTS, identity_max_length=120,
        # private nsc_private_first_collector.yml: cron '10 10 * * *'
        collection_cron_utc="10:10", collection_receipt_dirs=("private_attempts",),
        links="core.daily_sources:_nsc_links",
        quality="processing.daily_intake:english_official_quality",
        release_gate="core.daily_sources:_nsc_category_gate"),
    DailySource(
        family="id_kemhan_news", desk_id="indonesia", custody_ref="archive/indonesia-kemhan",
        language="id", label="Kemhan",
        publisher="Kementerian Pertahanan Republik Indonesia", public_issuer=None,
        prompt_versions=("id-relevance-v1+id-analysis-v6",), identity_max_length=2000,
        # The one published Record (2026-10-23) was released under v4; it stays
        # readable. No other superseded Indonesia pair was ever released.
        released_prompt_versions=("id-relevance-v1+id-analysis-v4",),
        first_party=True, reject_credit_line=True,
        # private indonesia_private_first_collector.yml: cron '17 17 * * *'
        collection_cron_utc="17:17", collection_receipt_dirs=("state/private_attempts",),
        links="core.daily_sources:_kemhan_links",
        quality="processing.indonesia_quality:quality_check",
        known_hold="core.daily_sources:_kemhan_known_hold",
        output_check="core.daily_sources:_kemhan_output_check"),
    DailySource(
        family="kr_policy_dapa_releases", desk_id="korea",
        custody_ref="archive/korea-dapa-policy-briefing", language="ko", label="DAPA",
        publisher="Defense Acquisition Program Administration",
        public_issuer="Defense Acquisition Program Administration",
        prompt_versions=("kr-dapa-relevance-v1+kr-dapa-analysis-v1",),
        identity_max_length=64,
        links="core.daily_sources:_dapa_links",
        quality="processing.korea_dapa_quality:quality_check",
        known_hold="core.daily_sources:_dapa_known_hold",
        output_check="core.daily_sources:_dapa_output_check",
        approved_input="core.daily_sources:_dapa_approved_input",
        parent="core.daily_sources:_dapa_parent",
        admission_migration="migrations.versions.m0021_dapa_daily_machine_parent:is_already_applied",
        desk_registered=False),
    DailySource(
        family="sg_mindef_releases", desk_id="singapore",
        custody_ref="archive/singapore-mindef-daily", language="en", label="MINDEF",
        publisher="Ministry of Defence, Singapore",
        public_issuer="Ministry of Defence, Singapore",
        prompt_versions=("sg-relevance-v2+sg-analysis-v2",
                         "sg-relevance-v2+sg-analysis-v3",
                         "sg-relevance-v2+sg-analysis-v4",
                         "sg-relevance-v2+sg-analysis-v5",
                         "sg-relevance-v2+sg-analysis-v6"),
        identity_max_length=64,
        links="core.daily_sources:_sg_links",
        quality="processing.daily_intake:english_official_quality",
        known_hold="core.daily_sources:_sg_known_hold",
        output_check="core.daily_sources:_sg_output_check",
        output_check_before_signing=True,
        parent="core.daily_sources:_sg_parent",
        admission_migration="migrations.versions.m0022_singapore_mindef_source_records:is_already_applied",
        # private singapore_mindef_private_first_collector.yml: cron '37 10 * * *'
        collection_cron_utc="10:37",
        # A manifest-registered manual source: public Daily admits signed links
        # and outputs, never fetches MINDEF originals. Recurring since the
        # founder's 22 Nov approval (DECISION_LOG 2026-11-22).
        desk_registered=True),
    DailySource(
        # Standing first-party text family (PR #1015, Public Data License 1.0):
        # English HTML article prose only. The private branch continues the
        # preserved JCG evidence ancestry rather than starting a second copy.
        family="jp_jcg_press_en", desk_id="japan", custody_ref="archive/japan-jcg",
        language="en", label="JCG", publisher="Japan Coast Guard",
        public_issuer="Japan Coast Guard",
        # v3 is what the processor now emits; v2 and v1 stay admissible for
        # any output signed before each switch (none was complete at either).
        prompt_versions=("jp-jcg-relevance-v1+jp-jcg-analysis-v3",
                         "jp-jcg-relevance-v1+jp-jcg-analysis-v2",
                         "jp-jcg-relevance-v1+jp-jcg-analysis-v1"),
        identity_max_length=64,
        # private japan_jcg_private_first_collector.yml: cron '13 19 * * *'
        collection_cron_utc="19:13",
        links="core.daily_sources:_jcg_links",
        quality="processing.daily_intake:english_official_quality",
        known_hold="core.daily_sources:_jcg_known_hold",
        known_hold_reason="core.daily_sources:_jcg_known_hold_reason",
        resumable_holds=JCG_RESUMABLE_HOLDS,
        first_attempts_first=True,
        evidence_report="core.daily_sources:_jcg_evidence_report",
        output_check="core.daily_sources:_jcg_output_check",
        parent="core.daily_sources:_jcg_parent",
        admission_migration="migrations.versions.m0023_japan_jcg_source_records:is_already_applied",
        # One owner switch for both public halves: official-link parents and
        # machine outputs. Off stops admission of either.
        public_switch="JP_JCG_LINKS_ENABLED",
        # A manifest-registered manual source: public Daily admits signed links
        # and outputs, never fetches the Japan Coast Guard site.
        desk_registered=True),
    DailySource(
        # Commission-authored institutional press releases under the founder's
        # standing-family assessment (DECISION_LOG 2026-11-03/04/07): only the
        # unquoted narrative the qualifier includes reaches a model. Quotations,
        # linked reports, testimony, attachments and media never do.
        family="us_uscc_press_en", desk_id="us-indopacific", custody_ref="archive/uscc-press",
        language="en", label="USCC",
        publisher="U.S.-China Economic and Security Review Commission",
        public_issuer="U.S.-China Economic and Security Review Commission",
        prompt_versions=("us-uscc-relevance-v1+us-uscc-analysis-v1",),
        identity_max_length=140,
        links="core.daily_sources:_uscc_links",
        approved_input="core.daily_sources:_uscc_approved_input",
        quality="processing.daily_intake:english_official_quality",
        known_hold="core.daily_sources:_uscc_known_hold",
        known_hold_reason="core.daily_sources:_uscc_known_hold_reason",
        output_check="core.daily_sources:_uscc_output_check",
        parent="core.daily_sources:_uscc_parent",
        # Observed 2026-11-23 (private queue at state/shared-daily f61c044):
        # the newest release was retriable after a factual-QA hold while the
        # only other bindable release had 0 attempts and, under newest-first
        # with one record per run, would wait out the first one's retries.
        # Order only; attempts, budget, cap and checks are unchanged.
        first_attempts_first=True,
        admission_migration="migrations.versions.m0024_uscc_press_source_records:is_already_applied",
        # One owner switch for both public halves, off by default.
        public_switch="US_USCC_LINKS_ENABLED",
        # A manifest-registered manual source (2026-11-22 founder activation):
        # public Daily admits signed links and outputs, never fetches uscc.gov.
        desk_registered=True,
        # private uscc_private_first_collector.yml: cron '35 11 * * *'. Every
        # attempt writes state/private_attempts/<run_id>-<attempt>.json with its
        # exit status, so a refusal or crash that wrote no ledger is reported.
        collection_cron_utc="11:35", collection_receipt_dirs=("state/private_attempts",),
        # Custody keeps the pre-schema ledger(s) of the first collector forever
        # (the collector refuses to modify or delete under state/ledger).
        collection_ledger_after=USCC_LEDGER_AFTER),
)}


def source_for(family) -> Optional[DailySource]:
    return SOURCES.get(family) if type(family) is str else None
