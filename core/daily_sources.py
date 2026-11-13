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
ATTENDED_PILOT_ENV = {"sg_mindef_releases": "IPR_SG_MINDEF_ATTENDED_PILOT_IDENTITY"}
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


def _jcg_output_check(output) -> Optional[str]:
    ok = not output["model_flagged"] and re.search(
        r"\bJCG\b|\bJapan Coast Guard\b", output["summary"]) is not None
    return None if ok else "daily_japan_jcg_flag_or_attribution_held"


def _jcg_parent(conn, identity) -> Optional[dict]:
    """The admitted JCG official link (link-only scope) in shared field names."""
    from core import japan_jcg_links
    return japan_jcg_links.read_parent(conn, identity)


SOURCES: Dict[str, DailySource] = {s.family: s for s in (
    DailySource(
        family="ph_afp_articles", desk_id="philippines", custody_ref="archive/ph-afp",
        language="en", label="AFP", publisher="Armed Forces of the Philippines",
        public_issuer="Armed Forces of the Philippines", prompt_versions=_PH_PROMPTS,
        identity_max_length=120, first_party=True,
        links="core.daily_sources:_afp_links",
        quality="processing.daily_intake:english_official_quality"),
    DailySource(
        family="ph_nsc_official_statements", desk_id="philippines",
        custody_ref="archive/ph-nsc", language="en", label="NSC",
        publisher="National Security Council", public_issuer=None,
        prompt_versions=_PH_PROMPTS, identity_max_length=120,
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
                         "sg-relevance-v2+sg-analysis-v4"),
        identity_max_length=64,
        links="core.daily_sources:_sg_links",
        quality="processing.daily_intake:english_official_quality",
        known_hold="core.daily_sources:_sg_known_hold",
        output_check="core.daily_sources:_sg_output_check",
        parent="core.daily_sources:_sg_parent",
        admission_migration="migrations.versions.m0022_singapore_mindef_source_records:is_already_applied",
        # A manifest-registered manual source: public Daily admits signed outputs,
        # never fetches MINDEF originals. Runtime source-use gates stay off.
        desk_registered=True),
    DailySource(
        # Standing first-party text family (PR #1015, Public Data License 1.0):
        # English HTML article prose only. The private branch continues the
        # preserved JCG evidence ancestry rather than starting a second copy.
        family="jp_jcg_press_en", desk_id="japan", custody_ref="archive/japan-jcg",
        language="en", label="JCG", publisher="Japan Coast Guard",
        public_issuer="Japan Coast Guard",
        prompt_versions=("jp-jcg-relevance-v1+jp-jcg-analysis-v1",),
        identity_max_length=64,
        links="core.daily_sources:_jcg_links",
        quality="processing.daily_intake:english_official_quality",
        known_hold="core.daily_sources:_jcg_known_hold",
        output_check="core.daily_sources:_jcg_output_check",
        parent="core.daily_sources:_jcg_parent",
        admission_migration="migrations.versions.m0023_japan_jcg_source_records:is_already_applied",
        # One owner switch for both public halves: official-link parents and
        # machine outputs. Off stops admission of either.
        public_switch="JP_JCG_LINKS_ENABLED",
        # A manifest-registered manual source: public Daily admits signed links
        # and outputs, never fetches the Japan Coast Guard site.
        desk_registered=True),
)}


def source_for(family) -> Optional[DailySource]:
    return SOURCES.get(family) if type(family) is str else None
