"""
Interim China Desk source-use hold (core/china_source_use_hold.py).

Synthetic fixtures only: no publisher request, no model call, no production
database. The hold is disabled by default; every enabled-mode test sets
``IPR_CHINA_SOURCE_USE_HOLD`` to exactly "true" inside the test, and the
"unset" tests pin that merging the module changes nothing.

Covered, with the hold enabled:
  * held sources make no adapter call and report a non-failure hold;
  * no title or body reaches a model through relevance screening, the daily
    analysis queue (including already-stored backlog) or headline translation;
  * the storage seam refuses a held source's write instead of reporting a
    duplicate;
  * stored rows are untouched and unheld China sources and other desks run on.
"""

import json
import os
import sqlite3
import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

from core import china_source_use_hold as hold
from core.collection import status as st
from tests.integration.test_pipeline_run import (
    PipelineRunCase, article, scraper_factory)

HELD = ("global_times_mil", "mod_china", "pla_daily")
UNHELD_CHINA = ("xinhua_mil", "china_mil_online")


def enabled():
    return mock.patch.dict(os.environ, {hold.HOLD_ENV: "true"})


def unset():
    env = dict(os.environ)
    env.pop(hold.HOLD_ENV, None)
    return mock.patch.dict(os.environ, env, clear=True)


class CountingAnalyzer:
    """Records every model-bound call; none may happen for a held source."""

    def __init__(self):
        self.calls = []

    def score_relevance(self, title, body, **kwargs):
        self.calls.append(("score_relevance", title, body))
        return 0.9, "scripted"

    def analyze_record(self, title, body, profile=None):
        # A scripted "not relevant" verdict. A failure result would make the
        # run a total analysis failure, which writes the tracked
        # billing-failure marker.
        self.calls.append(("analyze_record", title, body))
        return {"relevance_score": 0.1, "relevance_reasoning": "scripted",
                "passed_relevance": False, "model_id": "scripted",
                "prompt_version": "scripted"}

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            raise AssertionError("unexpected model call: %s" % name)
        return record


class TestModule(unittest.TestCase):

    def test_off_unless_exactly_true(self):
        for value in (None, "", "True", "TRUE", "1", "yes", "false", " true"):
            env = {} if value is None else {hold.HOLD_ENV: value}
            with mock.patch.dict(os.environ, env, clear=False):
                if value is None:
                    os.environ.pop(hold.HOLD_ENV, None)
                self.assertFalse(hold.hold_enabled(), value)
                self.assertFalse(hold.is_held_source("pla_daily"), value)

    def test_exactly_the_three_host_slugs(self):
        with enabled():
            for slug in HELD:
                self.assertTrue(hold.is_held_source(slug), slug)
            for slug in UNHELD_CHINA + ("sg_mindef_releases", "kr_mnd", None, ""):
                self.assertFalse(hold.is_held_source(slug), slug)

    def test_hold_detail_is_stable_and_distinguishable(self):
        detail = hold.hold_detail("mod_china")
        self.assertTrue(detail.startswith(hold.HOLD_DETAIL_PREFIX))
        self.assertIn("mod_china", detail)

    def test_disabled_path_performs_no_lookup(self):
        calls = []
        with unset():
            self.assertEqual(hold.held_article_ids(calls.append), set())
        self.assertEqual(calls, [])

    def test_enabled_collects_ids_for_each_held_slug_only(self):
        ids = {"pla_daily": {1, 2}, "mod_china": {3}, "global_times_mil": set(),
               "xinhua_mil": {99}}
        with enabled():
            self.assertEqual(hold.held_article_ids(lambda s: ids[s]), {1, 2, 3})

    def test_assert_not_held(self):
        with unset():
            hold.assert_not_held("pla_daily")
        with enabled():
            hold.assert_not_held("xinhua_mil")
            with self.assertRaises(hold.SourceUseHold):
                hold.assert_not_held("pla_daily")


class TestRelevanceScreening(unittest.TestCase):

    def arts(self):
        return [
            {"url": "u1", "source_slug": "pla_daily",
             "title_original": "标题一", "text_original": "正文一"},
            {"url": "u2", "source_slug": "mod_china",
             "title_original": "标题二", "text_original": "正文二"},
            {"url": "u3", "source_slug": "global_times_mil",
             "title_original": "标题三", "text_original": "正文三"},
            {"url": "u4", "source_slug": "xinhua_mil",
             "title_original": "标题四", "text_original": "正文四"},
        ]

    def test_held_titles_and_bodies_never_reach_the_model(self):
        from processing.relevance import llm_relevance_check
        analyzer = CountingAnalyzer()
        with enabled():
            results = llm_relevance_check(self.arts(), analyzer)
        sent = [c for c in analyzer.calls if c[0] == "score_relevance"]
        self.assertEqual([c[1] for c in sent], ["标题四"])
        by_url = {a["url"]: (score, why) for a, score, why in results}
        self.assertEqual(len(results), 4)
        for url in ("u1", "u2", "u3"):
            self.assertEqual(by_url[url][0], 0.0)
            self.assertTrue(by_url[url][1].startswith("held:"))
        self.assertEqual(by_url["u4"][0], 0.9)

    def test_unset_scores_every_china_source_as_before(self):
        from processing.relevance import llm_relevance_check
        analyzer = CountingAnalyzer()
        with unset():
            results = llm_relevance_check(self.arts(), analyzer)
        self.assertEqual(len(analyzer.calls), 4)
        self.assertTrue(all(score == 0.9 for _, score, _ in results))


class TestStorageSeam(PipelineRunCase):

    def record(self, slug="pla_daily", url="http://www.81.cn/x/store1.html"):
        rec = article(url)
        rec["source_slug"] = slug
        rec["content_hash"] = "hash-" + slug
        return rec

    def count(self):
        con = sqlite3.connect(str(self.db_path))
        try:
            return con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        finally:
            con.close()

    def test_enabled_refuses_held_write_instead_of_reporting_duplicate(self):
        import storage.db as db
        db.init_db()
        run_id = db.start_scrape_run()
        with enabled():
            with self.assertRaises(hold.SourceUseHold):
                db.insert_article(self.record("pla_daily"), run_id)
            with self.assertRaises(hold.SourceUseHold):
                db.insert_article(self.record("mod_china"), run_id)
        self.assertEqual(self.count(), 0)

    def test_unset_stores_as_before(self):
        import storage.db as db
        db.init_db()
        run_id = db.start_scrape_run()
        with unset():
            self.assertIsNotNone(db.insert_article(self.record("pla_daily"), run_id))
        self.assertEqual(self.count(), 1)


class TestTitleTranslationCandidates(unittest.TestCase):

    def test_held_sources_are_not_candidates_but_others_are(self):
        from storage.title_translation import candidates
        from tests.test_china_title_translation import fixture
        con = sqlite3.connect(":memory:")
        fixture(con)
        con.executescript("""
            UPDATE sources SET slug = 'pla_daily' WHERE id = 1;
            UPDATE sources SET slug = 'xinhua_mil' WHERE id = 4;
        """)
        with unset():
            before = {r["id"] for r in candidates(con)}
        with enabled():
            after = {r["id"] for r in candidates(con)}
        held_ids = {r[0] for r in con.execute(
            "SELECT id FROM articles WHERE source_id = 1")}
        self.assertTrue(held_ids & before, "fixture must offer held-source rows")
        self.assertFalse(after & held_ids)
        self.assertEqual(after, before - held_ids)
        # Nothing was written by merely enumerating candidates.
        self.assertEqual(con.execute(
            "SELECT COUNT(*) FROM articles WHERE title_english IS NOT NULL").fetchone()[0],
            1)

    def test_single_article_lookup_is_also_held(self):
        from storage.title_translation import candidates
        from tests.test_china_title_translation import fixture
        con = sqlite3.connect(":memory:")
        fixture(con)
        con.execute("UPDATE sources SET slug = 'pla_daily' WHERE id = 1")
        with enabled():
            self.assertEqual(candidates(con, article_id=1), [])


class TestBackfillScript(unittest.TestCase):

    def test_held_records_are_dropped_from_the_manual_backlog(self):
        from scripts.backfill_unscored import _without_held_desks
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.executescript("""
            CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
            CREATE TABLE articles(id INTEGER PRIMARY KEY, source_id INTEGER);
            INSERT INTO sources VALUES (1,'pla_daily','china'),(2,'xinhua_mil','china'),
                                       (3,'mod_china','china');
            INSERT INTO articles VALUES (10,1),(11,2),(12,3);
        """)
        rows = [{"id": 10}, {"id": 11}, {"id": 12}]
        with unset():
            self.assertEqual([r["id"] for r in _without_held_desks(con, rows)],
                             [10, 11, 12])
        with enabled():
            self.assertEqual([r["id"] for r in _without_held_desks(con, rows)], [11])


class TestManualModelScripts(unittest.TestCase):
    """Operator-run scripts that send stored text to a model."""

    SCHEMA = """
        CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
        CREATE TABLE articles(id INTEGER PRIMARY KEY, source_id INTEGER, url TEXT,
            title_original TEXT, text_original TEXT, title_english TEXT,
            published_date TEXT, passed_relevance INTEGER, relevance_score REAL,
            relevance_reasoning TEXT, processing_state TEXT);
        INSERT INTO sources VALUES (1,'pla_daily','china'),(2,'xinhua_mil','china'),
                                   (3,'global_times_mil','china'),(4,'mod_china','china'),
                                   (5,'china_mil_online','china');
    """

    def db(self):
        import tempfile
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        con = sqlite3.connect(handle.name)
        con.executescript(self.SCHEMA)
        for ident in range(1, 6):
            con.execute(
                "INSERT INTO articles(id, source_id, url, title_original, text_original,"
                " title_english, passed_relevance) VALUES (?,?,?,?,?,?,1)",
                (ident, ident, "https://x.example/%d" % ident, "t", "body" * 50, None))
        con.commit()
        con.close()
        return handle.name

    def test_backfill_translations_skips_held_publishers_only_when_enabled(self):
        from scripts import backfill_translations as bt
        path = self.db()
        with mock.patch.object(bt, "DB_PATH", path):
            with unset():
                self.assertEqual(sorted(r["id"] for r in bt.fetch_stuck()), [1, 2, 3, 4, 5])
            with enabled():
                self.assertEqual(sorted(r["id"] for r in bt.fetch_stuck()), [2, 5])

    def test_rescreen_desk_never_lists_held_publishers_for_a_model(self):
        from scripts import rescreen_desk as rd
        con = sqlite3.connect(self.db())
        con.row_factory = sqlite3.Row
        self.addCleanup(con.close)
        with unset():
            self.assertEqual([r["id"] for r in rd.desk_records(con, "china")], [1, 2, 3, 4, 5])
        with enabled():
            self.assertEqual([r["id"] for r in rd.desk_records(con, "china")], [2, 5])


class TestPipeline(PipelineRunCase):
    """Through the real pipeline.run() on a temporary database."""

    def adapters(self, calls):
        def factory(slug, url):
            base = scraper_factory(urls=[url], pages={url: "<html/>"},
                                   parsed={url: dict(article(url), source_slug=slug)})

            class Tracked(base):
                def get_article_urls(inner):
                    calls.append(slug)
                    return super().get_article_urls()
            return Tracked
        adapters = {slug: factory(slug, "http://example.test/%s/a1.html" % slug)
                    for slug in HELD + UNHELD_CHINA}
        return adapters

    def stored(self):
        con = sqlite3.connect(str(self.db_path))
        try:
            return {r[0]: r[1] for r in con.execute(
                "SELECT s.slug, COUNT(*) FROM articles a JOIN sources s "
                "ON s.id = a.source_id GROUP BY s.slug")}
        finally:
            con.close()

    def test_enabled_makes_no_request_and_stores_nothing_for_held_sources(self):
        calls = []
        with enabled():
            self.run_pipeline(self.adapters(calls))
        self.assertEqual(sorted(set(calls)), sorted(UNHELD_CHINA))
        res = self.results()
        for slug in HELD:
            self.assertEqual(res[slug]["status"], st.SKIPPED_DISABLED, slug)
            self.assertEqual(res[slug]["is_failure"], 0, slug)
            self.assertTrue(res[slug]["error_detail"].startswith(
                hold.HOLD_DETAIL_PREFIX), slug)
            self.assertEqual((res[slug]["references_discovered"], res[slug]["fetched"],
                              res[slug]["new_documents"]), (0, 0, 0))
        for slug in UNHELD_CHINA:
            self.assertNotEqual(res[slug]["status"], st.SKIPPED_DISABLED, slug)
        stored = self.stored()
        for slug in HELD:
            self.assertNotIn(slug, stored)

    def test_unset_collects_every_source_as_before(self):
        calls = []
        with unset():
            self.run_pipeline(self.adapters(calls))
        self.assertEqual(sorted(set(calls)), sorted(HELD + UNHELD_CHINA))
        for slug, row in self.results().items():
            self.assertNotEqual(row["status"], st.SKIPPED_DISABLED, slug)

    def test_a_held_run_is_not_reported_as_failed_or_as_a_clean_empty_run(self):
        with enabled():
            self.run_pipeline({s: scraper_factory(urls=[]) for s in HELD},
                              sources=list(HELD))
        res = self.results()
        for slug in HELD:
            self.assertNotEqual(res[slug]["status"], st.OK_NO_PUBLICATIONS, slug)
            self.assertEqual(res[slug]["status"], st.SKIPPED_DISABLED, slug)
            self.assertEqual(res[slug]["is_failure"], 0, slug)

    def test_a_hold_alone_does_not_degrade_the_run(self):
        adapters = {s: scraper_factory(urls=[]) for s in HELD}
        adapters["china_mil_online"] = scraper_factory(urls=[])
        with enabled():
            self.run_pipeline(adapters)
        self.assertEqual(self.run_status(), "completed")

    def test_a_real_failure_elsewhere_still_degrades_a_held_run(self):
        adapters = {s: scraper_factory(urls=[]) for s in HELD}
        adapters["china_mil_online"] = scraper_factory(
            listing_exc=RuntimeError("connection reset"))
        with enabled():
            self.run_pipeline(adapters)
        res = self.results()
        self.assertEqual(res["china_mil_online"]["is_failure"], 1)
        for slug in HELD:
            self.assertEqual(res[slug]["status"], st.SKIPPED_DISABLED, slug)
        self.assertEqual(self.run_status(), "degraded")

    def seed(self, slug, n=2, passed=None):
        # First run creates the source rows from the manifests.
        self.run_pipeline({"china_mil_online": scraper_factory(urls=[])})
        con = sqlite3.connect(str(self.db_path))
        sid = con.execute("SELECT id FROM sources WHERE slug=?", (slug,)).fetchone()[0]
        ids = []
        for i in range(n):
            cur = con.execute(
                "INSERT INTO articles (source_id, url, title_original, "
                "text_original, published_date, content_hash, scraped_at, "
                "passed_relevance) VALUES (?,?,?,?,?,?,datetime('now'),?)",
                (sid, "http://example.test/%s/seed%d.html" % (slug, i),
                 "%s 解放军演习 %d" % (slug, i), "%s 解放军 演习 正文 %d" % (slug, i), "2026-05-01",
                 "hash-%s-%d" % (slug, i), passed))
            ids.append(cur.lastrowid)
        con.commit()
        con.close()
        return ids

    def snapshot(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(
                "SELECT * FROM articles ORDER BY id")]
        finally:
            con.close()

    def run_with_analysis(self, analyzer):
        from tests.test_desk_scoped_screening import FakeClient  # noqa: F401
        import sys
        from functools import partial
        from core import dossiers
        actual = dossiers.load_dossiers
        loader = partial(actual, source_dir=self.tmp / "dossiers")
        try:
            with mock.patch.object(dossiers, "load_dossiers", side_effect=loader), \
                    mock.patch.object(self.pipeline, "ANTHROPIC_API_KEY", "test-key"), \
                    mock.patch("analysis.analyzer.Analyzer", return_value=analyzer), \
                    mock.patch.object(self.pipeline, "_write_billing_failure_marker"), \
                    mock.patch.object(self.pipeline, "_record_llm_usage"), \
                    self.assertLogs("pipeline", level="INFO") as logs:
                try:
                    self.run_pipeline({"china_mil_online": scraper_factory(urls=[])},
                                      no_analysis=False)
                except SystemExit:
                    pass
        finally:
            preview = sys.modules.get("generate_preview")
            if preview is not None:
                preview.load_dossiers = actual
        return "\n".join(logs.output)

    def test_stored_backlog_is_never_queued_for_a_model(self):
        for slug in HELD:
            self.seed(slug)
        before = self.snapshot()
        analyzer = CountingAnalyzer()
        with enabled():
            log = self.run_with_analysis(analyzer)
        self.assertEqual([c for c in analyzer.calls if c[0] == "score_relevance"], [])
        self.assertEqual(analyzer.calls, [])
        self.assertIn("interim source-use hold", log)
        self.assertEqual(self.snapshot(), before, "existing rows must be untouched")

    def test_unset_still_queues_the_same_backlog(self):
        self.seed("pla_daily")
        analyzer = CountingAnalyzer()
        with unset():
            log = self.run_with_analysis(analyzer)
        self.assertNotIn("interim source-use hold", log)
        self.assertTrue(analyzer.calls, "the unheld path must still screen the backlog")

    def test_an_unheld_china_source_is_still_processed_while_held(self):
        self.seed("pla_daily")
        self.seed("xinhua_mil")
        analyzer = CountingAnalyzer()
        with enabled():
            self.run_with_analysis(analyzer)
        sent = [c for c in analyzer.calls if c[0] in ("score_relevance", "analyze_record")]
        self.assertTrue(sent, "the unheld China source must still reach the model")
        for _, title, body in sent:
            self.assertTrue(title.startswith("xinhua_mil"), title)
            self.assertTrue(body.startswith("xinhua_mil"), body)


class TestSharedDispatchComposition(unittest.TestCase):
    """The hold and the shared governed-admission dispatch must not overlap."""

    def test_no_held_slug_is_a_governed_manual_admission(self):
        import pipeline
        self.assertFalse(
            set(hold.HELD_SOURCE_SLUGS) & set(pipeline._governed_admissions()),
            "a held China source must not also be dispatched by the governed path")


class TestBriefsWriters(unittest.TestCase):
    """Stored text must not reach the Sunday/weekly briefs model while held."""

    def rows(self, published="2026-10-08"):
        from tests.test_sunday_source_offer_audit import row
        out = []
        for ident, desk, slug in (
                (1, "china", "pla_daily"), (2, "china", "global_times_mil"),
                (3, "china", "mod_china"), (4, "china", "xinhua_mil"),
                (5, "china", "china_mil_online"), (6, "singapore", "official")):
            r = row(ident, desk, published, analyzed=True, passed=1)
            r["source_slug"] = slug
            out.append(r)
        return out

    def sunday(self, rows, inventory=None):
        from scripts.sunday_briefs_auto_writer import choose_evidence
        from tests.test_sunday_source_offer_audit import sidecar, SAT
        with mock.patch("scripts.sunday_briefs_auto_writer.read_only"), mock.patch(
                "scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                return_value=rows):
            return choose_evidence(sidecar(rows), as_of=SAT, discovery_inventory=inventory)

    def weekly(self, rows):
        from scripts.author_brief import build_draft
        from scripts.weekly_briefs_auto_writer import choose_evidence
        draft = build_draft(rows, desks=["china", "singapore"],
                            week_start="2026-09-27", week_ending="2026-10-03")
        with mock.patch("scripts.weekly_briefs_auto_writer.read_only"), mock.patch(
                "scripts.weekly_briefs_auto_writer.get_articles_for_desks",
                return_value=rows):
            return choose_evidence(draft, as_of="2026-10-02")

    @staticmethod
    def ids(chosen):
        return sorted(pair[0]["id"] for pair in chosen)

    def test_sunday_enabled_offers_no_held_text_but_keeps_the_rest(self):
        with enabled():
            self.assertEqual(self.ids(self.sunday(self.rows())), [4, 5, 6])

    @staticmethod
    def _without_identity(rows):
        bare = []
        for r in rows:
            r = dict(r)
            del r["source_slug"]
            bare.append(r)
        return bare

    def test_enabled_hold_excludes_rows_with_absent_source_identity_from_sunday(self):
        # Unknown provenance must never bypass an enabled hold at the Briefs
        # model boundary: a row with no ``source_slug`` is not offered to the
        # model, in the legacy path or in complete-discovery mode.
        from scripts.sunday_briefs_auto_writer import choose_evidence
        from tests.test_sunday_source_offer_audit import sidecar, SAT
        full = self.rows()
        card = sidecar(full)
        bare = self._without_identity(full)
        inventory = []
        with enabled(), mock.patch("scripts.sunday_briefs_auto_writer.read_only"), \
                mock.patch("scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                           return_value=bare):
            self.assertEqual(
                choose_evidence(card, as_of=SAT, discovery_inventory=inventory), [])
            with self.assertRaisesRegex(ValueError, "fewer than two desks"):
                choose_evidence(card, as_of=SAT)
        self.assertEqual(
            sorted(e["id"] for e in inventory if e["reason"] == "source_use_hold"),
            [1, 2, 3, 4, 5, 6])

    def test_enabled_hold_excludes_rows_with_absent_source_identity_from_weekly(self):
        from scripts.author_brief import build_draft
        from scripts.weekly_briefs_auto_writer import choose_evidence
        full = self.rows("2026-09-30")
        draft = build_draft(full, desks=["china", "singapore"],
                            week_start="2026-09-27", week_ending="2026-10-03")
        bare = self._without_identity(full)
        with enabled(), mock.patch("scripts.weekly_briefs_auto_writer.read_only"), \
                mock.patch("scripts.weekly_briefs_auto_writer.get_articles_for_desks",
                           return_value=bare), \
                self.assertRaisesRegex(ValueError, "fewer than two desks"):
            choose_evidence(draft, as_of="2026-10-02")

    def test_null_and_empty_source_slug_are_unidentified_only_while_enabled(self):
        with enabled():
            for value in (None, "", 0):
                self.assertTrue(hold.is_held_row({"source_slug": value}), value)
            self.assertTrue(hold.is_held_row({}))
            self.assertFalse(hold.is_held_row({"source_slug": "xinhua_mil"}))
        with unset():
            for row in ({}, {"source_slug": None}, {"source_slug": "pla_daily"}):
                self.assertFalse(hold.is_held_row(row), row)

    def test_relevance_model_boundary_fails_closed_without_source_identity(self):
        from processing.relevance import llm_relevance_check
        analyzer = CountingAnalyzer()
        art = {"url": "u", "title_original": "t", "text_original": "b"}
        with enabled():
            out = llm_relevance_check([art], analyzer)
        self.assertEqual(analyzer.calls, [])
        self.assertEqual(out[0][1], 0.0)
        self.assertIn("source-use hold", out[0][2])

    def test_sqlite_rows_are_filtered_by_source_slug(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        held, other = conn.execute(
            "SELECT 'pla_daily' AS source_slug UNION ALL SELECT 'xinhua_mil'").fetchall()
        with enabled():
            self.assertTrue(hold.is_held_row(held))
            self.assertFalse(hold.is_held_row(other))
        with unset():
            self.assertFalse(hold.is_held_row(held))

    def test_sunday_unset_offers_every_row_as_before(self):
        with unset():
            self.assertEqual(self.ids(self.sunday(self.rows())), [1, 2, 3, 4, 5, 6])

    def test_sunday_discovery_records_each_hold_in_the_inventory(self):
        from tests.test_sunday_story_discovery import source
        rows = []
        for ident, slug in ((1, "pla_daily"), (2, "xinhua_mil")):
            r = source(ident)
            r["source_slug"] = slug
            rows.append(r)
        out = []
        with enabled():
            chosen = self.sunday(rows, out)
        self.assertEqual(self.ids(chosen), [2])
        reasons = {e["id"]: e["reason"] for e in out}
        self.assertEqual(reasons[1], "source_use_hold")
        self.assertNotEqual(reasons[2], "source_use_hold")

    def test_weekly_enabled_offers_no_held_text_but_keeps_the_rest(self):
        with enabled():
            self.assertEqual(self.ids(self.weekly(self.rows("2026-09-30"))), [4, 5, 6])

    def test_weekly_unset_offers_every_row_as_before(self):
        with unset():
            self.assertEqual(self.ids(self.weekly(self.rows("2026-09-30"))), [1, 2, 3, 4, 5, 6])

    def test_held_china_alone_cannot_satisfy_the_cross_desk_gate(self):
        rows = [r for r in self.rows("2026-09-30") if r["id"] in (1, 2, 3, 6)]
        with enabled(), self.assertRaisesRegex(ValueError, "fewer than two desks"):
            self.weekly(rows)


class TestWorkflowWiring(unittest.TestCase):
    """A repo variable reaches a job only if the workflow maps it into env."""

    WORKFLOWS = (
        "daily_update.yml",
        "china_title_completion_batch.yml",
        "sunday_briefs_editorial_handoff.yml",
        "weekly_briefs_editorial_handoff.yml",
    )

    def test_every_model_spending_china_route_maps_the_switch(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for name in self.WORKFLOWS:
            text = (root / name).read_text(encoding="utf-8")
            self.assertIn(
                "IPR_CHINA_SOURCE_USE_HOLD: ${{ vars.IPR_CHINA_SOURCE_USE_HOLD }}",
                text, name,
            )
            # Mapped from the variable only: never hard-coded on or off.
            self.assertNotIn("IPR_CHINA_SOURCE_USE_HOLD: 'true'", text, name)
            self.assertNotIn("IPR_CHINA_SOURCE_USE_HOLD: true", text, name)


if __name__ == "__main__":
    unittest.main()
