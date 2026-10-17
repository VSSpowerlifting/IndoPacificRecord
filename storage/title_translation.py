"""Bounded title-only work using existing articles, client and retry policy.

Connections are supplied explicitly. Callers choose a disposable copy or the
normal pipeline DAO; this module never opens the production database itself.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.processing_state import RETRY_BUDGET, classify, ANALYSIS_FAILED
from core.title_translation import english_title, title_hash, PROMPT_VERSION
from core.retired_article_urls import url_sha256

# Active articles are the public record corpus, unlike official-link references
# and shadow stores. Fail closed without the retirement ledger or desk metadata.
SELECT = """SELECT a.id, a.url, a.source_id, a.title_original, a.title_english,
 a.passed_relevance, a.analyzed_at, a.processing_state,
 s.desk_id, s.language_tag FROM articles a JOIN sources s ON s.id=a.source_id
 WHERE s.desk_id='china' AND s.enabled=1
 AND COALESCE(a.processing_state,'') NOT IN ('paused','terminal','held','private')
 AND NOT EXISTS (SELECT 1 FROM retired_article_urls r
                 WHERE r.original_article_id=a.id OR r.url_sha256=url_sha256(a.url))
 ORDER BY a.id"""


def candidates(conn, article_id=None):
    conn.create_function("url_sha256", 1, url_sha256)
    sql = SELECT
    args = ()
    if article_id is not None:
        sql = sql.replace(" ORDER BY a.id", " AND a.id=? ORDER BY a.id")
        args = (article_id,)
    rows = [dict(zip([c[0] for c in cur.description], row))
            for cur in [conn.execute(sql, args)] for row in cur.fetchall()]
    columns = {r[1] for r in conn.execute("PRAGMA table_info(articles)")}
    if "title_translation_claim" in columns:
        names = sorted(name for name in columns if name.startswith("title_translation_"))
        # Same eligibility restriction: never enumerate private/shadow stores.
        sql = sql.replace(SELECT.split(" FROM articles")[0],
                             "SELECT a.id," + ",".join("a." + n for n in names), 1)
        meta = {r[0]: dict(zip(names, r[1:])) for r in conn.execute(sql, args)}
        for row in rows:
            row.update(meta[row["id"]])
    return rows


def needed(row):
    return (bool((row["title_original"] or "").strip())
            and not english_title(row)
            and not (row.get("language_tag") or "").startswith("en"))


def ready(row):
    if not needed(row):
        return False
    same = row.get("title_translation_attempt_source") == title_hash(row["title_original"])
    if same and (row.get("title_translation_attempts") or 0) >= RETRY_BUDGET:
        return False
    claimed = row.get("title_translation_claimed_at")
    return not (row.get("title_translation_claim") and claimed
                and claimed > (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())


def resume(conn, expected):
    """Explicit reversible retry-budget reset, without changing analysis state."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = next(iter(candidates(conn, expected["id"])), None)
        if (not row or not needed(row) or row["title_original"] != expected["title_original"]
                or row["url"] != expected["url"] or row.get("title_translation_claim")):
            conn.commit()
            return False
        conn.execute("UPDATE articles SET title_translation_attempts=0, "
            "title_translation_state='retriable' WHERE id=?", (row["id"],))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def claim(conn, expected):
    """Reserve before paid dispatch, under SQLite's writer lock."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = next(iter(candidates(conn, expected["id"])), None)
        if (not row or not ready(row) or row["url"] != expected["url"]
                or row["source_id"] != expected["source_id"]
                or row["title_original"] != expected["title_original"]
                or row["title_english"] != expected["title_english"]):
            conn.commit()
            return None
        digest = title_hash(row["title_original"])
        before = 0
        if row.get("title_translation_attempt_source") == digest:
            before = row.get("title_translation_attempts") or 0
        token = uuid4().hex
        conn.execute("UPDATE articles SET title_translation_claim=?, "
            "title_translation_claimed_at=?, title_translation_attempt_source=?, "
            "title_translation_attempts=?, title_translation_state='retriable' WHERE id=?",
            (token, datetime.now(timezone.utc).isoformat(), digest, before + 1, row["id"]))
        conn.commit()
        return dict(row, token=token, attempts=before + 1)
    except Exception:
        conn.rollback()
        raise


def finish(conn, row, title, model):
    """CAS source identity, original bytes, existing title and owned claim."""
    from core.title_translation import valid_english
    if title is not None and not valid_english(title):
        raise ValueError("invalid English headline")
    conn.execute("BEGIN IMMEDIATE")
    try:
        current = next(iter(candidates(conn, row["id"])), None)
        matches = (current and needed(current) and current["url"] == row["url"]
                   and current["source_id"] == row["source_id"]
                   and current["title_original"] == row["title_original"]
                   and current["title_english"] == row["title_english"]
                   and current.get("title_translation_claim") == row["token"])
        if matches and title is not None:
            conn.execute("UPDATE articles SET title_english=?, "
                "title_translation_source_sha256=?, title_translation_model=?, "
                "title_translation_prompt=?, title_translated_at=?, "
                "title_translation_state=NULL WHERE id=?",
                (title, title_hash(row["title_original"]), model, PROMPT_VERSION,
                 datetime.now(timezone.utc).isoformat(), row["id"]))
        elif matches:
            disposition = classify(attempts_before=row["attempts"] - 1,
                                   has_body=True, failure=ANALYSIS_FAILED)
            conn.execute("UPDATE articles SET title_translation_state=? WHERE id=?",
                         (disposition.state, row["id"]))
        conn.execute("UPDATE articles SET title_translation_claim=NULL, "
            "title_translation_claimed_at=NULL WHERE id=? AND title_translation_claim=?",
            (row["id"], row["token"]))
        conn.commit()
        return bool(matches and title is not None)
    except Exception:
        conn.rollback()
        raise


def run_batch(conn, analyzer, rows, model):
    """No body access, screening writes or full-analysis calls."""
    from analysis.analyzer import AnalysisError, FatalAPIError
    result = {"translated": 0, "failed": 0, "skipped": 0}
    for expected in rows:
        row = claim(conn, expected)
        if row is None:
            result["skipped"] += 1
            continue
        try:
            title = analyzer.translate_title(row["title_original"])
        except FatalAPIError:
            finish(conn, row, None, model)
            raise
        except (AnalysisError, ValueError):
            finish(conn, row, None, model)
            result["failed"] += 1
            continue
        if finish(conn, row, title, model):
            result["translated"] += 1
        else:
            result["skipped"] += 1
    return result


def reconcile_titles(conn):
    """Carry successful local receipts to same-title public origin rows only.

    Reconciliation owns published IDs. Never copy claims or overwrite a title
    already present on origin. An old local schema has no new receipts.
    """
    from core.title_translation import english_title
    columns = {r[1] for r in conn.execute("PRAGMA loc.table_info(articles)")}
    if "title_translation_source_sha256" not in columns:
        return
    names = ("title_english", "title_translation_source_sha256",
             "title_translation_model", "title_translation_prompt", "title_translated_at")
    local = {r[0]: r[1:] for r in conn.execute(
        "SELECT url,title_original," + ",".join(names) +
        " FROM loc.articles WHERE title_translation_source_sha256 IS NOT NULL")}
    for row in candidates(conn):
        incoming = local.get(row["url"])
        if not needed(row) or not incoming or incoming[0] != row["title_original"]:
            continue
        candidate = dict(row, **dict(zip(names, incoming[1:])))
        if english_title(candidate):
            conn.execute("UPDATE articles SET " + ",".join(n + "=?" for n in names) +
                         " WHERE id=?", (*incoming[1:], row["id"]))
