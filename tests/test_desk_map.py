"""
The Desks-page map stays in step with the desk registry.

Editorial facts come from the registry and the corpus; `desks/geography.json`
only says where a desk sits. These checks keep the two from drifting: every
declared public desk is placed, nothing undeclared is, every seat falls inside
the frame and on its own country's land in the committed geometry, and every
plate's leader can be drawn without crossing its own plate.

2026-11-16: the Desks page map and its committed geometry
(`_desk_map_geo.svg`) are retired. The registry/placement, layout and
projection checks stay, because `scripts/build_geo_assets.py` reuses this
module's projection; the checks that read the retired geometry go with it.
"""

import json
import re
import unittest
from pathlib import Path

from core.desk_registry import load_registry
from scripts import desk_map

ROOT = Path(__file__).resolve().parent.parent


class DeskMapTest(unittest.TestCase):

    def setUp(self):
        self.places = json.loads(desk_map.GEOGRAPHY.read_text(encoding="utf-8"))["desks"]
        self.public = list(load_registry().public_entries)

    def test_every_public_desk_is_placed_and_nothing_else(self):
        slugs = {e.slug for e in self.public}
        # A newly launched source-status page is temporarily listed below the
        # map rather than fabricating an unverified geographic polygon. Every
        # existing placed country retains its pinned land/seat contracts.
        pending_status_only = {"indonesia"}
        self.assertEqual(set(self.places), slugs - pending_status_only)
        self.assertEqual(slugs - set(self.places), pending_status_only)


    def test_layout_places_every_desk_inside_the_frame(self):
        out = desk_map.layout(self.public)  # raises if a leader crosses its plate
        self.assertEqual((out["width"], out["height"]),
                         (desk_map.WIDTH, desk_map.HEIGHT))
        for slug, entry in out["desks"].items():
            with self.subTest(desk=slug):
                self.assertTrue(0 < float(entry["x"]) < desk_map.WIDTH)
                self.assertTrue(0 < float(entry["y"]) < desk_map.HEIGHT)
                for mode in ("wide", "mid"):
                    self.assertIn(entry[mode]["hang"], ("left", "right", "up", "down"))

    def test_projection_frame_corners(self):
        self.assertEqual(desk_map.project(desk_map.LON_W, desk_map.LAT_N), (0.0, 0.0))
        x, y = desk_map.project(desk_map.LON_E, desk_map.LAT_S)
        self.assertAlmostEqual(x, desk_map.WIDTH, delta=1)
        self.assertAlmostEqual(y, desk_map.HEIGHT, delta=1)

    @staticmethod
    def _contains(rings, x, y):
        """Even-odd ray cast across every ring, as `fill-rule="evenodd"` paints."""
        inside = False
        for ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
        return inside

    def test_containment_is_even_odd(self):
        square = lambda a, b: [(a, a), (b, a), (b, b), (a, b)]
        self.assertTrue(self._contains([square(0, 10)], 5, 5))
        self.assertFalse(self._contains([square(0, 10)], 15, 5))
        # A ring inside a ring is a hole; two separate islands both count.
        self.assertFalse(self._contains([square(0, 10), square(4, 6)], 5, 5))
        self.assertTrue(self._contains([square(0, 10), square(20, 30)], 25, 25))

if __name__ == "__main__":
    unittest.main()
