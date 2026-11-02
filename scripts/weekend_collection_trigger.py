"""Fail-closed check that a weekend Daily run really collected, before Briefs.

Adapted from the unmerged PR #807 Sunday-only verifier, generalised to the
Saturday provisional draft and the Sunday recheck notice. A Daily Update run
can be green because its guard SKIPPED collection, and a manual dispatch skips
the guards altogether. Only the original scheduled, successfully deployed main
run that wrote today's success marker may unlock the weekend editorial job.
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
REQUIRED_STEPS = (
    "Run pipeline",
    "Validate rendered output",
    "Deploy to GitHub Pages",
    "Record successful run",
)
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
MODES = {5: "saturday", 6: "sunday"}


class CollectionTriggerRefused(ValueError):
    pass


class NoNewCollection(CollectionTriggerRefused):
    """A weekday run, or a green run that did not actually collect anything."""


def verify(event, jobs, *, repo, marker, now):
    """Reconfirm today's original, live, successful scheduled collection.

    Saturday unlocks the provisional draft for the week ending today; Sunday
    unlocks only the recheck notice for the week ending yesterday.
    """
    if not REPO.fullmatch(repo):
        raise CollectionTriggerRefused("invalid repository")
    if now.tzinfo is None or now.utcoffset() is None:
        raise CollectionTriggerRefused("timezone-aware clock required")
    today = now.astimezone(NY).date()
    mode = MODES.get(today.weekday())
    if mode is None:
        # workflow_run subscribes to the daily workflow across all weekdays.
        # Weekdays are expected silent no-ops, NOT failed Briefs runs.
        raise NoNewCollection("not a weekend day in New York")
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
    state = {step["name"]: step.get("conclusion")
             for step in job["steps"] if isinstance(step, dict)
             and isinstance(step.get("name"), str)}
    if (state.get("Run pipeline") == "skipped"
            and state.get("Record successful run") == "skipped"):
        raise NoNewCollection("green run skipped production collection")
    if any(state.get(step) != "success" for step in REQUIRED_STEPS):
        raise CollectionTriggerRefused("upstream full collection/deployment was skipped or failed")
    if marker != today.isoformat():
        # No Friday substitution: yesterday's marker never stands in for today.
        raise CollectionTriggerRefused(mode.capitalize() + " marker not fresh and complete")
    saturday = today if mode == "saturday" else today - timedelta(days=1)
    return {"mode": mode, "week_ending": saturday.isoformat(),
            "collection_day": today.isoformat(), "upstream_id": run["id"]}


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
                        help="Set mode=saturday|sunday|none and week_ending")
    args = parser.parse_args(argv)
    now = now or datetime.now(NY)
    try:
        if now.astimezone(NY).weekday() not in MODES:
            # Skip without reading the upstream Actions API on weekdays.
            _write(args.github_output, mode="none")
            print("Outside the weekend; skipping editorial job.")
            return 0
        event = json.loads(args.event.read_text(encoding="utf-8"))
        run = event.get("workflow_run", {}) if isinstance(event, dict) else {}
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        marker = args.marker.read_text(encoding="utf-8").strip()
        jobs = jobs_reader(repo=repo, run_id=run.get("id"),
                           token=os.environ.get("GITHUB_TOKEN", ""))
        try:
            report = verify(event, jobs, repo=repo, marker=marker, now=now)
        except NoNewCollection:
            _write(args.github_output, mode="none")
            print("Daily run was green but skipped collection. No Brief job.")
            return 0
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, "Weekend collector handoff HELD: {}\n".format(exc))
    _write(args.github_output, mode=report["mode"], week_ending=report["week_ending"])
    print("Validated {} production collection for {} (week ending {}).".format(
        report["mode"], report["collection_day"], report["week_ending"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
