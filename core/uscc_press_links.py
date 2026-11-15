"""Private custody and official-link parents for USCC press-release machine records.

A shared-Daily machine record (``daily_machine_records``) is only public while
its family-scoped parent exists. For ``us_uscc_press_en`` that parent is a row
in ``uscc_press_source_records`` (m0024): the authenticated identity of one
Commission press release, with the hashes of the private capture, its stored
body text, its title and the qualified narrative input the explanation was
written from. It is link scope only: no title or text enters this table.

The family is the founder-approved, rebuttable standing-family assessment for
unsigned, Commission-issued institutional press releases
(``docs/engineering/USCC_OFFICIAL_METADATA_COLLECTION_2026-10-15.md``), applied
by the six checks of ``core.uscc_offline_input.qualify``. Quotations,
boilerplate, social labels, linked works, attachments, media and any release
the checks cannot recognise are never model input: a held row carries a fixed
code and is never signed.

Same four responsibilities as ``core.japan_jcg_links``: read pinned private
custody (qualifying every row there), admit link-only parents idempotently (a
changed version holds the admitted row instead of replacing it), look a parent
up for the lifecycle, and carry parents from private custody to the public
database as a MAC-authenticated link-scope envelope. Two USCC rules are added:

* the parent's identity, canonical URL and listing date must equal a row the
  existing metadata lane already admitted (``uscc_official_source_records``), so
  the listing identity stays the single public identity of a release;
* ``custody_row`` / ``write_custody`` are the one way a capture enters the shared
  custody layout (``state/shadow.db``, ``state/captures``, ``state/ledger``). No
  USCC collector calls them yet: recurring capture needs its own authorization.

Nothing heavy is imported at module scope (the qualifier needs bs4), so the
migration and the Daily fetcher keep their import closure.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

FAMILY = "us_uscc_press_en"
TABLE = "uscc_press_source_records"
METADATA_TABLE = "uscc_official_source_records"
# The metadata lane's issuer code (core.uscc_official_metadata.ISSUER).
ISSUER = "us_china_economic_security_review_commission"
URL_PREFIX = "https://www.uscc.gov/press-releases/"
IDENTITY_PREFIX = "uscc-press:"
IDENTITY = re.compile(r"uscc-press:[a-z0-9]+(?:-[a-z0-9]+)*")
IDENTITY_MAX = 140
HEX64 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
# Matches the metadata lane's trusted-date floor.
FAMILY_BEGIN = "2025-01-01"
PUBLICATION_KIND = "uscc_press_release"
CUSTODY_PROFILE = "uscc-press-custody/1"
# The version a machine record binds: identity, URL, date, and the hashes of the
# raw capture, the stored body text, the title and the qualified model input.
# A qualifier change that alters the input is a new version, held for review.
VERSION_FIELDS = ("source_identity", "canonical_official_url", "publisher_posted_date",
                  "content_sha256", "capture_sha256", "title_sha256",
                  "potential_input_sha256")
LINKS_SCHEMA = "ipr-uscc-press-links/1"
# Domain-separated from the machine-output envelope, which uses the same
# family key: a MAC for one can never authenticate the other.
LINKS_DOMAIN = b"ipr-uscc-press-links/1\n"
LINK_FIELDS = ("source_identity", "canonical_official_url", "publisher_posted_date",
               "metadata_version_sha256", "content_sha256", "capture_sha256",
               "title_sha256", "potential_input_sha256", "source_git_commit", "source_run")
MAX_LINKS = 400
MAX_ENVELOPE_BYTES = 512000
KEY_ENV = "DAILY_US_USCC_PRESS_EN_KEY"
LINKS_NAME = FAMILY + ".links.json"
LINKS_REF = "state/uscc-press-links"
PARENT_KEYS = ("canonical_official_url", "publisher_posted_date", "metadata_version_sha256",
               "content_sha256", "capture_sha256", "title_sha256")
SHADOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_records (
    url                TEXT PRIMARY KEY,
    source_identity    TEXT NOT NULL UNIQUE,
    source_slug        TEXT NOT NULL,
    title_original     TEXT NOT NULL,
    text_original      TEXT NOT NULL,
    published_date     TEXT NOT NULL,
    language_tag       TEXT NOT NULL,
    publication_kind   TEXT NOT NULL,
    content_sha256     TEXT NOT NULL,
    capture_sha256     TEXT NOT NULL,
    retrieved_at       TEXT NOT NULL,
    first_seen_run     TEXT NOT NULL,
    metadata_json      TEXT NOT NULL
)"""
SHADOW_COLUMNS = ("url", "source_identity", "source_slug", "title_original", "text_original",
                  "published_date", "language_tag", "publication_kind", "content_sha256",
                  "capture_sha256", "retrieved_at", "first_seen_run", "metadata_json")


class LinkRefused(ValueError):
    """A record that must not become a public official-link parent."""


def canonical_url(identity: str) -> str:
    return URL_PREFIX + identity[len(IDENTITY_PREFIX):]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def version_hash(fields: Dict[str, Optional[str]]) -> str:
    """Hash of exactly the identity, date, URL and private-original hashes."""
    body = json.dumps({k: fields[k] for k in VERSION_FIELDS}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def _identity_ok(identity) -> bool:
    return (type(identity) is str and len(identity) <= IDENTITY_MAX
            and IDENTITY.fullmatch(identity) is not None)


# --- Custody: the one way a capture enters the shared custody layout ---------

def custody_row(raw: bytes, *, source_identity: str, publication_date: str, access: dict,
                robots_txt: bytes, run_id: str, provenance: Optional[dict] = None
                ) -> Tuple[dict, Dict[str, bytes]]:
    """A ``shadow_records`` row and the captures it needs, for one release capture.

    ``access`` is the capture-bound receipt recorded at retrieval (exactly the
    qualifier's ``ACCESS_KEYS``); it is stored in ``metadata_json`` with the
    robots hash, and the robots bytes are kept as a capture so qualification can
    replay the access conditions at any later pin. Title and text are derived
    from the capture by the qualifier's own rule; a capture with no single
    release body is still preserved, with empty text, and qualification holds
    it. Nothing is fetched and nothing is judged eligible here.
    """
    from core.uscc_offline_input import ACCESS_KEYS, release_text
    if not _identity_ok(source_identity):
        raise LinkRefused("uscc_custody_identity_invalid")
    if type(publication_date) is not str or not DAY.fullmatch(publication_date):
        raise LinkRefused("uscc_custody_date_invalid")
    if type(raw) is not bytes or type(robots_txt) is not bytes or not robots_txt:
        raise LinkRefused("uscc_custody_bytes_invalid")
    if type(access) is not dict or set(access) != set(ACCESS_KEYS) \
            or access["capture_sha256"] != _sha(raw) or access["payload_bytes"] != len(raw) \
            or access["robots_sha256"] != _sha(robots_txt):
        raise LinkRefused("uscc_custody_access_receipt_mismatch")
    if type(run_id) is not str or not run_id:
        raise LinkRefused("uscc_custody_run_invalid")
    derived = release_text(raw)
    title, text = derived if derived is not None else ("", "")
    meta = {"source_identity": source_identity, "publication_kind": PUBLICATION_KIND,
            "custody_profile": CUSTODY_PROFILE, "access": dict(access)}
    if provenance is not None:
        meta["provenance"] = provenance
    row = {"url": canonical_url(source_identity), "source_identity": source_identity,
           "source_slug": FAMILY, "title_original": title, "text_original": text,
           "published_date": publication_date, "language_tag": "en",
           "publication_kind": PUBLICATION_KIND, "content_sha256": sha256_text(text),
           "capture_sha256": access["capture_sha256"], "retrieved_at": access["retrieved_utc"],
           "first_seen_run": run_id,
           "metadata_json": json.dumps(meta, sort_keys=True, ensure_ascii=False)}
    return row, {access["capture_sha256"]: raw, access["robots_sha256"]: robots_txt}


def write_custody(state_dir, rows: Iterable[dict], captures: Dict[str, bytes]) -> dict:
    """Append rows and content-addressed captures under ``state_dir`` (``state/``).

    Append-only: an identical row or capture already present is left as it is; a
    different row for an existing URL or identity, or different bytes under an
    existing capture name, is refused rather than overwritten. Ledger files are
    the collector's own record and are written by it, never here.
    """
    state = Path(state_dir)
    (state / "captures").mkdir(parents=True, exist_ok=True)
    for digest, raw in captures.items():
        if not HEX64.fullmatch(digest) or _sha(raw) != digest:
            raise LinkRefused("uscc_custody_capture_name_mismatch")
        path = state / "captures" / (digest + ".bin")
        if path.exists():
            if path.read_bytes() != raw:
                raise LinkRefused("uscc_custody_capture_conflict")
            continue
        path.write_bytes(raw)
    written, unchanged = 0, 0
    with sqlite3.connect(str(state / "shadow.db")) as conn:
        conn.execute(SHADOW_SCHEMA)
        for row in rows:
            if set(row) != set(SHADOW_COLUMNS):
                raise LinkRefused("uscc_custody_row_invalid")
            prior = conn.execute(
                "SELECT " + ",".join(SHADOW_COLUMNS) + " FROM shadow_records "
                "WHERE url=? OR source_identity=?", (row["url"], row["source_identity"])).fetchall()
            if prior:
                if len(prior) != 1 or prior[0] != tuple(row[c] for c in SHADOW_COLUMNS):
                    raise LinkRefused("uscc_custody_row_conflict")
                unchanged += 1
                continue
            conn.execute("INSERT INTO shadow_records (" + ",".join(SHADOW_COLUMNS) + ") VALUES ("
                         + ",".join("?" for _ in SHADOW_COLUMNS) + ")",
                         tuple(row[c] for c in SHADOW_COLUMNS))
            written += 1
    conn.close()
    return {"written": written, "unchanged": unchanged}


# --- Qualification at the pin (the shared Daily links adapter) ---------------

def _show(repo, commit, path) -> Optional[bytes]:
    result = subprocess.run(["git", "-C", str(repo), "show", commit + ":" + path],
                            capture_output=True)
    return result.stdout if result.returncode == 0 else None


def qualify_row(row: dict, raw: Optional[bytes], robots: Optional[bytes]) -> Tuple[Optional[str], Optional[dict]]:
    """(hold code, potential input) for one custody row at its pinned bytes.

    Codes only, never content. Eligible rows also prove the stored text and
    title are exactly what the capture reproduces under the qualifier's rule.
    """
    from core.uscc_offline_input import USCCInputHold, qualify
    try:
        meta = json.loads(row["metadata_json"] or "{}")
    except ValueError:
        return "uscc_custody_metadata_invalid", None
    if type(meta) is not dict or meta.get("custody_profile") != CUSTODY_PROFILE \
            or meta.get("source_identity") != row["source_identity"] \
            or meta.get("publication_kind") != PUBLICATION_KIND or type(meta.get("access")) is not dict:
        return "uscc_custody_metadata_invalid", None
    if raw is None:
        return "uscc_capture_missing_at_pin", None
    if _sha(raw) != row["capture_sha256"]:
        return "uscc_capture_hash_mismatch", None
    if robots is None:
        return "uscc_robots_capture_missing_at_pin", None
    try:
        result = qualify(raw, source_identity=row["source_identity"],
                         canonical_url=row["url"], publication_date=row["published_date"],
                         access=meta["access"], robots_txt=robots)
    except USCCInputHold as exc:
        return "uscc_" + str(exc), None
    manifest = result["manifest"]
    if manifest["content_sha256"] != row["content_sha256"] \
            or manifest["content_sha256"] != sha256_text(row["text_original"]) \
            or manifest["title_sha256"] != sha256_text(row["title_original"]):
        return "uscc_custody_text_not_reproduced", None
    return None, {"narrative": result["potential_input"]["narrative"],
                  "potential_input_sha256": manifest["potential_input_sha256"]}


def links_from_custody(repo, commit, family=FAMILY) -> List[dict]:
    """Link dicts for every USCC row in the pinned private custody database.

    Every row is qualified against its own capture at this pin. Eligible rows
    carry the narrative only under ``_narrative``, which the shared lifecycle
    pops before anything is persisted; held rows carry ``uscc_hold`` and no prose.
    """
    blob = _show(repo, commit, "state/shadow.db")
    if blob is None:
        raise LinkRefused("uscc_custody_database_missing")
    with tempfile.TemporaryDirectory(prefix="ipr-private-uscc-") as tmp:
        db = Path(tmp) / "shadow.db"
        db.write_bytes(blob)
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cols = {r[1] for r in conn.execute("PRAGMA table_info(shadow_records)")}
            if not set(SHADOW_COLUMNS) <= cols:
                raise LinkRefused("uscc_custody_schema_unsupported")
            rows = [dict(r) for r in conn.execute(
                "SELECT " + ",".join(SHADOW_COLUMNS) + " FROM shadow_records "
                "WHERE source_slug=? ORDER BY source_identity", (family,))]
    links = []
    for row in rows:
        raw = _show(repo, commit, "state/captures/" + row["capture_sha256"] + ".bin") \
            if HEX64.fullmatch(row["capture_sha256"] or "") else None
        try:
            access = json.loads(row["metadata_json"] or "{}").get("access") or {}
            robots_sha = access.get("robots_sha256") if type(access) is dict else None
        except (ValueError, AttributeError):
            robots_sha = None
        robots = _show(repo, commit, "state/captures/" + robots_sha + ".bin") \
            if type(robots_sha) is str and HEX64.fullmatch(robots_sha) else None
        hold, potential = qualify_row(row, raw, robots)
        fields = {"source_identity": row["source_identity"], "canonical_official_url": row["url"],
                  "publisher_posted_date": row["published_date"],
                  "content_sha256": row["content_sha256"], "capture_sha256": row["capture_sha256"],
                  "title_sha256": sha256_text(row["title_original"]),
                  "potential_input_sha256": potential["potential_input_sha256"] if potential else None}
        link = {"source_identity": row["source_identity"], "canonical_official_url": row["url"],
                "publisher_posted_date": row["published_date"], "official_issuer": ISSUER,
                "official_publisher": None, "official_republisher": None,
                "first_seen_run": row["first_seen_run"],
                "metadata_version_sha256": version_hash(fields),
                "potential_input_sha256": fields["potential_input_sha256"],
                "uscc_hold": hold}
        if potential is not None:
            link["_narrative"] = potential["narrative"]
        links.append(link)
    return links


# --- Public parent rows -----------------------------------------------------

def _table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def read_parent(conn, identity) -> Optional[dict]:
    """The admitted, link-only parent in shared field names, or None.

    The parent counts only while the metadata lane still holds the same
    identity, canonical URL and listing date.
    """
    if not (_table(conn, TABLE) and _table(conn, METADATA_TABLE)):
        return None
    row = conn.execute(
        "SELECT p.canonical_official_url,p.publisher_posted_date,p.metadata_version_sha256,"
        "p.content_sha256,p.capture_sha256,p.title_sha256 FROM " + TABLE + " p JOIN "
        + METADATA_TABLE + " m ON m.source_identity=p.source_identity "
        "AND m.canonical_official_url=p.canonical_official_url "
        "AND m.publisher_posted_date=p.publisher_posted_date "
        "WHERE p.source_identity=? AND p.official_issuer=? AND p.public_scope='official_link_only' "
        "AND m.public_scope='official_link_only'", (identity, ISSUER)).fetchone()
    return dict(zip(PARENT_KEYS, row)) if row else None


def _check(record) -> None:
    ident = record.get("source_identity")
    if not _identity_ok(ident):
        raise LinkRefused("uscc_link_identity_invalid")
    if record.get("uscc_hold"):
        raise LinkRefused(record["uscc_hold"])
    # The schema mirrors this set (m0024 CHECK); tests assert they are equal.
    from core.uscc_offline_input import HELD_IDENTITIES
    if ident in HELD_IDENTITIES:
        raise LinkRefused("uscc_source_specific_hold")
    if record.get("canonical_official_url") != canonical_url(ident):
        raise LinkRefused("uscc_link_url_not_canonical")
    day = record.get("publisher_posted_date")
    if type(day) is not str or not DAY.fullmatch(day) or day < FAMILY_BEGIN:
        raise LinkRefused("uscc_link_date_invalid")
    for key in ("content_sha256", "capture_sha256", "title_sha256", "potential_input_sha256",
                "metadata_version_sha256"):
        if type(record.get(key)) is not str or not HEX64.fullmatch(record[key]):
            raise LinkRefused("uscc_link_%s_invalid" % key)
    if type(record.get("source_git_commit")) is not str or not COMMIT.fullmatch(
            record["source_git_commit"]):
        raise LinkRefused("uscc_link_commit_invalid")
    if type(record.get("source_run")) is not str or not record["source_run"]:
        raise LinkRefused("uscc_link_run_invalid")
    if version_hash(record) != record["metadata_version_sha256"]:
        raise LinkRefused("uscc_link_version_mismatch")


def admit_links(conn, records: Iterable[dict], *, now: Optional[str] = None) -> dict:
    """Write link-only parent rows for verified USCC records.

    ``records`` is ``with_title_hash(verified_source(...))`` or the links of an
    authenticated envelope. All rows are written in one SAVEPOINT. A row whose
    identity, URL or listing date is not exactly an admitted metadata row is
    refused. A row identical to an admitted parent is ``unchanged``; a changed
    version of an admitted identity is not replaced: the admitted parent is held
    (``public_scope='held'``), which withdraws its machine record from readers
    until a human reviews the change. A refused record writes nothing and is
    reported with its reason code.
    """
    if not _table(conn, TABLE):
        raise LinkRefused("uscc_link_migration_required")
    if not _table(conn, METADATA_TABLE):
        raise LinkRefused("uscc_link_metadata_lane_missing")
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = {"admitted": [], "unchanged": [], "held": [], "refused": {}}
    conn.execute("SAVEPOINT uscc_press_links")
    try:
        for record in records:
            ident = record.get("source_identity")
            try:
                _check(record)
                listed = conn.execute(
                    "SELECT canonical_official_url,publisher_posted_date,official_issuer,public_scope "
                    "FROM " + METADATA_TABLE + " WHERE source_identity=?", (ident,)).fetchone()
                if listed is None:
                    raise LinkRefused("uscc_link_metadata_identity_missing")
                if tuple(listed) != (record["canonical_official_url"],
                                     record["publisher_posted_date"], ISSUER, "official_link_only"):
                    raise LinkRefused("uscc_link_metadata_identity_mismatch")
            except LinkRefused as exc:
                summary["refused"][str(ident)] = str(exc)
                continue
            prior = conn.execute(
                "SELECT metadata_version_sha256,public_scope FROM " + TABLE +
                " WHERE source_identity=?", (ident,)).fetchone()
            if prior is None:
                conn.execute(
                    "INSERT INTO " + TABLE + " (source_identity,canonical_official_url,"
                    "publisher_posted_date,source_git_commit,metadata_version_sha256,"
                    "content_sha256,capture_sha256,title_sha256,potential_input_sha256,"
                    "first_seen_run,official_issuer,public_scope,admitted_at_utc) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,'official_link_only',?)",
                    (ident, record["canonical_official_url"], record["publisher_posted_date"],
                     record["source_git_commit"], record["metadata_version_sha256"],
                     record["content_sha256"], record["capture_sha256"],
                     record["title_sha256"], record["potential_input_sha256"],
                     record["source_run"], ISSUER, stamp))
                summary["admitted"].append(ident)
            elif prior[0] == record["metadata_version_sha256"]:
                summary["unchanged"].append(ident)
            else:
                conn.execute("UPDATE " + TABLE + " SET public_scope='held' "
                             "WHERE source_identity=?", (ident,))
                summary["held"].append(ident)
        conn.execute("RELEASE SAVEPOINT uscc_press_links")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT uscc_press_links")
        conn.execute("RELEASE SAVEPOINT uscc_press_links")
        raise
    return summary


def with_title_hash(records: Iterable[dict]) -> List[dict]:
    """Add the title hash the parent row binds (records carry the original title)."""
    return [{**r, "title_sha256": sha256_text(r["title"])} for r in records]


def _canonical(packet) -> bytes:
    return json.dumps(packet, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def _mac(key: str, raw: bytes) -> str:
    return hmac.new(key.encode(), LINKS_DOMAIN + raw, hashlib.sha256).hexdigest()


def sign_links(records: Iterable[dict], *, key: str) -> dict:
    """Signed link-scope envelope for verified custody records.

    Only the fields in ``LINK_FIELDS`` leave private custody: no title, no text,
    no narrative. A held row is not sent; any other record that would be
    refused at public admission stops the signing rather than being dropped
    silently.
    """
    if type(key) is not str or len(key) < 32:
        raise LinkRefused("uscc_link_key_invalid")
    links = []
    for record in sorted(records, key=lambda r: str(r.get("source_identity"))):
        if record.get("uscc_hold"):
            continue
        _check(record)
        links.append({k: record[k] for k in LINK_FIELDS})
    if len(links) > MAX_LINKS:
        raise LinkRefused("uscc_link_envelope_too_large")
    packet = {"schema": LINKS_SCHEMA, "family": FAMILY, "links": links}
    raw = _canonical(packet)
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise LinkRefused("uscc_link_envelope_too_large")
    return {"packet": packet, "mac": _mac(key, raw)}


def authenticated_packet(envelope, *, key: str) -> dict:
    """The packet of a link envelope whose MAC and exact shape verify."""
    if type(key) is not str or len(key) < 32:
        raise LinkRefused("uscc_link_key_invalid")
    if type(envelope) is not dict or set(envelope) != {"packet", "mac"} \
            or type(envelope["packet"]) is not dict or type(envelope["mac"]) is not str:
        raise LinkRefused("uscc_link_envelope_invalid")
    packet = envelope["packet"]
    raw = _canonical(packet)
    if len(raw) > MAX_ENVELOPE_BYTES or not hmac.compare_digest(_mac(key, raw), envelope["mac"]):
        raise LinkRefused("uscc_link_envelope_mac_invalid")
    links = packet.get("links")
    if set(packet) != {"schema", "family", "links"} or packet["schema"] != LINKS_SCHEMA \
            or packet["family"] != FAMILY or type(links) is not list or len(links) > MAX_LINKS \
            or not all(type(link) is dict and set(link) == set(LINK_FIELDS) for link in links):
        raise LinkRefused("uscc_link_envelope_invalid")
    return packet


def admit_signed_links(conn, envelope, *, key: str, now: Optional[str] = None) -> dict:
    """Authenticate a link envelope, then admit its parents with ``admit_links``.

    Nothing is written unless the MAC and the exact packet shape verify. Every
    link is still re-checked by ``admit_links``, so the envelope adds
    authentication and never relaxes a rule.
    """
    return admit_links(conn, authenticated_packet(envelope, key=key)["links"], now=now)
