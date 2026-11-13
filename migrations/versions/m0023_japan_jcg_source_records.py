"""Give Japan Coast Guard English release machine records an official-link parent.

``daily_machine_records`` rows are public only while a family-scoped parent
exists (m0021, m0022). ``regional_official_source_links`` is CHECK-constrained
to specific families and cannot hold JCG, so this migration adds the same
link-only parent shape Singapore uses:

* ``japan_jcg_source_records``: one row per JCG English HTML release identity
  (``jcg-en:<N>``), link scope only, bound to the private original by hashes
  (never its text). The table's CHECK pins the URL to the standing first-party
  family ``https://www.kaiho.mlit.go.jp/e/topics_archive/article<N>.html``, so
  a PDF, a media URL or another page on the host cannot be admitted whatever
  the application does;
* the parent INSERT/UPDATE triggers are re-issued so that ``jp_jcg_press_en``
  rows need an ``official_link_only`` parent in that table, and the regional
  predicate no longer applies to JCG. The DAPA and Singapore predicates are
  carried over unchanged.

The table and triggers are created idempotently; no existing row is rewritten.
"""
from migrations.versions import m0021_dapa_daily_machine_parent as m21
from migrations.versions import m0022_singapore_mindef_source_records as prev

VERSION = "0023"
NAME = "japan_jcg_source_records"
TABLE = "japan_jcg_source_records"
FAMILY = "jp_jcg_press_en"
ISSUER = "jp_coast_guard"
TARGET = m21.TABLE
INSERT_TRIGGER = m21.INSERT_TRIGGER
UPDATE_TRIGGER = m21.UPDATE_TRIGGER

DDL = """
CREATE TABLE IF NOT EXISTS japan_jcg_source_records (
 source_identity TEXT PRIMARY KEY CHECK(length(source_identity) BETWEEN 8 AND 16
  AND substr(source_identity,1,7)='jcg-en:'
  AND substr(source_identity,8,1) GLOB '[1-9]'
  AND substr(source_identity,8) NOT GLOB '*[^0-9]*'),
 canonical_official_url TEXT NOT NULL UNIQUE,
 publisher_posted_date TEXT NOT NULL CHECK(publisher_posted_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND publisher_posted_date >= '2026-09-01'),
 source_git_commit TEXT NOT NULL CHECK(length(source_git_commit)=40),
 metadata_version_sha256 TEXT NOT NULL CHECK(length(metadata_version_sha256)=64),
 content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
 capture_sha256 TEXT NOT NULL CHECK(length(capture_sha256)=64),
 title_sha256 TEXT NOT NULL CHECK(length(title_sha256)=64),
 first_seen_run TEXT NOT NULL CHECK(length(first_seen_run)>0),
 official_issuer TEXT NOT NULL CHECK(official_issuer='jp_coast_guard'),
 public_scope TEXT NOT NULL CHECK(public_scope IN ('held','official_link_only')),
 admitted_at_utc TEXT NOT NULL,
 CHECK(canonical_official_url = 'https://www.kaiho.mlit.go.jp/e/topics_archive/article' || substr(source_identity,8) || '.html')
)"""


def jcg_parent_missing(row):
    """True when a JCG row lacks its jp_coast_guard, official-link-only parent."""
    return ("({row}.source_family='{fam}' AND NOT EXISTS (SELECT 1 FROM {table} j "
            "WHERE j.source_identity={row}.source_identity AND j.official_issuer='{issuer}' "
            "AND j.public_scope='official_link_only'))"
            ).format(row=row, fam=FAMILY, table=TABLE, issuer=ISSUER)


def regional_parent_missing(row):
    """True when a family other than DAPA, Singapore and JCG lacks its regional link row."""
    return ("({row}.source_family NOT IN ('{dapa}','{sg}','{fam}') AND NOT EXISTS (SELECT 1 FROM "
            "regional_official_source_links r WHERE r.source_family={row}.source_family "
            "AND r.source_identity={row}.source_identity))"
            ).format(row=row, dapa=m21.DAPA_FAMILY, sg=prev.FAMILY, fam=FAMILY)


_PARENT_MISSING = " OR ".join((m21.dapa_parent_missing("NEW"),
                               prev.singapore_parent_missing("NEW"),
                               jcg_parent_missing("NEW"),
                               regional_parent_missing("NEW")))


def _trigger(name, event):
    return ("CREATE TRIGGER %s BEFORE %s ON %s WHEN %s BEGIN "
            "SELECT RAISE(ABORT,'daily_machine_record_parent_missing'); END"
            % (name, event, TARGET, _PARENT_MISSING))


TRIGGERS = ((INSERT_TRIGGER, _trigger(INSERT_TRIGGER, "INSERT")),
            (UPDATE_TRIGGER, _trigger(UPDATE_TRIGGER, "UPDATE")))


def _sql(conn, kind, name):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?",
                       (kind, name)).fetchone()
    return row[0] if row else None


def is_already_applied(conn):
    if _sql(conn, "table", TABLE) is None:
        return False
    return all(TABLE in (_sql(conn, "trigger", name) or "") for name, _ in TRIGGERS)


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("Japan JCG source records require the m0022 triggers")
    conn.execute(DDL)
    for name, sql in TRIGGERS:
        conn.execute("DROP TRIGGER IF EXISTS " + name)
        conn.execute(sql)
    if not (is_already_applied(conn) and prev.is_already_applied(conn)):
        raise ValueError("Japan JCG parent migration did not apply")
