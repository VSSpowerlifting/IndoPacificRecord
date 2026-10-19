"""0013 — extend the existing regional link index to three Vietnam families.

Schema capability only: admits no records, changes no source-use holds.
Preserves every existing AFP/Kemhan row, constraint and index in the runner's
transaction. No original text or second publication database is introduced.
"""
from migrations.versions import m0010_regional_official_source_links as old

VERSION = "0013"
NAME = "vietnam_regional_official_links"
TEMP = "regional_official_source_links_v13"
FAMILIES = ("vn_mps_foreign_affairs_vi", "vn_moit_energy_vi",
            "vn_moit_foundational_industry_vi")

DDL = old.DDL.replace("CREATE TABLE IF NOT EXISTS " + old.TABLE,
                      "CREATE TABLE " + TEMP).replace(
    "'ph_afp_articles', 'id_kemhan_news'",
    "'ph_afp_articles', 'id_kemhan_news', " + ", ".join(repr(s) for s in FAMILIES)
).replace(
    "(source_family='id_kemhan_news' AND desk='indonesia')",
    "(source_family='id_kemhan_news' AND desk='indonesia') OR "
    "(source_family IN (%s) AND desk='vietnam')" % ", ".join(repr(s) for s in FAMILIES)
).replace(
    "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*')",
    "AND canonical_official_url GLOB 'https://www.kemhan.go.id/*') OR "
    "(source_family='vn_mps_foreign_affairs_vi' AND "
    "canonical_official_url GLOB 'https://bocongan.gov.vn/bai-viet/*') OR "
    "(source_family IN ('vn_moit_energy_vi','vn_moit_foundational_industry_vi') "
    "AND canonical_official_url GLOB 'https://moit.gov.vn/tin-tuc/*')"
).replace(
    "AND official_issuer IS NULL AND official_publisher='id_kemhan')",
    "AND official_issuer IS NULL AND official_publisher='id_kemhan') OR "
    "(source_family='vn_mps_foreign_affairs_vi' AND official_issuer IS NOT NULL "
    "AND official_issuer='vn_mps' AND official_publisher='vn_mps') OR "
    "(source_family IN ('vn_moit_energy_vi','vn_moit_foundational_industry_vi') "
    "AND official_issuer IS NOT NULL AND official_issuer='vn_moit' "
    "AND official_publisher='vn_moit')"
)


def is_already_applied(conn):
    if old._columns(conn) != old.COLUMNS:
        return False
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (old.TABLE,)).fetchone()[0]
    return all("'" + f + "'" in sql for f in FAMILIES) and old._has_index(conn)


def up(conn):
    if is_already_applied(conn):
        return
    if old._columns(conn) != old.COLUMNS:
        raise ValueError("regional source index must be migrated before Vietnam extension")
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TEMP,)).fetchone():
        raise ValueError("Vietnam migration temporary table already exists")
    columns = ",".join(sorted(old.COLUMNS))
    conn.execute(DDL)
    conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" %
                 (TEMP, columns, columns, old.TABLE))
    conn.execute("DROP TABLE " + old.TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, old.TABLE))
    conn.execute(old.INDEX_DDL)
    if not is_already_applied(conn):
        raise ValueError("Vietnam regional index extension incomplete")
