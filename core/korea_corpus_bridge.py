"""Governed bridge from released Korean MND originals into the shared corpus.

The bridge is the only writer of Korean MND rows in `articles`. It crawls
nothing and reads no private package: its inputs are the already-public,
SHA-pinned KOGL Type 1 release index (core.korea_published_originals) and the
production metadata admission in `korea_official_source_records`. A record is
admitted only when both agree on identity, official URL, posting date and
original-text digest, the record is MND (never DAPA), and it is not one of
the excluded identities.

Rights authority: permission to carry the original text comes only from the
release-index row itself — its KOGL Type 1 release decision and policy digests
(`release_decision_sha256`, `policy_sha256`), which are pinned in the ledger.
The metadata row's `public_scope == 'official_link_only'` is an identity
cross-check (the same record was admitted as an official link), not a text
licence; a mismatch is held as `korea_metadata_scope_mismatch`.

Excluded identities:

  * the 14 frozen historical references (scripts.admit_korea_standing_original_texts.baseline);
  * the standing research hold (core.korea_private_research_candidates.HOLD_NEWS_IDS);
  * any identity with a reviewed English release or an owner English draft
    handoff, so a reviewed page never gets a competing machine version.

`title_original` is the document's own heading line in the released text, not
the private portal listing title, which has no public release. The heading is
the first line after the `배포` distribution timestamp; if that structure is
absent the record is held, never guessed.

Exactly once per source version: `korea_corpus_admissions` (migration 0015)
pins each admitted identity to its text, release-decision and policy digests.
A replay writes nothing. A later change to an admitted source (digest drift,
removal from the release index, revoked release) withdraws the record from
rendering rather than overwriting it. Hold reasons are fixed machine codes;
no Korean text is ever logged or written to a receipt.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from core.korea_published_originals import (
    INDEX, ORIGINAL_DIR, read_release_index,
)

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_VERSION = "kr-corpus-bridge-v1"
SOURCE_SLUG = "kr_policy_mnd_releases"
DESK_ID = "korea"
ENGLISH_INDEX = ROOT / "research" / "korea_english_publications.json"
HANDOFF_RECEIPTS = ROOT / "research" / "korea_english_draft_handoff_receipts.json"
MAX_ADMISSIONS_PER_RUN = 10
HEADING_SEARCH_LINES = 12
HEADING_MAX_CHARS = 200

_DIST_LABEL = "배포"
_TIMESTAMP = re.compile(
    r"(?:19|20)[0-9]{2}\.\s*[0-9]{1,2}\.\s*[0-9]{1,2}\.\s*"
    r"\([월화수목금토일]\)\s*[0-9]{1,2}:[0-9]{2}\Z")
_HANGUL = re.compile(r"[가-힣]")
_NOT_HEADING = ("-", "□", "○", "※", "▲", "◆", "■", "*", "<", "[")
_IDENTITY = re.compile(r"korea-policy:[0-9]{9}\Z")


class BridgeHold(ValueError):
    """Whole-run refusal. Static machine codes only, never source content."""


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise BridgeHold(reason)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Every Korea consumer splits a released text the same way: the bridge's
# heading index, the line-numbered translation payload, the QA gate and the
# benchmark. Plain "\n" only. str.splitlines() also breaks on \r, \x0b, \x85,
# \u2028 and others, which would silently shift line numbers between those
# consumers, so a text containing one is refused rather than guessed at.
_OTHER_SEPARATORS = re.compile("[\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029]")


def source_lines(text: str):
    """The document's lines (0-based list), or None for unsupported breaks."""
    if not isinstance(text, str) or _OTHER_SEPARATORS.search(text):
        return None
    return text.split("\n")


def document_heading(text: str):
    """(line_index, heading) of the released document, or None.

    Anchored on the exact `배포` label, not the first timestamp: the 보도시점
    embargo line can carry its own timestamp (e.g. 156785286). The index is
    0-based into source_lines(); translation entries are 1-based (index + 1).
    """
    lines = source_lines(text)
    if lines is None:
        return None
    window = [line.strip() for line in lines[:HEADING_SEARCH_LINES]]
    try:
        label = window.index(_DIST_LABEL)
    except ValueError:
        return None
    if label + 1 >= len(window) or not _TIMESTAMP.fullmatch(window[label + 1]):
        return None
    for idx in range(label + 2, len(window)):
        line = window[idx]
        if not line:
            continue
        if (line.startswith(_NOT_HEADING) or len(line) > HEADING_MAX_CHARS
                or not _HANGUL.search(line)):
            return None
        return idx, line
    return None


# ── excluded identities ───────────────────────────────────────────────────────

def _english_identities(english_index: Path, handoff: Path) -> set:
    """Reviewed English releases plus owner handoffs. Unreadable → refuse."""
    found = set()
    for path, key in ((english_index, "releases"), (handoff, "delivered")):
        _require(path.is_file() and not path.is_symlink(),
                 "korea_english_registry_unavailable")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise BridgeHold("korea_english_registry_invalid") from None
        rows = payload.get(key) if isinstance(payload, dict) else None
        _require(isinstance(rows, list), "korea_english_registry_invalid")
        for row in rows:
            ident = row.get("source_identity") if isinstance(row, dict) else None
            _require(isinstance(ident, str), "korea_english_registry_invalid")
            found.add(ident)
    return found


def excluded_identities(*, english_index: Path = ENGLISH_INDEX,
                        handoff: Path = HANDOFF_RECEIPTS,
                        frozen: Optional[Iterable[str]] = None) -> Dict[str, str]:
    """{identity: exclusion code}; never bridged, never ledgered."""
    from core.korea_private_research_candidates import HOLD_NEWS_IDS
    if frozen is None:
        from scripts.admit_korea_standing_original_texts import baseline
        frozen = baseline()
    out = {ident: "excluded_frozen_baseline" for ident in frozen}
    for ident in _english_identities(english_index, handoff):
        out.setdefault(ident, "excluded_reviewed_english")
    for news_id in HOLD_NEWS_IDS:
        out["korea-policy:" + news_id] = "excluded_research_hold"
    return out


# ── activation gates ──────────────────────────────────────────────────────────

def source_row(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT id, desk_id, enabled, access_method FROM sources WHERE slug=?",
        (SOURCE_SLUG,)).fetchone()


def check_gates(conn: sqlite3.Connection, *, registry=None) -> int:
    """Return the source id, or refuse unless the Korea desk is activated.

    Activation is the owner-approved desks/korea manifest (synced into
    `sources` by the migration runner) plus a live registry entry. Neither
    exists before the activation change, so the bridge cannot write.
    """
    _require(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='korea_corpus_admissions'").fetchone() is not None,
        "korea_corpus_ledger_missing")
    row = source_row(conn)
    _require(row is not None, "korea_source_not_registered")
    _require(row[1] == DESK_ID and row[2] == 1 and row[3] == "manual",
             "korea_source_not_activated")
    if registry is None:
        from core.desk_registry import get_desk_registry
        registry = get_desk_registry()
    entry = registry.get(DESK_ID)
    _require(entry is not None and entry.status == "live"
             and bool(entry.manifest_path), "korea_desk_not_live")
    return row[0]


# ── planning ──────────────────────────────────────────────────────────────────

def _db_records(conn: sqlite3.Connection) -> Dict[str, sqlite3.Row]:
    cur = conn.execute(
        "SELECT source_identity, canonical_official_url, publisher_posted_date, "
        "original_text_sha256, official_issuer, public_scope "
        "FROM korea_official_source_records")
    cols = [c[0] for c in cur.description]
    return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}


def _ledger(conn: sqlite3.Connection) -> Dict[str, dict]:
    cur = conn.execute("SELECT * FROM korea_corpus_admissions")
    cols = [c[0] for c in cur.description]
    return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}


def _candidate_hold(rec: dict, db: Optional[dict]) -> Optional[str]:
    if db is None:
        return "korea_metadata_admission_missing"
    if db["official_issuer"] != "kr_mnd":
        return "korea_issuer_not_mnd"
    if db["public_scope"] != "official_link_only":
        return "korea_metadata_scope_mismatch"
    if db["canonical_official_url"] != rec["official_url"]:
        return "korea_official_url_mismatch"
    if db["publisher_posted_date"] != rec["publisher_posted_date"]:
        return "korea_posted_date_mismatch"
    if db["original_text_sha256"] != rec["original_text_sha256"]:
        return "korea_original_text_digest_mismatch"
    if document_heading(rec["text_original"]) is None:
        return "korea_heading_unidentifiable"
    return None


def plan(conn: sqlite3.Connection, *, index=INDEX, original_dir=ORIGINAL_DIR,
         excluded: Optional[Dict[str, str]] = None) -> List[dict]:
    """Pure decision list. Reads only; the index failing closed raises."""
    released = read_release_index(index=index, original_dir=original_dir)
    if excluded is None:
        excluded = excluded_identities()
    db = _db_records(conn)
    ledger = _ledger(conn)
    by_id = {r["source_identity"]: r for r in released}
    decisions = []

    for ident, row in sorted(ledger.items()):
        if row["state"] != "admitted":
            continue
        rec, meta = by_id.get(ident), db.get(ident)
        reason = None
        if rec is None:
            reason = "source_withdrawn_from_release_index"
        elif meta is None or meta["public_scope"] != "official_link_only":
            reason = "source_release_revoked"
        elif (rec["original_text_sha256"] != row["original_text_sha256"]
              or meta["original_text_sha256"] != row["original_text_sha256"]
              or rec["release_decision_sha256"] != row["release_decision_sha256"]
              or rec["policy_sha256"] != row["policy_sha256"]):
            reason = "source_version_changed"
        elif _sha(rec["text_original"]) != row["original_text_sha256"]:
            reason = "source_version_changed"
        decisions.append({"source_identity": ident,
                          "action": "withdraw" if reason else "unchanged",
                          "reason": reason, "article_id": row["article_id"]})

    for rec in sorted(released, key=lambda r: r["source_identity"]):
        ident = rec["source_identity"]
        prior = ledger.get(ident)
        if prior is not None and prior["state"] in ("admitted", "withdrawn"):
            continue
        if ident in excluded:
            decisions.append({"source_identity": ident, "action": "excluded",
                              "reason": excluded[ident]})
            continue
        if not _IDENTITY.fullmatch(ident):
            decisions.append({"source_identity": ident, "action": "excluded",
                              "reason": "excluded_not_mnd_identity"})
            continue
        reason = _candidate_hold(rec, db.get(ident))
        decision = {"source_identity": ident,
                    "action": "hold" if reason else "admit",
                    "reason": reason, "_record": rec}
        decisions.append(decision)
    return decisions


# ── applying ──────────────────────────────────────────────────────────────────

def _ledger_values(rec: dict, now: str) -> dict:
    found = document_heading(rec["text_original"])
    return {
        "source_identity": rec["source_identity"],
        "canonical_official_url": rec["official_url"],
        "publisher_posted_date": rec["publisher_posted_date"],
        "original_text_sha256": rec["original_text_sha256"],
        "document_heading_sha256": _sha(found[1]) if found else None,
        "release_decision_sha256": rec["release_decision_sha256"],
        "policy_sha256": rec["policy_sha256"],
        "bridge_version": BRIDGE_VERSION,
        "updated_at_utc": now,
    }


def _upsert_hold(conn, rec: dict, reason: str, now: str) -> None:
    vals = _ledger_values(rec, now)
    conn.execute(
        "INSERT INTO korea_corpus_admissions (source_identity, "
        "canonical_official_url, publisher_posted_date, original_text_sha256, "
        "document_heading_sha256, release_decision_sha256, policy_sha256, "
        "bridge_version, state, hold_reason, first_seen_at_utc, updated_at_utc) "
        "VALUES (:source_identity, :canonical_official_url, "
        ":publisher_posted_date, :original_text_sha256, "
        ":document_heading_sha256, :release_decision_sha256, :policy_sha256, "
        ":bridge_version, 'held', :reason, :updated_at_utc, :updated_at_utc) "
        "ON CONFLICT(source_identity) DO UPDATE SET "
        "canonical_official_url=excluded.canonical_official_url, "
        "publisher_posted_date=excluded.publisher_posted_date, "
        "original_text_sha256=excluded.original_text_sha256, "
        "document_heading_sha256=excluded.document_heading_sha256, "
        "release_decision_sha256=excluded.release_decision_sha256, "
        "policy_sha256=excluded.policy_sha256, "
        "bridge_version=excluded.bridge_version, hold_reason=excluded.hold_reason, "
        "updated_at_utc=CASE WHEN korea_corpus_admissions.hold_reason IS "
        "excluded.hold_reason AND korea_corpus_admissions.original_text_sha256 = "
        "excluded.original_text_sha256 THEN korea_corpus_admissions.updated_at_utc "
        "ELSE excluded.updated_at_utc END "
        "WHERE korea_corpus_admissions.state = 'held'",
        {**vals, "reason": reason})


def _admit(conn, rec: dict, source_id: int, run_id: Optional[int], now: str):
    from core.retired_article_urls import is_retired, next_available_article_id
    url = rec["official_url"]
    if is_retired(conn, url):
        return None, "korea_url_retired"
    if conn.execute("SELECT 1 FROM articles WHERE url=?", (url,)).fetchone():
        return None, "korea_url_already_in_corpus"
    _, heading = document_heading(rec["text_original"])
    article_id = next_available_article_id(conn)
    conn.execute(
        "INSERT INTO articles (id, url, content_hash, source_id, scrape_run_id, "
        "title_original, text_original, published_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (article_id, url, rec["original_text_sha256"], source_id, run_id,
         heading, rec["text_original"], rec["publisher_posted_date"]))
    vals = _ledger_values(rec, now)
    conn.execute(
        "INSERT INTO korea_corpus_admissions (source_identity, article_id, "
        "canonical_official_url, publisher_posted_date, original_text_sha256, "
        "document_heading_sha256, release_decision_sha256, policy_sha256, "
        "bridge_version, state, first_seen_at_utc, updated_at_utc) "
        "VALUES (:source_identity, :article_id, :canonical_official_url, "
        ":publisher_posted_date, :original_text_sha256, "
        ":document_heading_sha256, :release_decision_sha256, :policy_sha256, "
        ":bridge_version, 'admitted', :updated_at_utc, :updated_at_utc) "
        "ON CONFLICT(source_identity) DO UPDATE SET "
        "article_id=excluded.article_id, state='admitted', hold_reason=NULL, "
        "original_text_sha256=excluded.original_text_sha256, "
        "document_heading_sha256=excluded.document_heading_sha256, "
        "release_decision_sha256=excluded.release_decision_sha256, "
        "policy_sha256=excluded.policy_sha256, "
        "bridge_version=excluded.bridge_version, "
        "updated_at_utc=excluded.updated_at_utc "
        "WHERE korea_corpus_admissions.state = 'held'",
        {**vals, "article_id": article_id})
    return article_id, None


def apply(conn: sqlite3.Connection, *, run_id: Optional[int] = None,
          index=INDEX, original_dir=ORIGINAL_DIR,
          excluded: Optional[Dict[str, str]] = None, registry=None,
          max_admissions: int = MAX_ADMISSIONS_PER_RUN) -> dict:
    """One all-or-nothing transaction. Returns a receipt with no source text."""
    source_id = check_gates(conn, registry=registry)
    decisions = plan(conn, index=index, original_dir=original_dir,
                     excluded=excluded)
    now = _now()
    receipt = {"bridge_version": BRIDGE_VERSION, "admitted": [], "held": [],
               "withdrawn": [], "excluded": [], "unchanged": [], "deferred": []}
    conn.execute("BEGIN IMMEDIATE")
    try:
        for d in decisions:
            ident, action = d["source_identity"], d["action"]
            if action == "unchanged":
                receipt["unchanged"].append(ident)
            elif action == "excluded":
                receipt["excluded"].append({"source_identity": ident,
                                            "reason": d["reason"]})
            elif action == "withdraw":
                conn.execute(
                    "UPDATE korea_corpus_admissions SET state='withdrawn', "
                    "hold_reason=?, updated_at_utc=? WHERE source_identity=? "
                    "AND state='admitted'", (d["reason"], now, ident))
                receipt["withdrawn"].append({"source_identity": ident,
                                             "article_id": d["article_id"],
                                             "reason": d["reason"]})
            elif action == "hold":
                _upsert_hold(conn, d["_record"], d["reason"], now)
                receipt["held"].append({"source_identity": ident,
                                        "reason": d["reason"]})
            elif action == "admit":
                if len(receipt["admitted"]) >= max_admissions:
                    # Bounded per run; the next Daily continues.
                    receipt["deferred"].append(ident)
                    continue
                article_id, reason = _admit(conn, d["_record"], source_id,
                                            run_id, now)
                if reason:
                    _upsert_hold(conn, d["_record"], reason, now)
                    receipt["held"].append({"source_identity": ident,
                                            "reason": reason})
                else:
                    receipt["admitted"].append({"source_identity": ident,
                                                "article_id": article_id})
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return receipt


def renderable_article_ids(conn: sqlite3.Connection) -> set:
    """Korea corpus rows that may render: admitted and still pinned."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='korea_corpus_admissions'").fetchone() is None:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT article_id FROM korea_corpus_admissions "
        "WHERE state='admitted' AND article_id IS NOT NULL")}


def withdrawn_article_ids(conn: sqlite3.Connection) -> set:
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='korea_corpus_admissions'").fetchone() is None:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT article_id FROM korea_corpus_admissions "
        "WHERE state='withdrawn' AND article_id IS NOT NULL")}
