"""Offline Korea Daily model-path tests: zero paid calls or site mutations.

The model is mocked. Where a realistic translation is needed the mock returns
the reviewed English of an already-released MND text (research/), so these
tests exercise the real heading, alignment and QA paths without inventing
Korean or English content.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
from analysis.usage import UsageLedger
from analysis.korea_daily import analyze, translate
from analysis.korea_prompts import (
    TRANSLATION_PROMPT_ID, TRANSLATION_SYSTEM, TRANSLATION_TOOL,
    analysis_messages, relevance_messages, translation_messages,
)
from processing.screening import KOREA_PROFILE, CHINA_PROFILE, profile_for_desk

ROOT = Path(__file__).resolve().parent.parent
RELEASE = "156784297"          # heading on source line 7 (0-based index 6)


def released():
    text = (ROOT / "research/korea_published_original_texts"
            / (RELEASE + ".txt")).read_text(encoding="utf-8")
    reviewed = json.loads((ROOT / "research/korea_english_reviewed"
                           / (RELEASE + ".json")).read_text(encoding="utf-8"))
    entries = [{"index": t["index"], "text_en": t["text_en"]}
               for t in reviewed["translations"]]
    return text, entries


def analyzer(entries=None, summary=("The Ministry of National Defense "
                                    "stated its position.", False, None)):
    a = object.__new__(Analyzer)
    a.score_relevance = Mock(return_value=(0.95, "MND press release"))
    a._call_tool = Mock(return_value={"translations": entries})
    a._desk_summary_and_flag = Mock(return_value=summary)
    # `usage` is a read-only property over the instance's `_usage` ledger.
    a._usage = Mock(spec=UsageLedger)
    return a


class KoreaDailyProcessingTests(unittest.TestCase):
    def test_korea_profile_is_explicit_and_daily_inactive(self):
        self.assertIs(profile_for_desk("korea"), KOREA_PROFILE)
        self.assertIs(profile_for_desk("china"), CHINA_PROFILE)
        self.assertFalse(KOREA_PROFILE.daily_queue)
        self.assertFalse(KOREA_PROFILE.keyword_prefilter)

    def test_prompt_specificity_and_versioning(self):
        for word in ("국방부", "방위사업청", "배포", "보도시점", "한미일",
                     "ROK–Japan", "ROK–U.S.–Japan"):
            self.assertIn(word, TRANSLATION_SYSTEM)
        self.assertNotIn("emit_translation ", TRANSLATION_SYSTEM)
        self.assertIn("NOT required", relevance_messages("제목", "본문")[0]["content"])
        content = translation_messages(["제목", "", "본문"])[0]["content"]
        self.assertIn('"source_language": "ko"', content)
        self.assertIn('"line_count": 3', content)
        self.assertIn('{"index": 2, "ko": ""}', content)
        self.assertIn("Routine diplomatic meetings", analysis_messages("Meeting", "Minister met envoy")[0]["content"])
        self.assertTrue(KOREA_PROFILE.analysis_prompt_version.startswith("kr-analysis"))
        self.assertEqual(TRANSLATION_PROMPT_ID, "kr-translation-v3/kr-glossary-v1")
        self.assertEqual(TRANSLATION_TOOL["name"], "emit_korea_translation")

    def test_analyzer_does_not_fall_through_to_china(self):
        text, entries = released()
        a = analyzer(entries)
        result = Analyzer.analyze_record(a, "제목", text, KOREA_PROFILE)
        self.assertTrue(result["requires_translation"])
        self.assertEqual(result["categories"], [])
        self.assertEqual(result["title_english"], entries[6]["text_en"].strip())
        self.assertEqual(result["text_english"],
                         "\n".join(e["text_en"] for e in entries))
        self.assertIn("kr-translation-v3/kr-glossary-v1", result["prompt_version"])
        call = a._call_tool.call_args
        self.assertIs(call.args[1], TRANSLATION_TOOL)
        self.assertIn("국방부", call.args[0][0]["content"])
        self.assertIn("ROK–Japan", call.kwargs["system"][0]["text"])
        a._desk_summary_and_flag.assert_called_once()

    def test_incomplete_translation_is_a_hold(self):
        text, _ = released()
        a = analyzer([])
        with self.assertRaises(AnalysisError):
            translate(a, text)
        a.usage.mark_failed.assert_called_once()

    def test_qa_failure_stops_before_the_summary_call(self):      # scenario 4
        text, entries = released()
        entries[5] = {"index": 6, "text_en": entries[5]["text_en"].replace(
            "15:40", "16:40")}
        a = analyzer(entries)
        result = analyze(a, "제목", text, KOREA_PROFILE)
        self.assertFalse(result["translation_qa"].passed)
        self.assertIn("qa_number_missing", result["translation_qa"].reasons)
        self.assertNotIn("text_english", result)
        a._desk_summary_and_flag.assert_not_called()

    def test_source_without_heading_makes_no_call(self):
        a = analyzer()
        a.score_relevance = Mock(side_effect=AssertionError("paid call"))
        self.assertIsNone(analyze(a, "제목", "본문", KOREA_PROFILE))
        self.assertIsNone(analyze(a, "제목", "배포\r\n본문", KOREA_PROFILE))

    def test_incomplete_summary_never_returns_public_english(self):
        text, entries = released()
        a = analyzer(entries)
        a._desk_summary_and_flag = Mock(side_effect=AnalysisError("invalid summary"))
        result = analyze(a, "제목", text, KOREA_PROFILE)
        self.assertTrue(result["passed_relevance"])
        self.assertNotIn("text_english", result)

    def test_unrelated_article_never_triggers_paid_translation(self):
        text, _ = released()
        a = analyzer()
        a.score_relevance = Mock(return_value=(0.1, "not defense"))
        a._call_tool = Mock(side_effect=AssertionError("unexpected API call"))
        result = analyze(a, "제목", text, KOREA_PROFILE)
        self.assertFalse(result["passed_relevance"])
        a._call_tool.assert_not_called()

    def test_account_billing_failure_propagates(self):
        text, _ = released()
        a = analyzer()
        a.score_relevance = Mock(side_effect=FatalAPIError("billing"))
        with self.assertRaises(FatalAPIError):
            analyze(a, "제목", text, KOREA_PROFILE)

    def test_billing_failure_during_translation_propagates(self):
        text, _ = released()
        a = analyzer()
        a._call_tool = Mock(side_effect=FatalAPIError("billing"))
        with self.assertRaises(FatalAPIError):
            analyze(a, "제목", text, KOREA_PROFILE)


if __name__ == "__main__":
    unittest.main()
