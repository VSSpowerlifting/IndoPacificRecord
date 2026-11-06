"""Philippines Desk: the page, overview and automation say what is true.

The desk publishes verified neutral AFP/NSC link metadata and released machine
explanations. It holds no original-document corpus records. These tests pin
that distinction against the tracked production database, so obsolete
shadow-stage wording, zero-source messaging and inflated or leaked content fail
loudly. Nothing here collects, calls a model or writes to the tracked database.
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.daily_machine_records import load as load_machine_records
from core.desk_registry import RegistryError, load_registry
from core.regional_official_link_render import load_admitted_links
from scripts.verify_regional_source_index_readback import validate_page
from tests.test_desk_rollout_contract import REPO_ROOT, TRACKED_DB, DeskCase

OBSOLETE_PAGE_PHRASES = (
    "No individual source references have completed",
    "Shadow collection only",
    "NSC publication needs its own owner decision",
    "does not inherit AFP",
    "being retired; collection continues in private custody once the owner activates it",
    "Sources enabled in production",
    "Sources configured in production",
    "This desk has no admitted records in the public IPR corpus",
    "machine screening is never published as analysis",
    "translations and automatic analysis are excluded",
    "Shadow evaluation",
)


def scratch_copy(tmp):
    """A throwaway copy; the tracked WAL database is never opened in place."""
    target = Path(tmp) / "pla_watch.db"
    shutil.copyfile(TRACKED_DB, target)
    return target


class PhilippinesRegistry(unittest.TestCase):
    def test_label_is_reader_wording_not_a_status_promotion(self):
        desk = load_registry().get("philippines")
        self.assertEqual(desk.status, "shadow")
        self.assertFalse(desk.is_collecting)
        self.assertFalse(desk.has_production_records)
        self.assertIn("machine explanations", desk.status_label)
        self.assertIn("not in corpus", desk.status_label)
        self.assertNotIn("Shadow evaluation", desk.status_label)
        self.assertNotIn("Live", desk.status_label)

    def test_other_desks_keep_their_standard_labels(self):
        japan = load_registry().get("japan")
        self.assertEqual(japan.status_label, "Shadow evaluation — not in corpus")
        self.assertIsNone(japan.public_status_label)

    def test_custom_label_is_refused_on_a_collecting_desk(self):
        raw = json.loads((REPO_ROOT / "desks" / "registry.json").read_text("utf-8"))
        desk = next(d for d in raw["desks"] if d["slug"] == "china")
        self.assertEqual(desk["status"], "live")
        desk["public_status_label"] = "Quietly improved"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(RegistryError):
                load_registry(path)

    def test_registry_prose_has_no_obsolete_shadow_stage_claims(self):
        desk = load_registry().get("philippines")
        text = json.dumps([desk.status_explanation, desk.research, desk.limits])
        for phrase in ("requires its own owner decision", "being retired",
                       "No Philippine source is enabled", "NSC must qualify separately",
                       "link publication requires its own owner decision"):
            self.assertNotIn(phrase, text)
        self.assertTrue(desk.research["resolved"])


class PhilippinesPublicPages(DeskCase):
    def admitted(self):
        return load_admitted_links(TRACKED_DB, "philippines")

    def machine(self):
        return [r for r in load_machine_records(TRACKED_DB)
                if r["desk_id"] == "philippines"]

    def test_page_lists_exactly_the_admitted_links_grouped_by_publisher(self):
        page = self.page("philippines.html")
        links = self.admitted()
        afp = [r for r in links if r["publisher_label"] == "Armed Forces of the Philippines"]
        nsc = [r for r in links if r["publisher_label"] == "National Security Council"]
        self.assertTrue(afp and nsc)
        self.assertEqual(len(links), len(afp) + len(nsc))
        self.assertEqual(set(re.findall(r'data-regional-official-source-id="([^"]+)"', page)),
                         {r["source_identity"] for r in links})
        self.assertEqual(page.count("data-regional-official-source-id="), len(links))
        self.assertIn('id="ph-afp-links">Armed Forces of the Philippines · %d links' % len(afp), page)
        self.assertIn('id="ph-nsc-links">National Security Council · %d link<' % len(nsc), page)
        self.assertEqual(validate_page(page, links), len(links))

    def test_summary_counts_come_from_their_own_tables_and_never_enter_corpus(self):
        page = self.page("philippines.html")
        links = self.admitted()
        machine = self.machine()
        self.assertIn("<dt>Verified official links</dt><dd>%d " % len(links), page)
        self.assertIn("<dt>Machine explanations</dt><dd>%d " % len(machine), page)
        self.assertIn("<dt>Original documents in the IPR corpus</dt><dd>None ", page)
        self.assertNotIn('href="archive.html?desk=philippines"', page)

    def test_every_released_machine_explanation_is_listed_with_its_labels(self):
        page = self.page("philippines.html")
        machine = self.machine()
        self.assertTrue(machine)
        for rec in machine:
            with self.subTest(record=rec["source_identity"]):
                self.assertIn('data-machine-explanation-id="%s"' % rec["source_identity"], page)
                self.assertIn(rec["summary"], page)
                self.assertIn('href="%s"' % rec["record_path"], page)
                self.assertIn("Machine explanation", page)
        self.assertIn("not human-reviewed", page)
        self.assertEqual(page.count("data-machine-explanation-id="), len(machine))
        # A link whose machine explanation exists says so; the row keeps exactly
        # one outbound anchor so the readback gate still parses it.
        self.assertEqual(page.count("Machine explanation published above"), len(machine))

    def test_other_desks_machine_explanations_are_not_listed(self):
        page = self.page("philippines.html")
        for rec in load_machine_records(TRACKED_DB):
            if rec["desk_id"] != "philippines":
                with self.subTest(record=rec["source_identity"]):
                    self.assertNotIn('data-machine-explanation-id="%s"' %
                                     rec["source_identity"], page)
                    self.assertNotIn('href="%s"' % rec["record_path"], page)

    def test_no_obsolete_or_contradictory_language(self):
        page = self.page("philippines.html")
        for phrase in OBSOLETE_PAGE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, page)
        self.assertIn("Official links and machine explanations, published automatically", page)
        self.assertIn("The NSC site hosts statements from several offices", page)

    def test_page_never_reproduces_withheld_originals(self):
        page = self.page("philippines.html")
        for forbidden in ("body_original", "text_original", "title_original",
                          "api.afp.mil.ph/articles/", "download.do?fileId="):
            self.assertNotIn(forbidden, page)
        self.assertIsNone(re.search(r"<img[^>]+(afp\.mil\.ph|nsc\.gov\.ph)", page))

    def test_desks_overview_reflects_lanes_without_inflating_corpus(self):
        desks = self.page("desks.html")
        links = self.admitted()
        machine = self.machine()
        plate = re.search(r'<section class="desk[^"]*" id="desk-philippines".*?</section>',
                          desks, re.S).group(0)
        self.assertIn("Official links and machine explanations — not in corpus", plate)
        self.assertNotIn("Shadow evaluation", plate)
        self.assertIn("<dt>Verified official links</dt><dd>%d</dd>" % len(links), plate)
        self.assertIn("<dt>Machine explanations</dt><dd>%d</dd>" % len(machine), plate)
        self.assertIn("<dt>Corpus records</dt><dd>Not admitted</dd>", plate)
        scope = desks.split('id="desk-scopes"', 1)[1]
        self.assertIn('data-philippines-directory-scope-count="%d"' % len(links), scope)
        for other in ("china", "singapore", "japan", "korea", "vietnam", "us-indopacific"):
            other_plate = re.search(r'<section class="desk[^"]*" (?:id="desk-%s"|data-desk="%s")' % (other, other), desks)
            if other_plate:
                tail = desks[other_plate.start():].split("</section>", 1)[0]
                self.assertNotIn("data-philippines-directory", tail)


class MachineExplanationEligibility(unittest.TestCase):
    """Only released, version-matched, non-excluded records may publish."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ph-eligibility-")
        self.db = scratch_copy(self.tmp)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def mutate(self, sql, *args):
        con = sqlite3.connect(str(self.db))
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()

    def identities(self):
        return {r["source_identity"] for r in load_machine_records(self.db)}

    def test_baseline_includes_the_three_released_fixture_records(self):
        # Daily may legitimately add eligible records to the tracked corpus.
        self.assertTrue({"afp:1409", "afp:1410", "nsc:3108"} <= self.identities())

    def test_held_record_never_publishes(self):
        before = self.identities()
        self.assertIn("afp:1409", before)
        self.mutate("UPDATE daily_machine_records SET publication_state='held' "
                    "WHERE source_identity='afp:1409'")
        self.assertEqual(self.identities(), before - {"afp:1409"})

    def test_record_without_matching_link_version_never_publishes(self):
        before = self.identities()
        self.assertIn("nsc:3108", before)
        self.mutate("UPDATE daily_machine_records SET metadata_version_sha256=? "
                    "WHERE source_identity='nsc:3108'", "0" * 64)
        self.assertEqual(self.identities(), before - {"nsc:3108"})

    def test_owner_excluded_identity_never_publishes(self):
        self.mutate("UPDATE daily_machine_records SET source_identity='afp:1418' "
                    "WHERE source_identity='afp:1409'")
        self.assertNotIn("afp:1418", self.identities())


class PhilippinesWorkflowRunners(unittest.TestCase):
    """Philippines jobs stay on the pinned ubuntu-24.04 runner image."""

    WORKFLOWS = (
        "ph_afp_verified_official_link_production.yml",
        "ph_nsc_verified_official_link_production.yml",
        "ph_afp_shadow.yml",
        "ph_nsc_shadow.yml",
    )

    def test_philippines_jobs_use_pinned_ubuntu_2404(self):
        for name in self.WORKFLOWS:
            with self.subTest(workflow=name):
                text = (REPO_ROOT / ".github" / "workflows" / name).read_text("utf-8")
                self.assertIn("python-version: '3.13'", text)
                runners = re.findall(r"^\s*runs-on:\s*(\S+)", text, re.M)
                self.assertTrue(runners)
                self.assertEqual(set(runners), {"ubuntu-24.04"})


if __name__ == "__main__":
    unittest.main()
