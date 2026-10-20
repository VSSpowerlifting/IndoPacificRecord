"""NSC private-to-public handoff: envelope, custody, atomic write and recovery.

State comes from the real NSC shadow runner over the unit-test fixture pages
with the network blocked (tests.test_ph_nsc_official_link_admission). It is a
synthetic rehearsal, never a live observation. The bridge key is a fictional
test value; the committed policy stays closed throughout.
"""
import contextlib
import copy
import gzip
import hashlib
import io
import json
import os
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core import ph_nsc_official_link_admission as nsc
from core.regional_official_link_release import canonical
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0013_vietnam_regional_official_links as m13
from migrations.versions import m0014_ph_nsc_regional_official_links as m14
from scripts import admit_ph_nsc_official_links as cli
from tests.test_ph_nsc_official_link_admission import (
    NOW, RESOLVED, STANDING, NscCase, decision, git,
)

BRIDGE = b"fictional-nsc-bridge-test-key-000000000000"
ROOT = Path(__file__).resolve().parents[1]
HEAD = git(ROOT, "rev-parse", "HEAD")
QUIET = date(2026, 10, 2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Handoff(NscCase):
    def setUp(self):
        super().setUp()
        self.db = self.root / "pla_watch.db"
        with sqlite3.connect(str(self.db)) as cx:
            cx.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT)")
            cx.execute("INSERT INTO articles (url) VALUES ('https://example.invalid/a')")
            base.up(cx)
            m13.up(cx)
            m14.up(cx)
            from tests.test_regional_official_link_render import insert
            insert(cx)  # AFP / Kemhan rows that must never move
            cx.execute("PRAGMA journal_mode=DELETE")
        cx.close()

    def nsc_rows(self):
        with sqlite3.connect(self.db.as_uri() + "?mode=ro", uri=True) as cx:
            rows = cx.execute("SELECT source_identity FROM " + base.TABLE
                              + " WHERE source_family=? ORDER BY 1", (nsc.FAMILY,)).fetchall()
        cx.close()
        return [r[0] for r in rows]

    def unrelated(self):
        with sqlite3.connect(self.db.as_uri() + "?mode=ro", uri=True) as cx:
            d = cli.unrelated_digest(cx)
        cx.close()
        return d

    def envelope(self, packet, key=BRIDGE, attempt="123-1", ref=HEAD):
        return cli.sign_envelope(packet, key=key, source_run_attempt=attempt, validator_ref=ref)

    def validate(self, body, mac, key=BRIDGE):
        return cli.validate_envelope(body, mac, key=key, public_main=ROOT)

    def resign(self, mutate):
        """An envelope whose body was altered by someone holding the key."""
        if not hasattr(self, "_signed"):
            _, commit = self.collect(run_id="resign")
            self._signed = self.envelope(self.packet(commit))[0]
        env = json.loads(gzip.decompress(self._signed))
        mutate(env)
        body = gzip.compress(canonical(env), mtime=0)
        return body, cli._mac(BRIDGE, body)


class Envelope(Handoff):
    def test_round_trip_carries_metadata_only(self):
        _, commit = self.collect()
        packet = self.packet(commit)
        body, mac = self.envelope(packet)
        got, attempt = self.validate(body, mac)
        self.assertEqual((got, attempt), (packet, "123-1"))
        text = gzip.decompress(body).decode()
        for k in ("title_original", "text_original", "site_byline", "summary"):
            self.assertNotIn(k, text)

    def test_tampered_body_wrong_key_and_short_key_hold(self):
        _, commit = self.collect()
        body, mac = self.envelope(self.packet(commit))
        flipped = body[:-1] + bytes([body[-1] ^ 1])
        for args, reason in (((flipped, mac), "mac_invalid"),
                             ((body, mac, b"another-fictional-key-0000000000000"), "mac_invalid"),
                             ((body, "0" * 64), "mac_invalid"),
                             ((body, mac, b"short"), "bridge_key_missing_or_short"),
                             ((b"", mac), "size_invalid"),
                             ((b"x" * (cli.MAX_ENVELOPE_BYTES + 1), mac), "size_invalid")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.validate(*args)

    def test_title_or_body_cannot_ride_along(self):
        def add_title(env):
            env["packet"]["records"][0]["title_original"] = "smuggled"
        def add_text(env):
            env["packet"]["links"][0]["text_original"] = "smuggled"
        def add_packet_key(env):
            env["packet"]["excerpt"] = "smuggled"
        def add_env_key(env):
            env["translation"] = "smuggled"
        for fn, reason in ((add_title, "record_invalid"), (add_text, "link_invalid"),
                           (add_packet_key, "packet_schema_invalid"),
                           (add_env_key, "envelope_schema_invalid")):
            with self.subTest(fn=fn.__name__), self.assertRaisesRegex(ValueError, reason):
                self.validate(*self.resign(fn))

    def test_carried_claims_are_recomputed(self):
        def url(env):
            env["packet"]["links"][0]["canonical_official_url"] = "https://nsc.gov.ph/2026/07/09/x/"
        def version(env):
            env["packet"]["links"][0]["metadata_version_sha256"] = "f" * 64
        def day(env):
            for k in ("records", "links"):
                env["packet"][k][0]["publisher_posted_date"] = "2026-01-01"
        def issuer(env):
            env["packet"]["links"][0]["official_issuer"] = "ph_afp"
        def exported(env):
            env["packet"]["original_content_exported"] = True
        def dup(env):
            env["packet"]["links"][1] = copy.deepcopy(env["packet"]["links"][0])
        for fn, reason in ((url, "link_mismatch"), (version, "link_mismatch"),
                           (day, "record_invalid"), (issuer, "link_mismatch"),
                           (exported, "packet_schema_invalid"), (dup, "link_mismatch")):
            with self.subTest(fn=fn.__name__), self.assertRaisesRegex(ValueError, reason):
                self.validate(*self.resign(fn))

    def test_public_branch_is_refused_even_when_silent(self):
        _, commit = self.collect(run_id="quiet", target=QUIET, lookback=6)
        packet = self.packet(commit, nsc.PUBLIC_REF)
        self.assertEqual(packet["links"], [])
        with self.assertRaisesRegex(ValueError, "not_from_private_custody"):
            self.envelope(packet)
        def public(env):
            env["source_ref"] = nsc.PUBLIC_REF
        with self.assertRaisesRegex(ValueError, "not_from_private_custody"):
            self.validate(*self.resign(public))
        with self.assertRaisesRegex(ValueError, "not_from_private_custody"):
            cli.admit_validated(self.db, packet, policy=STANDING, as_of_utc=NOW)

    def test_validator_code_must_be_on_public_main(self):
        _, commit = self.collect()
        packet = self.packet(commit)
        with self.assertRaisesRegex(ValueError, "validator_code_not_on_public_main"):
            self.validate(*self.envelope(packet, ref="0" * 40))
        with self.assertRaisesRegex(ValueError, "source_run_attempt_invalid"):
            self.envelope(packet, attempt="latest")


class Admission(Handoff):
    def setUp(self):
        super().setUp()
        self.before_unrelated = self.unrelated()

    def tearDown(self):
        self.assertEqual(self.before_unrelated, self.unrelated())
        self.assertEqual([p.name for p in self.root.iterdir() if ".nsc-admission-" in p.name], [])

    def admit(self, packet, pol=STANDING, **kw):
        return cli.admit_validated(self.db, packet, policy=pol, as_of_utc=NOW, **kw)

    def test_quiet_window_is_byte_identical_no_op(self):
        _, commit = self.collect(target=QUIET, lookback=6)
        before = sha(self.db)
        receipt, total = self.admit(self.packet(commit), pol=nsc.load_policy())
        self.assertEqual((receipt["status"], total), ("no_eligible_records", 0))
        self.assertEqual(sha(self.db), before)

    def test_closed_policy_holds_without_writing(self):
        _, commit = self.collect()
        before = sha(self.db)
        for pol, reason in ((nsc.load_policy(), "category_anomaly_unresolved"),
                            (RESOLVED, "metadata_publication_not_authorized")):
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                self.admit(self.packet(commit), pol=pol)
        self.assertEqual(sha(self.db), before)

    def test_authorized_admission_then_idempotent_retry(self):
        _, commit = self.collect()
        receipt, total = self.admit(self.packet(commit))
        self.assertEqual((receipt["new_official_links"], total), (2, 2))
        after_first = sha(self.db)
        receipt, total = self.admit(self.packet(commit))
        self.assertEqual((receipt["unchanged_official_links"], total), (2, 2))
        self.assertEqual(self.nsc_rows(), ["nsc:2269", "nsc:3108"])
        # Unchanged rows keep their original commit, proof and timestamp.
        self.assertEqual(sha(self.db), after_first)

    def test_sealed_exact_version_decision_admits_selection(self):
        _, commit = self.collect()
        packet = self.packet(commit)
        sealed = decision(packet, approved_source_identities=["nsc:3108"])
        from tests.test_ph_nsc_official_link_admission import KEY
        self.admit(packet, pol=RESOLVED, sealed=sealed, secret=KEY)
        self.assertEqual(self.nsc_rows(), ["nsc:3108"])

    def test_interrupted_write_leaves_production_unchanged_and_retry_succeeds(self):
        _, commit = self.collect()
        before = sha(self.db)
        with self.assertRaisesRegex(RuntimeError, "runner killed"):
            self.admit(self.packet(commit),
                       fail_after_insert=mock.Mock(side_effect=RuntimeError("runner killed")))
        self.assertEqual(sha(self.db), before)
        self.assertEqual(self.nsc_rows(), [])
        self.assertEqual(self.admit(self.packet(commit))[1], 2)

    def test_concurrent_production_change_is_held(self):
        _, commit = self.collect()
        before = sha(self.db)

        def other_writer():
            with sqlite3.connect(str(self.db)) as cx:
                cx.execute("INSERT INTO articles (url) VALUES ('https://example.invalid/b')")
            cx.close()
        with self.assertRaisesRegex(ValueError, "changed_concurrently"):
            self.admit(self.packet(commit), fail_after_insert=other_writer)
        self.assertNotEqual(sha(self.db), before)  # the other writer's change survives
        self.assertEqual(self.nsc_rows(), [])
        self.before_unrelated = self.unrelated()

    def test_admitted_statement_missing_from_later_private_state_holds(self):
        _, commit = self.collect()
        self.admit(self.packet(commit))
        quiet = copy.deepcopy(self.packet(commit))
        quiet["records"], quiet["links"] = quiet["records"][:1], quiet["links"][:1]
        before = sha(self.db)
        for packet in (quiet, dict(quiet, records=[], links=[])):
            with self.assertRaisesRegex(ValueError, "missing_from_private_source"):
                self.admit(packet)
        self.assertEqual(sha(self.db), before)


class CommandLine(Handoff):
    def run_cli(self, *argv, env=None):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env or {cli.BRIDGE_KEY_ENV: BRIDGE.decode()}), \
                contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, json.loads(out.getvalue())

    def sign(self, commit):
        out = self.root / "env"
        with mock.patch.object(cli, "_head", side_effect=lambda r: (
                HEAD if Path(r) == cli.ROOT else git(r, "rev-parse", "HEAD"))):
            code, msg = self.run_cli("sign-private", "--state-repo", str(self.repo),
                                     "--source-commit", commit, "--source-run-attempt", "9-1",
                                     "--output-dir", str(out))
        return code, msg, out

    def admit(self, out, *extra, env=None):
        return self.run_cli("admit", "--production-db", str(self.db), "--rehearsal",
                            "--signed-envelope", str(out / "nsc-envelope.json.gz"),
                            "--signed-mac", str(out / "nsc-envelope.mac"), *extra, env=env)

    def test_end_to_end_quiet_day_and_held_day(self):
        _, quiet = self.collect(target=QUIET, lookback=6)
        code, msg, out = self.sign(quiet)
        self.assertEqual((code, msg["status"], msg["links"]), (0, "SIGNED", 0))
        before = sha(self.db)
        code, msg = self.admit(out)
        self.assertEqual((code, msg["status"], msg["nsc_rows_after"]),
                         (0, "NO_ELIGIBLE_RECORDS", 0))
        self.assertEqual(sha(self.db), before)
        # A day with statements: the committed closed policy holds, nothing moves.
        _, busy = self.collect(run_id="r2")
        code, msg, out = self.sign(busy)
        self.assertEqual((code, msg["links"]), (0, 2))
        code, msg = self.admit(out)
        self.assertEqual((code, msg["status"], msg["reason"]),
                         (2, "HOLD", "nsc_category_anomaly_unresolved"))
        self.assertFalse(msg["published_original_titles_or_bodies"])
        self.assertEqual(sha(self.db), before)

    def test_missing_key_and_production_guard(self):
        _, quiet = self.collect(target=QUIET, lookback=6)
        _, _, out = self.sign(quiet)
        code, msg = self.admit(out, env={cli.BRIDGE_KEY_ENV: ""})
        self.assertEqual((code, msg["reason"]), (2, "nsc_bridge_key_not_configured"))
        code, msg = self.run_cli("admit", "--production-db", str(self.db),
                                 "--signed-envelope", str(out / "nsc-envelope.json.gz"),
                                 "--signed-mac", str(out / "nsc-envelope.mac"))
        self.assertEqual((code, msg["reason"]), (2, "only_canonical_production_database_allowed"))

    def test_signing_prints_no_publisher_text(self):
        _, commit = self.collect()
        code, msg, out = self.sign(commit)
        self.assertEqual(code, 0)
        self.assertEqual(set(msg), {"status", "replayed_records", "links",
                                    "envelope_bytes", "candidate_sha256"})
        self.assertEqual(sorted(p.name for p in out.iterdir()),
                         ["nsc-envelope.json.gz", "nsc-envelope.mac"])


class ProductionWorkflow(unittest.TestCase):
    """Static contract: the public lane only ever receives a signed envelope."""

    def setUp(self):
        raw = (ROOT / ".github/workflows/ph_nsc_verified_official_link_production.yml").read_text()
        self.raw = raw
        self.code = "\n".join(line for line in raw.splitlines()
                              if not line.lstrip().startswith("#"))

    def test_dispatch_only_and_held_until_bridge_enabled(self):
        on = self.code.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
        self.assertIn("workflow_dispatch:", on)
        for trigger in ("schedule:", "push:", "pull_request", "workflow_run"):
            self.assertNotIn(trigger, on)
        self.assertIn("vars.NSC_METADATA_BRIDGE_ENABLED", self.code)
        first = self.code.split("    steps:\n", 1)[1].split("      - name: Check out", 1)[0]
        self.assertIn('test "$BRIDGE_ENABLED" = true', first)

    def test_least_privilege_and_shared_philippines_lock(self):
        self.assertRegex(self.code, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("group: philippines-verified-official-link-production", self.code)
        self.assertIn("cancel-in-progress: false", self.code)
        self.assertIn("secrets.NSC_BRIDGE_KEY", self.code)
        self.assertNotIn("AFP_BRIDGE_KEY", self.code)

    def test_no_collection_custody_or_original_text_paths(self):
        for forbidden in (
                "shadow_collect_ph", "sign-private", "shadow/ph-nsc", "archive/ph-nsc",
                "git clone", "actions: write", "pages: write", "id-token: write",
                "upload-artifact", "curl ", "wget ", "git add -A", "git add .",
                "--force", "push -f", "pull_request_target", "ANTHROPIC", "OPENAI"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)

    def test_writes_only_the_db_and_philippines_page_with_optimistic_checks(self):
        self.assertIn("python -m migrations.cli --apply", self.code)
        self.assertIn("python scripts/admit_ph_nsc_official_links.py admit", self.code)
        self.assertIn("git add -- pla_watch.db output/philippines.html", self.code)
        self.assertIn("git add -- philippines.html", self.code)
        self.assertIn("Production main moved", self.code)
        self.assertIn("Pages moved; never overwrite", self.code)
        self.assertIn("main output and gh-pages Philippines bytes differ", self.code)
        self.assertIn("assert got == rows", self.code)
