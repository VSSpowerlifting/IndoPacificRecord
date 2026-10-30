"""Every published Brief shares navigable reading styles without prose edits.

This contract deliberately reads checked-in output. Rendering of source-linked
Nos. 18–19, native Nos. 15–17 and historical Nos. 1–14 is covered elsewhere.

Native Nos. 15–17 cite Singapore MINDEF records and are withheld whole by the
production rights boundary, so they are absent from the checked-in output. Their
reading structure is still verified from a build under an explicit *synthetic*
rights authority, which does not clear the real works.
"""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
HISTORICAL = (
    "05-09", "05-16", "05-23", "05-30", "06-06", "06-13", "06-20",
    "06-27", "07-04", "07-11", "07-18", "08-01", "08-08", "08-15",
)
NATIVE = (
    "maritime-cooperation-2026",
    "xiangshan-security-frames-defense-ties",
    "trident-resolve-regional-scale-specific-chinese-tasks",
    "what-is-being-built-in-laos",
    "three-days-chinese-flights-six-months-japanese-scrambles",
)
WITHHELD = NATIVE[:3]
PUBLISHED = NATIVE[3:]
PAGES = tuple(ROOT / "output/the-pla-watch/posts" / ("2026-" + day + ".html")
              for day in HISTORICAL) + tuple(
    ROOT / "output/briefs" / (slug + ".html") for slug in PUBLISHED)


def _toc_ok(case, path, soup):
    case.assertEqual(len(soup.select("h1")), 1)
    case.assertIsNotNone(soup.select_one(".brief-layout"))
    case.assertIsNotNone(soup.select_one(".brief-byline"))
    toc = soup.select_one("nav.brief-toc")
    case.assertIsNotNone(toc)
    targets = [a.get("href", "")[1:] for a in toc.select('a[href^="#"]')]
    case.assertGreaterEqual(len(targets), 3)
    for target in targets:
        case.assertIsNotNone(soup.find(id=target), (path, target))


class UnifiedBriefReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as gp
        cls.auth_tmp = Path(tempfile.mkdtemp(prefix="unified-reading-auth-"))
        cls.addClassCleanup(shutil.rmtree, cls.auth_tmp, ignore_errors=True)
        with mock.patch("core.mindef_public_boundary.editorial_hold", return_value=False):
            gp.build(cls.auth_tmp, gp.PUBLIC_TITLE, gp.TRACKED_DB,
                     snapshot=gp.snapshot_from_corpus(gp.TRACKED_DB))

    def test_all_sixteen_published_pages_keep_navigable_editorial_sections(self):
        self.assertEqual(len(PAGES), 16)
        for path in PAGES:
            with self.subTest(page=path.relative_to(ROOT)):
                soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
                _toc_ok(self, path, soup)

    def test_withheld_native_briefs_are_absent_from_output_but_read_well_when_authorised(self):
        for slug in WITHHELD:
            with self.subTest(slug=slug):
                self.assertFalse((ROOT / "output/briefs" / (slug + ".html")).exists())
                built = self.auth_tmp / "briefs" / (slug + ".html")
                soup = BeautifulSoup(built.read_text(encoding="utf-8"), "html.parser")
                _toc_ok(self, built, soup)

    def test_unified_css_is_generated_and_uses_turquoise_not_red(self):
        source = (ROOT / "site/preview/briefs.css").read_bytes()
        output = (ROOT / "output/briefs.css").read_bytes()
        self.assertEqual(output, source)
        css = source.decode("utf-8")
        self.assertIn(".brief-layout>.brief-reading-navigation{position:sticky;", css)
        self.assertIn(".brief-layout:not(.brief-layout--structured) .brief-main>.brief-section[id]:target", css)
        self.assertIn(".brief-reading-finding{border-top:2px solid var(--accent);", css)
        self.assertIn(".brief-signal{border:0;", css)
        self.assertNotIn("var(--crimson)", css)
        self.assertNotIn("var(--crimson-ink)", css)

    def test_historical_routes_and_laos_owner_presentation_remain_distinct(self):
        historic = (ROOT / "output/analysis.html").read_text(encoding="utf-8")
        for day in HISTORICAL:
            with self.subTest(issue=day):
                self.assertIn("/the-pla-watch/posts/2026-" + day + ".html", historic)
        laos = BeautifulSoup((ROOT / "output/briefs/what-is-being-built-in-laos.html")
                             .read_text(encoding="utf-8"), "html.parser")
        self.assertIsNotNone(laos.select_one(".brief-layout--structured"))
        self.assertEqual(len(laos.select("[data-manuscript-paragraph]")), 11)
        self.assertEqual(len(laos.select(".brief-reading-section")), 5)
        for slug in WITHHELD:
            with self.subTest(native=slug):
                page = BeautifulSoup((self.auth_tmp / "briefs" / (slug + ".html"))
                                     .read_text(encoding="utf-8"), "html.parser")
                self.assertIsNone(page.select_one(".brief-layout--structured"))
                self.assertIsNotNone(page.select_one("#s-development"))


if __name__ == "__main__":
    unittest.main()
