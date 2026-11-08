"""Treasury: source-specific U.S. Desk metadata rendering, no corpus inflation."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class TreasuryPublicContracts(unittest.TestCase):
    def test_distinct_official_sources_and_governed_links(self):
        template=(ROOT/"site/preview/templates/desk.html").read_text(encoding="utf-8")
        generator=(ROOT/"site/preview/generate_preview.py").read_text(encoding="utf-8")
        self.assertIn("data-us-pacom-link=",template)
        self.assertIn("data-uscc-official-link=",template)
        self.assertIn("data-us-treasury-official-link=",template)
        self.assertIn("us_treasury_official_links=treasury_links",generator)
        self.assertIn("load_treasury_live_links(db_path)",generator)
        self.assertIn("U.S. Department of the Treasury",template)
        self.assertIn("inclusion does not establish Indo-Pacific relevance",template)
        self.assertIn("executive department",template)
        self.assertIn("Access blocked",template)
    def test_release_uses_only_approved_paths(self):
        # Runtime migration 4: the scheduled Daily workflow clones the preserved
        # listing history and the pipeline's governed admission writes the rows;
        # Daily's own commit and deploy steps publish the database and site.
        daily=(ROOT/".github/workflows/daily_update.yml").read_text(encoding="utf-8")
        self.assertIn("shadow/us-treasury-press",daily)
        self.assertIn("IPR_US_TREASURY_SOURCE_CHECKOUT: ${{ runner.temp }}/treasury-preserved-metadata",daily)
        self.assertIn("git add pla_watch.db output/",daily)
        self.assertNotIn("deploy_output_only",daily)
        workflow=(ROOT/".github/workflows/treasury_verified_official_links_release.yml").read_text(encoding="utf-8")
        self.assertIn("shadow/us-treasury-press",workflow)
        self.assertIn("isolated-render-contract",workflow)
        self.assertNotIn("production-metadata-page-only",workflow)
        self.assertNotIn("git push",workflow)

if __name__=="__main__":
    unittest.main()
