"""Let a DAPA machine record reference its Korea official-link parent.

m0015 declared one foreign key, to ``regional_official_source_links``. DAPA
official links live in ``korea_official_source_records`` instead, so with
``PRAGMA foreign_keys=ON`` (the daily runner) a DAPA machine row could never be
written. SQLite cannot give one column pair two alternative parents, so the
table is rebuilt with identical columns, order, keys and CHECKs, minus the
foreign key, and family-scoped BEFORE INSERT/UPDATE triggers replace it:

* ``kr_policy_dapa_releases`` rows need a ``korea_official_source_records``
  parent with the same identity, ``official_issuer='kr_dapa'`` and
  ``public_scope='official_link_only'``;
* every other family still needs its exact (family, identity) row in
  ``regional_official_source_links``, as before.

Unlike the old foreign key, the triggers apply whatever the
``foreign_keys`` pragma says. Deletion of a parent is not guarded here: a
trigger on a parent table would vanish silently in any later rebuild of that
table. Instead every reader (``core.daily_machine_records.load``, the
reconcile check and the weekly audit) re-reads the parent and fails closed
when it is missing, held or at another version.

Every other schema object on the table (the MINDEF machine-publication
triggers today) is captured from ``sqlite_master`` and replayed unchanged.
"""
import hashlib

from migrations.versions import m0015_daily_machine_records as prev
from migrations.versions.m0014_ph_nsc_regional_official_links import _once

VERSION = "0021"
NAME = "dapa_daily_machine_parent"
TABLE = "daily_machine_records"
TEMP = "daily_machine_records_v21"
DAPA_FAMILY = "kr_policy_dapa_releases"
INSERT_TRIGGER = "daily_machine_parent_insert"
UPDATE_TRIGGER = "daily_machine_parent_update"

_FK = (",\n FOREIGN KEY(source_family, source_identity)\n"
       " REFERENCES regional_official_source_links(source_family, source_identity)\n)")
DDL = _once(_once(prev.DDL, _FK, "\n)"), "CREATE TABLE " + TABLE, "CREATE TABLE " + TEMP)

_PARENT_MISSING = (
    "(NEW.source_family='{dapa}' AND NOT EXISTS (SELECT 1 FROM korea_official_source_records k "
    "WHERE k.source_identity=NEW.source_identity AND k.official_issuer='kr_dapa' "
    "AND k.public_scope='official_link_only')) OR "
    "(NEW.source_family<>'{dapa}' AND NOT EXISTS (SELECT 1 FROM regional_official_source_links r "
    "WHERE r.source_family=NEW.source_family AND r.source_identity=NEW.source_identity))"
).format(dapa=DAPA_FAMILY)


def _trigger(name, event):
    return ("CREATE TRIGGER %s BEFORE %s ON %s WHEN %s BEGIN "
            "SELECT RAISE(ABORT,'daily_machine_record_parent_missing'); END"
            % (name, event, TABLE, _PARENT_MISSING))


TRIGGERS = (_trigger(INSERT_TRIGGER, "INSERT"), _trigger(UPDATE_TRIGGER, "UPDATE"))


def _table_sql(conn):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                       (TABLE,)).fetchone()
    return row[0] if row else None


def _trigger_names(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (TABLE,))}


def is_already_applied(conn):
    sql = _table_sql(conn)
    return (sql is not None and "FOREIGN KEY" not in sql.upper()
            and {INSERT_TRIGGER, UPDATE_TRIGGER} <= _trigger_names(conn))


def _dependents(conn):
    """Indexes, triggers and views tied to the table, excluding autoindexes."""
    return conn.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND type IN "
        "('index','trigger','view') AND (tbl_name=? OR (type='view' AND sql LIKE ?)) "
        "ORDER BY type,name",
        (TABLE, "%" + TABLE + "%")).fetchall()


def _digest(conn):
    h = hashlib.sha256()
    for row in conn.execute("SELECT * FROM %s ORDER BY source_family,source_identity" % TABLE):
        h.update(repr(tuple(row)).encode())
    return h.hexdigest()


def up(conn):
    if is_already_applied(conn):
        return
    if not prev.is_already_applied(conn):
        raise ValueError("DAPA machine parent requires the m0015 table")
    columns = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)]
    dependents = _dependents(conn)
    if any(kind == "view" for kind, _, _ in dependents):
        raise ValueError("daily_machine_records view dependency not supported by m0021")
    before = _digest(conn)
    conn.execute(DDL)
    if [r[1] for r in conn.execute("PRAGMA table_info(%s)" % TEMP)] != columns:
        raise ValueError("daily_machine_records columns changed unexpectedly")
    cols = ",".join(columns)
    conn.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (TEMP, cols, cols, TABLE))
    conn.execute("DROP TABLE " + TABLE)
    conn.execute("ALTER TABLE %s RENAME TO %s" % (TEMP, TABLE))
    for _, _, sql in dependents:
        conn.execute(sql)
    for sql in TRIGGERS:
        conn.execute(sql)
    if _digest(conn) != before or not is_already_applied(conn):
        raise ValueError("DAPA machine parent migration did not preserve existing rows")
