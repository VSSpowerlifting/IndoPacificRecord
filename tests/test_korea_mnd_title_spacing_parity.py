"""Offline regression for 28 Oct 2026 Korea MND detail-title spacing drift.

Five authenticated private captures had identical words, dates, and release
identity, but two ASCII spaces in the detail heading versus one in the listing.
Only comparison-time duplicate-space folding is authorized. Never change the
actual extracted title, source identity, date, or admission rules.
"""
import re
import unicodedata

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import CollectionWindow
from tests.test_indonesia_korea_shadow import (
    Case, Response, ROWS, TARGET, adapter, fixture, kr_url,
)


class KoreaMNDTitleSpacingParityTests(Case):
    def setUp(self):
        super().setUp()
        row = next(r for r in ROWS if r.get("capture") == "korea-article-1.bin")
        self.url = kr_url(row["url"])
        self.original_html = fixture("korea-article-1.bin").decode("utf-8")

    def heading_variant(self, mutate):
        pattern = re.compile(r"(<h1>)([^<]+)(</h1>)")
        changed, count = pattern.subn(
            lambda m: m.group(1) + mutate(m.group(2)) + m.group(3),
            self.original_html, count=1,
        )
        self.assertEqual(count, 1)
        return changed

    def fetch_variant(self, html):
        a, session = adapter(
            "korea", {self.url: Response(self.url, html.encode("utf-8"))}
        )
        refs = a.discover(CollectionWindow(TARGET)).references
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].url, self.url)
        return a, session, a.fetch(refs[0])

    def test_extra_ascii_heading_space_does_not_reject_same_release(self):
        spaced = self.heading_variant(
            lambda title: title.replace(" ", "  ", 1)
        )
        a, session, capture = self.fetch_variant(spaced)
        self.assertEqual(capture.status, st.OK)
        result = a.extract(capture)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.documents[0].published_date, TARGET.isoformat())
        # Original detail title is retained, never silently rewritten to the
        # listing variant. The HWPX attachment remains mandatory.
        self.assertEqual(result.documents[0].title_original,
                         BeautifulSoup(spaced, "html.parser").select_one(
                             ".view_title h1").get_text(" ", strip=True))
        self.assertIn("  ", result.documents[0].title_original)
        self.assertTrue(
            any("/common/download.do" in req[1] for req in session.calls)
        )

    def test_non_ascii_and_invisible_title_differences_fail_closed(self):
        for replacement in ("\u00a0", "\t", "\u200b"):
            with self.subTest(replacement=repr(replacement)):
                changed = self.heading_variant(
                    lambda title: title.replace(" ", replacement, 1))
                _, session, capture = self.fetch_variant(changed)
                self.assertEqual(capture.status, st.EXTRACTION_FAILURE)
                self.assertFalse(any("/common/download.do" in req[1]
                                     for req in session.calls))
        changed = self.heading_variant(lambda title: unicodedata.normalize("NFD", title))
        self.assertNotEqual(changed, self.original_html)
        _, _, capture = self.fetch_variant(changed)
        self.assertEqual(capture.status, st.EXTRACTION_FAILURE)

    def test_extract_rechecks_the_same_title_relation(self):
        for mutation in (
                lambda title: title + " ALTERED",
                lambda title: title.replace(" ", "\u00a0", 1),
                lambda title: title.replace(" ", "\t", 1),
                lambda title: title.replace(" ", "\u200b", 1)):
            with self.subTest(mutation=mutation):
                a, _, capture = self.fetch_variant(self.original_html)
                self.assertEqual(capture.status, st.OK)
                # Exercise inherited extract independently of the fetch check.
                a.references[self.url]["title"] = mutation(a.references[self.url]["title"])
                result = a.extract(capture)
                self.assertEqual(result.status, st.EXTRACTION_FAILURE)
                self.assertIn("titles/identities disagree", result.error_detail)

    def test_non_korea_adapter_keeps_exact_title_comparison(self):
        a, _ = adapter("indonesia")
        ref = a.discover(CollectionWindow(TARGET, 0)).references[0]
        capture = a.fetch(ref)
        self.assertEqual(capture.status, st.OK)
        self.assertEqual(a.extract(capture).status, st.OK)
        title = a.references[ref.url]["title"]
        self.assertIn(" ", title)
        a.references[ref.url]["title"] = title.replace(" ", "  ", 1)
        result = a.extract(capture)
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertIn("titles/identities disagree", result.error_detail)

    def test_changed_word_still_fails_closed_before_attachment(self):
        changed = self.heading_variant(lambda title: title + " ALTERED")
        _, session, capture = self.fetch_variant(changed)
        self.assertEqual(capture.status, st.EXTRACTION_FAILURE)
        self.assertIn("metadata disagrees", capture.error_detail)
        self.assertFalse(
            any("/common/download.do" in req[1] for req in session.calls)
        )

    def test_changed_publisher_date_still_fails_closed(self):
        self.assertIn("2026.10.06", self.original_html)
        changed = self.original_html.replace("2026.10.06", "2026.10.05")
        _, session, capture = self.fetch_variant(changed)
        self.assertEqual(capture.status, st.EXTRACTION_FAILURE)
        self.assertIn("metadata disagrees", capture.error_detail)
        self.assertFalse(
            any("/common/download.do" in req[1] for req in session.calls)
        )


if __name__ == "__main__":
    import unittest
    unittest.main()
