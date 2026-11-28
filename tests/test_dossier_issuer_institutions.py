"""
Source-less dossier issuer institutions (DECISION_LOG.md, 2026-11-14).

The owner approved registering 23 institutions as issuers of Living Dossier
external sources for two manuscripts, including attributed press under the new
`independent_media` type. These tests pin exactly what was approved: the ids,
their desks and types, and that none of them gains a source, so nothing is
collected for them and no public institution count (derived from sources)
moves.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import dossiers as d  # noqa: E402
from core.domain import INSTITUTION_TYPES  # noqa: E402
from core.manifests import load_all_desks  # noqa: E402

#: institution_id -> (desk_id, institution_type), as approved.
APPROVED = {
    "cn_ccg": ("china", "other"),
    "cn_mfa": ("china", "other"),
    "cn_embassy_ph": ("china", "other"),
    "jp_jica": ("japan", "other"),
    "jp_mhi": ("japan", "other"),
    "ph_dfa": ("philippines", "other"),
    "ph_dof": ("philippines", "other"),
    "ph_dotr": ("philippines", "other"),
    "ph_nmc": ("philippines", "other"),
    "ph_ntf_wps": ("philippines", "other"),
    "ph_pcg": ("philippines", "other"),
    "ph_pia": ("philippines", "state_news_agency"),
    "ph_ptv": ("philippines", "state_linked_media"),
    "press_abscbn": ("philippines", "independent_media"),
    "press_bombo": ("philippines", "independent_media"),
    "press_dzrh": ("philippines", "independent_media"),
    "press_gma": ("philippines", "independent_media"),
    "press_inquirer": ("philippines", "independent_media"),
    "press_philstar": ("philippines", "independent_media"),
    "press_tribune": ("philippines", "independent_media"),
    "press_usni": ("us-indopacific", "independent_media"),
    "press_navalnews": ("us-indopacific", "independent_media"),
    "press_portnews": ("us-indopacific", "independent_media"),
}


class TestDossierIssuerInstitutions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.desks = load_all_desks()
        cls.institutions = {i.institution_id: i for cfg in cls.desks.values()
                            for i in cfg.institutions}

    def test_the_new_type_is_declared(self):
        self.assertIn("independent_media", INSTITUTION_TYPES)

    def test_every_approved_institution_is_registered_as_approved(self):
        self.assertEqual(len(APPROVED), 23)
        for iid, (desk, kind) in APPROVED.items():
            with self.subTest(institution=iid):
                inst = self.institutions[iid]
                self.assertEqual((inst.desk_id, inst.institution_type), (desk, kind))

    def test_only_the_approved_outlets_are_independent_media(self):
        independent = {iid for iid, inst in self.institutions.items()
                       if inst.institution_type == "independent_media"}
        self.assertEqual(independent, {iid for iid in APPROVED if iid.startswith("press_")})

    def test_no_approved_institution_has_a_source(self):
        used = {s.institution_id for cfg in self.desks.values() for s in cfg.sources}
        self.assertEqual(used & set(APPROVED), set())

    def test_reconcile_accepts_a_registered_press_issuer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "registry.db"
            con = sqlite3.connect(str(db))
            con.execute("CREATE TABLE institutions (institution_id TEXT PRIMARY KEY, display_name TEXT)")
            con.executemany("INSERT INTO institutions VALUES (?, ?)",
                            [(i, inst.display_name) for i, inst in self.institutions.items()])
            con.commit()
            con.close()
            ext = dict(id="x1", url="https://www.gmanetwork.com/news/", published_on="2024-09-15",
                       publisher="GMA News", institution_id="press_gma", language="en",
                       retrieved_on="2026-11-14")
            out = d.reconcile_external_sources({"external_sources": [ext]}, db)
            self.assertEqual(out["x1"]["institution_name"], "GMA News")
            ext["institution_id"] = "press_unregistered"
            with self.assertRaisesRegex(ValueError, "unknown_external_institution"):
                d.reconcile_external_sources({"external_sources": [ext], "sections": []}, db)


if __name__ == "__main__":
    unittest.main()
