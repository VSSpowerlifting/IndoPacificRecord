"""Pure Sunday-reconciliation release contract for weekly Briefs, no I/O.

Ported from #957 (ce6573a58d) and unified with the #960 Saturday recheck.
The receipt lives in the sidecar under ``saturday_sunday_cycle`` and binds
one exact final manuscript to one Sunday (or later) reconciliation of the
complete reporting week. It is checked by ``validate_brief`` for approved
Briefs and by ``validate_readiness``.

The receipt is required by participation, not by date. A manuscript derived
from a weekend editorial cycle carries ``editorial_cycle`` provenance (the
cycle packet's own identity), stamped by the Sunday recheck and carried by
the importer from hidden DOCX properties, never from a visible label or the
stated author. Provenance is part of ``manuscript_digest``, so a companion
Brief, human rewrite or analyst-reconciled version needs its own receipt,
and stripping or altering the provenance breaks the receipt it had. A Brief
with neither provenance nor a receipt was authored independently and keeps
the existing publication safeguards; shared source URLs are not provenance.
Inventory and policy fingerprints are recomputed at readiness by
``scripts.author_brief`` against the live corpus.
"""
import hashlib
import json
import re
from datetime import date, timedelta

SCHEMA = "ipr-saturday-sunday-cycle/1"
KEY = "saturday_sunday_cycle"
PROVENANCE_SCHEMA = "ipr-weekend-editorial-cycle/1"
PROVENANCE_KEY = "editorial_cycle"
# Where the Saturday DOCX carries the cycle identity: a custom document
# property and a document variable, neither shown in Word's title/author/
# keywords fields. The visible label and keyword are display signals only.
DOCX_CYCLE_PROPERTY = "IPR editorial cycle"
DOCX_CYCLE_VARIABLE = "IPREditorialCycle"
SATURDAY_PROVISIONAL_LABEL = "SATURDAY PROVISIONAL · SUNDAY RECHECK REQUIRED"
SATURDAY_PROVISIONAL_KEYWORD = "ipr-saturday-provisional"
PACKET_KINDS = ("saturday_provisional", "friday_provisional", "complete_week")
# One count per drift category the Sunday recheck reports; see
# scripts.weekly_briefs_saturday_audit.diff_snapshots.
COUNT_KEYS = (
    "late_saturday_arrivals", "backdated_arrivals", "removed_from_week",
    "eligibility_or_metadata_changed", "pinned_original_changed",
    "pinned_original_no_longer_eligible", "newly_eligible_originals",
    "appendix_records_changed", "policy_or_source_versions_changed",
)
# #946's per-Brief identity: IPR-<Saturday> for the week's primary Brief,
# IPR-<Saturday>-<slug> for an additional one; same slug grammar as there.
COMPANION_SLUG = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
EXCLUDED = {KEY, "approval", "issue_number", "editorial_status",
            "editorial_review", "policy_ruling"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), default=str).encode()).hexdigest()


def manuscript_digest(sidecar):
    """Fingerprint of the publishable content, excluding approval metadata."""
    return digest({k: v for k, v in sidecar.items() if k not in EXCLUDED})


def identity_matches(identity, week):
    if not isinstance(identity, str) or not isinstance(week, str):
        return False
    base = "IPR-" + week
    return identity == base or (identity.startswith(base + "-")
                                and bool(COMPANION_SLUG.fullmatch(identity[len(base) + 1:])))


def packet_identity(text):
    """The single ``Packet:`` identity in a worksheet's own header, else None."""
    if not isinstance(text, str):
        return None
    head = text.replace("\r\n", "\n").split("\n\n", 1)[0]
    found = [line[len("Packet: "):] for line in head.splitlines() if line.startswith("Packet: ")]
    return found[0] if len(found) == 1 else None


def cycle_provenance(identity):
    """The ``editorial_cycle`` value for one cycle Brief identity."""
    week = identity[4:14] if isinstance(identity, str) else None
    try:
        saturday = date.fromisoformat(week).weekday() == 5
    except (TypeError, ValueError):
        saturday = False
    if not saturday or not identity_matches(identity, week):
        raise ValueError("not a weekend editorial cycle Brief identity")
    return {"schema": PROVENANCE_SCHEMA, "identity": identity, "week_ending": week}


def provenance_problems(sidecar):
    if PROVENANCE_KEY not in sidecar:
        return []
    marker = sidecar[PROVENANCE_KEY]
    try:
        valid = marker == cycle_provenance(marker.get("identity"))
    except (AttributeError, ValueError):
        valid = False
    if not valid:
        return ["invalid weekend editorial cycle provenance"]
    if marker["week_ending"] != sidecar.get("week_ending"):
        return ["weekend editorial cycle provenance is for a different reporting week"]
    return []


def compare(before, after):
    old, new = before.get("sources", {}), after.get("sources", {})
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(k for k in set(old) & set(new) if old[k] != new[k]),
        "policy_changed": before.get("policy") != after.get("policy"),
        "desks_changed": before.get("desks") != after.get("desks"),
    }


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _named(review):
    return isinstance(review, dict) and all(
        isinstance(review.get(k), str) and review[k].strip() for k in ("reviewed_by", "reference"))


def receipt_problems(sidecar):
    week = sidecar.get("week_ending")
    problems = provenance_problems(sidecar)
    if problems:
        return problems
    marker = sidecar.get(PROVENANCE_KEY)
    if KEY not in sidecar:
        if marker is None:
            # Independently authored: the existing publication safeguards apply.
            return []
        return ["cycle-derived Brief requires its own Sunday reconciliation receipt"]
    receipt = sidecar[KEY]
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return ["invalid Saturday–Sunday editorial cycle receipt"]
    # The recheck always stamps provenance, so a receipt without it was stripped.
    if marker is None:
        return ["Sunday reconciliation receipt lacks its editorial cycle provenance"]
    if receipt.get("identity") != marker["identity"]:
        return ["Sunday reconciliation receipt is for a different cycle Brief"]
    if receipt.get("status") != "SUNDAY_RECHECKED":
        return ["Saturday provisional manuscript requires Sunday reconciliation"]
    try:
        end = date.fromisoformat(week)
        observed = date.fromisoformat(receipt.get("collection_day"))
    except (ValueError, TypeError):
        return ["invalid Saturday–Sunday reporting week or collection day"]
    identity = receipt.get("identity")
    if (end.weekday() != 5 or end.isoformat() != week
            or receipt.get("week_ending") != week
            or not identity_matches(identity, week)
            # Dylan may return the revision after Sunday; never before it.
            or observed < end + timedelta(days=1)
            or receipt.get("packet_kind") not in PACKET_KINDS
            or receipt.get("manuscript_sha256") != manuscript_digest(sidecar)):
        return ["Sunday reconciliation does not bind this exact final manuscript/week"]
    if sidecar.get("manuscript_sha256") is not None and (
            receipt.get("revised_manuscript_sha256") != sidecar["manuscript_sha256"]):
        return ["Sunday reconciliation does not bind this exact revised DOCX"]
    if not all(_hex(receipt.get(k)) for k in ("inventory_sha256", "packet_sha256", "diff_sha256")):
        return ["Sunday reconciliation source/packet fingerprint is missing"]
    if (receipt.get("complete_week_claimed") is not False
            or receipt.get("publication_authorized") is not False
            or receipt.get("program_verified_facts") is not False):
        return ["Sunday reconciliation receipt must not claim approval or verified facts"]
    if receipt.get("unresolved_comments_or_tracked_changes") != 0:
        return ["revised manuscript still carries comments or tracked changes"]
    if not _named(receipt.get("source_claim_review")):
        return ["Sunday source-to-claim human review is missing"]
    counts = receipt.get("counts")
    if (not isinstance(counts, dict) or set(counts) != set(COUNT_KEYS)
            or any(type(v) is not int or v < 0 for v in counts.values())):
        return ["Sunday reconciliation change accounting is invalid"]
    review = receipt.get("change_review")
    if any(counts.values()):
        if not _named(review) or review.get("diff_sha256") != receipt["diff_sha256"]:
            return ["Sunday source changes lack exact-diff human adjudication"]
    elif review is not None:
        return ["Sunday reconciliation change accounting is invalid"]
    analyst = receipt.get("analyst")
    if analyst is not None and (
            not isinstance(analyst, dict)
            or not all(_hex(analyst.get(k)) for k in ("assignment_sha256", "feedback_sha256"))
            or analyst.get("state") in (None, "HELD")):
        return ["analyst return is held or unbound; reconcile it before release"]
    return []
