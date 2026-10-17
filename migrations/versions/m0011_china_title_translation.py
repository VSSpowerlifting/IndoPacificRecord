"""0011 — title-only receipts/claims on articles; no observed data backfill.

0010 belongs to the regional source index. No separate metadata store.
The existing title, analysis and source bytes are untouched by this migration.
"""
VERSION = "0011"
NAME = "china_title_translation"
COLUMNS = (
    ("title_translation_source_sha256", "TEXT"),
    ("title_translation_model", "TEXT"),
    ("title_translation_prompt", "TEXT"),
    ("title_translated_at", "TEXT"),
    ("title_translation_attempts", "INTEGER"),
    ("title_translation_state", "TEXT"),
    ("title_translation_claim", "TEXT"),
    ("title_translation_claimed_at", "TEXT"),
    ("title_translation_attempt_source", "TEXT"),
)


def is_already_applied(conn):
    columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    return all(name in columns for name, _ in COLUMNS)


def up(conn):
    columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    for name, kind in COLUMNS:
        if name not in columns:
            conn.execute("ALTER TABLE articles ADD COLUMN %s %s" % (name, kind))
