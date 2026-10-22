"""DAPA scheduled-source authorization, zero government network on negative cases."""
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE
from scripts import shadow_collect_desk as runner


class ScheduledDapaContracts(unittest.TestCase):
    def args(self, *extra):
        return ["--desk", "korea_dapa", "--state-dir", "/tmp/dapa-no-network-schedule-contract",
                "--event-name", "schedule", "--cron-utc", "22:17",
                "--run-attempt", "1", "--cap", "5", "--lookback-days", "0", *extra]

    def test_scheduled_source_refuses_without_distinct_recurring_authorization(self):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY":
                                           "VSSpowerlifting/ipr-source-evidence-private"}):
            with mock.patch.object(runner, "run") as capture:
                self.assertEqual(runner.main(self.args()), 2)
                capture.assert_not_called()

    def test_wrong_repository_cron_manual_day_and_retries_do_not_collect(self):
        cases = (
            (self.args("--approve-recurring-dapa-original-access"),
             {"GITHUB_REPOSITORY": "VSSpowerlifting/IndoPacificRecord"}),
            (self.args("--approve-recurring-dapa-original-access",
                       "--target-date", "2026-10-18"),
             {"GITHUB_REPOSITORY": "VSSpowerlifting/ipr-source-evidence-private"}),
            (self.args("--approve-recurring-dapa-original-access", "--run-attempt", "2"),
             {"GITHUB_REPOSITORY": "VSSpowerlifting/ipr-source-evidence-private"}),
            (self.args("--approve-recurring-dapa-original-access",
                       "--approve-one-time-dapa-original-access"),
             {"GITHUB_REPOSITORY": "VSSpowerlifting/ipr-source-evidence-private"}),
            (self.args("--approve-recurring-dapa-original-access", "--cron-utc", "21:17"),
             {"GITHUB_REPOSITORY": "VSSpowerlifting/ipr-source-evidence-private"}),
        )
        for args, env in cases:
            with self.subTest(args=args):
                with mock.patch.dict(os.environ, env):
                    with mock.patch.object(runner, "run") as capture:
                        self.assertEqual(runner.main(args), 2)
                        capture.assert_not_called()

    def test_permitted_scheduled_slot_is_explicitly_labelled_not_manual(self):
        with mock.patch.dict(os.environ, {"GITHUB_REPOSITORY":
                                           "VSSpowerlifting/ipr-source-evidence-private"}):
            with mock.patch.object(runner, "run", return_value={"health": "ok"}) as run:
                self.assertEqual(runner.main(
                    self.args("--approve-recurring-dapa-original-access")), 0)
                self.assertTrue(run.call_args.kwargs["dapa_recurring_access_authorized"])
                self.assertFalse(run.call_args.kwargs["dapa_original_access_authorized"])
                self.assertEqual(run.call_args.kwargs["target_source"], SOURCE_SCHEDULE)

    def test_direct_import_keeps_manual_and_schedule_permissions_separate(self):
        for kw in (
            {"target_source": SOURCE_SCHEDULE,
             "dapa_original_access_authorized": True},
            {"target_source": SOURCE_EXPLICIT,
             "dapa_recurring_access_authorized": True},
            {"target_source": SOURCE_SCHEDULE,
             "dapa_recurring_access_authorized": False},
            {"target_source": SOURCE_SCHEDULE,
             "dapa_recurring_access_authorized": True,
             "dapa_original_access_authorized": True},
        ):
            with self.subTest(kw=kw), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "evidence"
                with self.assertRaises(ValueError):
                    runner.run("korea_dapa", root, date(2026, 10, 18),
                               lookback=0, cap=5, **kw)
                self.assertFalse(root.exists())

    def test_source_ceiling_still_applies_to_recurring_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            for cap, lookback in ((6, 0), (40, 0), (5, 1)):
                with self.subTest(cap=cap, lookback=lookback):
                    with self.assertRaisesRegex(ValueError, "bounded cap"):
                        runner.run(
                            "korea_dapa", root, date(2026, 10, 18),
                            lookback=lookback, cap=cap,
                            target_source=SOURCE_SCHEDULE,
                            dapa_recurring_access_authorized=True)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
