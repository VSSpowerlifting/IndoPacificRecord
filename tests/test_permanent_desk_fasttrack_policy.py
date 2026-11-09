"""Offline guard: legacy seven/thirty-day launch rules are historical, not active."""
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

    def test_current_acceptance_does_not_require_obsolete_launch_clocks(self):
        section = self.criteria.split(
            "### C13 — Source-to-reader acceptance without artificial launch clocks",
            1)[1].split("\n---", 1)[0]
        normalized = " ".join(section.split())
        for phrase in (
            "no mandatory seven-day or thirty-day prelaunch clock",
            "source-specific use and component scope",
            "the existing shared processing/admission path",
            "controlled deployment/readback",
            "subsequent unattended collection/processing cycle",
            "authentic",
            "publisher",
            "founder",
            "quality",
        ):
            self.assertIn(phrase.lower(), normalized.lower())
        # A historic checkpoint must never silently become a current waiting rule.
        self.assertNotIn("Thirty consecutive genuine collecting days", section)
        self.assertNotIn("at least seven consecutive", section)
        self.assertNotIn("all three human reviews completed", section)
        self.assertIn("RETIRED AS AN OPERATING LAUNCH RULE", self.record)
        self.assertIn("The dated procedures below are historical", self.record)

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

    def test_historical_postlaunch_evidence_cannot_be_backdated(self):
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
