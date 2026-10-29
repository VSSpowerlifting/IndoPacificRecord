#!/usr/bin/env python3
"""Bounded, opt-in A/B experiment; never connected to IPR Daily or publishing.

Input: JSONL with id, title_en, body_en from approved frozen evaluation data.
Output: private JSON with baseline and folded outputs for blinded review.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from analysis.analyzer import Analyzer
from analysis.china_fold_experiment import (
    COMBINED_MAX_TOKENS, build_combined_messages, run_combined,
)
from analysis.prompts import build_category_messages, build_summary_messages
from analysis.pricing import PRICING_USD_PER_MTOK
from analysis.usage import build_run_record
from config import ANALYSIS_MODEL, RELEVANCE_MODEL

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_INPUT_CHARS = 16000


def load_cases(path, limit):
    cases = []
    ids = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if type(row) is not dict or not all(
                    type(row.get(k)) is str and row[k].strip()
                    for k in ("id", "title_en", "body_en")):
                raise ValueError("Every case needs string id, title_en, body_en")
            if row["id"] in ids:
                raise ValueError("Duplicate evaluation record id")
            if len(row["title_en"]) + len(row["body_en"]) > MAX_INPUT_CHARS:
                raise ValueError("Input exceeds bounded 16,000-character limit")
            cases.append({k: row[k] for k in ("id", "title_en", "body_en")})
            ids.add(row["id"])
            if len(cases) >= limit:
                break
    if not cases:
        raise ValueError("No evaluation cases")
    return cases


def preflight_upper_bound_usd(case):
    """Conservative per-record estimate, NOT a guaranteed provider billing cap.

    UTF-8 byte counts deliberately overestimate typical input tokens; includes
    an allowance for a malformed-summary fallback and request overhead.
    """
    title, body = case["title_en"], case["body_en"]
    prompts = [
        build_summary_messages(title, body),
        build_category_messages(title, body),
        build_combined_messages(title, body),
        build_summary_messages(title, body),  # optional malformed-JSON retry
    ]
    system_bytes = sum(len(block["text"].encode("utf-8"))
                       for block in Analyzer._SYSTEM_WITH_CACHE)
    input_bound = sum(
        len(json.dumps(msg, ensure_ascii=False).encode("utf-8")) + system_bytes + 2000
        for msg in prompts
    )
    output_bound = 1000 + 500 + COMBINED_MAX_TOKENS + 1000
    rate = PRICING_USD_PER_MTOK.get(ANALYSIS_MODEL)
    if rate is None:
        raise ValueError("Unpriced model: cannot enforce pilot preflight")
    return (input_bound * rate["input"] * 1.25
            + output_bound * rate["output"]) / 1000000


def current_spend(analyzers):
    total = 0.0
    unpriced = []
    for analyzer in analyzers:
        record = build_run_record(
            analyzer.usage,
            run_date=datetime.now(timezone.utc).date().isoformat(),
            recorded_at=datetime.now(timezone.utc).isoformat(),
            run_status="local_experiment",
            analysis_model=ANALYSIS_MODEL, relevance_model=RELEVANCE_MODEL,
            articles_queued=0, articles_fully_analyzed=0,
        )
        total += record["estimated_cost_usd"]
        unpriced.extend(record["unpriced_models"])
    if unpriced:
        raise ValueError("Unpriced response; abort instead of undercounting spend")
    return round(total, 6)


def write_private(path, report):
    # Never write evaluation source text or model outputs into the public repo.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-records", type=int, default=20)
    parser.add_argument("--max-estimated-spend-usd", type=float, default=3.0)
    parser.add_argument("--execute", action="store_true",
                        help="Explicitly authorize paid requests")
    parser.add_argument("--confirm-model-rights", action="store_true",
                        help="Confirm samples are authorized for provider processing")
    args = parser.parse_args()
    if not 1 <= args.max_records <= 30:
        parser.error("--max-records must be 1..30")
    if not 0 < args.max_estimated_spend_usd <= 3:
        parser.error("Pilot budget must be greater than $0 and no more than $3")
    cases = load_cases(args.input, args.max_records)
    bounds = [preflight_upper_bound_usd(c) for c in cases]
    print("Cases:", len(cases), "model:", ANALYSIS_MODEL,
          "conservative preflight estimate USD:", round(sum(bounds), 4))
    if not args.execute:
        print("DRY RUN ONLY: no paid calls, output files, or publication writes.")
        return 0
    if not args.confirm_model_rights or args.output is None:
        parser.error("--execute requires --confirm-model-rights and --output")
    output = args.output.resolve()
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        parser.error("Private evaluation output must be outside the public repository")
    if output.exists():
        parser.error("Output already exists: use a new private path")
    baseline, folded = Analyzer(), Analyzer()
    report = {
        "experiment": "china_summary_category_fold_v1",
        "model": ANALYSIS_MODEL,
        "cases": [],
        "status": "incomplete",
        "baseline_cost_usd": 0.0,
        "combined_cost_usd": 0.0,
        "estimated_spend_usd": 0.0,
        "quality_review_status": "not_reviewed",
        "note": "Cost is estimated from API usage; quality needs independent review.",
    }
    spent = 0.0
    try:
        for case, upper_bound in zip(cases, bounds):
            if spent + upper_bound > args.max_estimated_spend_usd:
                report["status"] = "budget_preflight_stop"
                break
            item = {"id": case["id"]}
            try:
                summary = baseline.summarize(case["title_en"], case["body_en"])
                categories, flag, reason = baseline.categorize(
                    case["title_en"], case["body_en"])
                item["baseline"] = {
                    "summary": summary, "categories": categories,
                    "significance": flag, "significance_reason": reason,
                }
                item["combined"] = run_combined(
                    folded, case["title_en"], case["body_en"])
            except Exception as exc:
                # Do not log raw output or source text in error reports.
                item["error_type"] = type(exc).__name__
            report["cases"].append(item)
            base_cost = current_spend([baseline])
            fold_cost = current_spend([folded])
            spent = round(base_cost + fold_cost, 6)
            report["baseline_cost_usd"] = base_cost
            report["combined_cost_usd"] = fold_cost
            report["estimated_spend_usd"] = spent
            write_private(output, report)
        else:
            report["status"] = "complete"
    finally:
        write_private(output, report)
    print("Status:", report["status"], "USD estimated:", spent,
          "cases completed:", len(report["cases"]))
    print("Private report:", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
