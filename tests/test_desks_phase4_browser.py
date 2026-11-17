"""Phase 4A browser gate for the rendered eight-desk directory (2026-11-16).

The map is retired; the directory is the page. Builds into a disposable
folder from the tracked DB through the renderer's safe path, never touching
output/ or production state. Every state and count is checked against the
registry and the build's own data, at phone through wide desktop widths.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402
from core.desk_registry import load_registry  # noqa: E402

DB = ROOT / "pla_watch.db"
WIDTHS = (320, 375, 768, 1100, 1280, 1600)

PROBE = r"""() => [...document.querySelectorAll('.deskmap-register section.desk')].map(s => ({
  slug: s.dataset.desk,
  name: s.querySelector('h3 a').textContent.trim(),
  href: s.querySelector('h3 a').getAttribute('href'),
  state: s.querySelector('.desk-state').textContent.trim(),
  records: [...s.querySelectorAll('.deskmap-stats div')].filter(d =>
    d.querySelector('dt').textContent.trim() === 'Records').map(d =>
    d.querySelector('dd').textContent.trim())[0],
  right: s.getBoundingClientRect().right
}))"""


class DesksDirectoryBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.is_file():
            raise unittest.SkipTest("tracked DB unavailable")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ipr-phase4a-browser-"))
        cls.out = cls.tmp / "preview"
        try:
            gp.build(cls.out, "Indo-Pacific Record", DB,
                     snapshot=gp.snapshot_from_corpus(DB))
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except Exception:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise
        cls.registry = {e.slug: e for e in load_registry().public_entries}

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _rows(self, **context):
        ctx = self.browser.new_context(**context)
        page = ctx.new_page()
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            return page.evaluate(PROBE), page.evaluate(
                "document.documentElement.scrollWidth")
        finally:
            ctx.close()

    def test_desks_markup_respects_strict_page_size(self):
        path = self.out / "desks.html"
        html = path.read_text(encoding="utf-8")
        self.assertLessEqual(path.stat().st_size, 120_500)
        for label in ("What each desk reads", "Every desk, side by side",
                      "What a state means"):
            self.assertIn(label, html)

    def test_every_desk_states_its_registry_state_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                rows, doc_width = self._rows(viewport={"width": width, "height": 900},
                                             reduced_motion="reduce")
                self.assertEqual(len(rows), 8, rows)
                self.assertEqual({r["slug"] for r in rows}, set(self.registry))
                for row in rows:
                    entry = self.registry[row["slug"]]
                    self.assertEqual(row["state"], entry.status_label, row)
                    self.assertEqual(row["href"], entry.route, row)
                    self.assertLessEqual(row["right"], width + 1, row)
                self.assertLessEqual(doc_width, width + 1)

    def test_counts_are_registry_counts_and_absence_is_never_zero(self):
        rows, _ = self._rows(viewport={"width": 1280, "height": 900})
        corpus = gp.load_corpus(DB)["corpus"]
        for row in rows:
            entry = self.registry[row["slug"]]
            held = sum(1 for r in corpus if r.get("desk_id") == row["slug"])
            with self.subTest(desk=row["slug"]):
                if held:
                    self.assertEqual(row["records"], "{:,}".format(held))
                else:
                    self.assertIn(row["records"], ("None in the public record", "None collected"))
                    self.assertNotIn("0", row["records"])
                if entry.status == "shadow":
                    self.assertNotRegex(row["records"], r"\d")

    def test_no_javascript_still_exposes_every_public_desk(self):
        rows, doc_width = self._rows(viewport={"width": 375, "height": 812},
                                     java_script_enabled=False)
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(r["href"] for r in rows))
        self.assertLessEqual(doc_width, 376)

    def test_on_page_contents_reach_real_sections(self):
        ctx = self.browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            targets = page.locator("nav.reader-contents a").evaluate_all(
                "(n) => n.map(a => a.getAttribute('href'))")
            self.assertTrue(targets)
            for target in targets:
                self.assertEqual(page.locator(target).count(), 1, target)
        finally:
            ctx.close()


if __name__ == "__main__":
    unittest.main()
