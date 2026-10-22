"""Strictly pin the owner's 2026-10-17 DAPA link-only permission.

Policy is a narrow source-family authorization, NOT evidence that a specific
government article was captured, reviewed or released.
"""
from __future__ import annotations

import json
from pathlib import Path

from core import korea_official_metadata_admission as mnd

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/korea_dapa_official_link_automatic_admission.json"

EXPECTED = {
    "schema": "ipr-korea-dapa-official-link-policy/1",
    "owner_decision_date": "2026-10-17",
    "desk": "korea",
    "source_family": "kr_policy_dapa_releases",
    "issuer": "kr_dapa",
    "republisher": "kr_policy_briefing",
    "government_portal_issuer_code": "B00008",
    "source_identity_prefix": "korea-dapa-policy:",
    "canonical_url_prefix": mnd.PREFIX,
    "automatic_admission_of_verified_link_metadata": True,
    "public_fields": mnd.FIELDS,
    "source_capture_and_version_verification_required": True,
    "private_original_custody_required": True,
    "publish_original_korean_titles": False,
    "publish_original_text": False,
    "publish_document_media": False,
    "publish_translations_or_analysis": False,
    "publish_to_model_or_email": False,
    "rights_to_rehost_original_implied": False,
    "retrospective_approval_of_unverified_articles": False,
    "desk_launch_or_collector_schedule_authorized_by_policy": False,
}


class DAPAPolicyHold(ValueError):
    pass


def read_policy(path=POLICY_PATH):
    path = Path(path)
    if path != POLICY_PATH or path.is_symlink():
        raise DAPAPolicyHold("dapa_owner_policy_unpinned")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DAPAPolicyHold("dapa_owner_policy_not_available") from None
    if type(data) is not dict or data != EXPECTED:
        raise DAPAPolicyHold("dapa_owner_permission_scope_changed")
    return data
