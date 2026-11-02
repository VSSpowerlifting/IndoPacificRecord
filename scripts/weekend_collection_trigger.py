"""Fail-closed check that a weekend Daily run really collected, before Briefs.

Adapted from the unmerged PR #807 Sunday-only verifier, generalised to the
Saturday provisional draft and the Sunday recheck notice. A Daily Update run
can be green because its guard SKIPPED collection, and a manual dispatch skips
the guards altogether. Only the original scheduled, successfully deployed main
run that wrote its own success marker may unlock the weekend editorial job.

The reporting day is the New York date on which the upstream run's
"Scheduling guard" step ran, because that is the date the Daily run records in
its success marker. It is never the time this event happens to be delivered:
a Saturday collection that finishes after midnight is still Saturday's, and a
delayed event is refused once a later collection has moved the marker on.
No manuscript generation, mail or publication occurs here; output is metadata.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
MAX_JSON_BYTES = 250_000
UPSTREAM_NAME = "Daily PLA Watch Update"
UPSTREAM_PATH = ".github/workflows/daily_update.yml"
GUARD_STEP = "Scheduling guard"
REQUIRED_STEPS = (
    "Run pipeline",
    "Validate rendered output",
    "Deploy to GitHub Pages",
    "Record successful run",
)
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MODES = {5: "saturday", 6: "sunday"}
# Daily cron windows open about 08:00-10:30 New York time. Twenty hours from
# the guard still ends before the next day's first window, so a later run
# cannot have collected; the marker check below enforces that independently.
MAX_TRIGGER_LAG = timedelta(hours=20)
# Prefilter: only runs started Friday-Sunday (New York) can be weekend
# collections; Friday covers a guard that crossed midnight into Saturday.
CANDIDATE_START_DAYS = (4, 5, 6)


class CollectionTriggerRefused(ValueError):
    pass


class NoNewCollection(CollectionTriggerRefused):
    """A weekday run, or a green run that did not actually collect anything."""


def _instant(value, label):
    if not isinstance(value, str) or not value:
        raise CollectionTriggerRefused(label + " timestamp missing")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CollectionTriggerRefused(label + " timestamp invalid") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise CollectionTriggerRefused(label + " timestamp lacks a timezone")
    return moment


def collection_day_of(job):
    """New York date the upstream guard computed for its success marker."""
    guard = [step for step in job["steps"] if isinstance(step, dict)
             and step.get("name") == GUARD_STEP]
    if len(guard) != 1 or guard[0].get("conclusion") != "success":
        raise CollectionTriggerRefused("upstream scheduling guard evidence unavailable")
    started = _instant(guard[0].get("started_at"), "guard start")
    completed = _instant(guard[0].get("completed_at"), "guard completion")
    first, last = started.astimezone(NY).date(), completed.astimezone(NY).date()
    if first != last or completed < started:
        # The guard straddled New York midnight: its marker date is ambiguous.
        raise CollectionTriggerRefused("upstream guard crossed New York midnight")
    return first, started


def verify(event, jobs, *, repo, marker, now):
    """Reconfirm one original, live, successful scheduled weekend collection.

    The reporting day comes from the upstream run itself. Saturday unlocks the
    provisional draft for the week ending that Saturday; Sunday unlocks only
    the recheck notice for the week ending the day before.
    """
    if not REPO.fullmatch(repo):
        raise CollectionTriggerRefused("invalid repository")
    if now.tzinfo is None or now.utcoffset() is None:
        raise CollectionTriggerRefused("timezone-aware clock required")
    if not isinstance(event, dict) or not isinstance(event.get("workflow_run"), dict):
        raise CollectionTriggerRefused("missing upstream workflow event")
    run = event["workflow_run"]
    if (run.get("name") != UPSTREAM_NAME
            or run.get("path") != UPSTREAM_PATH
            or run.get("event") != "schedule"
            or run.get("head_branch") != "main"
            or run.get("conclusion") != "success"
            or run.get("status") != "completed"
            or type(run.get("run_attempt")) is not int
            or run["run_attempt"] != 1
            or not isinstance(run.get("head_repository"), dict)
            or run["head_repository"].get("full_name") != repo
            or not isinstance(event.get("repository"), dict)
            or event["repository"].get("full_name") != repo):
        raise CollectionTriggerRefused("not the original successful main scheduled collection")
    if type(run.get("id")) is not int or run["id"] <= 0:
        raise CollectionTriggerRefused("missing upstream run id")
    if not isinstance(jobs, dict) or not isinstance(jobs.get("jobs"), list):
        raise CollectionTriggerRefused("upstream job evidence unavailable")
    if jobs.get("total_count") != len(jobs["jobs"]) or len(jobs["jobs"]) != 1:
        raise CollectionTriggerRefused("ambiguous upstream jobs")
    job = jobs["jobs"][0]
    if (not isinstance(job, dict) or job.get("name") != "update"
            or job.get("conclusion") != "success"
            or not isinstance(job.get("steps"), list)):
        raise CollectionTriggerRefused("upstream daily job not successful")
    day, guard_started = collection_day_of(job)
    mode = MODES.get(day.weekday())
    if mode is None:
        # workflow_run subscribes to the daily workflow across all weekdays.
        # Weekday collections are expected silent no-ops, NOT failed Briefs runs.
        raise NoNewCollection("upstream collection was not on a New York weekend day")
    state = {step["name"]: step.get("conclusion")
             for step in job["steps"] if isinstance(step, dict)
             and isinstance(step.get("name"), str)}
    if (state.get("Run pipeline") == "skipped"
            and state.get("Record successful run") == "skipped"):
        raise NoNewCollection("green run skipped production collection")
    if any(state.get(step) != "success" for step in REQUIRED_STEPS):
        raise CollectionTriggerRefused("upstream full collection/deployment was skipped or failed")
    lag = now - guard_started
    if lag < timedelta(0) or lag > MAX_TRIGGER_LAG:
        raise CollectionTriggerRefused(mode.capitalize() + " collection event is stale or from the future")
    if marker != day.isoformat():
        # No Friday substitution, and no draft from a corpus that a later
        # collection has already extended: the marker must still be this run's.
        raise CollectionTriggerRefused(mode.capitalize() + " marker not fresh and complete")
    saturday = day if mode == "saturday" else day - timedelta(days=1)
    return {"mode": mode, "week_ending": saturday.isoformat(),
            "collection_day": day.isoformat(), "upstream_id": run["id"]}


def candidate(event):
    """Cheap no-API prefilter on the upstream run's own start, never on now."""
    run = event.get("workflow_run") if isinstance(event, dict) else None
    if not isinstance(run, dict):
        return True  # Let verify() refuse malformed events loudly.
    try:
        started = _instant(run.get("run_started_at"), "upstream start")
    except CollectionTriggerRefused:
        return True
    return started.astimezone(NY).weekday() in CANDIDATE_START_DAYS


def fetch_jobs(*, repo, run_id, token):
    if not REPO.fullmatch(repo) or type(run_id) is not int or run_id <= 0 or not token:
        raise CollectionTriggerRefused("upstream jobs cannot be authenticated")
    request = Request(
        "https://api.github.com/repos/{}/actions/runs/{}/jobs?per_page=100".format(repo, run_id),
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + token,
                 "User-Agent": "ipr-weekend-editorial-collector-gate"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except Exception as exc:
        raise CollectionTriggerRefused("GitHub upstream jobs read failed") from exc
    if len(raw) > MAX_JSON_BYTES:
        raise CollectionTriggerRefused("oversized upstream evidence")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectionTriggerRefused("invalid upstream jobs JSON") from exc


def _write(path, **values):
    if path is None:
        return
    with path.open("a", encoding="utf-8") as out:
        for key, value in values.items():
            out.write("{}={}\n".format(key, value))


def main(argv=None, *, now=None, jobs_reader=fetch_jobs):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--marker", required=True, type=Path)
    parser.add_argument("--github-output", type=Path,
                        help="Set mode=saturday|sunday|none, week_ending and collection_day")
    args = parser.parse_args(argv)
    now = now or datetime.now(NY)
    try:
        event = json.loads(args.event.read_text(encoding="utf-8"))
        if not candidate(event):
            # Skip weekday collections without reading the Actions API.
            _write(args.github_output, mode="none")
            print("Upstream collection was not a weekend run; skipping editorial job.")
            return 0
        run = event.get("workflow_run", {}) if isinstance(event, dict) else {}
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        marker = args.marker.read_text(encoding="utf-8").strip()
        jobs = jobs_reader(repo=repo, run_id=run.get("id"),
                           token=os.environ.get("GITHUB_TOKEN", ""))
        try:
            report = verify(event, jobs, repo=repo, marker=marker, now=now)
        except NoNewCollection:
            _write(args.github_output, mode="none")
            print("Daily run did not collect for a weekend day. No Brief job.")
            return 0
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, "Weekend collector handoff HELD: {}\n".format(exc))
    _write(args.github_output, mode=report["mode"], week_ending=report["week_ending"],
           collection_day=report["collection_day"])
    print("Validated {} production collection for {} (week ending {}).".format(
        report["mode"], report["collection_day"], report["week_ending"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
