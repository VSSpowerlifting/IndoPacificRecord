"""Permitted optional originals on the shared Daily Record.

Each reviewed release pins the authenticated capture, accepted parent version,
and exact public title and text. A new capture is never implicitly authorized.
See DECISION_LOG.md (standing publisher permissions, PR #1033).
"""

import hashlib
import json
import re
from pathlib import Path

from migrations.versions.m0025_daily_record_originals import FIELDS, is_already_applied

POLICY_PATH = Path(__file__).resolve().parents[1] / "config/daily_public_originals.json"
AFP = "ph_afp_articles"
VERSION_FIELDS = ("metadata_version_sha256", "content_sha256", "capture_sha256")
MEDIA_CREDIT = re.compile(r"\n\nPhotos(?: and Videos)? by[^\n]*\Z", re.IGNORECASE)


def load_pins():
    from processing.daily_intake import load_policy
    pins = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy = load_policy()["sources"][AFP]
    if not policy["public_machine_explanation"] or not policy["unattended_release"]:
        return {}
    return {AFP: {identity: pin for identity, pin in pins.get(AFP, {}).items()
                  if identity not in policy["excluded_source_identities"]}}


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def permitted(component, record, pins):
    if type(component) is not dict or component.keys() != set(FIELDS):
        return False
    if not all(type(component[k]) is str and component[k].strip() for k in FIELDS):
        return False
    family, identity = (component[k] for k in FIELDS[:2])
    pin = pins.get(family, {}).get(identity)
    if family != AFP or not pin or any(component[k] != record[k] for k in FIELDS[:3]):
        return False
    return (all(record[k] == pin[k] for k in VERSION_FIELDS)
            and text_hash(component["title_original"]) == pin["title_sha256"]
            and text_hash(component["text_original"]) == pin["public_text_sha256"])


def project(verified_records, state, family, pins):
    """Project only verified source material backed by an accepted explanation."""
    if family != AFP or not pins.get(family):
        return []
    originals = []
    for record in verified_records:
        identity = record["source_identity"]
        entry = state.get(family + ":" + identity, {})
        if (identity not in pins[family] or entry.get("status") != "complete"
                or record["official_issuer"] != "ph_afp"
                or record["official_publisher"] != "ph_afp"
                or record["official_republisher"]):
            continue
        output = entry["output"]
        if any(record[k] != output[k] for k in VERSION_FIELDS):
            continue
        body = record["body"]
        if text_hash(body) != record["content_sha256"]:
            continue
        component = dict(zip(FIELDS, (family, identity, record["capture_sha256"],
                                      record["title"], MEDIA_CREDIT.sub("", body))))
        if permitted(component, output, pins):
            originals.append(component)
    return originals


def stored_component(conn, family, identity):
    row = conn.execute(
        "SELECT " + ", ".join(FIELDS) + " FROM daily_record_originals "
        "WHERE source_family=? AND source_identity=?", (family, identity)
    ).fetchone()
    return dict(zip(FIELDS, row)) if row else None


def released_parent(conn, family, identity):
    keys = (*FIELDS[:2], *VERSION_FIELDS)
    row = conn.execute("""
        SELECT m.source_family, m.source_identity, m.metadata_version_sha256,
               m.content_sha256, m.capture_sha256
        FROM daily_machine_records m JOIN regional_official_source_links l
            USING (source_family, source_identity, metadata_version_sha256)
        WHERE m.source_family=? AND m.source_identity=? AND m.publication_state='released'
            AND l.official_issuer='ph_afp' AND l.official_publisher='ph_afp'
            AND l.official_republisher IS NULL AND l.first_seen_run=m.source_run
    """, (family, identity)).fetchone()
    return dict(zip(keys, row)) if row else None


def store(conn, component, pins):
    """Return inserted, duplicate or held within the caller's transaction."""
    if type(component) is not dict or not all(type(component.get(k)) is str for k in FIELDS[:2]):
        return "held"
    family, identity = (component[k] for k in FIELDS[:2])
    parent = released_parent(conn, family, identity)
    if not parent or not permitted(component, parent, pins):
        return "held"
    prior = stored_component(conn, family, identity)
    if prior is not None:
        return "duplicate" if prior == component else "held"
    conn.execute("INSERT INTO daily_record_originals VALUES (?, ?, ?, ?, ?)",
                 tuple(component[k] for k in FIELDS))
    return "inserted"


def withdrawn_components(conn, pins):
    if not is_already_applied(conn):
        return []
    withdrawn = []
    for row in conn.execute("SELECT " + ", ".join(FIELDS) + " FROM daily_record_originals"):
        component = dict(zip(FIELDS, row))
        family, identity = row[:2]
        parent = released_parent(conn, family, identity)
        if not parent or not permitted(component, parent, pins):
            withdrawn.append((family, identity))
    return withdrawn


def prune(conn, pins):
    """Remove withdrawn public components while retaining machine Records and custody."""
    withdrawn = withdrawn_components(conn, pins)
    if withdrawn:
        conn.execute("PRAGMA secure_delete=ON")
        conn.executemany("DELETE FROM daily_record_originals WHERE source_family=? AND source_identity=?",
                         withdrawn)
