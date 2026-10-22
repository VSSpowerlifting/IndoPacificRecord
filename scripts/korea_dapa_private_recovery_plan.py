"""Read-only DAPA missed-day recovery plan from restricted private attempt ledgers.

Advisory ONLY: this is not private source authentication, approval to fetch,
a scheduler, or proof of public admission. Missing / failed UTC days require
separate explicit owner collection authorization, one exact day at a time.
Never accepts documents, network credentials, or public production state.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

RUN = re.compile(r"[0-9]{8,20}-[1-9][0-9]{0,5}\Z")
GOOD = {"ok", "ok_no_publications", "ok_all_duplicates"}
DAY_ZERO = date(2026, 10, 16)
MAX_WINDOW = 7


class RecoveryHold(ValueError):
    pass


def plan(state_dir: Path, start: date, end: date, *, as_of: date):
    if (not DAY_ZERO <= start <= end <= as_of or
            (end - start).days >= MAX_WINDOW):
        raise RecoveryHold("DAPA_RECOVERY_WINDOW_INVALID")
    state = Path(state_dir)
    ledger = state / "ledger"
    receipts = state / "private_attempts"
    if (not ledger.is_dir() or ledger.is_symlink() or
            not receipts.is_dir() or receipts.is_symlink()):
        raise RecoveryHold("DAPA_PRIVATE_ATTEMPT_HISTORY_MISSING")
    by_day = {start + timedelta(days=i): []
              for i in range((end - start).days + 1)}
    for path in sorted(ledger.glob("*.json")):
        if path.is_symlink() or path.stat().st_size > 150000:
            raise RecoveryHold("DAPA_PRIVATE_LEDGER_UNTRUSTED")
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError):
            raise RecoveryHold("DAPA_PRIVATE_LEDGER_INVALID") from None
        if type(row) is not dict or row.get("desk") != "korea_dapa":
            raise RecoveryHold("DAPA_PRIVATE_LEDGER_FOREIGN_DESK")
        target = row.get("target_date")
        try:
            day = date.fromisoformat(target)
            if target != day.isoformat():
                raise ValueError()
        except (ValueError, TypeError):
            raise RecoveryHold("DAPA_PRIVATE_LEDGER_DATE_INVALID") from None
        if day not in by_day:
            continue
        run = row.get("run_id")
        if type(run) is not str or not RUN.fullmatch(run):
            raise RecoveryHold("DAPA_PRIVATE_ATTEMPT_ID_INVALID")
        receipt_file = receipts / (run + ".json")
        if receipt_file.is_symlink() or not receipt_file.is_file():
            raise RecoveryHold("DAPA_PRIVATE_ATTEMPT_RECEIPT_MISSING")
        try:
            receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            raise RecoveryHold("DAPA_PRIVATE_ATTEMPT_RECEIPT_INVALID") from None
        if (type(receipt) is not dict or receipt.get("run_attempt") != run
                or type(receipt.get("collector_exit_status")) is not int
                or type(row.get("result")) is not str
                or type(row.get("health")) is not str
                or type(row.get("inserted")) is not int
                or type(row.get("cap")) is not int
                or not 1 <= row["cap"] <= 5
                or row.get("lookback_days") != 0
                or row.get("target_date_source") != "explicit"):
            raise RecoveryHold("DAPA_PRIVATE_ATTEMPT_CONTRACT_INVALID")
        clean = (receipt["collector_exit_status"] == 0
                 and row["result"] in GOOD and row["health"] == "ok")
        if (clean and row["result"] == "ok" and row["inserted"] < 1) or (
                clean and row["result"] != "ok" and row["inserted"] != 0):
            raise RecoveryHold("DAPA_PRIVATE_LEDGER_RESULT_INCONSISTENT")
        by_day[day].append({
            "run_attempt": run,
            "status": "COLLECTED_CLEAN" if clean else "FAILED_REQUIRES_REVIEW",
            "new_originals": row["inserted"] if clean else 0,
        })
    days = []
    for day, attempts in by_day.items():
        if any(x["status"] == "COLLECTED_CLEAN" for x in attempts):
            status = "COLLECTED_CLEAN"
        elif attempts:
            status = "FAILED_REQUIRES_REVIEW"
        else:
            status = "MISSING_REQUIRES_REVIEW"
        days.append({
            "date": day.isoformat(), "status": status, "attempts": attempts,
            "next_step": ("none" if status == "COLLECTED_CLEAN"
                          else "owner_review_then_one_day_authorized_collection"),
        })
    return {
        "schema": "ipr-dapa-private-gap-planner/1",
        "offline_only": True,
        "authentication_or_publication_decision": False,
        "lookback_days": 0,
        "max_one_day_per_manual_action": True,
        "days": days,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--private-state-dir", type=Path, required=True)
    ap.add_argument("--start-date", type=date.fromisoformat, required=True)
    ap.add_argument("--end-date", type=date.fromisoformat, required=True)
    ap.add_argument("--as-of-date", type=date.fromisoformat, default=date.today())
    args = ap.parse_args(argv)
    try:
        print(json.dumps(plan(args.private_state_dir, args.start_date,
                              args.end_date, as_of=args.as_of_date),
                         sort_keys=True, indent=2))
    except RecoveryHold as exc:
        print(json.dumps({"status": "HOLD", "code": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
