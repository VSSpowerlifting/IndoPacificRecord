"""Singapore MINDEF recurrence: signed parent links and the end of the pilot.

Synthetic offline contracts only. Custody is a throw-away git repository with
placeholder English bodies, the model is a fake, and no MINDEF text, media or
capture is used. Nothing here spends money or touches a production database.
"""
import copy
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import daily_sources
from core import singapore_mindef_links as links
from scripts import singapore_mindef_links as links_cli
from processing import daily_intake as d
from processing import daily_runner
from scripts import fetch_daily_machine_outputs as fetch
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate
from tests.test_singapore_daily_completion import (
    BODY, DAY, FAMILY, IDENT, ROOT, TITLE, analyzer, build_custody, policy)

KEY = "synthetic-singapore-key-" * 2
SECOND = "synthetic-release-two"
HELD = links.HELD_IDENTITIES[0]
ROWS = [(IDENT, TITLE, BODY, DAY), (SECOND, TITLE + " two", BODY + "\n\nMore.", "2026-10-29"),
        (HELD, "Held synthetic", BODY, "2026-08-15")]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "scratch.db"
        build_legacy_db(self.db)
        migrate(self.db)
        self.repo, self.head = build_custody(self.tmp, ROWS)
        self.records = links.with_title_hash(d.verified_source(self.repo, self.head, FAMILY))
        self.envelope = links.sign_links(self.records, key=KEY)

    def connect(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(conn.close)
        return conn

    def parents(self):
        return [r[0] for r in self.connect().execute(
            "SELECT source_identity FROM singapore_mindef_source_records ORDER BY 1")]


class SignedParentLinks(Base):
    def test_envelope_carries_link_scope_only_and_never_a_held_identity(self):
        sent = self.envelope["packet"]["links"]
        self.assertEqual([l["source_identity"] for l in sent], sorted([IDENT, SECOND]))
        for link in sent:
            self.assertEqual(set(link), set(links.LINK_FIELDS))
        text = json.dumps(self.envelope)
        for private in (TITLE, BODY.split("\n")[0], HELD):
            self.assertNotIn(private, text)

    def test_admission_is_idempotent_and_binds_the_private_records(self):
        with self.connect() as conn:
            first = links.admit_signed_links(conn, self.envelope, key=KEY)
            again = links.admit_signed_links(conn, self.envelope, key=KEY)
        self.assertEqual(sorted(first["admitted"]), sorted([IDENT, SECOND]))
        self.assertEqual((again["admitted"], sorted(again["unchanged"])),
                         ([], sorted([IDENT, SECOND])))
        self.assertEqual(self.parents(), sorted([IDENT, SECOND]))
        bound = d.bind_admitted_metadata(self.records, self.connect(), source_repo=self.repo)
        self.assertEqual(sorted(r["source_identity"] for r in bound), sorted([IDENT, SECOND]))

    def test_tampering_wrong_key_or_other_domain_admits_nothing(self):
        tampered = copy.deepcopy(self.envelope)
        tampered["packet"]["links"][0]["publisher_posted_date"] = "2026-10-30"
        extra = copy.deepcopy(self.envelope)
        extra["packet"]["note"] = "x"
        # A machine-output MAC over the same bytes must not authenticate links.
        import hashlib
        import hmac
        cross = copy.deepcopy(self.envelope)
        cross["mac"] = hmac.new(KEY.encode(), d.DOMAIN + links._canonical(cross["packet"]),
                                hashlib.sha256).hexdigest()
        cases = ((tampered, KEY, "singapore_link_envelope_mac_invalid"),
                 (extra, KEY, "singapore_link_envelope_mac_invalid"),
                 (cross, KEY, "singapore_link_envelope_mac_invalid"),
                 (self.envelope, "another-synthetic-key-" * 2, "singapore_link_envelope_mac_invalid"),
                 (self.envelope, "short", "singapore_link_key_invalid"),
                 ({"packet": [], "mac": "x"}, KEY, "singapore_link_envelope_invalid"))
        for envelope, key, reason in cases:
            with self.subTest(reason=reason), self.connect() as conn:
                with self.assertRaisesRegex(links.LinkRefused, reason):
                    links.admit_signed_links(conn, envelope, key=key)
        self.assertEqual(self.parents(), [])

    def test_a_validly_signed_packet_is_still_rechecked_link_by_link(self):
        packet = copy.deepcopy(self.envelope["packet"])
        packet["links"][0]["canonical_official_url"] = "https://example.invalid/x/"
        held = dict(packet["links"][1], source_identity=HELD,
                    canonical_official_url=links.canonical_url(HELD))
        packet["links"].append(held)
        envelope = {"packet": packet, "mac": links._mac(KEY, links._canonical(packet))}
        with self.connect() as conn:
            summary = links.admit_signed_links(conn, envelope, key=KEY)
        self.assertEqual(len(summary["admitted"]), 1)
        self.assertEqual(sorted(summary["refused"].values()),
                         ["singapore_link_identity_held", "singapore_link_url_not_canonical"])
        self.assertNotIn(HELD, self.parents())

    def test_signing_refuses_a_record_public_admission_would_refuse(self):
        bad = [dict(self.records[0], canonical_official_url="https://example.invalid/x/")]
        with self.assertRaisesRegex(links.LinkRefused, "singapore_link_url_not_canonical"):
            links.sign_links(bad, key=KEY)
        with self.assertRaisesRegex(links.LinkRefused, "singapore_link_key_invalid"):
            links.sign_links(self.records, key="short")


class CommandLine(Base):
    def run_cli(self, *argv, key=KEY):
        import contextlib
        import io
        out = io.StringIO()
        with patch.dict(os.environ, {links.KEY_ENV: key}), contextlib.redirect_stdout(out):
            code = links_cli.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_sign_then_admit_round_trip_prints_counts_only(self):
        path = self.tmp / "links.json"
        code, receipt = self.run_cli("sign", "--source-checkout", str(self.repo),
                                     "--source-commit", self.head, "--output", str(path))
        self.assertEqual((code, receipt), (0, {"status": "ok", "signed_links": 2}))
        code, receipt = self.run_cli("admit", "--database", str(self.db), "--envelope", str(path))
        self.assertEqual((code, receipt["status"], receipt["admitted"]), (0, "ok", 2))
        self.assertEqual(self.parents(), sorted([IDENT, SECOND]))

    def test_missing_envelope_is_a_clean_no_op_and_a_bad_one_is_held(self):
        code, receipt = self.run_cli("admit", "--database", str(self.db),
                                     "--envelope", str(self.tmp / "absent.json"))
        self.assertEqual((code, receipt), (0, {"status": "no_link_envelope_delivered"}))
        path = self.tmp / "links.json"
        path.write_text(json.dumps(self.envelope))
        code, receipt = self.run_cli("admit", "--database", str(self.db),
                                     "--envelope", str(path), key="another-synthetic-key-" * 2)
        self.assertEqual((code, receipt), (1, {"status": "held",
                                               "reason": "singapore_link_envelope_mac_invalid"}))
        path.write_text("{not json")
        code, receipt = self.run_cli("admit", "--database", str(self.db), "--envelope", str(path))
        self.assertEqual((code, receipt["reason"]), (1, "singapore_link_envelope_invalid"))
        self.assertEqual(self.parents(), [])


class FetchLinkEnvelope(unittest.TestCase):
    def run_fetch(self, enabled):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / fetch.LINKS_NAME
            stale.write_text("{}")
            env = {"IPR_PRIVATE_DAILY_ENABLED": "true", "IPR_DAILY_INTAKE_DIR": tmp}
            if enabled:
                env["SG_MINDEF_LINKS_ENABLED"] = "true"
            done = subprocess.CompletedProcess([], 0, stdout=b'{"packet":{},"mac":"m"}')
            with patch.dict(os.environ, env, clear=False), \
                 patch.object(fetch, "load_policy", return_value=policy(False)), \
                 patch.object(fetch.subprocess, "run", return_value=done) as run:
                if not enabled:
                    os.environ.pop("SG_MINDEF_LINKS_ENABLED", None)
                result = fetch.main()
            calls = [" ".join(c.args[0]) for c in run.call_args_list]
            return result, stale.exists(), [c for c in calls if "links" in c]

    def test_links_are_fetched_only_under_their_own_switch(self):
        result, exists, calls = self.run_fetch(False)
        self.assertNotIn(fetch.LINKS_NAME, result)
        self.assertFalse(exists, "a stale link envelope must not survive a disabled run")
        self.assertEqual(calls, [])
        result, exists, calls = self.run_fetch(True)
        self.assertEqual(result[fetch.LINKS_NAME], "fetched")
        self.assertTrue(exists)
        self.assertEqual(len(calls), 1)
        self.assertIn("contents/sg_mindef_releases.links.json?ref=state/singapore-mindef-links",
                      calls[0])

    def test_daily_workflow_gates_fetch_and_admission_on_the_owner_switch(self):
        text = (ROOT / ".github/workflows/daily_update.yml").read_text()
        step = text.split("- name: Admit Singapore MINDEF official-link parents", 1)[1]
        step = step.split("\n      - name:", 1)[0]
        for required in ("vars.SG_MINDEF_LINKS_ENABLED == 'true'",
                         "vars.IPR_PRIVATE_DAILY_ENABLED == 'true'", "continue-on-error: true",
                         "secrets.DAILY_SG_MINDEF_RELEASES_KEY",
                         "python scripts/singapore_mindef_links.py admit --database pla_watch.db"):
            self.assertIn(required, step)
        self.assertLess(text.index("python -m scripts.fetch_daily_machine_outputs"),
                        text.index("- name: Admit Singapore MINDEF official-link parents"))
        self.assertLess(text.index("- name: Admit Singapore MINDEF official-link parents"),
                        text.index("      - name: Run pipeline\n"))


class PilotLimitsFollowTheGate(Base):
    """The one-item limits key on the pilot gate, not on the family name."""

    def setUp(self):
        super().setUp()
        with self.connect() as conn:
            links.admit_signed_links(conn, self.envelope, key=KEY)
        self.p = policy()
        self.state_path = self.tmp / "private" / "queues" / (FAMILY + ".json")
        self.out = self.tmp / "private" / "envelopes"

    def private_run(self, **kwargs):
        spec = ",".join((FAMILY, str(self.repo), self.head))
        with patch.object(daily_runner, "load_policy", return_value=self.p), \
             patch.object(d, "load_policy", return_value=self.p), \
             patch.object(d, "build_analyzer", side_effect=lambda *a, **k: analyzer()(), create=True), \
             patch.dict(os.environ, {"DAILY_OUTPUT_KEY": KEY}):
            return daily_runner.private_run(spec, public_db=self.db, state_path=self.state_path,
                                            out_dir=self.out, **kwargs)

    def test_while_the_pilot_is_open_an_unselected_run_is_refused_before_custody(self):
        self.assertTrue(daily_sources.attended_only(FAMILY))
        with patch.object(daily_runner, "verified_source") as custody:
            with self.assertRaisesRegex(d.IntakeHold, "daily_singapore_pilot_identity_required"):
                self.private_run()
        custody.assert_not_called()
        self.assertFalse(self.state_path.exists())

    def test_other_families_are_never_treated_as_a_pilot(self):
        for family in daily_sources.SOURCES:
            self.assertEqual(daily_sources.attended_only(family), family == FAMILY)

    def test_once_the_pilot_ends_admission_accepts_more_than_one_record(self):
        bound = d.bind_admitted_metadata(self.records, self.connect(), source_repo=self.repo)
        bound = [r for r in bound if r["source_identity"] != HELD]
        policy_two = copy.deepcopy(self.p)
        policy_two["sources"][FAMILY]["max_records_per_run"] = 2
        state, _ = d.process(bound, {}, family=FAMILY, policy=policy_two,
                             analyzer_factory=analyzer)
        self.assertEqual(sorted(v["status"] for v in state.values()), ["complete", "complete"])
        envelope = d.sign_outputs(state, family=FAMILY, policy=policy_two, key=KEY)
        self.assertEqual(len(envelope["packet"]["records"]), 2)
        with self.connect() as conn:
            with self.assertRaisesRegex(d.IntakeHold, "daily_singapore_pilot_envelope_exceeds_one"):
                d.admit(conn, envelope, family=FAMILY, policy=policy_two, key=KEY)
        with patch.dict(daily_sources.ATTENDED_PILOT_ENV, clear=True), self.connect() as conn:
            self.assertFalse(daily_sources.attended_only(FAMILY))
            receipt = d.admit(conn, envelope, family=FAMILY, policy=policy_two, key=KEY)
        self.assertEqual(receipt["admitted"], 2)


if __name__ == "__main__":
    unittest.main()
