"""Korea desk registry truth contract after limited MND production activation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class KoreaRegistryTruth(unittest.TestCase):
    def test_existing_publishers_follow_actual_collector_name(self):
        workflows = ROOT / ".github/workflows"
        collector_name = (workflows / "indonesia_korea_shadow.yml").read_text().splitlines()[0].removeprefix("name: ")
        for name in ("korea_verified_official_link_production.yml",
                     "korea_standing_original_text_production.yml"):
            flow = (workflows / name).read_text()
            self.assertIn("  workflow_run:\n    workflows:\n      - " + collector_name + "\n", flow)

    def test_mnd_content_and_dapa_limits_stated_without_full_desk_promotion(self):
        doc = json.loads((ROOT / "desks/registry.json").read_text(encoding="utf-8"))
        rows = doc["desks"] if type(doc) is dict else doc
        korea = next(x for x in rows if x["slug"] == "korea")
        self.assertEqual(korea["status"], "shadow",
                         "full desk status must not be promoted by copy changes")
        self.assertIs(korea["has_production_records"], False,
                      "source-specific MND metadata is not the full desk corpus")
        self.assertIsNone(korea["manifest"],
                          "general corpus discovery remains separate from admitted metadata")
        public = " ".join([
            korea["scope"], korea["status_explanation"],
            *korea["limits"],
            *[part for pair in korea["research"]["blockers"] for part in pair],
            *[part for pair in korea["research"]["resolved"] for part in pair],
        ])
        for expected in (
            "MND", "DAPA", "Korean", "English", "approved",
            "publisher", "original", "rights", "metadata",
        ):
            self.assertIn(expected.lower(), public.lower())
        for stale in (
            "no archived Korean bodies, production records",
            "The directory reproduces Korean headline, canonical official link and source dates only",
            "without IPR analytical summaries",
            "No IPR translation, full original Korean article body",
            "Public scope is five frozen bibliographic links",
        ):
            self.assertNotIn(stale, public)
        self.assertIn("MND and DAPA official-link metadata", korea["scope"])
        for stale in ("DAPA collection remains research-only", "separate unadmitted issuer",
                      "No DAPA production", "production admission remain unapproved"):
            self.assertNotIn(stale, json.dumps(korea, ensure_ascii=False))
        self.assertIn("HWPX", public)
        self.assertIn("photographs", public)
        self.assertIn("human", public.lower()) if "human" in public.lower() else self.assertIn("editor", public.lower())

    def test_korea_page_rebuild_trigger_is_bounded_to_existing_writer(self):
        flow = (ROOT / ".github/workflows/korea_verified_official_link_production.yml"
                ).read_text(encoding="utf-8")
        self.assertIn("- desks/registry.json", flow)
        self.assertIn("git add -- pla_watch.db output/korea.html", flow)
        self.assertIn("cp ../output/korea.html korea.html", flow)
        self.assertIn("cmp ../output/korea.html korea.html", flow)
        self.assertIn("group: korea-verified-official-link-production", flow)
        self.assertIn("cancel-in-progress: false", flow)
        self.assertNotIn("korea_dapa_single_article_canary.yml", flow)


if __name__ == "__main__":
    unittest.main()
