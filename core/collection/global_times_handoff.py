"""Global Times military: private-first custody and its signed public handoff.

DECISION_LOG 2026-11-22 (action D). The public Daily no longer fetches Global
Times. A private collector runs this module's ``collect`` against the
publisher, keeps every observed capture in the private evidence repository
(``archive/global-times-mil``), proves the committed state with ``verify`` on a
fresh clone, and ``sign``s a small envelope of the latest public-text record
per article. The public Daily replays that envelope through
``adapters.global_times_handoff.GlobalTimesHandoffAdapter``; it never reaches
the publisher and never writes custody.

Read side (``load_envelope``, ``verify_envelope``) is pure and imports no
network library: the adapter imports it. Everything that touches the
publisher, the scraper or ``git`` is imported inside the subcommand that needs
it.

Private custody (``state/`` in the custody checkout):

* ``shadow.db`` table ``capture_versions``: one append-only row per distinct
  ``(source_identity, capture_sha256)``. Re-observations of a known article are
  recorded as versions, never skipped. ``content_sha256`` is exactly the
  public Daily's ``content_hash`` for the same parsed page
  (``processing.metadata.normalize_article``), so a public row can always be
  tied back to the bytes it came from.
* ``captures/<capture_sha256>.bin``: the exact wire bytes, content-addressed.
  A page whose body is held (``text_held``, e.g. another agency's byline)
  keeps NO bytes and a blank body.
* ``ledger/<%Y%m%dT%H%M%SZ>-<run>.json``: one ``ipr-collection-attempts/1``
  ledger per attempt, written even when the attempt fails.
* ``private_attempts/<run>.json``: the attempt's integer exit status.
* ``clock.json``: day zero, written once on the first healthy attempt.

Nothing printed by the CLI carries page text: counts and codes only.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from core.collection import attempts
from core.collection import status as st
from processing.metadata import normalize_article

FAMILY = "global_times_mil"
SOURCE_SLUG = "global_times_mil"
SCHEMA = "ipr-global-times-captures/1"
DOMAIN = b"ipr-global-times-captures/1\n"
CUSTODY_REF = "archive/global-times-mil"
ENVELOPE_REF = "state/global-times-captures"
ENVELOPE_NAME = "global_times_mil.captures.json"
KEY_ENV = "DAILY_GLOBAL_TIMES_MIL_KEY"
INTAKE_DIR_ENV = "IPR_DAILY_INTAKE_DIR"
CRON_UTC = "01:17"
GRACE_HOURS = 14
LOOKBACK_DAYS = 2                 # collection window [target-2, target]
RECORD_WINDOW = timedelta(days=3)  # envelope: versions fetched in the last 3 days
MAX_ENVELOPE_BYTES = 512000
MAX_RECORDS = 400

#: The one canonical article URL form. Matched in full, never normalised: a
#: URL that differs from what the public archive stores by one byte would
#: create a second public record for the same article.
CANONICAL_URL = re.compile(
    r"https://www\.globaltimes\.cn/page/[0-9]{6}/([0-9]{1,12})\.shtml")

_HEX64 = re.compile(r"[a-f0-9]{64}")
_HEX40 = re.compile(r"[a-f0-9]{40}")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_RUN = re.compile(r"([0-9]{1,20})-([0-9]{1,6})")
_CODE = re.compile(r"[a-z0-9_]{1,40}")

ENVELOPE_KEYS = frozenset({"schema", "family", "custody_ref", "custody_commit",
                           "generated_utc", "collection", "records", "mac"})
RECORD_KEYS = frozenset({"url", "source_slug", "title_original", "text_original",
                         "published_date", "content_verdict", "text_held",
                         "source_identity", "capture_sha256", "content_sha256",
                         "fetched_at", "source_run", "collector_commit",
                         "raw_retained"})
#: Exactly the keys the legacy scraper's ``parse_article`` returns (without
#: its private ``custody`` block); ``text_held`` only when held.
RAW_KEYS = ("url", "source_slug", "title_original", "text_original",
            "published_date", "content_verdict")
CONTENT_VERDICTS = (None, "media_only")

CAPTURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS capture_versions (
    source_identity  TEXT NOT NULL,
    url              TEXT NOT NULL,
    title_original   TEXT NOT NULL,
    text_original    TEXT NOT NULL,
    published_date   TEXT NOT NULL,
    content_verdict  TEXT,
    text_held        TEXT,
    byline           TEXT,
    pub_time         TEXT,
    content_type     TEXT,
    capture_sha256   TEXT NOT NULL,
    content_sha256   TEXT NOT NULL,
    fetched_at       TEXT NOT NULL,
    source_run       TEXT NOT NULL,
    collector_commit TEXT NOT NULL,
    PRIMARY KEY (source_identity, capture_sha256)
);
CREATE INDEX IF NOT EXISTS capture_versions_url ON capture_versions (url);
CREATE TRIGGER IF NOT EXISTS capture_versions_no_update
    BEFORE UPDATE ON capture_versions
    BEGIN SELECT RAISE(ABORT, 'capture_versions is append-only'); END;
CREATE TRIGGER IF NOT EXISTS capture_versions_no_delete
    BEFORE DELETE ON capture_versions
    BEGIN SELECT RAISE(ABORT, 'capture_versions is append-only'); END;
"""


class HandoffError(ValueError):
    """A fixed, public-safe code. Never carries page text, URLs or keys."""


# ── shared helpers (pure) ─────────────────────────────────────────────────────

def source_identity(url) -> Optional[str]:
    """``gt:<article number>`` for a canonical URL, else None."""
    m = CANONICAL_URL.fullmatch(url) if isinstance(url, str) else None
    return "gt:" + m.group(1) if m else None


def public_raw(article: dict) -> dict:
    """The legacy ``parse_article`` dict the public pipeline receives."""
    raw = {k: article[k] for k in RAW_KEYS}
    if article.get("text_held"):
        raw["text_held"] = article["text_held"]
    return raw


def content_sha256(raw: dict) -> str:
    """The public ``content_hash`` this dict will be stored under."""
    return normalize_article(raw)["content_hash"]


def canonical(packet) -> bytes:
    return json.dumps(packet, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def mac(key: str, packet: dict) -> str:
    body = {k: v for k, v in packet.items() if k != "mac"}
    return hmac.new(key.encode("utf-8"), DOMAIN + canonical(body),
                    hashlib.sha256).hexdigest()


def _key_ok(key) -> bool:
    return type(key) is str and len(key) >= 32


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value) -> Optional[datetime]:
    if not (isinstance(value, str) and _UTC.fullmatch(value)):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def _date_ok(value) -> bool:
    if not (isinstance(value, str) and _DATE.fullmatch(value)):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_record(rec) -> dict:
    """One envelope record, exactly well formed; HandoffError otherwise."""
    if type(rec) is not dict or set(rec) != RECORD_KEYS:
        raise HandoffError("gt_handoff_record_shape")
    ident = source_identity(rec["url"])
    held = rec["text_held"]
    ok = (ident is not None and rec["source_identity"] == ident
          and rec["source_slug"] == SOURCE_SLUG
          and type(rec["title_original"]) is str and rec["title_original"].strip()
          and type(rec["text_original"]) is str
          and _date_ok(rec["published_date"])
          and rec["content_verdict"] in CONTENT_VERDICTS
          and (held is None or (type(held) is str and _CODE.fullmatch(held)))
          and (rec["capture_sha256"] is None
               or (type(rec["capture_sha256"]) is str
                   and _HEX64.fullmatch(rec["capture_sha256"])))
          and type(rec["content_sha256"]) is str
          and _HEX64.fullmatch(rec["content_sha256"])
          and _parse_utc(rec["fetched_at"]) is not None
          and type(rec["source_run"]) is str and _RUN.fullmatch(rec["source_run"])
          and type(rec["collector_commit"]) is str
          and _HEX40.fullmatch(rec["collector_commit"])
          and type(rec["raw_retained"]) is bool)
    if not ok:
        raise HandoffError("gt_handoff_record_invalid")
    if held is not None and (rec["text_original"] != "" or rec["raw_retained"]
                             or rec["content_verdict"] is not None):
        # A held body is never published and its bytes are never kept.
        raise HandoffError("gt_handoff_held_record_invalid")
    if held is None and (not rec["raw_retained"] or rec["capture_sha256"] is None):
        # A public text without its retained capture is not custody.
        raise HandoffError("gt_handoff_record_not_retained")
    if content_sha256(public_raw(rec)) != rec["content_sha256"]:
        raise HandoffError("gt_handoff_content_hash_mismatch")
    return rec


def verify_envelope(raw: bytes, key) -> dict:
    """The envelope, authenticated and exactly well formed; HandoffError otherwise.

    Rejects oversize input, unknown or missing keys, a bad MAC, a wrong schema
    or family and any non-canonical URL. Nothing is normalised. ``collection``
    may be null; ``load_envelope`` turns that into ``collection_not_attested``.
    """
    if not _key_ok(key):
        raise HandoffError("gt_handoff_key_unavailable")
    if type(raw) is not bytes or len(raw) > MAX_ENVELOPE_BYTES:
        raise HandoffError("gt_handoff_envelope_too_large")
    try:
        env = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        raise HandoffError("gt_handoff_envelope_malformed") from None
    if type(env) is not dict or set(env) != ENVELOPE_KEYS \
            or type(env.get("mac")) is not str:
        raise HandoffError("gt_handoff_envelope_shape")
    if not hmac.compare_digest(mac(key, env), env["mac"]):
        raise HandoffError("gt_handoff_mac_invalid")
    if env["schema"] != SCHEMA or env["family"] != FAMILY \
            or env["custody_ref"] != CUSTODY_REF:
        raise HandoffError("gt_handoff_schema_invalid")
    if not (type(env["custody_commit"]) is str
            and _HEX40.fullmatch(env["custody_commit"])
            and _parse_utc(env["generated_utc"]) is not None
            and type(env["records"]) is list
            and len(env["records"]) <= MAX_RECORDS):
        raise HandoffError("gt_handoff_envelope_invalid")
    facts = env["collection"]
    if facts is not None:
        if attempts.validate(facts) is None or facts["family"] != FAMILY \
                or facts["custody_commit"] != env["custody_commit"]:
            raise HandoffError("gt_handoff_collection_invalid")
    seen = set()
    for rec in env["records"]:
        _check_record(rec)
        if rec["source_identity"] in seen:
            raise HandoffError("gt_handoff_duplicate_record")
        seen.add(rec["source_identity"])
    return env


def load_envelope(path, key, now: Optional[datetime] = None
                  ) -> Tuple[List[dict], Optional[str], Optional[str]]:
    """(records, status_or_None, detail) for the public replay adapter.

    Fails closed with no records: absent file -> LISTING_FAILURE
    ``gt_handoff_not_delivered``; bad MAC/schema/shape -> ADAPTER_ERROR with a
    fixed code; no collection facts -> FETCH_FAILURE
    ``collection_not_attested``; a failed or stale collection -> the
    attempts verdict. Never raises for any input.
    """
    now = now or _utc_now()
    try:
        p = Path(path) if path else None
        if p is None or not p.is_file():
            return [], st.LISTING_FAILURE, "gt_handoff_not_delivered"
        if p.stat().st_size > MAX_ENVELOPE_BYTES:
            return [], st.ADAPTER_ERROR, "gt_handoff_envelope_too_large"
        env = verify_envelope(p.read_bytes(), key)
    except HandoffError as exc:
        return [], st.ADAPTER_ERROR, str(exc)
    except Exception:
        return [], st.ADAPTER_ERROR, "gt_handoff_unreadable"
    if env["collection"] is None:
        return [], st.FETCH_FAILURE, "collection_not_attested"
    objection = attempts.verdict(env["collection"], now=now, cron_utc=CRON_UTC,
                                 grace_hours=GRACE_HOURS, require_attestation=True)
    if objection is not None:
        return [], objection[0], objection[1]
    return list(env["records"]), None, None


# ── private side: collect ─────────────────────────────────────────────────────

def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(CAPTURE_SCHEMA)
    return conn


def _write_capture(captures: Path, sha: str, wire: bytes) -> None:
    """Content-addressed; an existing file must already hold these bytes."""
    if hashlib.sha256(wire).hexdigest() != sha:
        raise HandoffError("capture_digest_mismatch")
    path = captures / (sha + ".bin")
    if path.exists():
        if path.read_bytes() != wire:
            raise HandoffError("capture_file_conflict")
        return
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(wire)
    tmp.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise HandoffError("capture_write_unverified")


def _ledger_name(finished_utc: str, run_id: str) -> str:
    moment = _parse_utc(finished_utc)
    return "%s-%s.json" % (moment.strftime("%Y%m%dT%H%M%SZ"), run_id)


def _write_ledger(entry: dict, state: Path) -> Path:
    path = state / "ledger" / _ledger_name(entry["finished_utc"], entry["run_id"])
    path.write_text(json.dumps(entry, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


def _finish(entry: dict, state: Path, skeleton: Optional[Path] = None) -> int:
    """Write the ledger and the exit receipt; return the exit status."""
    entry["finished_utc"] = _stamp(_utc_now())
    exit_status = 0 if entry["health"] in ("ok", "partial", "skipped") else 1
    healthy = entry["result"] in st.SUCCESS_STATUSES and entry["health"] in ("ok", "partial")
    clock_path = state / "clock.json"
    if healthy and not clock_path.exists():
        clock_path.write_text(json.dumps(
            {"day_zero_utc": entry["finished_utc"],
             "day_zero_run_id": entry["run_id"]}, indent=1) + "\n", encoding="utf-8")
    final = _write_ledger(entry, state)
    if skeleton is not None and skeleton != final:
        skeleton.unlink(missing_ok=True)
    (state / "private_attempts" / (entry["run_id"] + ".json")).write_text(
        json.dumps({"run_id": entry["run_id"], "collector_exit_status": exit_status},
                   sort_keys=True) + "\n", encoding="utf-8")
    return exit_status


def _observe(scraper, url: str, conn, captures: Path, run_id: str,
             commit: str, entry: dict) -> None:
    """Fetch, parse and record one listed article; counts into ``entry``."""
    if source_identity(url) is None:
        entry["non_canonical"] += 1
        return
    html = scraper.fetch(url)
    if not html:
        entry["fetch_failures"] += 1
        return
    wire = scraper._captured.get(url, (None, None))[0]
    if wire is None:
        entry["fetch_failures"] += 1
        return
    article = scraper.parse_article(url, html)
    if not article:
        entry["not_parsed"] += 1
        return
    custody = article.get("custody") or {}
    sha = hashlib.sha256(wire).hexdigest()
    if custody.get("capture_sha256") != sha or article.get("url") != url:
        raise HandoffError("capture_binding_mismatch")
    held = article.get("text_held")
    raw = public_raw(article)
    if held:
        entry["held"] += 1
    else:
        _write_capture(captures, sha, wire)
    cur = conn.execute(
        "INSERT OR IGNORE INTO capture_versions (source_identity, url,"
        " title_original, text_original, published_date, content_verdict,"
        " text_held, byline, pub_time, content_type, capture_sha256,"
        " content_sha256, fetched_at, source_run, collector_commit)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (source_identity(url), url, raw["title_original"],
         "" if held else raw["text_original"], raw["published_date"],
         raw["content_verdict"], held or None, custody.get("byline"),
         custody.get("pub_time"), custody.get("content_type"), sha,
         content_sha256(raw), custody.get("fetched_at") or _stamp(_utc_now()),
         run_id, commit))
    entry["observed"] += 1
    if cur.rowcount:
        entry["new_versions"] += 1
    else:
        entry["known_versions"] += 1


def run_collect(state: Path, target: date, target_source: str, run_id: str,
                commit: str, scraper_factory=None) -> int:
    """One collection attempt. Always leaves a ledger and a receipt."""
    from core import china_source_use_hold as hold
    for sub in ("ledger", "captures", "private_attempts"):
        (state / sub).mkdir(parents=True, exist_ok=True)
    entry = {"schema": attempts.SCHEMA, "family": FAMILY, "run_id": run_id,
             "target_date": target.isoformat(), "target_date_source": target_source,
             "window": [(target - timedelta(days=LOOKBACK_DAYS)).isoformat(),
                        target.isoformat()],
             "collector_commit": commit,
             # Initialised as a failure: only a completed attempt can clear it.
             "result": st.ADAPTER_ERROR, "health": "fail",
             "error_detail": "collector_incomplete",
             "discovered": 0, "observed": 0, "new_versions": 0,
             "known_versions": 0, "held": 0, "fetch_failures": 0,
             "not_parsed": 0, "non_canonical": 0, "failed_listing_fetches": 0,
             "finished_utc": _stamp(_utc_now())}
    # Persisted before any request: an attempt killed mid-run still leaves a
    # well-formed failed ledger for the custody commit to attest.
    skeleton = _write_ledger(entry, state)
    if hold.is_held_source(FAMILY):
        # Mirror of the public hold: no publisher request at all.
        entry.update(result=st.SKIPPED_DISABLED, health="skipped",
                     error_detail="source_use_hold")
        return _finish(entry, state, skeleton)
    conn = None
    try:
        if scraper_factory is None:
            from scraper.sources.global_times_mil import GlobalTimesMilScraper
            scraper_factory = GlobalTimesMilScraper
        scraper = scraper_factory(target_date=target, lookback_days=LOOKBACK_DAYS)
        urls = scraper.get_article_urls()
        entry["discovered"] = len(urls)
        entry["failed_listing_fetches"] = len(getattr(scraper, "failed_fetches", []))
        conn = _connect(state / "shadow.db")
        for url in urls:
            _observe(scraper, url, conn, state / "captures", run_id, commit, entry)
        conn.commit()
        gaps = entry["fetch_failures"] + entry["not_parsed"] + entry["non_canonical"]
        if not urls and entry["failed_listing_fetches"]:
            entry.update(result=st.LISTING_FAILURE, health="fail",
                         error_detail="listing_unreachable")
        elif not urls:
            entry.update(result=st.OK_NO_PUBLICATIONS, health="ok", error_detail=None)
        elif not entry["observed"]:
            if entry["fetch_failures"]:
                entry.update(result=st.FETCH_FAILURE, health="fail",
                             error_detail="no_article_retrieved")
            else:
                entry.update(result=st.EXTRACTION_FAILURE, health="fail",
                             error_detail="no_article_parsed")
        else:
            result = st.OK if entry["new_versions"] else st.OK_ALL_DUPLICATES
            entry.update(result=result, health="partial" if gaps else "ok",
                         error_detail="incomplete_window" if gaps else None)
    except HandoffError as exc:
        entry.update(result=st.STORAGE_FAILURE, health="fail", error_detail=str(exc))
    except Exception:
        entry.update(result=st.ADAPTER_ERROR, health="fail",
                     error_detail="collector_raised")
    finally:
        if conn is not None:
            conn.close()
    return _finish(entry, state, skeleton)


# ── private side: verify ──────────────────────────────────────────────────────

def _git(repo, *args) -> bytes:
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, timeout=300).stdout


def decode_capture(wire: bytes, content_type: Optional[str]) -> str:
    """The HTML exactly as the live fetch decoded these bytes."""
    from requests.models import Response
    from requests.structures import CaseInsensitiveDict
    from requests.utils import get_encoding_from_headers
    from scraper.base import _decode_response
    resp = Response()
    resp._content = wire
    resp.status_code = 200
    resp.headers = CaseInsensitiveDict(
        {"Content-Type": content_type} if content_type else {})
    resp.encoding = get_encoding_from_headers(resp.headers)
    return _decode_response(resp)


def reparse(wire: bytes, row) -> Optional[dict]:
    """``parse_article`` on retained bytes, offline; the public raw dict."""
    from scraper.sources.global_times_mil import GlobalTimesMilScraper
    scraper = GlobalTimesMilScraper(
        target_date=date.fromisoformat(row["published_date"]), lookback_days=0)
    article = scraper.parse_article(row["url"], decode_capture(wire, row["content_type"]))
    return public_raw(article) if article else None


def _open_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def verify_clone(clone: Path, expect_head: str, collector_commit: str) -> Optional[str]:
    """None when the committed custody is sound; else a failure code."""
    try:
        if _git(clone, "rev-parse", "HEAD").decode().strip() != expect_head:
            return "head_mismatch"
        _git(clone, "fsck", "--strict")
    except Exception:
        return "git_check_failed"
    state = clone / "state"
    db_path = state / "shadow.db"
    if not db_path.is_file():
        return "custody_db_missing"
    conn = _open_ro(db_path)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            return "custody_db_corrupt"
        rows = conn.execute("SELECT * FROM capture_versions").fetchall()
    except sqlite3.Error:
        return "custody_db_unreadable"
    finally:
        conn.close()
    captures = state / "captures"
    files = {p.name[:-4]: p for p in captures.glob("*.bin")} if captures.is_dir() else {}
    retained = {r["capture_sha256"] for r in rows if r["text_held"] is None}
    for row in rows:
        # Checked first: bytes kept for a held page are the specific failure,
        # not merely an unreferenced file.
        if row["text_held"] is not None and (
                row["capture_sha256"] in files or row["text_original"] != ""):
            return "held_row_retained"
    for sha, path in files.items():
        if not _HEX64.fullmatch(sha) or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            return "capture_digest_mismatch"
        if sha not in retained:
            return "capture_unreferenced"
    for row in rows:
        if source_identity(row["url"]) != row["source_identity"]:
            return "row_identity_mismatch"
        if row["text_held"] is not None:
            continue
        if row["capture_sha256"] not in files:
            return "capture_missing"
        if row["collector_commit"] != collector_commit:
            continue
        try:
            parsed = reparse(files[row["capture_sha256"]].read_bytes(), row)
        except Exception:
            return "reparse_raised"
        if parsed is None or any(parsed[k] != row[k] for k in (
                "title_original", "text_original", "published_date",
                "content_verdict")) or content_sha256(parsed) != row["content_sha256"]:
            return "reparse_mismatch"
    return None


# ── private side: sign ────────────────────────────────────────────────────────

def build_envelope(clone: Path, commit: str, key: str, now: datetime) -> dict:
    """The signed envelope, from the committed clone only; HandoffError otherwise."""
    if not _key_ok(key):
        raise HandoffError("gt_handoff_key_unavailable")
    try:
        if _git(clone, "rev-parse", "HEAD").decode().strip() != commit:
            raise HandoffError("clone_head_mismatch")
        if _git(clone, "status", "--porcelain", "--untracked-files=all").strip():
            raise HandoffError("clone_not_clean")
    except HandoffError:
        raise
    except Exception:
        raise HandoffError("clone_unreadable") from None
    facts = attempts.read_custody(clone, commit, FAMILY,
                                  receipt_dirs=("state/private_attempts",))
    if facts.get("attested") is not True:
        # Nothing committed to attest: publish nothing. The last envelope on
        # the public branch then ages into a staleness verdict.
        raise HandoffError("collection_not_attested")
    db_path = clone / "state" / "shadow.db"
    if not db_path.is_file():
        rows = []
    else:
        conn = _open_ro(db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM capture_versions ORDER BY source_identity,"
                " fetched_at, capture_sha256").fetchall()
        finally:
            conn.close()
    floor = now - RECORD_WINDOW
    latest = {}
    for row in rows:
        fetched = _parse_utc(row["fetched_at"])
        if fetched is None or not (floor <= fetched <= now):
            continue
        current = latest.get(row["source_identity"])
        if current is None or (row["fetched_at"], row["capture_sha256"]) > (
                current["fetched_at"], current["capture_sha256"]):
            latest[row["source_identity"]] = row
    records = []
    for ident in sorted(latest):
        row = latest[ident]
        held = row["text_held"]
        retained = False
        if held is None:
            path = clone / "state" / "captures" / (row["capture_sha256"] + ".bin")
            if not (path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()
                    == row["capture_sha256"]):
                raise HandoffError("capture_not_retained")
            retained = True
        rec = {"url": row["url"], "source_slug": SOURCE_SLUG,
               "title_original": row["title_original"],
               "text_original": "" if held else row["text_original"],
               "published_date": row["published_date"],
               "content_verdict": row["content_verdict"], "text_held": held,
               "source_identity": ident, "capture_sha256": row["capture_sha256"],
               "content_sha256": row["content_sha256"],
               "fetched_at": row["fetched_at"], "source_run": row["source_run"],
               "collector_commit": row["collector_commit"],
               "raw_retained": retained}
        _check_record(rec)
        records.append(rec)
    if len(records) > MAX_RECORDS:
        raise HandoffError("gt_handoff_envelope_too_large")
    env = {"schema": SCHEMA, "family": FAMILY, "custody_ref": CUSTODY_REF,
           "custody_commit": commit, "generated_utc": _stamp(now),
           "collection": facts, "records": records}
    env["mac"] = mac(key, env)
    if len(canonical(env)) > MAX_ENVELOPE_BYTES:
        raise HandoffError("gt_handoff_envelope_too_large")
    verify_envelope(canonical(env), key)   # what the public side will accept
    return env


# ── recovery without a public binding ─────────────────────────────────────────

def recover(public_row: dict, custody_db: Path, captures: Path) -> dict:
    """Tie a public ``articles`` row back to its private capture.

    ``articles.url`` -> ``gt:<id>`` -> ``capture_versions`` (by url) -> retained
    ``.bin`` -> offline ``parse_article`` -> ``normalize_article`` content hash,
    which must equal the public ``articles.content_hash``. Returns
    ``{"status": recovered|held_no_bytes|no_version|no_match, "capture_sha256"}``.
    """
    url = public_row["url"]
    ident = source_identity(url)
    if ident is None:
        return {"status": "no_version", "capture_sha256": None}
    conn = _open_ro(custody_db)
    try:
        rows = conn.execute(
            "SELECT * FROM capture_versions WHERE url = ? AND source_identity = ?"
            " ORDER BY fetched_at, capture_sha256", (url, ident)).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"status": "no_version", "capture_sha256": None}
    for row in rows:
        if row["text_held"] is not None:
            continue
        path = captures / (row["capture_sha256"] + ".bin")
        if not path.is_file():
            continue
        wire = path.read_bytes()
        if hashlib.sha256(wire).hexdigest() != row["capture_sha256"]:
            continue
        parsed = reparse(wire, row)
        if parsed is not None and content_sha256(parsed) == public_row["content_hash"]:
            return {"status": "recovered", "capture_sha256": row["capture_sha256"]}
    if all(r["text_held"] is not None for r in rows):
        return {"status": "held_no_bytes", "capture_sha256": None}
    return {"status": "no_match", "capture_sha256": None}


# ── CLI ──────────────────────────────────────────────────────────────────────

def _cmd_collect(args) -> int:
    from core.shadow_schedule import ScheduleError, resolve_target_date
    m = _RUN.fullmatch(args.run_id or "")
    if not m or m.group(2) != str(args.run_attempt) \
            or not _HEX40.fullmatch(args.commit or ""):
        print("collection refused: run_or_commit_invalid", file=sys.stderr)
        return 2
    try:
        target, source = resolve_target_date(
            _utc_now(), args.event_name, args.cron_utc, args.target_date,
            str(args.run_attempt))
    except ScheduleError:
        print("collection refused: schedule_invalid", file=sys.stderr)
        return 2
    code = run_collect(Path(args.state_dir), target, source, args.run_id, args.commit)
    ledgers = sorted((Path(args.state_dir) / "ledger").glob("*-%s.json" % args.run_id))
    entry = json.loads(ledgers[-1].read_text(encoding="utf-8")) if ledgers else {}
    print(json.dumps({k: entry.get(k) for k in (
        "result", "health", "error_detail", "target_date", "discovered",
        "observed", "new_versions", "known_versions", "held", "fetch_failures",
        "not_parsed", "non_canonical")}, sort_keys=True))
    return code


def _cmd_verify(args) -> int:
    if not (_HEX40.fullmatch(args.expect_head) and _HEX40.fullmatch(args.collector_commit)):
        print("verify: argument_invalid", file=sys.stderr)
        return 1
    failure = verify_clone(Path(args.clone), args.expect_head, args.collector_commit)
    print("verify: %s" % (failure or "ok"))
    return 1 if failure else 0


def _cmd_sign(args) -> int:
    now = _parse_utc(args.now) if args.now else _utc_now()
    if now is None or not _HEX40.fullmatch(args.commit or ""):
        print("sign: argument_invalid", file=sys.stderr)
        return 1
    try:
        env = build_envelope(Path(args.clone), args.commit,
                             os.environ.get(KEY_ENV, ""), now)
    except HandoffError as exc:
        print("sign refused: %s" % exc, file=sys.stderr)
        return 1
    out = Path(args.out)
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(canonical(env))
    tmp.replace(out)
    print("sign: %d record(s)" % len(env["records"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="core.collection.global_times_handoff")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--state-dir", required=True)
    c.add_argument("--run-id", required=True)
    c.add_argument("--run-attempt", required=True)
    c.add_argument("--event-name", required=True)
    c.add_argument("--commit", required=True)
    when = c.add_mutually_exclusive_group(required=True)
    when.add_argument("--cron-utc")
    when.add_argument("--target-date")
    v = sub.add_parser("verify")
    v.add_argument("--clone", required=True)
    v.add_argument("--expect-head", required=True)
    v.add_argument("--collector-commit", required=True)
    s = sub.add_parser("sign")
    s.add_argument("--clone", required=True)
    s.add_argument("--commit", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--now")
    args = ap.parse_args(argv)
    return {"collect": _cmd_collect, "verify": _cmd_verify, "sign": _cmd_sign}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
