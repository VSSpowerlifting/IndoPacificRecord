"""Audit Saturday additions and Friday-packet drift before Briefs editorial approval.

This command is read-only: it reads the tracked corpus and, optionally, the
owner's private original Friday .txt attachment. It never generates a Brief,
changes the corpus, calls an LLM, emails Dylan, or approves anything.

Usage (after Saturday ends in New York):
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10 \
        --friday-packet /private/IPR-Briefs-Provisional-2026-10-10.txt

The first command is appropriate for manual GitHub Actions execution, with
only aggregate counts printed. The second is local/private: source IDs from
the original packet are compared to current full-week candidates.

Sunday recheck of a Saturday provisional manuscript (owner-local, private):
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10 \
        --saturday-packet /private/IPR-2026-10-10-saturday.txt \
        --revised-docx /private/IPR-2026-10-10-dylan.docx \
        --receipt-out /private/IPR-2026-10-10-recheck.json

The recheck applies the writer's own eligibility and body-hash rules to the
refreshed full week and compares them with the Saturday packet's discovery
receipt. Any drift HOLDS; after human review the owner may rerun with
``--acknowledge-diff <diff_sha256>``. The receipt binds the result to the
exact revised DOCX bytes; ``import_brief_manuscript`` refuses a provisional
manuscript without it. Only aggregate counts are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DB_PATH
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.weekly_briefs_auto_writer import live_editorial_desks
from storage.db import get_articles_for_desks

NEW_YORK = ZoneInfo("America/New_York")
MAX_PACKET_BYTES = 2_000_000
APPENDIX_MARKER = "=== SOURCE APPENDIX — DO NOT EDIT ==="
END_APPENDIX = "END OF SOURCE APPENDIX"
RECHECK_SCHEMA = "ipr-sunday-provisional-recheck/1"
DISCOVERY_LINE = "DISCOVERY RECEIPT (private, no source body): "
MARKER = Path(".github/state/last_daily_run_date.txt")
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RECORD_LINE = re.compile(
    r"^Record ([1-9][0-9]*) \| ([a-z0-9_-]+) \| ([0-9]{4}-[0-9]{2}-[0-9]{2}) \| .+$",
    re.MULTILINE,
)


def parse_saturday(value: str, *, now=None) -> date:
    """Refuse incomplete weeks, malformed dates and non-Saturday identities."""
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Saturday must be a YYYY-MM-DD date") from exc
    if parsed.isoformat() != value or parsed.weekday() != 5:
        raise ValueError("week ending must be a Saturday in YYYY-MM-DD format")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must include a timezone")
    today = now.astimezone(NEW_YORK).date()
    if parsed >= today:
        raise ValueError("cannot audit an incomplete Saturday; wait until Sunday in New York")
    return parsed


def parse_original_packet(path: Path, *, saturday: date) -> dict:
    """Read only the immutable source appendix of the originally sent packet.

    This detects candidate ID drift, not editorial truth or record mutation.
    No model-authored prose or recipient information is logged.
    """
    if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
        raise ValueError("original Friday packet missing or larger than 2 MB")
    try:
        txt = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("original Friday packet must be UTF-8") from exc
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    if txt.count(APPENDIX_MARKER) != 1 or txt.count(END_APPENDIX) != 1:
        raise ValueError("original Friday packet has invalid appendix markers")
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in txt:
        raise ValueError("packet must be an unapproved editorial worksheet")
    if "Packet: IPR-" + saturday.isoformat() not in txt.split(APPENDIX_MARKER, 1)[0].splitlines():
        raise ValueError("Friday packet does not match requested Saturday edition")
    cutoff = saturday - timedelta(days=1)
    as_of = "AS-OF CUT-OFF: " + cutoff.isoformat() + " (FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)"
    if as_of not in txt.split(APPENDIX_MARKER, 1)[0].splitlines():
        raise ValueError("packet is not the Friday provisional cutoff")
    appendix = txt.split(APPENDIX_MARKER, 1)[1].split(END_APPENDIX, 1)[0]
    entries = RECORD_LINE.findall(appendix)
    if not entries:
        raise ValueError("original packet has no source record listings")
    ids = [int(rid) for rid, _, _ in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("original packet has duplicate source IDs")
    beginning = saturday - timedelta(days=6)
    for _rid, _desk, value in entries:
        try:
            pub = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("original packet contains malformed publication dates") from exc
        if not beginning <= pub <= cutoff:
            raise ValueError("original Friday appendix includes out-of-window records")
    return {"records": {int(rid): desk for rid, desk, _ in entries}}


def summarize(*, saturday: date, desks, friday_rows, saturday_rows,
              friday_draft, full_draft, original=None):
    """All public outputs are aggregate; optional private IDs are never printed."""
    fri_by_desk = Counter(e["desk"] for e in friday_draft["source_trail"])
    fri_stored_by_desk = Counter(r["desk_id"] for r in friday_rows)
    sat_stored_by_desk = Counter(r["desk_id"] for r in saturday_rows)
    sat_offered = [
        e for e in full_draft["source_trail"] if e["date"] == saturday.isoformat()
    ]
    sat_by_desk = Counter(e["desk"] for e in sat_offered)
    friday_ids = {e["record_id"]: e["desk"] for e in friday_draft["source_trail"]}
    sat_ids = {e["record_id"]: e["desk"] for e in sat_offered}
    if set(friday_ids).intersection(sat_ids):
        raise ValueError("source appears as both Friday and Saturday candidate")

    result = {
        "status": "FULL_WEEK_SOURCE_REVIEW_REQUIRED",
        "saturday_identity": saturday.isoformat(),
        "friday_cutoff": (saturday - timedelta(days=1)).isoformat(),
        "sunday_start": (saturday - timedelta(days=6)).isoformat(),
        "saturday_stored_records": len(saturday_rows),
        "saturday_offered_candidates": len(sat_offered),
        "saturday_records_require_editorial_review": bool(sat_offered),
        "by_desk": {
            desk: {
                "friday_stored": fri_stored_by_desk[desk],
                "friday_candidates_current": fri_by_desk[desk],
                "saturday_stored": sat_stored_by_desk[desk],
                "saturday_candidates": sat_by_desk[desk],
            }
            for desk in desks
        },
        "friday_packet_comparison": "not supplied",
        "approval_or_publication_authorized": False,
        "warning": (
            "This reports only the repository's current stored publication dates; "
            "missing Saturday records do not establish institutional silence. "
            "Late-collected earlier-dated records, source changes and external "
            "publication completeness require separate human verification."
        ),
    }
    if original is not None:
        baseline = original["records"]
        if any(desk not in desks for desk in baseline.values()):
            raise ValueError("original packet names an unrecognized current desk")
        new = set(friday_ids) - set(baseline)
        missing = set(baseline) - set(friday_ids)
        mismatched = [rid for rid in baseline.keys() & friday_ids.keys()
                      if baseline[rid] != friday_ids[rid]]
        result["friday_packet_comparison"] = {
            "original_friday_candidates": len(baseline),
            "current_friday_candidates": len(friday_ids),
            "new_candidate_ids_since_packet": len(new),
            "missing_or_no_longer_offered_ids": len(missing),
            "changed_desk_assignments": len(mismatched),
            "needs_friday_reconciliation": bool(new or missing or mismatched),
            "note": ("Counts reflect current eligible candidates, not proof of "
                     "new publication or deleted records. A record can change "
                     "screening state between the Friday packet and this audit."),
        }
    return result


def collect_report(saturday: str, *, original_path=None, db=DB_PATH, now=None):
    target = parse_saturday(saturday, now=now)
    original = (parse_original_packet(Path(original_path), saturday=target)
                if original_path is not None else None)
    desks = live_editorial_desks()
    if len(desks) < 2:
        raise ValueError("fewer than two production-backed desks are live")
    start = (target - timedelta(days=6)).isoformat()
    cutoff = (target - timedelta(days=1)).isoformat()
    with read_only(Path(db)) as conn:
        rows = get_articles_for_desks(start, target.isoformat(), desks, conn=conn)
    friday_rows = [r for r in rows if r["published_date"] <= cutoff]
    saturday_rows = [r for r in rows if r["published_date"] == target.isoformat()]
    friday_draft = build_draft(friday_rows, desks=desks, week_start=start,
                               week_ending=target.isoformat())
    full_draft = build_draft(rows, desks=desks, week_start=start,
                             week_ending=target.isoformat())
    return summarize(saturday=target, desks=desks, friday_rows=friday_rows,
                     saturday_rows=saturday_rows, friday_draft=friday_draft,
                     full_draft=full_draft, original=original)


def parse_saturday_packet(path: Path, *, saturday: date) -> dict:
    """Read the private Saturday provisional packet's appendix and receipt.

    Only the header, the immutable appendix and the writer-owned discovery
    receipt are read; manuscript prose is ignored and never logged.
    """
    from scripts.sunday_editorial_handoff import is_saturday_provisional
    if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
        raise ValueError("Saturday packet missing or larger than 2 MB")
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Saturday packet must be UTF-8") from exc
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    if not is_saturday_provisional(txt):
        raise ValueError("packet is not a Saturday provisional draft")
    if txt.count(APPENDIX_MARKER) != 1 or txt.count(END_APPENDIX) != 1:
        raise ValueError("Saturday packet has invalid appendix markers")
    head, rest = txt.split(APPENDIX_MARKER, 1)
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in txt:
        raise ValueError("packet must be an unapproved editorial worksheet")
    if "Packet: IPR-" + saturday.isoformat() not in head.splitlines():
        raise ValueError("Saturday packet does not match requested Saturday edition")
    appendix = rest.split(END_APPENDIX, 1)[0]
    entries = RECORD_LINE.findall(appendix)
    ids = [int(rid) for rid, _, _ in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("Saturday packet has duplicate source IDs")
    beginning = saturday - timedelta(days=6)
    for _rid, _desk, value in entries:
        try:
            pub = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Saturday packet contains malformed publication dates") from exc
        if not beginning <= pub <= saturday:
            raise ValueError("Saturday appendix includes out-of-window records")
    receipts = [line[len(DISCOVERY_LINE):] for line in txt.splitlines()
                if line.startswith(DISCOVERY_LINE)]
    if len(receipts) != 1:
        raise ValueError("Saturday packet needs exactly one discovery receipt")
    try:
        receipt = json.loads(receipts[0])
    except json.JSONDecodeError as exc:
        raise ValueError("Saturday discovery receipt is not valid JSON") from exc
    if (not isinstance(receipt, dict) or receipt.get("schema") != "ipr-sunday-discovery/1"
            or not isinstance(receipt.get("inventory"), list)
            or not isinstance(receipt.get("source_pins"), list)):
        raise ValueError("Saturday discovery receipt is incomplete")
    production, research = {}, 0
    for pin in receipt["source_pins"]:
        if not isinstance(pin, dict):
            raise ValueError("malformed Saturday source pin")
        if pin.get("lane") == "production_record" and type(pin.get("id")) is int:
            production[pin["id"]] = (pin.get("desk"), pin.get("body_sha256"))
        elif pin.get("lane") == "private_research":
            research += 1
        else:
            raise ValueError("unknown Saturday source pin lane")
    return {"sha256": hashlib.sha256(raw).hexdigest(),
            "records": {(int(r), d, v) for r, d, v in entries},
            "inventory": _inventory(receipt["inventory"]),
            "production_pins": production,
            "research_pins": research}


def _inventory(rows) -> dict:
    """Key by typed id: numeric production rows never alias link-lane identities."""
    result = {}
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) not in (int, str):
            raise ValueError("malformed discovery inventory row")
        key = (type(row["id"]).__name__, str(row["id"]))
        if key in result:
            raise ValueError("duplicate discovery inventory identity")
        result[key] = (row.get("desk"), row.get("date"), row.get("reason"))
    return result


def docx_open_questions(path: Path) -> int:
    """Count unresolved review comments and tracked changes in the revision."""
    from zipfile import BadZipFile, ZipFile
    from xml.etree import ElementTree as ET
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            document = ET.fromstring(archive.read("word/document.xml"))
            comments = (ET.fromstring(archive.read("word/comments.xml"))
                        if "word/comments.xml" in names else None)
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError("revised manuscript is not a readable DOCX") from exc
    count = sum(1 for _ in document.iter(WORD + "ins")) + sum(
        1 for _ in document.iter(WORD + "del"))
    if comments is not None:
        count += sum(1 for _ in comments.iter(WORD + "comment"))
    return count


def diff_snapshots(saturday: dict, *, inventory: dict, pins: dict, records: set,
                   week_ending: date) -> dict:
    """Exact private drift between Saturday's snapshot and the refreshed week."""
    before, after = saturday["inventory"], inventory
    added = sorted(after.keys() - before.keys())
    late = [k for k in added if after[k][1] == week_ending.isoformat()]
    return {
        "late_saturday_arrivals": late,
        "backdated_arrivals": [k for k in added if k not in late],
        "removed_from_week": sorted(before.keys() - after.keys()),
        "eligibility_or_metadata_changed": sorted(
            k for k in before.keys() & after.keys() if before[k] != after[k]),
        "pinned_original_changed": sorted(
            i for i in saturday["production_pins"].keys() & pins.keys()
            if saturday["production_pins"][i] != pins[i]),
        "pinned_original_no_longer_eligible": sorted(
            saturday["production_pins"].keys() - pins.keys()),
        "newly_eligible_originals": sorted(pins.keys() - saturday["production_pins"].keys()),
        "appendix_records_changed": sorted(saturday["records"] ^ records),
    }


def sunday_recheck(saturday: str, *, packet_path, revised_docx, marker_path=MARKER,
                   db=DB_PATH, now=None, acknowledge=None) -> tuple:
    """Reconcile the Saturday draft against the refreshed full week.

    Returns ``(public_report, private_receipt)``. The private receipt carries
    exact source IDs for the owner's review; the public report only counts.
    """
    from scripts.sunday_briefs_auto_writer import choose_evidence
    target = parse_saturday(saturday, now=now)
    sunday = target + timedelta(days=1)
    observed = Path(marker_path).read_text(encoding="utf-8").strip()
    if observed != sunday.isoformat():
        raise ValueError("Sunday production update has not recorded its success marker")
    packet = parse_saturday_packet(Path(packet_path), saturday=target)
    revised = Path(revised_docx)
    if not revised.is_file() or revised.is_symlink():
        raise ValueError("revised manuscript DOCX missing")
    revised_sha = hashlib.sha256(revised.read_bytes()).hexdigest()
    open_questions = docx_open_questions(revised)
    desks = live_editorial_desks()
    if len(desks) < 2:
        raise ValueError("fewer than two production-backed desks are live")
    start = (target - timedelta(days=6)).isoformat()
    with read_only(Path(db)) as conn:
        rows = get_articles_for_desks(start, target.isoformat(), desks, conn=conn)
    sidecar = build_draft(rows, desks=desks, week_start=start, week_ending=target.isoformat())
    inventory = []
    verified = choose_evidence(sidecar, as_of=target.isoformat(), db=db,
                               discovery_inventory=inventory)
    pins = {row["id"]: (row["desk_id"], hashlib.sha256(body.encode()).hexdigest())
            for row, body in verified}
    records = {(e["record_id"], e["desk"], e["date"]) for e in sidecar["source_trail"]}
    diff = diff_snapshots(packet, inventory=_inventory(inventory), pins=pins,
                          records=records, week_ending=target)
    counts = {key: len(value) for key, value in diff.items()}
    drift = any(counts.values())
    digest = hashlib.sha256(json.dumps(diff, sort_keys=True).encode()).hexdigest()
    reasons = [key for key, value in counts.items() if value]
    if open_questions:
        # Comments and tracked changes are unresolved claims; no override.
        reasons.append("revised_manuscript_has_unresolved_comments_or_tracked_changes")
    acknowledged = bool(drift and acknowledge == digest)
    if open_questions or (drift and not acknowledged):
        status = "HELD"
    else:
        status = "SUNDAY_RECHECKED"
    public = {
        "schema": RECHECK_SCHEMA,
        "week_ending": target.isoformat(),
        "status": status,
        "hold_reasons": reasons if status == "HELD" else [],
        "sunday_marker": observed,
        "counts": counts,
        "unresolved_comments_or_tracked_changes": open_questions,
        "research_pins_need_human_verification": packet["research_pins"],
        "diff_sha256": digest,
        "owner_acknowledged_changes": acknowledged,
        "saturday_packet_sha256": packet["sha256"],
        "revised_manuscript_sha256": revised_sha,
        "complete_week_claimed": False,
        "publication_authorized": False,
    }
    private = dict(public, diff={k: [list(x) if isinstance(x, tuple) else x for x in v]
                                 for k, v in diff.items()})
    return public, private


def write_private_receipt(path: Path, receipt: dict) -> None:
    """Owner-only, never overwritten: a second recheck needs a fresh path."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")


def load_recheck_receipt(path, *, manuscript_sha256: str) -> dict:
    """Consumer check: a provisional manuscript is ready only after Sunday."""
    try:
        receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Sunday recheck receipt unreadable") from exc
    if (not isinstance(receipt, dict) or receipt.get("schema") != RECHECK_SCHEMA
            or receipt.get("status") != "SUNDAY_RECHECKED"
            or receipt.get("publication_authorized") is not False):
        raise ValueError("Saturday provisional manuscript lacks a passed Sunday recheck")
    if receipt.get("revised_manuscript_sha256") != manuscript_sha256:
        raise ValueError("Sunday recheck was made for a different manuscript revision")
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saturday", required=True, help="week-ending Saturday YYYY-MM-DD")
    parser.add_argument("--friday-packet", type=Path,
                        help="optional original private Friday .txt sent to Dylan")
    parser.add_argument("--saturday-packet", type=Path,
                        help="private Saturday provisional .txt sent to Dylan")
    parser.add_argument("--revised-docx", type=Path,
                        help="Dylan's returned DOCX revision to bind")
    parser.add_argument("--receipt-out", type=Path,
                        help="new private 0600 recheck receipt path")
    parser.add_argument("--marker", type=Path, default=MARKER)
    parser.add_argument("--acknowledge-diff",
                        help="diff_sha256 the owner reviewed in a held receipt")
    args = parser.parse_args(argv)
    recheck = (args.saturday_packet, args.revised_docx, args.receipt_out)
    if any(recheck) or args.acknowledge_diff:
        if not all(recheck) or args.friday_packet:
            parser.error("recheck needs --saturday-packet, --revised-docx and --receipt-out only")
        try:
            report, receipt = sunday_recheck(
                args.saturday, packet_path=args.saturday_packet,
                revised_docx=args.revised_docx, marker_path=args.marker,
                acknowledge=args.acknowledge_diff)
            write_private_receipt(args.receipt_out, receipt)
        except (OSError, ValueError) as exc:
            parser.exit(2, "REFUSED: " + str(exc) + "\n")
        print(json.dumps({k: report[k] for k in (
            "status", "week_ending", "counts", "hold_reasons",
            "research_pins_need_human_verification", "owner_acknowledged_changes")},
            indent=2, sort_keys=True))
        print("Private receipt written; publication remains unapproved.")
        return 0 if report["status"] == "SUNDAY_RECHECKED" else 3
    try:
        report = collect_report(args.saturday, original_path=args.friday_packet)
    except ValueError as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Unapproved source audit only; human editor must review records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
