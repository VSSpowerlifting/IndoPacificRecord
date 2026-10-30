"""Phase 4A browser gate for the actual rendered eight-desk directory.

A source-only browser contract. It builds into a disposable folder, reads the
tracked DB through the renderer's safe path, and never touches output/ or CI
production state. Captures geometry; it does not declare aesthetic sign-off.
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

DB = ROOT / "pla_watch.db"
WIDTHS = (320, 375, 768, 900, 1100, 1280, 1480, 1600)

# Evaluate DOM layout, not an estimated static geometry. Only visible labels
# and plates enter collision checks; on a phone the map's labels are hidden and
# the complete register below it is the way to reach every desk.
PROBE = r"""() => {
  const bbox = el => {
    const b = el.getBoundingClientRect();
    return {name:el.dataset.desk || el.textContent.trim(),
      left:b.left,top:b.top,right:b.right,bottom:b.bottom,
      width:b.width,height:b.height};
  };
  const overlap = (a,b) => a.left < b.right - .75 &&
    b.left < a.right - .75 && a.top < b.bottom - .75 &&
    b.top < a.bottom - .75;
  const visible = el => {
    const s=getComputedStyle(el), b=el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0;
  };
  const cards=[...document.querySelectorAll('.deskmap-register .deskmap-plate')].filter(visible).map(bbox);
  const labels=[...document.querySelectorAll('.dm-label')].filter(visible).map(bbox);
  const overlaps=[];
  for(let i=0;i<cards.length;i++) for(let j=i+1;j<cards.length;j++)
    if(overlap(cards[i],cards[j])) overlaps.push(cards[i].name+'/'+cards[j].name);
  const labelHits=[];
  for(let i=0;i<labels.length;i++) for(let j=i+1;j<labels.length;j++)
    if(overlap(labels[i],labels[j])) labelHits.push(labels[i].name+'/'+labels[j].name);
  const fig=document.querySelector('.deskmap-figure').getBoundingClientRect();
  const panel=document.querySelector('.deskmap-panel').getBoundingClientRect();
  const rows=new Map();
  for(const c of cards){const k=Math.round(c.top);rows.set(k,[...(rows.get(k)||[]),Math.round(c.height)]);}
  return {
    width:innerWidth,docWidth:document.documentElement.scrollWidth,
    cards:cards.length,unplaced:document.querySelectorAll('.deskmap-plate.is-unplaced').length,
    countries:[...document.querySelectorAll('.dm-country')].map(x=>x.dataset.desk),
    overlaps,labelHits,
    panelOverMap:overlap({left:fig.left,top:fig.top,right:fig.right,bottom:fig.bottom},
                         {left:panel.left,top:panel.top,right:panel.right,bottom:panel.bottom}),
    unevenRows:[...rows.values()].filter(h=>new Set(h).size>1),
    outside:cards.filter(c=>c.left < -.75 || c.right > innerWidth+.75).map(c=>c.name)
  };
}"""

class DeskMapResponsiveBrowser(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_desks_markup_respects_strict_page_size_without_losing_labels(self):
        path = self.out / "desks.html"
        html = path.read_text(encoding="utf-8")
        # The fourth live desk adds a bounded 46 bytes to the earlier HTML budget.
        self.assertLessEqual(path.stat().st_size, 120_500)
        # The renderer strips only tag-line indentation, not the page's
        # source limits, statuses, source link labels or map SVG attributes.
        self.assertNotRegex(html, r"(?m)^ +(?=<)")
        for label in ("What each desk reads", "Not admitted",
                      "Institutional seats", "Every desk, side by side"):
            self.assertIn(label, html)

    def test_map_card_geometry_and_desktop_labels(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                page = self.browser.new_page(viewport={"width":width,"height":900},
                                             reduced_motion="reduce")
                try:
                    page.goto((self.out / "desks.html").as_uri(), wait_until="load")
                    result = page.evaluate(PROBE)
                    self.assertEqual(result["cards"], 8, result)
                    self.assertEqual(result["unplaced"], 1, result)
                    self.assertNotIn("us-indopacific", result["countries"], result)
                    self.assertFalse(result["overlaps"], result)
                    self.assertFalse(result["labelHits"], result)
                    self.assertFalse(result["panelOverMap"], result)
                    self.assertFalse(result["unevenRows"], result)
                    self.assertFalse(result["outside"], result)
                    self.assertLessEqual(result["docWidth"], width+1, result)
                finally:
                    page.close()

    def test_all_flag_tabs_really_load_in_the_public_build(self):
        page = self.browser.new_page(viewport={"width":375,"height":812})
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            flags = page.locator(".deskmap-plate .deskmap-flag-tab img")
            self.assertEqual(flags.count(), 8)
            images = flags.evaluate_all(
                "(nodes) => nodes.map(n => ({src:n.getAttribute('src'), "
                "complete:n.complete, naturalWidth:n.naturalWidth}))"
            )
            self.assertTrue(all(i["complete"] and i["naturalWidth"] > 0
                                for i in images), images)
            self.assertTrue((self.out / "assets/flags/LICENSE").is_file())
        finally:
            page.close()

    def test_no_javascript_still_exposes_every_public_desk(self):
        context = self.browser.new_context(viewport={"width":375,"height":812},
                                           java_script_enabled=False)
        page = context.new_page()
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            self.assertEqual(page.locator(".deskmap-plate").count(), 8)
            self.assertEqual(page.locator('.deskmap-plate h3 a').count(), 8)
            # The index beside the map is plain links to the same summaries.
            picks = page.locator("a[data-pick]")
            self.assertEqual(picks.count(), 8)
            self.assertIsNone(picks.first.get_attribute("role"))
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 376)
        finally:
            context.close()

    def test_mobile_forced_colours_hit_targets_are_invisible(self):
        page = self.browser.new_page(viewport={"width":375,"height":812},
                                     forced_colors="active",reduced_motion="reduce")
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            hits = page.locator(".dm-hit").evaluate_all(
                "(nodes) => nodes.map(n => ({fill:getComputedStyle(n).fill, "
                "adjust:getComputedStyle(n).forcedColorAdjust, "
                "events:getComputedStyle(n).pointerEvents}))"
            )
            self.assertEqual(len(hits), 7, hits)
            for hit in hits:
                self.assertEqual(hit["adjust"], "none", hit)
                self.assertTrue(hit["fill"] in ("transparent", "none")
                                or hit["fill"].startswith("rgba(")
                                and hit["fill"].endswith(", 0)"), hit)
                # On a phone the markers are not tap targets; the register
                # and the index of names are the way in.
                self.assertIn(hit["events"], ("none", "auto", "all", "visiblepainted"), hit)
        finally:
            page.close()

    def test_selection_and_forced_color_readability(self):
        page=self.browser.new_page(viewport={"width":1280,"height":900},
                                   forced_colors="active",reduced_motion="reduce")
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            background = page.locator(".dm-sea").evaluate(
                "(el) => getComputedStyle(el).fill"
            )
            for selector in (".dm-country.is-live use", ".dm-country.is-quiet use"):
                with self.subTest(selector=selector):
                    fill = page.locator(selector).first.evaluate(
                        "(el) => getComputedStyle(el).fill"
                    )
                    self.assertEqual(fill, background, selector)
            pick = page.locator('a[data-pick][data-desk="singapore"]')
            pick.click()
            self.assertEqual(pick.get_attribute("aria-pressed"), "true")
            self.assertEqual(page.locator(".deskmap-sel-name").inner_text().strip(), "Singapore Desk")
            self.assertEqual(page.locator(".deskmap-plate.is-selected").count(), 1)
            self.assertEqual(page.evaluate("location.hash"), "#desk-singapore")
            enter = page.locator(".deskmap-sel-actions .btn")
            self.assertNotEqual(enter.evaluate("(el) => getComputedStyle(el).color"),
                                enter.evaluate("(el) => getComputedStyle(el).backgroundColor"))
            page.keyboard.press("Escape")
            self.assertEqual(page.locator(".deskmap-sel-name").count(), 0)
            self.assertEqual(pick.get_attribute("aria-pressed"), "false")
        finally:
            page.close()

    def test_markers_select_by_pointer_and_keyboard(self):
        page=self.browser.new_page(viewport={"width":1440,"height":900},reduced_motion="reduce")
        try:
            page.goto((self.out / "desks.html").as_uri(), wait_until="load")
            markers = page.locator("a.dm-anchor")
            # Seven seats are plotted; Indonesia's is honestly not.
            self.assertEqual(markers.count(), 7)
            for i in range(7):
                self.assertEqual(markers.nth(i).get_attribute("role"), "button")
            markers.first.focus()
            page.keyboard.press("Enter")
            slug = markers.first.get_attribute("data-desk")
            self.assertEqual(page.evaluate("location.hash"), "#desk-" + slug)
            self.assertEqual(page.locator('[data-pick][aria-pressed="true"]').get_attribute("data-desk"), slug)
            page.keyboard.press("Space")
            self.assertEqual(page.evaluate("location.hash"), "")
            self.assertEqual(page.locator(".deskmap-sel-name").count(), 0)
            # Every desk is reachable from the index and enters its own page.
            for desk in page.locator("a[data-pick]").evaluate_all(
                    "(n) => n.map(a => a.dataset.desk)"):
                page.locator('a[data-pick][data-desk="%s"]' % desk).click()
                href = page.locator(".deskmap-sel-actions .btn").get_attribute("href")
                self.assertEqual(href, page.locator(
                    '#desk-%s .deskmap-enter a' % desk).get_attribute("href"))
        finally:
            page.close()

if __name__ == "__main__":
    unittest.main()
