"""Korea MND admission inside the shared Daily (pipeline.py).

The MND source is `access_method: manual`: the Daily never fetches it. Its
records enter `articles` only through the governed, source-pinned bridge
(core/korea_corpus_bridge.py), which the pipeline runs after storage and before
the queues are read. These tests pin:

  * every status the governed step can report, and that it never raises;
  * zero network for a manual source (no adapter is ever built);
  * the owner switch (KOREA_DAILY_AUTOMATION_ENABLED) is the only way the
    bridge runs, and a dry run never runs it;
  * the bridge through the pipeline's real `db.get_conn()` path, exactly once;
  * through the real pipeline.run(): an inactive desk is reported, not hidden,
    and China collection is unaffected.

Everything runs on scratch databases; nothing touches pla_watch.db.
"""
import dataclasses
import functools
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pipeline
from core import korea_corpus_bridge as bridge
from core.collection import status as st
from core.korea_published_originals import INDEX, ORIGINAL_DIR, PublishedKoreaHold
from migrations.runner import apply_all, connect
from tests.test_korea_corpus_bridge import LIVE, SHADOW, activate
from tests.test_migrations import build_legacy_db

SLUG = bridge.SOURCE_SLUG
ACTIVATED = (Path(__file__).resolve().parent.parent
             / "desks" / "korea" / "manifest.json").is_file()


class FakeRegistry:
    def __init__(self, desk="korea"):
        self.desk = desk
        self.adapters_built = []

    def get_source(self, slug):
        return SimpleNamespace(desk_id=self.desk, access_method="manual")

    def get_adapter(self, slug):              # must never be reached
        self.adapters_built.append(slug)
        raise AssertionError("adapter built for a manual source")


def receipt(**kw):
    base = {"bridge_version": bridge.BRIDGE_VERSION, "admitted": [],
            "held": [], "withdrawn": [], "excluded": [], "unchanged": [],
            "deferred": []}
    base.update(kw)
    return base


class TestGovernedManualSourceStatuses(unittest.TestCase):
    def run_step(self, admit, enabled=True, dry_run=False, slugs=(SLUG,)):
        errors = []
        with mock.patch("config.KOREA_DAILY_AUTOMATION_ENABLED", enabled), \
                mock.patch.object(pipeline, "_governed_admissions",
                                  return_value={SLUG: admit} if admit else {}):
            results = pipeline.run_governed_manual_sources(
                list(slugs), 7, FakeRegistry(), errors, dry_run=dry_run)
        return results, errors

    def never(self, run_id):
        raise AssertionError("bridge ran")

    def test_manual_source_without_governed_admission(self):
        [r], errors = self.run_step(None, slugs=("some_manual_source",))
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertIn("no governed admission", r.error_detail)
        self.assertEqual(errors, [])

    def test_inactive_switch_never_runs_the_bridge(self):
        [r], errors = self.run_step(self.never, enabled=False)
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertIn("awaiting owner activation", r.error_detail)
        self.assertEqual((r.desk_id, errors), ("korea", []))

    def test_dry_run_never_runs_the_bridge(self):
        [r], _ = self.run_step(self.never, dry_run=True)
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertIn("dry run", r.error_detail)

    def test_admissions_are_new_documents(self):
        rec = receipt(admitted=[{"source_identity": "korea-policy:156784297",
                                 "article_id": 9}],
                      unchanged=["korea-policy:156785286"])
        [r], errors = self.run_step(lambda run_id: rec)
        self.assertEqual((r.status, r.new_documents, r.duplicates),
                         (st.OK, 1, 1))
        self.assertEqual(errors, [])

    def test_replay_is_all_duplicates(self):                    # scenario 2
        rec = receipt(unchanged=["korea-policy:156784297"])
        [r], _ = self.run_step(lambda run_id: rec)
        self.assertEqual((r.status, r.new_documents, r.duplicates),
                         (st.OK_ALL_DUPLICATES, 0, 1))

    def test_zero_new_day(self):                                # scenario 9 (zero-new)
        rec = receipt(excluded=[{"source_identity": "korea-policy:156785161",
                                 "reason": "excluded_research_hold"}])
        [r], errors = self.run_step(lambda run_id: rec)
        self.assertEqual(r.status, st.OK_NO_PUBLICATIONS)
        self.assertEqual(errors, [])

    def test_bridge_hold_is_a_reported_source_failure(self):     # scenario 5, 13
        def held(run_id):
            raise bridge.BridgeHold("korea_original_text_mismatch")
        [r], errors = self.run_step(held)
        self.assertEqual(r.status, st.ADAPTER_ERROR)
        self.assertEqual(r.error_detail,
                         "korea_corpus_bridge: korea_original_text_mismatch")
        self.assertEqual(len(errors), 1)

    def test_release_index_hold_is_a_reported_source_failure(self):
        def held(run_id):
            raise PublishedKoreaHold("korea_release_index_invalid")
        [r], _ = self.run_step(held)
        self.assertEqual(r.status, st.ADAPTER_ERROR)

    def test_unexpected_error_reports_type_only(self):
        def boom(run_id):
            raise ValueError("private text that must not be logged")
        with self.assertLogs("pipeline", level="ERROR") as logs:
            [r], errors = self.run_step(boom)
        self.assertEqual(r.error_detail, "korea_corpus_bridge: ValueError")
        self.assertNotIn("private text", "\n".join(logs.output + errors))

    def test_held_items_are_logged_by_identity_and_code_only(self):
        rec = receipt(held=[{"source_identity": "korea-policy:156785999",
                             "reason": "korea_heading_unidentifiable"}])
        with self.assertLogs("pipeline", level="WARNING") as logs:
            self.run_step(lambda run_id: rec)
        self.assertIn("korea-policy:156785999 korea_heading_unidentifiable",
                      "\n".join(logs.output))


class TestProcessingCapInput(unittest.TestCase):
    def test_cap_is_fail_safe(self):
        import config
        cap = config._korea_processing_cap
        self.assertEqual([cap("4"), cap("0"), cap("99"), cap("-3"), cap(""),
                          cap("four"), cap(None)], [4, 0, 20, 0, 0, 0, 0])


class TestAdmissionThroughPipelineConnection(unittest.TestCase):
    """`_admit_korea_mnd` through the real storage.db.get_conn() path."""

    def setUp(self):
        import storage.db as sdb
        self.tmp = tempfile.TemporaryDirectory()
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
        self.addCleanup(self.tmp.cleanup)
        # Real released index and texts; exclusions lifted and the desk
        # treated as live only inside this scratch run.
        # Pin this four-release scenario; later official releases are tested
        # through the separate real-index admission path below.
        from tests.test_korea_corpus_bridge import released
        fixture = root / "korea-four-release-index.json"
        fixture.write_text(json.dumps({
            "schema": "ipr-korea-public-original-text-index/1",
            "records": released(),
        }), encoding="utf-8")
        self.apply = functools.partial(
            bridge.apply, index=fixture, original_dir=self.originals,
            excluded={}, registry=LIVE)

    def seed_metadata(self):
        from tests.test_korea_corpus_bridge import admit_metadata, released
        conn = sqlite3.connect(str(self.db_path))
        for rec in released():
            admit_metadata(conn, rec)
        conn.close()

    def ledger(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            return conn.execute(
                "SELECT source_identity, article_id, state FROM "
                "korea_corpus_admissions ORDER BY source_identity").fetchall()
        finally:
            conn.close()

    def test_admits_once_and_replays_as_unchanged(self):         # scenario 1, 2, 15
        self.seed_metadata()
        with mock.patch.object(bridge, "apply", self.apply):
            first = pipeline._admit_korea_mnd(1)
            ledger = self.ledger()
            second = pipeline._admit_korea_mnd(2)
        self.assertEqual(len(first["admitted"]), 4)
        self.assertEqual(len(second["admitted"]), 0)
        self.assertEqual(len(second["unchanged"]), 4)
        self.assertEqual(self.ledger(), ledger)
        self.assertTrue(all(state == "admitted" for _, _, state in ledger))

    def test_repository_defaults_admit_only_the_unreviewed_release(self):  # 6, 7, 8
        # The real exclusions: frozen baseline, the reviewed English releases
        # and the 156785161 research hold. 156785691 has only an unreviewed
        # English draft handoff, which does not exclude it.
        self.seed_metadata()
        live_only = functools.partial(bridge.apply, original_dir=self.originals,
                                      registry=LIVE)
        with mock.patch.object(bridge, "apply", live_only):
            rec = pipeline._admit_korea_mnd(1)
        self.assertEqual([a["source_identity"] for a in rec["admitted"]],
                         ["korea-policy:156785691"])
        excluded = {e["source_identity"]: e["reason"] for e in rec["excluded"]}
        self.assertEqual(excluded.get("korea-policy:156785286"),
                         "excluded_reviewed_english")
        self.assertNotIn("korea-policy:156785161",
                         [i for i, _, _ in self.ledger()])

    def test_repository_registry_refuses(self):                  # scenario 13
        if ACTIVATED:
            # After the owner activation the registry gate passes; with no
            # governed metadata in this database nothing is admitted.
            rec = pipeline._admit_korea_mnd(1)
            self.assertEqual(rec["admitted"], [])
            return
        with self.assertRaises(bridge.BridgeHold) as ctx:
            pipeline._admit_korea_mnd(1)
        self.assertIn(str(ctx.exception), {"korea_desk_not_live",
                                           "korea_source_not_activated"})


class TestRealPipelineRun(unittest.TestCase):
    """The governed step inside the real pipeline.run()."""

    def setUp(self):
        from tests.integration.test_pipeline_run import (
            PipelineRunCase, scraper_factory)
        self.scraper_factory = scraper_factory
        self.case = PipelineRunCase("run")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.case.run_pipeline({"china_mil_online": scraper_factory(urls=[])})
        conn = sqlite3.connect(str(self.case.db_path))
        activate(conn)
        conn.close()

    def run_with_manual_source(self, enabled):
        """Run with a registry that also declares the manual MND source."""
        from core.registry import SourceRegistry
        import core.registry as reg
        case = self.case
        built = []

        class WithManual(SourceRegistry):
            def __init__(self):
                super().__init__()
                template = self.get_source("sg_mindef_releases")
                self._sources[SLUG] = dataclasses.replace(
                    template, slug=SLUG, desk_id="korea",
                    access_method="manual", adapter=None, language_tag="ko")

            def get_adapter(self, slug):
                built.append(slug)
                from adapters.legacy import LegacyScraperAdapter
                return LegacyScraperAdapter(
                    self.get_source(slug),
                    scraper_class=case_factory)

        case_factory = self.scraper_factory(urls=[])
        registry = WithManual()
        reg._DEFAULT = registry
        case.pipeline.get_registry = lambda refresh=False: registry
        from datetime import date
        with mock.patch("config.KOREA_DAILY_AUTOMATION_ENABLED", enabled):
            case.pipeline.run(sources=["china_mil_online", SLUG],
                              target_date=date(2026, 5, 10), dry_run=False,
                              no_analysis=True)
        return built

    def test_inactive_switch_is_skipped_and_china_runs(self):     # scenario 11
        built = self.run_with_manual_source(enabled=False)
        self.assertEqual(built, ["china_mil_online"])
        results = self.case.results()
        self.assertEqual(results[SLUG]["status"], st.SKIPPED_DISABLED)
        self.assertNotEqual(self.case.run_status(), "failed")

    def test_switch_on_without_live_desk_is_reported(self):      # scenario 13
        with mock.patch("core.desk_registry.get_desk_registry",
                        return_value=SHADOW):
            built = self.run_with_manual_source(enabled=True)
        self.assertEqual(built, ["china_mil_online"])
        result = self.case.results()[SLUG]
        self.assertEqual(result["status"], st.ADAPTER_ERROR)
        self.assertTrue(result["error_detail"].startswith(
            "korea_corpus_bridge: korea_"))
        conn = sqlite3.connect(str(self.case.db_path))
        try:
            n = conn.execute("SELECT count(*) FROM korea_corpus_admissions"
                             ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
