"""Synthetic-only contracts for the read-only Singapore MINDEF exposure audit."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.audit_mindef_public_surfaces import audit, main


class PublicMINDEFExposureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / "synthetic.db"
        self.output = self.root / "output"
        (self.output / "record").mkdir(parents=True)
        with sqlite3.connect(self.db) as db:
            db.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT UNIQUE);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, source_id INTEGER, url TEXT,
                    title_original TEXT, title_english TEXT, text_original TEXT,
                    summary_english TEXT
                );
                INSERT INTO sources VALUES (1, 'sg_mindef_releases');
                INSERT INTO sources VALUES (2, 'unrelated');
                INSERT INTO articles VALUES
                    (101, 1, 'https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/',
                     'SYNTHETIC TITLE', NULL, 'SYNTHETIC SOURCE BODY', 'SYNTHETIC SUMMARY');
                INSERT INTO articles VALUES
                    (102, 1, 'https://www.mindef.gov.sg/other/',
                     NULL, NULL, NULL, NULL);
                INSERT INTO articles VALUES
                    (200, 2, 'https://example.org/',
                     'UNRELATED TITLE', NULL, 'UNRELATED BODY', NULL);
            """)
        (self.output / "record/101.html").write_text(
            '<a href="https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/">'
            'Approved</a><div class="original-text"><p>SYNTHETIC SOURCE BODY</p></div>',
            encoding="utf-8")
        (self.output / "record/102.html").write_text(
            '<a href="https://www.mindef.gov.sg/other/">Not approved</a>',
            encoding="utf-8")

    def test_census_separates_body_database_and_links(self):
        r = audit(self.db, self.output)
        self.assertEqual(r["source_records"], 2)
        self.assertEqual(r["nonempty_db_fields"], {
            "title_original": 1, "title_english": 0,
            "text_original": 1, "summary_english": 1,
        })
        self.assertEqual(r["rendered_source_body_pages"], 1)
        self.assertEqual(r["approved_outbound_link_count"], 1)
        self.assertEqual(r["unapproved_outbound_link_count"], 1)
        self.assertEqual(r["unapproved_link_routes"], ["record/102.html"])
        self.assertFalse(r["release_eligible_from_this_scan"])

    def test_clean_projection_enforce_succeeds(self):
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE articles SET title_original=NULL, title_english=NULL, "
                       "text_original=NULL, summary_english=NULL WHERE source_id=1")
        (self.output / "record/101.html").write_text(
            '<a href="https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/">'
            'Approved</a>', encoding="utf-8")
        (self.output / "record/102.html").write_text(
            "<p>Unlinked, publisher URL recorded privately</p>", encoding="utf-8")
        r = audit(self.db, self.output)
        self.assertTrue(r["release_eligible_from_this_scan"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--db", str(self.db), "--output", str(self.output),
                                   "--enforce"]), 0)

    def test_enforce_fails_and_report_only_does_not_claim_clearance(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["--db", str(self.db), "--output", str(self.output)]), 0)
        self.assertFalse(json.loads(stdout.getvalue())["release_eligible_from_this_scan"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--db", str(self.db), "--output", str(self.output),
                                   "--enforce"]), 2)

    def test_no_original_text_or_titles_logged_and_no_mutation(self):
        h1 = hashlib.sha256(self.db.read_bytes()).hexdigest()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--db", str(self.db), "--output", str(self.output)])
        self.assertNotIn("SYNTHETIC SOURCE BODY", output.getvalue())
        self.assertNotIn("SYNTHETIC TITLE", output.getvalue())
        self.assertNotIn("SYNTHETIC SUMMARY", output.getvalue())
        self.assertEqual(h1, hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_missing_output_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "output directory missing"):
            audit(self.db, self.root / "missing")


if __name__ == "__main__":
    unittest.main()
