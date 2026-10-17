"""0011 — add independently identified DAPA official-link rows to Korea metadata.

Rebuild the existing, MND-only reference table transactionally. Keep exact
column ordering, all prior rows, source hashes, dates and release timestamps.
This migration authorizes NO DAPA record or public release by itself.
"""
from __future__ import annotations

import sqlite3

from migrations.versions.m0008_korea_official_source_metadata import (
    EXPECTED_COLUMNS, INDEX, TABLE,
)

VERSION = "0011"
NAME = "korea_dapa_metadata_source_separation"
TEMP = "korea_official_source_records_v11"

SCHEMA = """
CREATE TABLE korea_official_source_records_v11 (
    source_identity TEXT PRIMARY KEY NOT NULL,
    canonical_official_url TEXT NOT NULL UNIQUE,
    publisher_posted_date TEXT NOT NULL,
    source_git_commit TEXT NOT NULL,
    source_db_sha256 TEXT NOT NULL,
    candidate_version_sha256 TEXT NOT NULL,
    original_title_sha256 TEXT NOT NULL,
    original_text_sha256 TEXT NOT NULL,
    publisher_html_sha256 TEXT NOT NULL,
    original_hwpx_sha256 TEXT NOT NULL,
    official_issuer TEXT NOT NULL
        CHECK (official_issuer IN ('kr_mnd', 'kr_dapa')),
    official_republisher TEXT NOT NULL
        CHECK (official_republisher = 'kr_policy_briefing'),
    source_language TEXT NOT NULL CHECK (source_language = 'ko'),
    authority_tier TEXT NOT NULL CHECK (authority_tier = 'B'),
    originality TEXT NOT NULL CHECK (originality = 'syndicated'),
    public_scope TEXT NOT NULL DEFAULT 'held'
        CHECK (public_scope IN ('held', 'official_link_only')),
    admitted_at_utc TEXT,
    released_at_utc TEXT,
    CHECK (
      (official_issuer = 'kr_mnd'
       AND length(source_identity) = 22
       AND substr(source_identity, 1, 13) = 'korea-policy:'
       AND substr(source_identity, 14) NOT GLOB '*[^0-9]*'
       AND canonical_official_url =
         'https://www.korea.kr/briefing/pressReleaseView.do?newsId=' ||
         substr(source_identity, 14))
      OR
      (official_issuer = 'kr_dapa'
       AND length(source_identity) = 27
       AND substr(source_identity, 1, 18) = 'korea-dapa-policy:'
       AND substr(source_identity, 19) NOT GLOB '*[^0-9]*'
       AND canonical_official_url =
         'https://www.korea.kr/briefing/pressReleaseView.do?newsId=' ||
         substr(source_identity, 19))
    ),
    CHECK (length(source_git_commit) = 40),
    CHECK (length(source_db_sha256) = 64),
    CHECK (length(candidate_version_sha256) = 64),
    CHECK (length(original_title_sha256) = 64),
    CHECK (length(original_text_sha256) = 64),
    CHECK (length(publisher_html_sha256) = 64),
    CHECK (length(original_hwpx_sha256) = 64),
    CHECK (length(publisher_posted_date) = 10
           AND publisher_posted_date GLOB
             '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'),
    CHECK (public_scope = 'held' OR
           (admitted_at_utc IS NOT NULL AND released_at_utc IS NOT NULL))
)
"""


def _existing(conn):
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE,),
    ).fetchone()


def is_already_applied(conn: sqlite3.Connection) -> bool:
    row = _existing(conn)
    if row is None:
        return False
    columns = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    if columns != EXPECTED_COLUMNS:
        raise ValueError("Korea metadata schema drift: cannot migrate")
    if "korea-dapa-policy:" not in row[0]:
        return False
    # Reintroduced rows without the source/issuer coupling are unsafe.
    for required in ("official_issuer = 'kr_dapa'",
                     "official_issuer = 'kr_mnd'",
                     "korea-dapa-policy:", "korea-policy:"):
        if required not in row[0]:
            raise ValueError("Korea combined-issuer schema drift")
    return True


def up(conn: sqlite3.Connection) -> None:
    if is_already_applied(conn):
        return
    if _existing(conn) is None:
        raise ValueError("Korea MND metadata table must exist before 0011")
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name=?", (TEMP,)
    ).fetchone():
        raise ValueError("unreviewed Korea metadata migration scratch table")
    # Migration runner supplies its own transaction and foreign-key check.
    # No partial destructive drop is allowed outside that runner.
    conn.execute(SCHEMA)
    old_cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)]
    new_cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % TEMP)]
    if old_cols != new_cols:
        raise ValueError("Korea metadata column order changed")
    old_count = conn.execute("SELECT COUNT(*) FROM %s" % TABLE).fetchone()[0]
    conn.execute("INSERT INTO %s SELECT * FROM %s" % (TEMP, TABLE))
    if conn.execute("SELECT COUNT(*) FROM %s" % TEMP).fetchone()[0] != old_count:
        raise ValueError("Korea source metadata row count mismatch")
    conn.execute("DROP TABLE %s" % TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, TABLE))
    conn.execute(INDEX)
    if not is_already_applied(conn):
        raise ValueError("DAPA source-family schema was not installed")
