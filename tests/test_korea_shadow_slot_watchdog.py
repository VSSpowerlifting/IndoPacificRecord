"""Synthetic, publisher-free Korea scheduled-slot watcher contracts."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import watch_korea_shadow_slots as watch

SHA = "a" * 40
CLOCK = {"desk": "korea", "day_zero_utc": "2026-10-06T16:52:01.420713+00:00",
         "day_zero_run_id": "local-native-20261006-korea"}


def receipt(d, *, run, origin="schedule-slot", health="ok",
            result="ok_all_duplicates"):
    return {"desk": "korea", "run_id": run, "target_date": d,
            "target_date_source": origin, "health": health, "result": result,
            "started_utc": d + "T20:40:00+00:00",
            "finished_utc": d + "T20:41:00+00:00"}


def originals():
    data = [receipt("2026-10-06", run="local-native-20261006-korea",
                    origin="explicit", result="ok")]
    for i, d in enumerate(range(6, 12)):
        data.append(receipt("2026-10-%02d" % d, run="%d-1" % (37533278839 + i),
                            result="ok" if d == 8 else "ok_all_duplicates"))
    return data


def held(d, *, run, count=1, **kwargs):
    """A receipt recording `count` releases left out of custody by the size hold."""
    data = receipt(d, run=run, **kwargs)
    data["attachment_holds"] = count
    data["attachment_hold_items"] = [
        {"url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=%d" % (9000 + n)}
        for n in range(count)]
    return data


def through_october_thirteen():
    return originals() + [receipt("2026-10-12", run="38323793488-1"),
                          receipt("2026-10-13", run="38400000001-1")]


class KoreaWatchTests(unittest.TestCase):
    def run_main(self, ledgers, as_of, *flags):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            clock = Path(tmp) / "state" / "clock.json"
            clock.parent.mkdir()
            clock.write_text(json.dumps(CLOCK), encoding="utf-8")
            out = io.StringIO()
            with patch.object(watch, "pinned_ledger_checkout",
                              return_value=(SHA, ledgers)), \
                    contextlib.redirect_stdout(out):
                code = watch.main(["--shadow-checkout", tmp,
                                   "--as-of-utc", as_of, *flags])
        return code, out.getvalue()

    def test_hold_on_the_latest_scheduled_slot_fails_the_check_without_identities(self):
        data = originals() + [held("2026-10-12", run="38323793488-1",
                                   count=2, result="ok")]
        report = watch.summarize(data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertFalse(report["current_mature_slot_missing"])
        self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_HAS_ATTACHMENT_HOLDS")
        self.assertEqual(report["attachment_holds_latest_mature_slot"], 2)
        self.assertEqual(report["scheduled_dates_with_attachment_holds"], ["2026-10-12"])
        self.assertEqual(report["distinct_attachment_hold_identities_in_ledgers"], 2)
        self.assertFalse(report["attachment_hold_custody_resolution_verified"])
        self.assertFalse(report["production_eligible"])
        code, out = self.run_main(data, "2026-10-13T01:30:00Z", "--fail-current-gap")
        self.assertEqual(code, 2)
        self.assertEqual(out.count("::error::"), 1)
        self.assertIn("left 2 release(s) out of custody", out)
        # Public Actions log: counts and dates only, never a release identity.
        self.assertNotIn("newsId", out)
        self.assertNotIn("korea.kr", out)
        # Without the flag the same evidence is reported but never fails.
        code, out = self.run_main(data, "2026-10-13T01:30:00Z")
        self.assertEqual(code, 0)
        self.assertNotIn("::error::", out)
        self.assertIn("::warning::Korea ledgers in the evaluated window record", out)

    def test_later_clean_slot_keeps_an_earlier_hold_visible_and_blocks_the_candidate(self):
        clean = through_october_thirteen()
        report = watch.summarize(clean, CLOCK, commit=SHA, as_of="2026-10-14T01:30:00Z")
        self.assertTrue(report["rolling_seven_consecutive_ledger_candidate"])
        self.assertEqual(report["scheduled_dates_with_attachment_holds"], [])
        self.assertEqual(report["attachment_holds_latest_mature_slot"], 0)
        code, out = self.run_main(clean, "2026-10-14T01:30:00Z", "--fail-current-gap")
        self.assertEqual((code, out.count("::")), (0, 0))

        data = [held(r["target_date"], run=r["run_id"], result="ok")
                if r["target_date"] == "2026-10-12" else r for r in clean]
        report = watch.summarize(data, CLOCK, commit=SHA, as_of="2026-10-14T01:30:00Z")
        self.assertEqual(report["status"], "LEDGER_SCHEDULED_SLOTS_OBSERVED")
        self.assertEqual(report["missing_scheduled_dates"], [])
        self.assertEqual(report["attachment_holds_latest_mature_slot"], 0)
        self.assertEqual(report["scheduled_dates_with_attachment_holds"], ["2026-10-12"])
        self.assertEqual(report["rolling_seven_dates_with_attachment_holds"], ["2026-10-12"])
        self.assertFalse(report["rolling_seven_consecutive_ledger_candidate"])
        code, out = self.run_main(data, "2026-10-14T01:30:00Z", "--fail-current-gap")
        self.assertEqual(code, 0)
        self.assertNotIn("::error::", out)
        self.assertEqual(out.count("::warning::"), 1)
        self.assertIn("A later clean slot does not show those releases were collected", out)
        self.assertNotIn("newsId", out)

    def test_failed_scheduled_run_with_holds_is_both_missing_and_held(self):
        data = originals() + [held("2026-10-12", run="38323793488-1",
                                   health="fail", result="oversized_response")]
        report = watch.summarize(data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertTrue(report["current_mature_slot_missing"])
        self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_MISSING")
        self.assertEqual(report["attachment_holds_latest_mature_slot"], 1)
        self.assertEqual(report["scheduled_dates_with_attachment_holds"], ["2026-10-12"])
        code, out = self.run_main(data, "2026-10-13T01:30:00Z", "--fail-current-gap")
        self.assertEqual((code, out.count("::error::")), (2, 2))

    def test_missing_latest_slot_without_holds_still_fails_the_check(self):
        code, out = self.run_main(originals(), "2026-10-13T01:30:00Z", "--fail-current-gap")
        self.assertEqual((code, out.count("::error::")), (2, 1))
        self.assertIn("no successful scheduled-run ledger", out)
        self.assertNotIn("out of custody", out)
        code, out = self.run_main(originals(), "2026-10-13T01:30:00Z")
        self.assertEqual((code, out.count("::error::")), (0, 0))

    def test_explicit_recovery_that_left_releases_out_is_not_a_recovery(self):
        data = originals() + [held("2026-10-12", run="9991-1", origin="explicit",
                                   result="ok")]
        report = watch.summarize(data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertEqual(report["source_dates_recovered_explicitly_but_not_scheduled"], [])
        self.assertEqual(
            report["source_dates_without_successful_scheduled_or_explicit_recovery"],
            ["2026-10-12"])
        self.assertEqual(report["explicit_recovery_dates_with_attachment_holds"],
                         ["2026-10-12"])
        self.assertEqual(report["scheduled_dates_with_attachment_holds"], [])
        # A second, clean recovery of the same date does recover it.
        data.append(receipt("2026-10-12", run="9992-1", origin="explicit", result="ok"))
        report = watch.summarize(data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertEqual(report["source_dates_recovered_explicitly_but_not_scheduled"],
                         ["2026-10-12"])
        self.assertEqual(report["explicit_recovery_dates_with_attachment_holds"], [])
        self.assertEqual(report["distinct_attachment_hold_identities_in_ledgers"], 1)

    def test_malformed_attachment_hold_evidence_fails_closed(self):
        url = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=9000"
        for bad in ({"attachment_holds": 1},
                    {"attachment_hold_items": [{"url": url}]},
                    {"attachment_holds": True, "attachment_hold_items": [{"url": url}]},
                    {"attachment_holds": "1", "attachment_hold_items": [{"url": url}]},
                    {"attachment_holds": -1, "attachment_hold_items": []},
                    {"attachment_holds": 1, "attachment_hold_items": {"url": url}},
                    {"attachment_holds": 1, "attachment_hold_items": [url]},
                    {"attachment_holds": 1, "attachment_hold_items": [{"url": ""}]},
                    {"attachment_holds": 2, "attachment_hold_items": [{"url": url}] * 2},
                    {"attachment_holds": 1, "attachment_hold_items": [{"url": url}] * 2},
                    {"attachment_holds": 41, "attachment_hold_items": [
                        {"url": url + str(n)} for n in range(41)]}):
            with self.subTest(bad=sorted(bad)):
                data = originals()
                data.append(dict(receipt("2026-10-12", run="38323793488-1"), **bad))
                with self.assertRaisesRegex(watch.KoreaWatchHold, "attachment-hold"):
                    watch.summarize(data, CLOCK, commit=SHA,
                                    as_of="2026-10-13T01:30:00Z")

    def test_maturation_never_alerts_before_six_hour_grace(self):
        self.assertEqual(watch.matured_slot("2026-10-13T23:46:59Z").isoformat(),
                         "2026-10-12")
        self.assertEqual(watch.matured_slot("2026-10-13T23:47:00Z").isoformat(),
                         "2026-10-13")
        self.assertEqual(watch.matured_slot("2026-10-14T06:07:00Z").isoformat(),
                         "2026-10-13")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.matured_slot("2026-10-13T23:47:00-04:00")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.matured_slot("2026-10-13T23:47:00")

    def test_live_october_six_to_eleven_metadata_reports_october_twelve_gap(self):
        report = watch.summarize(
            originals(), CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
        self.assertEqual(report["latest_mature_slot"], "2026-10-12")
        self.assertEqual(report["successful_scheduled_slots"], 5)
        self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_MISSING")
        self.assertTrue(report["current_mature_slot_missing"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["authenticates_all_github_actions_attempts"])

    def test_manual_recovery_covers_source_date_but_never_fabricates_schedule(self):
        data = originals()
        data.append(receipt("2026-10-12", run="9991-1", origin="explicit",
                            result="ok"))
        report = watch.summarize(
            data, CLOCK, commit=SHA, as_of="2026-10-13T23:47:10Z")
        self.assertEqual(report["missing_scheduled_dates"],
                         ["2026-10-12", "2026-10-13"])
        self.assertEqual(
            report["source_dates_recovered_explicitly_but_not_scheduled"],
            ["2026-10-12"])
        self.assertEqual(
            report["source_dates_without_successful_scheduled_or_explicit_recovery"],
            ["2026-10-13"])
        self.assertFalse(report["weekly_brief_eligible"])
        self.assertFalse(report["source_or_media_rights_approved"])

    def test_later_success_does_not_hide_prior_failure(self):
        data = originals()
        data.append(receipt("2026-10-13", run="384001-1", result="ok"))
        report = watch.summarize(
            data, CLOCK, commit=SHA, as_of="2026-10-13T23:48:00Z")
        self.assertFalse(report["current_mature_slot_missing"])
        self.assertEqual(report["status"], "HISTORICAL_SCHEDULED_GAPS_REMAIN")
        self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        self.assertFalse(report["human_review_approved"])

    def test_failure_and_foreign_provenance_never_count_as_scheduled(self):
        for changed in ({"health": "fail"}, {"result": "robots_timeout"}):
            data = originals()
            data.append(dict(receipt("2026-10-12", run="38323793488-1"), **changed))
            report = watch.summarize(
                data, CLOCK, commit=SHA, as_of="2026-10-13T01:30:00Z")
            self.assertEqual(report["missing_scheduled_dates"], ["2026-10-12"])
        for bad in ({"run_id": "38323793488-2"},
                    {"target_date_source": "guess"},
                    {"target_date": "2026-02-30"},
                    {"desk": "indonesia"}):
            data = originals()
            data.append(dict(receipt("2026-10-12", run="38323793488-1"), **bad))
            with self.assertRaises(watch.KoreaWatchHold):
                watch.summarize(data, CLOCK, commit=SHA,
                                as_of="2026-10-13T01:30:00Z")

    def test_duplicated_ids_foreign_clock_or_unpinned_commit_fail(self):
        data = originals()
        data.append(dict(data[-1]))
        with self.assertRaisesRegex(watch.KoreaWatchHold, "duplicate"):
            watch.summarize(data, CLOCK, commit=SHA,
                            as_of="2026-10-13T01:30:00Z")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.summarize(originals(), dict(CLOCK, desk="indonesia"),
                            commit=SHA, as_of="2026-10-13T01:30:00Z")
        with self.assertRaises(watch.KoreaWatchHold):
            watch.summarize(originals(), CLOCK, commit="main",
                            as_of="2026-10-13T01:30:00Z")

    def test_readonly_sparse_checkout_reuses_immutable_ledger_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            clock = path / "state" / "clock.json"
            clock.parent.mkdir()
            clock.write_text(json.dumps(CLOCK), encoding="utf-8")
            with patch.object(watch, "pinned_ledger_checkout",
                              return_value=(SHA, originals())) as verifier:
                report = watch.inspect_checkout(
                    path, as_of="2026-10-13T01:30:00Z")
                verifier.assert_called_once_with(path, expected_branch=watch.STATE_BRANCH)
                self.assertEqual(report["state_commit"], SHA)
                self.assertEqual(report["status"], "CURRENT_SCHEDULED_SLOT_MISSING")

    def test_workflow_is_source_free_and_readonly_with_a_delayed_slot_check(self):
        raw = (Path(__file__).resolve().parents[1] / ".github" /
               "workflows/korea_shadow_slot_watchdog.yml"
               ).read_text(encoding="utf-8")
        self.assertIn("7 6 * * *", raw)
        self.assertIn("permissions:\n  contents: read", raw)
        self.assertIn("archive/korea-policy-briefing", raw)
        self.assertIn("secrets.IPR_KOREA_PRIVATE_READ_TOKEN", raw)
        self.assertIn("--filter=blob:none", raw)
        self.assertIn("'/state/ledger/**' '/state/clock.json'", raw)
        # The filtered fetch and its implicit checkout-time blob fetch must
        # both be authenticated. The header is command-scoped, not persisted.
        auth_arg = 'http.https://github.com/.extraheader=AUTHORIZATION: basic $auth'
        self.assertEqual(raw.count(auth_arg), 2)
        checkout_prefix = raw.split(
            'checkout -q -b archive/korea-policy-briefing FETCH_HEAD', 1
        )[0].splitlines()[-2]
        self.assertIn('git -C "$repo" -c', checkout_prefix)
        self.assertIn(auth_arg, checkout_prefix)
        self.assertNotIn('git -C "$repo" config http', raw)
        self.assertNotIn('https://x-access-token:', raw)
        self.assertIn("state/ledger", raw)
        self.assertIn("state/clock.json", raw)
        self.assertIn("scripts.watch_korea_shadow_slots", raw)
        self.assertNotIn("refs/heads/shadow/korea-policy-briefing", raw)
        self.assertIn("--fail-current-gap", raw)
        for forbidden in ("git push", "actions/upload-artifact",
                          "workflow_dispatch --ref", "ANTHROPIC_API_KEY",
                          "IPR_SMTP_APP_PASSWORD",
                          "state/captures/*.bin", "state/shadow.db\n",
                          "git merge", "gh workflow run"):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
