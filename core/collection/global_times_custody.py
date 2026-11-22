"""Custody rows for Global Times military article captures.

Each distinct capture of an article page becomes one row in the shared
`official_document_versions` store (migration 0026): `capture_sha256` is the
SHA-256 of the exact wire bytes, and the metadata binds that capture to the
stored article's `content_hash`, URL, byline and printed publication time.
Re-recording identical bytes writes nothing.

Provenance is taken only from the GitHub Actions run (`GITHUB_RUN_ID`,
`GITHUB_RUN_ATTEMPT`, `GITHUB_SHA`). Outside such a run no row is written and
nothing is invented. No source text is stored here.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from typing import Mapping, Optional, Tuple

FAMILY = "global_times_mil"
SOURCE_SLUG = "global_times_mil"
METADATA_FIELDS = ("url", "content_hash", "byline", "pub_time", "fetched_at",
                   "text_held")

_ID_RE = re.compile(r"^https?://www\.globaltimes\.cn/page/\d{6}/(\d+)\.shtml$")
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_HEX40 = re.compile(r"^[a-f0-9]{40}$")

logger = logging.getLogger(__name__)


class CustodyError(RuntimeError):
    """The capture could not be recorded; the article must not be stored."""


def source_identity(url: str) -> str:
    m = _ID_RE.match(url or "")
    if not m:
        raise CustodyError("not a Global Times article URL: %r" % (url,))
    return "gt:" + m.group(1)


def provenance(env: Optional[Mapping[str, str]] = None) -> Optional[Tuple[str, str]]:
    """(source_run, collector_commit) from a GitHub Actions run, else None."""
    env = os.environ if env is None else env
    run, attempt = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    sha = env.get("GITHUB_SHA", "")
    if not (run.isdigit() and attempt.isdigit() and _HEX40.match(sha)):
        return None
    return "%s-%s" % (run, attempt), sha


def metadata(article: dict) -> dict:
    custody = article.get("custody") or {}
    return {
        "url": article["url"],
        "content_hash": article["content_hash"],
        "byline": custody.get("byline"),
        "pub_time": custody.get("pub_time"),
        "fetched_at": custody.get("fetched_at"),
        # Why the stored body is blank, when it was withheld on purpose
        # (e.g. "non_gt_byline"); None when the body was kept.
        "text_held": custody.get("text_held"),
    }


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()


def record_capture(conn: sqlite3.Connection, article: dict,
                   env: Optional[Mapping[str, str]] = None) -> str:
    """
    Write this article's capture row inside the caller's transaction.

    Returns "written", "unchanged" (these bytes are already recorded for this
    identity) or "no_provenance" (not a GitHub Actions run; nothing written).
    Raises CustodyError on malformed custody or a failed write.
    """
    custody = article.get("custody") or {}
    capture = custody.get("capture_sha256") or ""
    if not _HEX64.match(capture):
        raise CustodyError("capture_sha256 missing or malformed")
    if not _HEX64.match(article.get("content_hash") or ""):
        raise CustodyError("content_hash missing or malformed")
    if not custody.get("fetched_at"):
        raise CustodyError("fetched_at missing")
    ident = source_identity(article["url"])
    prov = provenance(env)
    if prov is None:
        logger.warning("%s: no GitHub run provenance; capture %s not recorded",
                       ident, capture[:12])
        return "no_provenance"
    source_run, commit = prov
    try:
        if conn.execute(
                "SELECT 1 FROM official_document_versions WHERE source_family=? "
                "AND source_identity=? AND capture_sha256=?",
                (FAMILY, ident, capture)).fetchone():
            return "unchanged"
        meta = metadata(article)
        conn.execute(
            "INSERT INTO official_document_versions (source_family, source_identity, "
            "metadata_sha256, metadata_json, capture_sha256, first_observed_utc, "
            "source_run, collector_commit) VALUES (?,?,?,?,?,?,?,?)",
            (FAMILY, ident, digest(meta),
             json.dumps(meta, ensure_ascii=False, sort_keys=True), capture,
             meta["fetched_at"], source_run, commit))
    except sqlite3.Error as exc:
        raise CustodyError("capture row not written: %s" % exc) from exc
    return "written"
