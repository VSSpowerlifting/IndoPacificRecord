"""Manually hand the EXACT owner-reviewed Sunday Briefs worksheet to its editor.

Offline digest receipt by default. The explicit --send --confirm-owner-reviewed
path sends a temporary byte-for-byte snapshot, never starts an AI model, and
never regenerates a source appendix. Not publication or a rights approval.

The worksheet may be the week's primary Brief (``Packet: IPR-<Saturday>``) or
an additional Brief of the same week (``Packet: IPR-<Saturday>-<slug>``). The
editor defaults to IPR_EDITOR_TO; ``--editor-to`` assigns one named editor.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.sunday_editorial_handoff import (
    packet_identity, quality_hold, send_packet, single_address,
)

NY = ZoneInfo("America/New_York")
SCHEMA = "ipr-reviewed-sunday-manual-handoff/1"
MAX_BYTES = 3_000_000
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
HEADER = "INDO-PACIFIC RECORD | BRIEFS EDITORIAL WORKSHEET"
STRUCTURE = (
    "=== EDITABLE MANUSCRIPT ===",
    "## WORKING TITLE",
    "=== SOURCE APPENDIX — DO NOT EDIT ===",
    "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===",
    "END OF MANUSCRIPT SOURCE USE",
    "END OF SOURCE APPENDIX",
    "END OF UNAPPROVED WORKSHEET",
)
# One of two worksheet layouts: the article-first draft (single ARTICLE section;
# citations mapped in the hash-validated appendix) or the retired fixed outline.
LAYOUTS = (
    ("## ARTICLE", "ARTICLE SOURCE ACCOUNTING (private;"),
    ("## CONCRETE DEVELOPMENT", "SOURCE RECORD IDS:"),
)


class ReviewedHandoffRefused(ValueError):
    """Unsafe or unapproved exact-file editorial handoff."""


def worksheet_identity(text, week_ending):
    """Return ``None`` for the week's primary worksheet or the additional-Brief
    slug, refusing any other edition identity on the second line."""
    match = re.match(re.escape(HEADER) + r"\nPacket: IPR-" + re.escape(week_ending)
                     + r"(?:-([a-z][a-z0-9-]{0,79}))?\n", text)
    if match is None:
        raise ReviewedHandoffRefused("worksheet header or exact edition identity mismatch")
    return match.group(1)


def validate_file(path, week_ending, *, now=None):
    """Return a verified immutable-in-memory snapshot of the local worksheet."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".txt":
        raise ReviewedHandoffRefused("reviewed packet must be an existing regular .txt, not a symlink")
    if not DATE.fullmatch(week_ending):
        raise ReviewedHandoffRefused("reporting Saturday must be exact YYYY-MM-DD")
    try:
        saturday = date.fromisoformat(week_ending)
    except ValueError as exc:
        raise ReviewedHandoffRefused("invalid reporting Saturday") from exc
    if saturday.weekday() != 5:
        raise ReviewedHandoffRefused("reporting date must be a Saturday")
    if now is None:
        now = datetime.now(NY)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ReviewedHandoffRefused("local clock must have timezone")
    today = now.astimezone(NY).date()
    if saturday >= today:
        raise ReviewedHandoffRefused("reporting Saturday has not ended")
    if saturday < today - timedelta(days=98):
        raise ReviewedHandoffRefused("reviewed edition is outside 98-day historical review window")
    if path.stat().st_size > MAX_BYTES:
        raise ReviewedHandoffRefused("unexpectedly large editorial worksheet")
    payload = path.read_bytes()
    if not payload or len(payload) > MAX_BYTES:
        raise ReviewedHandoffRefused("empty or unexpectedly large reviewed attachment")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewedHandoffRefused("owner-review attachment must be UTF-8 text") from exc
    worksheet_identity(text, week_ending)
    if text.count("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED") != 1:
        raise ReviewedHandoffRefused("worksheet must explicitly remain unnumbered and unapproved")
    for marker in STRUCTURE:
        if text.count(marker) != 1:
            raise ReviewedHandoffRefused("reviewed worksheet lacks unique protected structure: " + marker)
    layouts = [(h, c) for h, c in LAYOUTS if text.count("\n" + h + "\n") == 1]
    if len(layouts) != 1:
        raise ReviewedHandoffRefused(
            "reviewed worksheet must have exactly one recognised layout (ARTICLE or CONCRETE DEVELOPMENT)")
    if layouts[0][1] not in text:
        raise ReviewedHandoffRefused("thematic manuscript lacks production citation bookkeeping")
    if not text.endswith("END OF UNAPPROVED WORKSHEET\n"):
        raise ReviewedHandoffRefused("reviewed file has trailing or missing worksheet boundary")
    return payload


def inspect_reviewed_attachment(path, week_ending, *, approval_week="", approval_digest="",
                                now=None):
    packet = validate_file(path, week_ending, now=now)
    actual = hashlib.sha256(packet).hexdigest()
    slug = worksheet_identity(packet.decode("utf-8"), week_ending)
    approved = bool(
        approval_week == week_ending and isinstance(approval_digest, str)
        and DIGEST.fullmatch(approval_digest)
        and hmac.compare_digest(actual, approval_digest)
    )
    return packet, {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "packet_identity": packet_identity(week_ending, slug),
        "companion_slug": slug,
        "attachment_sha256": actual,
        "attachment_bytes": len(packet),
        "exact_owner_approval_matches": approved,
        "quality_hold_present": quality_hold(packet.decode("utf-8")),
        "automated_model_called": False,
        "publisher_rights_or_facts_reviewed_by_program": False,
        "email_sent": False,
        "publication_authorized": False,
    }


def handoff(path, week_ending, *, send=False, owner_confirmed=False,
            historical_override=False, editor_to=None, now=None):
    """Return metadata only; never email unless BOTH explicit manual flags hold.

    ``editor_to`` assigns this exact worksheet to one named editor instead of
    IPR_EDITOR_TO; it is subject to the same distinct-from-owner rule."""
    if now is None:
        now = datetime.now(NY)
    packet, receipt = inspect_reviewed_attachment(
        path, week_ending,
        approval_week=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_WEEK", ""),
        approval_digest=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_SHA256", ""),
        now=now,
    )
    if not send:
        if owner_confirmed or historical_override:
            raise ReviewedHandoffRefused("send confirmations are invalid on a dry run")
        if editor_to is not None:
            editor = single_address(editor_to, "assigned editor")
            owner = os.environ.get("IPR_PREVIEW_TO", "").strip()
            if owner and editor.casefold() == owner.casefold():
                raise ReviewedHandoffRefused(
                    "manual editor recipient must differ from the owner-preview address")
            receipt["assigned_editor"] = editor
        return receipt
    if not owner_confirmed or not receipt["exact_owner_approval_matches"]:
        raise ReviewedHandoffRefused(
            "editor send refused: --confirm-owner-reviewed and exact approved "
            "IPR_SUNDAY_OWNER_REVIEWED_WEEK/SHA256 are required"
        )
    local_day = now.astimezone(NY).date()
    latest_saturday = local_day - timedelta(days=(local_day.weekday() - 5) % 7)
    if (week_ending != latest_saturday.isoformat()
            or local_day.weekday() != 6) and not historical_override:
        raise ReviewedHandoffRefused(
            "sending a past-week reviewed manuscript requires --allow-historical-send"
        )
    # A deliberate manual editor handoff must not run alongside the old
    # recurring Friday delivery service. The operator supplies the same
    # environment that IPR's weekly workflow uses; we do not update variables.
    for service in ("IPR_EDITOR_DELIVERY_ENABLED",
                    "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED"):
        if os.environ.get(service, "").strip().lower() == "true":
            raise ReviewedHandoffRefused(
                "parallel editor service enabled: disable " + service
            )
    try:
        editor = (single_address(editor_to, "assigned editor") if editor_to is not None
                  else single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO"))
        owner = single_address(os.environ.get("IPR_PREVIEW_TO", ""), "IPR_PREVIEW_TO")
    except ValueError as exc:
        raise ReviewedHandoffRefused(
            "manual handoff needs distinct configured owner and editor addresses"
        ) from exc
    if editor.casefold() == owner.casefold():
        raise ReviewedHandoffRefused(
            "manual editor recipient must differ from the owner-preview address"
        )
    # Snapshot bytes in a private temporary directory. Protect against a
    # changed original file between preflight hashing and SMTP attachment read.
    with tempfile.TemporaryDirectory(prefix="ipr-reviewed-sunday-") as folder:
        reviewed_copy = Path(folder) / Path(path).name
        reviewed_copy.write_bytes(packet)
        # Reaching here required --confirm-owner-reviewed AND an exact digest match,
        # which is the owner's informed release of any narrative-quality hold.
        # The primary single-Brief call stays exactly as before; an additional
        # Brief or a named editor adds only the arguments it needs.
        extra = {}
        if receipt["companion_slug"] is not None:
            extra["companion_slug"] = receipt["companion_slug"]
        if editor_to is not None:
            extra["editor_to"] = editor
        send_packet(reviewed_copy, week_ending, provisional=True, full_week=True,
                    owner_released=True, **extra)
    receipt["email_sent"] = True
    receipt["assigned_editor"] = editor
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--packet", type=Path, required=True,
                   help="local owner-reviewed .txt; never a fresh AI run")
    p.add_argument("--week-ending", required=True, help="reviewed reporting Saturday")
    p.add_argument("--send", action="store_true",
                   help="actually deliver the exact approved file; absent means offline receipt")
    p.add_argument("--confirm-owner-reviewed", action="store_true",
                   help="explicit owner acknowledgement for this exact attachment")
    p.add_argument("--allow-historical-send", action="store_true",
                   help="acknowledge deliberate older-edition delivery")
    p.add_argument("--editor-to", default=None,
                   help="one named editor for this worksheet (default IPR_EDITOR_TO)")
    args = p.parse_args(argv)
    try:
        receipt = handoff(
            args.packet, args.week_ending, send=args.send,
            owner_confirmed=args.confirm_owner_reviewed,
            historical_override=args.allow_historical_send,
            editor_to=args.editor_to,
        )
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
