"""The home opening's photograph is granted, never assumed.

`home_hero()` opens the home page on the latest Brief's admitted photograph
only when every gate holds: a published (non-fixture) Brief leads, its
catalogue admission is a photograph, its recorded treatment is the gradient
the opening draws (so the credit discloses that change), and its cover pairs
with the admission. Any failure means a plain navy opening.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))

import generate_preview as gp  # noqa: E402


class Media(SimpleNamespace):
    @property
    def is_photograph(self):
        return self.kind == "photograph"


def collection(entry, kind="brief"):
    return SimpleNamespace(lead_row={"kind": kind, "entry": entry})


class HomeHeroGates(unittest.TestCase):
    ENTRY = {"slug": "x-brief", "issue": 9, "url": "briefs/x-brief.html"}

    def media(self, treatment="gradient", kind="photograph"):
        return {"x-brief": Media(kind=kind, photo={"cover_treatment": treatment})}

    def test_no_collection_or_no_lead(self):
        self.assertIsNone(gp.home_hero(None, {}, {}))
        self.assertIsNone(gp.home_hero(SimpleNamespace(lead_row=None), {}, {}))

    def test_an_earlier_issue_never_opens_the_page(self):
        self.assertIsNone(gp.home_hero(collection(self.ENTRY, kind="issue"),
                                       self.media(), {}))

    def test_a_fixture_brief_never_opens_the_page(self):
        entry = dict(self.ENTRY, synthetic=True)
        self.assertIsNone(gp.home_hero(collection(entry), self.media(), {}))

    def test_no_admitted_photograph_means_plain_navy(self):
        self.assertIsNone(gp.home_hero(collection(self.ENTRY), {}, {}))
        self.assertIsNone(gp.home_hero(collection(self.ENTRY),
                                       self.media(kind="plate"), {}))

    def test_a_treatment_other_than_the_gradient_means_plain_navy(self):
        # The opening always draws the gradient; a credit that does not name
        # it would misstate the change, so such a photograph cannot open it.
        for treatment in (None, "", "none", "duotone"):
            with self.subTest(treatment=treatment):
                self.assertIsNone(gp.home_hero(collection(self.ENTRY),
                                               self.media(treatment), {}))

    def test_the_current_latest_brief_opens_the_page_with_its_cover(self):
        editions = gp.load_editions(ROOT)
        col = gp.load_collection(editions, gp.load_registry(),
                                 briefs_dir=ROOT / "briefs")
        from core.catalogue_media import load_admissions, resolve_catalogue_media
        admissions = load_admissions(repo_root=ROOT)
        media = {row["entry"]["slug"]: resolve_catalogue_media(row, admissions, repo_root=ROOT)
                 for row in col.rows}
        hero = gp.home_hero(col, media, admissions)
        lead = col.lead_row
        if lead["kind"] != "brief" or not media[lead["entry"]["slug"]].is_photograph:
            self.skipTest("the latest item has no admitted photograph")
        self.assertIsNotNone(hero)
        self.assertEqual(hero["brief"]["slug"], lead["entry"]["slug"])
        self.assertEqual(hero["photo"]["cover_treatment"], "gradient")
        self.assertIn("gradient", hero["photo"]["change_note"].lower())
        self.assertTrue((ROOT / "site" / hero["src"]["route"]).is_file())
        self.assertTrue(all((ROOT / "site" / v["route"]).is_file() for v in hero["webp"]))


if __name__ == "__main__":
    unittest.main()
