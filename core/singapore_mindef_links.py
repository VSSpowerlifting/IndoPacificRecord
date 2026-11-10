"""Official-link parent rows for Singapore MINDEF machine records.

A shared-Daily machine record (``daily_machine_records``) is only public while
its family-scoped parent exists. For ``sg_mindef_releases`` that parent is a
row in ``singapore_mindef_source_records`` (m0022): the authenticated identity
of one MINDEF release, with the hashes of the private original that the
explanation was written from. It is link scope only. The original text and any
media never enter this table; they stay in private custody.

This module does three things and nothing else:

* ``links_from_custody`` reads the pinned private custody database that
  ``scripts/shadow_collect.py`` writes (the shared lifecycle's
  ``verified_source`` revalidates every row it returns);
* ``admit_links`` writes the parent rows into the public database, idempotently,
  and holds a row whose version drifted instead of replacing it;
* ``read_parent`` is the lookup ``DailySource.parent_link`` uses, so the
  lifecycle binds a machine record to the version that was actually admitted.

The two speech releases that earlier source review excluded stay excluded here
by a database CHECK as well as by policy.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

FAMILY = "sg_mindef_releases"
TABLE = "singapore_mindef_source_records"
ISSUER = "sg_mindef"
URL_PREFIX = "https://www.mindef.gov.sg/news-and-events/latest-releases/"
# Mirrors scraper.sources.sg_mindef.HELD_RELEASE_SLUGS (asserted in tests); the
# collector module is not imported here so migrations stay dependency-free.
HELD_IDENTITIES = ("15aug26-speech", "16sep26-speech")
IDENTITY = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
HEX64 = re.compile(r"[0-9a-f]{64}")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
VERSION_FIELDS = ("source_identity", "canonical_official_url", "publisher_posted_date",
                  "content_sha256", "capture_sha256", "title_sha256")
PARENT_KEYS = ("canonical_official_url", "publisher_posted_date", "metadata_version_sha256",
               "content_sha256", "capture_sha256", "title_sha256")


class LinkRefused(ValueError):
    """A record that must not become a public official-link parent."""


def canonical_url(identity: str) -> str:
    return URL_PREFIX + identity + "/"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def version_hash(fields: Dict[str, Optional[str]]) -> str:
    """Hash of exactly the identity, date, URL and private-original hashes."""
    body = json.dumps({k: fields[k] for k in VERSION_FIELDS}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def link_from_row(identity, url, day, run, capture_sha, content_sha, title) -> dict:
    """One link dict in the shared shape; ``verified_source`` revalidates it."""
    fields = {"source_identity": identity, "canonical_official_url": url,
              "publisher_posted_date": day, "content_sha256": content_sha,
              "capture_sha256": capture_sha, "title_sha256": sha256_text(title or "")}
    return {"source_identity": identity, "canonical_official_url": url,
            "publisher_posted_date": day, "official_issuer": ISSUER,
            "official_publisher": None, "official_republisher": None,
            "first_seen_run": run, "metadata_version_sha256": version_hash(fields)}


def links_from_custody(repo, commit, family=FAMILY) -> List[dict]:
    """Link dicts for every Singapore row in the pinned private custody database."""
    blob = subprocess.run(["git", "-C", str(repo), "show", commit + ":state/shadow.db"],
                          check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="ipr-private-sg-") as tmp:
        db = Path(tmp) / "shadow.db"
        db.write_bytes(blob)
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
            rows = conn.execute(
                "SELECT source_identity,url,published_date,first_seen_run,capture_sha256,"
                "content_sha256,title_original FROM shadow_records WHERE source_slug=? "
                "ORDER BY source_identity", (family,)).fetchall()
    return [link_from_row(*row) for row in rows]


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
        raise LinkRefused("singapore_link_identity_invalid")
    if ident in HELD_IDENTITIES:
        raise LinkRefused("singapore_link_identity_held")
    if record.get("canonical_official_url") != canonical_url(ident):
        raise LinkRefused("singapore_link_url_not_canonical")
    if type(record.get("publisher_posted_date")) is not str or not DAY.fullmatch(record["publisher_posted_date"]):
        raise LinkRefused("singapore_link_date_invalid")
    for key in ("content_sha256", "capture_sha256", "title_sha256", "metadata_version_sha256"):
        if type(record.get(key)) is not str or not HEX64.fullmatch(record[key]):
            raise LinkRefused("singapore_link_%s_invalid" % key)
    if type(record.get("source_git_commit")) is not str or not re.fullmatch(
            r"[0-9a-f]{40}", record["source_git_commit"]):
        raise LinkRefused("singapore_link_commit_invalid")
    if type(record.get("source_run")) is not str or not record["source_run"]:
        raise LinkRefused("singapore_link_run_invalid")
    if version_hash(record) != record["metadata_version_sha256"]:
        raise LinkRefused("singapore_link_version_mismatch")


def admit_links(conn, records: Iterable[dict], *, now: Optional[str] = None) -> dict:
    """Write link-only parent rows for verified Singapore records.

    ``records`` is the output of ``processing.daily_intake.verified_source``
    (which already reconciled each row to the pinned custody bytes) with a
    ``title_sha256`` added by ``with_title_hash``. All rows are written in one
    SAVEPOINT. A row identical to an admitted one is ``unchanged``; a changed
    version of an admitted identity is not replaced: the admitted row is held
    (``public_scope='held'``), which withdraws its machine record from readers
    until a human reviews the change. A refused record writes nothing and is
    reported with its reason code.
    """
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TABLE,)).fetchone():
        raise LinkRefused("singapore_link_migration_required")
    stamp = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = {"admitted": [], "unchanged": [], "held": [], "refused": {}}
    conn.execute("SAVEPOINT sg_mindef_links")
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
        conn.execute("RELEASE SAVEPOINT sg_mindef_links")
    except BaseException:
        conn.execute("ROLLBACK TO SAVEPOINT sg_mindef_links")
        conn.execute("RELEASE SAVEPOINT sg_mindef_links")
        raise
    return summary


def with_title_hash(records: Iterable[dict]) -> List[dict]:
    """Add the title hash the parent row binds (records carry the original title)."""
    return [{**r, "title_sha256": sha256_text(r["title"])} for r in records]
