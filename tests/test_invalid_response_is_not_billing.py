"""
A returned-but-unusable model response is not a billing failure.

Daily run 43103361840 (2026-11-11): the analysis queue held one backlog
article (6303). Haiku answered HTTP 200 with malformed relevance JSON, so
analyze() returned None. pipeline.py inferred "API or billing failure" from
"everything failed", wrote the billing-failure marker, exited 2 and skipped
render and deploy for every desk. The account was working the whole time.

Pinned here, offline and with no model spend:
  * the analyzer types every response-level rejection as InvalidModelResponse
    (still an AnalysisError) and leaves transport/status errors untyped;
  * analyze() records which kind of relevance failure produced None;
  * through the real pipeline.run(): an invalid-response-only zero-analysis run
    writes no billing marker, does not exit 2 and is recorded as degraded,
    while connection-style failures, mixed failures and FatalAPIError keep the
    existing conservative billing-marker behaviour;
  * per-article attempt accounting still counts the failed article.
"""

import json
import sqlite3
import unittest
from functools import partial
from unittest import mock

from analysis import analyzer as an
from tests.integration.test_pipeline_run import PipelineRunCase, scraper_factory
from tests.test_relevance_tool_optin import _Client, analyzer


class _StatusError(Exception):
    pass


class TestAnalyzerTypesResponseLevelFailures(unittest.TestCase):

    def test_malformed_json_is_an_invalid_model_response(self):
        with self.assertRaises(an.InvalidModelResponse) as ctx:
            an.Analyzer._parse_json('{\n  "score": 0.4,\n  "reasoning": "bad "quote" here"\n}')
        self.assertIsInstance(ctx.exception, an.AnalysisError)
        self.assertNotIn("quote", str(ctx.exception), "raw output must never be logged")

    def test_invalid_relevance_values_are_invalid_model_responses(self):
        a = analyzer(_Client(legacy=json.dumps({"score": "high", "reasoning": "x"})))
        with mock.patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
            with self.assertRaises(an.InvalidModelResponse):
                a.score_relevance("标题", "正文")

    def test_analyze_records_an_invalid_response_relevance_failure(self):
        a = analyzer(_Client(legacy='{"score": 0.5, "reasoning": "a "b" c"}'))
        with mock.patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
            self.assertIsNone(a.analyze("标题", "正文"))
        self.assertEqual(a.last_relevance_failure, an.RELEVANCE_FAILURE_INVALID_RESPONSE)

    def test_a_non_response_failure_is_recorded_as_an_api_error(self):
        a = analyzer(_Client())
        with mock.patch.object(a, "score_relevance",
                               side_effect=an.AnalysisError("API connection error: reset")):
            self.assertIsNone(a.analyze("标题", "正文"))
        self.assertEqual(a.last_relevance_failure, an.RELEVANCE_FAILURE_API_ERROR)

    def test_a_status_error_is_not_typed_as_an_invalid_response(self):
        exc = _StatusError()
        exc.status_code, exc.message = 500, "overloaded"
        classified = an._classify_status_error(exc)
        self.assertNotIsInstance(classified, an.InvalidModelResponse)
        self.assertNotIsInstance(classified, an.FatalAPIError)

    def test_a_successful_analysis_clears_a_previous_failure_kind(self):
        a = analyzer(_Client(legacy='{"score": 0.1, "reasoning": "not military"}'))
        a.last_relevance_failure = an.RELEVANCE_FAILURE_INVALID_RESPONSE
        with mock.patch("analysis.analyzer.RELEVANCE_TOOL_OUTPUT_ENABLED", False):
            result = a.analyze("标题", "正文")
        self.assertFalse(result["passed_relevance"])
        self.assertIsNone(a.last_relevance_failure)


class _ScriptedAnalyzer:
    """analyze_record() fails each article with the next scripted kind."""

    def __init__(self, kinds, fatal=False):
        self.kinds, self.fatal, self.calls = list(kinds), fatal, 0
        self.last_relevance_failure = None

    def analyze_record(self, title, body, profile=None):
        self.calls += 1
        if self.fatal:
            raise an.FatalAPIError("API status error (402): credit balance is too low")
        self.last_relevance_failure = self.kinds.pop(0)
        return None

    def __getattr__(self, name):
        raise AttributeError(name)


class TestPipelineClassification(PipelineRunCase):
    """Through the real pipeline.run() on a temporary database."""

    def seed(self, n):
        self.run_pipeline({"china_mil_online": scraper_factory(urls=[])})
        con = sqlite3.connect(str(self.db_path))
        sid = con.execute("SELECT id FROM sources WHERE slug='xinhua_mil'").fetchone()[0]
        ids = []
        for i in range(n):
            cur = con.execute(
                "INSERT INTO articles (source_id, url, title_original, text_original, "
                "published_date, content_hash, scraped_at) "
                "VALUES (?,?,?,?,?,?,datetime('now'))",
                (sid, "http://example.test/xinhua/seed%d.html" % i,
                 "解放军演习 %d" % i, "解放军 演习 正文 %d" % i, "2026-05-01",
                 "hash-invalid-%d" % i))
            ids.append(cur.lastrowid)
        con.commit()
        con.close()
        return ids

    def run_with(self, fake):
        from core import dossiers
        actual = dossiers.load_dossiers
        loader = partial(actual, source_dir=self.tmp / "dossiers")
        exit_code = None
        with mock.patch.object(dossiers, "load_dossiers", side_effect=loader), \
                mock.patch.object(self.pipeline, "ANTHROPIC_API_KEY", "test-key"), \
                mock.patch("analysis.analyzer.Analyzer", return_value=fake), \
                mock.patch.object(self.pipeline, "_record_llm_usage"), \
                mock.patch.object(self.pipeline, "_write_billing_failure_marker") as marker:
            try:
                self.run_pipeline({"china_mil_online": scraper_factory(urls=[])},
                                  no_analysis=False)
            except SystemExit as exc:
                exit_code = exc.code
        return marker.call_count, exit_code

    def attempts(self, ids):
        con = sqlite3.connect(str(self.db_path))
        try:
            return [con.execute("SELECT processing_attempts FROM articles WHERE id=?",
                                (i,)).fetchone()[0] for i in ids]
        finally:
            con.close()

    def test_the_incident_shape_writes_no_billing_marker_and_does_not_exit_2(self):
        ids = self.seed(1)
        fake = _ScriptedAnalyzer([an.RELEVANCE_FAILURE_INVALID_RESPONSE])
        markers, code = self.run_with(fake)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(markers, 0, "a returned response proves the account works")
        self.assertNotEqual(code, 2)
        self.assertEqual(self.run_status(), "degraded")
        self.assertEqual(self.attempts(ids), [1], "the failed attempt is still counted")

    def test_several_invalid_responses_alone_are_still_not_billing(self):
        self.seed(3)
        fake = _ScriptedAnalyzer([an.RELEVANCE_FAILURE_INVALID_RESPONSE] * 3)
        markers, code = self.run_with(fake)
        self.assertEqual((fake.calls, markers), (3, 0))
        self.assertNotEqual(code, 2)

    def test_non_response_failures_keep_the_conservative_marker(self):
        self.seed(2)
        fake = _ScriptedAnalyzer([an.RELEVANCE_FAILURE_API_ERROR] * 2)
        markers, code = self.run_with(fake)
        self.assertEqual((markers, code), (1, 2))
        self.assertEqual(self.run_status(), "failed")

    def test_mixed_failures_keep_the_conservative_marker(self):
        self.seed(2)
        fake = _ScriptedAnalyzer([an.RELEVANCE_FAILURE_INVALID_RESPONSE,
                                  an.RELEVANCE_FAILURE_API_ERROR])
        markers, code = self.run_with(fake)
        self.assertEqual((markers, code), (1, 2))

    def test_an_unclassified_failure_keeps_the_conservative_marker(self):
        self.seed(1)
        fake = _ScriptedAnalyzer([None])
        markers, code = self.run_with(fake)
        self.assertEqual((markers, code), (1, 2))

    def test_an_account_block_is_unchanged(self):
        self.seed(1)
        fake = _ScriptedAnalyzer([], fatal=True)
        markers, code = self.run_with(fake)
        self.assertEqual((markers, code), (1, 2))


if __name__ == "__main__":
    unittest.main()
