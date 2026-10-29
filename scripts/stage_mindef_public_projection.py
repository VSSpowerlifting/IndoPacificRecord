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
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.mindef_permissions import MINDEF_SOURCE_SLUG
from scripts.audit_mindef_public_surfaces import _sha256
from scripts.reconcile_db import read_only

# Expression-bearing official captures and derivative machine text. Source ID,
# canonical URL, collection dates, original immutable content hash and record
# ID remain for provenance. This is NOT a license for publication of URLs.
RESTRICTED_COLUMNS = (
    "title_original", "text_original", "title_english", "text_english",
    "summary_english", "relevance_reasoning", "significance_reasoning",
)
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
            columns = ", ".join(col + "=NULL" for col in RESTRICTED_COLUMNS)
            projected.execute(
                "UPDATE articles SET " + columns + " WHERE source_id IN "
                "(SELECT id FROM sources WHERE slug=?)", (MINDEF_SOURCE_SLUG,))
            projected.commit()
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

        if _sha256(source) != before:
            raise ValueError("source DB mutated during staging")
        receipt = {
            "schema": "ipr-mindef-staged-db-separation/1",
            "source_db_sha256": before,
            "private_db_sha256": _sha256(private),
            "public_candidate_db_sha256": _sha256(public),
            "private_mindef_article_digest": original_hash,
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--private-copy", type=Path, required=True)
    parser.add_argument("--public-candidate", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = stage(args.source_db, args.private_copy,
                    args.public_candidate, args.receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
