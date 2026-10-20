"""Offline Korea Daily model-path tests: zero paid calls or site mutations."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
from analysis.korea_daily import analyze, translate
from analysis.korea_prompts import (
    TRANSLATION_SYSTEM, analysis_messages, relevance_messages,
    translation_messages,
)
from processing.screening import KOREA_PROFILE, CHINA_PROFILE, profile_for_desk


class KoreaDailyProcessingTests(unittest.TestCase):
    def test_korea_profile_is_explicit_and_daily_inactive(self):
        self.assertIs(profile_for_desk("korea"), KOREA_PROFILE)
        self.assertIs(profile_for_desk("china"), CHINA_PROFILE)
        self.assertFalse(KOREA_PROFILE.daily_queue)
        self.assertFalse(KOREA_PROFILE.keyword_prefilter)

    def test_prompt_specificity_and_versioning(self):
        for word in ("국방부", "방위사업청", "배포", "보도시점", "한미일"):
            self.assertIn(word, TRANSLATION_SYSTEM)
        self.assertIn("NOT required", relevance_messages("제목", "본문")[0]["content"])
        self.assertIn('"source_language": "ko"', translation_messages("제목", "본문")[0]["content"])
        self.assertIn("Routine diplomatic meetings", analysis_messages("Meeting", "Minister met envoy")[0]["content"])
        self.assertTrue(KOREA_PROFILE.analysis_prompt_version.startswith("kr-analysis"))

    def test_analyzer_does_not_fall_through_to_china(self):
        a = object.__new__(Analyzer)
        a.score_relevance = Mock(return_value=(0.95, "MND press release"))
        a._call_tool = Mock(return_value={"title_en": "ROK meeting", "body_en": "An official met an envoy."})
        a._desk_summary_and_flag = Mock(return_value=("MND announced a meeting.", False, None))
        a.usage = SimpleNamespace(mark_failed=Mock())
        result = Analyzer.analyze_record(a, "국방부", "협력", KOREA_PROFILE)
        self.assertTrue(result["requires_translation"])
        self.assertEqual(result["categories"], [])
        self.assertEqual(result["title_english"], "ROK meeting")
        self.assertIn("kr-translation", result["prompt_version"])
        self.assertIn("국방부", a._call_tool.call_args.args[0][0]["content"])
        self.assertIn("ROK–Japan", a._call_tool.call_args.kwargs["system"][0]["text"])
        a._desk_summary_and_flag.assert_called_once()

    def test_incomplete_translation_is_a_hold(self):
        a = object.__new__(Analyzer)
        a._call_tool = Mock(return_value={"title_en": "ROK", "body_en": " "})
        a.usage = SimpleNamespace(mark_failed=Mock())
        with self.assertRaises(AnalysisError):
            translate(a, "제목", "본문")
        a.usage.mark_failed.assert_called_once()

    def test_incomplete_summary_never_returns_public_english(self):
        a = object.__new__(Analyzer)
        a.score_relevance = Mock(return_value=(0.95, "MND"))
        a._call_tool = Mock(return_value={"title_en": "Title", "body_en": "Body"})
        a._desk_summary_and_flag = Mock(side_effect=AnalysisError("invalid summary"))
        a.usage = SimpleNamespace(mark_failed=Mock())
        result = analyze(a, "제목", "본문", KOREA_PROFILE)
        self.assertTrue(result["passed_relevance"])
        self.assertNotIn("text_english", result)

    def test_unrelated_article_never_triggers_paid_translation(self):
        a = object.__new__(Analyzer)
        a.score_relevance = Mock(return_value=(0.1, "not defense"))
        a._call_tool = Mock(side_effect=AssertionError("unexpected API call"))
        result = analyze(a, "제목", "본문", KOREA_PROFILE)
        self.assertFalse(result["passed_relevance"])
        a._call_tool.assert_not_called()

    def test_account_billing_failure_propagates(self):
        a = object.__new__(Analyzer)
        a.score_relevance = Mock(side_effect=FatalAPIError("billing"))
        with self.assertRaises(FatalAPIError):
            analyze(a, "제목", "본문", KOREA_PROFILE)


if __name__ == "__main__":
    unittest.main()
