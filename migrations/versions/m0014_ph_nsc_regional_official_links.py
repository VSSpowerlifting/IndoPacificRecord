"""0014 — extend the existing regional link index to Philippine NSC statements.

Schema capability only: admits no records, grants no publication right and
changes no source-use hold. NSC rows join the Philippines desk beside AFP under
the Kemhan model (no separately stated issuer; the publisher is the NSC site).
Preserves every existing AFP/Kemhan/Vietnam row, constraint and index in the
runner's transaction. No original text or second publication database.
"""
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0013_vietnam_regional_official_links as prev

VERSION = "0014"
NAME = "ph_nsc_regional_official_links"
TEMP = "regional_official_source_links_v14"
FAMILY = "ph_nsc_official_statements"


def _once(sql, old, new):
    # Each anchor must occur exactly once, or the extension would silently
    # widen (or fail to narrow) a constraint it was not meant to touch.
    if sql.count(old) != 1:
        raise ValueError("NSC index extension anchor is not unique: %r" % old)
    return sql.replace(old, new)


def _ddl():
    sql = _once(prev.DDL, "CREATE TABLE " + prev.TEMP, "CREATE TABLE " + TEMP)
    sql = _once(sql, "'vn_moit_foundational_industry_vi')),\n",
                "'vn_moit_foundational_industry_vi', '%s')),\n" % FAMILY)
    sql = _once(sql, "(source_family='ph_afp_articles' AND desk='philippines') OR",
                "(source_family='ph_afp_articles' AND desk='philippines') OR\n"
                "        (source_family='%s' AND desk='philippines') OR" % FAMILY)
    sql = _once(sql, "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*')",
                "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*') OR "
                "(source_family='%s' AND canonical_official_url GLOB "
                "'https://nsc.gov.ph/20[0-9][0-9]/[01][0-9]/[0-3][0-9]/?*/')" % FAMILY)
    sql = _once(sql, "AND official_issuer IS NULL AND official_publisher='id_kemhan')",
                "AND official_issuer IS NULL AND official_publisher='id_kemhan') OR "
                "(source_family='%s' AND official_issuer IS NULL "
                "AND official_publisher='ph_nsc')" % FAMILY)
    return sql


DDL = _ddl()


def is_already_applied(conn):
    if base._columns(conn) != base.COLUMNS:
        return False
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?",
                       (base.TABLE,)).fetchone()[0]
    return "'" + FAMILY + "'" in sql and base._has_index(conn)


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("Vietnam index extension 0013 must precede NSC extension")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TEMP,)).fetchone():
        raise ValueError("NSC migration temporary table already exists")
    columns = ",".join(sorted(base.COLUMNS))
    before = conn.execute("SELECT count(*) FROM " + base.TABLE).fetchone()[0]
    conn.execute(DDL)
    conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" %
                 (TEMP, columns, columns, base.TABLE))
    conn.execute("DROP TABLE " + base.TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, base.TABLE))
    conn.execute(base.INDEX_DDL)
    after = conn.execute("SELECT count(*) FROM " + base.TABLE).fetchone()[0]
    if after != before or not is_already_applied(conn):
        raise ValueError("NSC regional index extension incomplete")
