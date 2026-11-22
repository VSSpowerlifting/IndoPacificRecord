"""Offline checks for historical launch-clock retirement and current evidence gates."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PermanentDeskExceptionPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.criteria = (ROOT / "docs/DESK_STRENGTH_CRITERIA.md").read_text()
        cls.record = (ROOT / "docs/PERMANENT_DESK_ACCELERATED_ACTIVATION_2026-10-15.md").read_text()
        cls.registry = {d["slug"]: d for d in
                        json.loads((ROOT / "desks/registry.json").read_text())["desks"]}

    def test_current_operational_milestones_have_no_obsolete_waiting_clock(self):
        section = self.criteria.split(
            "### C13 — Minimum source-to-reader acceptance without launch clocks", 1
        )[1].split("\n---", 1)[0]
        for phrase in (
            "no mandatory seven-day or thirty-day",
            "authentic permitted original",
            "authorized custody",
            "factual and language QA",
            "shared processing/admission",
            "independent HTTPS readback",
            "genuine unattended cycle",
            "Full-scope milestone",
            "sixteen-family",
        ):
            # The final item names the full milestone concept, not a fixed day count.
            if phrase == "sixteen-family":
                self.assertIn("sixteen-family original roster", section)
            else:
                self.assertIn(phrase.lower(), section.lower())
        self.assertNotIn("Thirty consecutive genuine collecting days", section)
        self.assertNotIn("all three human reviews completed", section)
        self.assertIn("RETIRED AS AN OPERATING LAUNCH RULE", self.record)
        self.assertIn("The dated procedures below are", self.record)

    def test_exception_is_not_unverified_source_or_rights_approval(self):
        for phrase in (
            "not source-specific publication approval",
            "seven consecutive",
            "cancelled/missing/failed",
            "publisher's robots/access terms",
            "Named substantive human source review",
            "exact original language",
            "Source-specific rights and access decision",
            "owner",
            "DECISION_LOG.md",
            "No status tag",
            "not yet admitted",
            "not a completed release receipt",
        ):
            self.assertIn(phrase, self.record)
        self.assertNotIn("production_eligible=true", self.record)
        self.assertNotIn("bypass robots", self.record)
        self.assertNotIn("ignore copyright", self.record)

    def test_no_country_promoted_by_exception_document(self):
        for name in ("philippines", "indonesia", "japan"):
            d = self.registry[name]
            self.assertEqual(d["status"], "shadow")
            self.assertFalse(d["has_production_records"])
        # Korea is live through its own activation change, not this document.
        for name in ("china", "singapore", "korea", "vietnam"):
            self.assertEqual(self.registry[name]["status"], "live")
            self.assertTrue(self.registry[name]["has_production_records"])

    def test_policy_requires_real_postlaunch_day14_and_day30_observation(self):
        for phrase in (
            "after those dates occur",
            "without backdating",
            "material coverage failure",
            "stop admission",
            "never retroactively",
        ):
            self.assertIn(phrase, self.record)


if __name__ == "__main__":
    unittest.main()
