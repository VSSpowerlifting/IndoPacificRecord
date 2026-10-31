"""Synthetic index boundaries and read-only committed Vietnam source bindings."""
from __future__ import annotations

import hashlib
import copy
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.regional_official_link_release import SCHEMA_SQL
from scripts.verify_regional_source_index_readback import (
    ReadbackHold, MetadataOnlySourceParser, main, validate_page, verify,
    vietnam_explanations, verify_vietnam_https,
)
from tests.test_regional_live_site_wiring import html_for
from tests.test_regional_official_link_render import insert
from core.regional_official_link_render import load_admitted_links


class RegionalReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "db.sqlite"
        self.site = self.root / "committed"
        self.pages = self.root / "deployed"
        self.site.mkdir()
        self.pages.mkdir()
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE scratch (id INTEGER)")
        con.commit()
        con.close()
        self.make_pages()

    def make_pages(self):
        for desk in ("philippines", "indonesia"):
            (self.site / (desk + ".html")).write_text(
                html_for(desk, []), encoding="utf-8")

    def migrate(self):
        con=sqlite3.connect(str(self.db))
        con.execute(SCHEMA_SQL)
        con.commit()
        return con

    def admit_afp(self):
        con = self.migrate()
        insert(con)
        con.commit()
        con.close()
        self.make_pages_with_admitted()

    def make_pages_with_admitted(self):
        for desk in ("philippines", "indonesia"):
            rows = load_admitted_links(self.db, desk)
            (self.site / (desk + ".html")).write_text(
                html_for(desk, rows), encoding="utf-8")

    def digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()

    def test_no_migration_has_zero_and_not_live(self):
        before=self.digest()
        packet=verify(self.db,self.site)
        self.assertEqual(packet["source_families"]["ph_afp_articles"][
            "admitted_official_link_count"],0)
        self.assertEqual(packet["source_families"]["id_kemhan_news"][
            "admitted_official_link_count"],0)
        self.assertEqual(self.digest(),before)
        self.assertFalse(Path(str(self.db)+"-wal").exists())
        self.assertFalse(Path(str(self.db)+"-shm").exists())

    def test_empty_source_index_cannot_masquerade_as_live(self):
        con=self.migrate()
        con.close()
        with self.assertRaisesRegex(ReadbackHold, "claimed_live_desk"):
            verify(self.db,self.site,require_records=True)

    def test_exact_rendered_record_matches_sqlite(self):
        self.admit_afp()
        before=self.digest()
        result=verify(self.db,self.site)
        self.assertEqual(result["source_families"]["ph_afp_articles"][
            "admitted_official_link_count"],1)
        self.assertEqual(result["source_families"]["id_kemhan_news"][
            "admitted_official_link_count"],0)
        self.assertEqual(self.digest(),before)

    def test_new_admitted_row_missing_from_rendered_page_holds(self):
        con=self.migrate()
        insert(con)
        con.commit()
        con.close()
        with self.assertRaisesRegex(ReadbackHold,
                                    "regional_source_section_presence_disagrees_with_db"):
            verify(self.db,self.site)

    def test_forged_unadmitted_extra_html_row_holds(self):
        con=self.migrate()
        con.close()
        fake=html_for("philippines", [{
            "source_identity":"afp:1499",
            "canonical_official_url":"https://www.afp.mil.ph/news/fake",
            "publisher_posted_date":"2026-10-15",
            "label":"AFP official source"}])
        (self.site/"philippines.html").write_text(fake,encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "presence_disagrees_with_db"):
            verify(self.db,self.site)

    def test_tampered_official_url_rejected_against_db(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        original=page.read_text(encoding="utf-8")
        page.write_text(original.replace(
            "https://www.afp.mil.ph/news/fictional-exercise",
            "https://www.afp.mil.ph/news/other-source"),
            encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold,
                                    "html_link_date_or_neutral_label_differs_from_db"):
            verify(self.db,self.site)

    def test_tampered_publisher_date_rejected_against_db(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        page.write_text(page.read_text(encoding="utf-8").replace(
            'datetime="2026-10-15"','datetime="2026-10-14"'),
            encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "html_link_date_or_neutral_label"):
            verify(self.db,self.site)

    def test_duplicate_row_rejected_even_with_same_source_id(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        original=page.read_text(encoding="utf-8")
        start=original.index('    <li data-regional-official-source-id="afp:1499"')
        end=original.index("</li>",start)+5
        page.write_text(original[:end]+original[start:end]+original[end:],
                        encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold,"rendered_official_source_count"):
            verify(self.db,self.site)

    def test_two_claimed_live_desks_require_two_eligible_source_rows(self):
        self.admit_afp()
        with self.assertRaisesRegex(ReadbackHold, "claimed_live_desk"):
            verify(self.db,self.site,require_records=True)

    def test_independent_afp_activation_does_not_require_kemhan_launch(self):
        self.admit_afp()
        receipt = verify(self.db, self.site, required_desks=("philippines",))
        self.assertEqual(receipt["source_families"]["ph_afp_articles"][
            "admitted_official_link_count"], 1)
        self.assertEqual(receipt["source_families"]["id_kemhan_news"][
            "admitted_official_link_count"], 0)

    def test_required_indonesia_launch_stays_held_if_only_afp_live(self):
        self.admit_afp()
        with self.assertRaisesRegex(ReadbackHold, "claimed_live_desk"):
            verify(self.db, self.site, required_desks=("indonesia",))

    def test_unknown_required_desk_cannot_be_promoted(self):
        with self.assertRaisesRegex(ReadbackHold,
                                    "unknown_required_regional_source_desk"):
            verify(self.db, self.site, required_desks=("atlantis",))

    def test_pages_byte_parity_succeeds_if_equal(self):
        self.admit_afp()
        for page in self.site.glob("*.html"):
            shutil.copyfile(page,self.pages/page.name)
        receipt=verify(self.db,self.site,pages_dir=self.pages)
        self.assertTrue(receipt["site_bytes_match_deployed_checkout"])
        self.assertFalse(receipt["actual_pages_deployed_by_this_check"])

    def test_changed_deployed_page_fails_even_with_same_number_of_links(self):
        self.admit_afp()
        for page in self.site.glob("*.html"):
            shutil.copyfile(page,self.pages/page.name)
        page=self.pages/"philippines.html"
        page.write_bytes(page.read_bytes()+b"\n<!-- injected stale edit -->\n")
        with self.assertRaisesRegex(ReadbackHold,"deployed_pages_route_differs"):
            verify(self.db,self.site,pages_dir=self.pages)

    def test_missing_published_page_always_fails(self):
        self.admit_afp()
        (self.site/"indonesia.html").unlink()
        with self.assertRaisesRegex(ReadbackHold,"committed_regional_desk_page_missing"):
            verify(self.db,self.site)

    def test_schema_present_but_corrupt_is_hard_hold(self):
        con=sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE regional_official_source_links(id INTEGER)")
        con.commit()
        con.close()
        with self.assertRaises(Exception):
            verify(self.db,self.site)

    def test_no_original_text_in_receipt(self):
        self.admit_afp()
        packet=verify(self.db,self.site)
        blob=json.dumps(packet)
        self.assertNotIn("original_title",blob)
        self.assertNotIn("publisher_body",blob)
        self.assertIn("source_families",packet)


class VietnamExplanationReadbackTests(unittest.TestCase):
    """Replay committed admissions read-only; no synthetic operational claim."""

    def setUp(self):
        self.db = Path(__file__).resolve().parents[1] / "pla_watch.db"
        self.page = self.db.parent / "output/vietnam.html"
        self.rows = load_admitted_links(self.db, "vietnam")
        self.bindings = vietnam_explanations(self.db, self.rows)
        self.html = self.page.read_text()
        self.sid = "vpcp-vi:220065"
        self.route = self.bindings[self.sid]

    def test_committed_bibliography_and_explanation_share_exact_identity(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.assertEqual(validate_page(self.html, self.rows,
                                       explanations=self.bindings), len(self.rows))
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertEqual(self.page.read_text(), self.html)
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_internal_link_needs_committed_admission_not_just_a_record_path(self):
        with self.assertRaisesRegex(ReadbackHold, "explanation_does_not_match"):
            validate_page(self.html, self.rows)
        wrong = dict(self.bindings, **{self.sid: "record/1.html"})
        with self.assertRaisesRegex(ReadbackHold, "explanation_does_not_match"):
            validate_page(self.html, self.rows, explanations=wrong)

    def test_vpcp_subject_stays_bibliography_separate_from_english_explanation(self):
        parser = MetadataOnlySourceParser()
        parser.feed(self.html)
        parser.close()
        row = next(r for r in parser.rows if r["source_identity"] == self.sid)
        expected = next(r for r in self.rows if r["source_identity"] == self.sid)
        self.assertEqual(row["label"].strip(), expected["document"]["document_number"])
        self.assertIn(expected["document"]["subject"], self.html)
        self.assertEqual(row["explanation"], self.route)
        self.assertNotIn("English machine explanation", row["label"])

    def test_second_official_url_stays_held_even_if_identical(self):
        row = next(r for r in self.rows if r["source_identity"] == self.sid)
        from html import escape
        for url in (row["canonical_official_url"],
                    row["canonical_official_url"].replace("220065", "220077")):
            changed = self.html.replace('href="' + self.route + '">Read',
                'rel="noopener noreferrer" href="' + escape(url, quote=True) + '">Read')
            with self.subTest(url=url), self.assertRaisesRegex(
                    ReadbackHold, "more_than_one_official_source_url"):
                validate_page(changed, self.rows, explanations=self.bindings)

    def test_repeated_explanation_is_not_an_extra_record_or_ignored(self):
        changed = self.html.replace('href="' + self.route + '">Read',
            'href="' + self.route + '">Duplicate</a><a href="' + self.route + '">Read')
        with self.assertRaisesRegex(ReadbackHold, "more_than_one_published_explanation"):
            validate_page(changed, self.rows, explanations=self.bindings)

    def test_same_official_url_under_conflicting_identities_stays_held(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["canonical_official_url"] = rows[0]["canonical_official_url"]
        with self.assertRaisesRegex(ReadbackHold, "official_url_shared_by_source_identities"):
            validate_page(self.html, rows, explanations=self.bindings)

    def test_changed_bibliography_invalidates_stale_explanation(self):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r["source_identity"] == self.sid)
        row["document"]["signatory"] = "Synthetic changed signatory"
        with self.assertRaisesRegex(ReadbackHold, "explanation_does_not_match"):
            vietnam_explanations(self.db, rows)

    def test_changed_content_or_rejected_qa_cannot_supply_explanation_binding(self):
        from scripts.reconcile_db import read_only
        for fault in ("content", "qa"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                db = Path(tmp) / "scratch.db"
                with read_only(str(self.db)) as source, sqlite3.connect(str(db)) as conn:
                    source.backup(conn)
                    if fault == "content":
                        conn.execute("UPDATE articles SET content_hash=? WHERE id=5646", ("a" * 64,))
                    else:
                        proof = json.loads(conn.execute("SELECT qa_json FROM vietnam_article_provenance "
                            "WHERE article_id=5646").fetchone()[0])
                        proof["outcome"] = "held_review"
                        conn.execute("UPDATE vietnam_article_provenance SET qa_json=? WHERE article_id=5646",
                                     (json.dumps(proof),))
                with self.assertRaisesRegex(ReadbackHold, "explanation_does_not_match"):
                    vietnam_explanations(db, self.rows)

    def test_different_official_url_cannot_borrow_an_admitted_explanation(self):
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r["source_identity"] == self.sid)
        row["canonical_official_url"] += "&unverified=1"
        with self.assertRaisesRegex(ReadbackHold, "explanation_does_not_match"):
            vietnam_explanations(self.db, rows)

    def test_internal_link_cannot_borrow_another_source_identity(self):
        changed = self.html.replace('data-regional-official-source-id="' + self.sid + '"',
                                    'data-regional-official-source-id="mps-vi:1"')
        with self.assertRaisesRegex(ReadbackHold, "unadmitted_or_duplicate_source_id"):
            validate_page(changed, self.rows, explanations=self.bindings)

    def test_https_readback_requires_exact_bytes_and_same_source_binding(self):
        receipt = verify_vietnam_https(self.db, self.page.parent,
                                      fetch=lambda url: self.page.read_bytes())
        self.assertEqual(receipt["admitted_official_link_count"], len(self.rows))
        with self.assertRaisesRegex(ReadbackHold, "https_bytes_differ"):
            verify_vietnam_https(self.db, self.page.parent,
                                 fetch=lambda url: self.page.read_bytes() + b"stale")

    def test_ordinary_daily_checks_vietnam_after_deploy_before_success_marker(self):
        workflow = (self.db.parent / ".github/workflows/daily_update.yml").read_text()
        name = "      - name: Reconcile Vietnam SQLite, HTML and Pages"
        start = workflow.index(name)
        step = workflow[start:workflow.index("      - name:", start + len(name))]
        self.assertLess(workflow.index("- name: Deploy to GitHub Pages"), start)
        self.assertLess(start, workflow.index("- name: Record successful run"))
        self.assertNotIn("continue-on-error", step)
        self.assertIn("VIETNAM_DAILY_HANDOFF_ENABLED == 'true'", step)
        self.assertIn("--deployed-dir", step)
        self.assertIn("--vietnam-https", step)
        # The wait must outlast a normal Pages build (22-71 s recorded) yet
        # stay bounded, and exhausting it must still fail the run.
        import re
        loop = re.search(r"for attempt in \$\(seq 1 (\d+)\); do(.*?)\n\s*done", step, re.S)
        self.assertIsNotNone(loop, "bounded retry loop is required")
        attempts = int(loop.group(1))
        pause = int(re.search(r"sleep (\d+)", loop.group(2)).group(1))
        self.assertGreaterEqual(attempts * pause, 180)
        self.assertLessEqual(attempts * pause, 600)
        self.assertNotIn("|| true", step)
        self.assertTrue(step.rstrip().endswith("exit 1"))
        self.assertIn("exit 1", step)


if __name__ == "__main__":
    unittest.main()
