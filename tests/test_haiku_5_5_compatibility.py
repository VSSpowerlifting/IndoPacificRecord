"""
Opt-in `claude-haiku-5-5` compatibility and request-level cost accounting.

Offline only: every response is a scripted stand-in, no API key is read, no
database is opened and nothing tracked is written. The tracked usage history is
read, never written. See docs/engineering/HAIKU_5_5_COMPATIBILITY_2026-10-28.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.test_llm_usage_telemetry import (  # noqa: E402 — synthetic doubles
    CATEGORY_JSON, HAIKU, RELEVANCE_JSON, SONNET, SUMMARY_JSON, FakeClient,
    analyzer_for, rows_by_task, text_response, tool_response, usage,
)

HAIKU_5_5 = "claude-haiku-5-5"
HISTORY = REPO_ROOT / ".github" / "state" / "llm_usage.jsonl"
NEW_SETTINGS = {"thinking": {"type": "disabled"},
                "output_config": {"effort": "high"}}
SAMPLING = {"temperature", "top_p", "top_k"}


def text(t):
    return SimpleNamespace(type="text", text=t)


def thinking(t="private reasoning"):
    return SimpleNamespace(type="thinking", thinking=t, signature="sig")


def reply(blocks, u=None, stop="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop, usage=u)


def on_haiku_5_5():
    """Both model settings as the env override would set them, for one test."""
    return mock.patch.multiple("analysis.analyzer", ANALYSIS_MODEL=HAIKU_5_5,
                               RELEVANCE_MODEL=HAIKU_5_5)


def one_row(analyzer, task):
    row = rows_by_task(analyzer)[task]
    return (row["model"], row["calls"], row["succeeded_calls"],
            row["failed_calls"], row["input_tokens"], row["output_tokens"])


# ── 1. Defaults and the old request shapes ───────────────────────────────────

class TestDefaultsAndOldRequestsAreUnchanged(unittest.TestCase):

    def test_default_models_and_cap_without_any_override(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANALYSIS_MODEL", "RELEVANCE_MODEL",
                            "DAILY_ANALYSIS_CAP", "ANTHROPIC_API_KEY")}
        # A local .env must not decide what "default" means here.
        code = ("import dotenv; dotenv.load_dotenv = lambda *a, **k: False\n"
                "import json, config\n"
                "print(json.dumps([config.RELEVANCE_MODEL, config.ANALYSIS_MODEL,"
                " config.DAILY_ANALYSIS_CAP, config.RELEVANCE_TOOL_OUTPUT_ENABLED]))")
        out = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(json.loads(out.strip().splitlines()[-1]),
                         [HAIKU, SONNET, 55, False])

    def test_old_models_send_temperature_and_nothing_new(self):
        client = FakeClient(
            creates=[text_response(RELEVANCE_JSON, usage(1, 1)),
                     text_response(SUMMARY_JSON, usage(1, 1))],
            streams=[tool_response({"title_en": "T", "body_en": "B"})])
        a = analyzer_for(client)
        a.score_relevance("t", "b")
        a.summarize("t", "b")
        a.translate("t", "b")
        self.assertEqual([k["model"] for k in client.create_kwargs], [HAIKU, SONNET])
        for sent in client.create_kwargs:
            self.assertEqual(set(sent), {"model", "system", "messages",
                                         "max_tokens", "temperature"})
        sent = client.stream_kwargs[0]
        self.assertEqual(set(sent), {"model", "system", "messages", "max_tokens",
                                     "temperature", "tools", "tool_choice"})
        self.assertEqual((sent["model"], sent["temperature"]), (SONNET, 0.3))


# ── 2. The opt-in request shapes ─────────────────────────────────────────────

class TestOptInRequests(unittest.TestCase):

    def test_text_requests_omit_sampling_and_send_the_verified_settings(self):
        client = FakeClient(creates=[text_response(RELEVANCE_JSON, usage(1, 1)),
                                     text_response(SUMMARY_JSON, usage(1, 1))])
        a = analyzer_for(client)
        with on_haiku_5_5():
            a.score_relevance("t", "b")
            self.assertEqual(a.summarize("t", "b"), "Scripted summary.")
        for sent in client.create_kwargs:
            self.assertEqual(sent["model"], HAIKU_5_5)
            self.assertFalse(SAMPLING & set(sent))
            self.assertEqual(sent["extra_body"], NEW_SETTINGS)
            self.assertEqual(set(sent), {"model", "system", "messages",
                                         "max_tokens", "extra_body"})
            # No assistant prefill: the last message is the user's.
            self.assertEqual(sent["messages"][-1]["role"], "user")

    def test_translation_streams_the_forced_tool_and_returns_strings_verbatim(self):
        title = "  Ministry statement: “exercise” — 第2 phase\n"
        body = "Paragraph one.\n\n\tParagraph two, with  double spaces and 中文.\n"
        client = FakeClient(streams=[tool_response(
            {"title_en": title, "body_en": body}, usage(900, 1500))])
        a = analyzer_for(client)
        with on_haiku_5_5():
            self.assertEqual(a.translate("标题", "正文"), (title, body))
        sent = client.stream_kwargs[0]
        self.assertEqual(sent["model"], HAIKU_5_5)
        self.assertFalse(SAMPLING & set(sent))
        self.assertEqual(sent["extra_body"], NEW_SETTINGS)
        self.assertEqual(sent["tool_choice"],
                         {"type": "tool", "name": "emit_translation"})
        self.assertEqual([t["name"] for t in sent["tools"]], ["emit_translation"])
        from config import TRANSLATION_MAX_TOKENS
        self.assertEqual(sent["max_tokens"], TRANSLATION_MAX_TOKENS)
        self.assertEqual(one_row(a, "translation"),
                         (HAIKU_5_5, 1, 1, 0, 900, 1500))

    def test_the_request_serializes_through_the_installed_sdk(self):
        """The real client builds the HTTP body; only the transport is fake."""
        import anthropic
        import httpx
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "msg_offline", "type": "message", "role": "assistant",
                "model": HAIKU_5_5, "stop_reason": "end_turn",
                "stop_sequence": None,
                "content": [{"type": "text", "text": SUMMARY_JSON}],
                "usage": {"input_tokens": 10, "output_tokens": 5}})

        client = anthropic.Anthropic(
            api_key="offline-test-not-a-key", max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        a = analyzer_for(client)
        with on_haiku_5_5():
            self.assertEqual(a.summarize("t", "b"), "Scripted summary.")
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0]["thinking"], {"type": "disabled"})
        self.assertEqual(bodies[0]["output_config"], {"effort": "high"})
        self.assertFalse(SAMPLING & set(bodies[0]))


# ── 3. Response blocks are read by type ──────────────────────────────────────

class TestResponseBlocks(unittest.TestCase):

    def run_summary(self, response):
        a = analyzer_for(FakeClient(creates=[response]))
        with on_haiku_5_5():
            return a, a.summarize("t", "b")

    def test_thinking_before_text_is_skipped(self):
        a, out = self.run_summary(reply([thinking(), text(SUMMARY_JSON)],
                                        usage(10, 5)))
        self.assertEqual(out, "Scripted summary.")
        self.assertEqual(one_row(a, "summary"), (HAIKU_5_5, 1, 1, 0, 10, 5))

    def test_multiple_text_blocks_are_joined_in_order(self):
        a, out = self.run_summary(reply(
            [text('{"summary": "First half, '), thinking(),
             text('second half."}')], usage(10, 5)))
        self.assertEqual(out, "First half, second half.")

    def test_a_tool_block_is_never_the_answer_to_a_text_request(self):
        from analysis.analyzer import AnalysisError
        stray = SimpleNamespace(type="tool_use", name="x", input={"summary": "no"})
        a = analyzer_for(FakeClient(creates=[reply([stray], usage(10, 5))]))
        with on_haiku_5_5(), self.assertRaisesRegex(AnalysisError,
                                                    "Empty response content"):
            a.summarize("t", "b")
        self.assertEqual(one_row(a, "summary"), (HAIKU_5_5, 1, 0, 1, 10, 5))

    def test_reasoning_only_or_blank_text_fails_once(self):
        from analysis.analyzer import AnalysisError
        for blocks in ([thinking()], [text("   \n")], []):
            a = analyzer_for(FakeClient(creates=[reply(blocks, usage(10, 5))]))
            with on_haiku_5_5(), self.assertRaisesRegex(
                    AnalysisError, "Empty response content"):
                a.summarize("t", "b")
            self.assertEqual(one_row(a, "summary"), (HAIKU_5_5, 1, 0, 1, 10, 5))

    def test_a_missing_tool_block_fails_once(self):
        from analysis.analyzer import AnalysisError
        a = analyzer_for(FakeClient(streams=[reply([thinking(), text("Sure.")],
                                                   usage(10, 5))]))
        with on_haiku_5_5(), self.assertRaisesRegex(
                AnalysisError, "no `emit_translation`"):
            a.translate("t", "b")
        self.assertEqual(one_row(a, "translation"), (HAIKU_5_5, 1, 0, 1, 10, 5))

    def test_malformed_tool_values_fail_once_and_are_never_coerced(self):
        from analysis.analyzer import AnalysisError
        cases = [("a string, not an object", "tool input type"),
                 ({"title_en": None, "body_en": "B"}, "empty title_en"),
                 ({"title_en": "T", "body_en": 7}, "empty title_en"),
                 ({"title_en": "T", "body_en": "  "}, "empty title_en"),
                 ({"title_en": "T"}, "empty title_en")]
        for payload, message in cases:
            a = analyzer_for(FakeClient(streams=[tool_response(payload,
                                                               usage(10, 5))]))
            with on_haiku_5_5(), self.assertRaisesRegex(AnalysisError, message):
                a.translate("t", "b")
            self.assertEqual(one_row(a, "translation"),
                             (HAIKU_5_5, 1, 0, 1, 10, 5))


# ── 4. Voiding stops fail closed, once, with no fallback or retry ────────────

class TestVoidingStops(unittest.TestCase):

    STOPS = (("refusal", "declined"),
             ("model_context_window_exceeded", "context window"),
             ("max_tokens", "truncated"))

    def test_text_requests_fail_even_when_the_text_looks_valid(self):
        from analysis.analyzer import AnalysisError
        for stop, message in self.STOPS:
            client = FakeClient(creates=[text_response(SUMMARY_JSON, usage(40, 9),
                                                       stop=stop)])
            a = analyzer_for(client)
            with on_haiku_5_5(), self.assertRaisesRegex(AnalysisError, message):
                a.summarize("t", "b")
            self.assertEqual(len(client.create_kwargs), 1, stop)
            self.assertEqual(one_row(a, "summary"), (HAIKU_5_5, 1, 0, 1, 40, 9))
            self.assertEqual(set(rows_by_task(a)), {"summary"})

    def test_tool_requests_fail_even_when_the_tool_input_looks_valid(self):
        from analysis.analyzer import AnalysisError
        for stop, message in self.STOPS:
            client = FakeClient(streams=[tool_response(
                {"title_en": "T", "body_en": "B"}, usage(40, 9), stop=stop)])
            a = analyzer_for(client)
            with on_haiku_5_5(), self.assertRaisesRegex(AnalysisError, message):
                a.translate("t", "b")
            self.assertEqual(len(client.stream_kwargs), 1, stop)
            self.assertEqual(one_row(a, "translation"),
                             (HAIKU_5_5, 1, 0, 1, 40, 9))

    def test_old_models_reject_the_same_stops(self):
        from analysis.analyzer import AnalysisError
        for stop, message in self.STOPS:
            a = analyzer_for(FakeClient(creates=[text_response(
                CATEGORY_JSON, usage(40, 9), stop=stop)]))
            with self.assertRaisesRegex(AnalysisError, message):
                a.categorize("t", "b")
            self.assertEqual(one_row(a, "categorization"),
                             (SONNET, 1, 0, 1, 40, 9))

    def test_a_refused_translation_keeps_only_the_relevance_record(self):
        client = FakeClient(
            creates=[text_response(RELEVANCE_JSON, usage(100, 10))],
            streams=[tool_response({"title_en": "T", "body_en": "B"},
                                   usage(900, 50), stop="refusal")])
        a = analyzer_for(client)
        with on_haiku_5_5(), self.assertLogs("analysis.analyzer", "ERROR"):
            result = a.analyze("标题", "正文")
        # The existing partial record: relevance survives, nothing translated.
        self.assertEqual(set(result), {"relevance_score", "relevance_reasoning",
                                       "passed_relevance", "model_id",
                                       "prompt_version"})
        self.assertEqual((len(client.create_kwargs), len(client.stream_kwargs)),
                         (1, 1))
        self.assertEqual([(r["task"], r["model"], r["calls"], r["failed_calls"])
                          for r in a.usage.rows()],
                         [("relevance", HAIKU_5_5, 1, 0),
                          ("translation", HAIKU_5_5, 1, 1)])

    def test_parse_errors_stay_redacted_on_the_opt_in_model(self):
        from analysis.analyzer import AnalysisError
        leak = "MODEL-PROSE-THAT-MUST-NOT-REACH-LOGS"
        raw = '{"categories": ["' + leak + '"], broken}'
        client = FakeClient(creates=[reply([thinking(), text(raw)], usage(30, 8))])
        a = analyzer_for(client)
        with on_haiku_5_5(), self.assertRaisesRegex(
                AnalysisError, "JSON parse failed") as cm:
            a.categorize("t", "b")
        self.assertNotIn(leak, str(cm.exception))
        self.assertIn("response_chars=", str(cm.exception))
        self.assertEqual(one_row(a, "categorization"),
                         (HAIKU_5_5, 1, 0, 1, 30, 8))
        self.assertEqual((len(client.create_kwargs), len(client.stream_kwargs)),
                         (1, 0))


# ── 5. Tiered pricing, priced per response ───────────────────────────────────

class TestTieredPricing(unittest.TestCase):

    def cost(self, *counts):
        from analysis.pricing import estimate_usage_cost_usd
        return estimate_usage_cost_usd(HAIKU_5_5, *counts)

    def test_the_pinned_bands(self):
        from analysis import pricing
        self.assertEqual(pricing.TIERED_PRICING_USD_PER_MTOK[HAIKU_5_5], {
            "threshold_prompt_tokens": 100_000,
            "base": {"input": 0.10, "output": 0.50},
            "long": {"input": 0.50, "output": 2.50}})
        self.assertNotIn(HAIKU_5_5, pricing.PRICING_USD_PER_MTOK)

    def test_exactly_100000_prompt_tokens_is_the_lower_band(self):
        # 100,000 * 0.10 + 1,000 * 0.50 = 10,500 / 1e6
        self.assertAlmostEqual(self.cost(100_000, 1_000), 0.0105, 12)

    def test_100001_prompt_tokens_prices_the_whole_request_in_the_upper_band(self):
        # 100,001 * 0.50 + 1,000 * 2.50 = 52,500.5 / 1e6
        self.assertAlmostEqual(self.cost(100_001, 1_000), 0.0525005, 12)

    def test_cache_writes_and_reads_count_toward_the_band(self):
        # 40,000 uncached + 30,000 written + 30,001 read = 100,001 -> upper band.
        # 40,000*0.50 + 1,000*2.50 + 30,000*0.625 + 30,001*0.05 = 42,750.05
        self.assertAlmostEqual(self.cost(40_000, 1_000, 30_000, 30_001),
                               0.04275005, 12)
        # One fewer cache read: exactly 100,000 -> lower band.
        # 40,000*0.10 + 1,000*0.50 + 30,000*0.125 + 30,000*0.01 = 8,550
        self.assertAlmostEqual(self.cost(40_000, 1_000, 30_000, 30_000),
                               0.00855, 12)

    def ledger_cost(self, responses, task="translation"):
        from analysis.usage import UsageLedger, build_run_record
        from tests.test_llm_usage_telemetry import RUN_FIELDS
        ledger = UsageLedger()
        for u, failed in responses:
            ledger.record_response(task, HAIKU_5_5, u, failed=failed)
        return build_run_record(ledger, **RUN_FIELDS)

    def test_two_short_requests_stay_in_the_lower_band_together(self):
        rec = self.ledger_cost([(usage(60_000, 1_000), False),
                                (usage(60_000, 1_000), False)])
        # Each: 60,000*0.10 + 1,000*0.50 = 6,500. Summed tokens (120,000) would
        # wrongly price both at the upper band: 65,000.
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.013, 9)
        self.assertEqual(rec["input_tokens"], 120_000)
        self.assertEqual(rec["unpriced_models"], [])

    def test_mixed_bands_are_summed_without_repricing_the_short_one(self):
        rec = self.ledger_cost([(usage(1_000, 100), False),
                                (usage(150_000, 2_000), False)])
        # 1,000*0.10 + 100*0.50 = 150;  150,000*0.50 + 2,000*2.50 = 80,000
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.08015, 9)
        self.assertAlmostEqual(rec["tasks"][0]["estimated_cost_usd"], 0.08015, 9)

    def test_failed_paid_responses_keep_their_cost(self):
        rec = self.ledger_cost([(usage(1_000, 100), True),
                                (usage(2_000, 0), True)])
        # 150 + 200 = 350
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.00035, 9)
        self.assertEqual((rec["calls"], rec["failed_calls"]), (2, 2))

    def test_a_marked_failure_keeps_its_cost_and_a_bare_failure_adds_none(self):
        from analysis.usage import UsageLedger, build_run_record
        from tests.test_llm_usage_telemetry import RUN_FIELDS
        ledger = UsageLedger()
        ledger.record_response("summary", HAIKU_5_5, usage(1_000, 100))
        ledger.mark_failed("summary", HAIKU_5_5)
        ledger.record_failure("summary", HAIKU_5_5)  # e.g. a connection error
        rec = build_run_record(ledger, **RUN_FIELDS)
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.00015, 9)
        self.assertEqual((rec["calls"], rec["failed_calls"]), (2, 2))

    def test_an_analyzer_run_is_priced_per_response(self):
        a = analyzer_for(FakeClient(creates=[
            text_response(SUMMARY_JSON, usage(90_000, 500)),
            text_response(SUMMARY_JSON, usage(90_000, 500))]))
        with on_haiku_5_5():
            a.summarize("t", "b")
            a.summarize("t", "b")
        self.assertAlmostEqual(
            a.usage.tiered_costs()[("summary", HAIKU_5_5)], 0.0185, 12)

    def test_old_models_and_unknown_models_are_priced_as_before(self):
        from analysis.pricing import estimate_usage_cost_usd as cost
        from analysis.usage import UsageLedger, build_run_record
        from tests.test_llm_usage_telemetry import RUN_FIELDS
        self.assertAlmostEqual(cost(SONNET, 1000, 500, 200, 4000), 0.01245, 9)
        self.assertAlmostEqual(cost(HAIKU, 2000, 100), 0.0025, 9)
        # Summed-token pricing is unchanged for flat-rate models.
        self.assertAlmostEqual(cost(SONNET, 200_000, 0), 0.6, 9)
        self.assertIsNone(cost("claude-haiku-5-5-not-a-model", 1, 1))
        self.assertIsNone(cost("claude-sonnet-5-5", 1, 1))
        ledger = UsageLedger()
        ledger.record_response("summary", "claude-sonnet-5-5", usage(10, 10))
        ledger.record_response("relevance", HAIKU, usage(2000, 100))
        rec = build_run_record(ledger, **RUN_FIELDS)
        self.assertEqual(rec["unpriced_models"], ["claude-sonnet-5-5"])
        self.assertAlmostEqual(rec["estimated_cost_usd"], 0.0025, 9)

    def test_the_tracked_history_still_loads_and_reprices_identically(self):
        """Read-only: every historical row re-derives its recorded estimate."""
        from analysis.pricing import estimate_usage_cost_usd
        before = HISTORY.read_bytes()
        lines = [ln for ln in before.decode("utf-8").splitlines() if ln.strip()]
        self.assertGreater(len(lines), 0)
        for ln in lines:
            rec = json.loads(ln)
            for row in rec["tasks"]:
                cost = estimate_usage_cost_usd(
                    row["model"], row["input_tokens"], row["output_tokens"],
                    row["cache_creation_input_tokens"],
                    row["cache_read_input_tokens"])
                expected = None if cost is None else round(cost, 6)
                self.assertEqual(expected, row["estimated_cost_usd"],
                                 (rec["run_date"], row["task"], row["model"]))
        self.assertEqual(HISTORY.read_bytes(), before)


# ── 6. The bulk heuristic refuses the opt-in model ───────────────────────────

class TestBulkEstimateRefusesHaiku55(unittest.TestCase):

    def test_spend_guard_refuses_a_tiered_model(self):
        from scripts import spend_guard
        with self.assertRaisesRegex(KeyError, "priced per request"):
            spend_guard._price(HAIKU_5_5)
        with self.assertRaisesRegex(KeyError, "priced per request"):
            spend_guard.estimate_cost_usd(1_000, HAIKU_5_5)

    def test_spend_guard_old_models_and_unknown_message_are_unchanged(self):
        from scripts import spend_guard
        self.assertEqual(spend_guard._price(SONNET),
                         {"input": 3.00, "output": 15.00})
        with self.assertRaisesRegex(KeyError, "No price on file"):
            spend_guard._price("claude-sonnet-5-5")


# ── 7. Shared consumers keep their boundaries ────────────────────────────────

class TestSharedConsumerBoundaries(unittest.TestCase):

    def test_the_vpcp_bridge_still_pins_the_default_models(self):
        source = (REPO_ROOT / "processing" / "vpcp_policy.py").read_text("utf-8")
        self.assertIn("RELEVANCE_MODEL!='claude-haiku-4-5-20251001' or "
                      "ANALYSIS_MODEL!='claude-sonnet-4-6'", source)
        self.assertIn("vpcp_model_not_authorized", source)

    def test_vpcp_price_verification_covers_only_the_flat_table(self):
        from analysis.pricing import PRICING_USD_PER_MTOK
        self.assertEqual(set(PRICING_USD_PER_MTOK),
                         {SONNET, HAIKU, "claude-haiku-4-5"})

    def private_intake(self, analysis_model, payload_chars):
        """The private two-call bound around a fake `_call`; nothing is sent."""
        from processing import daily_intake
        sent = []

        class _Client:
            def with_options(self, **kw):
                sent.append(("with_options", kw))
                return self

        fake = SimpleNamespace(_client=_Client(),
                               _call=lambda *a, **k: sent.append(("call", k)))
        policy = {"max_estimated_cost_usd_per_run": 0.05}
        with mock.patch.multiple("config", ANALYSIS_MODEL=analysis_model,
                                 RELEVANCE_MODEL=HAIKU,
                                 RELEVANCE_TOOL_OUTPUT_ENABLED=False):
            daily_intake.bound_private_calls(fake, policy)
            messages = [{"role": "user", "content": "x" * payload_chars}]
            fake._call(messages, model=HAIKU, max_tokens=500, task="relevance")
            fake._call(messages, max_tokens=2200, task="summary")
            with self.assertRaises(daily_intake.IntakeHold):
                fake._call(messages, max_tokens=2200, task="summary")
        return sent

    def test_private_intake_keeps_two_calls_and_no_retries(self):
        sent = self.private_intake(SONNET, 100)
        self.assertEqual(sent[0], ("with_options", {"max_retries": 0}))
        self.assertEqual([s[1]["task"] for s in sent[1:]],
                         ["relevance", "summary"])

    def test_private_intake_reservation_is_never_below_the_upper_band(self):
        """
        The reservation prices UTF-8 bytes (an upper bound on tokens) as cache
        writes, so a request that could cross the band is reserved at the upper
        band. Shown on the pricing function the reservation calls.
        """
        from analysis.pricing import estimate_usage_cost_usd
        short = estimate_usage_cost_usd(HAIKU_5_5, 0, 2200, 100_000, 0)
        long = estimate_usage_cost_usd(HAIKU_5_5, 0, 2200, 100_001, 0)
        self.assertGreater(long, short * 4)
        self.assertAlmostEqual(long, (2200 * 2.50 + 100_001 * 0.625) / 1e6, 12)


if __name__ == "__main__":
    unittest.main()
