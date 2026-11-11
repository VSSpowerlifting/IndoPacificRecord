"""Tests for the image-free, rights-neutral Brief link-card generator."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.brief_social_card import (
    CARD_SIZE, MAX_BYTES, render_brief_social_card,
)


class BriefSocialCardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.out = Path(self.folder.name) / "assets" / "social" / "brief.png"

    def render(self, **replacements):
        values = dict(
            title="Taiwan Reports More Than 100 Chinese Vessels Across the Western Pacific",
            issue=23, week_ending="2026-11-07",
        )
        values.update(replacements)
        return render_brief_social_card(self.out, **values)

    def test_published_long_title_is_legible_size_and_within_budget(self):
        alt = self.render()
        self.assertIn("No. 23", alt)
        self.assertIn("Taiwan Reports", alt)
        with Image.open(self.out) as im:
            self.assertEqual(im.size, CARD_SIZE)
            self.assertEqual(im.format, "PNG")
        self.assertLess(self.out.stat().st_size, MAX_BYTES)

    def test_card_changes_with_edition_identity(self):
        self.render()
        first = hashlib.sha256(self.out.read_bytes()).hexdigest()
        self.render(issue=24, title="Singapore and Indonesia Fly Their First Joint Fighter Patrol")
        self.assertNotEqual(first, hashlib.sha256(self.out.read_bytes()).hexdigest())

    def test_missing_or_invalid_canonical_identity_is_rejected(self):
        for values in ({"issue": None}, {"issue": 0}, {"issue": True},
                       {"title": ""}, {"week_ending": "last Saturday"}):
            with self.subTest(values=values):
                with self.assertRaises((ValueError, TypeError)):
                    self.render(**values)

    def test_a_longer_title_still_fits(self):
        alt = self.render(title=(
            "Japan and the United States Agree to Establish AMRAAM "
            "Final Assembly in Japan"))
        self.assertIn("AMRAAM", alt)
        self.assertLess(self.out.stat().st_size, MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
