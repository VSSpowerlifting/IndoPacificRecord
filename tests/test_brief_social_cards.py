"""Unit tests: only genuine checked cover bytes can enter social output.

The synthetic raster below is a TEST FIXTURE and never a publication image.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.brief_social_card import (
    CARD_SIZE, MAX_BYTES, render_brief_social_card, social_preview_granted,
)


class BriefSocialCardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.photo = root / "fixture.jpg"
        Image.new("RGB", (1498, 999), (64, 105, 125)).save(self.photo, "JPEG")
        self.out = root / "assets" / "social" / "brief.jpg"
        self.provenance = {
            "credit": "Fixture publisher · CC BY 4.0",
            "license": "CC BY 4.0",
            "source_page": "https://example.invalid/fixture",
            "depicts": "context",
            "date_note": "Archive from 2022, not the 2026 event.",
            "alt": "Test-only fixture showing solid color.",
        }

    def render(self, **replacements):
        values = dict(
            title="Taiwan Reports More Than 100 Chinese Vessels Across the Western Pacific",
            issue=23, week_ending="2026-11-07", photo_file=self.photo,
            photo=self.provenance, byline="Benjamin Yang",
        )
        values.update(replacements)
        return render_brief_social_card(self.out, **values)

    def approved_cover(self):
        photo = dict(self.provenance)
        photo["sha256"] = "a" * 64
        photo["social_preview_approval"] = {
            "approved_by": "Benjamin Yang",
            "approved_on": "2026-11-10",
            "scope": "brief-link-preview",
            "source_sha256": photo["sha256"],
            "reference": (
                "https://github.com/VSSpowerlifting/IndoPacificRecord/"
                "issues/123#issuecomment-999"
            ),
        }
        return photo

    def test_automatic_preview_begins_at_issue_25_only(self):
        approved = self.approved_cover()
        self.assertFalse(social_preview_granted(24, approved))
        self.assertFalse(social_preview_granted(23, approved))
        self.assertFalse(social_preview_granted(None, approved))
        self.assertTrue(social_preview_granted(25, approved))
        self.assertTrue(social_preview_granted(26, approved))

    def test_each_photo_requires_its_own_social_surface_grant(self):
        approved = self.approved_cover()
        self.assertFalse(social_preview_granted(25, self.provenance))
        for altered in (
            {"social_preview_approval": None},
            {"social_preview_approval": {"approved_by": "Benjamin Yang"}},
            {"social_preview_approval": {
                **approved["social_preview_approval"], "scope": "article"}},
            {"social_preview_approval": {
                **approved["social_preview_approval"], "source_sha256": "b" * 64}},
            {"social_preview_approval": {
                **approved["social_preview_approval"], "approved_by": "AI agent"}},
            {"social_preview_approval": {
                **approved["social_preview_approval"], "approved_on": "tomorrow"}},
            {"social_preview_approval": {
                **approved["social_preview_approval"], "reference": "https://example.com/ok"}},
            {"sha256": "not-a-hash"},
        ):
            with self.subTest(altered=altered):
                self.assertFalse(social_preview_granted(25, {**approved, **altered}))

    def test_photo_card_size_source_attribution_and_budget(self):
        alt = self.render()
        self.assertIn("No. 23", alt)
        self.assertIn("Fixture publisher", alt)
        with Image.open(self.out) as im:
            self.assertEqual(im.size, CARD_SIZE)
            self.assertEqual(im.format, "JPEG")
        self.assertLess(self.out.stat().st_size, MAX_BYTES)

    def test_card_changes_with_approved_publication_identity(self):
        self.render()
        first = hashlib.sha256(self.out.read_bytes()).hexdigest()
        self.render(issue=24, title="Singapore and Indonesia Fly Their First Joint Fighter Patrol")
        self.assertNotEqual(first, hashlib.sha256(self.out.read_bytes()).hexdigest())

    def test_invalid_publication_or_source_is_rejected(self):
        for values in ({"issue": None}, {"issue": 0}, {"issue": True},
                       {"title": ""}, {"week_ending": "last Saturday"},
                       {"photo": {**self.provenance, "credit": ""}},
                       {"photo": {**self.provenance, "license": "unknown"}},
                       {"photo": {**self.provenance, "depicts": "guess"}},
                       {"photo_file": self.out.parent / "not-found.jpg"}):
            with self.subTest(values=values):
                with self.assertRaises((ValueError, TypeError, OSError)):
                    self.render(**values)

    def test_source_required_notice_is_preserved_and_card_fits(self):
        source = {
            **self.provenance,
            "license": "Public domain",
            "notice": ("The appearance of U.S. Department of War (DoW) visual "
                       "information does not imply or constitute DoW endorsement."),
        }
        self.render(photo=source)
        self.assertLess(self.out.stat().st_size, MAX_BYTES)

    def test_long_approved_title_fits(self):
        alt = self.render(title=(
            "Japan and the United States Agree to Establish AMRAAM "
            "Final Assembly in Japan"))
        self.assertIn("AMRAAM", alt)


if __name__ == "__main__":
    unittest.main()
