"""Identity and custody-metadata helpers for Global Times military captures.

Custody itself lives in the private evidence repository (DECISION_LOG
2026-11-22, action D): ``core.collection.global_times_handoff`` appends one
``capture_versions`` row per distinct capture there, keyed by the identity
below and the SHA-256 of the exact wire bytes. Nothing here writes to the
public database.

Provenance requires a complete GitHub Actions run (numeric `GITHUB_RUN_ID` and
`GITHUB_RUN_ATTEMPT`). `collector_commit` is `git rev-parse HEAD` of the
checkout that is executing, not `GITHUB_SHA`: a workflow may check out a
different revision than the event SHA. If HEAD cannot be read, or there is no
Actions run, no provenance is invented. `content_type` records the HTTP
Content-Type header, which drives text decoding but is not part of the wire
bytes. No source text is stored here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Callable, Mapping, Optional, Tuple

FAMILY = "global_times_mil"
SOURCE_SLUG = "global_times_mil"
METADATA_FIELDS = ("url", "content_hash", "byline", "pub_time", "fetched_at",
                   "text_held", "raw_retained", "content_type")

_ID_RE = re.compile(r"^https?://www\.globaltimes\.cn/page/\d{6}/(\d+)\.shtml$")
_HEX40 = re.compile(r"^[a-f0-9]{40}$")

REPO_ROOT = Path(__file__).resolve().parents[2]


class CustodyError(RuntimeError):
    """A capture's identity or custody facts are not well formed."""


def source_identity(url: str) -> str:
    m = _ID_RE.match(url or "")
    if not m:
        raise CustodyError("not a Global Times article URL: %r" % (url,))
    return "gt:" + m.group(1)


def repo_head() -> Optional[str]:
    """`git rev-parse HEAD` of the running checkout, or None if unreadable."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                                      stderr=subprocess.DEVNULL, timeout=30)
        return out.decode().strip()
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None


def provenance(env: Optional[Mapping[str, str]] = None,
               head: Optional[Callable[[], Optional[str]]] = None
               ) -> Optional[Tuple[str, str]]:
    """(source_run, collector_commit) from a GitHub Actions run, else None."""
    env = os.environ if env is None else env
    run, attempt = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    if not (run.isdigit() and attempt.isdigit()):
        return None
    commit = (head or repo_head)()
    if not (commit and _HEX40.match(commit)):
        return None
    return "%s-%s" % (run, attempt), commit


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
        # True only when the exact wire bytes were written to the configured
        # store. False means this row proves what was read, not that the bytes
        # can be recovered.
        "raw_retained": custody.get("raw_retained") is True,
        # HTTP Content-Type header as received; its charset decides decoding
        # and is not recoverable from the wire bytes. None if not captured.
        "content_type": custody.get("content_type"),
    }


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()

