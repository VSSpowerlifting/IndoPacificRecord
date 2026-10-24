"""Permit approved VPCP projections in existing Vietnam article provenance only."""
from migrations.versions import m0017_vietnam_article_provenance as previous
VERSION='0019'
NAME='vpcp_article_provenance'
FAMILY='vn_vpcp_official_documents_vi'


def is_already_applied(conn):
    row=conn.execute("SELECT sql FROM sqlite_master WHERE name=?",(previous.TABLE,)).fetchone()
    return previous.is_already_applied(conn) and bool(row and "'"+FAMILY+"'" in row[0])


def up(conn):
    if is_already_applied(conn):return
    if not previous.is_already_applied(conn):raise ValueError('Vietnam provenance 0017 required')
    ddl=previous.DDL.replace('CREATE TABLE '+previous.TABLE,'CREATE TABLE vietnam_provenance_v19',1)
    ddl=ddl.replace(previous._in(previous.FAMILIES),previous._in(previous.FAMILIES+(FAMILY,)),1)
    conn.execute(ddl)
    columns=','.join(sorted(previous.COLUMNS))
    conn.execute('INSERT INTO vietnam_provenance_v19 ('+columns+') SELECT '+columns+' FROM '+previous.TABLE)
    conn.execute('DROP TABLE '+previous.TABLE)
    conn.execute('ALTER TABLE vietnam_provenance_v19 RENAME TO '+previous.TABLE)
