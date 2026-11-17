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

    def test_atlas_labels_stay_clear_of_each_other_and_inside_the_map(self):
        # The regional atlas (2026-11-17): no name overlaps another name or
        # another desk's mark, and none leaves the map, at any width.
        probe = """() => {const m=document.querySelector('.atlas-map').getBoundingClientRect();
          const r=[...document.querySelectorAll('.atlas .seat')].map(a=>{
            const t=a.querySelector('.seat-text').getBoundingClientRect(),k=a.querySelector('.seat-mark').getBoundingClientRect();
            return {n:a.querySelector('b').textContent,t:[t.left,t.top,t.right,t.bottom],
                    k:[k.left+12,k.top+12,k.right-12,k.bottom-12],h:a.getBoundingClientRect().height}});
          const hit=(a,b)=>a[0]<b[2]&&b[0]<a[2]&&a[1]<b[3]&&b[1]<a[3],out=[];
          for(let i=0;i<r.length;i++)for(let j=0;j<r.length;j++){if(i===j)continue;
            if(j>i&&hit(r[i].t,r[j].t))out.push(r[i].n+' / '+r[j].n);
            if(hit(r[i].t,r[j].k))out.push(r[i].n+' over the mark of '+r[j].n)}
          for(const x of r){if(x.t[0]<m.left-1||x.t[2]>m.right+1||x.t[1]<m.top-1||x.t[3]>m.bottom+1)out.push(x.n+' outside the map');
            if(x.h<40)out.push(x.n+' target under 40px')}
          return {count:r.length,problems:out}}"""
        for width in WIDTHS + (414, 1024):
            ctx = self.browser.new_context(viewport={"width": width, "height": 900})
            page = ctx.new_page()
            try:
                page.goto((self.out / "desks.html").as_uri(), wait_until="load")
                result = page.evaluate(probe)
            finally:
                ctx.close()
            with self.subTest(width=width):
                self.assertEqual(result["count"], len(self.registry))
                self.assertEqual(result["problems"], [])

    def test_atlas_navigation_pairs_and_responsive_order(self):
        """The introductory index links to the existing register, with the
        map using the same desk order, at phone, tablet and desktop widths."""
        for width in WIDTHS + (1024,):
            ctx = self.browser.new_context(viewport={"width": width, "height": 900},
                                           reduced_motion="reduce")
            page = ctx.new_page()
            try:
                page.goto((self.out / "desks.html").as_uri(), wait_until="load")
                links = page.locator(".desk-jump-list a")
                maps = page.locator(".atlas-seats a")
                self.assertEqual(links.count(), len(self.registry))
                self.assertEqual(maps.count(), links.count())
                jump_targets = links.evaluate_all(
                    "(n) => n.map(a => a.getAttribute('href'))")
                map_targets = maps.evaluate_all(
                    "(n) => n.map(a => a.getAttribute('href'))")
                self.assertEqual(jump_targets, map_targets)
                for slug, target in [(a.removeprefix("#desk-"), a)
                                     for a in jump_targets]:
                    self.assertIn(slug, self.registry)
                    self.assertEqual(page.locator(target).count(), 1)
                    self.assertIn(self.registry[slug].status_label,
                                  page.locator('.desk-jump-list a[data-desk="%s"]' % slug).inner_text())
                atlas = page.locator(".atlas").bounding_box()
                jump = page.locator(".desk-jump").bounding_box()
                if width >= 1140:
                    self.assertLessEqual(jump["x"] + jump["width"],
                                         atlas["x"] + 2)
                else:
                    self.assertGreaterEqual(jump["y"], atlas["y"] + atlas["height"] - 2)
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),
                                     width + 1)
                # The matched highlight is a progressive enhancement: both
                # lists remain ordinary working links without JavaScript.
                links.first.hover()
                decoration = maps.first.locator("b").evaluate(
                    "(n) => getComputedStyle(n).textDecorationLine")
                self.assertIn("underline", decoration)
                maps.first.hover()
                bg = links.first.evaluate("(n) => getComputedStyle(n).backgroundColor")
                self.assertNotEqual(bg, "rgba(0, 0, 0, 0)")
            finally:
                ctx.close()

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
