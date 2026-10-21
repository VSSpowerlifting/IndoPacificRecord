"""Korea MND processing lane of the shared Daily.

Admitted Korean records (core/korea_corpus_bridge.py) are already rows of the
one `articles` corpus. This lane gives them the shared engine's Korea profile —
relevance, full line-aligned translation, summary and model flag
(analysis/korea_daily.py) — then the automatic QA gate
(processing/korea_translation_qa.py), and writes the result to the same
`articles` columns every desk uses. It is not a second corpus, renderer or
engine: it only selects, pre-checks, dispatches and records.

Properties the pipeline relies on:

  * Separate budget. It runs after the China/Singapore queue with its own cap
    (KOREA_DAILY_PROCESSING_CAP), so Korea can never take a China slot.
  * Free checks first. A record whose stored text or heading no longer matches
    its ledger pin, or that is too large for the translation ceiling, is held
    with a machine reason before any paid call.
  * Exactly once per source version. Only `pending`/`retryable` rows are
    dispatched; a processed, not-relevant, QA-held or paused row is never paid
    for again. A crash between the `articles` write and the ledger write is
    repaired from `articles` on the next run without a call.
  * Isolated failures. One record's failure is recorded against that record
    and the lane continues; only an account-level block stops it.
  * Nothing private in logs: identities and machine codes only, never Korean
    text or model output.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from core import processing_state
from core.korea_corpus_bridge import document_heading
from processing import korea_translation_qa as qa

logger = logging.getLogger(__name__)

# Ledger processing states (migrations/versions/m0016_korea_corpus_admissions).
PENDING, RETRYABLE, QA_HELD = "pending", "retryable", "qa_held"
PROCESSED, NOT_RELEVANT, PAUSED = "processed", "not_relevant", "paused"
DISPATCHABLE = (PENDING, RETRYABLE)

# core.processing_state spells the retry state differently from the ledger.
_LEDGER_STATE = {processing_state.RETRIABLE: RETRYABLE,
                 processing_state.PAUSED: PAUSED}

PIN_TEXT_MISMATCH = "pin_text_mismatch"
PIN_HEADING_MISMATCH = "pin_heading_mismatch"


@dataclass
class LaneReport:
    selected: int = 0
    deferred: int = 0
    processed: list = field(default_factory=list)
    not_relevant: list = field(default_factory=list)
    qa_held: list = field(default_factory=list)       # (identity, reasons)
    retryable: list = field(default_factory=list)     # (identity, reason)
    paused: list = field(default_factory=list)
    repaired: list = field(default_factory=list)
    blocked: Optional[str] = None
    flagged: int = 0


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _table_exists(conn) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='korea_corpus_admissions'").fetchone() is not None


def candidates(conn) -> list[dict]:
    """Admitted, still-dispatchable ledger rows with their corpus row, FIFO.

    First-seen order means a late admission is processed on a later Daily and
    no record is starved by newer ones.
    """
    if not _table_exists(conn):
        return []
    rows = conn.execute(
        "SELECT k.source_identity, k.article_id, k.original_text_sha256, "
        "k.document_heading_sha256, k.processing_state, k.processing_attempts, "
        "a.title_original, a.text_original, a.content_hash, a.analyzed_at, "
        "a.passed_relevance, a.summary_english, a.prompt_version "
        "FROM korea_corpus_admissions k JOIN articles a ON a.id = k.article_id "
        "WHERE k.state = 'admitted' AND k.processing_state IN (?, ?) "
        "ORDER BY k.first_seen_at_utc, k.source_identity", DISPATCHABLE
    ).fetchall()
    return [dict(r) for r in rows]


def pin_hold(row: dict) -> Optional[str]:
    """A reason the stored corpus row no longer matches its ledger pin."""
    text = row.get("text_original") or ""
    pin = row["original_text_sha256"]
    if _sha(text) != pin or row.get("content_hash") != pin:
        return PIN_TEXT_MISMATCH
    found = document_heading(text)
    if (found is None or _sha(found[1]) != row["document_heading_sha256"]
            or row.get("title_original") != found[1]):
        return PIN_HEADING_MISMATCH
    return None


def _set_ledger(conn, identity: str, expected: str, state: str, *,
                attempts: Optional[int] = None, reason: Optional[str] = None,
                versions: Optional[dict] = None) -> bool:
    """Conditional on the row still being admitted and in `expected`."""
    from core.processing_state import now_utc
    versions = versions or {}
    cur = conn.execute(
        "UPDATE korea_corpus_admissions SET processing_state = ?, "
        "processing_attempts = COALESCE(?, processing_attempts), "
        "processing_reason = ?, qa_version = COALESCE(?, qa_version), "
        "glossary_version = COALESCE(?, glossary_version), "
        "prompt_version = COALESCE(?, prompt_version), updated_at_utc = ? "
        "WHERE source_identity = ? AND state = 'admitted' "
        "AND processing_state = ?",
        (state, attempts, reason, versions.get("qa_version"),
         versions.get("glossary_version"), versions.get("prompt_version"),
         now_utc(), identity, expected))
    return cur.rowcount == 1


def _versions(result: Optional[dict]) -> dict:
    return {"qa_version": qa.QA_VERSION,
            "glossary_version": qa.glossary_version(),
            "prompt_version": (result or {}).get("prompt_version")}


def run(analyzer, *, cap: int, db, profile=None,
        max_output_tokens: Optional[int] = None,
        fatal_error: type = Exception) -> LaneReport:
    """Process up to `cap` dispatchable Korean records. Never raises for a
    per-record failure; an account-level block is returned in `blocked`.

    `db` is storage.db (its get_conn and article writers). `fatal_error` is
    the analyzer's FatalAPIError.
    """
    from config import TRANSLATION_MAX_TOKENS
    from processing.screening import KOREA_PROFILE
    profile = profile or KOREA_PROFILE
    ceiling = max_output_tokens or TRANSLATION_MAX_TOKENS
    report = LaneReport()

    with db.get_conn() as conn:
        rows = candidates(conn)
        dispatch = []
        for row in rows:
            ident, state = row["source_identity"], row["processing_state"]
            # Repair a crash between the articles write and the ledger write:
            # the corpus row already carries the outcome, so no call is due.
            if row.get("analyzed_at") and (row.get("summary_english") or "").strip():
                if _set_ledger(conn, ident, state, PROCESSED, reason=None,
                               versions={"qa_version": qa.QA_VERSION,
                                         "glossary_version": qa.glossary_version(),
                                         "prompt_version": row.get("prompt_version")}):
                    report.repaired.append(ident)
                continue
            if row.get("passed_relevance") == 0:
                if _set_ledger(conn, ident, state, NOT_RELEVANT, reason=None):
                    report.repaired.append(ident)
                continue
            hold = pin_hold(row) or qa.dispatch_hold(
                row["text_original"], max_output_tokens=ceiling)
            if hold:
                if _set_ledger(conn, ident, state, QA_HELD, reason=hold,
                               versions=_versions(None)):
                    report.qa_held.append((ident, hold))
                continue
            dispatch.append(row)
        conn.commit()

    report.selected = min(len(dispatch), max(cap, 0))
    report.deferred = len(dispatch) - report.selected

    for row in dispatch[:report.selected]:
        ident, state = row["source_identity"], row["processing_state"]
        aid, body = row["article_id"], row["text_original"]
        attempts_before = row["processing_attempts"] or 0
        try:
            result = analyzer.analyze_record(row["title_original"], body, profile)
        except fatal_error as exc:
            report.blocked = type(exc).__name__
            break
        except Exception as exc:  # noqa: BLE001 — isolate one record
            logger.error("Korea lane: %s raised %s", ident, type(exc).__name__)
            result = None

        if result is None or (result.get("passed_relevance")
                              and "translation_qa" not in result
                              and not (result.get("summary_english") or "").strip()):
            failure = (processing_state.ANALYSIS_FAILED if result is None
                       else processing_state.ANALYSIS_INCOMPLETE)
            disp = processing_state.classify(
                attempts_before=attempts_before, has_body=bool(body.strip()),
                failure=failure)
            ledger_state = _LEDGER_STATE[disp.state]   # never terminal here
            db.record_processing_failure(aid, disp)
            with db.get_conn() as conn:
                _set_ledger(conn, ident, state, ledger_state,
                            attempts=disp.attempts, reason=disp.reason,
                            versions=_versions(result))
            (report.paused if ledger_state == PAUSED
             else report.retryable).append((ident, disp.reason))
            continue

        if not result["passed_relevance"]:
            db.update_relevance(aid, score=result["relevance_score"],
                                reasoning=result["relevance_reasoning"],
                                passed=False)
            with db.get_conn() as conn:
                _set_ledger(conn, ident, state, NOT_RELEVANT, reason=None,
                            attempts=attempts_before + 1,
                            versions=_versions(result))
            report.not_relevant.append(ident)
            continue

        checked = result.get("translation_qa")
        if checked is None:
            checked = qa.check_record(body, result.get("heading_index", -1),
                                      result)
        if not checked.passed:
            reasons = checked.reason_string()
            with db.get_conn() as conn:
                _set_ledger(conn, ident, state, QA_HELD, reason=reasons,
                            attempts=attempts_before + 1,
                            versions=_versions(result))
            report.qa_held.append((ident, reasons))
            continue

        db.update_relevance(aid, score=result["relevance_score"],
                            reasoning=result["relevance_reasoning"], passed=True)
        db.update_analysis(
            article_id=aid,
            title_english=result["title_english"],
            text_english=result["text_english"],
            summary_english=result["summary_english"],
            is_significant=result["is_significant"],
            significance_reasoning=result.get("significance_reasoning"),
            categories=[],
            model_id=result["model_id"],
            prompt_version=result["prompt_version"],
        )
        db.clear_processing_failure(aid)
        with db.get_conn() as conn:
            _set_ledger(conn, ident, state, PROCESSED, reason=None,
                        attempts=attempts_before + 1,
                        versions=_versions(result))
        report.processed.append(ident)
        report.flagged += bool(result["is_significant"])

    _log(report)
    return report


def _log(report: LaneReport) -> None:
    logger.info(
        "Korea lane: %d dispatched (%d deferred by cap), %d processed "
        "(%d model-flagged), %d not relevant, %d QA-held, %d retryable, "
        "%d paused, %d repaired without a call%s",
        report.selected, report.deferred, len(report.processed), report.flagged,
        len(report.not_relevant), len(report.qa_held), len(report.retryable),
        len(report.paused), len(report.repaired),
        "; stopped: account-level block" if report.blocked else "")
    for ident, reasons in report.qa_held:
        logger.warning("Korea lane QA hold: %s %s", ident, reasons)
    for ident, reason in report.retryable + report.paused:
        logger.warning("Korea lane failure: %s %s", ident, reason)
