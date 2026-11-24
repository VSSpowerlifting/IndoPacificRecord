"""Unit tests for the corpus-growth canary's grow(): load()'s eligibility, and
which gaps fail. Kept apart from the slow canary run (see its HELPER_TESTS)."""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.test_corpus_growth_canary import (
    TRACKED, _sha, code_gaps, grow, unexpected_gaps)

# Gaps a family may legitimately report on any tracked data state.
DATA_GAPS = {"no_resolvable_parent", "all_parents_released", "no_parent_rows"}


class GrowHelperEligibility(unittest.TestCase):
    """grow() follows load()'s own eligibility and never raises on stopped families."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED.exists():
            raise unittest.SkipTest("tracked database absent")
        cls.sha = _sha(TRACKED)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-growth-unit-")
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "g.db"
        shutil.copyfile(TRACKED, self.db)
        # Start from no released rows so outcomes do not depend on which
        # parents earlier Daily runs happened to release.
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("DELETE FROM daily_machine_records")
        conn.close()

    def tearDown(self):
        self.assertEqual(_sha(TRACKED), self.sha)

    @staticmethod
    def _on(s, *families):
        """Pin a family eligible whatever the committed switches say, so an
        emergency pause in policy alone cannot turn these tests red."""
        for f in families:
            s[f].update(public_machine_explanation=True, private_model_processing=True,
                        unattended_release=True, excluded_source_identities=[])

    def _grow(self, edit):
        import copy
        from unittest import mock
        from processing import daily_intake as di
        pol = copy.deepcopy(di.load_policy())
        edit(pol["sources"])
        with mock.patch.object(di, "load_policy", lambda: pol), \
                mock.patch("core.daily_machine_records.load_policy", lambda: pol):
            return grow(self.db)

    def assertGrownOrDataGap(self, family, inserted, skipped, gaps):
        """Eligible: either grown, or a gap the tracked data alone explains."""
        self.assertNotIn(family, skipped)
        if family not in inserted:
            self.assertIn(family, gaps)
            self.assertIn(gaps[family][0], DATA_GAPS, gaps[family])

    def test_paused_family_is_skipped_not_raised(self):
        def edit(s):
            self._on(s, "us_uscc_press_en")
            s["id_kemhan_news"]["private_model_processing"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("id_kemhan_news", skipped)
        self.assertNotIn("id_kemhan_news", inserted)
        self.assertGrownOrDataGap("us_uscc_press_en", inserted, skipped, gaps)

    def test_singapore_with_both_switches_off_uses_display_policy(self):
        def edit(s):
            self._on(s, "sg_mindef_releases")
            s["sg_mindef_releases"]["private_model_processing"] = False
            s["sg_mindef_releases"]["unattended_release"] = False
        inserted, skipped, gaps = self._grow(edit)
        # Not skipped: load() normalizes the display policy, so hashes match.
        self.assertGrownOrDataGap("sg_mindef_releases", inserted, skipped, gaps)
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_singapore_with_one_switch_off_is_skipped(self):
        def edit(s):
            self._on(s, "sg_mindef_releases")
            s["sg_mindef_releases"]["unattended_release"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("sg_mindef_releases", skipped)

    def test_release_held_family_is_skipped(self):
        from unittest import mock
        from core import daily_sources
        src = daily_sources.source_for("jp_jcg_press_en")
        with mock.patch.object(type(src), "release_hold", lambda self: "held" if self is src else None):
            inserted, skipped, gaps = self._grow(lambda s: self._on(s, "jp_jcg_press_en"))
        self.assertIn("jp_jcg_press_en", skipped)
        self.assertNotIn("jp_jcg_press_en", inserted)

    def test_dapa_is_covered_the_day_it_becomes_eligible(self):
        def edit(s):
            s["kr_policy_dapa_releases"].update(
                public_machine_explanation=True, private_model_processing=True,
                unattended_release=True)
        inserted, skipped, gaps = self._grow(edit)
        self.assertGrownOrDataGap("kr_policy_dapa_releases", inserted, skipped, gaps)
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_no_gap_fails_the_run_except_an_invisible_insert(self):
        """Gaps depend on data and policy; failing on them would let a
        data-only Daily turn main red. Code defects fail in code_gaps()."""
        from unittest import mock

        def edit(s):
            s["kr_policy_dapa_releases"].update(
                public_machine_explanation=True, private_model_processing=True,
                unattended_release=True)
        from tests import test_corpus_growth_canary as canary
        real = canary.parent_table
        with mock.patch.object(canary, "parent_table",
                               lambda src: None if src.family == "kr_policy_dapa_releases" else real(src)):
            inserted, skipped, gaps = self._grow(edit)
        self.assertEqual(gaps["kr_policy_dapa_releases"][0], "parent_not_enumerable")
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_an_insert_load_does_not_show_fails_the_run(self):
        """The one failing gap: a released row load() would not show."""
        from unittest import mock
        from core import daily_machine_records as dmr
        real = dmr.load

        def hide_uscc(*a, **k):
            return [r for r in real(*a, **k) if r["source_family"] != "us_uscc_press_en"]
        with mock.patch.object(dmr, "load", hide_uscc):
            inserted, skipped, gaps = self._grow(lambda s: self._on(s, "us_uscc_press_en"))
        if "us_uscc_press_en" in gaps and gaps["us_uscc_press_en"][0] in DATA_GAPS:
            self.skipTest("no resolvable USCC parent in the tracked database")
        self.assertEqual(gaps["us_uscc_press_en"][0], "not_visible_after_insert", gaps)
        self.assertIn("us_uscc_press_en", unexpected_gaps(gaps))

    def test_policy_stop_of_every_family_grows_nothing_without_raising(self):
        def edit(s):
            for v in s.values():
                v["private_model_processing"] = False
                v["unattended_release"] = False
                v["public_machine_explanation"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertEqual(inserted, {})
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_held_parents_do_not_exhaust_attempts(self):
        """A Daily that holds parents (changed versions) is data-only: the canary
        must still grow on a resolvable parent, or report a data gap."""
        with sqlite3.connect(str(self.db)) as conn:
            n = conn.execute("UPDATE japan_jcg_source_records SET public_scope='held'").rowcount
        conn.close()
        if not n:
            self.skipTest("no JCG parent rows in the tracked database")
        inserted, skipped, gaps = self._grow(lambda s: self._on(s, "jp_jcg_press_en"))
        self.assertNotIn("jp_jcg_press_en", inserted)
        self.assertEqual(gaps["jp_jcg_press_en"][0], "no_resolvable_parent")
        self.assertNotIn("jp_jcg_press_en", unexpected_gaps(gaps))

    def test_newly_activated_family_without_parents_is_a_data_gap(self):
        def edit(s):
            s["kr_policy_dapa_releases"].update(
                public_machine_explanation=True, private_model_processing=True,
                unattended_release=True)
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("DELETE FROM korea_official_source_records WHERE official_issuer='kr_dapa'")
        conn.close()
        inserted, skipped, gaps = self._grow(edit)
        # Other Korean issuers' rows remain, so none resolves through DAPA's
        # own issuer filter; either way it is a data gap, not a failure.
        self.assertIn(gaps["kr_policy_dapa_releases"][0], {"no_parent_rows", "no_resolvable_parent"})
        self.assertNotIn("kr_policy_dapa_releases", inserted)
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_missing_parent_table_is_a_data_gap(self):
        # A family activated before its parent table is migrated in (JCG at
        # 8f25f4ff74). Simulated by pointing it at an absent table, since
        # dropping a real one breaks unrelated triggers.
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        real = canary.parent_table
        with mock.patch.object(canary, "parent_table",
                               lambda src: "not_yet_migrated" if src.family == "us_uscc_press_en" else real(src)):
            inserted, skipped, gaps = self._grow(lambda s: self._on(s, "us_uscc_press_en"))
        self.assertEqual(gaps["us_uscc_press_en"][0], "parent_table_missing")
        self.assertFalse(unexpected_gaps(gaps), gaps)


class TargetSelection(unittest.TestCase):
    """Every way a test reaches the tracked database is selected."""

    def test_copy_and_reader_patterns_are_selected(self):
        from tests.test_corpus_growth_canary import is_target
        selected = [
            'shutil.copyfile(TRACKED, db)',
            'shutil.copy2(ROOT / "pla_watch.db", tmp)',
            'with read_only(str(ROOT / "pla_watch.db")) as source:\n    source.backup(dest)',
            'DB = ROOT / "pla_watch.db"\nwith mock.patch("core.daily_machine_records.load_policy", p):',
            'rows = load(TRACKED_DB)\nfrom processing import daily_intake',
        ]
        for text in selected:
            self.assertTrue(is_target(text), text)
        for text in ('shutil.copyfile(fixture, db)', 'DB = ROOT / "pla_watch.db"\nprint(DB)'):
            self.assertFalse(is_target(text), text)

    def test_known_readers_stay_selected(self):
        from tests.test_corpus_growth_canary import target_modules
        mods = set(target_modules())
        for m in ("test_korea_render_gate", "test_korea_official_metadata_auto_admission",
                  "test_archive_integration", "test_china_titles_public", "test_dossiers",
                  "test_korea_dapa_private_to_production", "test_japan_mod_official_links",
                  "test_desk_rollout_contract", "test_public_chrome_is_truthful",
                  "test_japan_vietnam_publisher_navigation", "test_singapore_daily_completion",
                  "test_uscc_press_daily", "test_japan_jcg_daily"):
            self.assertIn(f"tests.{m}", mods)


class FailureAttribution(unittest.TestCase):
    """Baseline comparison must keep each subTest distinct (3.9 and 3.11+)."""

    def _ids(self, text):
        import types
        from tests.test_corpus_growth_canary import _failed_ids
        return _failed_ids(types.SimpleNamespace(stderr=text))

    def test_subtests_are_attributed_separately(self):
        for cls in ("mod.C", "mod.C.test_f"):
            base = self._ids(f"FAIL: test_f ({cls}) (family='a')\n")
            grown = self._ids(f"FAIL: test_f ({cls}) (family='a')\nFAIL: test_f ({cls}) (family='b')\n")
            self.assertEqual(grown - base, {f"test_f ({cls}) (family='b')"}, cls)

    def test_plain_failures_and_class_errors_parse(self):
        self.assertEqual(self._ids("ERROR: setUpClass (tests.m.C)\nFAIL: test_x (tests.m.C)  \n"),
                         {"setUpClass (tests.m.C)", "test_x (tests.m.C)"})


class DailySkip(unittest.TestCase):
    def test_canary_skips_outside_pull_request_and_push(self):
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        if not canary.TRACKED.exists():
            self.skipTest("tracked database absent")
        for event in ("schedule", "workflow_dispatch"):
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event}):
                result = unittest.TestResult()
                canary.CorpusGrowthCanary("test_tracked_db_readers_survive_first_released_records").run(result)
                self.assertEqual(len(result.skipped), 1, event)
                self.assertFalse(result.failures or result.errors, event)


class CannedRowsCoverEveryFamily(unittest.TestCase):
    """Code-time coverage: independent of tracked data and policy switches."""

    def test_every_policy_family_is_growable_by_the_canary(self):
        self.assertEqual(code_gaps(), {}, "fix the canary's parent_table() or FAMILY_SUMMARY")

    def test_parent_tables_come_from_the_resolvers(self):
        from core import daily_sources
        from tests.test_corpus_growth_canary import parent_table
        expected = {"jp_jcg_press_en": "japan_jcg_source_records",
                    "us_uscc_press_en": "uscc_press_source_records",
                    "sg_mindef_releases": "singapore_mindef_source_records",
                    "kr_policy_dapa_releases": "korea_official_source_records"}
        for family, table in expected.items():
            self.assertEqual(parent_table(daily_sources.source_for(family)), table, family)

    def test_underivable_parent_table_is_reported(self):
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        with mock.patch.object(canary, "parent_table", lambda src: None):
            self.assertIn("not derivable", code_gaps()["us_uscc_press_en"])

    def test_parent_table_absent_from_migrations_is_reported(self):
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        with mock.patch.object(canary, "parent_table", lambda src: "uscc_press_source_record_typo"):
            self.assertIn("created by no migration", code_gaps()["us_uscc_press_en"])

    def test_parent_table_without_source_identity_is_reported(self):
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        with mock.patch.object(canary, "parent_table", lambda src: "articles"):
            self.assertIn("no source_identity column", code_gaps()["us_uscc_press_en"])

    def test_parent_table_without_a_posted_date_is_still_enumerable(self):
        """A family whose parent table lacks publisher_posted_date must not
        raise once a policy-only change activates it."""
        import sqlite3
        from unittest import mock
        from core import daily_sources
        from tests import test_corpus_growth_canary as canary
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE p (source_identity TEXT)")
        conn.executemany("INSERT INTO p VALUES (?)", [("a",), ("b",)])
        src = daily_sources.source_for("us_uscc_press_en")
        with mock.patch.object(canary, "parent_table", lambda s: "p"):
            self.assertEqual(canary._parent_identities(conn, "us_uscc_press_en", src), ["b", "a"])

    def test_rejected_canned_row_is_reported_even_when_family_is_not_growable(self):
        # NSC is fully released (not growable in data) and DAPA is policy-off;
        # a wording defect for either must still fail at code time.
        from unittest import mock
        from tests import test_corpus_growth_canary as canary
        for family in ("ph_nsc_official_statements", "kr_policy_dapa_releases"):
            with mock.patch.dict(canary.FAMILY_SUMMARY, {family: "Unattributed text."}):
                self.assertIn("rejected by the output check", code_gaps().get(family, ""), family)


if __name__ == "__main__":
    unittest.main()
