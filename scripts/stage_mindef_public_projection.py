#!/usr/bin/env python3
"""Offline, non-destructive staging of a private original and public-safe candidate.

This is a migration *staging* tool, not a deployment or a source-use license.
It never edits the source DB or existing files, and it refuses to stage any
copies inside the public checkout. Durable private custody, new collection
routing, regenerated pages, external references and history require separate
gates before public publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.mindef_permissions import MINDEF_SOURCE_SLUG
from core.mindef_public_boundary import (RESTRICTED_COLUMNS, table_digests,
    expression_probes, assert_no_expression_bytes, project, assert_projected)
from scripts.audit_mindef_public_surfaces import _sha256
from scripts.reconcile_db import read_only

# Expression-bearing official captures and derivative machine text. Source ID,
# canonical URL, collection dates, original immutable content hash and record
# ID remain for provenance. This is NOT a license for publication of URLs.
PRESERVED_COLUMNS = (
    "id", "url", "content_hash", "source_id", "scrape_run_id",
    "published_date", "scraped_at",
)


def _outside_checkout(path):
    resolved = path.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("staging destinations must be outside the public checkout")


def _article_digest(con, predicate):
    con.row_factory = sqlite3.Row
    digest = hashlib.sha256()
    for row in con.execute(
        "SELECT a.* FROM articles a JOIN sources s ON s.id=a.source_id "
        "WHERE " + predicate + " ORDER BY a.id",
        (MINDEF_SOURCE_SLUG,)):
        digest.update(json.dumps(dict(row), sort_keys=True, ensure_ascii=False,
                                 default=str, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _source_counts(con):
    con.row_factory = sqlite3.Row
    return dict(con.execute(
        "SELECT s.slug, COUNT(a.id) AS n FROM sources s "
        "LEFT JOIN articles a ON a.source_id=s.id "
        "GROUP BY s.slug ORDER BY s.slug").fetchall())


def _assert_integrity(con):
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("sqlite integrity check failed")
    if con.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("sqlite foreign-key check failed")


def _copy_db(source_con, dest):
    fd = os.open(str(dest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    dest.chmod(0o600)
    with sqlite3.connect(str(dest)) as out:
        source_con.backup(out)
        _assert_integrity(out)


def stage(source, private, public, manifest):
    source, private, public, manifest = map(lambda p: Path(p).resolve(),
                                           (source, private, public, manifest))
    paths = [private, public, manifest]
    if len({str(p) for p in [source] + paths}) != 4:
        raise ValueError("source and three output files must be different")
    if not source.is_file():
        raise ValueError("source DB missing")
    for path in paths:
        _outside_checkout(path)
        if not path.parent.is_dir():
            raise ValueError("destination directory does not exist")
        if path.exists() or path.is_symlink():
            raise ValueError("refusing to overwrite existing staging file")
    if any(Path(str(source) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("source must be a quiescent checkpointed snapshot, not a live writer")
    before = _sha256(source)
    created = []
    try:
        with read_only(source) as original:
            _assert_integrity(original)
            cols = {r[1] for r in original.execute("PRAGMA table_info(articles)")}
            if not set(RESTRICTED_COLUMNS + PRESERVED_COLUMNS).issubset(cols):
                raise ValueError("source schema lacks required migration columns")
            source_count = original.execute(
                "SELECT count(*) FROM articles a JOIN sources s ON s.id=a.source_id "
                "WHERE s.slug=?", (MINDEF_SOURCE_SLUG,)).fetchone()[0]
            if source_count == 0:
                raise ValueError("no matching Singapore MINDEF source records")
            original_hash = _article_digest(original, "s.slug=?")
            others_hash = _article_digest(original, "s.slug!=?")
            original_counts = _source_counts(original)
            all_tables_before = table_digests(original, exclude_mindef=True)
            probes = expression_probes(original)
            created.append(private)
            _copy_db(original, private)
        with read_only(private) as vault:
            _assert_integrity(vault)
            if _article_digest(vault, "s.slug=?") != original_hash:
                raise ValueError("private custody copy failed original-record verification")
            if _article_digest(vault, "s.slug!=?") != others_hash:
                raise ValueError("private copy changed non-Singapore records")
            created.append(public)
            _copy_db(vault, public)

        with sqlite3.connect(str(public)) as projected:
            project(projected)
            # Rebuild allocated pages. NULL updates alone leave recoverable
            # expression in freelists, journals and overflow pages.
            projected.execute("PRAGMA journal_mode=DELETE")
            projected.execute("VACUUM")
            assert_projected(projected)
            if table_digests(projected, exclude_mindef=True) != all_tables_before:
                raise ValueError("projection changed unrelated table rows")
            _assert_integrity(projected)
            if _article_digest(projected, "s.slug!=?") != others_hash:
                raise ValueError("projection changed unrelated source records")
            if _source_counts(projected) != original_counts:
                raise ValueError("projection changed source row counts")
            query = (
                "SELECT count(*) FROM articles a JOIN sources s ON s.id=a.source_id "
                "WHERE s.slug=? AND (" +
                " OR ".join("NULLIF(TRIM(a." + col + "), '') IS NOT NULL"
                            for col in RESTRICTED_COLUMNS) + ")"
            )
            if projected.execute(query, (MINDEF_SOURCE_SLUG,)).fetchone()[0]:
                raise ValueError("restricted text remains in public projection")

        assert_no_expression_bytes(public, probes)
        if any(Path(str(public) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise ValueError("public candidate has SQLite sidecars")
        if (_sha256(source) != before or any(Path(str(source) + suffix).exists()
                for suffix in ("-wal", "-shm", "-journal"))):
            raise ValueError("source DB mutated during staging")
        receipt = {
            "schema": "ipr-mindef-staged-db-separation/1",
            "source_db_sha256": before,
            "private_db_sha256": _sha256(private),
            "public_candidate_db_sha256": _sha256(public),
            "private_mindef_article_digest": original_hash,
            "all_non_mindef_table_digests": all_tables_before,
            "public_expression_byte_probe_count": len(probes),
            "public_freelist_count": 0,
            "physical_rebuild_verified": True,
            "non_mindef_article_digest_preserved": others_hash,
            "source_slug": MINDEF_SOURCE_SLUG,
            "source_record_count": source_count,
            "restricted_columns_null_in_public_candidate": list(RESTRICTED_COLUMNS),
            "durable_private_custody_confirmed": False,
            "public_release_approved": False,
            "deployment_or_git_history_remediated": False,
        }
        created.append(manifest)
        fd = os.open(str(manifest), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, sort_keys=True)
            f.write("\n")
        return receipt
    except BaseException:
        for path in reversed(created):
            if path.exists():
                path.unlink()
        raise


def install_candidate(source, candidate, staged_receipt, restored, restore_receipt):
    """Install on a quiescent review/release checkout after private readback.

    Caller must serialize the actual release with Daily; this command never
    merges, pushes or deploys. A changed baseline requires renewed custody.
    """
    source, candidate, restored = map(Path, (source, candidate, restored))
    _outside_checkout(candidate)
    _outside_checkout(restored)
    staged, recovery = (json.loads(Path(p).read_text())
                        for p in (staged_receipt, restore_receipt))
    if (not recovery.get("durable_private_custody_confirmed")
            or recovery.get("source_db_sha256") != staged["source_db_sha256"]
            or _sha256(restored) != recovery["restored_db_sha256"]
            or _sha256(source) not in (staged["source_db_sha256"], staged["public_candidate_db_sha256"])
            or _sha256(candidate) != staged["public_candidate_db_sha256"]):
        raise ValueError("custody/candidate/baseline mismatch; restage before cutover")
    for path in (source, candidate):
        if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise ValueError("cutover requires quiescent files without SQLite sidecars")
    with read_only(restored) as vault, read_only(candidate) as public:
        _assert_integrity(vault)
        _assert_integrity(public)
        assert_projected(public)
        if _article_digest(vault, "s.slug=?") != staged["private_mindef_article_digest"]:
            raise ValueError("custody source digest mismatch")
        if table_digests(public, exclude_mindef=True) != table_digests(vault, exclude_mindef=True):
            raise ValueError("unrelated data changed before cutover")
        assert_no_expression_bytes(candidate, expression_probes(vault))
    if _sha256(source) == staged["public_candidate_db_sha256"]:
        return {"public_db_sha256": _sha256(source), "source_records": staged["source_record_count"],
                "private_git_commit": recovery["private_git_commit"], "idempotent_retry": True,
                "release_approved": False}
    # Build beside the target for an atomic rename. Never copy a raw original
    # into the public checkout. Crash before rename leaves the baseline intact.
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix=".mindef-safe-", dir=source.parent)
    try:
        with os.fdopen(fd, "wb") as out, candidate.open("rb") as src:
            shutil.copyfileobj(src, out)
            out.flush()
            os.fsync(out.fileno())
        if (_sha256(source) != staged["source_db_sha256"] or
                any(Path(str(source) + suffix).exists()
                    for suffix in ("-wal", "-shm", "-journal"))):
            raise ValueError("baseline changed during cutover; no overwrite")
        os.replace(temporary, source)
        directory = os.open(str(source.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"public_db_sha256": _sha256(source), "source_records": staged["source_record_count"],
            "private_git_commit": recovery["private_git_commit"], "release_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--private-copy", type=Path)
    parser.add_argument("--public-candidate", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--install", action="store_true", help="Install on a serialized review/release checkout after verified private recovery")
    parser.add_argument("--custody-restored-db", type=Path)
    parser.add_argument("--custody-restore-receipt", type=Path)
    args = parser.parse_args(argv)
    if args.install:
        if not args.custody_restored_db or not args.custody_restore_receipt:
            parser.error("--install requires the restored private DB and its recovery receipt")
        receipt = install_candidate(args.source_db, args.public_candidate, args.receipt,
                                    args.custody_restored_db, args.custody_restore_receipt)
    else:
        if not args.private_copy:
            parser.error("staging requires --private-copy")
        receipt = stage(args.source_db, args.private_copy,
                        args.public_candidate, args.receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
