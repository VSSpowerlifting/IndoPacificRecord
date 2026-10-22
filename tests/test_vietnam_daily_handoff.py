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
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import vietnam_corpus_bridge as bridge
from core import vietnam_daily_handoff as handoff
from core import vietnam_daily_qa as qa
from core import vietnam_official_link_admission as vn
from tests import test_vietnam_daily_pipeline as pipeline
from tests.test_vietnam_daily_pipeline import (ENERGY, KEY, MPS, NOW, PROMOTED,
                                               FakeAnalyzer, clone_schema, decision, grant)

BRIDGE_KEY = b"fictional-test-only-private-bridge-key-0000"
WITHHOLD = {"public_original_storage": False, "public_full_translation": False,
            "public_excerpt": False}


class Handoff(unittest.TestCase):
    setUp = pipeline.PrivateCustodyDaily.setUp
    custody = pipeline.PrivateCustodyDaily.custody
    run_private = pipeline.PrivateCustodyDaily.run_private
    originals = pipeline.PrivateCustodyDaily.originals

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
    def corpus(conn):
        arts = conn.execute("SELECT * FROM articles ORDER BY url").fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM articles").description]
        prov = conn.execute("SELECT * FROM vietnam_article_provenance"
                            " ORDER BY source_identity").fetchall()
        pcols = [d[0] for d in conn.execute(
            "SELECT * FROM vietnam_article_provenance").description]
        return ([{c: v for c, v in zip(cols, r) if c != "id"} for r in arts],
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
        self.assertEqual(self.corpus(public), self.corpus(self.conn))
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
        self.assertEqual(self.corpus(public), self.corpus(self.conn))

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

        before = hashlib.sha256(db.read_bytes()).hexdigest()
        code, out = run()  # live MPS still requires a sealed owner decision
        self.assertEqual((code, out["status"], out["reason"]),
                         (2, "HOLD", "source_use_decision_unsealed"))
        self.assertEqual(hashlib.sha256(db.read_bytes()).hexdigest(), before)
        with patch.object(handoff, "DECISIONS", self.decisions()), \
                patch.object(bridge, "desk_promoted", return_value=True):
            code, out = run()
            self.assertEqual((code, out["counts"]), (0, {qa.PUBLISHED: 2}))
            self.assertNotIn("summary_english", json.dumps(out))
            code, out = run()
            self.assertEqual((code, out["counts"]), (0, {bridge.DUPLICATE: 2}))
        with closing_ro(db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM articles").fetchone(), (2,))
        self.assertFalse(any(p.name.startswith(".vietnam-handoff-") for p in self.tmp.iterdir()))


def closing_ro(path):
    return contextlib.closing(sqlite3.connect("file:%s?mode=ro" % path, uri=True))


if __name__ == "__main__":
    unittest.main()
