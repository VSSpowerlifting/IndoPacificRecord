"""No-network contracts for the weekend post-collection trigger (adapted from #807)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.weekend_collection_trigger import (
    ATTEMPT_STEP, CollectionTriggerRefused, NoNewCollection, REQUIRED_STEPS,
    already_attempted, main, reservation_name, verify,
)

REPO = "VSSpowerlifting/IndoPacificRecord"
NY = ZoneInfo("America/New_York")
SATURDAY = datetime(2026, 10, 24, 12, 30, tzinfo=NY)
SUNDAY = datetime(2026, 10, 25, 12, 30, tzinfo=NY)
SATURDAY_GUARD = datetime(2026, 10, 24, 10, 5, tzinfo=NY)
SUNDAY_GUARD = datetime(2026, 10, 25, 10, 5, tzinfo=NY)


def stamp(moment):
    # The Actions API reports UTC instants with a trailing Z.
    return moment.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def parent(started=SATURDAY_GUARD):
    return {
        "repository": {"full_name": REPO},
        "workflow_run": {
            "name": "Daily PLA Watch Update",
            "path": ".github/workflows/daily_update.yml",
            "event": "schedule",
            "head_branch": "main",
            "status": "completed", "conclusion": "success",
            "run_attempt": 1, "head_repository": {"full_name": REPO},
            "id": 98765, "run_started_at": stamp(started - timedelta(minutes=1)),
        },
    }


def guard(started):
    return {"name": "Scheduling guard", "conclusion": "success",
            "started_at": stamp(started),
            "completed_at": stamp(started + timedelta(seconds=4))}


WEEK = "ipr-weekend-saturday-2026-10-24"


def attempt(run_id, week=WEEK, conclusion="success"):
    """One earlier handoff run whose marker step reached the given conclusion."""
    steps = [{"name": "Set up job", "conclusion": "success"},
             {"name": ATTEMPT_STEP + week, "conclusion": conclusion},
             {"name": "Generate source-cited Sunday manuscript and optionally email Dylan",
              "conclusion": "failure" if conclusion == "success" else "skipped"}]
    return {"id": run_id, "jobs": {"total_count": 1, "jobs": [
        {"name": "sunday-editor-handoff", "steps": steps}]}}


def history(*runs):
    return {"total_count": len(runs), "workflow_runs": list(runs)}


def unreserved(**_):
    return history()


def jobs(started=SATURDAY_GUARD):
    steps = [
        guard(started),
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
        result = verify(parent(SUNDAY_GUARD), jobs(SUNDAY_GUARD), repo=REPO,
                        marker="2026-10-25", now=SUNDAY)
        self.assertEqual(result["mode"], "sunday")
        self.assertEqual(result["week_ending"], "2026-10-24")
        self.assertEqual(result["collection_day"], "2026-10-25")

    def test_new_york_day_not_utc_day_decides_mode(self):
        # 01:30 UTC Sunday is still Saturday evening in New York (EDT).
        late = datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(verify(parent(late), jobs(late), repo=REPO,
                                marker="2026-10-24", now=late)["mode"], "saturday")
        # After the November DST change the offset is five hours.
        winter = datetime(2026, 11, 8, 4, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(verify(parent(winter), jobs(winter), repo=REPO,
                                marker="2026-11-07", now=winter)["mode"], "saturday")

    def test_saturday_collection_delivered_after_midnight_stays_saturday(self):
        # The upstream guard ran late Saturday; the event arrives on Sunday.
        guard_at = datetime(2026, 10, 24, 23, 50, tzinfo=NY)
        delivered = datetime(2026, 10, 25, 0, 30, tzinfo=NY)
        result = verify(parent(guard_at), jobs(guard_at), repo=REPO,
                        marker="2026-10-24", now=delivered)
        self.assertEqual(result, {"mode": "saturday", "week_ending": "2026-10-24",
                                  "collection_day": "2026-10-24", "upstream_id": 98765})

    def test_sunday_collection_delivered_on_monday_stays_sunday(self):
        guard_at = datetime(2026, 10, 25, 23, 50, tzinfo=NY)
        delivered = datetime(2026, 10, 26, 0, 40, tzinfo=NY)
        result = verify(parent(guard_at), jobs(guard_at), repo=REPO,
                        marker="2026-10-25", now=delivered)
        self.assertEqual((result["mode"], result["week_ending"]), ("sunday", "2026-10-24"))

    def test_friday_collection_delivered_on_saturday_is_not_a_draft(self):
        guard_at = datetime(2026, 10, 23, 23, 50, tzinfo=NY)
        delivered = datetime(2026, 10, 24, 0, 30, tzinfo=NY)
        with self.assertRaises(NoNewCollection):
            verify(parent(guard_at), jobs(guard_at), repo=REPO,
                   marker="2026-10-23", now=delivered)

    def test_delayed_saturday_event_after_sunday_collection_is_refused(self):
        # A late Saturday guard is still inside the lag bound, but Sunday's run
        # already recorded its marker, so Saturday's corpus has moved on.
        guard_at = datetime(2026, 10, 24, 14, 20, tzinfo=NY)
        delivered = datetime(2026, 10, 25, 9, 0, tzinfo=NY)
        with self.assertRaisesRegex(CollectionTriggerRefused, "marker not fresh"):
            verify(parent(guard_at), jobs(guard_at), repo=REPO,
                   marker="2026-10-25", now=delivered)

    def test_event_older_than_the_lag_bound_or_from_the_future_is_refused(self):
        for now in (SATURDAY_GUARD + timedelta(hours=20, minutes=1),
                    SATURDAY_GUARD - timedelta(minutes=5)):
            with self.subTest(now=now), self.assertRaisesRegex(
                    CollectionTriggerRefused, "stale or from the future"):
                verify(parent(), jobs(), repo=REPO, marker="2026-10-24", now=now)

    def test_guard_timestamps_must_exist_and_not_straddle_midnight(self):
        straddle = jobs()
        straddle["jobs"][0]["steps"][0] = {
            "name": "Scheduling guard", "conclusion": "success",
            "started_at": stamp(datetime(2026, 10, 24, 23, 59, 59, tzinfo=NY)),
            "completed_at": stamp(datetime(2026, 10, 25, 0, 0, 2, tzinfo=NY))}
        missing = jobs()
        del missing["jobs"][0]["steps"][0]["started_at"]
        absent = jobs()
        absent["jobs"][0]["steps"] = absent["jobs"][0]["steps"][1:]
        for case in (straddle, missing, absent):
            with self.assertRaises(CollectionTriggerRefused):
                verify(parent(), case, repo=REPO, marker="2026-10-24", now=SATURDAY)

    def test_weekdays_are_silent_no_ops(self):
        friday = datetime(2026, 10, 23, 12, tzinfo=NY)
        guard_at = datetime(2026, 10, 23, 10, 5, tzinfo=NY)
        with self.assertRaises(NoNewCollection):
            verify(parent(guard_at), jobs(guard_at), repo=REPO,
                   marker="2026-10-23", now=friday)

    def test_stale_or_friday_marker_never_substitutes(self):
        for marker in ("", "2026-10-23", "2026-10-25"):
            with self.subTest(marker=marker), self.assertRaisesRegex(
                    CollectionTriggerRefused, "Saturday marker not fresh"):
                verify(parent(), jobs(), repo=REPO, marker=marker, now=SATURDAY)

    def test_guard_skipped_green_run_is_a_no_op_not_a_draft(self):
        entry = jobs()
        entry["jobs"][0]["steps"] = [
            guard(SATURDAY_GUARD),
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
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO, "GITHUB_RUN_ID": "700"}):
                self.assertEqual(main(argv, now=SATURDAY, jobs_reader=lambda **_: jobs(),
                                      history_reader=unreserved), 0)
            self.assertEqual(out.read_text(), "mode=saturday\nweek_ending=2026-10-24\n"
                                              "collection_day=2026-10-24\n"
                                              "reservation=ipr-weekend-saturday-2026-10-24\n")
            out.write_text("")
            # A Thursday collection skips on its own start, not on the clock,
            # even when the event is read on a Saturday.
            event.write_text(json.dumps(parent(datetime(2026, 10, 22, 10, tzinfo=NY))),
                             encoding="utf-8")
            reader = lambda **_: self.fail("weekday must not read the Actions API")
            self.assertEqual(main(argv, now=SATURDAY, jobs_reader=reader), 0)
            self.assertEqual(out.read_text(), "mode=none\n")
            # A Sunday collection delivered on Monday is still read, not skipped.
            out.write_text("")
            late = datetime(2026, 10, 25, 23, 50, tzinfo=NY)
            event.write_text(json.dumps(parent(late)), encoding="utf-8")
            marker.write_text("2026-10-25\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO}):
                # Sunday's free notice is not reserved, so no history is read.
                self.assertEqual(main(argv, now=datetime(2026, 10, 26, 0, 30, tzinfo=NY),
                                      jobs_reader=lambda **_: jobs(late),
                                      history_reader=lambda **_: self.fail("read")), 0)
            self.assertIn("mode=sunday\nweek_ending=2026-10-24\n", out.read_text())
            event.write_text(json.dumps(parent()), encoding="utf-8")
            marker.write_text("2026-10-23\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPO}), \
                    self.assertRaises(SystemExit) as stop:
                main(argv, now=SATURDAY, jobs_reader=lambda **_: jobs())
            self.assertEqual(stop.exception.code, 2)


class OnceOnlyReservation(unittest.TestCase):
    def run_cli(self, reader, run_id="700"):
        import json
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            event, marker, out = (Path(tmp) / name for name in ("e.json", "m.txt", "o.txt"))
            event.write_text(json.dumps(parent()), encoding="utf-8")
            marker.write_text("2026-10-24\n", encoding="utf-8")
            argv = ["--event", str(event), "--marker", str(marker), "--github-output", str(out)]
            env = {"GITHUB_REPOSITORY": REPO, "GITHUB_TOKEN": "t", "GITHUB_RUN_ID": run_id}
            with patch.dict(os.environ, env):
                try:
                    code = main(argv, now=SATURDAY, jobs_reader=lambda **_: jobs(),
                                history_reader=reader)
                except SystemExit as stop:
                    self.assertEqual(out.read_text() if out.exists() else "", "")
                    return stop.code
            return code

    def test_second_saturday_collection_is_refused_after_a_failed_attempt(self):
        # A different upstream run for the same Saturday: the earlier run's
        # marker started, then its model step failed. It is never retried.
        seen = []

        def reader(**kwargs):
            seen.append(kwargs)
            return history(attempt(601, week="ipr-weekend-saturday-2026-10-17"), attempt(650))
        self.assertEqual(self.run_cli(reader), 2)
        self.assertEqual(seen, [{"repo": REPO, "since": datetime(2026, 10, 22).date(),
                                 "token": "t"}])
        for conclusion in ("failure", "cancelled", None):
            with self.subTest(conclusion=conclusion):
                self.assertEqual(self.run_cli(lambda **_: history(
                    attempt(650, conclusion=conclusion))), 2)

    def test_skipped_marker_other_weeks_and_this_run_do_not_reserve(self):
        for runs in ((), (attempt(650, conclusion="skipped"),),
                     (attempt(601, week="ipr-weekend-saturday-2026-10-17"),),
                     (attempt(700),)):
            with self.subTest(runs=runs):
                self.assertEqual(self.run_cli(lambda **_: history(*runs)), 0)

    def test_unreadable_or_unevaluated_history_fails_closed(self):
        def broken(**_):
            raise CollectionTriggerRefused("GitHub reservation history read failed")
        incomplete_jobs = attempt(650)
        incomplete_jobs["jobs"]["total_count"] = 2
        unevaluated = attempt(650, week="${{ needs.weekend-collection.outputs.reservation }}")
        for reader in (broken, lambda **_: {"workflow_runs": []},
                       lambda **_: {"total_count": 3, "workflow_runs": []},
                       lambda **_: history({"id": 650}),
                       lambda **_: history(incomplete_jobs),
                       lambda **_: history(unevaluated)):
            with self.subTest(reader=reader):
                self.assertEqual(self.run_cli(reader), 2)
        self.assertEqual(self.run_cli(unreserved, run_id=""), 2)

    def test_history_reads_this_workflows_event_runs_and_every_attempt(self):
        import io
        import json
        from unittest.mock import patch
        from scripts import weekend_collection_trigger as trigger
        urls = []
        bodies = [{"total_count": 1, "workflow_runs": [{"id": 650}]},
                  {"total_count": 0, "jobs": []}]

        def fake(request, timeout):
            urls.append(request.full_url)
            return io.BytesIO(json.dumps(bodies.pop(0)).encode())
        with patch.object(trigger, "urlopen", fake):
            result = trigger.fetch_history(repo=REPO, since=datetime(2026, 10, 22).date(),
                                           token="t")
        self.assertEqual(urls, [
            "https://api.github.com/repos/" + REPO + "/actions/workflows/"
            "sunday_briefs_editorial_handoff.yml/runs"
            "?event=workflow_run&per_page=100&created=%3E%3D2026-10-22",
            "https://api.github.com/repos/" + REPO + "/actions/runs/650/jobs"
            "?filter=all&per_page=100"])
        self.assertEqual(result["workflow_runs"][0]["jobs"], {"total_count": 0, "jobs": []})
        with self.assertRaises(CollectionTriggerRefused):
            trigger.fetch_history(repo=REPO, since=datetime(2026, 10, 22).date(), token="")

    def test_only_the_exact_week_name_reserves(self):
        name = reservation_name("saturday", "2026-10-24")
        self.assertEqual(name, WEEK)
        other = attempt(601, week="ipr-weekend-saturday-2026-10-17")
        self.assertFalse(already_attempted(history(other), name, current_run_id=700))
        self.assertTrue(already_attempted(history(attempt(650)), name, current_run_id=700))
        prefixed = attempt(650, week=WEEK + "-x")
        self.assertFalse(already_attempted(history(prefixed), name, current_run_id=700))
        for bad in (("draft", "2026-10-24"), ("saturday", "2026-10-24/x")):
            with self.subTest(bad=bad), self.assertRaises(CollectionTriggerRefused):
                reservation_name(*bad)


if __name__ == "__main__":
    unittest.main()
