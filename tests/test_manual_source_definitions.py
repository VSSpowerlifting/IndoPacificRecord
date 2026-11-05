"""Manual production sources share one registry, one dispatch and one row.

docs/desks/MIGRATION.md runtime migration 3: the Philippines, Indonesia and
Japan source families that were previously admitted beside the pipeline (a
Stage 14 intake call and a separate workflow step) are registered as manual
production sources and dispatched through `pipeline.run_governed_manual_sources`
like the Korean MND bridge. These tests pin what that registration may and may
not do:

  * every family is a manual, adapter-less, contract-validated source on a
    non-collecting desk — nothing fetches it;
  * `sync_desk_config` writes its desk, institution and source rows on an
    isolated database, so the one Daily migration step covers it;
  * every status the shared dispatch can report for the Daily and Japan paths,
    with fixed-code error details and no source text;
  * the liveness gate treats a manual source with nothing admitted as INERT.

Runtime migration 4 adds the two U.S. reference families (USCC and Treasury
official press-release listing metadata, `desks/us-indopacific/manifest.json`)
to the same table: standing owner approval, no activation variable, and the
preserved history handed to the run by the Daily workflow's clone step.

Everything runs on scratch databases or mocks; nothing touches pla_watch.db,
reaches a network, or runs a model.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pipeline                                                  # noqa: E402
from core import japan_mod_official_links as jp                  # noqa: E402
from core.collection import status as st                         # noqa: E402
from core.daily_sources import SOURCES                           # noqa: E402
from core.desk_registry import load_registry                     # noqa: E402
from core.manifests import load_all_desks                        # noqa: E402
from core.regional_official_link_release import RegionalLinkHold  # noqa: E402
from core.registry import sync_desk_config                       # noqa: E402
from migrations.runner import apply_all, connect                 # noqa: E402
from processing.daily_intake import IntakeHold                   # noqa: E402
from tests.test_migrations import build_legacy_db                # noqa: E402

MANUAL_FAMILIES = {
    "ph_afp_articles": "philippines",
    "ph_nsc_official_statements": "philippines",
    "id_kemhan_news": "indonesia",
    "jp_mod_news_ja": "japan",
    "uscc_press_official_metadata": "us-indopacific",
    "us_treasury_press_official_metadata": "us-indopacific",
}
#: The U.S. reference desk keeps its `access_blocked` registry status (PACOM
#: is still refused at the edge); every other manual registration is `shadow`.
MANUAL_DESK_STATUS = {"us-indopacific": "access_blocked"}


class FakeRegistry:
    def __init__(self, desk):
        self.desk = desk

    def get_source(self, slug):
        return SimpleNamespace(desk_id=self.desk, access_method="manual")

    def get_adapter(self, slug):
        raise AssertionError("adapter built for a manual source")


class TestRegistration(unittest.TestCase):

    def test_every_governed_family_is_a_manual_production_source(self):
        self.assertEqual(set(SOURCES) | {jp.FAMILY} | set(pipeline._US_METADATA_FAMILIES),
                         set(MANUAL_FAMILIES))
        registry = load_registry()
        for slug, desk in MANUAL_FAMILIES.items():
            with self.subTest(source=slug):
                entry = registry.get(desk)
                src = {s.slug: s for s in entry.sources}[slug]
                self.assertEqual(src.access_method, "manual")
                self.assertTrue(src.enabled)
                self.assertTrue(src.contract_validated)
                self.assertEqual(src.authority_tier, "A")
                self.assertEqual(entry.status, MANUAL_DESK_STATUS.get(desk, "shadow"))
                self.assertFalse(entry.is_collecting)
                self.assertFalse(entry.has_production_records)
                self.assertFalse(entry.may_show_record_count)

    def test_manual_manifests_declare_no_adapter_and_no_active_desk(self):
        desks = load_all_desks()
        for desk in ("philippines", "indonesia", "japan", "us-indopacific"):
            with self.subTest(desk=desk):
                cfg = desks[desk]
                self.assertEqual(cfg.desk.public_status, "shadow")
                self.assertFalse(cfg.desk.active)
                self.assertTrue(cfg.sources)
                for src in cfg.sources:
                    self.assertEqual(src.access_method, "manual")
                    self.assertIsNone(src.adapter)
                    self.assertEqual(src.originality, "original")

    def test_daily_source_metadata_matches_the_manifest(self):
        desks = load_all_desks()
        for family, source in SOURCES.items():
            with self.subTest(family=family):
                cfg = desks[source.desk_id]
                src = {s.slug: s for s in cfg.sources}[family]
                self.assertEqual(src.language_tag, source.language)
                institution = {i.institution_id: i for i in cfg.institutions}[src.institution_id]
                self.assertIn(source.publisher, (institution.display_name,
                                                 institution.name_original))

    def test_the_shadow_japan_manifest_is_still_the_shadow_runner_input(self):
        self.assertTrue((REPO_ROOT / "shadow" / "jp_mod" / "manifest.json").is_file())

    def test_every_governed_admission_has_a_registered_source(self):
        """A dispatch entry for a slug no manifest declares could never run,
        because the pipeline only dispatches slugs the registry calls manual."""
        registered = {s.slug for e in load_registry() for s in e.sources
                      if s.access_method == "manual"}
        self.assertLessEqual(set(pipeline._governed_admissions()), registered)
        self.assertLessEqual(set(MANUAL_FAMILIES), set(pipeline._governed_admissions()))

    def test_sync_desk_config_registers_the_manual_sources_on_a_scratch_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "scratch.db"
            build_legacy_db(db)
            conn = connect(db)
            apply_all(conn)
            conn.close()
            conn = sqlite3.connect(str(db))
            desks = {r[0] for r in conn.execute("SELECT desk_id FROM desks")}
            rows = {r[0]: r[1:] for r in conn.execute(
                "SELECT slug, desk_id, access_method, enabled, is_active FROM sources")}
            institutions = {r[0] for r in conn.execute(
                "SELECT institution_id FROM institutions")}
            conn.close()
        self.assertLessEqual({"philippines", "indonesia", "japan", "us-indopacific"}, desks)
        self.assertLessEqual({"ph_afp", "ph_nsc", "id_kemhan", "jp_mod",
                              "us_uscc", "us_treasury"}, institutions)
        for slug, desk in MANUAL_FAMILIES.items():
            with self.subTest(source=slug):
                self.assertEqual(rows[slug][:2], (desk, "manual"))
                self.assertEqual(rows[slug][2], 1)

    def test_sync_is_idempotent_for_the_new_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "scratch.db"
            build_legacy_db(db)
            conn = connect(db)
            apply_all(conn)
            second = sync_desk_config(conn)
            conn.close()
        self.assertEqual(second.get("sources_inserted", 0), 0)
        self.assertEqual(second.get("desks_inserted", 0), 0)


class TestGovernedDispatch(unittest.TestCase):
    """The shared dispatch, with the real Daily and Japan entries and mocked
    admissions. Nothing fetches, signs or reads a database here."""

    def dispatch(self, slug, entry, *, dry_run=False):
        errors = []
        desk = MANUAL_FAMILIES[slug]
        with mock.patch.object(pipeline, "_governed_admissions",
                               return_value={slug: entry}):
            [result] = pipeline.run_governed_manual_sources(
                [slug], 7, FakeRegistry(desk), errors, dry_run=dry_run)
        self.assertEqual(result.desk_id, desk)
        self.assertEqual(result.source_slug, slug)
        return result, errors

    # -- Daily families --------------------------------------------------

    def daily(self, family="ph_afp_articles", intake=None):
        return pipeline._daily_admission(family, intake=intake)

    def test_daily_awaits_activation_without_the_owner_variable(self):
        with mock.patch.dict(os.environ, {"IPR_DAILY_INTAKE_DIR": "/nowhere"}, clear=False):
            os.environ.pop("IPR_PRIVATE_DAILY_ENABLED", None)
            never = lambda *a: self.fail("intake ran")
            r, errors = self.dispatch("ph_afp_articles", self.daily(intake=never))
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertEqual(r.error_detail, "governed admission awaiting owner activation")
        self.assertEqual(errors, [])

    def test_daily_policy_withholding_release_is_reported_not_run(self):
        policy = {"sources": {"ph_afp_articles": {"private_model_processing": True,
                                                   "public_machine_explanation": True,
                                                   "unattended_release": False}}}
        with mock.patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true"}), \
                mock.patch("processing.daily_intake.load_policy", return_value=policy):
            r, errors = self.dispatch("ph_afp_articles",
                                      self.daily(intake=lambda *a: self.fail("ran")))
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertEqual(r.error_detail, "source-use policy withholds unattended release")
        self.assertEqual(errors, [])

    def activated(self):
        return mock.patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                            "IPR_DAILY_INTAKE_DIR": "/scratch/intake"})

    def policy_open(self):
        policy = {"sources": {f: {"private_model_processing": True,
                                  "public_machine_explanation": True,
                                  "unattended_release": True} for f in SOURCES}}
        return mock.patch("processing.daily_intake.load_policy", return_value=policy)

    def test_daily_dry_run_never_admits(self):
        with self.activated(), self.policy_open():
            r, errors = self.dispatch("ph_afp_articles",
                                      self.daily(intake=lambda *a: self.fail("ran")),
                                      dry_run=True)
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertIn("dry run", r.error_detail)

    def test_daily_without_intake_directory_is_disabled_not_failed(self):
        with mock.patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true"}), \
                self.policy_open():
            os.environ.pop("IPR_DAILY_INTAKE_DIR", None)
            r, errors = self.dispatch("ph_afp_articles",
                                      self.daily(intake=lambda *a: self.fail("ran")))
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertEqual(r.error_detail, "no shared Daily intake directory configured")
        self.assertEqual(errors, [])

    def test_daily_missing_envelope_is_a_visible_failure(self):
        seen = []
        def intake(db_path, intake_dir, family):
            seen.append((intake_dir, family))
            return None
        with self.activated(), self.policy_open():
            r, errors = self.dispatch("id_kemhan_news", self.daily("id_kemhan_news", intake=intake))
        self.assertEqual(seen, [("/scratch/intake", "id_kemhan_news")])
        self.assertEqual(r.status, st.FETCH_FAILURE)
        self.assertTrue(r.is_failure)
        self.assertEqual(r.error_detail, "no signed envelope delivered this run")
        self.assertEqual(len(errors), 1)

    def test_daily_receipt_statuses(self):
        cases = [
            ({"records": 3, "admitted": 2, "holds": []}, st.OK, 2, 1, None),
            ({"records": 2, "admitted": 0, "holds": []}, st.OK_ALL_DUPLICATES, 0, 2, None),
            ({"records": 0, "admitted": 0, "holds": []}, st.OK_NO_PUBLICATIONS, 0, 0, None),
            ({"records": 2, "admitted": 0, "holds": ["daily_record_copying", "daily_record_copying"]},
             st.OK_ALL_FILTERED, 0, 2, "held: daily_record_copying"),
        ]
        for receipt, status, new, dups, detail in cases:
            with self.subTest(receipt=receipt), self.activated(), self.policy_open():
                r, errors = self.dispatch("ph_afp_articles",
                                          self.daily(intake=lambda *a, rc=receipt: rc))
                self.assertEqual((r.status, r.new_documents, r.duplicates, r.error_detail),
                                 (status, new, dups, detail))
                self.assertEqual(errors, [])

    def test_daily_hold_is_a_fixed_code_and_isolated(self):
        def intake(*a):
            raise IntakeHold("daily_envelope_mac_invalid")
        with self.activated(), self.policy_open():
            r, errors = self.dispatch("ph_nsc_official_statements",
                                      self.daily("ph_nsc_official_statements", intake=intake))
        self.assertEqual(r.status, st.ADAPTER_ERROR)
        self.assertEqual(r.error_detail, "daily_intake: daily_envelope_mac_invalid")
        self.assertEqual(len(errors), 1)

    def test_daily_unexpected_exception_reports_only_its_type(self):
        def intake(*a):
            raise ValueError("Original title: restricted text")
        with self.activated(), self.policy_open(), self.assertLogs("pipeline", level="ERROR") as logs:
            r, errors = self.dispatch("ph_afp_articles", self.daily(intake=intake))
        self.assertEqual(r.error_detail, "daily_intake: ValueError")
        self.assertNotIn("restricted", "".join(logs.output) + "".join(errors))

    def test_families_are_dispatched_independently(self):
        """One family's hold neither stops nor hides another's admission."""
        entries = {
            "ph_afp_articles": self.daily(intake=lambda *a: {"records": 1, "admitted": 1, "holds": []}),
            "ph_nsc_official_statements": self.daily(
                "ph_nsc_official_statements",
                intake=mock.Mock(side_effect=IntakeHold("daily_envelope_mac_invalid"))),
        }
        errors = []
        with self.activated(), self.policy_open(), \
                mock.patch.object(pipeline, "_governed_admissions", return_value=entries):
            results = pipeline.run_governed_manual_sources(
                list(entries), 7, FakeRegistry("philippines"), errors)
        by_slug = {r.source_slug: r for r in results}
        self.assertEqual(by_slug["ph_afp_articles"].status, st.OK)
        self.assertEqual(by_slug["ph_nsc_official_statements"].status, st.ADAPTER_ERROR)
        self.assertEqual(len(errors), 1)

    # -- Collector heartbeat (monitoring only) -----------------------------

    def with_heartbeat(self, stamp, intake, family="ph_nsc_official_statements"):
        """Dispatch `family` with an intake dir that holds `stamp` as its heartbeat."""
        from processing.daily_runner import heartbeat_path, write_heartbeat
        with tempfile.TemporaryDirectory() as tmp:
            if stamp == "malformed":
                heartbeat_path(tmp, family).write_text("{not json", encoding="utf-8")
            elif stamp:
                write_heartbeat(tmp, family, stamp)
            with mock.patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                              "IPR_DAILY_INTAKE_DIR": tmp}), \
                    self.policy_open():
                return self.dispatch(family, self.daily(family, intake=intake))

    def test_heartbeat_is_recorded_as_completed_at_for_every_active_outcome(self):
        stamp = "2026-11-03T06:00:00Z"
        outcomes = {
            "quiet": ({"records": 0, "admitted": 0, "holds": []}, st.OK_NO_PUBLICATIONS),
            "admitted": ({"records": 2, "admitted": 2, "holds": []}, st.OK),
            "held": ({"records": 1, "admitted": 0, "holds": ["daily_record_copying"]},
                     st.OK_ALL_FILTERED),
            "no envelope": (None, st.FETCH_FAILURE),
        }
        for name, (receipt, status) in outcomes.items():
            with self.subTest(outcome=name):
                r, _ = self.with_heartbeat(stamp, lambda *a, rc=receipt: rc)
                self.assertEqual(r.status, status)
                self.assertEqual(r.completed_at, stamp)

    def test_heartbeat_survives_an_intake_hold(self):
        def intake(*a):
            raise IntakeHold("daily_envelope_mac_invalid")
        r, _ = self.with_heartbeat("2026-11-03T06:00:00Z", intake)
        self.assertEqual(r.status, st.ADAPTER_ERROR)
        self.assertEqual(r.completed_at, "2026-11-03T06:00:00Z")

    def test_heartbeat_absent_or_malformed_records_no_completion_time(self):
        quiet = {"records": 0, "admitted": 0, "holds": []}
        for stamp in (None, "malformed"):
            with self.subTest(stamp=stamp):
                r, _ = self.with_heartbeat(stamp, lambda *a: quiet)
                self.assertEqual(r.status, st.OK_NO_PUBLICATIONS)
                self.assertIsNone(r.completed_at)

    def test_inactive_admission_never_reports_a_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            from processing.daily_runner import write_heartbeat
            write_heartbeat(tmp, "ph_afp_articles", "2026-11-03T06:00:00Z")
            with mock.patch.dict(os.environ, {"IPR_DAILY_INTAKE_DIR": tmp}):
                os.environ.pop("IPR_PRIVATE_DAILY_ENABLED", None)
                r, _ = self.dispatch("ph_afp_articles",
                                     self.daily(intake=lambda *a: self.fail("ran")))
            self.assertEqual(r.status, st.SKIPPED_DISABLED)
            self.assertIsNone(r.completed_at)
            with self.activated(), self.policy_open():
                os.environ["IPR_DAILY_INTAKE_DIR"] = tmp
                r, _ = self.dispatch("ph_afp_articles",
                                     self.daily(intake=lambda *a: self.fail("ran")),
                                     dry_run=True)
            self.assertIsNone(r.completed_at)

    def test_heartbeat_is_never_an_admission_input(self):
        """The same receipt gives the same result whatever the heartbeat says."""
        receipt = {"records": 2, "admitted": 0, "holds": []}
        seen = []
        for stamp in (None, "2020-01-01T00:00:00Z", "2026-11-03T06:00:00Z"):
            r, _ = self.with_heartbeat(stamp, lambda *a: receipt)
            seen.append((r.status, r.new_documents, r.duplicates, r.error_detail))
        self.assertEqual(len(set(seen)), 1)

    # -- Japan official links --------------------------------------------

    def japan(self, admit_links=None, resolve_commit=None):
        return pipeline._japan_admission(admit_links=admit_links,
                                         resolve_commit=resolve_commit)

    def test_japan_awaits_activation(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JAPAN_MOD_OFFICIAL_LINKS_ENABLED", None)
            r, errors = self.dispatch("jp_mod_news_ja", self.japan(
                admit_links=lambda *a: self.fail("ran"),
                resolve_commit=lambda: self.fail("resolved")))
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertEqual(r.error_detail, "governed admission awaiting owner activation")

    def test_japan_unavailable_collector_branch_is_a_visible_failure(self):
        with mock.patch.dict(os.environ, {"JAPAN_MOD_OFFICIAL_LINKS_ENABLED": "true"}):
            r, errors = self.dispatch("jp_mod_news_ja", self.japan(
                admit_links=lambda *a: self.fail("ran"), resolve_commit=lambda: None))
        self.assertEqual(r.status, st.LISTING_FAILURE)
        self.assertEqual(r.error_detail, "japan_mod_source_ref_unavailable")
        self.assertEqual(len(errors), 1)

    def test_japan_receipt_statuses_and_pinned_commit(self):
        calls = []
        def admit_links(root, commit, db):
            calls.append((commit, db))
            return {"new_official_links": 2, "unchanged_official_links": 5,
                    "source_commit": commit}
        with mock.patch.dict(os.environ, {"JAPAN_MOD_OFFICIAL_LINKS_ENABLED": "true"}):
            r, errors = self.dispatch("jp_mod_news_ja", self.japan(
                admit_links=admit_links, resolve_commit=lambda: "a" * 40))
        self.assertEqual(calls, [("a" * 40, pipeline.DB_PATH)])
        self.assertEqual((r.status, r.new_documents, r.duplicates), (st.OK, 2, 5))
        for receipt, status in (({"new_official_links": 0, "unchanged_official_links": 3},
                                 st.OK_ALL_DUPLICATES),
                                ({"new_official_links": 0, "unchanged_official_links": 0},
                                 st.OK_NO_PUBLICATIONS)):
            with self.subTest(receipt=receipt), \
                    mock.patch.dict(os.environ, {"JAPAN_MOD_OFFICIAL_LINKS_ENABLED": "true"}):
                r, _ = self.dispatch("jp_mod_news_ja", self.japan(
                    admit_links=lambda *a, rc=receipt: rc, resolve_commit=lambda: "b" * 40))
                self.assertEqual(r.status, status)

    def test_japan_hold_is_a_fixed_code(self):
        def admit_links(*a):
            raise RegionalLinkHold("japan_production_sqlite_invalid")
        with mock.patch.dict(os.environ, {"JAPAN_MOD_OFFICIAL_LINKS_ENABLED": "true"}):
            r, errors = self.dispatch("jp_mod_news_ja", self.japan(
                admit_links=admit_links, resolve_commit=lambda: "c" * 40))
        self.assertEqual(r.status, st.ADAPTER_ERROR)
        self.assertEqual(r.error_detail,
                         "japan_mod_official_links: japan_production_sqlite_invalid")
        self.assertEqual(len(errors), 1)

    # -- Korea gating is unchanged ---------------------------------------

    def test_korea_entry_keeps_its_switch_and_label(self):
        entry = pipeline._korea_admission(bridge=lambda run_id: self.fail("ran"))
        self.assertEqual(entry.label, "korea_corpus_bridge")
        with mock.patch("config.KOREA_DAILY_AUTOMATION_ENABLED", False):
            self.assertEqual(entry.inactive_reason(),
                             "governed admission awaiting owner activation")
        with mock.patch("config.KOREA_DAILY_AUTOMATION_ENABLED", True):
            self.assertIsNone(entry.inactive_reason())

    def test_stage_14_no_longer_admits_beside_the_dispatch(self):
        source = (REPO_ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertNotIn("public_intake", source)
        runner = (REPO_ROOT / "processing" / "daily_runner.py").read_text(encoding="utf-8")
        self.assertNotIn("def public_intake", runner)


class TestUSMetadataGovernedDispatch(unittest.TestCase):
    """USCC and Treasury listing metadata through the same dispatch (runtime
    migration 4). The importer is mocked: nothing clones a branch, runs git
    or opens pla_watch.db."""

    USCC = "uscc_press_official_metadata"
    TREASURY = "us_treasury_press_official_metadata"
    CHECKOUT_ENV = {USCC: "IPR_USCC_SOURCE_CHECKOUT",
                    TREASURY: "IPR_US_TREASURY_SOURCE_CHECKOUT"}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.checkout = Path(tmp.name) / "preserved"
        (self.checkout / ".git").mkdir(parents=True)

    def us(self, slug, admit_metadata=None):
        return pipeline._us_metadata_admission(slug, admit_metadata=admit_metadata)

    def delivered(self, slug, path=None):
        return mock.patch.dict(os.environ,
                               {self.CHECKOUT_ENV[slug]: str(path or self.checkout)})

    def dispatch(self, slug, entry, *, dry_run=False):
        errors = []
        with mock.patch.object(pipeline, "_governed_admissions",
                               return_value={slug: entry}):
            [result] = pipeline.run_governed_manual_sources(
                [slug], 7, FakeRegistry("us-indopacific"), errors, dry_run=dry_run)
        self.assertEqual((result.desk_id, result.source_slug), ("us-indopacific", slug))
        return result, errors

    @staticmethod
    def receipt(new, observations=12):
        return {"source_commit_sha": "a" * 40, "observations": observations,
                "new_official_metadata_records": new,
                "source_bodies_copied": False, "publisher_titles_copied": False}

    def test_both_families_reuse_their_existing_importer_and_hold(self):
        from core.uscc_official_metadata import USCCAdmissionHold
        from core.us_treasury_official_metadata import TreasuryAdmissionHold
        from scripts import admit_uscc_official_metadata, admit_us_treasury_official_metadata
        self.assertEqual(set(pipeline._US_METADATA_FAMILIES), {self.USCC, self.TREASURY})
        uscc, treasury = self.us(self.USCC), self.us(self.TREASURY)
        self.assertEqual((uscc.label, uscc.holds), ("uscc_official_metadata", (USCCAdmissionHold,)))
        self.assertEqual((treasury.label, treasury.holds),
                         ("treasury_official_metadata", (TreasuryAdmissionHold,)))
        self.assertEqual(pipeline._US_METADATA_FAMILIES[self.USCC].importer,
                         admit_uscc_official_metadata.__name__)
        self.assertEqual(pipeline._US_METADATA_FAMILIES[self.TREASURY].importer,
                         admit_us_treasury_official_metadata.__name__)

    def test_no_activation_variable_is_awaited(self):
        """The 2026-10-15 approval is standing. The only gate is whether this
        run was handed the preserved history, and a run that was not is
        reported as disabled, not as awaiting an owner act."""
        for slug in (self.USCC, self.TREASURY):
            with self.subTest(source=slug), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(self.CHECKOUT_ENV[slug], None)
                r, errors = self.dispatch(slug, self.us(
                    slug, admit_metadata=lambda *a: self.fail("ran")))
                self.assertEqual(r.status, st.SKIPPED_DISABLED)
                self.assertEqual(r.error_detail,
                                 "preserved source history not delivered to this run")
                self.assertEqual(errors, [])

    def test_missing_clone_is_a_visible_failure(self):
        for slug, code in ((self.USCC, "uscc_source_checkout_unavailable"),
                           (self.TREASURY, "treasury_source_checkout_unavailable")):
            with self.subTest(source=slug), \
                    self.delivered(slug, self.checkout / "absent"):
                r, errors = self.dispatch(slug, self.us(
                    slug, admit_metadata=lambda *a: self.fail("ran")))
                self.assertEqual(r.status, st.LISTING_FAILURE)
                self.assertTrue(r.is_failure)
                self.assertEqual(r.error_detail, code)
                self.assertEqual(len(errors), 1)

    def test_dry_run_never_admits(self):
        with self.delivered(self.USCC):
            r, errors = self.dispatch(self.USCC, self.us(
                self.USCC, admit_metadata=lambda *a: self.fail("ran")), dry_run=True)
        self.assertEqual(r.status, st.SKIPPED_DISABLED)
        self.assertIn("dry run", r.error_detail)

    def test_receipt_statuses_and_pinned_arguments(self):
        calls = []
        def admit_metadata(checkout, db):
            calls.append((Path(checkout), db))
            return self.receipt(3)
        with self.delivered(self.USCC):
            r, errors = self.dispatch(self.USCC, self.us(self.USCC, admit_metadata=admit_metadata))
        self.assertEqual(calls, [(self.checkout, pipeline.DB_PATH)])
        self.assertEqual((r.status, r.new_documents, r.duplicates), (st.OK, 3, 0))
        self.assertEqual(errors, [])
        # A re-examined history with nothing new is "all duplicates"; the
        # receipt counts observation files, so no duplicate figure is invented.
        with self.delivered(self.TREASURY):
            r, errors = self.dispatch(self.TREASURY, self.us(
                self.TREASURY, admit_metadata=lambda *a: self.receipt(0)))
        self.assertEqual((r.status, r.new_documents, r.duplicates),
                         (st.OK_ALL_DUPLICATES, 0, 0))
        self.assertEqual(errors, [])

    def test_hold_is_a_fixed_code_and_isolated(self):
        from core.uscc_official_metadata import USCCAdmissionHold
        from core.us_treasury_official_metadata import TreasuryAdmissionHold
        for slug, hold, detail in (
                (self.USCC, USCCAdmissionHold("missing_or_excessive_source_history"),
                 "uscc_official_metadata: missing_or_excessive_source_history"),
                (self.TREASURY, TreasuryAdmissionHold("invalid_observation_file"),
                 "treasury_official_metadata: invalid_observation_file")):
            with self.subTest(source=slug), self.delivered(slug):
                r, errors = self.dispatch(slug, self.us(
                    slug, admit_metadata=mock.Mock(side_effect=hold)))
                self.assertEqual(r.status, st.ADAPTER_ERROR)
                self.assertEqual(r.error_detail, detail)
                self.assertEqual(len(errors), 1)

    def test_unexpected_exception_reports_only_its_type(self):
        import subprocess
        def admit_metadata(*a):
            raise subprocess.CalledProcessError(
                128, ["git"], output="fatal: Original title: restricted text")
        with self.delivered(self.USCC), self.assertLogs("pipeline", level="ERROR") as logs:
            r, errors = self.dispatch(self.USCC, self.us(self.USCC, admit_metadata=admit_metadata))
        self.assertEqual(r.error_detail, "uscc_official_metadata: CalledProcessError")
        self.assertNotIn("restricted", "".join(logs.output) + "".join(errors))

    def test_the_two_families_are_dispatched_independently(self):
        from core.uscc_official_metadata import USCCAdmissionHold
        entries = {
            self.USCC: self.us(self.USCC, admit_metadata=mock.Mock(
                side_effect=USCCAdmissionHold("database_integrity_hold"))),
            self.TREASURY: self.us(self.TREASURY, admit_metadata=lambda *a: self.receipt(1)),
        }
        errors = []
        with self.delivered(self.USCC), self.delivered(self.TREASURY), \
                mock.patch.object(pipeline, "_governed_admissions", return_value=entries):
            results = pipeline.run_governed_manual_sources(
                list(entries), 7, FakeRegistry("us-indopacific"), errors)
        by_slug = {r.source_slug: r for r in results}
        self.assertEqual(by_slug[self.USCC].status, st.ADAPTER_ERROR)
        self.assertEqual(by_slug[self.TREASURY].status, st.OK)
        self.assertEqual(len(errors), 1)


class TestLivenessTreatsManualRegistrationsAsInert(unittest.TestCase):

    def test_manual_sources_with_nothing_admitted_are_inert(self):
        from scripts import check_source_liveness as liveness
        expectations = liveness.expectations()
        for slug in MANUAL_FAMILIES:
            with self.subTest(source=slug):
                exp = expectations[slug]
                self.assertTrue(exp.manual)
                self.assertFalse(exp.broken)
                state, _, detail = liveness.classify(slug, 0, None, date(2026, 11, 1), 7, exp)
                self.assertEqual(state, "INERT")
                self.assertIn("manual source", detail)

    # -- Collector heartbeat -------------------------------------------------
    # NSC last posted in July and must not read as red while its collector runs.

    TODAY = date(2026, 11, 4)

    def classify(self, slug, total, last_seen, heartbeat, **kw):
        from scripts import check_source_liveness as liveness
        exp = liveness.expectations()[slug]
        return liveness.classify(slug, total, last_seen, self.TODAY, 7, exp,
                                 heartbeat=heartbeat, **kw)

    def test_quiet_publisher_behind_a_running_collector_is_healthy(self):
        state, days, detail = self.classify(
            "ph_nsc_official_statements", 3, "2026-07-14", "2026-11-03T06:00:00Z")
        self.assertEqual((state, days), ("HEALTHY", 1))
        self.assertIn("collector heartbeat 2026-11-03", detail)
        self.assertIn("last article 2026-07-14", detail)

    def test_never_admitted_family_with_a_running_collector_is_healthy(self):
        state, _, detail = self.classify(
            "ph_afp_articles", 0, None, "2026-11-04T06:00:00Z")
        self.assertEqual(state, "HEALTHY")
        self.assertIn("no article admitted", detail)

    def test_stalled_collector_is_unhealthy_whatever_the_articles_say(self):
        state, days, detail = self.classify(
            "ph_afp_articles", 40, "2026-11-03", "2026-10-28T06:00:00Z")
        self.assertEqual((state, days), ("UNHEALTHY", 7))
        self.assertIn("collector heartbeat last observed 2026-10-28", detail)

    def test_heartbeat_threshold_is_inclusive_and_tunable(self):
        edge = "2026-11-01T06:00:00Z"          # 3 days
        self.assertEqual(self.classify("ph_afp_articles", 0, None, edge)[0], "HEALTHY")
        late = "2026-10-31T06:00:00Z"          # 4 days
        self.assertEqual(self.classify("ph_afp_articles", 0, None, late)[0], "UNHEALTHY")
        self.assertEqual(self.classify("ph_afp_articles", 0, None, "2026-10-30T06:00:00Z",
                                       heartbeat_max_days=5)[0], "HEALTHY")

    def test_no_heartbeat_is_judged_exactly_as_before(self):
        self.assertEqual(self.classify("ph_afp_articles", 0, None, None)[0], "INERT")
        # Without a heartbeat an old article is still stale, as before.
        self.assertEqual(self.classify(
            "ph_nsc_official_statements", 3, "2026-07-14", None)[0], "UNHEALTHY")

    def test_unparseable_heartbeat_falls_back(self):
        self.assertEqual(self.classify("ph_afp_articles", 0, None, "garbage")[0], "INERT")

    def test_broken_inert_and_scraped_expectations_are_unaffected(self):
        from scripts import check_source_liveness as liveness
        fresh = "2026-11-04T06:00:00Z"
        broken = liveness.Expectation(broken=True, reason="adapter unusable")
        inert = liveness.Expectation(inert=True, reason="declared stub")
        scraped = liveness.Expectation(threshold=7)
        self.assertEqual(liveness.classify("x", 5, "2026-11-03", self.TODAY, 7, broken,
                                           heartbeat=fresh)[0], "UNHEALTHY")
        self.assertEqual(liveness.classify("x", 0, None, self.TODAY, 7, inert,
                                           heartbeat=fresh)[0], "INERT")
        # A scraped source is judged by article recency; a heartbeat is ignored.
        self.assertEqual(liveness.classify("x", 5, "2026-10-01", self.TODAY, 7, scraped,
                                           heartbeat=fresh)[0], "UNHEALTHY")

    def test_every_manual_family_classifies_by_heartbeat(self):
        for slug in MANUAL_FAMILIES:
            with self.subTest(source=slug):
                self.assertEqual(self.classify(slug, 0, None, "2026-11-03T06:00:00Z")[0],
                                 "HEALTHY")
                self.assertEqual(self.classify(slug, 0, None, "2026-10-01T06:00:00Z")[0],
                                 "UNHEALTHY")


class TestHeartbeatsFromRunResults(unittest.TestCase):
    """`heartbeats()` reads only the latest row per slug from source_run_results."""

    def build(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "t.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE source_run_results (id INTEGER PRIMARY KEY, "
                     "source_slug TEXT, status TEXT, completed_at TEXT)")
        conn.executemany("INSERT INTO source_run_results (source_slug, status, completed_at) "
                         "VALUES (?,?,?)", rows)
        conn.commit()
        conn.close()
        return path

    def test_latest_row_wins_and_disabled_or_null_rows_give_none(self):
        from scripts import check_source_liveness as liveness
        path = self.build([
            ("a", st.OK, "2026-11-01T06:00:00Z"),
            ("a", st.OK_ALL_DUPLICATES, "2026-11-03T06:00:00Z"),   # latest
            ("b", st.OK, "2026-11-02T06:00:00Z"),
            ("b", st.SKIPPED_DISABLED, "2026-11-03T06:00:00Z"),    # disabled since
            ("c", st.OK, "2026-11-02T06:00:00Z"),
            ("c", st.OK, None),                                    # unreadable since
            ("d", st.FETCH_FAILURE, "2026-11-03T07:00:00Z"),       # collector ran
        ])
        self.assertEqual(liveness.heartbeats(path),
                         {"a": "2026-11-03T06:00:00Z", "d": "2026-11-03T07:00:00Z"})

    def test_round_trip_through_the_real_recorder(self):
        """dispatch -> storage.db.record_source_run_result -> migrated table ->
        heartbeats(): the stamp survives, and no write time replaces it."""
        from processing.daily_runner import write_heartbeat
        from scripts import check_source_liveness as liveness
        from storage import db
        slug, stamp = "ph_nsc_official_statements", "2026-11-03T06:00:00Z"
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "rt.db"
        build_legacy_db(db_path)
        conn = connect(db_path)
        apply_all(conn)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM scrape_runs WHERE id = 1").fetchone()[0], 1)
        conn.close()
        write_heartbeat(tmp.name, slug, stamp)
        entry = pipeline._daily_admission(
            slug, intake=lambda *a: {"records": 0, "admitted": 0, "holds": []})
        policy = {"sources": {f: {"private_model_processing": True,
                                  "public_machine_explanation": True,
                                  "unattended_release": True} for f in SOURCES}}
        with mock.patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                          "IPR_DAILY_INTAKE_DIR": tmp.name}), \
                mock.patch("processing.daily_intake.load_policy", return_value=policy), \
                mock.patch.object(pipeline, "_governed_admissions", return_value={slug: entry}), \
                mock.patch.object(db, "DB_PATH", db_path):
            [result] = pipeline.run_governed_manual_sources(
                [slug], 1, FakeRegistry("philippines"), [])
            db.record_source_run_result(1, result)
        self.assertEqual(liveness.heartbeats(db_path), {slug: stamp})
        stored = sqlite3.connect(db_path).execute(
            "SELECT status, started_at, completed_at FROM source_run_results").fetchall()
        self.assertEqual(stored, [(st.OK_NO_PUBLICATIONS, None, stamp)])

    def test_database_without_the_table_has_no_heartbeats(self):
        from scripts import check_source_liveness as liveness
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "empty.db"
        sqlite3.connect(path).close()
        self.assertEqual(liveness.heartbeats(path), {})


if __name__ == "__main__":
    unittest.main()
