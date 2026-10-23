"""Bounded metadata-only source step of the shared Daily; no model or deploy.

CLI requires a migrated DB. The Daily owns migrations, commit, renderer and
Pages publication. Publisher originals/attachments are never saved or logged.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from core.collection.contract import CollectionWindow
from core.collection import status as st
from core.collection.host_gate import HostGate
from core.collection.vietnam_government_documents import FAMILY, GovernmentOfficeAdapter, digest
from processing.government_document_intake import admit, policy


def collect(conn, adapter, *, source_sha, run_id, observed_utc):
    policy()  # Refuse before any network request if source use changes.
    discovery = adapter.discover(CollectionWindow(date.fromisoformat(observed_utc[:10])))
    report = {"scope": "published_first_50_listing_entries", "archive_complete": False,
        "issue_date_is_posting_date": False, "attachment_contents_checked": False,
        "listing_sha256": adapter.listing_sha256, "listing_ids": [i["url"] for i in adapter.listed],
        "source_family": FAMILY, "source_run": run_id, "status": "held", "held": 0,
        "excluded_issuer": 0, "model_calls": 0}
    captures = []
    if discovery.ok:
        previous = conn.execute("SELECT report_json FROM official_document_collection_runs "
            "WHERE source_family=? AND status IN ('ok','partial') ORDER BY observed_utc DESC LIMIT 1", (FAMILY,)).fetchone()
        continuity = not previous or bool(set(json.loads(previous[0])["listing_ids"]) & set(report["listing_ids"]))
        # A listing that no longer overlaps the last observed window means the
        # portal moved past 50 entries between runs. Record that coverage gap
        # once and resume from the visible window; never hold the source forever.
        report["coverage_gap"] = not continuity
        report["candidates_skipped_by_budget"] = adapter.candidates_skipped
        for reference in discovery.references:
            capture = adapter.fetch(reference)
            extracted = adapter.extract(capture)
            if not capture.ok or not st.is_success(extracted.status):
                report["held"] += 1
                last = adapter.request_log[-1] if adapter.request_log else {}
                if last.get("stop_host") or last.get("status") in (401, 403):
                    break
                continue
            if not extracted.documents:
                report["excluded_issuer"] += 1
                continue
            captures.append((extracted.documents[0].extra, capture.payload_sha256))
        report.update(admit(conn, captures, source_sha=source_sha, run_id=run_id,
                            observed_utc=observed_utc))
        report["status"] = "partial" if report["held"] else "ok"
    else:
        report["hold_reason"] = "listing_or_access_failed"
    # Includes successful zero-new/duplicate attempts. No quiet day is omitted.
    report["requests"] = len(adapter.request_log)
    old = conn.execute("SELECT report_json FROM official_document_collection_runs "
        "WHERE source_family=? AND source_run=?", (FAMILY, run_id)).fetchone()
    if old:
        raise ValueError("collection_run_id_already_recorded")
    conn.execute("INSERT INTO official_document_collection_runs VALUES (?,?,?,?,?,?)",
        (FAMILY, run_id, observed_utc, source_sha, report["status"], json.dumps(report, sort_keys=True)))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--gate-dir", type=Path, required=True)
    args = p.parse_args(argv)
    source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))
    run_id += "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if not args.database.is_file() or args.database.is_symlink():
            raise ValueError("database_unavailable")
        with sqlite3.connect(str(args.database), timeout=30) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            report = collect(conn, GovernmentOfficeAdapter(gate=HostGate(args.gate_dir)),
                source_sha=source_sha, run_id=run_id, observed_utc=now)
            if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("integrity_failed")
        # Fixed fields only. No original HTML, government subject or response body.
        print(json.dumps({k: v for k, v in report.items() if k != "listing_ids"}, sort_keys=True))
        return 0 if report["status"] == "ok" else 2
    except (ValueError, OSError, sqlite3.Error):
        print(json.dumps({"source_family": FAMILY, "status": "held", "model_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
