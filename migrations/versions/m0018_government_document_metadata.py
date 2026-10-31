"""Extend the shared official-link index; retain approved bibliographic versions."""
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0014_ph_nsc_regional_official_links as prev

VERSION = "0018"
NAME = "government_document_metadata"
TEMP = "regional_official_source_links_v18"
FAMILY = "vn_vpcp_official_documents_vi"


def _ddl():
    sql = prev._once(prev.DDL, "CREATE TABLE " + prev.TEMP, "CREATE TABLE " + TEMP)
    sql = prev._once(sql, "'ph_nsc_official_statements')),", "'ph_nsc_official_statements', '%s'))," % FAMILY)
    sql = prev._once(sql, "(source_family='ph_afp_articles' AND desk='philippines') OR",
        "(source_family='%s' AND desk='vietnam') OR (source_family='ph_afp_articles' AND desk='philippines') OR" % FAMILY)
    sql = prev._once(sql, "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*')",
        "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*') OR "
        "(source_family='%s' AND canonical_official_url GLOB 'https://vanban.chinhphu.vn/?pageid=27160&docid=[0-9]*')" % FAMILY)
    return prev._once(sql, "AND official_issuer IS NULL AND official_publisher='id_kemhan')",
        "AND official_issuer IS NULL AND official_publisher='id_kemhan') OR "
        "(source_family='%s' AND official_issuer='vn_vpcp' AND official_publisher='vn_government_portal')" % FAMILY)


def is_already_applied(conn):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (base.TABLE,)).fetchone()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return bool(row and "'" + FAMILY + "'" in row[0]
        and {"official_document_versions", "official_document_collection_runs"} <= tables)


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("regional links 0014 required")
    columns = ",".join(sorted(base.COLUMNS))
    conn.execute(_ddl())
    conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (TEMP, columns, columns, base.TABLE))
    conn.execute("DROP TABLE " + base.TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, base.TABLE))
    conn.execute(base.INDEX_DDL)
    conn.execute("""CREATE TABLE official_document_versions (
        source_family TEXT NOT NULL CHECK(source_family='vn_vpcp_official_documents_vi'),
        source_identity TEXT NOT NULL,
        metadata_sha256 TEXT NOT NULL CHECK(length(metadata_sha256)=64),
        metadata_json TEXT NOT NULL,
        capture_sha256 TEXT NOT NULL CHECK(length(capture_sha256)=64),
        first_observed_utc TEXT NOT NULL,
        source_run TEXT NOT NULL,
        collector_commit TEXT NOT NULL CHECK(length(collector_commit)=40),
        PRIMARY KEY(source_family,source_identity,metadata_sha256)
    )""")
    conn.execute("""CREATE TABLE official_document_collection_runs (
        source_family TEXT NOT NULL CHECK(source_family='vn_vpcp_official_documents_vi'),
        source_run TEXT NOT NULL,
        observed_utc TEXT NOT NULL,
        collector_commit TEXT NOT NULL,
        status TEXT NOT NULL,
        report_json TEXT NOT NULL,
        PRIMARY KEY(source_family,source_run)
    )""")
