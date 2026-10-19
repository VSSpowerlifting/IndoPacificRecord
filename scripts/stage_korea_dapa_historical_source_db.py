"""Stage one private, genuine DAPA source SQLite; never approve/publicly release.

Run only against the verified private evidence checkout. No government GET.
The original extraction_failure record is never modified or reclassified.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
from pathlib import Path

from core import korea_dapa_historical_owner as hist
from core import korea_dapa_private_to_production as b


def stage(checkout):
    root = Path(checkout).resolve(strict=True)
    b.need(root.is_dir() and not root.is_symlink()
           and b._git(root, "branch", "--show-current") == b.REF
           and b._git(root, "rev-parse", "--show-toplevel") == str(root)
           and b._git(root, "status", "--porcelain") == "",
           "historical_private_checkout_must_be_clean")
    b._git(root, "merge-base", "--is-ancestor", hist.OWNER_COMMIT, "HEAD")
    base = root / hist.RELATIVE
    manifest = json.loads(hist._read(base, "historical_manifest.json", 15000))
    b.need(manifest.get("source_identity") == hist.IDENTITY
           and manifest.get("source_day") == hist.DATE
           and manifest.get("original_ledger_result") == "extraction_failure"
           and manifest.get("offline_adapter_replay_passed") is True
           and manifest.get("original_attempt_reclassified") is False
           and manifest.get("public_metadata_admission_approved") is False,
           "historical_staging_manifest_invalid")
    b.need(hist._hash(hist._read(base, "failed_original_ledger.json", 200000)) == hist.LEDGER_SHA,
           "historical_staging_failed_ledger_drift")
    for sha in (hist.ROBOTS_SHA, hist.LISTING_SHA, hist.HTML_SHA):
        b.need(hist._hash(hist._read(base, "captures/" + sha + ".bin", 12_000_000)) == sha,
               "historical_staging_original_capture_drift")
    raw = hist._read(base, hist.HWPX_SHA + ".hwpx", 2_000_000)
    b.need(len(raw) == 230559 and hist._hash(raw) == hist.HWPX_SHA,
           "historical_staging_original_hwpx_drift")
    from scraper.sources.kr_dapa_policy_briefing import KoreaDapaPolicyAdapter
    from scraper.sources.kr_policy_briefing import hwpx_text
    try:
        title, day, document = KoreaDapaPolicyAdapter.metadata(
            None, hist._read(base, "captures/" + hist.HTML_SHA + ".bin").decode("utf-8"), hist.URL)
        extracted = hwpx_text(raw)
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        raise b.DAPABridgeHold("historical_staging_parser_hold") from exc
    b.need(day == hist.DATE and "fileId=198570147" in document
           and hist._hash(title.encode("utf-8")) == hist.TITLE_SHA
           and hist._hash(extracted.encode("utf-8")) == hist.TEXT_SHA,
           "historical_staging_original_identity_mismatch")
    dbpath = base / "historical_source.db"
    b.need(not dbpath.exists() and not dbpath.is_symlink(),
           "historical_private_db_already_exists_no_overwrite")
    with sqlite3.connect(dbpath) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("CREATE TABLE historical_dapa_sources ("
                     "source_identity TEXT PRIMARY KEY NOT NULL,"
                     "original_article_sha256 TEXT NOT NULL,"
                     "original_hwpx_sha256 TEXT NOT NULL,"
                     "original_failed_ledger_sha256 TEXT NOT NULL)")
        conn.execute("INSERT INTO historical_dapa_sources VALUES (?,?,?,?)",
                     (hist.IDENTITY, hist.HTML_SHA, hist.HWPX_SHA, hist.LEDGER_SHA))
        conn.commit()
        b.need(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",),
               "historical_private_db_integrity_fail")
    os.chmod(dbpath, 0o600)
    return {"status": "PRIVATE_HISTORICAL_SOURCE_DB_STAGED_NOT_APPROVED",
            "source_identity": hist.IDENTITY,
            "source_db_sha256": hist._hash(dbpath.read_bytes()),
            "original_attempt_reclassified": False,
            "public_admission_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--private-checkout", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(stage(args.private_checkout), sort_keys=True))
        return 0
    except (b.DAPABridgeHold, OSError, sqlite3.Error, ValueError) as exc:
        print(json.dumps({"status": "HOLD",
                          "reason": str(exc) if isinstance(exc, b.DAPABridgeHold)
                          else "dapa_historical_private_staging_error",
                          "public_admission_approved": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
