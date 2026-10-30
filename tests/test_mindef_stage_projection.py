"""Synthetic verification of non-destructive MINDEF DB separation staging."""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.stage_mindef_public_projection import (
    RESTRICTED_COLUMNS, stage,
)
from scripts.audit_mindef_public_surfaces import audit


class StagedMINDEFSeparationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.source = self.base / "source.db"
        self.private = self.base / "private-vault.db"
        self.public = self.base / "public-candidate.db"
        self.receipt = self.base / "receipt.json"
        with sqlite3.connect(self.source) as con:
            con.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT UNIQUE);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, url TEXT UNIQUE, content_hash TEXT,
                    source_id INTEGER REFERENCES sources(id), scrape_run_id INTEGER,
                    title_original TEXT, text_original TEXT, published_date TEXT,
                    scraped_at TEXT, title_english TEXT, text_english TEXT,
                    summary_english TEXT, relevance_reasoning TEXT,
                    significance_reasoning TEXT
                );
                INSERT INTO sources VALUES (1, 'sg_mindef_releases');
                INSERT INTO sources VALUES (2, 'unrelated');
                INSERT INTO articles VALUES (
                    101,'https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/',
                    'HASH-101',1,7,'FAKE ORIGINAL TITLE','FAKE SOURCE BODY','2026-10-23',
                    '2026-10-24','FAKE TRANSLATION','FAKE LONG TRANSLATION',
                    'FAKE SUMMARY','FAKE REASON','FAKE SIGNIFICANCE'
                );
                INSERT INTO articles VALUES (
                    202,'https://example.org/other','HASH-202',2,8,'OTHER TITLE',
                    'OTHER BODY','2026-10-23','2026-10-24','OTHER TRANSLATION',
                    NULL,'OTHER SUMMARY',NULL,NULL
                );
            """)

    def run_stage(self):
        return stage(self.source, self.private, self.public, self.receipt)

    def test_private_full_fidelity_and_public_redacted_candidate(self):
        source_bytes = hashlib.sha256(self.source.read_bytes()).hexdigest()
        receipt = self.run_stage()
        self.assertEqual(source_bytes, hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(receipt["source_record_count"], 1)
        self.assertFalse(receipt["public_release_approved"])
        self.assertFalse(receipt["durable_private_custody_confirmed"])
        with sqlite3.connect(self.private) as con:
            self.assertEqual(con.execute(
                "SELECT text_original FROM articles WHERE id=101").fetchone()[0],
                "FAKE SOURCE BODY")
        with sqlite3.connect(self.public) as con:
            row = con.execute("SELECT * FROM articles WHERE id=101")
            cols = [x[0] for x in row.description]
            data = dict(zip(cols, row.fetchone()))
            self.assertTrue(all(data[f] is None for f in RESTRICTED_COLUMNS))
            self.assertEqual(data["content_hash"], "HASH-101")
            self.assertEqual(data["url"], "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/")
            self.assertEqual(con.execute(
                "SELECT text_original FROM articles WHERE id=202").fetchone()[0],
                "OTHER BODY")
        self.assertTrue(self.receipt.is_file())
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.public.stat().st_mode & 0o777, 0o600)

    def test_refuses_overwrites_and_preserves_source(self):
        self.private.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            self.run_stage()
        self.assertFalse(self.public.exists())
        self.assertEqual(self.private.read_text(encoding="utf-8"), "existing")

    def test_no_partial_files_for_empty_singapore_source(self):
        with sqlite3.connect(self.source) as con:
            con.execute("DELETE FROM articles WHERE source_id=1")
        with self.assertRaisesRegex(ValueError, "no matching Singapore"):
            self.run_stage()
        self.assertFalse(self.private.exists())
        self.assertFalse(self.public.exists())
        self.assertFalse(self.receipt.exists())

    def test_sanitized_candidate_is_not_release_without_safe_render(self):
        self.run_stage()
        output = self.base / "output"
        (output / "record").mkdir(parents=True)
        (output / "record/101.html").write_text(
            "<h1>Singapore MINDEF release</h1>"
            '<a href="https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/">'
            "Authorized link</a>", encoding="utf-8")
        census = audit(self.public, output)
        self.assertTrue(census["release_eligible_from_this_scan"])
        # A clean projection alone still does NOT check durable custody,
        # deployed copies, other editorial data, historical Git or links.
        self.assertFalse(census["historical_repository_and_cdn_exposure_not_audited"] is False)


if __name__ == "__main__":
    unittest.main()
