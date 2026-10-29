"""Offline contract tests for the isolated China summary/category experiment."""
import json
import unittest

from analysis.analyzer import AnalysisError
from analysis.china_fold_experiment import (
    TASK_COMBINED,
    build_combined_messages,
    run_combined,
    validate_combined,
)
from config import ANALYSIS_MODEL


GOOD = {
    "summary": "The 76th Group Army conducted a routine training exercise.",
    "categories": ["exercises"],
    "significance": False,
    "significance_reason": None,
}


class _Ledger:
    def __init__(self):
        self.failed = []

    def mark_failed(self, task, model):
        self.failed.append((task, model))


class _FakeAnalyzer:
    def __init__(self, payload):
        self.payload = payload
        self.usage = _Ledger()
        self.call_kwargs = None

    def _call(self, messages, **kwargs):
        self.call_kwargs = {"messages": messages, **kwargs}
        return json.dumps(self.payload)

    def _parse_task_json(self, raw, task, model):
        return json.loads(raw)


class ChinaFoldPilotTests(unittest.TestCase):

    def test_one_source_payload_and_both_original_rubrics(self):
        messages = build_combined_messages("UniqueTitle987", "UniqueBody654")
        self.assertEqual(len(messages), 1)
        text = messages[0]["content"]
        self.assertEqual(text.count("UniqueTitle987"), 1)
        self.assertEqual(text.count("UniqueBody654"), 1)
        self.assertIn("TASK A", text)
        self.assertIn("TASK B", text)
        self.assertIn("76th Group Army", text)
        self.assertIn("south_china_sea", text)
        self.assertEqual(text.count("Return only the raw JSON object"), 0)

    def test_valid_result(self):
        self.assertEqual(validate_combined(dict(GOOD)), GOOD)

    def test_true_flag_requires_reason(self):
        row = dict(GOOD, significance=True, significance_reason="Unusual scale.")
        self.assertEqual(validate_combined(row)["significance_reason"],
                         "Unusual scale.")
        row["significance_reason"] = None
        with self.assertRaises(AnalysisError):
            validate_combined(row)

    def test_false_flag_rejects_unsupported_reason(self):
        with self.assertRaises(AnalysisError):
            validate_combined(dict(GOOD, significance_reason="Speculation."))

    def test_reject_invalid_categories(self):
        for bad in ([], ["unknown"], ["exercises", "exercises"], [3], "exercises"):
            with self.subTest(bad=bad):
                with self.assertRaises(AnalysisError):
                    validate_combined(dict(GOOD, categories=bad))

    def test_reject_missing_extra_or_mistyped_fields(self):
        cases = [
            dict(GOOD, summary=" "),
            dict(GOOD, significance=1),
            dict(GOOD, unexpected=True),
            {k: v for k, v in GOOD.items() if k != "summary"},
            None,
        ]
        for row in cases:
            with self.subTest(row=row):
                with self.assertRaises(AnalysisError):
                    validate_combined(row)

    def test_single_call_and_separate_cost_label(self):
        fake = _FakeAnalyzer(GOOD)
        self.assertEqual(run_combined(fake, "Title", "Body"), GOOD)
        self.assertEqual(fake.call_kwargs["task"], TASK_COMBINED)
        self.assertEqual(fake.call_kwargs["model"], ANALYSIS_MODEL)
        self.assertEqual(fake.call_kwargs["max_tokens"], 1500)
        self.assertEqual(fake.usage.failed, [])

    def test_bad_response_marks_spent_call_as_failure(self):
        fake = _FakeAnalyzer(dict(GOOD, categories=["not_allowed"]))
        with self.assertRaises(AnalysisError):
            run_combined(fake, "Title", "Body")
        self.assertEqual(fake.usage.failed, [(TASK_COMBINED, ANALYSIS_MODEL)])


if __name__ == "__main__":
    unittest.main()
