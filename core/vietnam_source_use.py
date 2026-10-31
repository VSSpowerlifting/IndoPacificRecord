"""Standing, source-specific source-use policy for the Vietnam Desk.

Each ministry source family has its own permissions, held separately:

  collect_preserve             operate the private collector and keep originals
  external_model_transmission  send the original text to an external model
  public_original_storage      store the Vietnamese original in public Git/SQLite
  public_full_translation      publish a full English translation
  public_excerpt               publish a short quotation of the original
  public_ipr_analysis          publish IPR's own summary and classification
  public_title_display         show the original title on a public page

Nothing is granted here. Every family starts held with a reason code; the
existing record (docs/VIETNAM_FULL_OPERATION_2026-10-17.md, the private
cutover) establishes neither MPS reuse terms nor permission to send MPS text to
a model, and MOIT has a separate written-consent and robots hold.

A grant exists only in an owner-sealed decision (HMAC under DOMAIN, the same
envelope as other regional reviews). The seal authenticates the owner's
decision, not legal rights. An MPS-specific independently documented source-use
assessment may be recorded instead of implying every reporting use needs a
publisher license; it must separately cover full-body external model input.
This is never inferred from the China Desk, a source URL, or attribution.
MOIT retains its existing express-terms/permission and robots requirements.
Fixture keys exist only in tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, FrozenSet, Optional

from core.collection.vietnam_sources import PROCESSING_SOURCES as SOURCES
from core.regional_reviewed_evidence import _canonical, verify_review_seal
from core.regional_typed_source_use_decision import RIGHTS

import hashlib

SCHEMA = "ipr-vietnam-source-use-decision/1"
DOMAIN = b"IPR-VIETNAM-SOURCE-USE-DECISION-v1\n"
POLICY_VERSION = "vn-source-use-2026-10-19.1"
# This records an owner-reviewed legal/source-use rationale, NOT a publisher license.
# Only MPS may select it; public reproduction/translation remains separately held.
INDEPENDENT_ASSESSMENT = "documented_independent_source_use_assessment"
ADMINISTRATIVE_ASSESSMENT = "documented_administrative_document_assessment"
VPCP = "vn_vpcp_official_documents_vi"
SOURCE_USE_BASES = RIGHTS | frozenset((INDEPENDENT_ASSESSMENT, ADMINISTRATIVE_ASSESSMENT))

PERMISSIONS = (
    "collect_preserve", "external_model_transmission", "public_original_storage",
    "public_full_translation", "public_excerpt", "public_ipr_analysis",
    "public_title_display",
)

# A permission is usable only when every permission it depends on is too.
REQUIRES = {
    "external_model_transmission": ("collect_preserve",),
    "public_original_storage": ("collect_preserve", "public_title_display"),
    "public_full_translation": ("external_model_transmission", "public_title_display"),
    "public_excerpt": ("collect_preserve", "public_title_display"),
    "public_ipr_analysis": ("external_model_transmission", "public_title_display"),
    "public_title_display": ("collect_preserve",),
}

MPS = "vn_mps_foreign_affairs_vi"
_MOIT_HOLD = "moit_written_consent_and_robots_review_required"
_MPS_HOLD = "mps_reuse_and_model_terms_not_established"

# Standing holds, per family and permission. A sealed decision replaces them.
STANDING_HOLDS: Dict[str, Dict[str, str]] = {
    slug: {perm: ("vpcp_owner_source_use_decision_pending" if slug == VPCP else _MPS_HOLD if slug == MPS else _MOIT_HOLD) for perm in PERMISSIONS}
    for slug in SOURCES
}

_DECISION_KEYS = {
    "schema", "source_family", "policy_version", "decided_on", "decided_by",
    "rights_basis_type", "rights_basis_reference", "robots_review_reference",
    "permissions", "attribution_text", "license_terms", "excerpt_max_chars",
    "item_exceptions", "expires_on",
}


class SourceUseError(ValueError):
    """A decision is malformed, unsealed, expired or names no rights basis."""


def _need(ok, code):
    if not ok:
        raise SourceUseError(code)


def _day(value, code):
    _need(isinstance(value, str), code)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SourceUseError(code) from exc
    _need(parsed.isoformat() == value, code)
    return parsed


def _text(value, code, min_len=1):
    _need(isinstance(value, str) and value == value.strip()
          and len(value) >= min_len, code)
    return value


@dataclass(frozen=True)
class SourceUse:
    """What may be done with one family's originals, and why not otherwise."""
    source_family: str
    granted: FrozenSet[str]
    holds: Dict[str, str]
    decision_sha256: Optional[str] = None
    attribution_text: Optional[str] = None
    license_terms: Optional[str] = None
    excerpt_max_chars: Optional[int] = None
    item_withholds: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    policy_version: str = POLICY_VERSION

    def _dependencies(self, permission: str):
        # MPS and VPCP publish a separately authored factual English headline,
        # not the Vietnamese original. Analysis need not inherit title reuse.
        if SOURCES[self.source_family].analysis_headline and permission == "public_ipr_analysis":
            return ("external_model_transmission",)
        return REQUIRES.get(permission, ())

    def allows(self, permission: str, source_identity: Optional[str] = None) -> bool:
        _need(permission in PERMISSIONS, "unknown_source_use_permission")
        if permission not in self.granted:
            return False
        if source_identity and permission in self.item_withholds.get(source_identity, ()):
            return False
        return all(self.allows(dep, source_identity) for dep in self._dependencies(permission))

    def reason(self, permission: str, source_identity: Optional[str] = None) -> Optional[str]:
        """The hold code for a permission that is not usable; None when usable."""
        if self.allows(permission, source_identity):
            return None
        if permission not in self.granted:
            return self.holds.get(permission, "not_granted")
        if source_identity and permission in self.item_withholds.get(source_identity, ()):
            return "item_exception"
        for dep in self._dependencies(permission):
            if not self.allows(dep, source_identity):
                return "requires_" + dep
        return "not_granted"

    def snapshot(self, source_identity: Optional[str] = None) -> Dict[str, bool]:
        return {p: self.allows(p, source_identity) for p in PERMISSIONS}


def standing(family: str) -> SourceUse:
    """The policy with no owner decision: every permission held."""
    _need(family in SOURCES, "unknown_vietnam_source_family")
    return SourceUse(family, frozenset(), dict(STANDING_HOLDS[family]))


def decision_sha256(sealed: dict) -> str:
    return hashlib.sha256(_canonical(sealed)).hexdigest()


def verify_decision(sealed: dict, secret: bytes, family: str, *, as_of: str) -> SourceUse:
    """Authenticate and validate one owner decision for one family."""
    _need(family in SOURCES, "unknown_vietnam_source_family")
    try:
        review = verify_review_seal(sealed, secret, domain=DOMAIN)
    except ValueError as exc:
        raise SourceUseError("source_use_decision_unsealed") from exc
    _need(isinstance(review, dict) and set(review) == _DECISION_KEYS,
          "source_use_decision_fields")
    _need(review["schema"] == SCHEMA, "source_use_decision_schema")
    _need(review["source_family"] == family, "source_use_decision_family")
    _need(review["policy_version"] == POLICY_VERSION, "source_use_policy_version")
    today = _day(as_of, "source_use_as_of")
    _need(_day(review["decided_on"], "source_use_decided_on") <= today,
          "source_use_decision_future")
    if review["expires_on"] is not None:
        _need(_day(review["expires_on"], "source_use_expires_on") >= today,
              "source_use_decision_expired")
    _text(review["decided_by"], "source_use_decided_by", 3)
    # Attribution is a condition of use, never a basis for it.
    basis = review["rights_basis_type"]
    _need(basis in SOURCE_USE_BASES, "source_use_rights_basis_type")
    _text(review["rights_basis_reference"], "source_use_rights_basis_reference", 12)
    if basis == INDEPENDENT_ASSESSMENT:
        _need(family == MPS, "independent_assessment_mps_only")
        # A source-specific documented determination is required; a homepage
        # or site footer is not a substitute for reviewing model-input use.
        ref = review["rights_basis_reference"]
        _need(ref.startswith("docs/engineering/") and ref.endswith(".md"),
              "independent_assessment_document_required")
    if basis == ADMINISTRATIVE_ASSESSMENT:
        _need(family == VPCP and review["rights_basis_reference"] == "docs/engineering/VIETNAM_GOVERNMENT_DOCUMENT_TEXT_2026-10-23.md", "administrative_assessment_scope")
    _text(review["attribution_text"], "source_use_attribution_text", 3)
    if review["license_terms"] is not None:
        _text(review["license_terms"], "source_use_license_terms", 3)
    if family != MPS:
        _text(review["robots_review_reference"] or "", "moit_robots_review_required", 12)
    perms = review["permissions"]
    _need(isinstance(perms, dict) and set(perms) == set(PERMISSIONS)
          and all(type(v) is bool for v in perms.values()), "source_use_permissions")
    if basis in (INDEPENDENT_ASSESSMENT, ADMINISTRATIVE_ASSESSMENT):
        _need(not any(perms[p] for p in ("public_original_storage",
                                         "public_full_translation",
                                         "public_excerpt", "public_title_display")),
              "independent_assessment_cannot_grant_source_republication")
    if family == VPCP:
        _need(not any(perms[p] for p in ("public_original_storage", "public_full_translation", "public_excerpt", "public_title_display")), "vpcp_original_republication_held")
    excerpt = review["excerpt_max_chars"]
    if perms["public_excerpt"]:
        _need(type(excerpt) is int and 1 <= excerpt <= 600, "source_use_excerpt_limit")
    else:
        _need(excerpt is None, "source_use_excerpt_limit")
    withholds: Dict[str, FrozenSet[str]] = {}
    exceptions = review["item_exceptions"]
    _need(isinstance(exceptions, list), "source_use_item_exceptions")
    for item in exceptions:
        _need(isinstance(item, dict) and set(item) == {"source_identity", "withhold", "reason"},
              "source_use_item_exception_fields")
        _need(isinstance(item["source_identity"], str)
              and item["source_identity"].startswith(SOURCES[family].prefix),
              "source_use_item_exception_identity")
        _need(isinstance(item["withhold"], list) and item["withhold"]
              and set(item["withhold"]) <= set(PERMISSIONS), "source_use_item_exception_withhold")
        _text(item["reason"], "source_use_item_exception_reason", 3)
        _need(item["source_identity"] not in withholds, "source_use_item_exception_duplicate")
        withholds[item["source_identity"]] = frozenset(item["withhold"])
    granted = frozenset(p for p, ok in perms.items() if ok)
    holds = {p: "owner_decision_withholds" for p in PERMISSIONS if p not in granted}
    return SourceUse(family, granted, holds, decision_sha256(sealed),
                     review["attribution_text"], review["license_terms"], excerpt,
                     withholds)


def owner_decision_request(family: str) -> dict:
    """The exact decision the owner must make; an unsigned, all-held template."""
    _need(family in SOURCES, "unknown_vietnam_source_family")
    src = SOURCES[family]
    return {
        "source_family": family,
        "publisher": src.publisher,
        "listing": src.listing,
        "current_holds": dict(STANDING_HOLDS[family]),
        "questions": {
            "collect_preserve": "May IPR keep operating the private collector and preserving originals from this listing?",
            "external_model_transmission": "May the original Vietnamese text be sent to an external model provider (Anthropic) for translation and analysis?",
            "public_original_storage": "May the Vietnamese original be stored in the public pla_watch.db and public Git history?",
            "public_full_translation": "May IPR publish a complete machine English translation of each article?",
            "public_excerpt": "May IPR publish short quotations, and up to how many characters?",
            "public_ipr_analysis": "May IPR publish its own English summary and event classification of each article?",
            "public_title_display": "May IPR show the original Vietnamese title with a link to the official page?",
        },
        "evidence_required": [
            "rights_basis_type: one of " + ", ".join(sorted(
                SOURCE_USE_BASES if family in (MPS, VPCP) else RIGHTS))
            + " (a site footer or attribution line is not a basis)",
            "rights_basis_reference: explicit official terms/permission, or for MPS/VPCP "
            "a dated source-specific independent source-use assessment in docs/engineering/ "
            "covering full-body Anthropic input, provenance, applicable law and "
            "its limits; the assessment is not a publisher license",
            "attribution_text and any license_terms the basis imposes",
        ] + ([] if family == MPS else [
            "robots_review_reference: the dated robots.txt / access review for " + ("vanban.chinhphu.vn and datafiles.chinhphu.vn" if family == VPCP else "moit.gov.vn"),
        ]),
        "unsigned_template": {
            "schema": SCHEMA, "source_family": family, "policy_version": POLICY_VERSION,
            "decided_on": None, "decided_by": None, "rights_basis_type": None,
            "rights_basis_reference": None, "robots_review_reference": None,
            "permissions": {p: False for p in PERMISSIONS},
            "attribution_text": None, "license_terms": None, "excerpt_max_chars": None,
            "item_exceptions": [], "expires_on": None,
        },
        "public_release_authorized": False,
    }
