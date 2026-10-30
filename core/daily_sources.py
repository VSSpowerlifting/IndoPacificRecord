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
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

_PH_PROMPTS = ("ph-relevance-v1+ph-analysis-v10",
               "ph-relevance-v1+ph-analysis-v11",
               "ph-relevance-v1+ph-analysis-v12",
               "ph-relevance-v1+ph-analysis-v13")
_THIRD_PARTY_CREDIT = re.compile(r"(?im)^\s*(?:sumber|source|credit)\s*:")


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
    prompt_versions: Tuple[str, ...]   # every accepted relevance+analysis pair
    identity_max_length: int  # bound for policy exclusion identifiers
    links: str                # adapter: (repo, commit) -> verified link dicts
    quality: str              # adapter: (record, reading) -> quality digest
    first_party: bool = False  # require the link record's first-party binding
    reject_credit_line: bool = False
    release_gate: Optional[str] = None  # adapter: () -> hold reason | None
    known_hold: Optional[str] = None    # adapter: record -> bool
    output_check: Optional[str] = None  # adapter: output -> hold reason | None

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
        prompt_versions=("id-relevance-v1+id-analysis-v4",), identity_max_length=2000,
        first_party=True, reject_credit_line=True,
        links="core.daily_sources:_kemhan_links",
        quality="processing.indonesia_quality:quality_check",
        known_hold="core.daily_sources:_kemhan_known_hold",
        output_check="core.daily_sources:_kemhan_output_check"),
)}


def source_for(family) -> Optional[DailySource]:
    return SOURCES.get(family) if type(family) is str else None
