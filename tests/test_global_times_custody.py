"""Global Times capture custody: one versioned row per capture, or no article.

Covers the custody contract (core/collection/global_times_custody.py), its
atomic binding to the article insert (storage/db.py), the per-source storage
failure it raises in the pipeline fold, and the parser's deliberate body hold.
"""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.collection import status as collection_status
from core.collection.contract import ExtractedDocument
from core.collection.global_times_custody import (
    FAMILY, METADATA_FIELDS, CustodyError, digest, metadata, provenance,
    record_capture, source_identity)
from storage import db

URL = "https://www.globaltimes.cn/page/202611/1373365.shtml"
WIRE = b"<html>fictional wire bytes</html>"
RUN = {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
       "GITHUB_SHA": "a" * 40}


def article(url=URL, wire=WIRE, text_held=None, **custody):
    body = {"capture_sha256": hashlib.sha256(wire).hexdigest(),
            "byline": "By Fictional Reporter", "pub_time": "Nov 20, 2026",
            "fetched_at": "2026-11-21T10:00:00Z", "text_held": text_held}
    body.update(custody)
    return {"url": url, "source_slug": FAMILY, "content_hash": "c" * 64,
            "title_original": "Fictional title", "text_original": "Body.",
            "published_date": "2026-11-20", "custody": body}


class Identity(unittest.TestCase):
    def test_identity_is_the_article_number(self):
        self.assertEqual(source_identity(URL), "gt:1373365")

    def test_a_non_article_url_is_refused(self):
        with self.assertRaises(CustodyError):
            source_identity("https://www.globaltimes.cn/china/index.html")

    def test_provenance_only_from_a_complete_actions_run(self):
        self.assertEqual(provenance(RUN), ("123-1", "a" * 40))
        self.assertIsNone(provenance({}))
        self.assertIsNone(provenance(dict(RUN, GITHUB_SHA="short")))

    def test_metadata_records_the_hold_reason(self):
        self.assertIn("text_held", METADATA_FIELDS)
        self.assertEqual(sorted(metadata(article())), sorted(METADATA_FIELDS))
        self.assertEqual(metadata(article(text_held="non_gt_byline"))["text_held"],
                         "non_gt_byline")
        self.assertIsNone(metadata(article())["text_held"])


class Recording(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE official_document_versions (source_family TEXT, "
            "source_identity TEXT, metadata_sha256 TEXT, metadata_json TEXT, "
            "capture_sha256 TEXT, first_observed_utc TEXT, source_run TEXT, "
            "collector_commit TEXT)")

    def rows(self):
        return self.conn.execute(
            "SELECT source_identity, metadata_sha256, metadata_json, "
            "capture_sha256, source_run, collector_commit "
            "FROM official_document_versions").fetchall()

    def test_written_once_then_unchanged(self):
        a = article(text_held="non_gt_byline")
        self.assertEqual(record_capture(self.conn, a, RUN), "written")
        self.assertEqual(record_capture(self.conn, a, RUN), "unchanged")
        (ident, msha, mjson, csha, run, commit), = self.rows()
        self.assertEqual((ident, csha, run, commit),
                         ("gt:1373365", hashlib.sha256(WIRE).hexdigest(),
                          "123-1", "a" * 40))
        self.assertEqual(json.loads(mjson)["text_held"], "non_gt_byline")
        self.assertEqual(msha, digest(json.loads(mjson)))

    def test_new_bytes_are_a_new_version(self):
        record_capture(self.conn, article(), RUN)
        record_capture(self.conn, article(wire=WIRE + b" "), RUN)
        self.assertEqual(len(self.rows()), 2)

    def test_no_run_provenance_writes_nothing(self):
        self.assertEqual(record_capture(self.conn, article(), {}), "no_provenance")
        self.assertEqual(self.rows(), [])

    def test_malformed_custody_raises(self):
        for bad in ({"capture_sha256": "nothex"}, {"fetched_at": None}):
            with self.subTest(bad=bad), self.assertRaises(CustodyError):
                record_capture(self.conn, article(**bad), RUN)

    def test_a_failed_write_raises(self):
        self.conn.execute("DROP TABLE official_document_versions")
        with self.assertRaises(CustodyError):
            record_capture(self.conn, article(), RUN)


class AtomicInsert(unittest.TestCase):
    """The article row and its capture row commit together or not at all."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "gt.db"
        self.binding = patch.object(db, "DB_PATH", self.path)
        self.binding.start()
        db.init_db()
        if db.get_source_id(FAMILY) is None:
            with db.get_conn() as c:
                c.execute("INSERT INTO sources(slug,display_name,base_url,language,"
                          "desk_id) VALUES(?,?,?,?,?)",
                          (FAMILY, "Global Times", "https://www.globaltimes.cn/",
                           "en", "china"))
        self.run_id = db.start_scrape_run()
        self.env = patch.dict("os.environ", RUN)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.binding.stop()
        self.tmp.cleanup()

    def count(self, table):
        with db.get_conn() as c:
            return c.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]

    def test_article_and_capture_commit_together(self):
        self.assertIsNotNone(db.insert_article(article(), self.run_id))
        self.assertEqual(self.count("articles"), 1)
        self.assertEqual(self.count("official_document_versions"), 1)

    def test_custody_failure_raises_and_stores_neither_row(self):
        with self.assertRaises(CustodyError):
            db.insert_article(article(capture_sha256="nothex"), self.run_id)
        self.assertEqual(self.count("articles"), 0)
        self.assertEqual(self.count("official_document_versions"), 0)

    def test_a_duplicate_url_is_still_none(self):
        db.insert_article(article(), self.run_id)
        self.assertIsNone(db.insert_article(article(), self.run_id))


class PipelineFold(unittest.TestCase):
    def test_custody_failure_is_counted_not_read_as_a_duplicate(self):
        import pipeline
        failed = Counter()

        def custody_fails():
            raise CustodyError("x")

        self.assertIsNone(pipeline._counting_custody(custody_fails, article(),
                                                     failed))
        self.assertEqual(failed, Counter({FAMILY: 1}))
        # A duplicate (None) and a stored row (an id) are not counted.
        self.assertIsNone(pipeline._counting_custody(lambda: None, article(), failed))
        self.assertEqual(pipeline._counting_custody(lambda: 7, article(), failed), 7)
        self.assertEqual(failed[FAMILY], 1)
        # Any other storage error still propagates.
        def other():
            raise sqlite3.OperationalError("disk")
        with self.assertRaises(sqlite3.OperationalError):
            pipeline._counting_custody(other, article(), failed)

    def test_custody_failure_marks_storage_failure(self):
        import pipeline
        result = SimpleNamespace(status=collection_status.OK, error_detail="prior")
        pipeline._mark_custody_failure(result, 2)
        self.assertEqual(result.status, collection_status.STORAGE_FAILURE)
        self.assertEqual(result.error_detail, "prior; 2 capture custody row(s) "
                                              "failed; those articles not stored")


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

    def test_a_held_body_is_not_text_unavailable(self):
        result = self.collect([self.doc("", "non_gt_byline"), self.doc("Body.")])
        self.assertEqual(result.status, collection_status.OK)
        self.assertEqual(result.text_unavailable, 0)
        self.assertIn("held by the parser (non_gt_byline)", result.error_detail)

    def test_an_all_held_run_is_not_an_extraction_failure(self):
        result = self.collect([self.doc("", "non_gt_byline")])
        self.assertEqual(result.status, collection_status.OK)
        self.assertEqual(result.text_unavailable, 0)

    def test_a_genuinely_blank_body_still_counts(self):
        result = self.collect([self.doc(""), self.doc("", "non_gt_byline")])
        self.assertEqual(result.text_unavailable, 1)
        result = self.collect([self.doc("")])
        self.assertEqual(result.status, collection_status.EXTRACTION_FAILURE)


if __name__ == "__main__":
    unittest.main()
