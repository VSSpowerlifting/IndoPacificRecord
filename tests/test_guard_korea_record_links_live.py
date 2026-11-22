"""A Korea-only Pages publication holds rather than link an unshipped Record.

The gate belongs in the writers' Pages jobs only. Holding the main commit
would also hold the release register the Daily needs to render the Record,
so a new release would never heal.
"""
import contextlib
import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.guard_korea_record_links_live import (HELD_EXIT, HOLD,
                                                   linked_records, main,
                                                   missing)

ROOT = Path(__file__).resolve().parents[1]
WRITERS = (".github/workflows/korea_verified_official_link_production.yml",
           ".github/workflows/korea_standing_original_text_production.yml")


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)


class KoreaRecordLinksLive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        # The rendered site a writer would publish from (main's output/).
        self.out = base / "output"
        (self.out / "korea-originals").mkdir(parents=True)
        (self.out / "korea.html").write_text('<a href="record/1.html">x</a>')
        (self.out / "korea-originals" / "100000001.html").write_text(
            '<a href="../korea.html">d</a><a class="korea-record-backlink" '
            'href="../record/1.html">r</a>')
        # The Pages checkout, holding record/1.html only.
        self.pages = base / "pages"
        (self.pages / "record").mkdir(parents=True)
        _git(self.pages, "init", "-q", "-b", "gh-pages")
        _git(self.pages, "config", "user.email", "t@example.invalid")
        _git(self.pages, "config", "user.name", "t")
        (self.pages / "record" / "1.html").write_text("r1")
        _git(self.pages, "add", "-A")
        _git(self.pages, "commit", "-qm", "pages")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--output", str(self.out), "--pages-repo", str(self.pages)])
        return code, buf.getvalue()

    def test_links_to_live_records_pass(self):
        self.assertEqual(linked_records(self.out), {"record/1.html"})
        self.assertEqual(missing(self.out, self.pages), [])
        self.assertEqual(self.run_cli()[0], 0)

    def test_new_release_holds_pages_until_the_daily_deploys_its_record(self):
        # The standing writer has committed a new release to main: the desk
        # and the new exhibit now link record/2.html, which only the next
        # Daily renders and deploys.
        (self.out / "korea.html").write_text(
            '<a href="record/1.html">x</a><a href="record/2.html">y</a>')
        (self.out / "korea-originals" / "100000002.html").write_text(
            '<a class="korea-record-backlink" href="../record/2.html">r</a>')
        code, text = self.run_cli()
        self.assertEqual(code, HELD_EXIT)
        self.assertIn("HOLD " + HOLD, text)
        self.assertIn("record/2.html not on Pages", text)
        # The Daily deploys record/2.html; the same publication now proceeds.
        (self.pages / "record" / "2.html").write_text("r2")
        _git(self.pages, "add", "-A")
        _git(self.pages, "commit", "-qm", "daily deploy")
        self.assertEqual(self.run_cli()[0], 0)

    def test_an_uncommitted_pages_file_is_not_live(self):
        # Only committed Pages content counts, never a stray working file.
        (self.pages / "record" / "3.html").write_text("r3")
        (self.out / "korea.html").write_text('<a href="record/3.html">y</a>')
        self.assertEqual(missing(self.out, self.pages), ["record/3.html"])

    def test_unknown_pages_ref_fails_closed(self):
        self.assertEqual(missing(self.out, self.pages, "refs/heads/nope"),
                         ["record/1.html"])


class GuardPlacement(unittest.TestCase):
    """The gate guards Pages publication only, and a hold stays green."""

    def test_guard_sits_in_the_pages_publication_not_the_main_commit(self):
        for rel in WRITERS:
            with self.subTest(workflow=rel):
                yaml = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(yaml.count("scripts.guard_korea_record_links_live"), 1)
                guard = yaml.index("scripts.guard_korea_record_links_live")
                push_main = yaml.index("git push origin HEAD:main")
                pages_checkout = yaml.index("ref: gh-pages")
                push_pages = yaml.index("git push origin HEAD:gh-pages")
                self.assertLess(push_main, guard)
                self.assertLess(pages_checkout, guard)
                self.assertLess(guard, push_pages)
                # The hold exits the Pages step green and later readbacks skip.
                self.assertIn('[ "$rc" -eq 3 ] || exit "$rc"', yaml)
                self.assertIn("held=true", yaml)
                readbacks = re.findall(r"if: .*held != 'true'", yaml)
                self.assertTrue(readbacks)

    def test_standing_noop_mismatch_routes_to_the_full_path(self):
        yaml = (ROOT / WRITERS[1]).read_text(encoding="utf-8")
        self.assertIn("if ! python -m scripts.verify_korea_standing_noop_parity; then",
                      yaml)


if __name__ == "__main__":
    unittest.main()
