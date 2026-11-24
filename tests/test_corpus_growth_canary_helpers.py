"""Unit tests for the corpus-growth canary's grow(): load()'s eligibility, and
which gaps fail. Kept apart from the slow canary run (see its HELPER_TESTS)."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.test_corpus_growth_canary import (
    PARENT_TABLES, TRACKED, _sha, grow, unexpected_gaps)


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

    def tearDown(self):
        self.assertEqual(_sha(TRACKED), self.sha)

    def _grow(self, edit):
        import copy
        from unittest import mock
        from processing import daily_intake as di
        pol = copy.deepcopy(di.load_policy())
        edit(pol["sources"])
        with mock.patch.object(di, "load_policy", lambda: pol), \
                mock.patch("core.daily_machine_records.load_policy", lambda: pol):
            return grow(self.db)

    def test_paused_family_is_skipped_not_raised(self):
        def edit(s):
            s["id_kemhan_news"]["private_model_processing"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("id_kemhan_news", skipped)
        self.assertNotIn("id_kemhan_news", inserted)
        self.assertIn("us_uscc_press_en", inserted)

    def test_singapore_with_both_switches_off_uses_display_policy(self):
        def edit(s):
            s["sg_mindef_releases"]["private_model_processing"] = False
            s["sg_mindef_releases"]["unattended_release"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("sg_mindef_releases", inserted)  # visible via load(): hash matched

    def test_singapore_with_one_switch_off_is_skipped(self):
        def edit(s):
            s["sg_mindef_releases"]["unattended_release"] = False
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("sg_mindef_releases", skipped)

    def test_release_held_family_is_skipped(self):
        from unittest import mock
        from core import daily_sources
        src = daily_sources.source_for("jp_jcg_press_en")
        with mock.patch.object(type(src), "release_hold", lambda self: "held" if self is src else None):
            inserted, skipped, gaps = grow(self.db)
        self.assertIn("jp_jcg_press_en", skipped)
        self.assertNotIn("jp_jcg_press_en", inserted)

    def test_dapa_is_covered_the_day_it_becomes_eligible(self):
        def edit(s):
            s["kr_policy_dapa_releases"].update(
                public_machine_explanation=True, private_model_processing=True,
                unattended_release=True)
        inserted, skipped, gaps = self._grow(edit)
        self.assertIn("kr_policy_dapa_releases", inserted, gaps)
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_unlisted_gap_fails_loudly_naming_family_and_reason(self):
        from unittest import mock

        def edit(s):
            s["kr_policy_dapa_releases"].update(
                public_machine_explanation=True, private_model_processing=True,
                unattended_release=True)
        with mock.patch.dict(PARENT_TABLES, clear=False):
            del PARENT_TABLES["kr_policy_dapa_releases"]
            inserted, skipped, gaps = self._grow(edit)
        bad = unexpected_gaps(gaps)
        self.assertEqual(bad["kr_policy_dapa_releases"][0], "parent_not_enumerable")
        self.assertNotIn("ph_nsc_official_statements", bad)  # allow-listed

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
            spare = [r[0] for r in conn.execute(
                "SELECT source_identity FROM japan_jcg_source_records WHERE source_identity NOT IN "
                "(SELECT source_identity FROM daily_machine_records WHERE source_family='jp_jcg_press_en')")]
            conn.execute("UPDATE japan_jcg_source_records SET public_scope='held' WHERE source_identity IN (%s)"
                         % ",".join("?" * len(spare)), spare)
        conn.close()
        inserted, skipped, gaps = grow(self.db)
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
        self.assertEqual(gaps["kr_policy_dapa_releases"][0], "no_parent_rows")
        self.assertFalse(unexpected_gaps(gaps), gaps)

    def test_missing_parent_table_is_a_data_gap(self):
        # A family activated before its parent table is migrated in (JCG at
        # 8f25f4ff74). Simulated by pointing it at an absent table, since
        # dropping a real one breaks unrelated triggers.
        from unittest import mock
        with mock.patch.dict(PARENT_TABLES, {"us_uscc_press_en": ("not_yet_migrated", "1=1")}):
            inserted, skipped, gaps = grow(self.db)
        self.assertEqual(gaps["us_uscc_press_en"][0], "parent_table_missing")
        self.assertFalse(unexpected_gaps(gaps), gaps)

if __name__ == "__main__":
    unittest.main()
