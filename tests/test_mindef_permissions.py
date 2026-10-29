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

    def test_other_sources_unaffected(self):
        self.assertFalse(is_mindef_source("sg-other"))
        self.assertTrue(source_link_approved("uscc", "https://www.uscc.gov/"))
        self.assertTrue(source_link_approved("sg-other", "https://example.org/"))


if __name__ == "__main__":
    unittest.main()
