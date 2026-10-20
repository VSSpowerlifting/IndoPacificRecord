"""Public-safe machine records in the existing corpus DB; never originals."""
VERSION = "0015"
NAME = "daily_machine_records"
DDL = """CREATE TABLE daily_machine_records (
 source_family TEXT NOT NULL,
 source_identity TEXT NOT NULL,
 metadata_version_sha256 TEXT NOT NULL,
 content_sha256 TEXT NOT NULL,
 capture_sha256 TEXT NOT NULL,
 source_git_commit TEXT NOT NULL,
 source_run TEXT NOT NULL,
 summary TEXT NOT NULL,
 categories_json TEXT NOT NULL,
 model_flagged INTEGER NOT NULL CHECK(model_flagged IN (0,1)),
 flag_reason TEXT,
 model_id TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 quality_sha256 TEXT NOT NULL,
 policy_sha256 TEXT NOT NULL,
 publication_state TEXT NOT NULL DEFAULT 'released' CHECK(publication_state IN ('released','held')),
 PRIMARY KEY(source_family, source_identity),
 FOREIGN KEY(source_family, source_identity)
 REFERENCES regional_official_source_links(source_family, source_identity)
)"""


def is_already_applied(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name='daily_machine_records'").fetchone() is not None


def up(conn):
    if not is_already_applied(conn):
        conn.execute(DDL)
