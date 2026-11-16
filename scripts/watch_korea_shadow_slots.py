"""Read-only Korea collection-slot watchdog: ledger evidence, NOT source approval.

Inspect metadata from an authenticated, Git-pinned private ledger checkout. A successful
Korea target-date ledger shows an observed collection attempt; it cannot prove
publisher completeness, the Actions attempt census, correct HWPX semantics or
attachment rights. Recovery of source coverage must never be mistaken for a
successful scheduled collection.

An MND run of any origin may record attachment holds: releases whose HWPX the
collector's own byte cap refused, left out of custody. A run that held releases
and stored nothing new is recorded as failed, so holds are read from every
attempt before any health filter. They are reported here as counts and dates
only, warned whenever any ledger in the evaluated window has one, and fail the
check while the latest mature scheduled slot has any. A later clean slot or
clean recovery never proves a held release was collected, so a held date is
never reported as recovered and is never subtracted from the hold report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE
from scripts.run_korea_authenticated_actions_census import pinned_ledger_checkout

SCHEMA = "ipr-korea-readonly-logical-slot-watch/1"
STATE_BRANCH = "archive/korea-policy-briefing"
FIRST_SLOT = date(2026, 10, 7)
EXPECTED_CLOCK_DAY = date(2026, 10, 6)
CRON_HOUR, CRON_MINUTE = 17, 47
GRACE_HOURS = 6
MAX_DAYS = 30
MAX_HOLDS = 40  # the collector's per-run release cap
SUCCESS = frozenset(("ok", "ok_all_duplicates", "ok_no_publications", "ok_all_filtered"))
RUN_ID = re.compile(r"[1-9][0-9]*-1\Z")
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class KoreaWatchHold(ValueError):
    pass


def require(ok, why):
    if not ok:
        raise KoreaWatchHold(why)


def utc(value):
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise KoreaWatchHold("invalid UTC observation") from exc
    else:
        raise KoreaWatchHold("invalid UTC observation")
    require(moment.tzinfo is not None and moment.utcoffset() == timedelta(0),
            "UTC timezone is mandatory")
    return moment.astimezone(timezone.utc)


def day(value):
    require(isinstance(value, str) and DAY.fullmatch(value) is not None,
            "noncanonical target date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise KoreaWatchHold("invalid target date") from exc
    require(parsed.isoformat() == value, "invalid ISO target date")
    return parsed


def attachment_holds(receipt):
    """Releases one run left out of custody. Malformed evidence fails closed."""
    count = receipt.get("attachment_holds", 0)
    items = receipt.get("attachment_hold_items", [])
    require(type(count) is int and 0 <= count <= MAX_HOLDS
            and type(items) is list and len(items) == count
            and all(type(item) is dict and type(item.get("url")) is str and item["url"]
                    for item in items)
            and len({item["url"] for item in items}) == count,
            "malformed Korea attachment-hold evidence")
    return count, {item["url"] for item in items}


def matured_slot(as_of):
    """Latest 17:47 UTC schedule whose 6-hour delayed-run grace has elapsed."""
    moment = utc(as_of) - timedelta(hours=GRACE_HOURS)
    candidate = moment.date()
    if (moment.hour, moment.minute, moment.second) < (CRON_HOUR, CRON_MINUTE, 0):
        candidate -= timedelta(days=1)
    return candidate


def first_window_day(as_of):
    """First target date of the evaluated scheduled window."""
    return max(FIRST_SLOT, matured_slot(as_of) - timedelta(days=MAX_DAYS - 1))


def summarize(ledgers, clock, *, commit, as_of):
    """Distinguish scheduled-run continuity from explicitly recovered coverage."""
    require(isinstance(commit, str) and SHA.fullmatch(commit) is not None,
            "exact Korea state SHA required")
    now = utc(as_of)
    require(type(clock) is dict and clock.get("desk") == "korea"
            and day(utc(clock["day_zero_utc"]).date().isoformat()) == EXPECTED_CLOCK_DAY,
            "unexpected Korea Day 0 clock")
    require(type(ledgers) is list and bool(ledgers) and len(ledgers) <= 70,
            "absent or excessive Korea ledger entries")
    scheduled, recovered = set(), set()
    held_scheduled, held_unscheduled = {}, {}
    held_identities, window_identities = set(), set()
    seen, heldby = set(), {}
    for receipt in ledgers:
        require(type(receipt) is dict and receipt.get("desk") == "korea"
                and type(receipt.get("run_id")) is str
                and receipt["run_id"] not in seen,
                "foreign, duplicate or malformed Korea ledger")
        ident = receipt["run_id"]
        seen.add(ident)
        target = day(receipt.get("target_date"))
        require(target >= EXPECTED_CLOCK_DAY and target <= now.date(),
                "outside supported target-date interval")
        started = utc(receipt.get("started_utc"))
        finished = utc(receipt.get("finished_utc"))
        require(started <= finished and finished <= now + timedelta(minutes=5),
                "untrustworthy ledger timestamps")
        origin = receipt.get("target_date_source")
        require(origin in (SOURCE_SCHEDULE, SOURCE_EXPLICIT, "manual-utc-date"),
                "unknown logical target-date provenance")
        # Read holds from every attempt and every origin, failed ones
        # included, before the health filter: a run that held releases and
        # stored nothing new is recorded as failed, and an operator-dispatched
        # explicit or manual-date run is no less a hold than a scheduled one.
        held, identities = attachment_holds(receipt)
        held_identities |= identities
        if held:
            book = held_scheduled if origin == SOURCE_SCHEDULE else held_unscheduled
            book[target] = max(book.get(target, 0), held)
            heldby.setdefault(target, set()).update(identities)
        if receipt.get("health") != "ok" or receipt.get("result") not in SUCCESS:
            continue
        if origin == SOURCE_SCHEDULE:
            require(RUN_ID.fullmatch(ident) is not None,
                    "scheduled success must be a distinct first-attempt Actions ID")
            scheduled.add(target)
        elif origin == SOURCE_EXPLICIT:
            # Dates with any recorded hold are kept out of "recovered" below.
            recovered.add(target)

    latest = matured_slot(now)
    first = first_window_day(now)
    due = [first + timedelta(days=n)
           for n in range(max(0, (latest - first).days + 1))]
    missing = [d for d in due if d not in scheduled]
    # Ledgers alone cannot show that a held release later reached custody, so
    # any hold recorded for a date keeps that date out of "recovered",
    # whichever order the held and the clean attempts ran in.
    held_any = set(held_scheduled) | set(held_unscheduled)
    recovered_only = [d for d in missing if d in recovered and d not in held_any]
    uncovered = [d for d in missing if d not in recovered or d in held_any]
    # The evaluated window is the mature scheduled slots, first..latest. A
    # hold on a not-yet-mature date is reported once that date matures.
    for target, identities in heldby.items():
        if first <= target <= latest:
            window_identities |= identities
    current_missing = latest >= FIRST_SLOT and latest not in scheduled

    # The first October 7–13 Day-7 checkpoint remains historically failed;
    # do not make that fixed protocol silently slide forward. This independent
    # seven-slot observation identifies only a *prospective ledger candidate*.
    # Authentication of all Actions attempts, raw bytes, source rights and
    # editorial permission remain separate and explicitly false.
    last_seven = due[-7:]
    recent_missing = [d for d in last_seven if d not in scheduled]
    held_dates = [d for d in due if d in held_scheduled]
    recent_held = [d for d in last_seven if d in held_scheduled]
    current_held = held_scheduled.get(latest, 0) if latest >= FIRST_SLOT else 0
    prospective_candidate = (len(last_seven) == 7 and not recent_missing
                             and not recent_held)
    streak = 0
    for scheduled_day in reversed(due):
        if scheduled_day not in scheduled:
            break
        streak += 1
    return {
        "schema": SCHEMA,
        "state_branch": STATE_BRANCH,
        "state_commit": commit,
        "checked_at_utc": now.isoformat().replace("+00:00", "Z"),
        "logical_cron_utc": "17:47",
        "grace_hours": GRACE_HOURS,
        "latest_mature_slot": latest.isoformat(),
        "evaluated_scheduled_slots": len(due),
        "successful_scheduled_slots": len(due) - len(missing),
        "missing_scheduled_dates": [d.isoformat() for d in missing],
        "source_dates_recovered_explicitly_but_not_scheduled": [
            d.isoformat() for d in recovered_only],
        "source_dates_without_successful_scheduled_or_explicit_recovery": [
            d.isoformat() for d in uncovered],
        "current_mature_slot_missing": current_missing,
        "rolling_seven_observation_kind": "LEDGER_ONLY_CANDIDATE_NOT_AUTHENTICATED_ACTIONS",
        "rolling_seven_mature_dates": [d.isoformat() for d in last_seven],
        "rolling_seven_missing_scheduled_dates": [
            d.isoformat() for d in recent_missing],
        "rolling_seven_consecutive_ledger_candidate": prospective_candidate,
        "current_scheduled_ledger_streak_days": streak,
        # Counts and dates only; identities stay in the private ledgers.
        "attachment_holds_latest_mature_slot": current_held,
        "scheduled_dates_with_attachment_holds": [d.isoformat() for d in held_dates],
        "rolling_seven_dates_with_attachment_holds": [
            d.isoformat() for d in recent_held],
        # Explicit-recovery and manual-date attempts, failed or not. Never
        # reduced by a clean attempt for the same date.
        "unscheduled_dates_with_attachment_holds": sorted(
            d.isoformat() for d in held_unscheduled if first <= d <= latest),
        "distinct_attachment_hold_identities_in_ledgers": len(held_identities),
        "distinct_attachment_hold_identities_in_window": len(window_identities),
        "attachment_hold_custody_resolution_verified": False,
        "october_12_scheduled_gap_still_unrepaired": (
            latest >= date(2026, 10, 12) and
            date(2026, 10, 12) not in scheduled),
        "rolling_seven_production_admission_authorized": False,
        "status": ("CURRENT_SCHEDULED_SLOT_MISSING" if current_missing else
                   "CURRENT_SCHEDULED_SLOT_HAS_ATTACHMENT_HOLDS" if current_held else
                   "HISTORICAL_SCHEDULED_GAPS_REMAIN" if missing else
                   "LEDGER_SCHEDULED_SLOTS_OBSERVED"),
        "authenticates_all_github_actions_attempts": False,
        "verifies_capture_bytes_or_publisher_completeness": False,
        "government_silence_established": False,
        "human_review_approved": False,
        "source_or_media_rights_approved": False,
        "production_eligible": False,
        "weekly_brief_eligible": False,
        "automatically_retries_source": False,
        "changes_state": False,
    }


def inspect_checkout(folder, *, as_of):
    """Private sparse pinned checkout: only ledger/clock metadata are read."""
    commit, ledgers = pinned_ledger_checkout(folder, expected_branch=STATE_BRANCH)
    clockfile = Path(folder) / "state" / "clock.json"
    require(clockfile.is_file() and not clockfile.is_symlink()
            and clockfile.stat().st_size <= 10000, "unsafe or absent Korea clock")
    clock = json.loads(clockfile.read_text(encoding="utf-8"))
    return summarize(ledgers, clock, commit=commit, as_of=as_of)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shadow-checkout", type=Path, required=True)
    parser.add_argument("--as-of-utc", help="UTC instant; default real UTC now")
    parser.add_argument("--fail-current-gap", action="store_true",
                        help="Fail when the latest matured slot is missing or "
                             "left releases out of custody")
    args = parser.parse_args(argv)
    now = utc(args.as_of_utc or datetime.now(timezone.utc))
    require(now <= datetime.now(timezone.utc) + timedelta(minutes=5),
            "refuse future-dated observations")
    report = inspect_checkout(args.shadow_checkout, as_of=now)
    # Only bounded metadata goes into Actions logs. Never print source bodies.
    print(json.dumps(report, sort_keys=True))
    code = 0
    if args.fail_current_gap and report["current_mature_slot_missing"]:
        print("::error::Korea has no successful scheduled-run ledger for the "
              "latest mature slot. Verify authenticated Actions attempt census; "
              "use explicit desk=korea,target_date only for source recovery, "
              "not as replacement for uninterrupted scheduled reliability.")
        code = 2
    if args.fail_current_gap and report["attachment_holds_latest_mature_slot"]:
        print("::error::Korea's latest mature scheduled slot left %d release(s) "
              "out of custody: the collector's own byte cap refused the "
              "attachment. The held identities are in the private ledger; "
              "they age out of the listing window uncollected unless the cap "
              "is reviewed."
              % report["attachment_holds_latest_mature_slot"])
        code = 2
    if report["missing_scheduled_dates"]:
        print("::warning::Korea has historical scheduled-run gaps; "
              "manual recovery never retroactively qualifies those slots.")
    if report["distinct_attachment_hold_identities_in_window"]:
        print("::warning::Korea ledgers in the evaluated window record "
              "attachment holds (%d distinct release(s); scheduled dates %s; "
              "explicit or manual-date dates %s). A later clean slot or "
              "recovery does not show those releases were collected."
              % (report["distinct_attachment_hold_identities_in_window"],
                 ",".join(report["scheduled_dates_with_attachment_holds"]) or "none",
                 ",".join(report["unscheduled_dates_with_attachment_holds"]) or "none"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
