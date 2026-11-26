"""Offline regression tests for the generated Japan 13-link release contract."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.guard_japan_official_reference_release import (
    JCG_LINKS, MOD_LINKS, REQUIRED_TEXT, validate_japan_release_html,
)


def example_html():
    lines = ['<html><body><section>']
    lines.extend("<p>" + phrase + "</p>" for phrase in REQUIRED_TEXT)
    for url in JCG_LINKS + MOD_LINKS:
        lines.append('<a href="' + url
                     + '" rel="noopener noreferrer">Official document</a>')
    lines.append("</section></body></html>")
    return "\n".join(lines)


class JapanOfficialReferenceReleaseTests(unittest.TestCase):
    def test_live_feed_is_separate_from_frozen_historical_navigation(self):
        html = example_html().replace("All Japan production records remain held",
            "Japan original-text production records remain held").replace(
            "Japan remains shadow-only; no production or model use is authorized",
            "The news-feed official-link metadata service is separate; original-text and model use remain held")
        html += ('<section class="regional-official-live-links"><a href="' + MOD_LINKS[0]
                 + '">Separate admitted record</a></section>')
        self.assertEqual(validate_japan_release_html(html), [])

    def test_all_thirteen_exact_reviewed_links_pass(self):
        self.assertEqual(len(JCG_LINKS), 6)
        self.assertEqual(len(MOD_LINKS), 7)
        self.assertIn("https://www.mod.go.jp/j/press/news/2026/09/17a.pdf", MOD_LINKS)
        self.assertIn("https://www.mod.go.jp/j/press/news/2026/09/29d.pdf", MOD_LINKS)
        self.assertNotIn("https://www.mod.go.jp/j/press/news/2026/10/02b.pdf", MOD_LINKS)
        self.assertEqual(validate_japan_release_html(example_html()), [])

    def test_missing_reference_fails_closed(self):
        html = example_html().replace(
            '<a href="' + MOD_LINKS[-1]
            + '" rel="noopener noreferrer">Official document</a>', "")
        self.assertTrue(any(MOD_LINKS[-1] in error for error
                            in validate_japan_release_html(html)))

    def test_duplicates_fail_closed(self):
        extra = '<a href="' + JCG_LINKS[0] + '" rel="noopener noreferrer">Again</a>'
        self.assertTrue(any("found 2" in error for error
                            in validate_japan_release_html(example_html() + extra)))

    def test_unreviewed_mod_pdf_fails_closed(self):
        extra = ('<a href="https://www.mod.go.jp/j/press/news/2026/10/09z.pdf"'
                 ' rel="noopener noreferrer">Unreviewed</a>')
        self.assertTrue(any("Unreviewed" in error for error
                            in validate_japan_release_html(example_html() + extra)))

    def test_outbound_link_protection_is_required(self):
        html = example_html().replace('rel="noopener noreferrer"', 'rel="noopener"', 1)
        self.assertTrue(any("Missing external-link protection" in error
                            for error in validate_japan_release_html(html)))

    def test_shadow_status_qualification_is_required(self):
        html = example_html().replace("All Japan production records remain held", "Ready")
        self.assertTrue(any("qualification" in error
                            for error in validate_japan_release_html(html)))

    def test_image_only_exception_scope_cannot_disappear(self):
        for phrase in ("Visual original review only: no extractable PDF text layer",
                       "No extractable text layer; not eight independent archive originals",
                       "The oversized October 2 original remains intentionally excluded."):
            with self.subTest(phrase=phrase):
                self.assertTrue(any("qualification" in error for error in
                    validate_japan_release_html(example_html().replace(phrase, "REDACTED"))))

    def test_template_cites_two_new_undelivered_originals_and_holds_oversized(self):
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/desk.html").read_text(encoding="utf-8")
        for url in MOD_LINKS:
            self.assertEqual(template.count('href="' + url + '"'), 1)
        self.assertNotIn('href="https://www.mod.go.jp/j/press/news/2026/10/02b.pdf"', template)
        self.assertIn("Seven independently inspected original Ministry PDFs", template)
        self.assertIn("Five are text-bearing shadow source originals", template)
        self.assertIn("visual original review only", template.lower())
        self.assertIn("not machine-extracted records", template.lower())
        self.assertIn("seven reviewed Japanese PDFs", template)

    def test_no_embedded_shadow_body_or_archive_link(self):
        for marker in ('state/shadow.db', 'text_original',
                       'href="archive.html?desk=japan"'):
            with self.subTest(marker=marker):
                self.assertTrue(any("boundary violated" in error for error
                                    in validate_japan_release_html(example_html() + marker)))



JCG_ID = "jcg-en:9477"
JCG_URL = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9477.html"
REPO = Path(__file__).resolve().parents[1]
H = "a" * 64


def make_db(path, rows):
    """Minimal fixture with only the columns the guard reads.

    ``rows``: (identity, publication_state, public_scope, date[, parent_hash]).
    """
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE daily_machine_records (source_family TEXT, source_identity TEXT,"
                 " metadata_version_sha256 TEXT, content_sha256 TEXT, capture_sha256 TEXT,"
                 " publication_state TEXT)")
    conn.execute("CREATE TABLE japan_jcg_source_records (source_identity TEXT,"
                 " canonical_official_url TEXT, publisher_posted_date TEXT,"
                 " metadata_version_sha256 TEXT, content_sha256 TEXT, capture_sha256 TEXT,"
                 " official_issuer TEXT, public_scope TEXT)")
    for ident, state, scope, day, *parent_hash in rows:
        url = "https://www.kaiho.mlit.go.jp/e/topics_archive/article" + ident[7:] + ".html"
        conn.execute("INSERT INTO daily_machine_records VALUES (?,?,?,?,?,?)",
                     ("jp_jcg_press_en", ident, H, H, H, state))
        conn.execute("INSERT INTO japan_jcg_source_records VALUES (?,?,?,?,?,?,?,?)",
                     (ident, url, day, (parent_hash or [H])[0], H, H, "jp_coast_guard", scope))
    conn.commit()
    conn.close()


def machine_section(entries):
    items = "".join(
        '<li data-machine-source="' + ident + '"><p>Summary.</p><p class="meta">'
        '<a href="record/source-x.html">Record and model details</a> · <a href="' + href
        + '" target="_blank" rel="noopener noreferrer">Official source</a></p></li>'
        for ident, href in entries)
    return ('<section class="desk-section" data-japan-machine-explanations>'
            '<ol class="desk-reference-list">' + items + '</ol></section>')


class JapanMachineSectionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fixture.db"

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, rows, entries, extra=""):
        make_db(self.db, rows)
        return validate_japan_release_html(
            example_html() + machine_section(entries) + extra, self.db)

    def test_admitted_machine_section_passes(self):
        self.assertEqual(self.errors([(JCG_ID, "released", "official_link_only", "2026-10-15")],
                                     [(JCG_ID, JCG_URL)]), [])

    def test_machine_section_without_database_fails_closed(self):
        html = example_html() + machine_section([(JCG_ID, JCG_URL)])
        self.assertTrue(any("requires SQLite reconciliation" in e
                            for e in validate_japan_release_html(html)))

    def test_held_machine_record_blocks(self):
        errors = self.errors([(JCG_ID, "held", "official_link_only", "2026-10-15")],
                             [(JCG_ID, JCG_URL)])
        self.assertTrue(any("Unadmitted or held" in e for e in errors))

    def test_held_parent_blocks(self):
        errors = self.errors([(JCG_ID, "released", "held", "2026-10-15")],
                             [(JCG_ID, JCG_URL)])
        self.assertTrue(any("Unadmitted or held" in e for e in errors))

    def test_parent_with_different_source_binding_blocks(self):
        errors = self.errors([(JCG_ID, "released", "official_link_only", "2026-10-15", "b" * 64)],
                             [(JCG_ID, JCG_URL)])
        self.assertTrue(any("Unadmitted or held" in e for e in errors))

    def test_unadmitted_identity_blocks(self):
        other = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9999.html"
        errors = self.errors([(JCG_ID, "released", "official_link_only", "2026-10-15")],
                             [("jcg-en:9999", other)])
        self.assertTrue(any("Unadmitted or held Japan machine record in machine section: jcg-en:9999"
                            in e for e in errors))

    def test_href_differing_from_canonical_blocks(self):
        row = [(JCG_ID, "released", "official_link_only", "2026-10-15")]
        for href in (JCG_URL + "#top", JCG_URL + "?a=1", JCG_URL.replace("https:", "http:"),
                     "https://www.kaiho.mlit.go.jp/e/topics_archive/article9465.html"):
            with self.subTest(href=href):
                self.assertTrue(any("differs from admitted canonical" in e
                                    for e in self.errors(row, [(JCG_ID, href)])))

    def test_missing_rel_protection_in_section_blocks(self):
        make_db(self.db, [(JCG_ID, "released", "official_link_only", "2026-10-15")])
        html = example_html() + machine_section([(JCG_ID, JCG_URL)]).replace(
            'rel="noopener noreferrer"', 'rel="noopener"')
        self.assertTrue(any("Missing external-link protection" in e
                            for e in validate_japan_release_html(html, self.db)))

    def test_duplicate_entry_blocks(self):
        errors = self.errors([(JCG_ID, "released", "official_link_only", "2026-10-15")],
                             [(JCG_ID, JCG_URL), (JCG_ID, JCG_URL)])
        self.assertTrue(any("Duplicate Japan machine entry" in e for e in errors))

    def test_extra_official_link_inside_section_blocks(self):
        make_db(self.db, [(JCG_ID, "released", "official_link_only", "2026-10-15")])
        extra_entry = machine_section([(JCG_ID, JCG_URL)]).replace(
            "</p></li>", ' <a href="' + MOD_LINKS[0] + '" rel="noopener noreferrer">PDF</a></p></li>')
        self.assertTrue(any("expected exactly one official link" in e for e in
                            validate_japan_release_html(example_html() + extra_entry, self.db)))
        loose = machine_section([(JCG_ID, JCG_URL)]).replace(
            "</ol>", '</ol><a href="https://www.mod.go.jp/j/press/x.html">Loose</a>')
        self.assertTrue(any("outside a machine entry" in e for e in
                            validate_japan_release_html(example_html() + loose, self.db)))

    def test_count_must_equal_min_five_admitted(self):
        rows = [("jcg-en:%d" % n, "released", "official_link_only", "2026-10-%02d" % (n - 9470))
                for n in range(9471, 9478)]
        latest = [("jcg-en:%d" % n, "https://www.kaiho.mlit.go.jp/e/topics_archive/article%d.html" % n)
                  for n in range(9477, 9472, -1)]
        self.assertEqual(self.errors(rows, latest), [])
        self.assertTrue(any("expected 5" in e for e in self.errors(rows, latest[:4])))
        older = latest[:4] + [("jcg-en:9471",
                               "https://www.kaiho.mlit.go.jp/e/topics_archive/article9471.html")]
        self.assertTrue(any("renderer order" in e for e in self.errors(rows, older)))

    def test_admitted_records_without_section_block(self):
        make_db(self.db, [(JCG_ID, "released", "official_link_only", "2026-10-15")])
        self.assertTrue(any("expected 1" in e for e in
                            validate_japan_release_html(example_html(), self.db)))

    def test_extra_jcg_link_outside_special_sections_still_blocks(self):
        extra = '<a href="' + JCG_URL + '" rel="noopener noreferrer">Unreviewed</a>'
        errors = self.errors([(JCG_ID, "released", "official_link_only", "2026-10-15")],
                             [(JCG_ID, JCG_URL)], extra)
        self.assertIn("Unreviewed official Japan link: " + JCG_URL, errors)

    def test_real_committed_page_and_database_pass(self):
        page, db = REPO / "output/japan.html", REPO / "pla_watch.db"
        before = db.read_bytes()
        html = page.read_text(encoding="utf-8")
        self.assertIn("data-japan-machine-explanations", html)
        self.assertEqual(validate_japan_release_html(html, db), [])
        self.assertTrue(any("requires SQLite reconciliation" in e
                            for e in validate_japan_release_html(html)))
        self.assertEqual(db.read_bytes(), before)
        self.assertFalse((REPO / "pla_watch.db-wal").exists())


if __name__ == "__main__":
    unittest.main()
