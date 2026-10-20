"""Korea lane of the shared Daily (processing/korea_shared_queue.py).

Scratch databases only. The four already-released MND texts are admitted by
the real bridge; the model is mocked. Where a translation is needed the mock
returns the reviewed English of that release (research/korea_english_reviewed),
so the real heading, alignment, QA and storage paths run without inventing
Korean or English. 156785691 has no reviewed English, so its translation call
fails — a realistic retryable failure.

Scenarios (brief step 10): 3 translation OK, 4 QA failure held, 5 altered SHA
refused, 9 API failure retryable, 10 late import, 11 China unaffected,
15 full replay idempotent.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import Mock
import importlib.util

_real_spec = importlib.util.spec_from_file_location

from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
from analysis.usage import UsageLedger
from core import korea_corpus_bridge as bridge
from core.korea_published_originals import INDEX, ORIGINAL_DIR
from migrations.runner import apply_all, connect
from processing import korea_shared_queue as lane
from tests.test_korea_corpus_bridge import LIVE, activate
from tests.test_migrations import build_legacy_db

ROOT = Path(__file__).resolve().parent.parent
REVIEWED = ROOT / "research/korea_english_reviewed"
PASS = ("korea-policy:156784297", "korea-policy:156785444")
QA_FAIL = "korea-policy:156785286"
NO_REVIEW = "korea-policy:156785691"


def reviewed_by_lines():
    """Map the tuple of source lines to the reviewed English entries."""
    out = {}
    for path in REVIEWED.glob("*.json"):
        text = (ORIGINAL_DIR / (path.stem + ".txt")).read_text(encoding="utf-8")
        entries = [{"index": t["index"], "text_en": t["text_en"]} for t in
                   json.loads(path.read_text(encoding="utf-8"))["translations"]]
        out[tuple(bridge.source_lines(text))] = entries
    return out


def fake_analyzer(summary="The Ministry of National Defense stated its position.",
                  relevance=0.95, fatal_at=None):
    a = object.__new__(Analyzer)
    a._usage = Mock(spec=UsageLedger)
    a.score_relevance = Mock(return_value=(relevance, "MND release"))
    table = reviewed_by_lines()
    calls = {"n": 0}

    def call_tool(messages, tool, max_tokens, temperature, **kw):
        calls["n"] += 1
        if fatal_at is not None and calls["n"] >= fatal_at:
            raise FatalAPIError("credit balance exhausted")
        payload = json.loads(messages[0]["content"].split(":\n", 1)[1])
        lines = tuple(l["ko"] for l in payload["lines"])
        if lines not in table:
            raise AnalysisError("malformed tool output")
        return {"translations": table[lines]}

    a._call_tool = Mock(side_effect=call_tool)
    a._desk_summary_and_flag = Mock(return_value=(summary, False, None))
    return a


class LaneCase(unittest.TestCase):
    def setUp(self):
        import storage.db as sdb
        self.sdb = sdb
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db_path = root / "scratch.db"
        build_legacy_db(self.db_path)
        conn = connect(self.db_path)
        apply_all(conn)
        activate(conn)
        conn.close()
        self.originals = root / "originals"
        shutil.copytree(ORIGINAL_DIR, self.originals)
        saved = sdb.DB_PATH
        sdb.DB_PATH = self.db_path
        self.addCleanup(setattr, sdb, "DB_PATH", saved)

    def admit(self, only=None):
        from tests.test_korea_corpus_bridge import admit_metadata, released
        conn = sqlite3.connect(str(self.db_path))
        present = {r[0] for r in conn.execute(
            "SELECT source_identity FROM korea_official_source_records")}
        for rec in released():
            ident = rec["source_identity"]
            if (only is None or ident in only) and ident not in present:
                admit_metadata(conn, rec)
        conn.commit()
        conn.row_factory = sqlite3.Row
        try:
            return bridge.apply(conn, run_id=None, index=INDEX,
                                original_dir=self.originals, excluded={},
                                registry=LIVE)
        finally:
            conn.close()

    def run_lane(self, analyzer, cap=10):
        return lane.run(analyzer, cap=cap, db=self.sdb, fatal_error=FatalAPIError)

    def ledger(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            return {r["source_identity"]: dict(r) for r in conn.execute(
                "SELECT * FROM korea_corpus_admissions")}
        finally:
            conn.close()

    def article(self, ident):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            return dict(conn.execute(
                "SELECT a.* FROM articles a JOIN korea_corpus_admissions k "
                "ON k.article_id=a.id WHERE k.source_identity=?",
                (ident,)).fetchone())
        finally:
            conn.close()


class TestKoreaLane(LaneCase):
    def test_outcomes_on_the_released_texts(self):        # scenarios 3, 4, 9
        self.admit()
        report = self.run_lane(fake_analyzer())
        led = self.ledger()
        self.assertEqual(sorted(report.processed), sorted(PASS))
        for ident in PASS:
            row = led[ident]
            self.assertEqual(row["processing_state"], "processed")
            self.assertEqual(row["qa_version"], "kr-qa-v1")
            self.assertEqual(row["glossary_version"], "kr-glossary-v1")
            self.assertIn("kr-translation-v2/kr-glossary-v1", row["prompt_version"])
            art = self.article(ident)
            self.assertTrue(art["analyzed_at"])
            self.assertEqual(art["passed_relevance"], 1)
            self.assertTrue(art["title_english"])
            self.assertEqual(art["text_english"].count("\n"),
                             art["text_original"].count("\n"))
        # The real standing benchmark finding is written as a machine reason.
        self.assertEqual(led[QA_FAIL]["processing_state"], "qa_held")
        self.assertEqual(led[QA_FAIL]["processing_reason"], "qa_number_added")
        held = self.article(QA_FAIL)
        self.assertIsNone(held["analyzed_at"])
        self.assertIsNone(held["text_english"])
        self.assertIsNone(held["passed_relevance"])
        # A failing item does not block the others and stays retryable.
        self.assertEqual(led[NO_REVIEW]["processing_state"], "retryable")
        self.assertEqual(led[NO_REVIEW]["processing_attempts"], 1)
        self.assertEqual(self.article(NO_REVIEW)["processing_state"], "retriable")

    def test_replay_makes_no_further_calls(self):             # scenario 15
        self.admit()
        self.run_lane(fake_analyzer())
        before = self.ledger()
        second = fake_analyzer()
        report = self.run_lane(second)
        # Only the retryable record is dispatched again.
        self.assertEqual(second.score_relevance.call_count, 1)
        self.assertEqual(report.selected, 1)
        after = self.ledger()
        for ident in PASS + (QA_FAIL,):
            self.assertEqual(after[ident], before[ident])
        self.assertEqual(after[NO_REVIEW]["processing_attempts"], 2)

    def test_retry_budget_pauses(self):
        self.admit(only={NO_REVIEW})
        for _ in range(5):
            self.run_lane(fake_analyzer())
        led = self.ledger()[NO_REVIEW]
        self.assertEqual((led["processing_state"], led["processing_reason"],
                          led["processing_attempts"]),
                         ("paused", "retry_budget_exhausted", 5))
        a = fake_analyzer()
        self.run_lane(a)
        a.score_relevance.assert_not_called()

    def test_altered_text_is_held_before_any_call(self):      # scenario 5
        self.admit(only={PASS[0]})
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE articles SET text_original = text_original || ' ' "
                     "WHERE id = (SELECT article_id FROM korea_corpus_admissions "
                     "WHERE source_identity = ?)", (PASS[0],))
        conn.commit()
        conn.close()
        a = fake_analyzer()
        report = self.run_lane(a)
        a.score_relevance.assert_not_called()
        a._call_tool.assert_not_called()
        self.assertEqual(report.qa_held, [(PASS[0], "pin_text_mismatch")])
        self.assertEqual(self.ledger()[PASS[0]]["processing_state"], "qa_held")

    def test_altered_heading_is_held(self):
        self.admit(only={PASS[0]})
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE articles SET title_original = 'x' WHERE id = "
                     "(SELECT article_id FROM korea_corpus_admissions "
                     "WHERE source_identity = ?)", (PASS[0],))
        conn.commit()
        conn.close()
        report = self.run_lane(fake_analyzer())
        self.assertEqual(report.qa_held, [(PASS[0], "pin_heading_mismatch")])

    def test_withdrawn_rows_are_never_dispatched(self):       # scenario 6-style
        self.admit(only={PASS[0]})
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("UPDATE korea_corpus_admissions SET state='withdrawn', "
                     "hold_reason='korea_release_withdrawn' "
                     "WHERE source_identity = ?", (PASS[0],))
        conn.commit()
        conn.close()
        a = fake_analyzer()
        report = self.run_lane(a)
        a.score_relevance.assert_not_called()
        self.assertEqual(report.selected, 0)

    def test_not_relevant_is_final(self):
        self.admit(only={PASS[0]})
        a = fake_analyzer(relevance=0.1)
        report = self.run_lane(a)
        a._call_tool.assert_not_called()
        self.assertEqual(report.not_relevant, [PASS[0]])
        self.assertEqual(self.article(PASS[0])["passed_relevance"], 0)
        b = fake_analyzer()
        self.run_lane(b)
        b.score_relevance.assert_not_called()

    def test_cap_defers_and_a_late_record_is_imported_next_day(self):  # 10
        self.admit(only={PASS[0]})
        first = self.run_lane(fake_analyzer(), cap=1)
        self.assertEqual(first.processed, [PASS[0]])
        self.admit()                       # late arrivals on a later Daily
        a = fake_analyzer()
        second = self.run_lane(a, cap=1)
        self.assertEqual((second.selected, second.deferred), (1, 2))
        third = self.run_lane(fake_analyzer(), cap=10)
        self.assertEqual(third.selected, 2)
        # The first record was paid for once only; late arrivals drain FIFO.
        self.assertNotIn(PASS[0], second.processed + third.processed)
        self.assertEqual(self.ledger()[PASS[0]]["processing_attempts"], 1)

    def test_cap_zero_dispatches_nothing(self):
        self.admit()
        a = fake_analyzer()
        report = self.run_lane(a, cap=0)
        a.score_relevance.assert_not_called()
        self.assertEqual((report.selected, report.deferred), (0, 4))

    def test_account_block_stops_the_lane(self):
        self.admit(only=set(PASS))
        a = fake_analyzer(fatal_at=1)
        report = self.run_lane(a)
        self.assertEqual(report.blocked, "FatalAPIError")
        self.assertEqual(a._call_tool.call_count, 1)
        led = self.ledger()
        self.assertTrue(all(led[i]["processing_state"] == "pending"
                            and led[i]["processing_attempts"] == 0
                            for i in PASS))

    def test_crash_after_article_write_is_repaired_without_a_call(self):
        self.admit(only={PASS[0]})
        real = lane._set_ledger
        calls = []

        def crash_on_processed(conn, ident, expected, state, **kw):
            if state == lane.PROCESSED and not calls:
                calls.append(ident)
                raise RuntimeError("simulated crash")
            return real(conn, ident, expected, state, **kw)

        with mock.patch.object(lane, "_set_ledger", crash_on_processed):
            with self.assertRaises(RuntimeError):
                self.run_lane(fake_analyzer())
        self.assertEqual(self.ledger()[PASS[0]]["processing_state"], "pending")
        a = fake_analyzer()
        report = self.run_lane(a)
        a.score_relevance.assert_not_called()
        self.assertEqual(report.repaired, [PASS[0]])
        self.assertEqual(self.ledger()[PASS[0]]["processing_state"], "processed")

    def test_logs_carry_no_korean_text(self):
        self.admit()
        with self.assertLogs("processing.korea_shared_queue", "INFO") as logs:
            self.run_lane(fake_analyzer())
        joined = "\n".join(logs.output)
        self.assertFalse(any("가" <= ch <= "힣" for ch in joined))
        self.assertIn("qa_number_added", joined)

    def test_no_ledger_table_is_a_no_op(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DROP TABLE korea_corpus_admissions")
        conn.commit()
        conn.close()
        report = self.run_lane(fake_analyzer())
        self.assertEqual(report.selected, 0)


class TestLaneInsideTheDaily(unittest.TestCase):
    """The lane inside the real pipeline.run(), China collection alongside."""

    def setUp(self):
        from tests.integration.test_pipeline_run import (
            PipelineRunCase, scraper_factory)
        self.case = PipelineRunCase("run")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.china = {"china_mil_online": scraper_factory(urls=[])}
        from tests.test_korea_corpus_bridge import admit_metadata, released
        originals = self.case.tmp / "originals"
        shutil.copytree(ORIGINAL_DIR, originals)
        conn = sqlite3.connect(str(self.case.db_path))
        activate(conn)
        for rec in released():
            admit_metadata(conn, rec)
        conn.row_factory = sqlite3.Row
        bridge.apply(conn, run_id=None, index=INDEX, original_dir=originals,
                     excluded={}, registry=LIVE)
        conn.close()

    def run_daily(self, analyzer, enabled=True):
        marker = Mock()
        with mock.patch("config.KOREA_DAILY_AUTOMATION_ENABLED", enabled), \
                mock.patch("config.KOREA_DAILY_PROCESSING_CAP", 4), \
                mock.patch.object(self.case.pipeline, "ANTHROPIC_API_KEY", "test"), \
                mock.patch.object(self.case.pipeline, "_write_billing_failure_marker",
                                  marker), \
                mock.patch.object(self.case.pipeline, "_record_llm_usage"), \
                mock.patch("config.CHINA_TITLE_TRANSLATION_LIMIT", 0), \
                mock.patch("analysis.analyzer.Analyzer", lambda: analyzer), \
                mock.patch("importlib.util.spec_from_file_location",
                           self.stub_site_render):
            self.case.run_pipeline(self.china, no_analysis=False)
        return marker

    @staticmethod
    def stub_site_render(name, *args, **kw):
        """The site build is covered by the render tests; this exercises the
        lane, so the Daily's final render step is a no-op here."""
        import importlib.machinery
        if name != "site_render":
            return _real_spec(name, *args, **kw)
        loader = Mock()
        loader.exec_module = lambda module: setattr(
            module, "render_site",
            lambda: {"mode": "stub", "output_dir": "stub"})
        return importlib.machinery.ModuleSpec(name, loader)

    def states(self):
        conn = sqlite3.connect(str(self.case.db_path))
        try:
            return dict(conn.execute(
                "SELECT source_identity, processing_state "
                "FROM korea_corpus_admissions"))
        finally:
            conn.close()

    def test_lane_processes_and_the_daily_stays_healthy(self):   # scenario 11
        marker = self.run_daily(fake_analyzer())
        states = self.states()
        self.assertEqual([states[i] for i in PASS], ["processed", "processed"])
        self.assertEqual(states[QA_FAIL], "qa_held")
        self.assertEqual(states[NO_REVIEW], "retryable")
        self.assertNotIn(self.case.run_status(), ("failed", "degraded"))
        marker.assert_not_called()

    def test_korea_only_account_block_degrades_without_failing(self):
        marker = self.run_daily(fake_analyzer(fatal_at=1))
        self.assertEqual(self.case.run_status(), "degraded")
        marker.assert_called_once()
        self.assertTrue(all(v == "pending" for k, v in self.states().items()
                            if k in PASS))

    def test_switch_off_never_dispatches(self):
        a = fake_analyzer()
        self.run_daily(a, enabled=False)
        a.score_relevance.assert_not_called()
        self.assertEqual(set(self.states().values()), {"pending"})


if __name__ == "__main__":
    unittest.main()
