"""Private, no-send Saturday drafting and Sunday reconciliation.

Uses the existing writer, worksheet and source contracts. No scheduler, SMTP,
publisher or model retry is introduced. A model call requires --execute-model;
normal preparation only writes a private scaffold/inventory for owner review.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DB_PATH
from core.brief_editorial_cycle import manuscript_digest, receipt_problems
from scripts.reconcile_db import read_only
from scripts.sunday_briefs_auto_writer import live_editorial_desks
from storage.db import get_articles_for_desks

ROOT = Path(__file__).resolve().parents[1]
NY = ZoneInfo("America/New_York")
SCHEMA = "ipr-saturday-sunday-cycle/1"
MARKER = ROOT / ".github/state/last_daily_run_date.txt"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def collection_window(week_ending, phase, *, now=None, marker_path=MARKER):
    from scripts.sunday_corpus_readiness import iso_day
    end = iso_day(week_ending)
    clock = now or datetime.now(NY)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("cycle clock requires timezone")
    local = clock.astimezone(NY)
    required = end if phase == "saturday" else end + timedelta(days=1)
    if end.weekday() != 5 or phase not in ("saturday", "sunday"):
        raise ValueError("cycle requires Saturday reporting end and known phase")
    if local.date() != required:
        raise ValueError("cycle must run on its exact New York-local " + phase)
    if phase == "saturday" and (local.hour, local.minute) < (12, 30):
        raise ValueError("Saturday generation target has not been reached")
    marker = Path(marker_path)
    if marker.is_symlink() or not marker.is_file() or marker.read_text().strip() != required.isoformat():
        raise ValueError("same-day successful production collection marker missing or stale")
    return {"week_start": (end - timedelta(days=6)).isoformat(),
            "week_ending": end.isoformat(), "observed_at": local.isoformat(),
            "collection_day": required.isoformat(), "phase": phase,
            "capture_completeness_verified": False}


def policy_snapshot(root=ROOT):
    """Conservative local rights/configuration drift check, not a rights grant."""
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


def inventory(week_ending, *, database=DB_PATH, desks=None, root=ROOT):
    """Hash every weekly production row and metadata-only discovery row.

    No bodies or titles are copied into the receipt. Entire row hashes include
    originals, representations, screening and holds. Date-only source windows
    intentionally include late-admitted/backdated originals on Sunday.
    """
    from scripts.sunday_corpus_readiness import iso_day
    end = iso_day(week_ending)
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


def compare(before, after):
    old, new = before["sources"], after["sources"]
    return {"added": sorted(set(new) - set(old)),
            "removed": sorted(set(old) - set(new)),
            "changed": sorted(k for k in set(new) & set(old) if new[k] != old[k]),
            "policy_changed": before["policy"] != after["policy"],
            "desks_changed": before["desks"] != after["desks"]}


def private_directory(directory):
    directory = Path(directory)
    resolved = directory.resolve()
    if (ROOT == resolved or ROOT in resolved.parents or directory.is_symlink()
            or any((parent / ".git").exists() for parent in (resolved, *resolved.parents))):
        raise ValueError("cycle artifacts must stay outside the repository in private storage")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_mode & 0o077:
        raise ValueError("private cycle directory must have mode 0700")
    return directory


def write_private(path, value):
    """Exclusive output: accepted files are never overwritten or regenerated."""
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    binary = isinstance(value, bytes)
    handle = os.open(str(path), flags, 0o600)
    with os.fdopen(handle, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def prepare(week_ending, directory, *, database=DB_PATH, marker_path=MARKER,
            now=None, execute_model=False, client=None):
    """Prepare once per week. Replays return accepted hashes without a model."""
    window = collection_window(week_ending, "saturday", now=now, marker_path=marker_path)
    directory = private_directory(directory)
    state_path = directory / ("IPR-" + week_ending + ".json")
    with (directory / ".cycle.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state.get("schema") != SCHEMA or state.get("identity") != "IPR-" + week_ending:
                raise ValueError("existing cycle identity/schema mismatch")
            if state["status"] == "SATURDAY_PROVISIONAL":
                if state["packet_file"] != "IPR-Briefs-Editorial-" + week_ending + ".txt":
                    raise ValueError("accepted packet filename escaped its week identity")
                packet = directory / state["packet_file"]
                if hashlib.sha256(packet.read_bytes()).hexdigest() != state["packet_sha256"]:
                    raise ValueError("accepted provisional worksheet changed")
                for filename, sha in state["artifact_sha256"].items():
                    if Path(filename).name != filename or filename.startswith("."):
                        raise ValueError("accepted artifact filename escaped private cycle directory")
                    path = directory / filename
                    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                        raise ValueError("accepted provisional artifact changed")
            return state
        from scripts.author_brief import build_draft
        from scripts.sunday_briefs_auto_writer import choose_evidence, compose
        from scripts.sunday_editorial_handoff import render_packet
        desks = live_editorial_desks()
        with read_only(Path(database)) as conn:
            rows = get_articles_for_desks(window["week_start"], week_ending, desks, conn=conn)
        sidecar = build_draft(rows, desks=desks, week_start=window["week_start"],
                              week_ending=week_ending)
        sidecar["saturday_sunday_cycle"] = {"schema": SCHEMA,
            "identity": "IPR-" + week_ending, "status": "SATURDAY_PROVISIONAL"}
        observed = inventory(week_ending, database=database, desks=desks)
        # The existing full-discovery eligibility checks validate exact source
        # state and rights, not the looser corpus text-count diagnostic.
        eligible = choose_evidence(sidecar, as_of=week_ending, db=database,
                                   discovery_inventory=[])
        if len({row["desk_id"] for row, _ in eligible}) < 2:
            raise ValueError("fewer than two production desks with eligible original evidence")
        state = {"schema": SCHEMA, "identity": "IPR-" + week_ending,
                 "window": window, "inventory": observed, "status": "PREPARED_NO_MODEL",
                 "publication_authorized": False, "email_sent": False}
        scaffold_path = directory / ("IPR-" + week_ending + ".scaffold.json")
        if scaffold_path.exists():
            if scaffold_path.is_symlink() or json.loads(scaffold_path.read_text()) != sidecar:
                raise ValueError("prepared scaffold changed; owner reconciliation required")
        else:
            write_private(scaffold_path, sidecar)
        if not execute_model:
            # No permanent reservation: this is an inspectable offline scaffold,
            # never a claim that the model draft was accepted or sent.
            return state
        # Reserve before paid work; an interrupted/ambiguous call is held and
        # cannot be automatically retried. Accepted output gets a new receipt.
        reservation = directory / ("IPR-" + week_ending + ".model-attempt.json")
        write_private(reservation, {"status": "MODEL_ATTEMPT_RESERVED", "identity": state["identity"]})
        from core.brief_story_discovery import NoQualifyingStory
        try:
            manuscript = compose(sidecar, week_ending, db=database, client=client,
                                 automatic_story_selection=True, saturday_provisional=True)
        except NoQualifyingStory as exc:
            write_private(directory / ("IPR-" + week_ending + ".selection.json"), exc.receipt)
            state.update(status="ABSTAINED_NO_QUALIFYING_STORY")
            write_private(state_path, state)
            return state
        manuscript_name = "IPR-" + week_ending + ".manuscript.json"
        write_private(directory / manuscript_name, manuscript)
        text = render_packet(sidecar, manuscript=manuscript, as_of=week_ending,
                             saturday_provisional=True)
        from scripts.sunday_editor_docx import render_editor_docx
        word = render_editor_docx(text)
        packet_name = "IPR-Briefs-Editorial-" + week_ending + ".txt"
        write_private(directory / packet_name, text)
        write_private(directory / packet_name.replace(".txt", ".docx"), word)
        artifact_names = (packet_name, packet_name.replace(".txt", ".docx"),
                          manuscript_name, scaffold_path.name)
        state.update(status="SATURDAY_PROVISIONAL", packet_file=packet_name,
                     packet_sha256=hashlib.sha256(text.encode()).hexdigest(),
                     artifact_sha256={name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                      for name in artifact_names})
        if inventory(week_ending, database=database) != observed:
            state["status"] = "HELD_EVIDENCE_CHANGED_DURING_DRAFT"
        write_private(state_path, state)
        return state


def reconcile(state, sidecar, *, database=DB_PATH, marker_path=MARKER, now=None,
              reviewed_by="", review_reference="", decisions=None):
    """Prepare a Sunday source receipt, never infer human factual verification."""
    week = state["window"]["week_ending"]
    if state.get("schema") != SCHEMA or state.get("status") != "SATURDAY_PROVISIONAL":
        raise ValueError("Sunday recheck requires an accepted Saturday provisional draft")
    if sidecar.get("week_ending") != week or sidecar.get("week_start") != state["window"]["week_start"]:
        raise ValueError("final manuscript escaped the reporting week")
    window = collection_window(week, "sunday", now=now, marker_path=marker_path)
    current = inventory(week, database=database)
    delta = compare(state["inventory"], current)
    required = {kind + ":" + ident for kind in ("added", "removed", "changed")
                for ident in delta[kind]}
    required.update(kind for kind in ("policy_changed", "desks_changed") if delta[kind])
    decisions = decisions or {}
    # A human can adjudicate genuine late changes, but only against this exact
    # diff, current inventory and revised manuscript. No general bypass flag.
    resolved = set(decisions) == required and all(
        isinstance(item, dict) and item.get("disposition") == "resolved"
        and all(isinstance(item.get(key), str) and item[key].strip()
                for key in ("reason", "reviewed_by", "reference"))
        and item.get("inventory_sha256") == digest(current)
        and item.get("manuscript_sha256") == manuscript_digest(sidecar)
        for item in decisions.values())
    held = bool(required) and not resolved
    receipt = {"schema": SCHEMA, "identity": state["identity"],
               "status": "HELD" if held else "SUNDAY_RECHECKED",
               "week_ending": week, "collection_day": window["collection_day"],
               "inventory_sha256": digest(current), "packet_sha256": state["packet_sha256"],
               "manuscript_sha256": manuscript_digest(sidecar), "changes": delta,
               "change_decisions": decisions,
               "source_claim_review": {"reviewed_by": reviewed_by, "reference": review_reference},
               "program_verified_facts": False, "publication_authorized": False}
    if not reviewed_by.strip() or not review_reference.strip():
        receipt["status"] = "HELD"
        receipt["review_required"] = "explicit independent source-to-claim review reference missing"
    return receipt


def deliver(state, directory, *, send=False, owner_confirmed=False,
            approved_sha256="", marker_path=MARKER, now=None, database=DB_PATH,
            analyst_routing=False):
    """No-send by default; uncertain SMTP attempts hold instead of double-send.

    The durable private directory must survive runners/restarts before this
    interface may be connected to unattended dispatch. A reservation is not a
    delivery confirmation: on SMTP failure the owner must inspect Sent.
    ``analyst_routing`` recomputes the Track C route from durable receipts and
    sends only the provisional or owner-reconciled exact revised manuscript.
    """
    from scripts.sunday_editorial_handoff import send_packet, single_address
    from scripts.sunday_send_reviewed_packet import validate_file
    week = state["window"]["week_ending"]
    collection_window(week, "saturday", now=now, marker_path=marker_path)
    directory = private_directory(directory)
    if state.get("status") != "SATURDAY_PROVISIONAL":
        raise ValueError("editor handoff requires an accepted provisional manuscript")
    if state["packet_file"] != "IPR-Briefs-Editorial-" + week + ".txt":
        raise ValueError("accepted packet filename escaped its week identity")
    packet = directory / state["packet_file"]
    expected, decision = state["packet_sha256"], None
    if analyst_routing:
        from scripts.brief_editorial_routing import durable_directory, route
        durable_directory(directory)
        decision = route(state, directory, now=now)
        if decision["route"] not in ("NO_ANALYST", "DELIVER_PROVISIONAL", "DELIVER_REVISED"):
            raise ValueError("editor delivery held by analyst routing: " + decision["route"])
        if decision["route"] == "DELIVER_REVISED":
            packet, expected = directory / decision["packet_file"], decision["packet_sha256"]
    elif (directory / ("analyst-week-" + week + ".json")).exists():
        raise ValueError("an analyst assignment exists for this week; deliver with analyst routing")
    payload = validate_file(packet, week, now=now, saturday_provisional=True)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError("accepted provisional manuscript fingerprint changed")
    if any(compare(state["inventory"], inventory(week, database=database)).values()):
        raise ValueError("source evidence or permissions changed after drafting; hold editor delivery")
    result = {"status": "EDITOR_PREPARED", "packet_sha256": actual,
              "email_sent": False, "publication_authorized": False}
    if decision is not None:
        result["analyst_route"] = decision["route"]
    if not send:
        return result
    if not owner_confirmed or approved_sha256 != actual:
        raise ValueError("editor send requires explicit owner review of the exact attachment SHA")
    for flag in ("IPR_EDITOR_DELIVERY_ENABLED", "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED"):
        if os.environ.get(flag, "").lower() == "true":
            raise ValueError("legacy editor delivery must be disabled before new cycle email")
    editor = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    owner = single_address(os.environ.get("IPR_PREVIEW_TO", ""), "IPR_PREVIEW_TO")
    if editor.casefold() == owner.casefold():
        raise ValueError("editor and owner recipients must differ")
    # Reservation key includes phase/week/recipient, while exact bytes and
    # source snapshot remain bound in its private content. A revised payload
    # cannot obtain another automatic send for the same editor/week.
    key = digest({"identity": state["identity"], "phase": "editor",
                  "recipient": editor.casefold()})
    write_private(directory / ("dispatch-" + key + ".json"),
                  {"status": "DELIVERY_ATTEMPT_RESERVED", "packet_sha256": actual,
                   "source_inventory_sha256": digest(state["inventory"]),
                   "recipient": editor, "identity": state["identity"]})
    with tempfile.TemporaryDirectory(prefix="ipr-editor-snapshot-", dir=directory) as folder:
        frozen = Path(folder) / state["packet_file"]
        write_private(frozen, payload)
        send_packet(frozen, week, provisional=True, full_week=True,
                    owner_released=True, saturday_provisional=True)
    write_private(directory / ("delivered-" + key + ".json"),
                  {"status": "EDITOR_SENT", "packet_sha256": actual})
    result.update(status="EDITOR_SENT", email_sent=True)
    return result


def readiness_problems(sidecar, *, database=DB_PATH):
    """Real author_brief readiness/approval consumes participating cycle receipts."""
    problems = receipt_problems(sidecar)
    if problems or "saturday_sunday_cycle" not in sidecar:
        return problems
    receipt = sidecar["saturday_sunday_cycle"]
    week = sidecar["week_ending"]
    if receipt.get("inventory_sha256") != digest(inventory(week, database=database)):
        return ["Sunday source inventory or rights/status changed; reconcile again"]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sat = sub.add_parser("prepare")
    sat.add_argument("--week-ending", required=True)
    sat.add_argument("--private-dir", type=Path, required=True)
    sat.add_argument("--execute-model", action="store_true")
    sun = sub.add_parser("recheck")
    sun.add_argument("--state", type=Path, required=True)
    sun.add_argument("--manuscript", type=Path, required=True)
    sun.add_argument("--out", type=Path, required=True)
    sun.add_argument("--reviewed-by", default="")
    sun.add_argument("--review-reference", default="")
    sun.add_argument("--decisions", type=Path,
                     help="private exact-diff human resolution receipts; never inferred")
    for p in (sat, sun):
        p.add_argument("--db", type=Path, default=DB_PATH)
        p.add_argument("--marker", type=Path, default=MARKER)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.week_ending, args.private_dir, database=args.db,
                             marker_path=args.marker, execute_model=args.execute_model)
        else:
            state = json.loads(args.state.read_text())
            sidecar = json.loads(args.manuscript.read_text())
            result = reconcile(state, sidecar, database=args.db, marker_path=args.marker,
                               reviewed_by=args.reviewed_by, review_reference=args.review_reference,
                               decisions=json.loads(args.decisions.read_text()) if args.decisions else None)
            # Private output contains the exact candidate and its guarded review
            # receipt; copying into canonical briefs remains a controlled step.
            private_directory(args.out.parent)
            sidecar["saturday_sunday_cycle"] = result
            write_private(args.out, sidecar)
        print(json.dumps({"status": result["status"], "email_sent": False,
                          "publication_authorized": False}))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
