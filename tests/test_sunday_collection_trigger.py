"""No-network contracts for Sunday post-collection trigger and no-op refusal."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.sunday_collection_trigger import (
    CollectionTriggerRefused, REQUIRED_STEPS, verify,
)

ROOT = Path(__file__).resolve().parents[1]
REPO = "VSSpowerlifting/IndoPacificRecord"
SUNDAY = datetime(2026, 10, 25, 12, 30, tzinfo=ZoneInfo("America/New_York"))


def parent():
    return {
        "repository": {"full_name": REPO},
        "workflow_run": {
            "name": "Daily PLA Watch Update",
            "path": ".github/workflows/daily_update.yml",
            "event": "schedule",
            "head_branch": "main",
            "status": "completed", "conclusion": "success",
            "run_attempt": 1, "head_repository": {"full_name": REPO},
            "id": 98765,
        },
    }


def jobs():
    steps = [
        {"name": "Scheduling guard", "conclusion": "success"},
        *({"name": key, "conclusion": "success"} for key in REQUIRED_STEPS),
        {"name": "Health gate", "conclusion": "success"},
    ]
    return {"total_count": 1,
            "jobs": [{"name": "update", "conclusion": "success", "steps": steps}]}


class CollectionTriggeredSunday(unittest.TestCase):
    def test_real_sunday_production_completion_allows_one_editor_handoff(self):
        result = verify(parent(), jobs(), repo=REPO, marker="2026-10-25", now=SUNDAY)
        self.assertEqual(result["week_ending"], "2026-10-24")
        self.assertEqual(result["upstream_id"], 98765)

    def test_green_guard_only_no_op_cannot_trigger_editor(self):
        entry = jobs()
        entry["jobs"][0]["steps"] = [
            {"name": "Scheduling guard", "conclusion": "success"},
            *({"name": key, "conclusion": "skipped"} for key in REQUIRED_STEPS),
        ]
        with self.assertRaisesRegex(CollectionTriggerRefused, "skipped"):
            verify(parent(), entry, repo=REPO, marker="2026-10-25", now=SUNDAY)

    def test_incomplete_marker_and_non_sunday_refused(self):
        for marker in ("", "2026-10-24", "2026-10-26"):
            with self.subTest(marker=marker), self.assertRaises(CollectionTriggerRefused):
                verify(parent(), jobs(), repo=REPO, marker=marker, now=SUNDAY)
        monday = datetime(2026, 10, 26, 1, tzinfo=ZoneInfo("America/New_York"))
        with self.assertRaises(CollectionTriggerRefused):
            verify(parent(), jobs(), repo=REPO, marker="2026-10-26", now=monday)

    def test_manual_daily_runs_and_reruns_never_autosend(self):
        for field, value in (("event", "workflow_dispatch"),
                             ("run_attempt", 2), ("conclusion", "failure"),
                             ("head_branch", "candidate")):
            data = parent()
            data["workflow_run"][field] = value
            with self.subTest(field=field), self.assertRaises(CollectionTriggerRefused):
                verify(data, jobs(), repo=REPO, marker="2026-10-25", now=SUNDAY)

    def test_upstream_job_must_really_have_passed_publication_and_marker(self):
        for key in REQUIRED_STEPS:
            case = jobs()
            matching = next(x for x in case["jobs"][0]["steps"] if x["name"] == key)
            matching["conclusion"] = "skipped"
            with self.subTest(key=key), self.assertRaises(CollectionTriggerRefused):
                verify(parent(), case, repo=REPO, marker="2026-10-25", now=SUNDAY)

    def test_wrong_repository_or_untrustworthy_jobs_refused(self):
        for bad in (
            ({"repository": {"full_name": "other/repo"}, "workflow_run": parent()["workflow_run"]}, jobs()),
            (parent(), {"total_count": 0, "jobs": []}),
            (parent(), {"total_count": 2, "jobs": jobs()["jobs"]}),
        ):
            with self.assertRaises(CollectionTriggerRefused):
                verify(bad[0], bad[1], repo=REPO, marker="2026-10-25", now=SUNDAY)

    def test_replaces_cron_without_creating_another_workflow(self):
        text = (ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml").read_text()
        self.assertIn("workflow_run:", text)
        self.assertIn("workflows: [Daily PLA Watch Update]", text)
        self.assertIn("types: [completed]", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn("python -m scripts.sunday_collection_trigger", text)
        self.assertIn("actions: read", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' || (", text)
        self.assertIn("SUNDAY_SEND: ${{ github.event_name == 'workflow_run' ||", text)
        self.assertIn("github.event_name == 'workflow_run' && 'schedule'", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("actions/upload-artifact", text)


if __name__ == "__main__":
    unittest.main()
