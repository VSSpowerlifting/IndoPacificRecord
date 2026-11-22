"""Phase 4A, as rebuilt (2026-11-16): the public Desks page is a directory.

The geographic map, its script and its geometry are retired. These cheap
source contracts keep what the map's contract protected that still applies:
the registry, never geography, decides every state and count; a reader
without JavaScript reaches every desk; and the page carries no map.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "site/preview/templates/desks.html"
STYLE = ROOT / "site/preview/desk-map.css"


class DesksDirectoryContract(unittest.TestCase):
    def setUp(self):
        self.html = TEMPLATE.read_text(encoding="utf-8")
        self.css = STYLE.read_text(encoding="utf-8")

    def test_template_compiles_as_jinja(self):
        from jinja2 import Environment
        Environment().parse(self.html)

    def test_registry_drives_state_and_counts(self):
        self.assertIn("d.status_label", self.html)
        self.assertIn("d.record_count", self.html)
        self.assertIn("d.last_successful_run", self.html)
        self.assertIn("desks.declared_count", self.html)
        self.assertIn("desks.collecting_count", self.html)
        self.assertIn("desks.not_collecting_count", self.html)
        self.assertNotIn("private_originals", self.html)
        # The state is the registry's label verbatim, never a rewrite of it.
        self.assertNotIn("replace('Live", self.html)
        # Operating notes live on each desk page, not in the directory.
        self.assertNotIn("d.status_explanation", self.html)

    def test_every_desk_is_a_plain_linked_row_before_the_scopes(self):
        self.assertEqual(self.html.count('<div class="deskmap-register" id="desks-list">'), 1)
        self.assertLess(self.html.index('class="deskmap-register"'),
                        self.html.index('id="desk-scopes"'))
        self.assertIn('id="desk-{{ d.slug }}"', self.html)
        self.assertIn('<a href="{{ d.route }}">{{ d.name }}</a>', self.html)

    def test_on_page_contents_point_at_real_sections(self):
        nav = self.html[self.html.index('<nav class="reader-contents"'):]
        nav = nav[:nav.index("</nav>")]
        for target in ("desks-list", "desk-scopes", "desk-comparison", "desk-statuses"):
            with self.subTest(target=target):
                self.assertIn('href="#%s"' % target, nav)
                self.assertIn('id="%s"' % target, self.html)

    def test_the_map_is_retired(self):
        for retired in ("desk-map.js", "_relief.html", "_desk_map_geo", "dm-anchor",
                        "deskmap-chart", "desk_map"):
            self.assertNotIn(retired, self.html)
        self.assertFalse((ROOT / "site/preview/desk-map.js").exists())

    def test_stylesheet_has_no_map(self):
        for retired in ("--dm-sea", ".dm-", "deskmap-chart"):
            self.assertNotIn(retired, self.css)


if __name__ == "__main__":
    unittest.main()
