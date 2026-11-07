"""Synthetic, no-network Japan MOD original-replay and confidentiality tests."""
import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import japan_mod_official_links as gate
from core.japan_mod_original_replay import (
    JapanOriginalHold, replay_private_pdf, safe_cli_receipt)
from processing import pdf_text
from scripts.verify_japan_mod_original import run as cli_run
from tests.test_pdf_text import build_pdf

URL = "https://www.mod.go.jp/j/press/news/2026/10/23a.pdf"
IDENTITY = "jp_mod_news_ja:/j/press/news/2026/10/23a.pdf"
BODY = ("Synthetic Japan MOD notice about a fictional ministry event and "
        "hypothetical training planning. Every fact is invented for a test.")
COMMIT = "a" * 40


def sha(data):
    return hashlib.sha256(data).hexdigest()


class JapanOriginalReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.pdf = self.private / "original.pdf"
        self.install_pdf(build_pdf([BODY]))

    def install_pdf(self, pdf, *, archived=None, capture_hash=None,
                    stored_hash=None, slug=gate.FAMILY, first_seen="123456-1"):
        self.pdf.write_bytes(pdf)
        extraction = pdf_text.extract_pdf_text(pdf)
        stored_text = extraction.text if archived is None else archived
        digest = sha(stored_text.encode("utf-8"))
        if stored_hash is not None:
            digest = stored_hash
        db = self.root / "frozen.db"
        if db.exists():
            db.unlink()
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE shadow_records (url TEXT, source_slug TEXT,"
                        " content_sha256 TEXT, capture_sha256 TEXT,"
                        " text_original TEXT, first_seen_run TEXT,"
                        " published_date TEXT)")
            con.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?)",
                        (URL, slug, digest, capture_hash or sha(pdf),
                         stored_text, first_seen, "2026-10-23"))
        self.frozen = db.read_bytes()
        self.row = {
            "source_identity": IDENTITY, "source_family": gate.FAMILY,
            "canonical_official_url": URL, "source_git_commit": COMMIT,
            "first_seen_run": "123456-1", "publisher_posted_date": "2026-10-23"}
        self.evidence = {"source_commit": COMMIT,
                         "state_sha256": sha(self.frozen)}

    def replay(self, *, pdf=None, identity=IDENTITY, rows=None,
               state=None, evidence=None):
        with patch.object(gate, "candidates") as mocked_candidates, \
             patch.object(gate, "_blob",
                          return_value=self.frozen if state is None else state):
            # Use a list of trusted candidates, as candidates() returns.
            mocked_candidates.return_value = (
                [self.row] if rows is None else rows,
                self.evidence if evidence is None else evidence)
            return replay_private_pdf(
                self.repo, COMMIT, identity,
                self.pdf if pdf is None else pdf, fetch_run=lambda *_: None)

    def test_exact_version_replays_without_public_text_or_model_permission(self):
        receipt, text = self.replay()
        self.assertEqual(receipt["status"], "PDF_TEXT_LAYER_REPLAYED")
        self.assertEqual(receipt["pdf_capture_sha256"], sha(self.pdf.read_bytes()))
        self.assertEqual(receipt["text_sha256"], sha(text.encode()))
        self.assertEqual(text, pdf_text.extract_pdf_text(self.pdf.read_bytes()).text)
        self.assertEqual(receipt["page_count"], 1)
        for key in ("complete_pdf_visual_content_verified",
                    "publisher_license_qualified",
                    "external_model_input_authorized",
                    "public_original_authorized",
                    "machine_explanation_authorized",
                    "publication_authorized", "private_pdf_copied"):
            self.assertIs(receipt[key], False)
        safe = safe_cli_receipt(receipt)
        self.assertNotIn(BODY, safe)
        self.assertNotIn(str(self.pdf), safe)
        self.assertEqual(json.loads(safe), receipt)

    def test_changed_or_truncated_pdf_does_not_inherit_old_capture(self):
        orig = self.pdf.read_bytes()
        for payload in (orig + b" ", orig[:-16], b"<html>challenge</html>"):
            with self.subTest(length=len(payload)):
                self.pdf.write_bytes(payload)
                with self.assertRaisesRegex(JapanOriginalHold,
                                            "pdf_capture_version_mismatch"):
                    self.replay()
        self.pdf.write_bytes(orig)

    def test_archive_text_hash_and_exact_extraction_must_agree(self):
        self.install_pdf(self.pdf.read_bytes(),
                         stored_hash="b" * 64)
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "japan_shadow_text_hash_mismatch"):
            self.replay()
        self.install_pdf(self.pdf.read_bytes(),
                         archived="different but internally consistent text")
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "pdf_text_replay_mismatch"):
            self.replay()

    def test_no_text_layer_and_blank_pages_hold_even_when_pdf_hash_matches(self):
        self.install_pdf(build_pdf([None]))
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "pdf_original_extraction_unavailable"):
            self.replay()
        self.install_pdf(build_pdf([BODY, None]))
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "pdf_text_layer_incomplete_pages"):
            self.replay()

    def test_only_authenticated_news_family_and_exact_state_qualify(self):
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "source_not_in_authenticated_pdf_cohort"):
            self.replay(rows=[])
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "japan_shadow_db_version_mismatch"):
            self.replay(state=self.frozen + b"x")
        corrupt = b"synthetic non-sqlite bytes"
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "japan_shadow_db_invalid"):
            self.replay(state=corrupt,
                        evidence={"source_commit": COMMIT,
                                  "state_sha256": sha(corrupt)})
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "japan_source_commit_mismatch"):
            self.replay(evidence={"source_commit": "b" * 40,
                                  "state_sha256": sha(self.frozen)})
        self.install_pdf(self.pdf.read_bytes(), slug="jp_mod_siteupdate_ja")
        with self.assertRaisesRegex(JapanOriginalHold,
                                    "japan_shadow_record_identity_mismatch"):
            self.replay()

    def test_private_file_must_be_external_regular_and_not_a_symlink(self):
        within = self.repo / "accidental-public.pdf"
        within.write_bytes(self.pdf.read_bytes())
        with self.assertRaisesRegex(JapanOriginalHold, "regular_external_file"):
            self.replay(pdf=within)
        alias = self.private / "alias.pdf"
        alias.symlink_to(self.pdf)
        with self.assertRaisesRegex(JapanOriginalHold, "regular_external_file"):
            self.replay(pdf=alias)
        with self.assertRaisesRegex(JapanOriginalHold, "regular_external_file"):
            self.replay(pdf=self.root / "missing.pdf")

    def test_no_authenticated_source_is_safe_hold(self):
        with patch.object(gate, "candidates", side_effect=ValueError("invalid")):
            with self.assertRaisesRegex(JapanOriginalHold,
                                        "japan_shadow_lineage_unverified"):
                replay_private_pdf(
                    self.repo, COMMIT, IDENTITY, self.pdf, fetch_run=lambda *_: None)

    def test_cli_reports_hashes_only_and_fails_closed(self):
        output = io.StringIO()
        with patch.object(gate, "candidates",
                          return_value=([self.row], self.evidence)), \
             patch.object(gate, "_blob", return_value=self.frozen), \
             contextlib.redirect_stdout(output):
            code = cli_run([
                "--source-repo", str(self.repo),
                "--source-commit", COMMIT, "--source-identity", IDENTITY,
                "--local-pdf", str(self.pdf)], fetch_run=lambda *_: None)
        self.assertEqual(code, 0, output.getvalue())
        self.assertNotIn(BODY, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["status"],
                         "PDF_TEXT_LAYER_REPLAYED")
        output = io.StringIO()
        with patch.object(gate, "candidates", side_effect=ValueError("no")), \
             contextlib.redirect_stdout(output):
            code = cli_run([
                "--source-repo", str(self.repo),
                "--source-commit", COMMIT, "--source-identity", IDENTITY,
                "--local-pdf", str(self.pdf)], fetch_run=lambda *_: None)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "HOLD")
        self.assertNotIn(str(self.pdf), output.getvalue())


if __name__ == "__main__":
    unittest.main()
