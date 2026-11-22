"""The home opening's photograph is one stable, verified asset.

`home_hero()` opens the home page on the U.S. Navy photograph of the Ronald
Reagan Carrier Strike Group with Japan Maritime Self-Defense Force ships
(founder direction, 16 November), never on whichever Brief is newest. It holds
only while every link of the chain holds: the manifest entry exists and is
routed to the home page, the committed source matches the manifest's SHA-256,
and each served derivative matches the hash DELIVERY.json records for it.
Any failure means a plain navy opening.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))

import generate_preview as gp  # noqa: E402

EDITORIAL = Path("site/assets/editorial")
FRONTEND = Path("site/assets/frontend")


class HomeHeroGates(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="home-hero-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / EDITORIAL).mkdir(parents=True)
        (self.tmp / FRONTEND).mkdir(parents=True)
        shutil.copy(ROOT / EDITORIAL / "manifest.json", self.tmp / EDITORIAL)
        shutil.copy(ROOT / EDITORIAL / "reagan-jmsdf-2015.jpg", self.tmp / EDITORIAL)
        shutil.copy(ROOT / FRONTEND / "DELIVERY.json", self.tmp / FRONTEND)
        for name in ("pacific-fleet-800.webp", "pacific-fleet-1600.webp",
                     "pacific-fleet-2500.webp"):
            shutil.copy(ROOT / FRONTEND / name, self.tmp / FRONTEND)

    def edit_manifest(self, change):
        path = self.tmp / EDITORIAL / "manifest.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw if isinstance(raw, list) else (raw.get("assets") or raw.get("images"))
        entry = next(e for e in entries if e.get("id") == gp.HOME_PHOTO_ID)
        change(entries, entry)
        path.write_text(json.dumps(raw), encoding="utf-8")

    def test_the_repository_opens_on_the_reagan_jmsdf_photograph(self):
        hero = gp.home_hero(ROOT)
        self.assertIsNotNone(hero)
        self.assertEqual(hero["id"], "reagan-jmsdf-2015")
        self.assertEqual([v["width"] for v in hero["variants"]], [800, 1600, 2500])
        self.assertEqual(hero["src"]["route"], "assets/frontend/pacific-fleet-1600.webp")
        self.assertEqual(hero["license"], "Public domain")
        self.assertIn("Nathan Burke", hero["creator"])
        self.assertIn("commons.wikimedia.org", hero["source_page"])
        self.assertEqual(hero["dod_id"], "151123-N-OI810-363")
        for v in hero["variants"]:
            self.assertTrue((ROOT / "site" / v["route"]).is_file(), v["route"])

    def test_the_photograph_does_not_follow_the_latest_brief(self):
        # The function takes no collection: nothing about the Briefs can
        # change which photograph opens the page.
        self.assertEqual(gp.home_hero(self.tmp)["id"], gp.home_hero(ROOT)["id"])

    def test_a_missing_entry_means_plain_navy(self):
        self.edit_manifest(lambda entries, entry: entries.remove(entry))
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_an_entry_not_routed_to_the_home_page_means_plain_navy(self):
        self.edit_manifest(lambda entries, entry: entry["match"].update(routes=["article"]))
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_changed_source_means_plain_navy(self):
        with open(self.tmp / EDITORIAL / "reagan-jmsdf-2015.jpg", "ab") as handle:
            handle.write(b"\0")
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_changed_derivative_means_plain_navy(self):
        with open(self.tmp / FRONTEND / "pacific-fleet-1600.webp", "ab") as handle:
            handle.write(b"\0")
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_missing_derivative_means_plain_navy(self):
        (self.tmp / FRONTEND / "pacific-fleet-800.webp").unlink()
        self.assertIsNone(gp.home_hero(self.tmp))


    def test_a_missing_credit_field_means_plain_navy(self):
        for field in ("caption", "creator", "license", "license_url", "source_page"):
            with self.subTest(field=field):
                self.setUp()
                self.edit_manifest(lambda entries, entry, f=field: entry.update({f: ""}))
                self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_licence_other_than_public_domain_means_plain_navy(self):
        self.edit_manifest(lambda entries, entry: entry.update(license="CC BY-SA 2.0"))
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_source_page_off_commons_means_plain_navy(self):
        # The credit labels the link "Wikimedia Commons".
        self.edit_manifest(lambda entries, entry: entry.update(
            source_page="https://example.org/File:reagan.jpg"))
        self.assertIsNone(gp.home_hero(self.tmp))

    def test_a_missing_delivery_record_means_plain_navy(self):
        (self.tmp / FRONTEND / "DELIVERY.json").unlink()
        self.assertIsNone(gp.home_hero(self.tmp))

if __name__ == "__main__":
    unittest.main()
