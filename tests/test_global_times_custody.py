"""Global Times capture custody facts produced by the public scraper code.

Covers the scraper's per-capture custody block (read only by the private collector,
core/collection/global_times_handoff.py) and the parser's deliberate body hold
as counted by the legacy collection adapter. No custody is written to the
public database (DECISION_LOG 2026-11-22, action D).
"""
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.collection import status as collection_status
from core.collection.contract import ExtractedDocument
from core.collection.global_times_handoff import FAMILY

URL = "https://www.globaltimes.cn/page/202611/1373365.shtml"
WIRE = b"<html>fictional wire bytes</html>"


class ContentType(unittest.TestCase):
    def test_header_charset_is_recorded_not_the_meta_charset(self):
        from scraper.sources.global_times_mil import GlobalTimesMilScraper
        wire = (b'<html><head><meta charset="utf-8"><title>Fictional</title>'
                b'</head><body></body></html>')
        resp = SimpleNamespace(content=wire,
                               headers={"Content-Type": "text/html; charset=gbk"})
        s = GlobalTimesMilScraper()
        s._on_response(URL, resp)
        s._captured[URL] = (wire, wire.decode())
        s._captured_type[URL] = s._last_content_type[URL]
        page = ('<html><head></head><body><h1>Fictional title</h1>'
                '<span class="byline">By Fictional Reporter</span>'
                '<p>Published: Nov 20, 2026</p><div class="article_right">'
                '<p>Fictional body text.</p></div></body></html>')
        s.target_date = __import__("datetime").date(2026, 11, 20)
        with patch.object(s, "_extract_date",
                          return_value="2026-11-20"), \
                patch.object(s, "_extract_text", return_value="Body."):
            art = s.parse_article(URL, page)
        self.assertEqual(art["custody"]["content_type"], "text/html; charset=gbk")


class HeldPageCustody(unittest.TestCase):
    """The custody block names the hold; whether bytes are kept is private."""

    def parse(self, byline):
        from scraper.sources.global_times_mil import GlobalTimesMilScraper
        s = GlobalTimesMilScraper()
        s.target_date = __import__("datetime").date(2026, 11, 20)
        s._captured[URL] = (WIRE, "")
        page = ('<html><head></head><body><h1>Fictional title</h1>'
                '<span class="byline">%s</span><p>Published: Nov 20, 2026</p>'
                '<div class="article_right"><p>Fictional body.</p></div>'
                '</body></html>' % byline)
        with patch.object(s, "_extract_date", return_value="2026-11-20"), \
                patch.object(s, "_extract_text", return_value="Fictional body."):
            return s.parse_article(URL, page)

    def test_held_page_carries_the_hold_and_a_blank_body(self):
        art = self.parse("By Xinhua")
        self.assertEqual(art["text_held"], "non_gt_byline")
        self.assertEqual(art["text_original"], "")
        self.assertEqual(art["custody"]["text_held"], "non_gt_byline")
        self.assertEqual(art["custody"]["capture_sha256"],
                         hashlib.sha256(WIRE).hexdigest())

    def test_the_scraper_no_longer_writes_or_claims_retention(self):
        from scraper.sources import global_times_mil as gt
        art = self.parse("By Fictional Reporter")
        self.assertNotIn("raw_retained", art["custody"])
        self.assertNotIn("text_held", art)
        self.assertFalse(hasattr(gt.GlobalTimesMilScraper, "_store_raw"))
        self.assertFalse(hasattr(gt, "RAW_CAPTURE_DIR_ENV"))


class DeliberateHold(unittest.TestCase):
    """A body held on purpose was read, not lost; a blank body still counts."""

    def doc(self, text, held=None):
        extra = {"text_held": held} if held else {}
        return ExtractedDocument(url=URL, source_slug=FAMILY, title_original="t",
                                 text_original=text, published_date="2026-11-20",
                                 extra=extra)

    def collect(self, docs):
        from adapters.legacy import LegacyScraperAdapter
        source = SimpleNamespace(slug=FAMILY, desk_id="china", enabled=True,
                                 adapter=None, language_tag="en")
        adapter = LegacyScraperAdapter(source, scraper_class=type("S", (), {}))
        refs = [object() for _ in docs]
        adapter.discover = lambda window: SimpleNamespace(
            ok=True, references=refs, status=collection_status.OK,
            error_detail=None)
        adapter.fetch = lambda ref: SimpleNamespace(ok=True)
        queue = list(docs)
        adapter.extract = lambda capture: SimpleNamespace(
            status=collection_status.OK, documents=[queue.pop(0)])
        result, documents = adapter.collect(None)
        self.assertEqual(len(documents), len(docs))
        return result

    def test_a_held_body_is_reported_without_failing_collection(self):
        result = self.collect([self.doc("", "non_gt_byline"), self.doc("Body.")])
        self.assertEqual(result.status, collection_status.OK)
        self.assertEqual(result.text_unavailable, 1)
        self.assertIn("held by the parser (non_gt_byline)", result.error_detail)

    def test_an_all_held_run_is_not_an_extraction_failure(self):
        result = self.collect([self.doc("", "non_gt_byline")])
        self.assertEqual(result.status, collection_status.OK)
        self.assertEqual(result.text_unavailable, 1)

    def test_a_genuinely_blank_body_still_counts(self):
        result = self.collect([self.doc(""), self.doc("", "non_gt_byline")])
        self.assertEqual(result.text_unavailable, 2)
        self.assertIn("held by the parser (non_gt_byline)", result.error_detail)
        result = self.collect([self.doc("")])
        self.assertEqual(result.status, collection_status.EXTRACTION_FAILURE)


if __name__ == "__main__":
    unittest.main()
