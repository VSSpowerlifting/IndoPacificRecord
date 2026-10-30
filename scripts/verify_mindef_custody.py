#!/usr/bin/env python3
"""Restore an independently fetched PRIVATE custody ref; report hashes only."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.stage_mindef_public_projection import (
    _outside_checkout, _sha256, _assert_integrity, _article_digest,
)
from core.mindef_public_boundary import table_digests


def restore(payload, destination, expected_commit):
    payload, destination = Path(payload).resolve(), Path(destination).resolve()
    _outside_checkout(payload)
    _outside_checkout(destination)
    commit = subprocess.check_output(
        ["git", "-C", str(payload), "rev-parse", "HEAD"], text=True).strip()
    remote = subprocess.check_output(
        ["git", "-C", str(payload), "remote", "get-url", "origin"], text=True).strip()
    if commit != expected_commit or remote != "https://github.com/VSSpowerlifting/ipr-source-evidence-private.git":
        raise ValueError("private custody origin or pinned commit mismatch")
    manifest = json.loads((payload / "manifest.json").read_text())
    compressed = payload / "database.sqlite.gz"
    if _sha256(compressed) != manifest["compressed_db_sha256"]:
        raise ValueError("compressed custody digest mismatch")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out, gzip.open(compressed, "rb") as source:
            shutil.copyfileobj(source, out)
            out.flush()
            os.fsync(out.fileno())
        if _sha256(destination) != manifest["private_db_sha256"]:
            raise ValueError("restored SQLite byte digest mismatch")
        with sqlite3.connect(destination.as_uri() + "?mode=ro&immutable=1", uri=True) as con:
            _assert_integrity(con)
            if table_digests(con, exclude_mindef=True) != manifest["all_non_mindef_table_digests"]:
                raise ValueError("restored table parity mismatch")
            if _article_digest(con, "s.slug=?") != manifest["private_mindef_article_digest"]:
                raise ValueError("restored source record parity mismatch")
            count = con.execute("SELECT count(*) FROM articles WHERE source_id IN "
                "(SELECT id FROM sources WHERE slug='sg_mindef_releases')").fetchone()[0]
            if count != manifest["source_record_count"] or count != len(manifest["record_bindings"]):
                raise ValueError("restored source count mismatch")
            for binding in manifest["record_bindings"]:
                row = dict(con.execute("SELECT * FROM articles WHERE id=?", (binding["id"],)).fetchone())
                for name, expected in binding.items():
                    if name == "expression_hashes":
                        if any(hashlib.sha256((row[c] or "").encode()).hexdigest() != h
                               for c, h in expected.items()):
                            raise ValueError("restored expression hash mismatch")
                    elif row[name] != expected:
                        raise ValueError("restored source provenance mismatch")
        return {
            "schema": "ipr-mindef-private-restore/1",
            "private_git_commit": commit,
            "manifest_sha256": _sha256(payload / "manifest.json"),
            "restored_db_sha256": _sha256(destination),
            "source_git_commit": manifest["source_git_commit"],
            "source_db_sha256": manifest["source_db_sha256"],
            "public_candidate_db_sha256": manifest["public_candidate_db_sha256"],
            "source_record_count": count,
            "record_bindings_and_expression_hashes_verified": True,
            "integrity_and_foreign_keys_verified": True,
            "all_other_tables_verified": True,
            "durable_private_custody_confirmed": True,
            "independent_provider_backup": False,
            "public_release_approved": False,
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--restore", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(restore(args.payload, args.restore, args.expected_commit), sort_keys=True, indent=2))
