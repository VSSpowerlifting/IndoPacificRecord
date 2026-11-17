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
        # No declared cadence (attended pilot, unscheduled family): never required.
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
        for family in ("sg_mindef_releases", "us_uscc_press_en", "kr_policy_dapa_releases"):
            self.assertIsNone(got[family][0], family)


if __name__ == "__main__":
    unittest.main()
