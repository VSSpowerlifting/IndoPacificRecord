#!/usr/bin/env python3
"""Title-only China completion. Default is read-only, no API (including probes).

Execute only after separate paid-run authorization. Each invocation is bounded;
rerun the same command to resume. Successful titles and in-flight claims skip.
"""
import argparse
from collections import Counter
import json
import logging
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DB_PATH, ANALYSIS_MODEL
from core.title_translation import (MAX_TOKENS, SYSTEM, TOOL, title_hash,
                                    valid_english, english_title)
from core.processing_state import RETRY_BUDGET
from scripts.reconcile_db import read_only
from scripts.spend_guard import estimate_cost_usd, preflight
from storage.title_translation import candidates, needed, ready, run_batch, resume


def estimate(rows):
    # One token per character, including all serialized prompt/tool bytes;
    # 256 extra input tokens per call for framing. No cache discount assumed.
    chars = sum(len(json.dumps({"headline": r["title_original"]}, ensure_ascii=False))
                + len(SYSTEM) + len(json.dumps(TOOL)) + 256 for r in rows)
    ratio = len(rows) * MAX_TOKENS / chars if chars else 0
    return estimate_cost_usd(chars, ANALYSIS_MODEL, ratio), chars, ratio


def report(rows, limit):
    counts = Counter()
    for r in rows:
        state = ("awaiting_screening" if r["passed_relevance"] is None else
                 "not_selected" if not r["passed_relevance"] else
                 "analyzed" if r["analyzed_at"] else "analysis_incomplete")
        value = r["title_english"]
        if (r["language_tag"] or "").startswith("en"):
            kind = ("english_original_invalid_stored" if value and value.strip()
                    and not valid_english(value) else "english_original")
        elif (r.get("title_translation_source_sha256") and
              r["title_translation_source_sha256"] != title_hash(r["title_original"] or "")
              and not english_title(r)):
            kind = "stale"
        elif value is None:
            kind = "missing"
        elif not value.strip():
            kind = "blank"
        elif not valid_english(value):
            kind = "invalid"
        else:
            kind = "stored_valid"
        counts[(state, kind)] += 1
    work = [r for r in rows if ready(r)]
    batch = work[:limit]
    total_est, _, _ = estimate(work)
    batch_est, _, _ = estimate(batch)
    return {"model": ANALYSIS_MODEL, "public_china_records": len(rows),
            "counts": [{"state": s, "title": k, "count": n}
                       for (s, k), n in sorted(counts.items())],
            "needs_translation": sum(needed(r) for r in rows),
            "eligible_now": len(work), "batch_count": len(batch),
            "all_one_pass_estimate_usd": round(total_est["total_usd"], 6),
            "batch_estimate": batch_est,
            "five_attempt_estimate_usd": round(total_est["total_usd"] * RETRY_BUDGET, 6)}, batch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true", help="Default; no API or database writes")
    ap.add_argument("--execute", action="store_true", help="Paid title-only calls and database writes")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--resume-id", type=int, help="Explicitly reset only this title's exhausted retry budget")
    args = ap.parse_args(argv)
    if args.limit < 1 or args.limit > 200:
        ap.error("--limit must be between 1 and 200")
    if args.dry_run and args.execute:
        ap.error("choose --dry-run or --execute")
    with read_only(str(args.db)) as conn:
        rows = candidates(conn)
        if args.resume_id is not None:
            rows = [dict(r, title_translation_attempts=0) for r in rows if r['id'] == args.resume_id]
        receipt, batch = report(rows, args.limit)
    print(json.dumps(receipt, indent=2))
    if not args.execute or not batch:
        return 0
    # Refuse before even an API-access probe when the bounded estimate has not
    # been acknowledged. Reuse the existing spending guard/table/probe.
    if not args.confirm_spend:
        ap.error("--execute requires --confirm-spend after reviewing the dry-run estimate")
    est, chars, ratio = estimate(batch)
    if not preflight([("title-only", chars, ANALYSIS_MODEL, ratio)], len(batch), True):
        return 2
    from analysis.analyzer import Analyzer, FatalAPIError
    from migrations.versions.m0011_china_title_translation import up
    analyzer = Analyzer()
    conn = sqlite3.connect(args.db)
    try:
        up(conn)
        conn.commit()
        if args.resume_id is not None and not resume(conn, batch[0]):
            return 1
        result = run_batch(conn, analyzer, batch, ANALYSIS_MODEL)
        print(json.dumps({"result": result, "usage": analyzer.usage.rows()}))
        return 1 if result["failed"] else 0
    except FatalAPIError:
        logging.error("Account blocked; stopping title-only work")
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
