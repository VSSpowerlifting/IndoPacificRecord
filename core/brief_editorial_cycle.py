"""Pure release contract for opt-in Saturday–Sunday Briefs, no I/O or approvals."""
import hashlib
import json
from datetime import date, timedelta

SCHEMA = "ipr-saturday-sunday-cycle/1"


def manuscript_digest(sidecar):
    payload = {k: v for k, v in sidecar.items() if k not in {
        "saturday_sunday_cycle", "approval", "issue_number", "editorial_status",
        "editorial_review", "policy_ruling"}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def receipt_problems(sidecar):
    if "saturday_sunday_cycle" not in sidecar:
        return []
    receipt = sidecar["saturday_sunday_cycle"]
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return ["invalid Saturday–Sunday editorial cycle receipt"]
    if receipt.get("status") != "SUNDAY_RECHECKED":
        return ["Saturday provisional manuscript requires Sunday reconciliation"]
    week = sidecar.get("week_ending")
    try:
        end = date.fromisoformat(week)
        sunday = (end + timedelta(days=1)).isoformat()
    except (ValueError, TypeError):
        return ["invalid Saturday–Sunday reporting week"]
    if (end.weekday() != 5 or end.isoformat() != week
            or receipt.get("week_ending") != week
            or receipt.get("identity") != "IPR-" + week
            or receipt.get("collection_day") != sunday
            or receipt.get("manuscript_sha256") != manuscript_digest(sidecar)):
        return ["Sunday reconciliation does not bind this exact final manuscript/week"]
    review = receipt.get("source_claim_review")
    if not isinstance(review, dict) or not all(
            isinstance(review.get(k), str) and review[k].strip()
            for k in ("reviewed_by", "reference")):
        return ["Sunday source-to-claim human review is missing"]
    for key in ("inventory_sha256", "packet_sha256"):
        value = receipt.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            return ["Sunday reconciliation source/packet fingerprint is missing"]
    changes = receipt.get("changes")
    decisions = receipt.get("change_decisions")
    if not isinstance(changes, dict) or not isinstance(decisions, dict):
        return ["Sunday reconciliation change accounting is missing"]
    required = set()
    for kind in ("added", "removed", "changed"):
        rows = changes.get(kind)
        if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
            return ["Sunday reconciliation change accounting is invalid"]
        required.update(kind + ":" + row for row in rows)
    for kind in ("policy_changed", "desks_changed"):
        if type(changes.get(kind)) is not bool:
            return ["Sunday reconciliation change accounting is invalid"]
        if changes[kind]:
            required.add(kind)
    if set(decisions) != required or any(
            not isinstance(item, dict) or item.get("disposition") != "resolved"
            or any(not isinstance(item.get(k), str) or not item[k].strip()
                   for k in ("reason", "reviewed_by", "reference"))
            or item.get("inventory_sha256") != receipt["inventory_sha256"]
            or item.get("manuscript_sha256") != receipt["manuscript_sha256"]
            for item in decisions.values()):
        return ["Sunday source changes lack exact-version human adjudication"]
    return []
