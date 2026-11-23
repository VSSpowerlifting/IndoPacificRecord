"""
The regional atlas stays in step with the desk registry and the real coastline.

Editorial facts come from the registry and the corpus; `desks/geography.json`
only says where a desk's publishing institutions are based. These checks keep
the two from drifting: every declared public desk is placed (or explicitly
outside the frame), nothing undeclared is, every seat stands on land in the
committed Natural Earth geometry and inside the Desks view, and the drawing is
rebuilt byte for byte from its committed source.

History: the retired Desks map (2026-10-05 to 2026-11-16) drew plates and
leaders from this file; its layout checks went with it. 2026-11-17: the
atlas (`scripts/build_atlas.py`) places Indonesia at Jakarta and draws the
US Indo-Pacific Reference Desk as outside the frame, not as a Hawaii seat.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.desk_registry import load_registry
from scripts import build_atlas as atlas

ROOT = Path(__file__).resolve().parent.parent


def _contains(rings, x, y):
    """Even-odd ray cast across every ring, as `fill-rule="evenodd"` paints."""
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


class RegionalAtlasTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.places = json.loads(atlas.GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
        cls.public = list(load_registry().public_entries)
        cls.source = json.loads(atlas.SOURCE_JSON.read_text(encoding="utf-8"))

    def test_every_public_desk_is_placed_and_nothing_else(self):
        self.assertEqual(set(self.places), {e.slug for e in self.public})

    def test_each_entry_is_a_seat_or_explicitly_outside(self):
        for slug, p in self.places.items():
            with self.subTest(desk=slug):
                self.assertTrue(p.get("short"))
                if "outside" in p:
                    self.assertNotIn("anchor", p)
                    self.assertNotIn("seat", p)
                else:
                    self.assertTrue(p["seat"])
                    self.assertEqual(len(p["anchor"]), 2)
                    self.assertIn(p.get("label", "right"), ("left", "right", "below"))
                    self.assertIn(p.get("label_narrow", "right"), ("left", "right", "below"))

    def test_the_us_desk_is_never_drawn_as_a_hawaii_seat(self):
        us = self.places["us-indopacific"]
        self.assertEqual(us.get("outside"), "United States")
        self.assertNotIn("anchor", us)

    def test_every_seat_stands_on_land_in_the_committed_geometry(self):
        for slug, p in self.places.items():
            if "anchor" not in p:
                continue
            with self.subTest(desk=slug):
                self.assertTrue(_contains(self.source["land"], *atlas.project(*p["anchor"])))

    def test_the_view_places_every_seat_inside_it_and_points_off_for_the_rest(self):
        view = atlas.atlas_view(self.public)
        placed = {s["desk"].slug for s in view["seats"]}
        outside = {o["desk"].slug for o in view["outside"]}
        self.assertEqual(placed | outside, {e.slug for e in self.public})
        self.assertEqual(outside, {"us-indopacific"})
        for s in view["seats"]:
            for v in (s["x"], s["y"]):
                self.assertTrue(0 < float(v.rstrip("%")) < 100, (s["desk"].slug, v))
        # The edge pointer is not at the former Hawaii seat's latitude.
        self.assertNotAlmostEqual(atlas.OUTSIDE_EDGE_LAT, 21.4, delta=5)

    def test_the_edge_pointer_sits_in_open_sea_at_every_width(self):
        # Its mark stands at the view's east edge at OUTSIDE_EDGE_LAT; that
        # point (and a margin west of it) must be sea, never a stand-in seat
        # on someone's land. No stylesheet may move it off the built latitude.
        east = atlas.VIEW["lon"][1]
        for lon in (east, east - 1.5, east - 3.0):
            self.assertFalse(_contains(self.source["land"],
                                       *atlas.project(lon, atlas.OUTSIDE_EDGE_LAT)), lon)
        css = (ROOT / "site" / "preview" / "desk-map.css").read_text(encoding="utf-8")
        import re
        for rule in re.findall(r"\.seat--edge\{([^}]*)\}", css):
            tops = re.findall(r"(?:^|;)\s*top\s*:\s*([^;]+)", rule)
            self.assertTrue(all(t.strip() == "var(--y)" for t in tops), rule)

    def test_every_seated_desk_has_a_locator_and_the_outside_desk_has_none(self):
        for slug, p in self.places.items():
            loc = atlas.locator_view(slug)
            with self.subTest(desk=slug):
                if "outside" in p:
                    self.assertIsNone(loc)
                else:
                    self.assertEqual(loc["seat"], p["seat"])
                    for v in (loc["x"], loc["y"]):
                        self.assertTrue(0 < float(v.rstrip("%")) < 100)

    def test_a_locator_window_stays_on_the_drawing_and_honours_its_placement(self):
        for slug, p in self.places.items():
            loc = atlas.locator_view(slug)
            if loc is None:
                continue
            with self.subTest(desk=slug):
                for v in loc["window"]["position"].split():
                    self.assertTrue(0 <= float(v.rstrip("%")) <= 100, loc["window"])
                if "locator_at" in p:
                    fx, fy = p["locator_at"]
                    self.assertTrue(0 < fx < 1 and 0 < fy < 1, p["locator_at"])
                    # Unclamped, the seat sits exactly where the entry puts it.
                    self.assertEqual(float(loc["x"].rstrip("%")), round(fx * 100, 2))
                    self.assertEqual(float(loc["y"].rstrip("%")), round(fy * 100, 2))

    def test_atlas_links_follow_registry_order_with_the_outside_desk_last(self):
        view = atlas.atlas_view(self.public)
        for key in ("seats", "outside"):
            with self.subTest(placement=key):
                self.assertEqual([s["desk"].slug for s in view[key]],
                                 [d.slug for d in self.public
                                  if ("outside" in self.places[d.slug]) == (key == "outside")])

    def test_a_seat_outside_the_view_is_refused(self):
        stray = SimpleNamespace(slug="china")
        moved = {"china": {"seat": "Nowhere", "anchor": [60.0, 0.0], "short": "X"}}
        with mock.patch.object(atlas, "_places", return_value=moved):
            with self.assertRaises(ValueError):
                atlas.atlas_view([stray])

    def test_the_drawing_is_rebuilt_byte_for_byte(self):
        receipt = json.loads(atlas.RECEIPT.read_text(encoding="utf-8"))
        # Two inkings of the one drawing: the day chart and the night chart.
        for ink, path in ((atlas.DAY, atlas.ATLAS_SVG), (atlas.NIGHT, atlas.ATLAS_NIGHT_SVG)):
            svg = atlas.draw(self.source, ink).encode("utf-8")
            self.assertEqual(svg, path.read_bytes(), path.name)
            self.assertEqual(receipt["outputs"][path.name]["sha256"],
                             hashlib.sha256(svg).hexdigest(), path.name)
        self.assertEqual(sorted(receipt["outputs"]), ["atlas-night.svg", "atlas.svg"])
        self.assertEqual(receipt["source"]["sha256"],
                         hashlib.sha256(atlas.SOURCE_JSON.read_bytes()).hexdigest())
        self.assertNotIn("time", json.dumps(receipt).lower().replace("timeline", ""))

    def test_the_source_names_natural_earth_and_its_cut(self):
        src = self.source["source"]
        self.assertEqual(src["sha256"], atlas.RETIRED_SHA256)
        self.assertIn("countries-50m.json", src["natural_earth_inputs"])
        self.assertIn("Natural Earth", " ".join(self.source["_comment"]))
        svg = atlas.ATLAS_SVG.read_text(encoding="utf-8")
        self.assertIn("Natural Earth 1:50m (public domain", svg)
        self.assertIn("not depth", svg)

    def test_the_frame_holds_its_projection(self):
        self.assertEqual(atlas.project(atlas.LON_W, atlas.LAT_N), (0.0, 0.0))
        x, y = atlas.project(atlas.LON_E, atlas.LAT_S)
        self.assertAlmostEqual(x, atlas.WIDTH, delta=1)
        self.assertAlmostEqual(y, atlas.HEIGHT, delta=1)

    def test_containment_is_even_odd(self):
        square = lambda a, b: [(a, a), (b, a), (b, b), (a, b)]
        self.assertTrue(_contains([square(0, 10)], 5, 5))
        self.assertFalse(_contains([square(0, 10)], 15, 5))
        self.assertFalse(_contains([square(0, 10), square(4, 6)], 5, 5))
        self.assertTrue(_contains([square(0, 10), square(20, 30)], 25, 25))


class AtlasOnThePages(unittest.TestCase):
    """The committed output carries the atlas as rendered."""

    def test_desks_page_opens_on_the_atlas_with_a_link_per_desk(self):
        html = (ROOT / "output" / "desks.html").read_text(encoding="utf-8")
        start = html.index('<header class="page-head desks-head">')
        head = html[start:html.index("</header>", start)]
        self.assertIn('<figure class="atlas" id="atlas"', head)
        public = list(load_registry().public_entries)
        for d in public:
            self.assertIn('href="#desk-%s"' % d.slug, head)
            self.assertIn("%s. %s" % (d.name, d.status_label), head)
        self.assertIn("They show no coverage area", head)
        self.assertIn("IPR makes no boundary claim", head)
        self.assertIn("United States, </span>outside this map", head)
        self.assertNotIn("Hawaii", head)
        self.assertTrue((ROOT / "output" / "assets" / "geo" / "atlas.svg").is_file())

    def test_desk_pages_carry_a_locator_except_the_outside_desk(self):
        places = json.loads(atlas.GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
        for d in load_registry().public_entries:
            html = (ROOT / "output" / d.route).read_text(encoding="utf-8")
            with self.subTest(desk=d.slug):
                if "outside" in places[d.slug]:
                    self.assertNotIn('class="locator"', html)
                else:
                    self.assertIn('<figure class="locator">', html)
                    self.assertIn("Seat: %s" % places[d.slug]["seat"], html)

    def test_a_desk_with_no_seat_in_the_frame_is_never_set_on_a_chart(self):
        """The atlas uses the supported institutional location, with no fallback seat."""
        places = json.loads(atlas.GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
        for d in load_registry().public_entries:
            html = (ROOT / "output" / d.route).read_text(encoding="utf-8")
            with self.subTest(desk=d.slug):
                self.assertIn('data-surface="desk"', html)
                if "outside" in places[d.slug]:
                    self.assertNotIn("page-head--located", html)
                    self.assertNotIn("locator-map", html)


if __name__ == "__main__":
    unittest.main()
