"""Optional, version-bound title and text for an existing shared Daily Record."""

VERSION = "0025"
NAME = "daily_record_originals"
FIELDS = ("source_family", "source_identity", "capture_sha256", "title_original", "text_original")


def is_already_applied(conn):
    return conn.execute(
        "SELECT 1 FROM main.sqlite_master WHERE type='table' AND name=?", (NAME,)
    ).fetchone() is not None


def up(conn):
    conn.execute("""
        CREATE TABLE daily_record_originals (
            source_family TEXT NOT NULL,
            source_identity TEXT NOT NULL,
            capture_sha256 TEXT NOT NULL,
            title_original TEXT NOT NULL,
            text_original TEXT NOT NULL,
            PRIMARY KEY (source_family, source_identity),
            FOREIGN KEY (source_family, source_identity)
                REFERENCES daily_machine_records(source_family, source_identity)
                ON DELETE CASCADE
        )
    """)
