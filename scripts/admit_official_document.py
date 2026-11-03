"""Apply an exact editorial selection to an already-captured official document.

Supported family: vn_vpcp_official_documents_vi only; any other family holds.
The Daily collector is the single public writer and applies the committed
selection on every run. This CLI reports the same disposition from a read-only
copy, or with --write applies it to an isolated candidate database outside the
repository. It never fetches a publisher, reads a private body, calls a model,
renders or deploys. A pinned version that was never captured holds: individual
fetch of an unlisted URL is outside the adapter's access contract.

    python -m scripts.admit_official_document \\
        --family vn_vpcp_official_documents_vi --identity vpcp-vi:NNNNNN \\
        --database CANDIDATE.db [--selection FILE] [--private-record FILE] [--write]

--private-record is a sealed record from the private archive branch, read for
hashes only; its MAC is verified when VIETNAM_PRIVATE_BRIDGE_KEY is set.
--private-original is that record's original bytes (state/captures/<pdf>.bin):
their SHA-256 and extracted-content hash are replayed against the record.
The selection pins public metadata, not original content: `custody` reports
the private original separately and is "authenticated" only when the MAC
verified and both hashes replayed; otherwise it names the blocker.
Exit codes: 0 disposition reported, 2 held, 3 unsupported family.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from core.collection.vietnam_government_documents import FAMILY, digest, identity
from processing.government_document_intake import SELECTION, admit, need, selection
from processing.vpcp_document import inspect_pdf

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = Path.home() / "pla-watch/pla_watch.db"


def outside_repo(path, reason):
    need(not path.is_symlink(), reason)
    target = path.resolve()
    need(target != PRODUCTION.resolve() and not target.is_relative_to(ROOT), reason)
    return target


def private_readback(path, pin, original=None):
    """Hash-only readback of a sealed private capture; content is never emitted."""
    raw = outside_repo(path, "private_record_location_refused").read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    need(len(raw) <= 32000 and path.name == sha + ".json", "private_record_hash_mismatch")
    sealed = json.loads(raw)
    need(type(sealed) is dict and set(sealed) == {"capture", "mac"}, "private_record_invalid")
    cap = sealed["capture"]
    need(cap.get("schema") == "ipr-vpcp-private-capture/1"
         and cap["metadata_sha256"] == digest(cap["metadata"]), "private_record_invalid")
    need(cap["metadata_sha256"] == pin, "private_record_pin_mismatch")
    key = os.environ.get("VIETNAM_PRIVATE_BRIDGE_KEY", "").encode()
    mac = "unverified_key_absent"
    if len(key) >= 32:
        payload = json.dumps(cap, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        need(hmac.compare_digest(sealed["mac"], hmac.new(
            key, b"IPR-VPCP-CAPTURE-v1\n" + payload, hashlib.sha256).hexdigest()), "private_record_mac_invalid")
        mac = "verified"
    replay = "original_not_supplied"
    if original is not None:
        data = outside_repo(original, "private_original_location_refused").read_bytes()
        need(hashlib.sha256(data).hexdigest() == cap["pdf_sha256"], "private_original_hash_mismatch")
        reading = inspect_pdf(data, cap["metadata"], expected_sha256=cap["pdf_sha256"])
        need(reading["content_sha256"] == cap["content_sha256"], "private_content_hash_mismatch")
        replay = "replayed"
    blockers = [b for b, ok in (("bridge_key_absent", mac == "verified"),
                                ("original_not_supplied", replay == "replayed")) if not ok]
    return {"record_sha256": sha, "source_identity": identity(cap["metadata"]),
            "metadata_sha256": cap["metadata_sha256"], "pdf_sha256": cap["pdf_sha256"],
            "content_sha256": cap["content_sha256"], "source_run": cap["source_run"],
            "observed_utc": cap["observed_utc"], "mac": mac, "original_replay": replay,
            "custody": "authenticated" if not blockers else "blocked:" + ",".join(blockers)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--family", required=True)
    p.add_argument("--identity", required=True)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--selection", type=Path, default=SELECTION)
    p.add_argument("--private-record", type=Path)
    p.add_argument("--private-original", type=Path, help="original bytes named by --private-record")
    p.add_argument("--write", action="store_true", help="apply to an isolated candidate database")
    args = p.parse_args(argv)
    if args.family != FAMILY:
        print(json.dumps({"source_family": args.family, "status": "held",
                          "reason": "unsupported_family", "model_calls": 0}))
        return 3
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {"source_family": FAMILY, "source_identity": args.identity, "model_calls": 0}
    try:
        chosen = selection(args.selection)
        entry = [e for e in chosen["selections"] if e["source_identity"] == args.identity]
        need(entry, "identity_not_selected")
        report.update({"selection_sha256": digest(chosen), "pinned_metadata_sha256": entry[0]["metadata_sha256"]})
        need(args.private_record or not args.private_original, "private_original_without_record")
        if args.private_record:
            report["private_readback"] = private_readback(args.private_record, entry[0]["metadata_sha256"],
                                                          args.private_original)
        need(args.database.is_file() and not args.database.is_symlink(), "database_unavailable")
        if args.write:
            conn = sqlite3.connect(str(outside_repo(args.database, "candidate_db_not_isolated")), timeout=30)
        else:
            # Disposition only: replay against an in-memory copy.
            conn = sqlite3.connect(":memory:")
            uri = args.database.resolve().as_uri()
            try:
                source = sqlite3.connect(uri + "?mode=ro", uri=True)
                source.execute("SELECT count(*) FROM sqlite_master").fetchone()
            except sqlite3.OperationalError:
                # A clean WAL copy has no -shm, which read-only mode cannot
                # create; with no -wal either, the main file is complete.
                need(not Path(str(args.database) + "-wal").exists(), "database_unavailable")
                source = sqlite3.connect(uri + "?immutable=1", uri=True)
            with source:
                source.backup(conn)
            source.close()
        source_sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        with conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            result = admit(conn, [], source_sha=source_sha,
                           run_id="manual-" + now.replace("-", "").replace(":", ""),
                           observed_utc=now, selection_path=args.selection)
            need(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",), "integrity_failed")
        conn.close()
        disposition = result["selection"][args.identity]
        # The same run reconciles every entry; side effects on others are reported too.
        report["other_dispositions"] = {k: v for k, v in result["selection"].items() if k != args.identity}
        report.update({"disposition": disposition, "written": args.write, "model_calls": result["model_calls"],
                       "status": "ok" if disposition in ("selection_admitted", "selection_unchanged") else "held"})
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "ok" else 2
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, subprocess.CalledProcessError) as error:
        report.update({"status": "held", "reason": str(error.args[0]) if error.args else type(error).__name__})
        print(json.dumps(report, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
