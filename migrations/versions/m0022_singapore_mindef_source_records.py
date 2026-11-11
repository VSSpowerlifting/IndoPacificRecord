"""Give Singapore MINDEF machine records their own official-link parent.

``daily_machine_records`` rows are public only while a family-scoped parent
exists (m0021): DAPA rows need ``korea_official_source_records`` and every other
family needs ``regional_official_source_links``. That second table is
CHECK-constrained to specific families and cannot hold Singapore, so this
migration adds the same link-only parent shape DAPA uses:

* ``singapore_mindef_source_records``: one row per MINDEF release identity,
  link scope only, bound to the private original by hashes (never its text);
* the m0021 BEFORE INSERT/UPDATE triggers are replaced so that
  ``sg_mindef_releases`` rows need an ``official_link_only`` parent in that
  table, and the regional predicate no longer applies to Singapore.

The table and triggers are created idempotently; no existing row is rewritten
(m0021 already removed the foreign key, so no rebuild is needed). The two
speech releases excluded by source review cannot be admitted: the table's CHECK
rejects them whatever the application does.

Databases that ran ``scripts/stage_mindef_public_projection.py`` also carry the
``mindef_public_no_machine_*`` boundary triggers, whose permitted-row predicate
was frozen as ``0`` when no parent table existed. They are re-issued here with
the parent-bound predicate (identical to
``core.mindef_public_boundary.permitted_machine_sql``) so the earlier blanket
hold does not silently defeat admission; a database without them is untouched.
"""
from migrations.versions import m0021_dapa_daily_machine_parent as prev

VERSION = "0022"
NAME = "singapore_mindef_source_records"
TABLE = "singapore_mindef_source_records"
FAMILY = "sg_mindef_releases"
TARGET = prev.TABLE
INSERT_TRIGGER = prev.INSERT_TRIGGER
UPDATE_TRIGGER = prev.UPDATE_TRIGGER
URL_PREFIX = "https://www.mindef.gov.sg/news-and-events/latest-releases/"
HELD_IDENTITIES = ("15aug26-speech", "16sep26-speech")

DDL = """
CREATE TABLE IF NOT EXISTS singapore_mindef_source_records (
 source_identity TEXT PRIMARY KEY CHECK(length(source_identity) BETWEEN 1 AND 63
  AND source_identity NOT GLOB '*[^a-z0-9-]*'
  AND source_identity NOT IN ('15aug26-speech','16sep26-speech')),
 canonical_official_url TEXT NOT NULL UNIQUE,
 publisher_posted_date TEXT NOT NULL CHECK(publisher_posted_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
 source_git_commit TEXT NOT NULL CHECK(length(source_git_commit)=40),
 metadata_version_sha256 TEXT NOT NULL CHECK(length(metadata_version_sha256)=64),
 content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
 capture_sha256 TEXT NOT NULL CHECK(length(capture_sha256)=64),
 title_sha256 TEXT NOT NULL CHECK(length(title_sha256)=64),
 first_seen_run TEXT NOT NULL CHECK(length(first_seen_run)>0),
 official_issuer TEXT NOT NULL CHECK(official_issuer='sg_mindef'),
 public_scope TEXT NOT NULL CHECK(public_scope IN ('held','official_link_only')),
 admitted_at_utc TEXT NOT NULL,
 CHECK(canonical_official_url = 'https://www.mindef.gov.sg/news-and-events/latest-releases/' || source_identity || '/')
)"""


def singapore_parent_missing(row):
    """True when a Singapore row lacks its sg_mindef, official-link-only parent."""
    return ("({row}.source_family='{fam}' AND NOT EXISTS (SELECT 1 FROM {table} s "
            "WHERE s.source_identity={row}.source_identity AND s.official_issuer='sg_mindef' "
            "AND s.public_scope='official_link_only'))").format(row=row, fam=FAMILY, table=TABLE)


def regional_parent_missing(row):
    """True when a family other than DAPA and Singapore lacks its regional link row."""
    return ("({row}.source_family NOT IN ('{dapa}','{fam}') AND NOT EXISTS (SELECT 1 FROM "
            "regional_official_source_links r WHERE r.source_family={row}.source_family "
            "AND r.source_identity={row}.source_identity))"
            ).format(row=row, dapa=prev.DAPA_FAMILY, fam=FAMILY)


_PARENT_MISSING = " OR ".join((prev.dapa_parent_missing("NEW"),
                               singapore_parent_missing("NEW"),
                               regional_parent_missing("NEW")))


def _trigger(name, event):
    return ("CREATE TRIGGER %s BEFORE %s ON %s WHEN %s BEGIN "
            "SELECT RAISE(ABORT,'daily_machine_record_parent_missing'); END"
            % (name, event, TARGET, _PARENT_MISSING))


TRIGGERS = ((INSERT_TRIGGER, _trigger(INSERT_TRIGGER, "INSERT")),
            (UPDATE_TRIGGER, _trigger(UPDATE_TRIGGER, "UPDATE")))

# Boundary triggers installed by ``core.mindef_public_boundary.project`` on staged databases.
BOUNDARY_TRIGGERS = (("mindef_public_no_machine_insert", "INSERT"),
                     ("mindef_public_no_machine_update", "UPDATE"))


def permitted_machine_predicate(row="NEW"):
    """Same predicate as ``core.mindef_public_boundary.permitted_machine_sql`` with the parent."""
    held = ",".join("'%s'" % i for i in HELD_IDENTITIES)
    return (
        "{r}.source_identity NOT IN ({held}) AND {r}.model_flagged=0 "
        "AND instr({r}.summary,'MINDEF')>0 AND EXISTS (SELECT 1 FROM {t} p "
        "WHERE p.source_identity={r}.source_identity AND p.official_issuer='sg_mindef' "
        "AND p.public_scope='official_link_only' "
        "AND p.metadata_version_sha256={r}.metadata_version_sha256 "
        "AND p.content_sha256={r}.content_sha256 AND p.capture_sha256={r}.capture_sha256)"
    ).format(r=row, held=held, t=TABLE)


def _boundary_trigger(name, event):
    return ("CREATE TRIGGER %s BEFORE %s ON %s WHEN NEW.source_family='%s' "
            "AND NEW.publication_state='released' AND NOT (%s) "
            "BEGIN SELECT RAISE(ABORT,'MINDEF machine publication held'); END"
            % (name, event, TARGET, FAMILY, permitted_machine_predicate()))


def _sql(conn, kind, name):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type=? AND name=?",
                       (kind, name)).fetchone()
    return row[0] if row else None


def is_already_applied(conn):
    if _sql(conn, "table", TABLE) is None:
        return False
    if not all(TABLE in (_sql(conn, "trigger", name) or "") for name, _ in TRIGGERS):
        return False
    # A staged database's boundary triggers must also be parent-bound (absent ones are fine).
    return all(sql is None or TABLE in sql
               for sql in (_sql(conn, "trigger", name) for name, _ in BOUNDARY_TRIGGERS))


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("Singapore MINDEF source records require the m0021 triggers")
    conn.execute(DDL)
    for name, sql in TRIGGERS:
        conn.execute("DROP TRIGGER IF EXISTS " + name)
        conn.execute(sql)
    for name, event in BOUNDARY_TRIGGERS:
        if _sql(conn, "trigger", name) is not None:
            conn.execute("DROP TRIGGER " + name)
            conn.execute(_boundary_trigger(name, event))
    if not is_already_applied(conn):
        raise ValueError("Singapore MINDEF parent migration did not apply")
