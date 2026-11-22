"""Signed collection-attempt facts: validation and the freshness verdict.

Pure and offline. Every status detail must be built from fixed codes, dates and
run ids only, so none of these facts carries error text, URLs or request data.
"""
import copy
import unittest
from datetime import datetime, timezone

from core.collection import attempts
from core.collection import status as st
from core.daily_sources import SOURCES, source_for

COMMIT = "a" * 40


def facts(**over):
    base = {
        "schema": attempts.SCHEMA, "family": "ph_nsc_official_statements",
        "custody_commit": COMMIT, "attested": True, "reason": None,
        "latest": {"run_id": "43949292737-1", "target_date": "2026-11-15",
                   "target_date_source": "schedule-slot",
                   "finished_utc": "2026-11-16T20:24:55Z", "result": "ok",
                   "health": "ok", "healthy": True},
        "latest_healthy_target_date": "2026-11-15", "unledgered_exit": None}
    base.update(over)
    return base


def latest(**over):
    out = dict(facts()["latest"])
    out.update(over)
    return out


def at(day, hhmm):
    h, m = hhmm.split(":")
    return datetime(2026, 11, day, int(h), int(m), tzinfo=timezone.utc)


def verdict(f, now, cron="10:10", grace=14, require=False):
    return attempts.verdict(f, now=now, cron_utc=cron, grace_hours=grace,
                            require_attestation=require)


class Validate(unittest.TestCase):
    def test_accepts_well_formed_facts_and_stamp_precisions(self):
        self.assertEqual(attempts.validate(facts()), facts())
        for stamp in ("2026-11-16T20:24:55Z", "2026-11-16T20:24:55.123456Z",
                      "2026-11-16T20:24:55+00:00", "2026-11-16T20:24:55.123456+00:00"):
            with self.subTest(stamp=stamp):
                self.assertIsNotNone(attempts.validate(facts(latest=latest(finished_utc=stamp))))
        self.assertIsNotNone(attempts.validate(facts(latest=latest(run_id="pilot-20261110"))))
        self.assertIsNotNone(attempts.validate(facts(latest=None, latest_healthy_target_date=None)))
        self.assertIsNotNone(attempts.validate(facts(
            unledgered_exit={"run_id": "1-1", "collector_exit_status": 1})))
        self.assertIsNotNone(attempts.validate(facts(attested=False, reason="ledger_unreadable")))

    def test_rejects_extra_and_missing_keys(self):
        self.assertIsNone(attempts.validate(dict(facts(), error_detail="x")))
        self.assertIsNone(attempts.validate(dict(facts(), requests=[])))
        self.assertIsNone(attempts.validate(facts(latest=dict(latest(), error_detail="x"))))
        missing = facts()
        del missing["unledgered_exit"]
        self.assertIsNone(attempts.validate(missing))
        self.assertIsNone(attempts.validate(facts(
            unledgered_exit={"run_id": "1", "collector_exit_status": 1, "stderr": "x"})))

    def test_rejects_bad_values(self):
        bad = [
            facts(schema="ipr-collection-attempts/2"),
            facts(custody_commit="A" * 40), facts(custody_commit="a" * 39),
            facts(attested="yes"), facts(reason="Has Spaces"),
            facts(latest_healthy_target_date="2026-13-40"),
            facts(latest_healthy_target_date="2026-11-1"),
            facts(latest=latest(run_id="bad id")), facts(latest=latest(run_id="x" * 81)),
            facts(latest=latest(run_id="")),
            facts(latest=latest(result="exploded")),
            facts(latest=latest(health="great")),
            facts(latest=latest(healthy=1)),
            facts(latest=latest(target_date_source="guess")),
            facts(latest=latest(finished_utc="2026-11-16T20:24:55")),
            facts(latest=latest(finished_utc="2026-11-16T20:24:55+02:00")),
            facts(latest=latest(finished_utc="yesterday")),
            facts(unledgered_exit={"run_id": "1", "collector_exit_status": "1"}),
            facts(unledgered_exit={"run_id": "1", "collector_exit_status": True}),
        ]
        for f in bad:
            with self.subTest(f=f):
                self.assertIsNone(attempts.validate(f))
        for junk in (None, [], "x", 3, {}):
            self.assertIsNone(attempts.validate(junk))

    def test_validate_never_mutates_or_raises(self):
        f = facts()
        snapshot = copy.deepcopy(f)
        attempts.validate(f)
        self.assertEqual(f, snapshot)


class Verdict(unittest.TestCase):
    NOW = at(16, "12:00")

    def test_a_missing_block_is_no_verdict_unless_attestation_is_required(self):
        self.assertIsNone(verdict(None, self.NOW))
        self.assertEqual(verdict(None, self.NOW, require=True),
                         (st.FETCH_FAILURE, "collection_not_attested"))
        # No declared cadence (an attended-only family, an unscheduled family): never required.
        self.assertIsNone(verdict(None, self.NOW, cron=None, require=True))

    def test_not_attested_reports_only_a_fixed_code(self):
        self.assertEqual(verdict(facts(attested=False, reason="ledger_unreadable"), self.NOW),
                         (st.FETCH_FAILURE, "collection_not_attested: ledger_unreadable"))
        self.assertEqual(verdict({"attested": False, "reason": "collection_attestation_invalid"},
                                 self.NOW),
                         (st.FETCH_FAILURE,
                          "collection_not_attested: collection_attestation_invalid"))
        self.assertEqual(verdict({"attested": False, "reason": "Private text, https://x"},
                                 self.NOW)[1], "collection_not_attested: unclassified")

    def test_nsc_16_november_access_challenged_keeps_its_own_status(self):
        nsc = facts(latest=latest(run_id="43949292737-1", target_date="2026-11-16",
                                  result="access_challenged", health="fail", healthy=False),
                    latest_healthy_target_date="2026-11-04")
        self.assertEqual(verdict(nsc, at(17, "00:30")),
                         (st.ACCESS_CHALLENGED,
                          "collection access_challenged (run 43949292737-1, target 2026-11-16)"))

    def test_failure_statuses_and_unhealthy_health(self):
        for result in sorted(st.FAILURE_STATUSES):
            with self.subTest(result=result):
                status, _ = verdict(facts(latest=latest(result=result, health="fail",
                                                        healthy=False)), self.NOW)
                self.assertEqual(status, result)
        # A success result with health "fail" is still a failed collection.
        self.assertEqual(verdict(facts(latest=latest(result="ok", health="fail")), self.NOW)[0],
                         st.FETCH_FAILURE)

    def test_unledgered_exit(self):
        f = facts(unledgered_exit={"run_id": "pilot-20261110", "collector_exit_status": 7})
        self.assertEqual(verdict(f, self.NOW),
                         (st.FETCH_FAILURE, "collector exited 7 without a ledger (run pilot-20261110)"))

    def test_failure_outranks_exit_and_staleness(self):
        f = facts(latest=latest(result="timeout", health="fail"),
                  latest_healthy_target_date="2026-01-01",
                  unledgered_exit={"run_id": "1", "collector_exit_status": 1})
        self.assertEqual(verdict(f, self.NOW)[0], st.TIMEOUT)

    def test_health_only_failure_never_reads_as_collection_ok(self):
        status, detail = verdict(facts(latest=latest(result="ok", health="fail")), self.NOW)
        self.assertEqual(status, "fetch_failure")
        self.assertIn("collection health_fail (result ok", detail)
        self.assertNotIn("collection ok", detail)

    def test_stale_and_current_healthy_targets(self):
        stale = facts(latest_healthy_target_date="2026-11-13")
        self.assertEqual(verdict(stale, self.NOW),
                         (st.FETCH_FAILURE, "collection stale: last healthy target 2026-11-13 "
                          "(latest run 43949292737-1); expected slot 2026-11-15"))
        self.assertIsNone(verdict(facts(latest_healthy_target_date="2026-11-15"), self.NOW))
        self.assertIsNone(verdict(facts(latest_healthy_target_date="2026-11-16"), self.NOW))
        never = facts(latest=None, latest_healthy_target_date=None)
        self.assertEqual(verdict(never, self.NOW)[1],
                         "collection stale: last healthy target none (latest run none); "
                         "expected slot 2026-11-15")

    def test_no_cadence_means_no_staleness_verdict(self):
        self.assertIsNone(verdict(facts(latest_healthy_target_date=None), self.NOW, cron=None))

    def test_boundary_clocks_never_fail_a_run_within_its_observed_lag(self):
        """A collector that finished its previous slot is never stale at any Daily
        start from 03:34Z to 22:56Z, and a slot older than that always is."""
        for cron in ("06:40", "10:10", "17:17", "19:13", "18:17"):
            for hhmm in ("03:34", "12:23", "14:23", "22:56"):
                now = at(16, hhmm)
                from core.shadow_schedule import scheduled_slot_date
                from datetime import timedelta
                expected = scheduled_slot_date(now - timedelta(hours=14), cron)
                with self.subTest(cron=cron, now=hhmm):
                    on_time = facts(latest_healthy_target_date=expected.isoformat())
                    self.assertIsNone(verdict(on_time, now, cron=cron))
                    late = facts(latest_healthy_target_date=(expected - timedelta(days=1)).isoformat())
                    self.assertEqual(verdict(late, now, cron=cron)[0], st.FETCH_FAILURE)
                    # The previous day's slot is the most a normal run can lag behind.
                    self.assertLessEqual((now.date() - expected).days, 2)

    def test_every_status_detail_is_built_from_closed_fields(self):
        probes = [facts(attested=False, reason="x_y"), facts(latest_healthy_target_date="2026-01-01"),
                  facts(latest=latest(result="timeout", health="fail")),
                  facts(unledgered_exit={"run_id": "r-1", "collector_exit_status": 2})]
        for f in probes:
            detail = verdict(f, self.NOW)[1]
            self.assertRegex(detail, r"^[A-Za-z0-9 _.,:;()\-]+$")


class DeclaredCadence(unittest.TestCase):
    def test_declared_crons_and_exemptions(self):
        got = {f: source_for(f).collection_expectation() for f in SOURCES}
        self.assertEqual(got["ph_afp_articles"], ("06:40", 14))
        self.assertEqual(got["ph_nsc_official_statements"], ("10:10", 14))
        self.assertEqual(got["id_kemhan_news"], ("17:17", 14))
        self.assertEqual(got["jp_jcg_press_en"], ("19:13", 14))
        # Singapore MINDEF is recurring (22 Nov approval): private collector 10:37 UTC.
        self.assertEqual(got["sg_mindef_releases"], ("10:37", 14))
        for family in ("us_uscc_press_en", "kr_policy_dapa_releases"):
            self.assertIsNone(got[family][0], family)


FAMILY = "ph_nsc_official_statements"
SENTINELS = ("SENTINEL-error-detail", "SENTINEL-endpoint", "SENTINEL-requested-url",
             "SENTINEL-listing-url", "SENTINEL-failure-detail", "SENTINEL-identity")


def ledger(run_id, target, finished, result="ok", health="ok", **extra):
    out = {"run_id": run_id, "target_date": target, "target_date_source": "schedule-slot",
           "finished_utc": finished, "result": result, "health": health}
    out.update(extra)
    return out


def noisy(**over):
    """A ledger carrying private material that must never reach a signed block."""
    return ledger("90-1", "2026-11-17", "2026-11-17T10:00:00+00:00", **dict({
        "error_detail": SENTINELS[0], "failed_endpoints": [SENTINELS[1]],
        "requests": [{"requested_url": "https://example.invalid/" + SENTINELS[2]}],
        "observed": {"listing_url": "https://example.invalid/" + SENTINELS[3]},
        "failures": [{"detail": SENTINELS[4]}],
        "collector_identity": {"name": SENTINELS[5]},
        "listing_report": {"x": 1}, "attachment_hold_items": ["https://example.invalid/a"]},
        **over))


def custody(root, files):
    """A synthetic git checkout holding ``files`` ({path: dict | str}); its head."""
    import json
    import subprocess
    from pathlib import Path
    repo = Path(root) / "custody"
    repo.mkdir()
    for path, body in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body if isinstance(body, str) else json.dumps(body))
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-qm", "synthetic", "--allow-empty"], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    return repo, head


class ReadCustody(unittest.TestCase):
    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self._n = 0

    def read(self, files, receipt_dirs=()):
        import shutil
        self._n += 1
        root = "%s/%d" % (self.tmp, self._n)
        __import__("os").makedirs(root)
        repo, head = custody(root, files)
        out = attempts.read_custody(repo, head, FAMILY, receipt_dirs=receipt_dirs)
        self.assertIsNotNone(attempts.validate(out), out)
        self.assertEqual((out["family"], out["custody_commit"]), (FAMILY, head))
        return out

    def led(self, name, **kw):
        return "state/ledger/" + name + ".json", ledger(**kw)

    def test_orders_by_parsed_instant_not_run_id_or_precision(self):
        files = dict([
            self.led("20261116T000000+0000-9", run_id="9-1", target="2026-11-15",
                     finished="2026-11-16T00:00:00+00:00"),
            self.led("20261116T000001+0000-1", run_id="100-1", target="2026-11-16",
                     finished="2026-11-17T00:50:13.490049+00:00"),
            self.led("20261116T000002+0000-5", run_id="5-1", target="2026-11-16",
                     finished="2026-11-17T00:50:13Z", result="timeout", health="fail")])
        out = self.read(files)
        # Second precision sorts before the same second with microseconds.
        self.assertEqual(out["latest"]["run_id"], "100-1")
        self.assertTrue(out["attested"] and out["latest"]["healthy"])

    def test_failed_latest_stays_latest_and_rerun_sets_healthy_date(self):
        files = dict([
            self.led("a", run_id="1-1", target="2026-11-15", finished="2026-11-15T10:00:00+00:00"),
            self.led("b", run_id="2-1", target="2026-11-16", finished="2026-11-16T10:00:00+00:00",
                     result="access_challenged", health="fail"),
            # An explicit recovery rerun of an older slot finished earlier than b.
            self.led("c", run_id="1-2", target="2026-11-16", finished="2026-11-16T09:00:00+00:00")])
        out = self.read(files)
        self.assertEqual((out["latest"]["run_id"], out["latest"]["healthy"]), ("2-1", False))
        self.assertEqual(out["latest_healthy_target_date"], "2026-11-16")

    def test_unhealthy_results_and_health_fail_do_not_count(self):
        files = dict([
            self.led("a", run_id="1-1", target="2026-11-15", finished="2026-11-15T10:00:00+00:00"),
            self.led("b", run_id="2-1", target="2026-11-16", finished="2026-11-16T10:00:00+00:00",
                     health="fail"),
            self.led("c", run_id="3-1", target="2026-11-17", finished="2026-11-17T10:00:00+00:00",
                     result="fetch_failure", health=None)])
        out = self.read(files)
        self.assertEqual(out["latest_healthy_target_date"], "2026-11-15")
        self.assertFalse(out["latest"]["healthy"])
        self.assertIsNone(out["latest"]["health"])

    def test_a_switched_off_day_is_unhealthy_but_never_poisons_custody(self):
        # The collectors write result=skipped_disabled, health="skipped" for a
        # disabled day (shadow_collect_desk.py, shadow_collect_ph_nsc.py). It
        # must not make the next twenty healthy runs unattested.
        files = dict([
            self.led("a", run_id="1-1", target="2026-11-14", finished="2026-11-14T20:00:00+00:00"),
            self.led("b", run_id="2-1", target="2026-11-15", finished="2026-11-15T20:00:00+00:00",
                     result="skipped_disabled", health="skipped"),
            self.led("c", run_id="3-1", target="2026-11-16", finished="2026-11-16T20:00:00+00:00",
                     result="access_challenged", health="degraded")]
            + [self.led("d%02d" % i, run_id="%d-1" % (10 + i), target="2026-11-17",
                        finished="2026-11-17T%02d:00:00+00:00" % i) for i in range(3)])
        out = self.read(files)
        self.assertTrue(out["attested"], out)
        self.assertTrue(out["latest"]["healthy"])
        self.assertEqual(out["latest_healthy_target_date"], "2026-11-17")
        self.assertIsNone(verdict(out, at(17, "23:00")))
        # A skipped latest is valid, never healthy, and is judged by staleness.
        out = self.read(dict([
            self.led("a", run_id="1-1", target="2026-11-14", finished="2026-11-14T20:00:00+00:00"),
            self.led("b", run_id="2-1", target="2026-11-17", finished="2026-11-17T20:00:00+00:00",
                     result="skipped_disabled", health="skipped")]))
        self.assertTrue(out["attested"])
        self.assertFalse(out["latest"]["healthy"])
        self.assertEqual(out["latest_healthy_target_date"], "2026-11-14")
        self.assertEqual(verdict(out, at(17, "23:00"))[0], "fetch_failure")

    def test_rehearsal_ledgers_are_skipped(self):
        files = dict([
            self.led("a", run_id="1-1", target="2026-11-15", finished="2026-11-15T10:00:00+00:00"),
            ("state/ledger/b.json", dict(ledger("2-1", "2026-11-16", "2026-11-16T10:00:00+00:00",
                                                result="timeout", health="fail"), rehearsal=True))])
        self.assertEqual(self.read(files)["latest"]["run_id"], "1-1")
        only = {"state/ledger/b.json": dict(ledger("2-1", "2026-11-16", "2026-11-16T10:00:00+00:00"),
                                            rehearsal=True)}
        self.assertEqual(self.read(only)["reason"], "no_ledger")

    def test_only_the_newest_twenty_ledgers_are_read(self):
        files = {"state/ledger/%03d.json" % i: ledger(
            "%d-1" % (i + 1), "2026-10-%02d" % (i % 28 + 1), "2026-10-%02dT10:00:00+00:00" % (i % 28 + 1))
            for i in range(25)}
        files["state/ledger/000.json"] = "not json"  # outside the window
        self.assertTrue(self.read(files)["attested"])
        files["state/ledger/024.json"] = "not json"  # inside it
        self.assertEqual(self.read(files)["reason"], "ledger_unreadable")

    def test_unledgered_exit_rules_across_both_receipt_dirs(self):
        base = dict([self.led("a", run_id="100-1", target="2026-11-16",
                              finished="2026-11-16T10:00:00+00:00")])
        dirs = ("private_attempts", "state/private_attempts")
        receipt = lambda code: {"collector_exit_status": code, "schema": "x"}
        # Newer non-zero receipt, in either directory.
        for where in dirs:
            out = self.read(dict(base, **{where + "/101-1.json": receipt(1)}), dirs)
            self.assertEqual(out["unledgered_exit"], {"run_id": "101-1", "collector_exit_status": 1})
        # The newest of several non-zero receipts wins; zero exits are ignored.
        out = self.read(dict(base, **{"private_attempts/101-1.json": receipt(1),
                                       "state/private_attempts/103-1.json": receipt(2),
                                       "private_attempts/104-1.json": receipt(0)}), dirs)
        self.assertEqual(out["unledgered_exit"]["run_id"], "103-1")
        # Older, equal-run, matching-ledger and zero-exit receipts are not reported.
        files = dict(base, **{"private_attempts/99-1.json": receipt(1),
                              "private_attempts/100-1.json": receipt(1)})
        self.assertIsNone(self.read(files, dirs)["unledgered_exit"])
        files = dict(base, **dict([self.led("b", run_id="101-1", target="2026-11-17",
                                            finished="2026-11-17T10:00:00+00:00")]),
                     **{"private_attempts/101-1.json": receipt(1)})
        self.assertIsNone(self.read(files, dirs)["unledgered_exit"])
        # No receipt directory declared: nothing is read.
        self.assertIsNone(self.read(dict(base, **{"private_attempts/101-1.json": receipt(1)}))
                          ["unledgered_exit"])
        # A later attempt of the latest run, with no ledger, is a failed attempt.
        out = self.read(dict(base, **{"private_attempts/100-2.json": receipt(3)}), dirs)
        self.assertEqual(out["unledgered_exit"]["run_id"], "100-2")

    def test_a_newer_receipt_that_cannot_be_read_is_unattested(self):
        base = dict([self.led("a", run_id="100-1", target="2026-11-16",
                              finished="2026-11-16T10:00:00+00:00")])
        for body in ("not json", {"collector_exit_status": "1"}, {"collector_exit_status": True},
                     {}, []):
            out = self.read(dict(base, **{"private_attempts/101-1.json": body}), ("private_attempts",))
            self.assertEqual((out["attested"], out["reason"]), (False, "ledger_unreadable"), body)
        # An older unreadable receipt is never opened.
        out = self.read(dict(base, **{"private_attempts/50-1.json": "not json"}), ("private_attempts",))
        self.assertTrue(out["attested"])

    def test_total_and_fail_closed(self):
        import os
        good = dict([self.led("a", run_id="1-1", target="2026-11-15",
                              finished="2026-11-15T10:00:00+00:00")])
        for label, files in {
                "empty custody": {"README": "x"},
                "corrupt json": {"state/ledger/a.json": "{"},
                "not an object": {"state/ledger/a.json": "[1]"},
                "bad result": dict([self.led("a", run_id="1-1", target="2026-11-15",
                                             finished="2026-11-15T10:00:00+00:00",
                                             result="surprise")]),
                "bad date": dict([self.led("a", run_id="1-1", target="2026-13-45",
                                           finished="2026-11-15T10:00:00+00:00")]),
                "naive stamp": dict([self.led("a", run_id="1-1", target="2026-11-15",
                                              finished="2026-11-15T10:00:00")]),
                "bad run id": dict([self.led("a", run_id="a b/../c", target="2026-11-15",
                                             finished="2026-11-15T10:00:00+00:00")]),
                "bad health": dict([self.led("a", run_id="1-1", target="2026-11-15",
                                             finished="2026-11-15T10:00:00+00:00", health="great")]),
                "missing source": {"state/ledger/a.json": {"run_id": "1-1", "result": "ok"}},
                "good plus bad": dict(good, **{"state/ledger/b.json": "{"}),
        }.items():
            with self.subTest(label):
                out = self.read(files)
                self.assertFalse(out["attested"])
                self.assertEqual(out["reason"], "no_ledger" if label == "empty custody"
                                 else "ledger_unreadable")
                self.assertIsNone(out["latest"])
        # A missing repository or an unknown commit never raises either.
        out = attempts.read_custody(os.path.join(self.tmp, "nowhere"), COMMIT, FAMILY)
        self.assertEqual((out["attested"], out["reason"]), (False, "ledger_unreadable"))
        self.assertIsNotNone(attempts.validate(out))

    def test_only_allowlisted_fields_are_copied(self):
        import json
        out = self.read(dict([("state/ledger/a.json", noisy())]), ("private_attempts",))
        self.assertTrue(out["attested"])
        self.assertEqual(set(out["latest"]), {"run_id", "target_date", "target_date_source",
                                              "finished_utc", "result", "health", "healthy"})
        blob = json.dumps(out)
        for sentinel in SENTINELS + ("example.invalid",):
            self.assertNotIn(sentinel, blob)

    def test_real_shapes_afp_nsc_kemhan(self):
        files = dict([
            ("state/ledger/20261117T191008+0000-44155431133-1.json",
             ledger("44155431133-1", "2026-11-17", "2026-11-17T19:10:08+00:00",
                    result="access_challenged", health="fail", requests=[{"x": 1}])),
            ("state/ledger/20261116T191008+0000-44100000000-1.json",
             ledger("44100000000-1", "2026-11-16", "2026-11-16T19:10:08+00:00"))])
        out = self.read(files)
        self.assertEqual((out["latest"]["result"], out["latest_healthy_target_date"]),
                         ("access_challenged", "2026-11-16"))


class DeclaredReceiptDirs(unittest.TestCase):
    def test_receipt_dirs_and_signing_rule(self):
        self.assertEqual(source_for("ph_afp_articles").collection_receipt_dirs, ("private_attempts",))
        self.assertEqual(source_for("ph_nsc_official_statements").collection_receipt_dirs,
                         ("private_attempts",))
        self.assertEqual(source_for("id_kemhan_news").collection_receipt_dirs,
                         ("state/private_attempts",))
        signs = {f for f, s in SOURCES.items() if s.signs_collection()}
        self.assertEqual(signs, {"ph_afp_articles", "ph_nsc_official_statements",
                                 "id_kemhan_news", "jp_jcg_press_en", "sg_mindef_releases"})
        for family in ("sg_mindef_releases", "us_uscc_press_en", "kr_policy_dapa_releases"):
            self.assertEqual(source_for(family).collection_receipt_dirs, ())


if __name__ == "__main__":
    unittest.main()
