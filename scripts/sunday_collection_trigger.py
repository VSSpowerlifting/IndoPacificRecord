"""Fail-closed authorization for a collection-triggered Sunday editor handoff.

A Daily Update Actions run can be green because its guard SKIPPED collection.
Only one original scheduled, successfully deployed run with a newly written
Sunday success marker may unlock the existing Sunday editorial job.
No manuscript generation, mail or publication occurs here.
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


class CollectionTriggerRefused(ValueError):
    pass


class NoNewCollection(CollectionTriggerRefused):
    """A normal green retry did not actually collect or deploy anything."""
    pass


def verify(event, jobs, *, repo, marker, now):
    """Reconfirm original, live, successful scheduled Sunday collector."""
    if not REPO.fullmatch(repo):
        raise CollectionTriggerRefused("invalid repository")
    if now.tzinfo is None or now.utcoffset() is None:
        raise CollectionTriggerRefused("timezone-aware clock required")
    today = now.astimezone(NY).date()
    if today.weekday() != 6:
        # workflow_run subscribes to the daily workflow across all weekdays.
        # Non-Sundays are expected silent no-ops, NOT failed Briefs runs.
        raise NoNewCollection("not Sunday in New York")
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
        raise NoNewCollection("green retry skipped production collection")
    if any(state.get(step) != "success" for step in REQUIRED_STEPS):
        raise CollectionTriggerRefused("upstream full collection/deployment was skipped or failed")
    if marker != today.isoformat():
        raise CollectionTriggerRefused("Sunday marker not fresh and complete")
    return {"week_ending": (today - timedelta(days=1)).isoformat(),
            "collection_day": today.isoformat(), "upstream_id": run["id"]}


def fetch_jobs(*, repo, run_id, token):
    if not REPO.fullmatch(repo) or type(run_id) is not int or run_id <= 0 or not token:
        raise CollectionTriggerRefused("upstream jobs cannot be authenticated")
    request = Request(
        "https://api.github.com/repos/{}/actions/runs/{}/jobs?per_page=100".format(repo, run_id),
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + token,
                 "User-Agent": "ipr-sunday-editorial-collector-gate"},
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--marker", required=True, type=Path)
    parser.add_argument("--github-output", type=Path,
                        help="Set ready=true/false for the existing workflow's gated second job")
    args = parser.parse_args()
    try:
        # Native workflow_run is emitted every day. On weekdays, skip without
        # even reading the upstream Actions API or touching the sender.
        if datetime.now(NY).weekday() != 6:
            if args.github_output is None:
                raise NoNewCollection("not Sunday in New York")
            with args.github_output.open("a", encoding="utf-8") as out:
                out.write("ready=false\n")
            print("Outside Sunday; skipping editorial job.")
            return
        event = json.loads(args.event.read_text(encoding="utf-8"))
        run = event.get("workflow_run", {})
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        marker = args.marker.read_text(encoding="utf-8").strip()
        jobs = fetch_jobs(repo=repo, run_id=run.get("id"),
                          token=os.environ.get("GITHUB_TOKEN", ""))
        try:
            report = verify(event, jobs, repo=repo, marker=marker,
                            now=datetime.now(NY))
        except NoNewCollection:
            if args.github_output is None:
                raise
            with args.github_output.open("a", encoding="utf-8") as out:
                out.write("ready=false\n")
            print("Daily retry was green but skipped collection. No Brief job.")
            return
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, "Sunday collector handoff HELD: {}\n".format(exc))
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as out:
            out.write("ready=true\n")
    print("Validated complete Sunday production collection for " + report["collection_day"])
    print("Starting a single guarded editorial handoff; no email yet.")


if __name__ == "__main__":
    main()
