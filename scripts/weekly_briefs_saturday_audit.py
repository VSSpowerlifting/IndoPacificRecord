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

Sunday reconciliation of the week's manuscript (owner-local, private):
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10 \
        --saturday-packet /private/IPR-2026-10-10-saturday.txt \
        --candidate /private/candidate-sidecar.json \
        --revised-docx /private/IPR-2026-10-10-dylan.docx \
        --reviewed-by "Editor name" --review-reference "source review 2026-10-11" \
        --receipt-out /private/IPR-2026-10-10-recheck.json \
        --sidecar-out /private/candidate-reconciled.json

The recheck applies the writer's own eligibility and body-hash rules to the
refreshed full week and compares them, and the current source/policy files,
with the packet's discovery receipt. Saturday provisional and complete-week
packets are both reconciled the same way. Any drift HOLDS; after human review
the owner may rerun with ``--acknowledge-diff <diff_sha256>``. A passing run
writes the candidate sidecar with a ``saturday_sunday_cycle`` receipt that
binds the exact manuscript, revised DOCX, week inventory and reviewers;
``core.brief_contract`` refuses readiness or approval of any week from
``core.brief_editorial_cycle.CUTOVER_WEEK`` on without it, whatever labels the
DOCX carries. Exact source IDs stay in the private receipt; only aggregate
counts are printed.

When a research analyst reviewed the week (``scripts.brief_analyst_review``),
add ``--analyst-manifest`` and ``--analyst-feedback`` with the owner's
reconciled report. The receipt binds their hashes and state; a HELD report
(any unresolved finding) holds the recheck. Without them the analyst path is
simply absent, which is the ordinary no-analyst week.
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
from core.brief_editorial_cycle import digest, identity_matches
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.weekly_briefs_auto_writer import live_editorial_desks
from storage.db import get_articles_for_desks

NEW_YORK = ZoneInfo("America/New_York")
MAX_PACKET_BYTES = 2_000_000
APPENDIX_MARKER = "=== SOURCE APPENDIX — DO NOT EDIT ==="
END_APPENDIX = "END OF SOURCE APPENDIX"
DISCOVERY_LINE = "DISCOVERY RECEIPT (private, no source body): "
ROOT = Path(__file__).resolve().parents[1]
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


def packet_kind(head: str) -> str:
    """The packet's own as-of statement, never a DOCX label."""
    from scripts.sunday_editorial_handoff import SATURDAY_PROVISIONAL_MARK
    if "(" + SATURDAY_PROVISIONAL_MARK + ")" in head:
        return "saturday_provisional"
    if "(FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)" in head:
        return "friday_provisional"
    if ("(SATURDAY COMPLETE; CAPTURE COMPLETENESS UNVERIFIED)" in head
            or "Complete-week editorial worksheet" in head):
        return "complete_week"
    raise ValueError("packet does not state its as-of cut-off")


def parse_saturday_packet(path: Path, *, saturday: date) -> dict:
    """Read the private packet's appendix and writer-owned discovery receipt.

    Only the header, the immutable appendix and the discovery receipt are
    read; manuscript prose is ignored and never logged.
    """
    if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
        raise ValueError("editorial packet missing or larger than 2 MB")
    raw = path.read_bytes()
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("editorial packet must be UTF-8") from exc
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    kind = packet_kind(txt.split("\n\n", 1)[0])
    if txt.count(APPENDIX_MARKER) != 1 or txt.count(END_APPENDIX) != 1:
        raise ValueError("editorial packet has invalid appendix markers")
    head, rest = txt.split(APPENDIX_MARKER, 1)
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in txt:
        raise ValueError("packet must be an unapproved editorial worksheet")
    identities = [line[len("Packet: "):] for line in head.splitlines()
                  if line.startswith("Packet: ")]
    if len(identities) != 1 or not identity_matches(identities[0], saturday.isoformat()):
        raise ValueError("packet does not match requested Saturday edition")
    appendix = rest.split(END_APPENDIX, 1)[0]
    entries = RECORD_LINE.findall(appendix)
    ids = [int(rid) for rid, _, _ in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("editorial packet has duplicate source IDs")
    beginning = saturday - timedelta(days=6)
    for _rid, _desk, value in entries:
        try:
            pub = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("editorial packet contains malformed publication dates") from exc
        if not beginning <= pub <= saturday:
            raise ValueError("packet appendix includes out-of-window records")
    receipts = [line[len(DISCOVERY_LINE):] for line in txt.splitlines()
                if line.startswith(DISCOVERY_LINE)]
    if len(receipts) != 1:
        raise ValueError("editorial packet needs exactly one discovery receipt")
    try:
        receipt = json.loads(receipts[0])
    except json.JSONDecodeError as exc:
        raise ValueError("discovery receipt is not valid JSON") from exc
    if (not isinstance(receipt, dict) or receipt.get("schema") != "ipr-sunday-discovery/1"
            or not isinstance(receipt.get("inventory"), list)
            or not isinstance(receipt.get("source_pins"), list)):
        raise ValueError("discovery receipt is incomplete")
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
    policy = receipt.get("policy_sha256")
    return {"sha256": hashlib.sha256(raw).hexdigest(),
            "kind": kind,
            "identity": identities[0],
            # Absent from packets written before the fingerprint existed;
            # that counts as a change a human must adjudicate.
            "policy_sha256": policy if isinstance(policy, str) else None,
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


def policy_snapshot(root=ROOT) -> dict:
    """Conservative local rights/configuration drift check, not a rights grant.

    Ported from #957: any change to source, permission, rights, custody or
    policy files since the packet was written must be adjudicated on Sunday.
    """
    root = Path(root)
    paths = set()
    for pattern in ("config/**/*.json", "desks/**/*.json", "shadow/*/manifest.json",
                    "core/*source*.py", "core/*permission*.py", "core/*rights*.py",
                    "core/*custody*.py", "core/*policy*.py"):
        paths.update(root.glob(pattern))
    for name in ("DECISION_LOG.md", "core/standing_source_rights.py",
                 "core/brief_editorial_source_use.py", "core/mindef_permissions.py",
                 "processing/daily_intake.py", "core/daily_sources.py"):
        paths.add(root / name)
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file() and not p.is_symlink()}


def inventory(week_ending: str, *, database=DB_PATH, desks=None, root=ROOT) -> dict:
    """Hash every weekly production row and metadata-only discovery row.

    Ported from #957. No bodies or titles leave this function, only row
    hashes; whole-row hashes cover originals, representations, screening and
    holds. Date-only windows include late-admitted and backdated originals.
    """
    end = date.fromisoformat(week_ending)
    start = (end - timedelta(days=6)).isoformat()
    desks = list(desks if desks is not None else live_editorial_desks())
    with read_only(Path(database)) as conn:
        rows = get_articles_for_desks(start, week_ending, desks, conn=conn)
        pins = {"record:" + str(row["id"]): digest(dict(row)) for row in rows}
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("regional_official_source_links", "korea_official_source_records",
                      "uscc_official_source_records", "treasury_official_source_records",
                      "bis_authenticated_official_source_records"):
            if table in tables:
                cursor = conn.execute("SELECT * FROM " + table +
                                      " WHERE publisher_posted_date BETWEEN ? AND ?",
                                      (start, week_ending))
                columns = [col[0] for col in cursor.description]
                for row in cursor:
                    data = dict(zip(columns, row))
                    pins[table + ":" + data["source_identity"]] = digest(data)
        if {"daily_machine_records", "regional_official_source_links"} <= tables:
            cursor = conn.execute("SELECT m.* FROM daily_machine_records m JOIN "
                "regional_official_source_links l USING(source_family,source_identity) "
                "WHERE l.publisher_posted_date BETWEEN ? AND ?", (start, week_ending))
            columns = [col[0] for col in cursor.description]
            for row in cursor:
                data = dict(zip(columns, row))
                pins["machine:" + data["source_family"] + ":" + data["source_identity"]] = digest(data)
    return {"week_start": start, "week_ending": week_ending, "desks": desks,
            "sources": pins, "policy": policy_snapshot(root)}


def inventory_sha256(week_ending: str, *, database=DB_PATH) -> str:
    """The fingerprint readiness recomputes against the Sunday receipt."""
    return digest(inventory(week_ending, database=database))


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
                   week_ending: date, policy_sha256=None) -> dict:
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
        "policy_or_source_versions_changed": (
            [] if policy_sha256 is not None and saturday.get("policy_sha256") == policy_sha256
            else ["policy_snapshot"]),
    }


def _review(reviewed_by, reference):
    if not all(isinstance(v, str) and v.strip() for v in (reviewed_by, reference)):
        return None
    return {"reviewed_by": reviewed_by.strip(), "reference": reference.strip()}


def analyst_binding(manifest, report, *, week: str) -> dict:
    """Bind an owner-reconciled #956 analyst feedback report to this week.

    Only the trusted assignment manifest and the owner's feedback report are
    read; the analyst's returned DOCX stays in ``scripts.brief_analyst_review``.
    The receipt keeps hashes and the report state, never findings or names.
    """
    from core.brief_analyst_feedback import SCHEMA as FEEDBACK
    from core.brief_analyst_packet import digest as analyst_digest, validate_manifest
    validate_manifest(manifest)
    packet = manifest.get("packet")
    if manifest.get("week_ending") != week or not identity_matches(packet, week):
        raise ValueError("analyst assignment is not for this reporting week")
    if (not isinstance(report, dict) or report.get("schema") != FEEDBACK
            or report.get("feedback_sha256") != analyst_digest(
                {k: v for k, v in report.items() if k != "feedback_sha256"})):
        raise ValueError("analyst feedback report is invalid or altered")
    if (report.get("assignment_id") != manifest["assignment_id"]
            or report.get("worksheet_sha256") != manifest["worksheet_sha256"]):
        raise ValueError("analyst feedback does not belong to this assignment")
    # ``packet`` is checked against the Saturday packet by sunday_recheck and
    # is not kept in the receipt.
    return {"assignment_sha256": manifest["manifest_sha256"],
            "feedback_sha256": report["feedback_sha256"], "state": report.get("state"),
            "packet": packet}


def sunday_recheck(saturday: str, *, packet_path, candidate, revised_docx=None,
                   reviewed_by=None, review_reference=None, analyst=None,
                   marker_path=MARKER, db=DB_PATH, now=None, acknowledge=None) -> tuple:
    """Reconcile the week's manuscript against the refreshed full week.

    Returns ``(receipt, private_receipt, reconciled_sidecar)``. The receipt
    carries counts, hashes and reviewer references only; the private copy adds
    exact source IDs for the owner's review. ``reconciled_sidecar`` is the
    candidate with the receipt attached, or None while HELD.
    """
    from core.brief_editorial_cycle import COUNT_KEYS, KEY, SCHEMA, manuscript_digest
    from core.brief_source_linked import is_source_linked
    from scripts.sunday_briefs_auto_writer import choose_evidence
    now = now or datetime.now(timezone.utc)
    target = parse_saturday(saturday, now=now)
    week = target.isoformat()
    observed = Path(marker_path).read_text(encoding="utf-8").strip()
    try:
        collected = date.fromisoformat(observed)
    except ValueError:
        collected = None
    # Dylan's revision may come back after Sunday: any later successful
    # collection still covers the complete week; nothing before Sunday does.
    if (collected is None or collected.isoformat() != observed
            or not target + timedelta(days=1) <= collected <= now.astimezone(NEW_YORK).date()):
        raise ValueError("no successful production collection recorded since the week ended")
    if not isinstance(candidate, dict) or candidate.get("week_ending") != week:
        raise ValueError("candidate sidecar is not for this reporting week")
    base = {k: v for k, v in candidate.items() if k != KEY}
    packet = parse_saturday_packet(Path(packet_path), saturday=target)
    if analyst is not None:
        # One Brief's analyst return never releases another Brief of the week.
        if not isinstance(analyst, dict) or analyst.get("packet") != packet["identity"]:
            raise ValueError("analyst assignment is not for this Brief")
        analyst = {k: v for k, v in analyst.items() if k != "packet"}
    expected = base.get("manuscript_sha256")
    revised_sha, open_questions = None, 0
    if revised_docx is not None or expected is not None or is_source_linked(base):
        revised = Path(revised_docx) if revised_docx is not None else None
        if revised is None or not revised.is_file() or revised.is_symlink():
            raise ValueError("revised manuscript DOCX missing")
        revised_sha = hashlib.sha256(revised.read_bytes()).hexdigest()
        if expected is not None and revised_sha != expected:
            raise ValueError("candidate sidecar was not imported from this revised DOCX")
        open_questions = docx_open_questions(revised)
    desks = live_editorial_desks()
    if len(desks) < 2:
        raise ValueError("fewer than two production-backed desks are live")
    start = (target - timedelta(days=6)).isoformat()
    with read_only(Path(db)) as conn:
        rows = get_articles_for_desks(start, week, desks, conn=conn)
    sidecar = build_draft(rows, desks=desks, week_start=start, week_ending=week)
    found = []
    verified = choose_evidence(sidecar, as_of=week, db=db, discovery_inventory=found)
    pins = {row["id"]: (row["desk_id"], hashlib.sha256(body.encode()).hexdigest())
            for row, body in verified}
    records = {(e["record_id"], e["desk"], e["date"]) for e in sidecar["source_trail"]}
    diff = diff_snapshots(packet, inventory=_inventory(found), pins=pins, records=records,
                          week_ending=target, policy_sha256=digest(policy_snapshot()))
    counts = {key: len(diff[key]) for key in COUNT_KEYS}
    drift = any(counts.values())
    diff_sha = hashlib.sha256(json.dumps(diff, sort_keys=True).encode()).hexdigest()
    review = _review(reviewed_by, review_reference)
    reasons = [key for key in COUNT_KEYS if counts[key]]
    if open_questions:
        # Comments and tracked changes are unresolved claims; no override.
        reasons.append("revised_manuscript_has_unresolved_comments_or_tracked_changes")
    if review is None:
        reasons.append("source_to_claim_human_review_missing")
    analyst_held = analyst is not None and (
        not isinstance(analyst, dict) or analyst.get("state") in (None, "HELD"))
    if analyst_held:
        reasons.append("analyst_return_held")
    acknowledged = bool(drift and review is not None and acknowledge == diff_sha)
    held = open_questions or review is None or analyst_held or (drift and not acknowledged)
    status = "HELD" if held else "SUNDAY_RECHECKED"
    receipt = {
        "schema": SCHEMA,
        "status": status,
        "identity": packet["identity"],
        "week_ending": week,
        "collection_day": observed,
        "packet_kind": packet["kind"],
        "packet_sha256": packet["sha256"],
        "manuscript_sha256": manuscript_digest(base),
        "revised_manuscript_sha256": revised_sha,
        "inventory_sha256": digest(inventory(week, database=db, desks=desks)),
        "diff_sha256": diff_sha,
        "counts": counts,
        "change_review": dict(review, diff_sha256=diff_sha) if acknowledged else None,
        "source_claim_review": review,
        "analyst": analyst,
        "hold_reasons": reasons if held else [],
        "unresolved_comments_or_tracked_changes": open_questions,
        "research_pins_need_human_verification": packet["research_pins"],
        "complete_week_claimed": False,
        "publication_authorized": False,
        "program_verified_facts": False,
    }
    private = dict(receipt, diff={k: [list(x) if isinstance(x, tuple) else x for x in v]
                                  for k, v in diff.items()})
    reconciled = None if held else dict(base, **{KEY: receipt})
    return receipt, private, reconciled


def outside_repository(path: Path) -> Path:
    """Private evidence never lands in a checkout, where it could be committed."""
    path = Path(path)
    resolved = path.parent.resolve()
    if (path.is_symlink() or ROOT == resolved or ROOT in resolved.parents
            or any((parent / ".git").exists() for parent in (resolved, *resolved.parents))):
        raise ValueError("private receipts must stay outside the repository")
    return path


def write_private_receipt(path: Path, receipt: dict) -> None:
    """Owner-only, never overwritten: a second recheck needs a fresh path."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saturday", required=True, help="week-ending Saturday YYYY-MM-DD")
    parser.add_argument("--friday-packet", type=Path,
                        help="optional original private Friday .txt sent to Dylan")
    parser.add_argument("--saturday-packet", type=Path,
                        help="private Saturday provisional or complete-week .txt sent to Dylan")
    parser.add_argument("--candidate", type=Path,
                        help="candidate sidecar JSON for this week's final manuscript")
    parser.add_argument("--revised-docx", type=Path,
                        help="Dylan's returned DOCX revision to bind")
    parser.add_argument("--reviewed-by", help="human source-to-claim reviewer")
    parser.add_argument("--review-reference", help="where that review is recorded")
    parser.add_argument("--receipt-out", type=Path,
                        help="new private 0600 recheck receipt path, outside the repository")
    parser.add_argument("--sidecar-out", type=Path,
                        help="new path for the reconciled candidate sidecar")
    parser.add_argument("--marker", type=Path, default=MARKER)
    parser.add_argument("--acknowledge-diff",
                        help="diff_sha256 the owner reviewed in a held receipt")
    parser.add_argument("--analyst-manifest", type=Path,
                        help="optional private analyst assignment manifest (brief_analyst_review)")
    parser.add_argument("--analyst-feedback", type=Path,
                        help="the owner's reconciled analyst feedback report for that assignment")
    args = parser.parse_args(argv)
    recheck = (args.saturday_packet, args.candidate, args.receipt_out, args.sidecar_out)
    analyst_paths = (args.analyst_manifest, args.analyst_feedback)
    if any(recheck) or args.acknowledge_diff or args.revised_docx or any(analyst_paths):
        if not all(recheck) or args.friday_packet:
            parser.error("recheck needs --saturday-packet, --candidate, --receipt-out "
                         "and --sidecar-out")
        if any(analyst_paths) and not all(analyst_paths):
            parser.error("--analyst-manifest and --analyst-feedback go together")
        try:
            analyst = None
            if args.analyst_manifest:
                analyst = analyst_binding(
                    json.loads(args.analyst_manifest.read_text(encoding="utf-8")),
                    json.loads(args.analyst_feedback.read_text(encoding="utf-8")),
                    week=args.saturday)
            candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
            outside_repository(args.receipt_out)
            for path in (args.receipt_out, args.sidecar_out):
                if path.exists() or path.is_symlink():
                    raise ValueError("refusing to overwrite " + path.name)
            report, receipt, reconciled = sunday_recheck(
                args.saturday, packet_path=args.saturday_packet, candidate=candidate,
                revised_docx=args.revised_docx, reviewed_by=args.reviewed_by,
                review_reference=args.review_reference, analyst=analyst,
                marker_path=args.marker, acknowledge=args.acknowledge_diff)
            write_private_receipt(args.receipt_out, receipt)
            if reconciled is not None:
                write_private_receipt(args.sidecar_out, reconciled)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.exit(2, "REFUSED: " + str(exc) + "\n")
        print(json.dumps({k: report[k] for k in (
            "status", "week_ending", "packet_kind", "counts", "hold_reasons",
            "research_pins_need_human_verification")}, indent=2, sort_keys=True))
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
