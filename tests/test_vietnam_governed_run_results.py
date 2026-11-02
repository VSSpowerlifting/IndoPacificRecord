"""Vietnam run-result rows through the shared governed dispatch.

The two registered Vietnam families were dispatched as "manual source with no
governed admission" even on days their Daily steps admitted, held or missed
records. Both steps write pla_watch.db before the pipeline starts (the handoff
replaces the file atomically), so the pipeline reports what each recorded for
this run: the handoff step's printed receipt and the bibliographic collector's
own run row. These tests pin that every state stays distinguishable — awaiting
activation, quiet, unchanged, held, admitted and missed — with fixed-code
details and no source text.

Everything runs on scratch files and databases; nothing fetches, signs or
opens pla_watch.db.
"""
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pipeline
from core.collection import status as st
from scripts.collect_vietnam_government_documents import FAMILY as VPCP

MPS = "vn_mps_foreign_affairs_vi"
SIGNED = "2026-11-01T22:40:00Z"
NOW = datetime(2026, 11, 2, 11, 5, tzinfo=timezone.utc)
ACTIVE = {"VIETNAM_DAILY_HANDOFF_ENABLED": "true", "VIETNAM_VPCP_METADATA_ENABLED": "true",
          "GITHUB_RUN_ID": "41400000000", "GITHUB_RUN_ATTEMPT": "1"}


class FakeRegistry:
    def get_source(self, slug):
        return SimpleNamespace(desk_id="vietnam", access_method="manual")


def ok_receipt(by_family, generated_utc=SIGNED):
    return {"status": "OK", "run_id": "41399999999-1", "counts": {},
            "by_family": by_family, "generated_utc": generated_utc, "deferred": []}


class VietnamDispatch(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.receipt = self.tmp / "vietnam-handoff.json"
        env = mock.patch.dict(os.environ, {"IPR_VIETNAM_HANDOFF_RECEIPT": str(self.receipt)})
        env.start()
        self.addCleanup(env.stop)
        for name in ("VIETNAM_DAILY_HANDOFF_ENABLED", "VIETNAM_VPCP_METADATA_ENABLED",
                     "VPCP_METADATA_ONLY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            os.environ.pop(name, None)

    def write(self, receipt):
        self.receipt.write_text(json.dumps(receipt) if isinstance(receipt, dict) else receipt)

    def dispatch(self, slug, *, report=None, env=ACTIVE, dry_run=False):
        entries = {MPS: pipeline._vietnam_handoff_admission(MPS, clock=lambda: NOW),
                   VPCP: pipeline._vpcp_admission(clock=lambda: NOW,
                                                  read_report=lambda run: report)}
        errors = []
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(pipeline, "_governed_admissions", return_value=entries):
            [result] = pipeline.run_governed_manual_sources(
                [slug], 7, FakeRegistry(), errors, dry_run=dry_run)
        self.assertEqual((result.source_slug, result.desk_id), (slug, "vietnam"))
        return result, errors

    def assertRow(self, result, status, new=0, dups=0, detail=None):
        self.assertEqual((result.status, result.new_documents, result.duplicates,
                          result.error_detail), (status, new, dups, detail))

    # -- registration and activation -------------------------------------

    def test_both_registered_families_have_a_governed_admission(self):
        governed = pipeline._governed_admissions()
        self.assertIn(MPS, governed)
        self.assertIn(VPCP, governed)
        self.assertNotIn("vn_moit_energy_vi", governed)

    def test_unset_activations_report_awaiting_activation_and_read_nothing(self):
        self.write("not read")
        for slug in (MPS, VPCP):
            with self.subTest(source=slug):
                r, errors = self.dispatch(slug, report=None, env={})
                self.assertRow(r, st.SKIPPED_DISABLED,
                               detail="governed admission awaiting owner activation")
                self.assertEqual(errors, [])

    def test_metadata_only_run_does_not_report_the_handoff(self):
        r, _ = self.dispatch(MPS, env=dict(ACTIVE, VPCP_METADATA_ONLY="true"))
        self.assertRow(r, st.SKIPPED_DISABLED,
                       detail="metadata-only run: Vietnam handoff not admitted")

    def test_dry_run_reads_no_receipt(self):
        r, _ = self.dispatch(MPS, dry_run=True)
        self.assertRow(r, st.SKIPPED_DISABLED, detail="dry run: governed admission not run")

    # -- handoff lane ----------------------------------------------------

    def test_admitted_unchanged_and_quiet_families_are_told_apart(self):
        self.write(ok_receipt({MPS: {"published": 2, "duplicate": 1}}))
        self.assertRow(self.dispatch(MPS)[0], st.OK, new=2, dups=1)
        self.write(ok_receipt({MPS: {"duplicate": 3}}))
        self.assertRow(self.dispatch(MPS)[0], st.OK_ALL_DUPLICATES, dups=3)
        self.write(ok_receipt({MPS: {}}))
        self.assertRow(self.dispatch(MPS)[0], st.OK_NO_PUBLICATIONS)

    def test_held_records_are_reported_by_code(self):
        self.write(ok_receipt({MPS: {"held_source": 1, "rejected:Missing_Date": 1}}))
        r, errors = self.dispatch(MPS)
        self.assertRow(r, st.OK_ALL_FILTERED,
                       detail="held: held_source, rejected_missing_date")
        self.assertEqual(errors, [])

    def test_a_handoff_hold_is_a_failure_with_its_code_only(self):
        self.write({"status": "HOLD", "reason": "vietnam_handoff_signature_invalid",
                    "database_replaced": False})
        r, errors = self.dispatch(MPS)
        self.assertRow(r, st.ADAPTER_ERROR,
                       detail="vietnam_daily_handoff: vietnam_handoff_signature_invalid")
        self.assertEqual(len(errors), 1)
        self.write({"status": "HOLD", "reason": "Bộ Công an: free text <script>",
                    "database_replaced": False})
        r, _ = self.dispatch(MPS)
        self.assertRow(r, st.ADAPTER_ERROR, detail="vietnam_daily_handoff: unclassified_hold")

    def test_no_receipt_from_an_enabled_step_is_a_missed_run(self):
        r, errors = self.dispatch(MPS)
        self.assertRow(r, st.FETCH_FAILURE, detail="no handoff receipt recorded this run")
        self.assertEqual(len(errors), 1)

    def test_unreadable_receipt_is_an_adapter_error(self):
        for body in ("", "Traceback (most recent call last):", json.dumps(ok_receipt(None))):
            with self.subTest(body=body[:20]):
                self.write(body)
                self.assertRow(self.dispatch(MPS)[0], st.ADAPTER_ERROR,
                               detail="vietnam_daily_handoff: receipt_unreadable")

    def test_unconfigured_receipt_path_is_reported_not_failed(self):
        with mock.patch.dict(os.environ, {"IPR_VIETNAM_HANDOFF_RECEIPT": ""}):
            r, errors = self.dispatch(MPS)
        self.assertRow(r, st.SKIPPED_DISABLED,
                       detail="no Vietnam handoff receipt path configured")
        self.assertEqual(errors, [])

    def test_a_re_served_stale_envelope_is_missed_not_quiet(self):
        """The handoff re-serves the last envelope when the private run did not
        refresh it; its records re-admit as duplicates."""
        stale = (NOW - timedelta(hours=37)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write(ok_receipt({MPS: {"duplicate": 2}}, generated_utc=stale))
        r, errors = self.dispatch(MPS)
        self.assertRow(r, st.FETCH_FAILURE, detail="signed handoff not refreshed since "
                       "2026-10-31T22:05Z (run 41399999999-1)")
        self.assertEqual(len(errors), 1)
        fresh = (NOW - timedelta(hours=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write(ok_receipt({MPS: {"duplicate": 2}}, generated_utc=fresh))
        self.assertRow(self.dispatch(MPS)[0], st.OK_ALL_DUPLICATES, dups=2)

    def test_a_family_the_envelope_did_not_report_is_missed(self):
        self.write(ok_receipt({VPCP: {}}))
        self.assertRow(self.dispatch(MPS)[0], st.FETCH_FAILURE,
                       detail="signed handoff (run 41399999999-1) carried no report "
                              "for this family")

    # -- VPCP: bibliographic lane and composite ---------------------------

    def metadata_only(self):
        return dict(ACTIVE, VIETNAM_DAILY_HANDOFF_ENABLED="")

    def test_bibliographic_run_outcomes(self):
        cases = [
            ({"status": "ok", "new": 2, "revised": 1, "unchanged": 4, "held": 0},
             (st.OK, 3, 4, None)),
            ({"status": "ok", "new": 0, "revised": 0, "unchanged": 3, "held": 0},
             (st.OK_ALL_DUPLICATES, 0, 3, None)),
            ({"status": "ok", "new": 0, "revised": 0, "unchanged": 0, "held": 0},
             (st.OK_NO_PUBLICATIONS, 0, 0, None)),
            ({"status": "partial", "new": 0, "revised": 0, "unchanged": 1, "held": 2},
             (st.OK_ALL_FILTERED, 0, 1, "held: 2_records_held")),
            ({"status": "held", "held": 0, "hold_reason": "listing_or_access_failed"},
             (st.LISTING_FAILURE, 0, 0, "vpcp_bibliographic_metadata: listing_or_access_failed")),
        ]
        for report, expected in cases:
            with self.subTest(report=report):
                r, _ = self.dispatch(VPCP, report=report, env=self.metadata_only())
                self.assertRow(r, *expected)

    def test_an_enabled_collector_that_recorded_nothing_is_missed(self):
        r, errors = self.dispatch(VPCP, report=None, env=self.metadata_only())
        self.assertRow(r, st.FETCH_FAILURE, detail="no bibliographic collection recorded this run")
        self.assertEqual(len(errors), 1)

    def test_no_workflow_run_cannot_match_a_record(self):
        env = {k: v for k, v in self.metadata_only().items() if not k.startswith("GITHUB_")}
        r, _ = self.dispatch(VPCP, report={"status": "ok"}, env=env)
        self.assertRow(r, st.SKIPPED_DISABLED,
                       detail="no workflow run to match a collection record")

    def test_a_failed_lane_is_never_hidden_by_the_other(self):
        stale = (NOW - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write(ok_receipt({VPCP: {"duplicate": 1}}, generated_utc=stale))
        r, errors = self.dispatch(VPCP, report={"status": "ok", "new": 2, "revised": 0,
                                                "unchanged": 1, "held": 0})
        self.assertEqual((r.status, r.new_documents, r.duplicates),
                         (st.FETCH_FAILURE, 2, 1))
        self.assertTrue(r.error_detail.startswith(
            "vietnam_daily_handoff: signed handoff not refreshed since"))
        self.assertEqual(len(errors), 1)

    def test_lanes_combine_counts_and_precedence(self):
        self.write(ok_receipt({VPCP: {"published": 1}}))
        r, _ = self.dispatch(VPCP, report={"status": "ok", "new": 0, "revised": 0,
                                           "unchanged": 3, "held": 0})
        self.assertRow(r, st.OK, new=1, dups=3)
        self.write(ok_receipt({VPCP: {"held_source": 1}}))
        r, _ = self.dispatch(VPCP, report={"status": "ok", "new": 0, "revised": 0,
                                           "unchanged": 3, "held": 0})
        self.assertRow(r, st.OK_ALL_FILTERED, dups=3,
                       detail="vietnam_daily_handoff: held: held_source")
        self.write(ok_receipt({VPCP: {}}))
        r, _ = self.dispatch(VPCP, report={"status": "ok", "new": 0, "revised": 0,
                                           "unchanged": 0, "held": 0})
        self.assertRow(r, st.OK_NO_PUBLICATIONS)

    def test_handoff_only_vpcp_reports_its_handoff_lane(self):
        self.write(ok_receipt({VPCP: {"published": 1}}))
        env = dict(ACTIVE, VIETNAM_VPCP_METADATA_ENABLED="")
        self.assertRow(self.dispatch(VPCP, report="unread", env=env)[0], st.OK, new=1)


class VPCPCollectionRecord(unittest.TestCase):
    """The real query, against the collector's own table on a scratch database."""

    def test_reads_only_this_run_and_attempt(self):
        from migrations.runner import apply_all, connect
        from tests.test_migrations import build_legacy_db
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scratch.db"
            build_legacy_db(path)
            conn = connect(path)
            apply_all(conn)
            conn.close()
            conn = sqlite3.connect(str(path))
            for run, report in (("41400000000-1", {"status": "held",
                                                   "hold_reason": "listing_or_access_failed"}),
                                ("41400000000-2", {"status": "ok", "new": 1})):
                conn.execute("INSERT INTO official_document_collection_runs VALUES (?,?,?,?,?,?)",
                             (VPCP, run, SIGNED, "a" * 40, report["status"], json.dumps(report)))
            conn.commit()
            conn.close()
            with mock.patch("storage.db.DB_PATH", str(path)):
                self.assertEqual(pipeline._read_vpcp_collection_report("41400000000-2"),
                                 {"status": "ok", "new": 1})
                self.assertIsNone(pipeline._read_vpcp_collection_report("41400000001-1"))


if __name__ == "__main__":
    unittest.main()
