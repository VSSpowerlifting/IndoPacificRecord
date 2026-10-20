"""
Screening-profile resolution fails closed (processing/screening.py).

Until 2026-10-20 an unknown desk, an undeclared source and a missing slug all
resolved to the China profile, so a new desk's records would have been
screened against PLA vocabulary and, on a pass, translated "from Chinese".
DECISION_LOG 2026-10-19 rules that China's prompts are never the default for
an unregistered desk.

These tests pin three things:

  * Every registered desk and source family resolves exactly as before. The
    expected values are literals recorded from the pre-change code, not read
    back from the module under test.
  * An unregistered desk or source raises, and the helpers that hold such a
    record out (registered_profile, the keyword stage, the audits, the
    backfills, rescreen_desk) do so without consulting the China profile.
  * In the real pipeline.run(), a record of an unregistered desk gets no
    model call and stays awaiting screening, while a China record in the same
    run is screened as before.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_desk_scoped_screening import CN, SG, FakeClient, fake_analyzer

# Recorded from processing/screening.py on main 4509361d13, before this change.
SOURCE_DESKS = {
    "pla_daily": "china",
    "mod_china": "china",
    "xinhua_mil": "china",
    "global_times_mil": "china",
    "china_mil_online": "china",
    "sg_mindef_releases": "singapore",
}
REGISTERED_DESKS = {"china", "singapore", "korea"}


class TestRegisteredFamiliesResolveAsBefore(unittest.TestCase):

    def test_the_registered_desks_are_exactly_the_recorded_set(self):
        # A new profile must be added here deliberately, with its own
        # snapshot below (Vietnam: PR #834).
        from processing import screening
        self.assertEqual(set(screening._PROFILES), REGISTERED_DESKS)

    def test_each_desk_resolves_to_its_own_profile(self):
        from processing.screening import (CHINA_PROFILE, KOREA_PROFILE,
                                          SINGAPORE_PROFILE, profile_for_desk)
        self.assertIs(profile_for_desk("china"), CHINA_PROFILE)
        self.assertIs(profile_for_desk("singapore"), SINGAPORE_PROFILE)
        self.assertIs(profile_for_desk("korea"), KOREA_PROFILE)

    def test_each_declared_source_resolves_to_its_desk_and_profile(self):
        from processing.screening import (desk_for_source, profile_for_desk,
                                          profile_for_source, _desk_by_source)
        self.assertEqual(dict(_desk_by_source()), SOURCE_DESKS)
        for slug, desk in SOURCE_DESKS.items():
            self.assertEqual(desk_for_source(slug), desk, slug)
            self.assertIs(profile_for_source(slug), profile_for_desk(desk), slug)

    def test_each_profile_keeps_its_recorded_settings(self):
        from analysis.korea_prompts import ANALYSIS_VERSION, RELEVANCE_VERSION
        from analysis.prompts import (PROMPT_VERSION,
                                      SINGAPORE_ANALYSIS_PROMPT_VERSION,
                                      SINGAPORE_RELEVANCE_PROMPT_VERSION)
        from processing.screening import profile_for_desk
        expected = {
            "china": (True, True, True, PROMPT_VERSION, None),
            "singapore": (False, True, False, SINGAPORE_RELEVANCE_PROMPT_VERSION,
                          SINGAPORE_ANALYSIS_PROMPT_VERSION),
            "korea": (False, False, False, RELEVANCE_VERSION, ANALYSIS_VERSION),
        }
        for desk, settings in expected.items():
            p = profile_for_desk(desk)
            self.assertEqual(p.desk_id, desk)
            self.assertEqual((p.keyword_prefilter, p.daily_queue, p.translates,
                              p.prompt_version, p.analysis_prompt_version),
                             settings, desk)

    def test_china_keyword_stage_is_unchanged(self):
        from processing.relevance import (passes_desk_prefilter,
                                          passes_keyword_filter)
        for rec in CN.values():
            art = {"source_slug": rec["source_slug"],
                   "title_original": rec["title_original"],
                   "text_original": rec["text_original"]}
            self.assertEqual(passes_desk_prefilter(art),
                             passes_keyword_filter(art), rec["id"])


class TestUnregisteredDesksAreRefused(unittest.TestCase):

    def unprofiled_registry_desks(self):
        from core.desk_registry import get_desk_registry
        from processing import screening
        desks = set(get_desk_registry().slugs) - set(screening._PROFILES)
        self.assertTrue(desks, "every registry desk has a profile")
        return sorted(desks)

    def test_an_unknown_or_missing_desk_raises(self):
        from processing.screening import UnregisteredDeskError, profile_for_desk
        for desk in ["not_a_desk", None, ""] + self.unprofiled_registry_desks():
            with self.assertRaises(UnregisteredDeskError, msg=desk):
                profile_for_desk(desk)

    def test_an_undeclared_or_missing_source_raises(self):
        from processing.screening import (UnregisteredDeskError, desk_for_source,
                                          profile_for_source)
        for slug in ("not_a_source", "held_fixture_src", None, ""):
            self.assertIsNone(desk_for_source(slug), slug)
            with self.assertRaises(UnregisteredDeskError, msg=slug):
                profile_for_source(slug)

    def test_the_error_is_a_lookup_error_naming_the_desk(self):
        from processing.screening import UnregisteredDeskError, profile_for_desk
        self.assertTrue(issubclass(UnregisteredDeskError, LookupError))
        with self.assertRaisesRegex(UnregisteredDeskError, "'japan'"):
            profile_for_desk("japan")

    def test_registered_profile_returns_none_never_china(self):
        from processing.screening import CHINA_PROFILE, registered_profile
        self.assertIs(registered_profile("china"), CHINA_PROFILE)
        for desk in ["not_a_desk", None] + self.unprofiled_registry_desks():
            self.assertIsNone(registered_profile(desk), desk)

    def test_the_keyword_stage_does_not_apply_china_lists_to_an_unknown_source(self):
        # A record a China keyword list would reject still passes: it is
        # stored and held awaiting screening, never given a China verdict.
        from processing.relevance import (passes_desk_prefilter,
                                          passes_keyword_filter)
        art = {"source_slug": "not_a_source", "title_original": "Weather",
               "text_original": "Sunny with light winds."}
        self.assertFalse(passes_keyword_filter(art))
        with self.assertLogs("processing.relevance", level="WARNING") as logs:
            self.assertTrue(passes_desk_prefilter(art))
        self.assertIn("not_a_source", "\n".join(logs.output))

    def test_the_queue_audit_counts_an_unregistered_desk_as_held(self):
        from scripts.audit_analysis_queue_by_source import _daily_queue
        self.assertTrue(_daily_queue("china"))
        self.assertTrue(_daily_queue("singapore"))
        self.assertFalse(_daily_queue("korea"))
        for desk in ["not_a_desk", None] + self.unprofiled_registry_desks():
            self.assertFalse(_daily_queue(desk), desk)

    def test_rescreen_refuses_an_unregistered_desk(self):
        from scripts import rescreen_desk
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch("sys.stderr"), \
                self.assertRaises(SystemExit) as exit_:
            rescreen_desk.main(["plan", "--desk", "japan",
                                "--db", str(Path(tmp) / "none.db"),
                                "--out", str(Path(tmp) / "plan.json")])
        self.assertEqual(exit_.exception.code, 2)

    def test_the_backfills_skip_an_unregistered_desk(self):
        import scripts.backfill_translations as bt
        import scripts.backfill_unscored as bf
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "b.db"
            con = sqlite3.connect(str(db))
            con.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
                CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER,
                    url TEXT, title_original TEXT, text_original TEXT,
                    title_english TEXT, published_date TEXT,
                    passed_relevance INTEGER);
                INSERT INTO sources VALUES (1,'pla_daily','china'),
                                           (2,'jp_mod_releases','japan'),
                                           (3,'orphan_src',NULL);
                INSERT INTO articles VALUES
                    (1,1,'u1','t','b',NULL,'2026-09-05',NULL),
                    (2,2,'u2','t','b',NULL,'2026-09-05',NULL),
                    (3,3,'u3','t','b',NULL,'2026-09-05',NULL),
                    (4,1,'u4','t','b',NULL,'2026-09-05',1),
                    (5,2,'u5','t','b',NULL,'2026-09-05',1),
                    (6,3,'u6','t','b',NULL,'2026-09-05',1);
            """)
            con.commit()
            con.close()
            saved = bf.DB_PATH, bt.DB_PATH
            bf.DB_PATH = bt.DB_PATH = db
            try:
                self.assertEqual([r["id"] for r in bf.fetch_unscored()], [1])
                self.assertEqual([r["id"] for r in bt.fetch_stuck()], [4])
            finally:
                bf.DB_PATH, bt.DB_PATH = saved


class TestAnUnregisteredDeskIsHeldInTheDailyPipeline(unittest.TestCase):
    """Driven through the real pipeline.run() on a temporary database."""

    def setUp(self):
        from processing import screening
        from tests.integration.test_pipeline_run import (PipelineRunCase,
                                                         scraper_factory)
        self.case = PipelineRunCase("run")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.case.run_pipeline({"china_mil_online": scraper_factory(urls=[])})
        # Singapore's manifest still assigns sg_mindef_releases to the
        # singapore desk; with its profile withdrawn, that desk is unregistered.
        patcher = mock.patch.dict(
            screening._PROFILES,
            {k: v for k, v in screening._PROFILES.items() if k != "singapore"},
            clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def seed(self, slug, rec):
        con = sqlite3.connect(str(self.case.db_path))
        sid = con.execute("SELECT id FROM sources WHERE slug=?",
                          (slug,)).fetchone()[0]
        con.execute(
            "INSERT INTO articles (source_id, url, title_original, "
            "text_original, published_date, content_hash, scraped_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (sid, rec["url"], rec["title_original"], rec["text_original"],
             "2026-09-05", rec["url"]))
        con.commit()
        con.close()

    def verdict(self, url):
        con = sqlite3.connect(str(self.case.db_path))
        try:
            return con.execute("SELECT passed_relevance FROM articles WHERE url=?",
                               (url,)).fetchone()[0]
        finally:
            con.close()

    def test_no_model_call_for_it_and_china_is_screened_as_before(self):
        from analysis.prompts import SYSTEM_PROMPT
        from tests.integration.test_pipeline_run import scraper_factory
        self.seed("sg_mindef_releases", SG[4466])
        self.seed("china_mil_online", CN[4708])
        client = FakeClient(score=0.1, reasoning="scripted reject")
        with mock.patch.object(self.case.pipeline, "ANTHROPIC_API_KEY", "test-key"), \
                mock.patch("analysis.analyzer.Analyzer",
                           return_value=fake_analyzer(client)), \
                self.assertLogs("pipeline", level="INFO") as logs:
            self.case.run_pipeline({"china_mil_online": scraper_factory(urls=[])},
                                   no_analysis=False)
        log = "\n".join(logs.output)

        self.assertIn("Held out of the daily analysis queue: 1 record(s) of "
                      "desk 'singapore', which has no screening profile", log)
        # One call, for the China record, on the China system prompt; none
        # carries the Singapore record.
        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["system"][0]["text"], SYSTEM_PROMPT)
        self.assertNotIn(SG[4466]["title_original"],
                         call["messages"][0]["content"])
        self.assertIsNone(self.verdict(SG[4466]["url"]))
        self.assertEqual(self.verdict(CN[4708]["url"]), 0)


if __name__ == "__main__":
    unittest.main()
