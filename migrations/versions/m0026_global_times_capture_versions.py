"""Admit Global Times military captures to the shared document-version store.

`official_document_versions` (0018) was created for one family only. Global
Times article captures reuse the same rows and columns: one version row per
distinct capture, bound by `capture_sha256` to the exact wire bytes. Nothing
else changes; existing rows are copied verbatim.
"""

VERSION = "0026"
NAME = "global_times_capture_versions"
TABLE = "official_document_versions"
TEMP = TABLE + "_v26"
FAMILY = "global_times_mil"
OLD_CHECK = "CHECK(source_family='vn_vpcp_official_documents_vi')"
NEW_CHECK = ("CHECK(source_family IN ('vn_vpcp_official_documents_vi','%s'))"
             % FAMILY)


def _sql(conn):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                       (TABLE,)).fetchone()
    return row[0] if row else None


def is_already_applied(conn):
    sql = _sql(conn)
    return bool(sql and "'" + FAMILY + "'" in sql)


def up(conn):
    if is_already_applied(conn):
        return
    sql = _sql(conn)
    if sql is None:
        raise ValueError("official_document_versions (0018) required")
    if sql.count(OLD_CHECK) != 1 or sql.count("CREATE TABLE " + TABLE) != 1:
        raise ValueError("official_document_versions has an unexpected definition")
    conn.execute(sql.replace(OLD_CHECK, NEW_CHECK)
                 .replace("CREATE TABLE " + TABLE, "CREATE TABLE " + TEMP))
    conn.execute("INSERT INTO %s SELECT * FROM %s" % (TEMP, TABLE))
    conn.execute("DROP TABLE " + TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, TABLE))
