"""0016 — ledger for governed Korean MND admission into the shared corpus.

Creates an empty ledger, without admitting, processing or publishing anything.
One row per Korean source identity records which exact released source version
(original-text, release-decision and policy digests) was admitted to which
`articles` row, and where that record stands in Korea-specific processing.

The ledger is what makes the bridge exactly-once per source version: a replay
finds the identity and version already present and writes nothing; a changed
version is held rather than silently overwritten. Hold and QA reasons are fixed
machine codes only; no Korean title, body or model output is ever stored here.
"""
import sqlite3

VERSION = "0016"
NAME = "korea_corpus_admissions"

HEX = "length(%s) = 64 AND %s NOT GLOB '*[^0-9a-f]*'"

DDL = """
CREATE TABLE IF NOT EXISTS korea_corpus_admissions (
    source_identity          TEXT PRIMARY KEY NOT NULL
                             CHECK(source_identity GLOB
                               'korea-policy:[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
    article_id               INTEGER UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    canonical_official_url   TEXT NOT NULL CHECK(canonical_official_url GLOB
                               'https://www.korea.kr/briefing/pressReleaseView.do?newsId=[0-9]*'),
    publisher_posted_date    TEXT NOT NULL,
    original_text_sha256     TEXT NOT NULL CHECK(%(text)s),
    document_heading_sha256  TEXT CHECK(document_heading_sha256 IS NULL OR (%(head)s)),
    release_decision_sha256  TEXT NOT NULL CHECK(%(rel)s),
    policy_sha256            TEXT NOT NULL CHECK(%(pol)s),
    bridge_version           TEXT NOT NULL,
    state                    TEXT NOT NULL CHECK(state IN
                               ('admitted', 'held', 'withdrawn')),
    hold_reason              TEXT CHECK(hold_reason IS NULL OR
                               hold_reason GLOB '[a-z]*' AND
                               hold_reason NOT GLOB '*[^a-z0-9_]*'),
    processing_state         TEXT NOT NULL DEFAULT 'pending' CHECK(processing_state IN
                               ('pending', 'retryable', 'qa_held', 'processed',
                                'not_relevant', 'paused')),
    processing_attempts      INTEGER NOT NULL DEFAULT 0
                             CHECK(processing_attempts >= 0),
    processing_reason        TEXT CHECK(processing_reason IS NULL OR
                               processing_reason NOT GLOB '*[^a-z0-9_,]*'),
    qa_version               TEXT,
    glossary_version         TEXT,
    prompt_version           TEXT,
    first_seen_at_utc        TEXT NOT NULL,
    updated_at_utc           TEXT NOT NULL,
    CHECK(state != 'admitted' OR article_id IS NOT NULL),
    CHECK(state != 'admitted' OR document_heading_sha256 IS NOT NULL),
    CHECK(state != 'held' OR hold_reason IS NOT NULL)
)
""" % {
    "text": HEX % ("original_text_sha256", "original_text_sha256"),
    "head": HEX % ("document_heading_sha256", "document_heading_sha256"),
    "rel": HEX % ("release_decision_sha256", "release_decision_sha256"),
    "pol": HEX % ("policy_sha256", "policy_sha256"),
}

INDEX_DDL = ("CREATE INDEX IF NOT EXISTS idx_korea_corpus_processing "
             "ON korea_corpus_admissions(state, processing_state)")


def is_already_applied(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='korea_corpus_admissions'").fetchone() is not None and \
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' "
            "AND name='idx_korea_corpus_processing'").fetchone() is not None


def up(conn: sqlite3.Connection) -> None:
    # Empty on purpose: creating the ledger never makes an admission decision.
    conn.execute(DDL)
    conn.execute(INDEX_DDL)
