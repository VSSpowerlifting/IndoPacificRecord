"""Extend the shared metadata index to Japan MOD news, without admitting rows.

The legacy publisher_posted_date column holds RSS pubDate for this family;
every public projection must identify that date type explicitly.
"""
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0018_government_document_metadata as prev
from migrations.versions.m0014_ph_nsc_regional_official_links import _once

VERSION = "0020"
NAME = "japan_mod_official_links"
TEMP = "regional_official_source_links_v20"
FAMILY = "jp_mod_news_ja"


def _ddl():
    sql = _once(prev._ddl(), "CREATE TABLE " + prev.TEMP, "CREATE TABLE " + TEMP)
    for old, new in (
        ("'vn_vpcp_official_documents_vi')),", "'vn_vpcp_official_documents_vi', 'jp_mod_news_ja')),"),
        ("(source_family='ph_afp_articles' AND desk='philippines') OR",
         "(source_family='jp_mod_news_ja' AND desk='japan') OR\n        (source_family='ph_afp_articles' AND desk='philippines') OR"),
        ("AND canonical_official_url GLOB 'https://www.kemhan.go.id/*')",
         "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*') OR "
         "(source_family='jp_mod_news_ja' AND canonical_official_url GLOB 'https://www.mod.go.jp/j/press/news/20[0-9][0-9]/[01][0-9]/[0-3][0-9]*.pdf')"),
        ("AND official_issuer IS NULL AND official_publisher='id_kemhan')",
         "AND official_issuer IS NULL AND official_publisher='id_kemhan') OR "
         "(source_family='jp_mod_news_ja' AND official_issuer IS NOT NULL "
         "AND official_issuer='jp_mod' AND official_publisher='jp_mod')"),
    ):
        sql = _once(sql, old, new)
    return sql


DDL = _ddl()


def is_already_applied(conn):
    if base._columns(conn) != base.COLUMNS:
        return False
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (base.TABLE,)).fetchone()[0]
    return "'jp_mod_news_ja'" in sql and base._has_index(conn)


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("Japan extension requires the existing regional index")
    columns = ",".join(sorted(base.COLUMNS))
    before = conn.execute("SELECT * FROM " + base.TABLE + " ORDER BY source_family,source_identity").fetchall()
    conn.execute(DDL)
    conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (TEMP, columns, columns, base.TABLE))
    conn.execute("DROP TABLE " + base.TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, base.TABLE))
    conn.execute(base.INDEX_DDL)
    after = conn.execute("SELECT * FROM " + base.TABLE + " ORDER BY source_family,source_identity").fetchall()
    if before != after or not is_already_applied(conn):
        raise ValueError("Japan index migration did not preserve existing links")
