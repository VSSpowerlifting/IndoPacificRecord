"""Freshness step 2: the shared Daily signer carries signed collection facts.

Offline and synthetic: custody is a throwaway git checkout, the model is never
called, nothing contacts a publisher or GitHub.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pipeline
from core.collection import attempts
from core.collection import status as st
from core.crossdesk_official_metadata_candidates import canonical
from core.daily_sources import SOURCES
from processing import daily_intake as d, daily_runner as runner
from tests.test_collection_attempts import COMMIT, SENTINELS, custody, ledger, noisy
from tests.test_indonesia_shared_daily import FAMILY, KEY, policy
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate

POLICY = policy()
PROCESSOR = "f" * 40
NOW = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc)


def good(family=FAMILY, **over):
    base = {"schema": attempts.SCHEMA, "family": family, "custody_commit": COMMIT,
            "attested": True, "reason": None,
            "latest": {"run_id": "1-1", "target_date": "2026-11-16",
                       "target_date_source": "schedule-slot",
                       "finished_utc": "2026-11-17T00:50:13.490049+00:00",
                       "result": "ok", "health": "ok", "healthy": True},
            "latest_healthy_target_date": "2026-11-16", "unledgered_exit": None}
    base.update(over)
    return base


def sign(collection=None, **kw):
    with patch.object(d, "git", return_value=PROCESSOR.encode() + b"\n"):
        return d.sign_outputs({}, family=FAMILY, policy=policy(), key=KEY,
                              collection=collection, **kw)


class SignOutputs(unittest.TestCase):
    def test_without_collection_the_v1_packet_and_mac_are_unchanged(self):
        envelope = sign()
        expected = {"schema": "ipr-shared-daily-machine-output/1", "family": FAMILY,
                    "source_repository": d.PRIVATE_REPO, "source_ref": d.REFS[FAMILY],
                    "processor_commit": PROCESSOR, "records": [], "held": []}
        self.assertEqual(envelope["packet"], expected)
        self.assertEqual(d.DOMAIN, b"ipr-shared-daily-machine-output/1\n")
        mac = hmac.new(KEY.encode(), b"ipr-shared-daily-machine-output/1\n" + canonical(expected),
                       hashlib.sha256).hexdigest()
        self.assertEqual(envelope["mac"], mac)
        self.assertEqual(sign(None), envelope)

    def test_collection_signs_v2_under_its_own_domain(self):
        envelope = sign(good())
        packet = envelope["packet"]
        self.assertEqual(packet["schema"], d.SCHEMA_V2)
        self.assertEqual(packet["collection"], good())
        mac = hmac.new(KEY.encode(), b"ipr-shared-daily-machine-output/2\n" + canonical(packet),
                       hashlib.sha256).hexdigest()
        self.assertEqual(envelope["mac"], mac)
        self.assertNotEqual(envelope["mac"], sign()["mac"])
        # Same records and held list as /1.
        v1 = sign()["packet"]
        self.assertEqual({k: v for k, v in packet.items() if k not in ("schema", "collection")},
                         {k: v for k, v in v1.items() if k != "schema"})

    def test_invalid_collection_is_replaced_by_an_unattested_block(self):
        for bad in ({}, good(attested="yes"), dict(good(), extra=1), "x",
                    good(family="ph_afp_articles"), good(latest=dict(good()["latest"], result="zzz"))):
            with self.subTest(bad=bad):
                block = sign(bad)["packet"]["collection"]
                self.assertIsNotNone(attempts.validate(block))
                self.assertEqual((block["attested"], block["reason"], block["family"]),
                                 (False, "collection_attestation_invalid", FAMILY))
        # A well-formed commit in the bad block is kept; otherwise a zero commit.
        self.assertEqual(sign(good(attested="yes"))["packet"]["collection"]["custody_commit"], COMMIT)
        self.assertEqual(sign({})["packet"]["collection"]["custody_commit"], "0" * 40)

    def test_size_bound_still_applies(self):
        with patch.object(d, "canonical", return_value=b"x" * 512001):
            with self.assertRaises(d.IntakeHold):
                sign(good())

    def test_v2_round_trips_through_admit_and_collection_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "public.db"
            build_legacy_db(db)
            migrate(db)
            for block in (good(), good(attested=False, reason="no_ledger", latest=None,
                                       latest_healthy_target_date=None)):
                envelope = d.sign_outputs({}, family=FAMILY, policy=POLICY, key=KEY,
                                          collection=block)  # real processor commit
                with sqlite3.connect(str(db)) as conn:
                    receipt = d.admit(conn, envelope, family=FAMILY, policy=POLICY, key=KEY)
                self.assertEqual(receipt["holds"], [])
                self.assertEqual(d.collection_facts(envelope["packet"]), block)
            tampered = json.loads(json.dumps(d.sign_outputs(
                {}, family=FAMILY, policy=POLICY, key=KEY, collection=good())))
            tampered["packet"]["collection"]["latest"]["result"] = "timeout"
            with sqlite3.connect(str(db)) as conn, self.assertRaises(d.IntakeHold):
                d.admit(conn, tampered, family=FAMILY, policy=POLICY, key=KEY)

    def test_signing_rule_is_the_declared_unattended_cadence(self):
        self.assertEqual({f for f, s in SOURCES.items() if s.signs_collection()},
                         {"ph_afp_articles", "ph_nsc_official_statements", "id_kemhan_news",
                          "jp_jcg_press_en"})


class SignerEndToEnd(unittest.TestCase):
    """private_run over a synthetic custody, then the public governed admission."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "public.db"
        build_legacy_db(self.db)
        migrate(self.db)

    def run_signer(self, files, *, reader=None):
        repo, head = custody(self.tmp, files)
        self.head = head
        state = self.tmp / "queue.json"
        with patch.object(runner, "verified_source", return_value=[]), \
             patch.object(runner, "bind_admitted_metadata", return_value=[]), \
             patch.object(runner, "load_policy", return_value=POLICY), \
             patch.dict(os.environ, {"DAILY_OUTPUT_KEY": KEY}):
            if reader is None:
                result = runner.private_run(FAMILY + "," + str(repo) + "," + head,
                                            public_db=self.db, state_path=state,
                                            out_dir=self.tmp / "out")
            else:
                with patch("core.daily_sources.DailySource.collection_attempt", reader):
                    result = runner.private_run(FAMILY + "," + str(repo) + "," + head,
                                                public_db=self.db, state_path=state,
                                                out_dir=self.tmp / "out")
        self.assertTrue(state.exists())  # the queue is written before signing
        envelope = json.loads((self.tmp / "out" / (FAMILY + ".json")).read_text())
        return result, envelope

    def public_outcome(self, envelope):
        inbox = self.tmp / "in"
        inbox.mkdir(exist_ok=True)
        (inbox / (FAMILY + ".json")).write_text(json.dumps(envelope))
        env = {"IPR_DAILY_INTAKE_DIR": str(inbox), SOURCES[FAMILY].key_env: KEY}
        with patch.dict(os.environ, env), patch.object(pipeline, "DB_PATH", self.db), \
                patch.object(runner, "load_policy", return_value=POLICY), \
                patch.object(d, "load_policy", return_value=POLICY):
            return pipeline._daily_admission(FAMILY, clock=lambda: NOW).admit(1)

    def test_a_failed_latest_ledger_is_signed_and_reported_after_admission(self):
        files = {"state/ledger/a.json": ledger("100-1", "2026-11-17", "2026-11-17T19:10:08+00:00",
                                               result="access_challenged", health="fail"),
                 "state/ledger/z.json": noisy()}
        files["state/ledger/z.json"]["finished_utc"] = "2026-11-17T01:00:00+00:00"
        result, envelope = self.run_signer(files)
        self.assertEqual(envelope["packet"]["schema"], d.SCHEMA_V2)
        block = envelope["packet"]["collection"]
        self.assertEqual((block["attested"], block["latest"]["result"], block["latest"]["healthy"],
                          block["custody_commit"]), (True, "access_challenged", False, self.head))
        self.assertEqual(result["collection"], block)
        # No private ledger text is in the signed bytes or the public detail.
        raw = json.dumps(envelope)
        outcome = self.public_outcome(envelope)
        self.assertEqual(outcome.status, st.ACCESS_CHALLENGED)
        for sentinel in SENTINELS + ("example.invalid",):
            self.assertNotIn(sentinel, raw)
            self.assertNotIn(sentinel, outcome.error_detail or "")
        self.assertIn("access_challenged", outcome.error_detail)

    def test_a_healthy_current_collection_reports_ok(self):
        files = {"state/ledger/a.json": ledger("100-1", "2026-11-16", "2026-11-17T00:50:13.490049+00:00")}
        _, envelope = self.run_signer(files)
        self.assertEqual(self.public_outcome(envelope).status, st.OK_NO_PUBLICATIONS)

    def test_a_nonzero_exit_without_a_ledger_is_reported(self):
        files = {"state/ledger/a.json": ledger("100-1", "2026-11-16", "2026-11-17T00:50:13+00:00"),
                 "state/private_attempts/101-1.json": {"collector_exit_status": 1}}
        result, envelope = self.run_signer(files)
        self.assertEqual(result["collection"]["unledgered_exit"],
                         {"run_id": "101-1", "collector_exit_status": 1})
        outcome = self.public_outcome(envelope)
        self.assertEqual(outcome.status, st.FETCH_FAILURE)
        self.assertIn("without a ledger", outcome.error_detail)

    def test_empty_custody_signs_unattested(self):
        result, envelope = self.run_signer({"README": "x"})
        self.assertEqual((result["collection"]["attested"], result["collection"]["reason"]),
                         (False, "no_ledger"))
        outcome = self.public_outcome(envelope)
        self.assertEqual(outcome.status, st.FETCH_FAILURE)
        self.assertIn("no_ledger", outcome.error_detail)

    def test_a_reader_exception_still_writes_the_queue_and_signs(self):
        def broken(self_, repo, commit):
            raise RuntimeError("SENTINEL-reader-secret")
        result, envelope = self.run_signer({"README": "x"}, reader=broken)
        block = envelope["packet"]["collection"]
        self.assertEqual((block["attested"], block["reason"]), (False, "collection_reader_failed"))
        self.assertIsNotNone(attempts.validate(block))
        self.assertNotIn("SENTINEL-reader-secret", json.dumps(envelope) + json.dumps(result))
        self.assertEqual(envelope["packet"]["records"], [])

    def test_a_reader_returning_garbage_is_replaced_not_signed(self):
        result, envelope = self.run_signer({"README": "x"}, reader=lambda s, r, c: {"bad": 1})
        self.assertEqual(envelope["packet"]["collection"]["reason"], "collection_attestation_invalid")
        self.assertEqual(result["collection"], envelope["packet"]["collection"])

    def test_no_release_signs_nothing_and_reads_nothing(self):
        repo, head = custody(self.tmp, {"README": "x"})
        with patch.object(runner, "verified_source", return_value=[]), \
             patch.object(runner, "bind_admitted_metadata", return_value=[]), \
             patch.object(runner, "load_policy", return_value=POLICY), \
             patch("core.daily_sources.DailySource.collection_attempt") as read:
            result = runner.private_run(FAMILY + "," + str(repo) + "," + head, public_db=self.db,
                                        state_path=self.tmp / "q.json", out_dir=self.tmp / "out",
                                        no_release=True)
        read.assert_not_called()
        self.assertNotIn("collection", result)


class NoCadenceFamiliesStayV1(unittest.TestCase):
    def test_private_run_for_uscc_signs_v1_and_never_reads_custody(self):
        from tests import test_uscc_press_daily as u
        family = u.FAMILY
        self.assertFalse(SOURCES[family].signs_collection())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "public.db"
            build_legacy_db(db)
            migrate(db)
            repo, head = custody(root, {"README": "x"})
            p = d.load_policy()
            p["sources"][family].update(private_model_processing=True, public_machine_explanation=True,
                                        unattended_release=True,
                                        owner_decision="SYNTHETIC TEST ONLY; no owner authorization")
            with patch.object(runner, "verified_source", return_value=[]), \
                 patch.object(runner, "bind_admitted_metadata", return_value=[]), \
                 patch.object(runner, "load_policy", return_value=p), \
                 patch("core.daily_sources.DailySource.collection_attempt") as read, \
                 patch.dict(os.environ, {"DAILY_OUTPUT_KEY": KEY}):
                result = runner.private_run(family + "," + str(repo) + "," + head, public_db=db,
                                            state_path=root / "q.json", out_dir=root / "out")
            read.assert_not_called()
            self.assertNotIn("collection", result)
            envelope = json.loads((root / "out" / (family + ".json")).read_text())
            self.assertEqual(envelope["packet"]["schema"], d.SCHEMA_V1)
            self.assertNotIn("collection", envelope["packet"])


if __name__ == "__main__":
    unittest.main()
