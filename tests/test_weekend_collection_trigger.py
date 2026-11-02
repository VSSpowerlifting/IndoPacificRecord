"""No-network contracts for the weekend post-collection trigger (adapted from #807)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.weekend_collection_trigger import (
    CollectionTriggerRefused, NoNewCollection, REQUIRED_STEPS, main, verify,
)

REPO = "VSSpowerlifting/IndoPacificRecord"
NY = ZoneInfo("America/New_York")
SATURDAY = datetime(2026, 10, 24, 12, 30, tzinfo=NY)
SUNDAY = datetime(2026, 10, 25, 12, 30, tzinfo=NY)


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


class WeekendCollectionTrigger(unittest.TestCase):
    def test_saturday_collection_unlocks_only_that_saturdays_provisional_draft(self):
        result = verify(parent(), jobs(), repo=REPO, marker="2026-10-24", now=SATURDAY)
        self.assertEqual(result, {"mode": "saturday", "week_ending": "2026-10-24",
                                  "collection_day": "2026-10-24", "upstream_id": 98765})

    def test_sunday_collection_unlocks_recheck_for_the_previous_saturday(self):
        result = verify(parent(), jobs(), repo=REPO, marker="2026-10-25", now=SUNDAY)
        self.assertEqual(result["mode"], "sunday")
        self.assertEqual(result["week_ending"], "2026-10-24")

    def test_new_york_day_not_utc_day_decides_mode(self):
        # 01:30 UTC Sunday is still Saturday evening in New York (EDT).
        late = datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(verify(parent(), jobs(), repo=REPO, marker="2026-10-24",
                                now=late)["mode"], "saturday")
        # After the November DST change the offset is five hours.
        winter = datetime(2026, 11, 8, 4, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(verify(parent(), jobs(), repo=REPO, marker="2026-11-07",
                                now=winter)["mode"], "saturday")

    def test_weekdays_are_silent_no_ops(self):
        friday = datetime(2026, 10, 23, 12, tzinfo=NY)
        with self.assertRaises(NoNewCollection):
            verify(parent(), jobs(), repo=REPO, marker="2026-10-23", now=friday)

    def test_stale_or_friday_marker_never_substitutes(self):
        for marker in ("", "2026-10-23", "2026-10-25"):
            with self.subTest(marker=marker), self.assertRaisesRegex(
                    CollectionTriggerRefused, "Saturday marker not fresh"):
                verify(parent(), jobs(), repo=REPO, marker=marker, now=SATURDAY)

    def test_guard_skipped_green_run_is_a_no_op_not_a_draft(self):
        entry = jobs()
        entry["jobs"][0]["steps"] = [
            {"name": "Scheduling guard", "conclusion": "success"},
            *({"name": key, "conclusion": "skipped"} for key in REQUIRED_STEPS),
        ]
        with self.assertRaises(NoNewCollection):
            verify(parent(), entry, repo=REPO, marker="2026-10-24", now=SATURDAY)

    def test_each_required_step_must_have_succeeded(self):
        for key in REQUIRED_STEPS:
            case = jobs()
            next(x for x in case["jobs"][0]["steps"] if x["name"] == key)["conclusion"] = "failure"
            with self.subTest(key=key), self.assertRaises(CollectionTriggerRefused):
                verify(parent(), case, repo=REPO, marker="2026-10-24", now=SATURDAY)

    def test_manual_runs_reruns_branches_and_failures_refused(self):
        for field, value in (("event", "workflow_dispatch"), ("run_attempt", 2),
                             ("conclusion", "failure"), ("head_branch", "candidate"),
                             ("path", ".github/workflows/other.yml")):
            data = parent()
            data["workflow_run"][field] = value
            with self.subTest(field=field), self.assertRaises(CollectionTriggerRefused):
                verify(data, jobs(), repo=REPO, marker="2026-10-24", now=SATURDAY)

    def test_wrong_repository_or_ambiguous_jobs_refused(self):
        for event, entry in (
            ({"repository": {"full_name": "other/repo"},
              "workflow_run": parent()["workflow_run"]}, jobs()),
            (parent(), {"total_count": 0, "jobs": []}),
            (parent(), {"total_count": 2, "jobs": jobs()["jobs"]}),
        ):
            with self.assertRaises(CollectionTriggerRefused):
                verify(event, entry, repo=REPO, marker="2026-10-24", now=SATURDAY)

    def test_cli_writes_metadata_only_and_holds_on_refusal(self):
        import json
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            event, marker, out = (Path(tmp) / name for name in ("e.json", "m.txt", "o.txt"))
            event.write_text(json.dumps(parent()), encoding="utf-8")
            marker.write_text("2026-10-24\n", encoding="utf-8")
            argv = ["--event", str(event), "--marker", str(marker), "--github-output", str(out)]
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO}):
                self.assertEqual(main(argv, now=SATURDAY, jobs_reader=lambda **_: jobs()), 0)
            self.assertEqual(out.read_text(), "mode=saturday\nweek_ending=2026-10-24\n")
            out.write_text("")
            weekday = datetime(2026, 10, 22, 12, tzinfo=NY)
            reader = lambda **_: self.fail("weekday must not read the Actions API")
            self.assertEqual(main(argv, now=weekday, jobs_reader=reader), 0)
            self.assertEqual(out.read_text(), "mode=none\n")
            marker.write_text("2026-10-23\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO}), \
                    self.assertRaises(SystemExit) as stop:
                main(argv, now=SATURDAY, jobs_reader=lambda **_: jobs())
            self.assertEqual(stop.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
