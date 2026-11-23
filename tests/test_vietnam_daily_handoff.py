"""Vietnam Daily handoff: private bridge run -> signed articles -> public corpus.

SIMULATED and offline: the private side is the fixture private evidence
history of tests.test_vietnam_private_custody; both keys are fictional and
every sealed decision is a test fixture, not an owner decision.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pipeline as ipr_pipeline
from core import vietnam_corpus_bridge as bridge
from core import vietnam_daily_handoff as handoff
from core.collection import status as st
from core import vietnam_daily_qa as qa
from core import vietnam_official_link_admission as vn
from tests import test_vietnam_daily_pipeline as pipeline
from tests.test_vietnam_daily_pipeline import (ENERGY, KEY, MPS, NOW, PROMOTED,
                                               FakeAnalyzer, clone_schema, decision, grant)

BRIDGE_KEY = b"fictional-test-only-private-bridge-key-0000"
#: When the Daily pipeline reads the receipt: the same day the envelope was signed.
RECEIVED = datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc)
WITHHOLD = {"public_original_storage": False, "public_full_translation": False,
            "public_excerpt": False}


class Handoff(unittest.TestCase):
    setUp = pipeline.PrivateCustodyDaily.setUp
    custody = pipeline.PrivateCustodyDaily.custody
    run_private = pipeline.PrivateCustodyDaily.run_private
    originals = pipeline.PrivateCustodyDaily.originals

    def test_mps_source_hold_is_still_enforced_for_signed_projection(self):
        envelope=self.signed()
        with patch.dict(vn.HOLDS,{MPS:'synthetic explicit MPS hold'}):
            with self.assertRaisesRegex(handoff.HandoffError,'vietnam_handoff_source_hold'):
                self.verify(envelope)

    def decisions(self, **overrides):
        folder = self.tmp / "decisions"
        folder.mkdir(exist_ok=True)
        (folder / ("%s.json" % MPS)).write_text(json.dumps(decision(**overrides)))
        return folder

    def signed(self, **overrides):
        report, _ = self.run_private(source_use=grant(**overrides))
        ledger = json.loads(self.ledger.read_text())
        return handoff.sign([report], {MPS: ledger}, key=BRIDGE_KEY,
                            run_id="simulated-private-run", generated_utc=NOW)

    def test_analysis_headline_survives_signed_handoff_without_translation_rights(self):
        envelope = self.signed(permissions=WITHHOLD)
        records = self.verify(envelope, permissions=WITHHOLD)
        self.assertTrue(records)
        for family, record, row, provenance in records:
            self.assertEqual(row["title_english"], "Synthetic IPR factual headline")
            self.assertIsNone(row["text_original"])
            self.assertIsNone(row["text_english"])
            self.assertEqual(provenance["translation_published"], 0)
        tampered = self.resign(envelope, lambda body: body["families"][0]["records"][0]["row"].update(
            text_english="Unauthorized full translation"))
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_withheld_field"):
            self.verify(tampered, permissions=WITHHOLD)

    def test_mps_original_title_is_withheld_even_with_english_analysis(self):
        permissions = dict(WITHHOLD, public_title_display=False)
        envelope = self.signed(permissions=permissions)
        for _, _, row, _ in self.verify(envelope, permissions=permissions):
            self.assertIsNone(row["title_original"])
            self.assertTrue(row["title_english"])
        forged = self.resign(envelope, lambda body: body["families"][0]["records"][0][
            "row"].update(title_original="Synthetic withheld headline"))
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_withheld_field"):
            self.verify(forged, permissions=permissions)

    def public(self):
        conn = clone_schema(self.tmp / "public.db")
        self.addCleanup(conn.close)
        return conn

    def verify(self, envelope, desk=PROMOTED, decisions=None, **overrides):
        return handoff.verify(envelope, bridge_key=BRIDGE_KEY, review_key=KEY, as_of=NOW,
                              desk=desk, decisions=decisions or self.decisions(**overrides))

    def resign(self, envelope, edit):
        body = copy.deepcopy({k: v for k, v in envelope.items() if k != "mac"})
        edit(body)
        return dict(body, mac=handoff._mac(BRIDGE_KEY, body))

    @staticmethod
    def corpus(conn, *, shared_projection=False):
        arts = conn.execute("SELECT * FROM articles ORDER BY url").fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM articles").description]
        prov = conn.execute("SELECT * FROM vietnam_article_provenance"
                            " ORDER BY source_identity").fetchall()
        pcols = [d[0] for d in conn.execute(
            "SELECT * FROM vietnam_article_provenance").description]
        # scraped_at is SQLite's local insertion clock, not signed source
        # evidence. Compare it within one DB for idempotency, not across DBs.
        omitted = {"id", "scraped_at"} if shared_projection else {"id"}
        return ([{c: v for c, v in zip(cols, r) if c not in omitted} for r in arts],
                [{c: v for c, v in zip(pcols, r) if c != "article_id"} for r in prov])

    def test_round_trip_reproduces_the_private_projection_and_is_idempotent(self):
        envelope = self.signed()
        articles = [a for f in envelope["families"] for a in f["records"]]
        self.assertEqual(len(articles), 2)
        for article in articles:  # column drift between bridge and handoff
            self.assertEqual(set(article["row"]), bridge.ROW_COLUMNS)
            self.assertEqual(set(article["provenance"]), bridge.PROVENANCE_COLUMNS)
        public = self.public()
        records = self.verify(envelope)
        self.assertEqual(handoff.admit(public, records), {qa.PUBLISHED: 2})
        # Force different insertion clocks so a second boundary cannot make
        # this contract pass or fail by chance. Published source dates and all
        # signed provenance remain part of the exact comparison.
        self.conn.execute("UPDATE articles SET scraped_at=datetime(scraped_at, '-1 day')")
        self.assertNotEqual(public.execute("SELECT scraped_at FROM articles LIMIT 1").fetchone(),
                            self.conn.execute("SELECT scraped_at FROM articles LIMIT 1").fetchone())
        self.assertEqual(self.corpus(public, shared_projection=True),
                         self.corpus(self.conn, shared_projection=True))
        before = self.corpus(public)
        self.assertEqual(handoff.admit(public, self.verify(envelope)), {bridge.DUPLICATE: 2})
        self.assertEqual(self.corpus(public), before)

    def test_admitted_records_are_not_offered_again_and_unadmitted_ones_are(self):
        first = self.signed()
        # Next private run on a fresh copy of public main that lacks the records:
        # the ledger offers the stored projection again, without a model call.
        self.conn.close()
        self.conn = clone_schema(self.tmp / "fresh.db")
        self.addCleanup(self.conn.close)
        report, analyzer = self.run_private(source_use=grant())
        self.assertEqual(analyzer.calls, [])
        self.assertEqual([o["outcome"] for o in report["outcomes"]], [qa.PUBLISHED] * 2)
        again = handoff.sign([report], {MPS: json.loads(self.ledger.read_text())},
                             key=BRIDGE_KEY, run_id="r2", generated_utc=NOW)
        self.assertEqual(again["families"][0]["records"], first["families"][0]["records"])

    def test_delayed_handoff_after_private_archive_tip_advances(self):
        # SIMULATED: an earlier run processed two records, but public Daily
        # has not admitted them before the private archive receives new captures.
        report, _ = self.run_private(source_use=grant())
        earlier_tip = report["source_git_commit"]
        later_tip = "f" * 40 if earlier_tip != "f" * 40 else "e" * 40
        ledger = json.loads(self.ledger.read_text())
        envelope = handoff.sign(
            [dict(report, source_git_commit=later_tip)], {MPS: ledger},
            key=BRIDGE_KEY, run_id="simulated-delayed-handoff", generated_utc=NOW)
        entry = envelope["families"][0]
        self.assertEqual(entry["source_git_commit"], later_tip)
        self.assertEqual(len(entry["records"]), 2)
        self.assertTrue(all(r["provenance"]["source_git_commit"] == earlier_tip
                            for r in entry["records"]))

        public = self.public()
        self.assertEqual(handoff.admit(public, self.verify(envelope)), {qa.PUBLISHED: 2})
        # Delay necessarily permits distinct local insertion clocks; signed
        # dates/provenance must still match exactly, as in the round-trip case.
        self.conn.execute("UPDATE articles SET scraped_at=datetime(scraped_at, '-1 day')")
        self.assertNotEqual(public.execute("SELECT scraped_at FROM articles LIMIT 1").fetchone(),
                            self.conn.execute("SELECT scraped_at FROM articles LIMIT 1").fetchone())
        self.assertEqual(self.corpus(public, shared_projection=True),
                         self.corpus(self.conn, shared_projection=True))

        # Even a valid MAC must not turn a malformed historical commit into
        # acceptable provenance.
        def bad_evidence_commit(body):
            body["families"][0]["records"][0]["provenance"]["source_git_commit"] = "not-a-sha"

        with self.assertRaisesRegex(RuntimeError, "vietnam_handoff_provenance_mismatch"):
            self.verify(self.resign(envelope, bad_evidence_commit))

    def test_withheld_fields_never_cross(self):
        envelope = self.signed(permissions=WITHHOLD)
        text = json.dumps(envelope, ensure_ascii=False)
        for version in self.originals():
            for para in version["text_original"].split("\n\n"):
                if len(para.strip()) > 20:
                    self.assertNotIn(para.strip(), text)
        for article in envelope["families"][0]["records"]:
            self.assertIsNone(article["row"]["text_original"])
            self.assertIsNone(article["row"]["text_english"])

        def text_original(body):
            article = body["families"][0]["records"][0]
            article["row"]["text_original"] = "withheld original"
            article["provenance"]["original_withheld"] = 0

        with self.assertRaisesRegex(RuntimeError, "vietnam_handoff_withheld_field"):
            self.verify(self.resign(envelope, text_original), permissions=WITHHOLD)
        public = self.public()
        handoff.admit(public, self.verify(envelope, permissions=WITHHOLD))
        self.assertEqual(public.execute("SELECT COUNT(*) FROM articles WHERE text_original"
                                        " IS NOT NULL OR text_english IS NOT NULL").fetchone(),
                         (0,))

    def test_refusals_write_nothing(self):
        envelope = self.signed()
        records = envelope["families"][0]["records"]

        def permissions(body):
            prov = body["families"][0]["records"][0]["provenance"]
            prov["permissions_json"] = prov["permissions_json"].replace("true", "false", 1)

        def moit(body):
            body["families"].append({
                "source_family": ENERGY, "source_ref": vn.private_ref(ENERGY),
                "source_git_commit": body["families"][0]["source_git_commit"],
                "rights_decision_sha256": body["families"][0]["rights_decision_sha256"],
                "records": [records[0]]})

        def extra_column(body):
            body["families"][0]["records"][0]["row"]["url"] = "https://example.invalid/"

        tampered = copy.deepcopy(envelope)
        tampered["families"][0]["records"][0]["row"]["summary_english"] = "changed"
        cases = {
            "vietnam_handoff_mac_invalid": (tampered, {}),
            "vietnam_handoff_permissions_mismatch": (self.resign(envelope, permissions), {}),
            "vietnam_handoff_source_hold": (self.resign(envelope, moit), {}),
            "vietnam_handoff_record_columns": (self.resign(envelope, extra_column), {}),
            "vietnam_desk_not_promoted": (envelope, {"desk": SimpleNamespace(
                is_collecting=True, has_production_records=False)}),
            "vietnam_source_use_decision_absent": (envelope, {"decisions": self.tmp / "none"}),
        }
        # A decision withholding originals no longer matches a grant-all handoff.
        cases["vietnam_handoff_decision_mismatch"] = (envelope, {"permissions": WITHHOLD})
        for code, (env, kw) in cases.items():
            with self.subTest(code):
                with self.assertRaisesRegex((ValueError, RuntimeError), code):
                    self.verify(env, **kw)
        with self.assertRaisesRegex(RuntimeError, "must_differ"):
            handoff.verify(envelope, bridge_key=BRIDGE_KEY, review_key=BRIDGE_KEY, as_of=NOW,
                           desk=PROMOTED, decisions=self.decisions())

    def test_empty_and_held_families_need_no_decision_or_promotion(self):
        report, _ = self.run_private()  # standing policy: held for rights
        # A MOIT family under its consent/robots hold reports no outcomes.
        held = dict(report, source_family=ENERGY, outcomes=[],
                    custody=dict(report["custody"], source_ref=vn.private_ref(ENERGY)))
        envelope = handoff.sign([report, held], {MPS: json.loads(self.ledger.read_text()),
                                                 ENERGY: {"items": {}}},
                                key=BRIDGE_KEY, run_id="r", generated_utc=NOW)
        self.assertEqual([f["records"] for f in envelope["families"]], [[], []])
        self.assertEqual(self.verify(envelope, desk=None, decisions=self.tmp / "none"), [])

    def test_verify_accepts_old_and_new_family_entries_and_never_refuses_on_the_block(self):
        from tests.test_collection_attempts import facts
        good = facts(family=MPS)
        for label, block in (("valid", good), ("malformed", {"schema": "junk"}),
                             ("leaky", dict(good, error_detail="x")), ("null", None),
                             ("wrong custody", dict(good, custody_commit="0" * 40))):
            with self.subTest(label):
                report, _ = self.run_private(source_use=grant())
                ledger = json.loads(self.ledger.read_text())
                envelope = handoff.sign([report], {MPS: ledger}, key=BRIDGE_KEY,
                                        run_id="simulated-private-run", generated_utc=NOW)
                old = self.verify(envelope)
                self.assertEqual(handoff.collection_by_family(envelope), {MPS: None})
                for entry in envelope["families"]:
                    entry["collection"] = (dict(block, custody_commit=entry["source_git_commit"])
                                           if label in ("valid", "leaky") else block)
                body = {k: v for k, v in envelope.items() if k != "mac"}
                envelope["mac"] = handoff._mac(BRIDGE_KEY, body)
                self.assertEqual(self.verify(envelope), old)
                invalid = {"attested": False, "reason": "collection_attestation_invalid"}
                expected = {MPS: {"valid": envelope["families"][0]["collection"],
                                  "null": None}.get(label, invalid)}
                self.assertEqual(handoff.collection_by_family(envelope), expected)
        # A family-mismatched block is a defect too, not an absent block.
        report, _ = self.run_private(source_use=grant())
        envelope = handoff.sign([report], {MPS: json.loads(self.ledger.read_text())},
                                key=BRIDGE_KEY, run_id="simulated-private-run",
                                generated_utc=NOW)
        for entry in envelope["families"]:
            entry["collection"] = facts(family="vn_vpcp_official_documents_vi")
        envelope["mac"] = handoff._mac(BRIDGE_KEY, {k: v for k, v in envelope.items()
                                                    if k != "mac"})
        self.verify(envelope)
        self.assertEqual(handoff.collection_by_family(envelope),
                         {MPS: {"attested": False, "reason": "collection_attestation_invalid"}})

    def test_sign_authenticates_a_failed_sibling_without_changing_accepted_records(self):
        from tests.test_collection_attempts import facts
        vpcp = handoff.source_use.VPCP
        report, _ = self.run_private(source_use=grant())
        ledgers = {MPS: json.loads(self.ledger.read_text())}
        fields = dict(key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW)
        previous = handoff.sign([report], ledgers, **fields)
        mps = dict(facts(family=MPS), custody_commit=report["source_git_commit"])
        vpcp_facts = facts(family=vpcp)
        envelope = handoff.sign([report], ledgers, **fields,
                                collection={MPS: mps, vpcp: vpcp_facts},
                                failed_families={vpcp: (vpcp_facts["custody_commit"], "held_source")})
        records = self.verify(envelope)
        self.assertEqual(records, self.verify(previous))
        self.assertEqual(handoff.collection_by_family(envelope), {MPS: mps, vpcp: vpcp_facts})
        failed = envelope["families"][1]
        self.assertEqual((failed["bridge_status"], failed["records"]), ("held_source", []))
        public = self.public()
        self.assertEqual(handoff.admit(public, records), {qa.PUBLISHED: 2})
        self.assertEqual(handoff.admit(public, self.verify(envelope)), {bridge.DUPLICATE: 2})
        failed["bridge_status"] = "bridge_failed"
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_mac_invalid"):
            self.verify(envelope)
        forged = self.resign(envelope, lambda body: body["families"][1]["records"].append({}))
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_bridge_status_invalid"):
            self.verify(forged)

    def test_failed_collection_withholds_projection_without_changing_private_ledger(self):
        from tests.test_collection_attempts import facts, latest

        report, _ = self.run_private(source_use=grant())
        ledger_before = self.ledger.read_bytes()
        ledgers = {MPS: json.loads(ledger_before)}
        fields = dict(key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW)
        good = facts(family=MPS, custody_commit=report["source_git_commit"])
        failed = dict(good, latest=latest(result=st.FETCH_FAILURE, health="fail", healthy=False))

        envelope = handoff.sign([report], ledgers, **fields, collection={MPS: failed})
        self.assertEqual(envelope["families"][0]["records"], [])
        self.assertEqual(self.verify(envelope), [])
        self.assertEqual(handoff.collection_by_family(envelope), {MPS: failed})
        self.assertEqual(ledgers[MPS], json.loads(ledger_before))
        self.assertEqual(self.ledger.read_bytes(), ledger_before)

        recover = handoff.sign([report], ledgers, **fields, collection={MPS: good})
        records = self.verify(recover)
        public = self.public()
        self.assertEqual(handoff.admit(public, records), {qa.PUBLISHED: 2})
        self.assertEqual(handoff.admit(public, records), {bridge.DUPLICATE: 2})
        conflicting = self.resign(recover, lambda body: body["families"][0].update(collection=failed))
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_collection_failure_has_records"):
            self.verify(conflicting)

    # -- dispositions: signed counts of this run's bridge outcomes ----------

    #: SIMULATED: the 22 November shape (4 held for review, 3 screened out,
    #: 6 already in the corpus) plus one settled item; identities are synthetic.
    MIXED = ([qa.HELD_REVIEW] * 4 + [qa.SCREENED_OUT] * 3 + [bridge.DUPLICATE] * 6
             + [bridge.SETTLED])

    def mixed(self, report, published=True):
        kept = [o for o in report["outcomes"] if published and o["outcome"] == qa.PUBLISHED]
        extra = [{"source_identity": "synthetic-identity-%02d" % i, "content_sha256": "0" * 64,
                  "outcome": outcome, "failures": [], "article_id": None}
                 for i, outcome in enumerate(self.MIXED)]
        return dict(report, outcomes=kept + extra)

    @patch.object(handoff, "SIGN_DISPOSITIONS", True)
    def test_sign_counts_every_disposition_but_carries_only_published_records(self):
        report, _ = self.run_private(source_use=grant())
        ledgers = {MPS: json.loads(self.ledger.read_text())}
        fields = dict(key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW)
        plain = handoff.sign([report], ledgers, **fields)
        envelope = handoff.sign([self.mixed(report)], ledgers, **fields)
        entry = envelope["families"][0]
        self.assertEqual(entry["dispositions"], {
            qa.PUBLISHED: 2, qa.HELD_REVIEW: 4, qa.SCREENED_OUT: 3, bridge.DUPLICATE: 6,
            bridge.SETTLED: 1})
        self.assertEqual(entry["records"], plain["families"][0]["records"])
        self.assertEqual(plain["families"][0]["dispositions"], {qa.PUBLISHED: 2})
        self.assertNotIn("synthetic-identity", json.dumps(envelope))
        # Deterministic: the same run signs the same bytes.
        self.assertEqual(envelope, handoff.sign([self.mixed(report)], ledgers, **fields))
        self.assertEqual(self.verify(envelope), self.verify(plain))
        self.assertEqual(handoff.dispositions_by_family(envelope), {MPS: entry["dispositions"]})
        # The MAC covers the block: a changed count is refused, not read.
        envelope["families"][0]["dispositions"][qa.HELD_REVIEW] = 0
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_mac_invalid"):
            self.verify(envelope)

    @patch.object(handoff, "SIGN_DISPOSITIONS", True)
    def test_failed_and_quiet_families_dispositions(self):
        from tests.test_collection_attempts import facts
        vpcp = handoff.source_use.VPCP
        report, _ = self.run_private(source_use=grant())
        vpcp_facts = facts(family=vpcp)
        quiet = dict(report, source_family=ENERGY, outcomes=[],
                     custody=dict(report["custody"], source_ref=vn.private_ref(ENERGY)))
        envelope = handoff.sign(
            [report, quiet], {MPS: json.loads(self.ledger.read_text()), ENERGY: {"items": {}}},
            key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW,
            collection={vpcp: vpcp_facts},
            failed_families={vpcp: (vpcp_facts["custody_commit"], "held_source")})
        by_family = {e["source_family"]: e for e in envelope["families"]}
        self.assertNotIn("dispositions", by_family[vpcp])  # its bridge reported nothing
        self.assertEqual(by_family[ENERGY]["dispositions"], {})
        self.verify(envelope)
        self.assertEqual(handoff.dispositions_by_family(envelope),
                         {MPS: {qa.PUBLISHED: 2}, ENERGY: {}, vpcp: None})

    def test_dispositions_count_toward_the_size_bound(self):
        report, _ = self.run_private(source_use=grant())
        ledgers = {MPS: json.loads(self.ledger.read_text())}
        mixed = self.mixed(report)
        items = ledgers[MPS]["items"]
        articles = sum(len(handoff._canonical(items[o["source_identity"]]["article"]))
                       for o in mixed["outcomes"] if o["outcome"] == qa.PUBLISHED)
        block = len(handoff._canonical({"dispositions": handoff._dispositions(mixed["outcomes"])}))
        # Off (the default), an unsigned block costs nothing, so no record waits for it.
        for emit, exact in ((True, 2048 + block + articles), (False, 2048 + articles)):
            for bound, deferred in ((exact, 0), (exact - 1, 1)):
                with self.subTest(emit=emit, bound=bound), \
                        patch.object(handoff, "SIGN_DISPOSITIONS", emit), \
                        patch.object(handoff, "MAX_BYTES", bound):
                    envelope = handoff.sign([mixed], ledgers, key=BRIDGE_KEY, run_id="r",
                                            generated_utc=NOW)
                    self.assertEqual(
                        (envelope["deferred"], len(envelope["families"][0]["records"])),
                        (deferred, 2 - deferred))

    def test_legacy_envelope_without_dispositions_verifies_unchanged(self):
        report, _ = self.run_private(source_use=grant())
        ledgers = {MPS: json.loads(self.ledger.read_text())}
        fields = dict(key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW)
        old = handoff.sign([report], ledgers, **fields)  # the default signs the legacy shape
        self.assertNotIn("dispositions", old["families"][0])
        with patch.object(handoff, "SIGN_DISPOSITIONS", True):
            envelope = handoff.sign([report], ledgers, **fields)
        self.assertIn("dispositions", envelope["families"][0])
        self.assertEqual(self.verify(old), self.verify(envelope))
        self.assertEqual(handoff.dispositions_by_family(old), {MPS: None})

    def test_default_signer_stays_readable_by_the_previous_verifier(self):
        """Reader first: until SIGN_DISPOSITIONS is flipped, every family entry
        meets the exact family-key check of the verifier before this change, so a
        Daily re-run at an older SHA, or a revert, still reads the handoff."""
        from tests.test_collection_attempts import facts
        vpcp = handoff.source_use.VPCP
        report, _ = self.run_private(source_use=grant())
        quiet = dict(report, source_family=ENERGY, outcomes=[],
                     custody=dict(report["custody"], source_ref=vn.private_ref(ENERGY)))
        vpcp_facts = facts(family=vpcp)
        envelope = handoff.sign(
            [self.mixed(report), quiet],
            {MPS: json.loads(self.ledger.read_text()), ENERGY: {"items": {}}},
            key=BRIDGE_KEY, run_id="simulated-private-run", generated_utc=NOW,
            collection={vpcp: vpcp_facts},
            failed_families={vpcp: (vpcp_facts["custody_commit"], "held_source")})
        self.assertFalse(handoff.SIGN_DISPOSITIONS)
        self.assertEqual(len(envelope["families"]), 3)
        for entry in envelope["families"]:
            with self.subTest(family=entry["source_family"]):
                self.assertEqual(set(entry) - {"collection", "bridge_status"},
                                 handoff._FAMILY_KEYS)
        self.verify(envelope)
        self.assertEqual(handoff.dispositions_by_family(envelope),
                         {MPS: None, ENERGY: None, vpcp: None})

    def test_malformed_dispositions_are_reported_invalid_and_never_refuse(self):
        envelope = self.signed()
        expected = self.verify(envelope)
        for label, block in (("bool", {qa.HELD_REVIEW: True}), ("negative", {qa.HELD_REVIEW: -1}),
                             ("float", {qa.HELD_REVIEW: 1.0}), ("text", {qa.HELD_REVIEW: "4"}),
                             ("unknown code", {"held_unknown": 1}),
                             ("reason", {"E_ACRONYM": 2}), ("unbounded", {qa.HELD_REVIEW: 10 ** 9}),
                             ("list", [qa.HELD_REVIEW]), ("null", None), ("string", "4 held")):
            with self.subTest(label):
                bad = self.resign(envelope, lambda body: body["families"][0].update(
                    dispositions=block))
                self.assertEqual(self.verify(bad), expected)
                self.assertEqual(handoff.dispositions_by_family(bad),
                                 {MPS: handoff.DISPOSITIONS_INVALID})

    def test_disposition_codes_are_the_bridge_outcomes(self):
        self.assertEqual(set(handoff.DISPOSITIONS), {
            qa.PUBLISHED, qa.SCREENED_OUT, qa.HELD_RETRYABLE, qa.HELD_REVIEW, qa.HELD_RIGHTS,
            qa.HELD_SOURCE, qa.HELD_ESCALATED, bridge.DUPLICATE, bridge.SETTLED})
        self.assertEqual(set(qa.CODES.values()) - set(handoff.DISPOSITIONS), set())

    def test_verify_still_refuses_unknown_family_entry_keys(self):
        envelope = self.signed()
        envelope["families"][0]["extra"] = 1
        envelope["mac"] = handoff._mac(BRIDGE_KEY, {k: v for k, v in envelope.items() if k != "mac"})
        with self.assertRaisesRegex(handoff.HandoffError, "vietnam_handoff_family_invalid"):
            self.verify(envelope)

    def test_command_admits_into_a_copy_and_holds_without_touching_the_database(self):
        envelope = self.signed()
        path = self.tmp / "handoff.json"
        path.write_text(json.dumps(envelope))
        public = self.public()
        public.close()
        db = self.tmp / "public.db"
        env = {"VIETNAM_PRIVATE_BRIDGE_KEY": BRIDGE_KEY.decode(),
               "VIETNAM_SOURCE_USE_REVIEW_KEY": KEY.decode()}

        def run():
            out = io.StringIO()
            with patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                code = handoff.main(["--database", str(db), "--handoff", str(path)])
            return code, json.loads(out.getvalue())

        def reported(out):
            # The printed receipt is exactly what the Daily pipeline reports.
            receipt = self.tmp / "receipt.json"
            receipt.write_text(json.dumps(out))
            with patch.dict(os.environ, {"IPR_VIETNAM_HANDOFF_RECEIPT": str(receipt)}):
                return ipr_pipeline._vn_handoff_outcome(MPS, RECEIVED)

        before = hashlib.sha256(db.read_bytes()).hexdigest()
        code, out = run()  # live MPS still requires a sealed owner decision
        self.assertEqual((code, out["status"], out["reason"]),
                         (2, "HOLD", "source_use_decision_unsealed"))
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)
        self.assertEqual(reported(out), ipr_pipeline.GovernedOutcome(
            st.ADAPTER_ERROR, error_detail="vietnam_daily_handoff: source_use_decision_unsealed"))
        with patch.object(handoff, "DECISIONS", self.decisions()), \
                patch.object(bridge, "desk_promoted", return_value=True):
            code, out = run()
            self.assertEqual((code, out["counts"]), (0, {qa.PUBLISHED: 2}))
            self.assertEqual(out["by_family"], {MPS: {qa.PUBLISHED: 2}})
            self.assertEqual(out["collection_by_family"], {MPS: None})
            # The default signer carries no block, so the row is exactly as before.
            self.assertEqual(out["dispositions_by_family"], {MPS: None})
            self.assertEqual(out["generated_utc"], NOW)
            self.assertNotIn("summary_english", json.dumps(out))
            self.assertEqual(reported(out), ipr_pipeline.GovernedOutcome(st.OK, 2, 0))
            code, out = run()
            self.assertEqual((code, out["counts"]), (0, {bridge.DUPLICATE: 2}))
            self.assertEqual(out["by_family"], {MPS: {bridge.DUPLICATE: 2}})
            self.assertEqual(reported(out),
                             ipr_pipeline.GovernedOutcome(st.OK_ALL_DUPLICATES, 0, 2))
        with closing_ro(db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM articles").fetchone(), (2,))
        self.assertFalse(any(p.name.startswith(".vietnam-handoff-") for p in self.tmp.iterdir()))

    @patch.object(handoff, "SIGN_DISPOSITIONS", True)
    def test_command_reports_a_run_with_nothing_published_but_holds_and_duplicates(self):
        """SIMULATED 22 November shape: no published record crosses, yet the
        row reports what the private bridge held, screened and found unchanged."""
        report, _ = self.run_private(source_use=grant())
        envelope = handoff.sign([self.mixed(report, published=False)],
                                {MPS: json.loads(self.ledger.read_text())}, key=BRIDGE_KEY,
                                run_id="simulated-private-run", generated_utc=NOW)
        self.assertEqual(envelope["families"][0]["records"], [])
        path = self.tmp / "handoff.json"
        path.write_text(json.dumps(envelope))
        public = self.public()
        public.close()
        db = self.tmp / "public.db"
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        out = io.StringIO()
        with patch.dict(os.environ, {"VIETNAM_PRIVATE_BRIDGE_KEY": BRIDGE_KEY.decode(),
                                     "VIETNAM_SOURCE_USE_REVIEW_KEY": KEY.decode()}), \
                contextlib.redirect_stdout(out):
            self.assertEqual(handoff.main(["--database", str(db), "--handoff", str(path)]), 0)
        printed = json.loads(out.getvalue())
        self.assertEqual(printed["by_family"], {MPS: {}})
        self.assertEqual(printed["dispositions_by_family"], {MPS: {
            qa.HELD_REVIEW: 4, qa.SCREENED_OUT: 3, bridge.DUPLICATE: 6, bridge.SETTLED: 1}})
        self.assertNotIn("synthetic-identity", out.getvalue())
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)
        receipt = self.tmp / "receipt.json"
        receipt.write_text(out.getvalue())
        with patch.dict(os.environ, {"IPR_VIETNAM_HANDOFF_RECEIPT": str(receipt)}):
            self.assertEqual(ipr_pipeline._vn_handoff_outcome(MPS, RECEIVED),
                             ipr_pipeline.GovernedOutcome(
                                 st.OK_NO_PUBLICATIONS, 0, 0,
                                 "private bridge: 4 held_review, 3 screened_out, "
                                 "1 settled, 6 duplicate"))


def closing_ro(path):
    return contextlib.closing(sqlite3.connect("file:%s?mode=ro" % path, uri=True))


if __name__ == "__main__":
    unittest.main()
