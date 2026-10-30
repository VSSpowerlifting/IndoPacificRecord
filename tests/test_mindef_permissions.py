"""Synthetic-only contracts for MINDEF's limited hyperlink authorization."""
import unittest
from core.mindef_permissions import APPROVED_MINDEF_LINKS, is_mindef_source, source_link_approved


class MINDEFPermissionTests(unittest.TestCase):
    def test_only_two_exact_approved_urls(self):
        self.assertEqual(len(APPROVED_MINDEF_LINKS), 2)
        for url in APPROVED_MINDEF_LINKS:
            self.assertTrue(source_link_approved("sg_mindef_releases", url))

    def test_other_mindef_pages_fail_closed(self):
        for url in (
            "https://www.mindef.gov.sg/",
            "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2",
            "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/?copy=1",
            "http://www.mindef.gov.sg/news-and-events/latest-releases/31may25_nr3/",
            None, "",
        ):
            with self.subTest(url=url):
                self.assertFalse(source_link_approved("sg_mindef_releases", url))

    def test_record_template_does_not_render_mindef_original_body(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/record.html").read_text(encoding="utf-8")
        start = template.index("{% elif record.source_slug == 'sg_mindef_releases' %}")
        stop = template.index('{% else %}\n    <section class="record-section" aria-labelledby="record-text">', start)
        singapore_branch = template[start:stop]
        self.assertNotIn("text_original", singapore_branch)
        self.assertIn("MINDEF's original article text and media are not reproduced", singapore_branch)
        self.assertIn("record.mindef_link_allowed", singapore_branch)
        self.assertIn("record.source_slug != 'sg_mindef_releases' or record.mindef_link_allowed", template)

    def test_source_directory_does_not_link_unapproved_mindef_homepage(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/source.html").read_text(encoding="utf-8")
        self.assertIn("source.slug == 'sg_mindef_releases'", template)
        self.assertIn("publisher homepage, not within approved linking scope", template)

    def test_other_sources_unaffected(self):
        self.assertFalse(is_mindef_source("sg-other"))
        self.assertTrue(source_link_approved("uscc", "https://www.uscc.gov/"))
        self.assertTrue(source_link_approved("sg-other", "https://example.org/"))


if __name__ == "__main__":
    unittest.main()
