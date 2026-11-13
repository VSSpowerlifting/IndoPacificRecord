"""Official-link parent rows for Japan Coast Guard English release machine records.

A shared-Daily machine record (``daily_machine_records``) is only public while
its family-scoped parent exists. For ``jp_jcg_press_en`` that parent is a row in
``japan_jcg_source_records`` (m0023): the authenticated identity of one JCG
English HTML release, with the hashes of the private original the explanation
was written from. It is link scope only: the original text never enters this
table.

The family is the standing first-party text family
``core.standing_source_rights.POLICIES["jp_jcg_press_en"]`` (Public Data
License 1.0): English HTML article prose under
``www.kaiho.mlit.go.jp/e/topics_archive/article<N>.html`` only. Linked PDFs,
photographs, other media and translations are outside it, so a custody row that
collected an attachment, or whose body is not the published HTML text, is
refused here rather than passed to processing.

Same four responsibilities as ``core.singapore_mindef_links``: read pinned
private custody, admit link-only parents idempotently (a changed version holds
the admitted row instead of replacing it), look a parent up for the lifecycle,
and carry parents from private custody to the public database as a
MAC-authenticated link-scope envelope.
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
from typing import Dict, Iterable, List, Optional

FAMILY = "jp_jcg_press_en"
TABLE = "japan_jcg_source_records"
ISSUER = "jp_coast_guard"
URL_PREFIX = "https://www.kaiho.mlit.go.jp/e/topics_archive/article"
URL_SUFFIX = ".html"
IDENTITY_PREFIX = "jcg-en:"
IDENTITY = re.compile(r"jcg-en:[1-9][0-9]{0,8}")
HEX64 = re.compile(r"[0-9a-f]{64}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
# Mirrors scraper.sources.jp_jcg_en.PILOT_BEGIN (asserted in tests); the
# collector module is not imported here so migrations stay dependency-free.
FAMILY_BEGIN = "2026-09-01"
BODY_SCOPE = "published_html_text_only"
# Mirrors scraper.sources.jp_jcg_en.EXTRACTION_PROFILE (asserted in tests). An
# earlier profile kept attachment link labels in the text and dropped prose not
# wrapped in <p>, so its rows are held rather than used as model input.
EXTRACTION_PROFILE = "jcg-html-article-text/2"
# Residue of a linked attachment in the text ("... (PDF:390KB)"): the label of
# an excluded document is not article prose and must never reach the model.
ATTACHMENT_LABEL = re.compile(r"[(\uff08]\s*PDF\b|\bPDF\s*[:\uff1a]\s*\d", re.I)
VERSION_FIELDS = ("source_identity", "canonical_official_url", "publisher_posted_date",
                  "content_sha256", "capture_sha256", "title_sha256")
LINKS_SCHEMA = "ipr-japan-jcg-links/1"
# Domain-separated from the machine-output envelope, which uses the same
# family key: a MAC for one can never authenticate the other.
LINKS_DOMAIN = b"ipr-japan-jcg-links/1\n"
LINK_FIELDS = ("source_identity", "canonical_official_url", "publisher_posted_date",
               "metadata_version_sha256", "content_sha256", "capture_sha256",
               "title_sha256", "source_git_commit", "source_run")
MAX_LINKS = 400
MAX_ENVELOPE_BYTES = 512000
KEY_ENV = "DAILY_JP_JCG_PRESS_EN_KEY"
LINKS_NAME = FAMILY + ".links.json"
LINKS_REF = "state/japan-jcg-links"
PARENT_KEYS = ("canonical_official_url", "publisher_posted_date", "metadata_version_sha256",
               "content_sha256", "capture_sha256", "title_sha256")
# Public Data License 1.0 terms the public Record must carry: the source with
# its page URL, and a statement that IPR edited/processed the content so it is
# not presented as the Government of Japan's own publication.
LICENSE_NAME = "Public Data License (Version 1.0)"
LICENSE_URL = "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0"
TERMS_URL = "https://www.kaiho.mlit.go.jp/questions/post-1.html"


class LinkRefused(ValueError):
    """A record that must not become a public official-link parent."""


def canonical_url(identity: str) -> str:
    return URL_PREFIX + identity[len(IDENTITY_PREFIX):] + URL_SUFFIX


def attribution(url: str) -> str:
    """The PDL 1.0 source statement for one release page."""
    return "Source: Japan Coast Guard website (" + url + ")"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def version_hash(fields: Dict[str, Optional[str]]) -> str:
    """Hash of exactly the identity, date, URL and private-original hashes."""
    body = json.dumps({k: fields[k] for k in VERSION_FIELDS}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def scope_hold(metadata_json, text=None) -> Optional[str]:
    """Reason a custody row is outside the standing HTML-text family, or None.

    ``text`` is the private original body. It is checked here, in custody,
    so an excluded attachment's label is held before signing or processing.
    """
    try:
        meta = json.loads(metadata_json or "{}")
    except ValueError:
        return "jcg_link_metadata_invalid"
    if type(meta) is not dict:
        return "jcg_link_metadata_invalid"
    if meta.get("body_scope") != BODY_SCOPE:
        return "jcg_link_body_scope_not_html_text"
    if meta.get("attachments_collected") is not False:
        return "jcg_link_attachment_collected"
    if meta.get("extraction_profile") != EXTRACTION_PROFILE:
        return "jcg_link_extraction_profile_superseded"
    if type(text) is not str or not text.strip():
        return "jcg_link_body_missing"
    if ATTACHMENT_LABEL.search(text):
        return "jcg_link_attachment_label_in_text"
    return None


def link_from_row(identity, url, day, run, capture_sha, content_sha, title,
                  metadata_json=None, text=None) -> dict:
    """One link dict in the shared shape; ``verified_source`` revalidates it."""
    fields = {"source_identity": identity, "canonical_official_url": url,
              "publisher_posted_date": day, "content_sha256": content_sha,
              "capture_sha256": capture_sha, "title_sha256": sha256_text(title or "")}
    return {"source_identity": identity, "canonical_official_url": url,
            "publisher_posted_date": day, "official_issuer": ISSUER,
            "official_publisher": None, "official_republisher": None,
            "first_seen_run": run, "metadata_version_sha256": version_hash(fields),
            "jcg_scope_hold": scope_hold(metadata_json, text)}


def links_from_custody(repo, commit, family=FAMILY) -> List[dict]:
    """Link dicts for every JCG row in the pinned private custody database."""
    blob = subprocess.run(["git", "-C", str(repo), "show", commit + ":state/shadow.db"],
                          check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="ipr-private-jcg-") as tmp:
        db = Path(tmp) / "shadow.db"
        db.write_bytes(blob)
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(shadow_records)")}
            if not {"source_identity", "metadata_json"} <= cols:
                raise LinkRefused("jcg_link_custody_schema_unsupported")
            rows = conn.execute(
                "SELECT source_identity,url,published_date,first_seen_run,capture_sha256,"
                "content_sha256,title_original,metadata_json,text_original FROM shadow_records "
                "WHERE source_slug=? ORDER BY source_identity", (family,)).fetchall()
    links = [link_from_row(*row) for row in rows]
    # Standing-rights qualification (#1015): bind the stored text to the
    # authenticated raw HTML at this pin, verify the captured publisher terms
    # and screen item exceptions. Rows already outside the scope are not
    # replayed. Imported lazily so this module (and m0023) stays free of
    # the collector and bs4.
    pending = [(link, row) for link, row in zip(links, rows) if not link["jcg_scope_hold"]]
    if pending:
        from core import japan_jcg_rights
        keys = ("source_identity", "url", "published_date", "first_seen_run",
                "capture_sha256", "content_sha256", "title_original", "metadata_json",
                "text_original")
        holds = japan_jcg_rights.qualify_rows(
            repo, commit, [dict(zip(keys, row)) for _, row in pending])
        for (link, _), hold in zip(pending, holds):
            link["jcg_scope_hold"] = hold
    return links


def read_parent(conn, identity) -> Optional[dict]:
    """The admitted, link-only parent in shared field names, or None."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TABLE,)).fetchone():
        return None
    row = conn.execute(
        "SELECT canonical_official_url,publisher_posted_date,metadata_version_sha256,"
        "content_sha256,capture_sha256,title_sha256 FROM " + TABLE +
        " WHERE source_identity=? AND official_issuer=? AND public_scope='official_link_only'",
        (identity, ISSUER)).fetchone()
    return dict(zip(PARENT_KEYS, row)) if row else None


def _check(record) -> None:
    ident = record.get("source_identity")
    if type(ident) is not str or not IDENTITY.fullmatch(ident):
        raise LinkRefused("jcg_link_identity_invalid")
    if record.get("jcg_scope_hold"):
        raise LinkRefused(record["jcg_scope_hold"])
    if record.get("canonical_official_url") != canonical_url(ident):
        raise LinkRefused("jcg_link_url_not_canonical")
    day = record.get("publisher_posted_date")
    if type(day) is not str or not DAY.fullmatch(day) or day < FAMILY_BEGIN:
        raise LinkRefused("jcg_link_date_invalid")
    for key in ("content_sha256", "capture_sha256", "title_sha256", "metadata_version_sha256"):
        if type(record.get(key)) is not str or not HEX64.fullmatch(record[key]):
            raise LinkRefused("jcg_link_%s_invalid" % key)
    if type(record.get("source_git_commit")) is not str or not re.fullmatch(
            r"[0-9a-f]{40}", record["source_git_commit"]):
        raise LinkRefused("jcg_link_commit_invalid")
    if type(record.get("source_run")) is not str or not record["source_run"]:
        raise LinkRefused("jcg_link_run_invalid")
    if version_hash(record) != record["metadata_version_sha256"]:
        raise LinkRefused("jcg_link_version_mismatch")


def admit_links(conn, records: Iterable[dict], *, now: Optional[str] = None) -> dict:
    """Write link-only parent rows for verified JCG records.

    ``records`` is ``with_title_hash(verified_source(...))`` or the links of an
    authenticated envelope. All rows are written in one SAVEPOINT. A row
    identical to an admitted one is ``unchanged``; a changed version of an
    admitted identity is not replaced: the admitted row is held
    (``public_scope='held'``), which withdraws its machine record from readers
    until a human reviews the change. A refused record writes nothing and is
    reported with its reason code.
    """
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TABLE,)).fetchone():
        raise LinkRefused("jcg_link_migration_required")
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = {"admitted": [], "unchanged": [], "held": [], "refused": {}}
    conn.execute("SAVEPOINT jp_jcg_links")
    try:
        for record in records:
            ident = record.get("source_identity")
            try:
                _check(record)
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
                    "content_sha256,capture_sha256,title_sha256,first_seen_run,"
                    "official_issuer,public_scope,admitted_at_utc) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,'official_link_only',?)",
                    (ident, record["canonical_official_url"], record["publisher_posted_date"],
                     record["source_git_commit"], record["metadata_version_sha256"],
                     record["content_sha256"], record["capture_sha256"],
                     record["title_sha256"], record["source_run"], ISSUER, stamp))
                summary["admitted"].append(ident)
            elif prior[0] == record["metadata_version_sha256"]:
                summary["unchanged"].append(ident)
            else:
                conn.execute("UPDATE " + TABLE + " SET public_scope='held' "
                             "WHERE source_identity=?", (ident,))
                summary["held"].append(ident)
        conn.execute("RELEASE SAVEPOINT jp_jcg_links")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT jp_jcg_links")
        conn.execute("RELEASE SAVEPOINT jp_jcg_links")
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


EVIDENCE_KEYS = ("site_terms", "listing")
EVIDENCE_CODE = re.compile(r"[a-z_]{1,40}")


def _evidence_ok(evidence) -> bool:
    return (type(evidence) is dict and set(evidence) == set(EVIDENCE_KEYS)
            and all(type(v) is str and EVIDENCE_CODE.fullmatch(v) for v in evidence.values()))


def sign_links(records: Iterable[dict], *, key: str,
               source_evidence: Optional[dict] = None) -> dict:
    """Signed link-scope envelope for verified custody records.

    Only the fields in ``LINK_FIELDS`` leave private custody: no title, no
    text. A row outside the standing HTML-text family is not sent; any other
    record that would be refused at public admission stops the signing rather
    than being dropped silently. ``source_evidence`` (fixed status codes from
    ``japan_jcg_rights.source_evidence``) tells the public operator report
    whether the latest run reached the publisher's terms.
    """
    if source_evidence is not None and not _evidence_ok(source_evidence):
        raise LinkRefused("jcg_link_source_evidence_invalid")
    if type(key) is not str or len(key) < 32:
        raise LinkRefused("jcg_link_key_invalid")
    links = []
    for record in sorted(records, key=lambda r: str(r.get("source_identity"))):
        if record.get("jcg_scope_hold"):
            continue
        _check(record)
        links.append({k: record[k] for k in LINK_FIELDS})
    if len(links) > MAX_LINKS:
        raise LinkRefused("jcg_link_envelope_too_large")
    packet = {"schema": LINKS_SCHEMA, "family": FAMILY, "links": links}
    if source_evidence is not None:
        packet["source_evidence"] = dict(source_evidence)
    raw = _canonical(packet)
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise LinkRefused("jcg_link_envelope_too_large")
    return {"packet": packet, "mac": _mac(key, raw)}


def admit_signed_links(conn, envelope, *, key: str, now: Optional[str] = None) -> dict:
    """Authenticate a link envelope, then admit its parents with ``admit_links``.

    Nothing is written unless the MAC and the exact packet shape verify. Every
    link is still re-checked by ``admit_links``, so the envelope adds
    authentication and never relaxes a rule.
    """
    return admit_links(conn, authenticated_packet(envelope, key=key)["links"], now=now)


def authenticated_packet(envelope, *, key: str) -> dict:
    """The packet of a link envelope whose MAC and exact shape verify."""
    if type(key) is not str or len(key) < 32:
        raise LinkRefused("jcg_link_key_invalid")
    if type(envelope) is not dict or set(envelope) != {"packet", "mac"} \
            or type(envelope["packet"]) is not dict or type(envelope["mac"]) is not str:
        raise LinkRefused("jcg_link_envelope_invalid")
    packet = envelope["packet"]
    raw = _canonical(packet)
    if len(raw) > MAX_ENVELOPE_BYTES or not hmac.compare_digest(_mac(key, raw), envelope["mac"]):
        raise LinkRefused("jcg_link_envelope_mac_invalid")
    links = packet.get("links")
    keys = set(packet) - {"source_evidence"}
    if keys != {"schema", "family", "links"} or packet["schema"] != LINKS_SCHEMA \
            or packet["family"] != FAMILY or type(links) is not list or len(links) > MAX_LINKS \
            or not all(type(link) is dict and set(link) == set(LINK_FIELDS) for link in links) \
            or ("source_evidence" in packet and not _evidence_ok(packet["source_evidence"])):
        raise LinkRefused("jcg_link_envelope_invalid")
    return packet
