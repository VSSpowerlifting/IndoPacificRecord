"""0016 — provenance for Vietnam Desk articles in the shared corpus.

One row per `articles` row that core.vietnam_corpus_bridge admitted from an
authenticated private Vietnam capture. It keeps what the shared `articles`
columns cannot: the source identity and preserved version hash (the dedup and
material-change key), the private commit that held the capture, the
source-use policy and decision applied with the attribution and licence
terms it imposes, the QA rubric and the prompt and
terminology versions. Vietnam event types live here, not in the China
category taxonomy.

Schema only: creates an empty table, admits no record, grants no right and
adds no desk or source row. No original text is stored here.

A row goes with its article (ON DELETE CASCADE, as China retirement staging
requires of every `articles` dependent); the private bridge ledger remains the
durable record of what was admitted.
"""

VERSION = "0016"
NAME = "vietnam_article_provenance"
TABLE = "vietnam_article_provenance"

FAMILIES = ("vn_mps_foreign_affairs_vi", "vn_moit_energy_vi",
            "vn_moit_foundational_industry_vi")
EVENT_TYPES = ("meeting", "announcement", "agreement", "approval", "contract",
               "financing", "commencement", "completion", "policy_document",
               "other")

_HEX64 = "GLOB '" + "[0-9a-f]" * 64 + "'"
_HEX40 = "GLOB '" + "[0-9a-f]" * 40 + "'"


def _in(values):
    return "(" + ", ".join("'%s'" % v for v in values) + ")"


DDL = """
CREATE TABLE %(t)s (
    article_id                 INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    source_family              TEXT NOT NULL CHECK (source_family IN %(families)s),
    source_identity            TEXT NOT NULL UNIQUE,
    canonical_official_url     TEXT NOT NULL,
    publisher_posted_date      TEXT NOT NULL
        CHECK (publisher_posted_date GLOB '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]'),
    content_sha256             TEXT NOT NULL CHECK (content_sha256 %(hex64)s),
    capture_sha256             TEXT NOT NULL CHECK (capture_sha256 %(hex64)s),
    source_git_commit          TEXT NOT NULL CHECK (source_git_commit %(hex40)s),
    collector_commit           TEXT NOT NULL,
    rights_policy_version      TEXT NOT NULL,
    rights_decision_sha256     TEXT NOT NULL CHECK (rights_decision_sha256 %(hex64)s),
    attribution_text           TEXT NOT NULL CHECK (length(trim(attribution_text)) >= 3),
    license_terms              TEXT,
    permissions_json           TEXT NOT NULL CHECK (json_valid(permissions_json)),
    qa_rubric_version          TEXT NOT NULL,
    qa_json                    TEXT NOT NULL CHECK (json_valid(qa_json)),
    event_type                 TEXT NOT NULL CHECK (event_type IN %(events)s),
    terminology_version        TEXT NOT NULL,
    translation_prompt_version TEXT,
    original_withheld          INTEGER NOT NULL CHECK (original_withheld IN (0, 1)),
    translation_published      INTEGER NOT NULL CHECK (translation_published IN (0, 1)),
    published_by_run           TEXT NOT NULL,
    processed_utc              TEXT NOT NULL
)
""" % {"t": TABLE, "families": _in(FAMILIES), "events": _in(EVENT_TYPES),
       "hex64": _HEX64, "hex40": _HEX40}

COLUMNS = frozenset((
    "article_id", "source_family", "source_identity", "canonical_official_url",
    "publisher_posted_date", "content_sha256", "capture_sha256",
    "source_git_commit", "collector_commit", "rights_policy_version",
    "rights_decision_sha256", "attribution_text", "license_terms", "permissions_json", "qa_rubric_version", "qa_json",
    "event_type", "terminology_version", "translation_prompt_version",
    "original_withheld", "translation_published", "published_by_run",
    "processed_utc",
))


def is_already_applied(conn):
    cols = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    return cols == COLUMNS


def up(conn):
    if is_already_applied(conn):
        return
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
        raise ValueError("vietnam_article_provenance exists with unexpected columns")
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
                        ).fetchone():
        raise ValueError("articles table must precede Vietnam provenance")
    conn.execute(DDL)
    if not is_already_applied(conn):
        raise ValueError("Vietnam provenance table incomplete")
