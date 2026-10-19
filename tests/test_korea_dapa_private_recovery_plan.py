"""Offline-only bounded DAPA recovery planner contracts; no publisher access."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.korea_dapa_private_recovery_plan import RecoveryHold, plan


class PrivateGapPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ledger").mkdir()
        (self.root / "private_attempts").mkdir()

    def attempt(self, day, run, result="ok", code=0, inserted=1, cap=5):
        row = {
            "desk": "korea_dapa", "run_id": run, "target_date": day,
            "target_date_source": "explicit", "lookback_days": 0,
            "cap": cap, "inserted": inserted, "result": result,
            "health": "ok" if result.startswith("ok") else "fail",
        }
        receipt = {"run_attempt": run, "collector_exit_status": code}
        (self.root / "ledger" / ("20261018T000000-" + run + ".json")
         ).write_text(json.dumps(row), encoding="utf-8")
        (self.root / "private_attempts" / (run + ".json")
         ).write_text(json.dumps(receipt), encoding="utf-8")
        return row

    def test_identifies_missing_failed_and_proven_zero_day(self):
        self.attempt("2026-10-16", "39076047210-1", "ok_no_publications", 0, 0)
        self.attempt("2026-10-17", "39076047211-1", "listing_failure", 1, 0)
        result = plan(self.root, date(2026, 10, 16),
                      date(2026, 10, 18), as_of=date(2026, 10, 18))
        self.assertEqual([d["status"] for d in result["days"]],
                         ["COLLECTED_CLEAN", "FAILED_REQUIRES_REVIEW",
                          "MISSING_REQUIRES_REVIEW"])
        self.assertEqual(result["days"][0]["next_step"], "none")
        self.assertEqual(result["days"][2]["next_step"],
                         "owner_review_then_one_day_authorized_collection")
        self.assertTrue(result["offline_only"])
        self.assertFalse(result["authentication_or_publication_decision"])

    def test_later_clean_same_day_is_not_marked_missing(self):
        self.attempt("2026-10-18", "39076047212-1", "listing_failure", 1, 0)
        self.attempt("2026-10-18", "39076047213-1", "ok", 0, 2)
        x = plan(self.root, date(2026, 10, 18), date(2026, 10, 18),
                 as_of=date(2026, 10, 18))
        self.assertEqual(x["days"][0]["status"], "COLLECTED_CLEAN")
        self.assertEqual(len(x["days"][0]["attempts"]), 2)

    def test_no_future_or_unbounded_or_october_15(self):
        for start, end in (("2026-10-15", "2026-10-16"),
                           ("2026-10-16", "2026-10-23"),
                           ("2026-10-19", "2026-10-19"),
                           ("2026-10-18", "2026-10-17")):
            with self.subTest(start=start, end=end), self.assertRaises(RecoveryHold):
                plan(self.root, date.fromisoformat(start),
                     date.fromisoformat(end), as_of=date(2026, 10, 18))

    def test_bad_history_and_missing_receipt_hold(self):
        self.attempt("2026-10-18", "39076047219-1")
        receipt = self.root / "private_attempts/39076047219-1.json"
        receipt.unlink()
        with self.assertRaisesRegex(RecoveryHold, "RECEIPT_MISSING"):
            plan(self.root, date(2026, 10, 18), date(2026, 10, 18),
                 as_of=date(2026, 10, 18))

    def test_mismatched_success_counter_refused(self):
        self.attempt("2026-10-18", "39076047219-1", "ok", 0, 0)
        with self.assertRaisesRegex(RecoveryHold, "RESULT_INCONSISTENT"):
            plan(self.root, date(2026, 10, 18), date(2026, 10, 18),
                 as_of=date(2026, 10, 18))

    def test_no_writes_from_read_only_plan(self):
        self.attempt("2026-10-18", "39076047219-1")
        before = {str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        plan(self.root, date(2026, 10, 18), date(2026, 10, 18),
             as_of=date(2026, 10, 18))
        after = {str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
