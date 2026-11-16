"""Give USCC press-release machine records a version-bound official-link parent.

``daily_machine_records`` rows are public only while a family-scoped parent
exists (m0021-m0023). The existing USCC metadata lane
(``uscc_official_source_records``, created by ``core.uscc_official_metadata``)
holds listing URLs and dates only, with no content, capture, title or version
hash, so it cannot bind a machine record to the exact private original it was
written from. This migration adds the same link-only parent shape Singapore and
Japan Coast Guard use:

* ``uscc_press_source_records``: one row per USCC press-release identity
  (``uscc-press:<slug>``, the metadata lane's identity), link scope only, bound to
  the private capture, its stored body text, its title and the qualified
  narrative input by hashes (never their text). The CHECK pins the URL to the
  Commission's canonical press-release path for that slug, the issuer to the
  metadata lane's issuer, and refuses the three identities the standing-family
  assessment holds individually, whatever the application does. Application
  admission (``core.uscc_press_links.admit_links``) additionally requires the
  same identity, URL and listing date in ``uscc_official_source_records``;
* the parent INSERT/UPDATE triggers are re-issued so that ``us_uscc_press_en``
  rows need an ``official_link_only`` parent in that table, and the regional
  predicate no longer applies to USCC. The DAPA, Singapore and Japan Coast
  Guard predicates are carried over unchanged.

The table and triggers are created idempotently; no existing row is rewritten.
The metadata lane's table is not altered.
"""
from migrations.versions import m0021_dapa_daily_machine_parent as m21
from migrations.versions import m0022_singapore_mindef_source_records as m22
from migrations.versions import m0023_japan_jcg_source_records as prev

VERSION = "0024"
NAME = "uscc_press_source_records"
TABLE = "uscc_press_source_records"
FAMILY = "us_uscc_press_en"
ISSUER = "us_china_economic_security_review_commission"
TARGET = m21.TABLE
INSERT_TRIGGER = m21.INSERT_TRIGGER
UPDATE_TRIGGER = m21.UPDATE_TRIGGER
# core.uscc_offline_input.HELD_IDENTITIES, mirrored so this migration stays free
# of bs4 (asserted equal in tests). These never become parents.
HELD_IDENTITIES = (
    "uscc-press:press-release-plain-english-guide-ai-tech-stack",
    "uscc-press:press-release-dalai-lamas-succession-geopolitical-implications-and-policy",
    "uscc-press:press-release-new-report-chinas-gray-zone-threats-trans-pacific-undersea-cables",
)

DDL = """
CREATE TABLE IF NOT EXISTS uscc_press_source_records (
 source_identity TEXT PRIMARY KEY CHECK(length(source_identity) BETWEEN 13 AND 140
  AND substr(source_identity,1,11)='uscc-press:'
  AND substr(source_identity,12) NOT GLOB '*[^a-z0-9-]*'
  AND substr(source_identity,12,1) GLOB '[a-z0-9]'
  AND substr(source_identity,-1,1) GLOB '[a-z0-9]'
  AND instr(source_identity,'--')=0
  AND source_identity NOT IN (%s)),
 canonical_official_url TEXT NOT NULL UNIQUE,
 publisher_posted_date TEXT NOT NULL CHECK(publisher_posted_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
  AND publisher_posted_date >= '2025-01-01'),
 source_git_commit TEXT NOT NULL CHECK(length(source_git_commit)=40),
 metadata_version_sha256 TEXT NOT NULL CHECK(length(metadata_version_sha256)=64),
 content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
 capture_sha256 TEXT NOT NULL CHECK(length(capture_sha256)=64),
 title_sha256 TEXT NOT NULL CHECK(length(title_sha256)=64),
 potential_input_sha256 TEXT NOT NULL CHECK(length(potential_input_sha256)=64),
 first_seen_run TEXT NOT NULL CHECK(length(first_seen_run)>0),
 official_issuer TEXT NOT NULL CHECK(official_issuer='%s'),
 public_scope TEXT NOT NULL CHECK(public_scope IN ('held','official_link_only')),
 admitted_at_utc TEXT NOT NULL,
 CHECK(canonical_official_url = 'https://www.uscc.gov/press-releases/' || substr(source_identity,12))
)""" % (",".join("'%s'" % i for i in HELD_IDENTITIES), ISSUER)


def uscc_parent_missing(row):
    """True when a USCC row lacks its official-link-only Commission parent."""
    return ("({row}.source_family='{fam}' AND NOT EXISTS (SELECT 1 FROM {table} u "
            "WHERE u.source_identity={row}.source_identity AND u.official_issuer='{issuer}' "
            "AND u.public_scope='official_link_only'))"
            ).format(row=row, fam=FAMILY, table=TABLE, issuer=ISSUER)


def regional_parent_missing(row):
    """True when a family other than DAPA, Singapore, JCG and USCC lacks its regional link row."""
    return ("({row}.source_family NOT IN ('{dapa}','{sg}','{jcg}','{fam}') AND NOT EXISTS "
            "(SELECT 1 FROM regional_official_source_links r WHERE r.source_family={row}.source_family "
            "AND r.source_identity={row}.source_identity))"
            ).format(row=row, dapa=m21.DAPA_FAMILY, sg=m22.FAMILY, jcg=prev.FAMILY, fam=FAMILY)


_PARENT_MISSING = " OR ".join((m21.dapa_parent_missing("NEW"),
                               m22.singapore_parent_missing("NEW"),
                               prev.jcg_parent_missing("NEW"),
                               uscc_parent_missing("NEW"),
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
        raise ValueError("USCC press source records require the m0023 triggers")
    conn.execute(DDL)
    for name, sql in TRIGGERS:
        conn.execute("DROP TRIGGER IF EXISTS " + name)
        conn.execute(sql)
    if not (is_already_applied(conn) and prev.is_already_applied(conn)):
        raise ValueError("USCC press parent migration did not apply")
