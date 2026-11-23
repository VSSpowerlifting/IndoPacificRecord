"""
Source-liveness expectations must be derived, not hand-maintained.

The defect (2026-09-20). Xinhua Military was rewritten from a stub into a
working adapter on 2026-09-16 and delivered four new articles in the
2026-09-20 daily run. `scripts/check_source_liveness.py` still listed it in a
hand-maintained `KNOWN_INERT` dictionary whose stated reason — "returns [] by
design" — had been false for four days. INERT sources are exempt from every
recency threshold, so the one gate that exists to notice a source dying was
structurally blind to this one. Nothing failed; that is the point.

The repair is not a corrected list. It is the removal of the list: whether a
source may be silent now comes from the adapter's own offline `healthcheck()`
(NOT_IMPLEMENTED for a class declaring `IS_STUB`, SKIPPED_DISABLED for one the
manifest disables) and how long it may be silent comes from the manifest's
`silence_threshold_days`. Both already existed and were already correct about
Xinhua while the script's copy was wrong.

Offline: no network, no model calls. The live-corpus tests open the tracked
database read-only through `scripts.reconcile_db.read_only`, which copies.
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import SourceHealthResult         # noqa: E402
from core.registry import get_registry                          # noqa: E402
import scripts.check_source_liveness as liveness                # noqa: E402

TODAY = date(2026, 9, 20)


class FakeSource:
    def __init__(self, slug, silence_threshold_days=None, enabled=True):
        self.slug = slug
        self.silence_threshold_days = silence_threshold_days
        self.enabled = enabled


class FakeRegistry:
    """Just enough registry to drive `expectations()` without importing
    adapters or reading manifests."""

    def __init__(self, results, sources):
        self._results = results
        self._sources = {s.slug: s for s in sources}

    def healthcheck_all(self):
        return self._results

    def get_source(self, slug):
        return self._sources.get(slug)


def expectation_for(slug, status, detail=None, threshold=None):
    reg = FakeRegistry(
        [SourceHealthResult(slug, status, detail)],
        [FakeSource(slug, silence_threshold_days=threshold)],
    )
    return liveness.expectations(reg)[slug]


# ── The list is gone ──────────────────────────────────────────────────────────

class TheHandMaintainedListsAreGone(unittest.TestCase):

    def test_known_inert_no_longer_exists(self):
        """A second copy of a fact is a second chance to be wrong about it."""
        self.assertFalse(
            hasattr(liveness, "KNOWN_INERT"),
            "KNOWN_INERT is back. Inertness is declared by IS_STUB on the "
            "adapter and by `enabled` in the desk manifest; a source must not "
            "be exemptable by being named in this script.",
        )

    def test_hardcoded_threshold_table_no_longer_exists(self):
        self.assertFalse(
            hasattr(liveness, "SILENCE_THRESHOLD_DAYS"),
            "SILENCE_THRESHOLD_DAYS is back. Thresholds belong to the desk "
            "manifest, which core.collection.health already reads.",
        )

    def test_the_script_names_no_source_slug(self):
        """No per-source special case may be reintroduced as a literal."""
        source = (REPO_ROOT / "scripts" / "check_source_liveness.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        slugs = set(get_registry().slugs)
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        # Docstrings explain the history, so only executable code is scanned.
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc:
                    docstrings.add(doc)
        offenders = sorted((literals - docstrings) & slugs)
        self.assertEqual(
            [], offenders,
            "check_source_liveness.py special-cases %s by name" % offenders,
        )


# ── Xinhua specifically ───────────────────────────────────────────────────────

class XinhuaIsAWorkingSource(unittest.TestCase):

    def test_the_adapter_does_not_declare_itself_a_stub(self):
        from scraper.sources.xinhua_mil import XinhuaMilScraper
        self.assertFalse(getattr(XinhuaMilScraper, "IS_STUB", False))

    def test_the_registry_healthcheck_reports_it_collectible(self):
        result = next(
            r for r in get_registry().healthcheck_all()
            if r.source_slug == "xinhua_mil"
        )
        self.assertNotEqual(st.NOT_IMPLEMENTED, result.status)
        self.assertFalse(st.is_failure(result.status))

    def test_derived_expectation_is_not_inert(self):
        expected = liveness.expectations()["xinhua_mil"]
        self.assertFalse(expected.inert)
        self.assertFalse(expected.broken)

    def test_a_recent_result_passes(self):
        """The 2026-09-20 shape: collected on the day the run covers."""
        state, days, detail = liveness.classify(
            "xinhua_mil", 1, TODAY.isoformat(), TODAY, 7,
            liveness.expectations()["xinhua_mil"],
        )
        self.assertEqual("HEALTHY", state)
        self.assertEqual(0, days)
        self.assertIn("threshold", detail)

    def test_unexplained_silence_is_now_unhealthy(self):
        """Before the repair this returned INERT for any date at all."""
        silent_for = liveness.expectations()["xinhua_mil"].threshold + 1
        last_seen = date.fromordinal(TODAY.toordinal() - silent_for)
        state, days, _ = liveness.classify(
            "xinhua_mil", 1, last_seen.isoformat(), TODAY, 7,
            liveness.expectations()["xinhua_mil"],
        )
        self.assertEqual("UNHEALTHY", state)
        self.assertEqual(silent_for, days)

    def test_it_is_judged_by_the_same_standard_as_its_peers(self):
        """Same corpus shape, same verdict, for every implemented China source."""
        expected = liveness.expectations()
        peers = [s for s in get_registry().slugs_for_desk("china")
                 if not expected[s].inert and not expected[s].broken]
        self.assertIn("xinhua_mil", peers)

        verdicts = set()
        for slug in peers:
            silent_for = (expected[slug].threshold or 7) + 1
            last_seen = date.fromordinal(TODAY.toordinal() - silent_for)
            state, days, _ = liveness.classify(
                slug, 1, last_seen.isoformat(), TODAY, 7, expected[slug],
            )
            self.assertEqual(silent_for, days)
            verdicts.add(state)
        self.assertEqual({"UNHEALTHY"}, verdicts)


# ── Declared stubs still work ─────────────────────────────────────────────────

class DeclaredStubsAreStillExempt(unittest.TestCase):

    def test_a_not_implemented_adapter_is_inert(self):
        expected = expectation_for("someday_mil", st.NOT_IMPLEMENTED,
                                   "documented stub — no working path")
        self.assertTrue(expected.inert)
        state, days, detail = liveness.classify(
            "someday_mil", 0, None, TODAY, 7, expected)
        self.assertEqual("INERT", state)
        self.assertIsNone(days)
        self.assertIn("stub", detail)

    def test_a_manifest_disabled_source_is_inert(self):
        expected = expectation_for("paused_mil", st.SKIPPED_DISABLED,
                                   "disabled in desk manifest")
        self.assertTrue(expected.inert)
        state, _, detail = liveness.classify(
            "paused_mil", 0, None, TODAY, 7, expected)
        self.assertEqual("INERT", state)
        self.assertIn("disabled", detail)

    def test_an_inert_source_never_fails_the_gate(self):
        expected = expectation_for("someday_mil", st.NOT_IMPLEMENTED)
        state, _, _ = liveness.classify(
            "someday_mil", 0, None, TODAY, 7, expected)
        self.assertNotEqual("UNHEALTHY", state)

    def test_an_unimportable_adapter_is_unhealthy_not_inert(self):
        """The dangerous middle case: broken looks exactly like quiet."""
        expected = expectation_for("broken_mil", st.ADAPTER_ERROR,
                                   "No module named 'scraper.sources.gone'")
        self.assertFalse(expected.inert)
        self.assertTrue(expected.broken)
        state, _, detail = liveness.classify(
            "broken_mil", 900, TODAY.isoformat(), TODAY, 7, expected)
        self.assertEqual(
            "UNHEALTHY", state,
            "a source whose adapter will not import reported HEALTHY because "
            "yesterday's corpus was still warm",
        )
        self.assertIn("adapter unusable", detail)

    def test_a_manual_source_is_inert_only_until_its_first_admission(self):
        expected = liveness.Expectation(manual=True)
        state, _, detail = liveness.classify(
            "manual_mil", 0, None, TODAY, 7, expected)
        self.assertEqual("INERT", state)
        self.assertIn("nothing admitted yet", detail)
        state, _, _ = liveness.classify(
            "manual_mil", 3, "2026-09-05", TODAY, 7, expected)
        self.assertEqual("UNHEALTHY", state)        # 15d > 7d

    def test_a_policy_pause_is_reported_but_never_fails_the_gate(self):
        source = FakeSource("manual_mil", silence_threshold_days=7)
        source.access_method = "manual"
        reg = FakeRegistry([SourceHealthResult("manual_mil", st.OK, None)], [source])
        paused = liveness.expectations(reg, paused={"manual_mil": "switched off"})["manual_mil"]
        state, days, detail = liveness.classify(
            "manual_mil", 3, "2026-09-05", TODAY, 7, paused)
        self.assertEqual(("PAUSED", 15), (state, days))
        self.assertIn("switched off", detail)
        # Recent records are still simply healthy; the pause hides nothing.
        self.assertEqual("HEALTHY", liveness.classify(
            "manual_mil", 3, "2026-09-19", TODAY, 7, paused)[0])
        # Switch on again and the ordinary threshold applies at once.
        active = liveness.expectations(reg, paused={})["manual_mil"]
        self.assertEqual("UNHEALTHY", liveness.classify(
            "manual_mil", 3, "2026-09-05", TODAY, 7, active)[0])

    def test_a_pause_never_covers_a_fetched_or_broken_source(self):
        fetched = FakeSource("fetched_mil", silence_threshold_days=7)
        reg = FakeRegistry([SourceHealthResult("fetched_mil", st.OK, None)], [fetched])
        expected = liveness.expectations(reg, paused={"fetched_mil": "switched off"})
        self.assertIsNone(expected["fetched_mil"].paused)
        broken = liveness.Expectation(broken=True, reason="adapter unusable", paused="off")
        self.assertEqual("UNHEALTHY", liveness.classify(
            "manual_mil", 3, "2026-09-05", TODAY, 7, broken)[0])

    def test_the_pause_list_is_read_from_the_daily_policy(self):
        from core.daily_sources import attended_only
        from processing.daily_intake import load_policy
        off = {f for f, p in load_policy()["sources"].items()
               if not p["unattended_release"] or attended_only(f)}
        self.assertEqual(off, set(liveness.paused_by_policy()))

    def test_the_attended_pilot_gate_pauses_a_family_with_its_switches_on(self):
        """Switches on, gate still closed: no scheduled run may handle the
        family, so its silence is a pause, not a failure. A family with its
        switches on and no gate is judged by the ordinary threshold."""
        from unittest.mock import patch
        from processing import daily_intake
        policy = {"sources": {
            "gated_family": {"unattended_release": True},
            "open_family": {"unattended_release": True},
            "off_family": {"unattended_release": False}}}
        with patch.object(daily_intake, "load_policy", return_value=policy), \
                patch("core.daily_sources.ATTENDED_PILOT_ENV", {"gated_family": "X"}):
            paused = liveness.paused_by_policy()
        self.assertEqual(set(paused), {"gated_family", "off_family"})
        self.assertEqual(paused["gated_family"], "attended-pilot gate: no scheduled runs")

    def test_an_undeclared_slug_is_not_exempt(self):
        """A source configuration has forgotten is still expected to produce."""
        self.assertFalse(liveness.UNDECLARED.inert)
        state, _, _ = liveness.classify(
            "orphan_mil", 0, None, TODAY, 7, liveness.UNDECLARED)
        self.assertEqual("UNHEALTHY", state)


# ── Thresholds come from the manifest ─────────────────────────────────────────

class ThresholdsComeFromTheManifest(unittest.TestCase):

    def manifest_sources(self):
        data = json.loads(
            (REPO_ROOT / "desks" / "china" / "manifest.json").read_text(
                encoding="utf-8")
        )
        return {s["slug"]: s for s in data["sources"]}

    def test_every_derived_threshold_matches_its_manifest(self):
        declared = self.manifest_sources()
        expected = liveness.expectations()
        checked = 0
        for slug, entry in declared.items():
            self.assertEqual(
                entry.get("silence_threshold_days"), expected[slug].threshold,
                "threshold for %s diverged from its manifest" % slug,
            )
            checked += 1
        self.assertEqual(len(declared), checked)

    def test_a_manifest_threshold_is_honoured_over_the_flag(self):
        expected = expectation_for("slow_mil", st.OK, threshold=21)
        state, _, detail = liveness.classify(
            "slow_mil", 10, "2026-09-05", TODAY, 7, expected)
        self.assertEqual("HEALTHY", state)          # 15d < 21d
        self.assertIn("threshold 21d", detail)

    def test_no_manifest_threshold_falls_back_to_the_flag(self):
        expected = expectation_for("plain_mil", st.OK, threshold=None)
        state, _, detail = liveness.classify(
            "plain_mil", 10, "2026-09-05", TODAY, 7, expected)
        self.assertEqual("UNHEALTHY", state)        # 15d > 7d
        self.assertIn("threshold 7d", detail)


# ── Governed sources are judged by their recorded runs (2026-11-21) ──────────

def run_db(path, runs, with_run_tables=True):
    """A minimal database: one row per (slug, day, status, is_failure, detail).

    Governed rows leave `source_run_results.started_at` NULL, as the pipeline
    does; the date lives on `scrape_runs`.
    """
    import sqlite3
    conn = sqlite3.connect(str(path))
    conn.executescript(
        "CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, "
        "display_name TEXT, is_active INTEGER);"
        "CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER, "
        "scraped_at TEXT);")
    if with_run_tables:
        conn.executescript(
            "CREATE TABLE scrape_runs (id INTEGER PRIMARY KEY, started_at TEXT NOT NULL);"
            "CREATE TABLE source_run_results (id INTEGER PRIMARY KEY, "
            "scrape_run_id INTEGER NOT NULL, source_slug TEXT NOT NULL, "
            "status TEXT NOT NULL, is_failure INTEGER NOT NULL DEFAULT 0, "
            "started_at TEXT, error_detail TEXT);")
        for n, (slug, started, status, failed, detail) in enumerate(runs, start=1):
            conn.execute("INSERT INTO scrape_runs (id, started_at) VALUES (?, ?)",
                         (n, started))
            conn.execute(
                "INSERT INTO source_run_results (scrape_run_id, source_slug, status, "
                "is_failure, started_at, error_detail) VALUES (?, ?, ?, ?, NULL, ?)",
                (n, slug, status, failed, detail))
    conn.commit()
    conn.close()
    return path


class GovernedSourcesAreJudgedByTheirRuns(unittest.TestCase):
    """Governed families keep their records out of `articles`, so article
    count alone left every one INERT and exempt from every threshold."""

    MANUAL = liveness.Expectation(manual=True)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def history(self, *runs):
        db = run_db(Path(self.tmp.name) / "runs.db", runs)
        return liveness.governed_runs(db)

    def judge(self, runs, total=0, last_seen=None, expectation=None):
        return liveness.classify("gov_mil", total, last_seen, TODAY, 7,
                                 expectation or self.MANUAL, runs=runs)

    def test_recent_healthy_runs_are_healthy_not_inert(self):
        runs = self.history(
            ("gov_mil", "2026-09-18 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.OK_ALL_DUPLICATES, 0, None))
        state, days, detail = self.judge(runs["gov_mil"])
        self.assertEqual(("HEALTHY", 1), (state, days))
        self.assertIn("governed: last healthy run 2026-09-19 (1d ago, threshold 7d)", detail)
        self.assertIn("latest 2026-09-19 ok_all_duplicates", detail)

    def test_only_failures_in_the_window_are_unhealthy_with_the_error_shown(self):
        runs = self.history(
            ("gov_mil", "2026-09-05 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-17 23:00:00", st.FETCH_FAILURE, 1, "no signed envelope"),
            ("gov_mil", "2026-09-19 23:00:00", st.ACCESS_CHALLENGED, 1,
             "collection access_challenged (target 2026-09-18)"))
        state, days, detail = self.judge(runs["gov_mil"])
        self.assertEqual(("UNHEALTHY", 15), (state, days))
        self.assertIn("last healthy run 2026-09-05", detail)
        self.assertIn("latest 2026-09-19 access_challenged: collection access_challenged", detail)

    def test_a_source_that_has_only_ever_failed_is_unhealthy(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.ADAPTER_ERROR, 1, "daily_intake: mac_invalid"))
        state, days, detail = self.judge(runs["gov_mil"])
        self.assertEqual(("UNHEALTHY", None), (state, days))
        self.assertIn("no healthy run recorded", detail)
        self.assertIn("mac_invalid", detail)

    def test_no_runs_and_no_articles_is_inert(self):
        runs = self.history(("other_mil", "2026-09-19 23:00:00", st.OK, 0, None))
        self.assertNotIn("gov_mil", runs)
        state, days, detail = self.judge(runs.get("gov_mil", liveness.NO_GOVERNED_RUNS))
        self.assertEqual(("INERT", None), (state, days))
        self.assertIn("manual source", detail)
        self.assertIn("nothing admitted yet", detail)
        self.assertIn("no governed run recorded", detail)

    def test_skips_awaiting_activation_are_not_collection(self):
        """skipped_disabled is stored with is_failure 0 but collected nothing."""
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.SKIPPED_DISABLED, 0,
             "governed admission awaiting owner activation"))
        self.assertFalse(runs["gov_mil"].collected)
        self.assertIsNone(runs["gov_mil"].last_healthy)
        state, _, detail = self.judge(runs["gov_mil"])
        self.assertEqual("INERT", state)
        self.assertIn("latest 2026-09-19 skipped_disabled", detail)

    def test_a_skip_never_counts_as_a_healthy_run(self):
        runs = self.history(
            ("gov_mil", "2026-09-05 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.SKIPPED_DISABLED, 0, "gate closed"),
            ("gov_mil", "2026-09-19 23:30:00", st.NOT_IMPLEMENTED, 0, None))
        self.assertEqual("2026-09-05", runs["gov_mil"].last_healthy)
        self.assertEqual("UNHEALTHY", self.judge(runs["gov_mil"])[0])

    def test_a_held_admission_still_reached_its_source(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK_ALL_FILTERED, 0, "held: review"))
        self.assertEqual("HEALTHY", self.judge(runs["gov_mil"])[0])

    def test_signed_holds_on_a_healthy_run_are_visible_without_changing_it(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK_ALL_DUPLICATES, 0,
             "duplicates only; signed_held: 2"))
        state, days, detail = self.judge(runs["gov_mil"])
        self.assertEqual(("HEALTHY", 1), (state, days))
        self.assertIn("latest 2026-09-19 ok_all_duplicates: duplicates only; "
                      "signed_held: 2", detail)

    def test_a_healthy_run_without_detail_quotes_nothing(self):
        runs = self.history(("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None))
        self.assertTrue(self.judge(runs["gov_mil"])[2].endswith("latest 2026-09-19 ok"))

    def test_a_paused_source_is_paused_not_failed(self):
        runs = self.history(
            ("gov_mil", "2026-09-05 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.SKIPPED_DISABLED, 0, "gate closed"))
        paused = liveness.Expectation(manual=True, paused="switched off")
        state, days, detail = self.judge(runs["gov_mil"], total=3,
                                         last_seen="2026-09-05", expectation=paused)
        self.assertEqual(("PAUSED", 15), (state, days))
        self.assertTrue(detail.endswith("switched off"))

    def test_a_recent_run_never_rescues_stale_articles(self):
        """The invariant: a source UNHEALTHY before this signal stays UNHEALTHY."""
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK_NO_PUBLICATIONS, 0, None))
        before = liveness.classify("gov_mil", 3, "2026-09-05", TODAY, 7, self.MANUAL)
        state, days, detail = self.judge(runs["gov_mil"], total=3, last_seen="2026-09-05")
        self.assertEqual("UNHEALTHY", before[0])
        self.assertEqual(("UNHEALTHY", 15), (state, days))
        self.assertIn("last article 2026-09-05 (15d ago, threshold 7d)", detail)
        self.assertIn("governed: last healthy run 2026-09-19", detail)

    # -- A shared-Daily family never writes articles (Singapore MINDEF) ----------

    CLOSED = liveness.Expectation(manual=True, articles_closed=True)

    def test_a_shared_daily_family_is_judged_on_governed_runs_not_its_closed_articles(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None))
        state, days, detail = self.judge(runs["gov_mil"], total=40, last_seen="2026-07-01",
                                         expectation=self.CLOSED)
        self.assertEqual(("HEALTHY", 1), (state, days))
        self.assertIn("governed: last healthy run 2026-09-19", detail)
        self.assertNotIn("last article", detail)

    def test_a_shared_daily_family_with_a_stale_governed_run_is_unhealthy_on_the_run(self):
        runs = self.history(
            ("gov_mil", "2026-09-05 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.FETCH_FAILURE, 1, "handoff stale"))
        # Even with fresh articles the run decides; and stale articles are not blamed.
        for last_seen in ("2026-09-19", "2026-07-01"):
            with self.subTest(last_seen=last_seen):
                state, days, detail = self.judge(runs["gov_mil"], total=40, last_seen=last_seen,
                                                 expectation=self.CLOSED)
                self.assertEqual(("UNHEALTHY", 15), (state, days))
                self.assertIn("governed: last healthy run 2026-09-05", detail)
                self.assertIn("latest 2026-09-19 fetch_failure: handoff stale", detail)
                self.assertNotIn("last article", detail)

    def test_a_shared_daily_family_with_no_collection_run_still_falls_back_to_articles(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.SKIPPED_DISABLED, 0, "gate closed"))
        state, _, detail = self.judge(runs["gov_mil"], total=40, last_seen="2026-07-01",
                                      expectation=self.CLOSED)
        self.assertEqual("UNHEALTHY", state)
        self.assertIn("last article 2026-07-01", detail)

    def test_a_non_daily_manual_source_is_still_judged_on_the_worse_of_both(self):
        self.assertFalse(self.MANUAL.articles_closed)
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None))
        state, days, detail = self.judge(runs["gov_mil"], total=40, last_seen="2026-07-01")
        self.assertEqual(("UNHEALTHY", 81), (state, days))
        self.assertIn("last article 2026-07-01", detail)
        self.assertIn("governed: last healthy run 2026-09-19", detail)

    def test_articles_closed_is_derived_only_for_manual_shared_daily_families(self):
        from core.daily_sources import SOURCES

        class Source(FakeSource):
            def __init__(self, slug, access_method):
                super().__init__(slug)
                self.access_method = access_method

        daily = "sg_mindef_releases"
        self.assertIn(daily, SOURCES)
        reg = FakeRegistry(
            [SourceHealthResult(daily, st.OK, None),
             SourceHealthResult("other_manual", st.OK, None),
             SourceHealthResult("scraped_daily_like", st.OK, None)],
            [Source(daily, "manual"), Source("other_manual", "manual"),
             Source("scraped_daily_like", "scrape")])
        got = liveness.expectations(reg, paused={})
        self.assertTrue(got[daily].articles_closed)
        self.assertFalse(got["other_manual"].articles_closed)
        self.assertFalse(got["scraped_daily_like"].articles_closed)
        # A scraped source of the same slug set is never closed by this route.
        from unittest import mock
        with mock.patch("core.daily_sources.SOURCES", {"scraped_daily_like": object()}):
            got = liveness.expectations(reg, paused={})
        self.assertFalse(got["scraped_daily_like"].articles_closed)

    def test_singapore_mindef_is_derived_as_recurring_not_paused_and_articles_closed(self):
        got = liveness.expectations()["sg_mindef_releases"]
        self.assertEqual((got.manual, got.articles_closed, got.paused, got.inert, got.broken),
                         (True, True, None, False, False))

    def test_the_threshold_day_itself_is_still_healthy(self):
        runs = self.history(
            ("at_threshold", "2026-09-13 23:00:00", st.OK, 0, None),
            ("past_threshold", "2026-09-12 23:00:00", st.OK, 0, None))
        state, days, _ = self.judge(runs["at_threshold"])
        self.assertEqual(("HEALTHY", 7), (state, days))
        state, days, _ = self.judge(runs["past_threshold"])
        self.assertEqual(("UNHEALTHY", 7 + 1), (state, days))

    def test_an_undated_run_is_not_judged(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None),
            ("gov_mil", "not a date", st.FETCH_FAILURE, 1, "undated"))
        self.assertEqual(("2026-09-19", st.OK),
                         (runs["gov_mil"].latest_date, runs["gov_mil"].latest_status))

    def test_a_stale_run_turns_fresh_articles_unhealthy(self):
        runs = self.history(
            ("gov_mil", "2026-09-05 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.FETCH_FAILURE, 1, "handoff stale"))
        self.assertEqual("HEALTHY", liveness.classify(
            "gov_mil", 3, "2026-09-19", TODAY, 7, self.MANUAL)[0])
        self.assertEqual("UNHEALTHY", self.judge(
            runs["gov_mil"], total=3, last_seen="2026-09-19")[0])

    def test_a_latest_failure_is_visible_while_healthy(self):
        runs = self.history(
            ("gov_mil", "2026-09-17 23:00:00", st.OK_ALL_DUPLICATES, 0, None),
            ("gov_mil", "2026-09-19 23:00:00", st.ACCESS_CHALLENGED, 1, "x" * (liveness.DETAIL_LIMIT + 1)))
        state, _, detail = self.judge(runs["gov_mil"])
        self.assertEqual("HEALTHY", state)
        self.assertIn("latest 2026-09-19 access_challenged: ", detail)
        quoted = detail.split("access_challenged: ", 1)[1]
        self.assertEqual(liveness.DETAIL_LIMIT, len(quoted))
        self.assertTrue(quoted.endswith("…"))

    def test_latest_is_ordered_by_the_daily_not_by_row_id(self):
        runs = self.history(
            ("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None),
            ("gov_mil", "2026-09-18 23:00:00", st.FETCH_FAILURE, 1, "older"))
        self.assertEqual(("2026-09-19", st.OK),
                         (runs["gov_mil"].latest_date, runs["gov_mil"].latest_status))

    def test_a_database_without_run_tables_keeps_the_old_judgement(self):
        db = run_db(Path(self.tmp.name) / "old.db", (), with_run_tables=False)
        self.assertIsNone(liveness.governed_runs(db))
        self.assertEqual(
            liveness.classify("gov_mil", 0, None, TODAY, 7, self.MANUAL),
            ("INERT", None, "manual source — nothing admitted yet"))

    def test_the_gate_reads_the_runs_and_fails_on_them(self):
        """main() wires the run table into the verdict and the exit code."""
        import contextlib
        import io
        import os
        import sqlite3
        from unittest import mock
        db = run_db(Path(self.tmp.name) / "cli.db", (
            ("gov_mil", "2026-09-19 23:00:00", st.FETCH_FAILURE, 1, "handoff stale"),))
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO sources (slug, display_name, is_active) "
                     "VALUES ('gov_mil', 'Governed family', 1)")
        conn.commit()
        conn.close()
        argv = ["check_source_liveness.py", "--db", str(db), "--today", "2026-09-20"]
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_STEP_SUMMARY"}
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(liveness, "expectations",
                                  return_value={"gov_mil": self.MANUAL}), \
                contextlib.redirect_stdout(out):
            code = liveness.main()
        self.assertEqual(1, code)
        self.assertIn("UNHEALTHY", out.getvalue())
        self.assertIn("governed: no healthy run recorded; latest 2026-09-19 "
                      "fetch_failure: handoff stale", out.getvalue())

    def test_a_scraped_source_ignores_run_evidence(self):
        runs = self.history(
            ("fetched_mil", "2026-09-19 23:00:00", st.FETCH_FAILURE, 1, "down"))
        for expectation in (liveness.UNDECLARED, liveness.Expectation(threshold=21)):
            for total, seen in ((0, None), (3, "2026-09-19"), (3, "2026-09-05")):
                with self.subTest(expectation=expectation, seen=seen):
                    self.assertEqual(
                        liveness.classify("fetched_mil", total, seen, TODAY, 7, expectation),
                        liveness.classify("fetched_mil", total, seen, TODAY, 7, expectation,
                                          runs=runs["fetched_mil"]))

    def test_the_live_corpus_never_gets_more_lenient(self):
        """Over the tracked database: run evidence only ever adds a verdict."""
        if not liveness.DEFAULT_DB.exists():
            self.skipTest("tracked database not present")
        runs = liveness.governed_runs(liveness.DEFAULT_DB)
        if runs is None:
            self.skipTest("tracked database predates run tables")
        expected = liveness.expectations()
        today = date.today()
        for slug, name, total, last_seen in liveness.rows(liveness.DEFAULT_DB, today):
            exp = expected.get(slug, liveness.UNDECLARED)
            source_runs = runs.get(slug, liveness.NO_GOVERNED_RUNS)
            old = liveness.classify(*self._baseline(slug, total, last_seen, exp, source_runs),
                                    today, 7, exp)
            new = liveness.classify(slug, total, last_seen, today, 7, exp,
                                    runs=source_runs)
            with self.subTest(source=slug):
                if old[0] in {"UNHEALTHY", "PAUSED"}:
                    self.assertEqual(old[0], new[0])
                if not exp.manual:
                    self.assertEqual(old, new)

    @staticmethod
    def _baseline(slug, total, last_seen, exp, source_runs):
        """The article-only judgement the governed signal is compared against.

        A shared-Daily family (``articles_closed``) never writes ``articles``;
        once it has governed runs its article rows are a closed pre-cutover
        corpus that #1093 deliberately stops judging (see
        test_a_shared_daily_family_is_judged_on_governed_runs_not_its_closed_articles).
        Its baseline is therefore "nothing admitted": the invariant still holds
        for every other source, including every manual source that writes
        articles, whose stale articles a recent run must never rescue.
        """
        if exp.articles_closed and source_runs.collected:
            return slug, 0, None
        return slug, total, last_seen

    def test_only_a_closed_corpus_with_runs_gets_the_article_free_baseline(self):
        healthy = self.history(("gov_mil", "2026-09-19 23:00:00", st.OK, 0, None))["gov_mil"]
        closed = liveness.Expectation(manual=True, articles_closed=True)
        cases = (
            (closed, healthy, ("gov_mil", 0, None)),
            (closed, liveness.NO_GOVERNED_RUNS, ("gov_mil", 3, "2026-09-05")),
            (self.MANUAL, healthy, ("gov_mil", 3, "2026-09-05")),
            (liveness.UNDECLARED, healthy, ("gov_mil", 3, "2026-09-05")),
        )
        for exp, source_runs, expected in cases:
            with self.subTest(exp=exp, collected=source_runs.collected):
                self.assertEqual(expected,
                                 self._baseline("gov_mil", 3, "2026-09-05", exp, source_runs))
        # Without the closed flag, a manual source's stale articles still decide.
        old = liveness.classify("gov_mil", 3, "2026-09-05", TODAY, 7, self.MANUAL)
        new = liveness.classify("gov_mil", 3, "2026-09-05", TODAY, 7, self.MANUAL,
                                runs=healthy)
        self.assertEqual(("UNHEALTHY", "UNHEALTHY"), (old[0], new[0]))


# ── Against the live corpus ───────────────────────────────────────────────────

class TheLiveCorpusAgrees(unittest.TestCase):
    """Properties over the tracked database. Nothing here pins a count."""

    @classmethod
    def setUpClass(cls):
        cls.db = liveness.DEFAULT_DB
        if not cls.db.exists():
            raise unittest.SkipTest("tracked database not present")
        cls.rows = liveness.rows(cls.db, date.today())
        cls.expected = liveness.expectations()

    def test_no_producing_source_is_classified_inert(self):
        """The invariant the Xinhua defect violated for four days."""
        for slug, name, total, last_seen in self.rows:
            state, _, _ = liveness.classify(
                slug, total, last_seen, date.today(), 7,
                self.expected.get(slug, liveness.UNDECLARED),
            )
            if state == "INERT":
                self.assertEqual(
                    0, total,
                    "%s is classified INERT while holding articles" % name,
                )

    def test_every_live_source_is_judged(self):
        for slug, name, total, last_seen in self.rows:
            state, _, _ = liveness.classify(
                slug, total, last_seen, date.today(), 7,
                self.expected.get(slug, liveness.UNDECLARED),
            )
            self.assertIn(state, {"HEALTHY", "UNHEALTHY", "INERT", "PAUSED"})

    def test_no_moving_corpus_count_is_frozen_in_this_file(self):
        """Guard against pinning a total that grows every day.

        A literal is suspicious when it equals a live per-source total or the
        grand total AND is not a value configuration declares (a threshold or a
        cadence), which is how 7 and 21 stay legal.
        """
        # Zero is a stable empty-source sentinel, not a moving corpus total.
        totals = {total for _slug, _name, total, _seen in self.rows if total > 0}
        grand_total = sum(total for _s, _n, total, _x in self.rows)
        if grand_total > 0:
            totals.add(grand_total)
        configured = set()
        for slug in get_registry().slugs:
            src = get_registry().get_source(slug)
            for attr in ("silence_threshold_days", "expected_cadence_days"):
                value = getattr(src, attr, None)
                if value is not None:
                    configured.add(value)

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        literals = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        }
        frozen = sorted((literals & totals) - configured)
        self.assertEqual(
            [], frozen,
            "these test literals equal a live corpus total and will rot: %s"
            % frozen,
        )


if __name__ == "__main__":
    unittest.main()
