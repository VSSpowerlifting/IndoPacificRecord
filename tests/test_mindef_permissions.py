"""Synthetic-only MINDEF outbound-link checks and retained source-text holds."""
import unittest
from core.mindef_permissions import MINDEF_LINK_HOST, is_mindef_source, source_link_approved


class MINDEFPermissionTests(unittest.TestCase):
    def test_valid_official_https_links_include_new_articles(self):
        self.assertEqual(MINDEF_LINK_HOST, "www.mindef.gov.sg")
        for url in (
            "https://www.mindef.gov.sg/",
            "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/",
            "https://www.mindef.gov.sg/news-and-events/latest-releases/4nov26-nr/",
            "https://www.mindef.gov.sg/news-and-events/latest-releases/04mar25_speech3/",
        ):
            with self.subTest(url=url):
                self.assertTrue(source_link_approved("sg_mindef_releases", url))

    def test_invalid_urls_fail_closed(self):
        for url in (
            "https://mindef.gov.sg/",
            "https://www.mindef.gov.sg.evil.example/",
            "http://www.mindef.gov.sg/",
            "https://www.mindef.gov.sg:443/",
            "https://user@www.mindef.gov.sg/",
            "https://www.mindef.gov.sg/news?copy=1",
            "https://www.mindef.gov.sg/news#part",
            "https://www.mindef.gov.sg/a/../b/",
            "https://www.mindef.gov.sg//evil",
            "https://www.mindef.gov.sg/%2e%2e/secret",
            None, "", " https://www.mindef.gov.sg/",
        ):
            with self.subTest(url=url):
                self.assertFalse(source_link_approved("sg_mindef_releases", url))

    def test_record_template_preserves_source_text_hold(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/record.html").read_text(encoding="utf-8")
        start = template.index("{% elif record.source_slug == 'sg_mindef_releases' %}")
        stop = template.index('{% else %}\n    <section class="record-section" aria-labelledby="record-text">', start)
        branch = template[start:stop]
        self.assertNotIn("text_original", branch)
        self.assertIn("MINDEF's original article text and media are not reproduced", branch)
        self.assertIn("record.mindef_link_allowed", branch)
        self.assertIn("record.source_slug != 'sg_mindef_releases' or record.mindef_link_allowed", template)

    def test_source_directory_official_homepage_is_linked(self):
        from pathlib import Path
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/source.html").read_text(encoding="utf-8")
        self.assertNotIn("publisher homepage, not within approved linking scope", template)
        self.assertIn('href="{{ source.base_url }}"', template)

    def test_other_sources_unaffected(self):
        self.assertFalse(is_mindef_source("sg-other"))
        self.assertTrue(source_link_approved("uscc", "https://www.uscc.gov/"))
        self.assertTrue(source_link_approved("sg-other", "https://example.org/"))


if __name__ == "__main__":
    unittest.main()
