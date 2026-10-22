"""Offline Git-object review and serial remote publication boundaries."""
import json
import re
import socket
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE
from scripts import review_vietnam_ministry_state as review
from scripts import vietnam_ministry_remote as remote
from scripts.shadow_collect_vietnam_ministry import collect, load_source
from tests.test_vn_ministry_adapters import adapter, response, MPS, ENERGY, INDUSTRY

COMMIT = "a" * 40
BODIES = {MPS: ["mps-article-concordia.bin", "mps-article-tho-nhi-ky.bin"],
          ENERGY: ["derived-moit-article-thue-xang-dau.html", "derived-moit-article-nghi-dinh-xang-dau.html"],
          INDUSTRY: ["derived-moit-article-cnht-dinh-huong.html"]}


class WorkflowTokenPermissions(unittest.TestCase):
    def test_actions_api_jobs_keep_explicit_job_scoped_read_permissions(self):
        text = (Path(remote.REPO) / ".github/workflows/vietnam_ministry_shadow.yml").read_text()
        for name in ("shadow", "reviewed-release"):
            with self.subTest(job=name):
                job = re.search(r"(?ms)^  " + re.escape(name) +
                                r":\n(.*?)(?=^  [\w-]+:\n|\Z)", text)
                self.assertIsNotNone(job, "required Actions API job missing")
                permissions = re.search(r"(?m)^    permissions:\n((?:      [^\n]+\n)+)",
                                        job.group(1))
                self.assertIsNotNone(permissions, "job must declare its own token scopes")
                scopes = dict(line.strip().split(": ", 1)
                              for line in permissions.group(1).splitlines())
                self.assertEqual(scopes, {"contents": "write", "actions": "read"})


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo)] + list(args), stderr=subprocess.DEVNULL).decode().strip()


class RemoteReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.net = patch.object(socket.socket, "connect", side_effect=AssertionError("network"))
        self.net.start()
        self.addCleanup(self.net.stop)
        self.repos = self.root / "repos"
        self.gate = self.root / "gate"
        for slug in remote.SOURCES:
            repo = self.repos / slug
            repo.mkdir(parents=True)
            git(repo, "init")
            git(repo, "checkout", "--orphan", load_source(slug).state_branch)
            git(repo, "config", "user.name", "Offline test")
            git(repo, "config", "user.email", "offline@example.invalid")

    def collector(self, state, slug, target, lookback, cap, run_id, commit, **kwargs):
        return collect(state, slug, target, lookback, cap, run_id, commit,
                       adapter=adapter(slug, [response(n) for n in BODIES[slug]]))

    def batch(self, collector=None):
        return remote.run_batch(self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                                0, 2, "remote-test", COMMIT, collector or self.collector)

    def commit_state(self, slug=MPS):
        repo = self.repos / slug
        git(repo, "add", "state")
        git(repo, "commit", "-m", "successful isolated test state")
        return git(repo, "rev-parse", "HEAD")

    def packet(self, slug=MPS, name="packet", commit=None):
        commit = commit or self.commit_state(slug)
        out = self.root / name
        m = review.build(self.repos / slug, commit, slug, "day-07", "2026-10-07", out)
        return out, m

    def test_three_sources_commit_bound_and_byte_reproducible(self):
        self.batch()
        for slug in remote.SOURCES:
            commit = self.commit_state(slug)
            one, m = self.packet(slug, slug + "-one", commit)
            two, _ = self.packet(slug, slug + "-two", commit)
            self.assertEqual({p.name: p.read_bytes() for p in one.iterdir()},
                             {p.name: p.read_bytes() for p in two.iterdir()})
            self.assertTrue(m["formal"])
            self.assertFalse(m["checkpoint_reached"])
            self.assertEqual(m["source_slug"], slug)
            self.assertEqual(m["state_tree"], git(self.repos / slug, "rev-parse", commit + ":state"))
            self.assertIsNone(m["qualification"])

    def test_working_copy_cannot_substitute_committed_bytes(self):
        self.batch()
        commit = self.commit_state()
        one, m = self.packet(name="before", commit=commit)
        (self.repos / MPS / "state/shadow.db").write_bytes(b"tampered checkout")
        two, n = self.packet(name="after", commit=commit)
        self.assertEqual(m, n)
        self.assertEqual((one / "corpus_evidence.json").read_bytes(),
                         (two / "corpus_evidence.json").read_bytes())

    def test_foreign_branch_unreachable_commit_and_symlink_refused(self):
        self.batch()
        commit = self.commit_state()
        repo = self.repos / MPS
        git(repo, "branch", "-m", "unrelated")
        with self.assertRaises(review.formal.ReviewError):
            self.packet(commit=commit)
        git(repo, "checkout", "--orphan", load_source(MPS).state_branch)
        git(repo, "rm", "-rf", "state")
        (repo / "state").mkdir()
        (repo / "state/clock.json").symlink_to("/tmp/absent")
        new = self.commit_state()
        with self.assertRaises(review.formal.ReviewError):
            self.packet(commit=commit)
        with self.assertRaises(review.formal.ReviewError):
            self.packet(commit=new)

    def test_source_mismatch_and_collector_provenance_refused(self):
        self.batch()
        state = self.repos / MPS / "state"
        ledger = next((state / "ledger").glob("*.json"))
        row = json.loads(ledger.read_text())
        row["collector_commit"] = "rehearsal"
        ledger.write_text(json.dumps(row))
        commit = self.commit_state()
        with self.assertRaisesRegex(ValueError, "full SHA"):
            self.packet(commit=commit)
        row["collector_commit"] = COMMIT
        row["source_slug"] = ENERGY
        ledger.write_text(json.dumps(row))
        commit = self.commit_state()
        with self.assertRaisesRegex(ValueError, "foreign source"):
            self.packet(commit=commit)

    def test_moit_source_surface_warning_reaches_formal_signoff(self):
        self.batch()
        state = self.repos / ENERGY / "state"
        ledger = next((state / "ledger").glob("*.json"))
        row = json.loads(ledger.read_text(encoding="utf-8"))
        warning = ("robots_content_type: https://moit.gov.vn/robots.txt "
                   "is a rules file served as 'text/html; charset=UTF-8'")
        row["source_anomalies"] = [warning]
        row["anomalies"] = []  # Distinct collector field must not mask this.
        ledger.write_text(json.dumps(row), encoding="utf-8")
        commit = self.commit_state(ENERGY)
        out, manifest = self.packet(ENERGY, "moit-source-warning", commit)
        tagged = "source-surface run %s: %s" % (row["run_id"], warning)
        self.assertIn(tagged, manifest["anomalies"])
        signoff = json.loads((out / "signoff_template.json").read_text(encoding="utf-8"))
        self.assertIn({"anomaly": tagged, "disposition": ""}, signoff["anomalies"])
        self.assertTrue(any("anomaly has no disposition" in problem
                            for problem in review.check_signoff(
                                out, out / "signoff_template.json")))

    def test_malformed_source_surface_warning_is_refused(self):
        self.batch()
        state = self.repos / ENERGY / "state"
        ledger = next((state / "ledger").glob("*.json"))
        row = json.loads(ledger.read_text(encoding="utf-8"))
        for index, bad in enumerate((None, "warning-as-string", [""],
                                     ["line\nbreak"], [3], ["repeat", "repeat"])):
            with self.subTest(bad=bad):
                row["source_anomalies"] = bad
                ledger.write_text(json.dumps(row), encoding="utf-8")
                commit = self.commit_state(ENERGY)
                with self.assertRaisesRegex(ValueError,
                                            "invalid source-surface anomaly evidence"):
                    self.packet(ENERGY, "invalid-surface-%s" % index, commit)

    def test_private_mps_only_collection_never_touches_moit_state(self):
        successful = []
        calls = []

        def record(state, slug, *args, **kwargs):
            calls.append(slug)
            return self.collector(state, slug, *args, **kwargs)

        remote.run_batch(
            self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
            0, 2, "mps-only", COMMIT, record,
            successful_sources=successful, private=True, sources=(MPS,))
        self.assertEqual(calls, [MPS])
        self.assertEqual(successful, [MPS])
        for slug in (ENERGY, INDUSTRY):
            self.assertFalse((self.repos / slug / "state").exists())
        self.assertEqual(review.review(self.repos / MPS / "state", MPS)["failures"], 0)

    def test_mps_only_scope_refused_outside_private_custody(self):
        with self.assertRaisesRegex(ValueError, "unapproved Vietnam source scope"):
            remote.run_batch(
                self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                0, 2, "mps-only", COMMIT, self.collector, sources=(MPS,))
        self.assertFalse((self.repos / MPS / "state").exists())

    def test_private_mps_only_failure_never_attempts_moit(self):
        calls = []

        def fail(state, slug, *args, **kwargs):
            calls.append(slug)
            return {"health": "fail", "result": "source_unavailable"}

        with self.assertRaisesRegex(ValueError, "batch has failed sources"):
            remote.run_batch(
                self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                0, 2, "mps-only", COMMIT, fail,
                private=True, sources=(MPS,))
        self.assertEqual(calls, [MPS])
        for slug in (ENERGY, INDUSTRY):
            self.assertFalse((self.repos / slug / "state").exists())

    def test_batch_failure_preserves_failure_and_attempts_independent_sources(self):
        calls = []
        def failure(state, slug, *args, **kwargs):
            calls.append(slug)
            return {"health": "fail", "result": "access_challenged"}
        with self.assertRaisesRegex(ValueError, "batch has failed sources"):
            self.batch(failure)
        self.assertEqual(calls, list(remote.SOURCES))
        self.assertFalse((self.repos / ENERGY / "state").exists())
        for slug in remote.SOURCES:
            self.assertNotEqual(remote.git(["rev-parse", "--verify", "HEAD"], self.repos / slug, check=False).returncode, 0)

    def test_failed_recovery_download_ignores_partial_set_and_keeps_moit_independent(self):
        text = (Path(remote.REPO) / '.github/workflows/vietnam_ministry_shadow.yml').read_text()
        self.assertIn('MPS_RECOVERY_OUTCOME: ${{ steps.mps_recovery.outcome }}', text)
        start = text.index('          if [ -n "${MPS_RECOVERY_ATTEMPTS:-}" ]; then')
        end = text.index('          python scripts/vietnam_ministry_remote.py', start)
        partial = self.root / 'vn-mps-recovery-zips'
        partial.mkdir()
        (partial / '1234567-1.zip').write_bytes(b'partial download')
        import os
        env = dict(os.environ, RUNNER_TEMP=str(self.root), MPS_RECOVERY_ATTEMPTS='1234567-1',
                   MPS_RECOVERY_OUTCOME='failure')
        script = 'set -eu\nset --\n' + text[start:end] + '\nprintf "%s\\n" "$@"'
        args = subprocess.check_output(['bash', '-c', script], env=env, text=True).splitlines()
        self.assertEqual(args[0], '--mps-recovery-zips')
        self.assertNotEqual(Path(args[1]), partial)
        self.assertFalse(Path(args[1]).exists())
        successful = []
        def collector(state, slug, *args, **kwargs):
            if slug == MPS:
                return collect(state, slug, *args, adapter=adapter(MPS), **kwargs)
            return self.collector(state, slug, *args, **kwargs)
        with self.assertRaisesRegex(ValueError, MPS):
            remote.run_batch(self.repos, self.gate, date(2026,10,5), date(2026,9,30),
                0, 2, 'recovery-failed', COMMIT, collector, successful_sources=successful,
                mps_recovery_dir=Path(args[1]), api=object())
        self.assertEqual(successful, [ENERGY, INDUSTRY])

    def test_one_failed_source_does_not_block_verified_sibling_state(self):
        successful = []
        def mixed(state, slug, *args, **kwargs):
            if slug == MPS:
                return {"health": "fail", "result": "listing_failure"}
            return self.collector(state, slug, *args, **kwargs)
        with self.assertRaisesRegex(ValueError, MPS):
            remote.run_batch(self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                             0, 2, "remote-test", COMMIT, mixed, successful_sources=successful)
        self.assertEqual(successful, [ENERGY, INDUSTRY])
        self.assertFalse((self.repos / MPS / "state").exists())
        for slug in successful:
            self.assertEqual(review.review(self.repos / slug / "state", slug)["failures"], 0)

    def test_success_list_contains_only_verified_families_after_validation_failure(self):
        successful = []
        def bad_review(state, slug, *args, **kwargs):
            result = self.collector(state, slug, *args, **kwargs)
            if slug == ENERGY:
                (state / "captures").joinpath("unexpected.bin").write_bytes(b"invalid")
            return result
        with self.assertRaises((ValueError, review.formal.ReviewError)):
            remote.run_batch(self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                             0, 2, "remote-test", COMMIT, bad_review, successful_sources=successful)
        self.assertEqual(successful, [MPS])

    def test_prior_moit_states_seed_same_gate_before_any_request(self):
        self.batch()
        for slug in remote.SOURCES:
            self.commit_state(slug)
        calls = []
        with patch.object(remote, "host_gate", side_effect=lambda state, gate: calls.append((state, gate))):
            remote.prepare(self.repos, self.gate)
        self.assertEqual([s.parent.name for s, _ in calls], list(remote.SOURCES))
        self.assertTrue(all(g == self.gate for _, g in calls))

    def test_bootstrap_rejects_imported_rehearsal_and_wrong_branch(self):
        (self.repos / MPS / "state").mkdir()
        with self.assertRaisesRegex(ValueError, "rehearsal"):
            self.batch()
        (self.repos / MPS / "state").rmdir()
        git(self.repos / MPS, "symbolic-ref", "HEAD", "refs/heads/main")
        with self.assertRaisesRegex(ValueError, "wrong state branch"):
            self.batch()

    def test_budget_and_commit_refused_before_collection(self):
        for cap, commit in [(3, COMMIT), (2, "unknown")]:
            with self.assertRaises(ValueError):
                remote.run_batch(self.repos, self.gate, date(2026, 10, 5), date(2026, 9, 30),
                                 0, cap, "test", commit)
        self.assertFalse((self.repos / MPS / "state").exists())

    def test_scheduled_target_resolution_and_rerun_guard(self):
        started = datetime(2026, 10, 8, 0, 45, tzinfo=timezone.utc)
        mps, moit, source = remote.resolve_targets(
            "schedule", "1", "18:17", started=started)
        self.assertEqual((mps, moit, source),
                         (date(2026, 10, 7), date(2026, 10, 7), SOURCE_SCHEDULE))
        with self.assertRaisesRegex(ValueError, "attempt 2"):
            remote.resolve_targets("schedule", "2", "18:17", started=started)
        with self.assertRaisesRegex(ValueError, "manual dispatch requires"):
            remote.resolve_targets("workflow_dispatch", "1", "18:17", started=started)
        mps, moit, source = remote.resolve_targets(
            "workflow_dispatch", "2", "18:17",
            date(2026, 10, 7), date(2026, 10, 7), started=started)
        self.assertEqual((mps, moit, source),
                         (date(2026, 10, 7), date(2026, 10, 7), SOURCE_EXPLICIT))

    def test_ministry_collect_preserves_schedule_target_source(self):
        state = self.repos / MPS / "state"
        entry = collect(
            state, MPS, date(2026, 10, 7), 0, 2, "scheduled-slot", COMMIT,
            adapter=adapter(MPS, [response(n) for n in BODIES[MPS]]),
            target_source=SOURCE_SCHEDULE)
        self.assertEqual(entry["target_date_source"], SOURCE_SCHEDULE)

    def test_historical_evidence_mutation_refused(self):
        self.batch()
        for slug in remote.SOURCES:
            self.commit_state(slug)
        def mutation(state, slug, *args, **kwargs):
            (state / "clock.json").write_text("{}")
            return {"health": "ok"}
        with self.assertRaisesRegex(ValueError, "historical evidence changed"):
            self.batch(mutation)

    def test_empty_and_early_signoff_never_complete(self):
        self.batch()
        out, m = self.packet()
        signoff = json.loads((out / "signoff_template.json").read_text())
        path = self.root / "signoff.json"
        path.write_text(json.dumps(signoff))
        self.assertIn("checkpoint not reached", review.check_signoff(out, path))
        self.assertTrue(any("reviewer is empty" in p for p in review.check_signoff(out, path)))
        signoff["source_slug"] = ENERGY
        path.write_text(json.dumps(signoff))
        self.assertIn("signoff belongs to another source", review.check_signoff(out, path))

    def test_reached_checkpoint_complete_signoff_and_typed_answers(self):
        state = self.repos / MPS / "state"
        for run_id, day in (("day-zero", 7), ("day-seven", 14)):
            with patch("scripts.shadow_collect_vietnam.datetime", wraps=datetime) as clock:
                clock.now.return_value = datetime(2026, 10, day, 12, tzinfo=timezone.utc)
                self.collector(state, MPS, date(2026, 10, 5), 0, 2, run_id, COMMIT)
        out, m = self.packet()
        self.assertTrue(m["checkpoint_reached"])
        self.assertEqual(m["latest_shadow_day"], 7)
        self.assertTrue(m["missing_collecting_days"])
        signoff = json.loads((out / "signoff_template.json").read_text())
        signoff.update(reviewer="Offline synthetic reviewer", attestation="Test answers only",
                       review_started_utc="2026-10-14T13:00:00+00:00",
                       review_completed_utc="2026-10-14T14:00:00+00:00", verdict="pass_with_findings")
        for record in signoff["records"]:
            record.update({field: True for field in review.formal.CHECK_FIELDS})
        for anomaly in signoff["anomalies"]:
            anomaly["disposition"] = "Synthetic test gap, not a reliability claim"
        path = self.root / "signoff.json"
        path.write_text(json.dumps(signoff))
        self.assertEqual(review.check_signoff(out, path), [])
        signoff["records"][0]["source_page_opened"] = "yes"
        path.write_text(json.dumps(signoff))
        self.assertTrue(any("must be true or false" in p for p in review.check_signoff(out, path)))

    def test_unknown_file_and_damaged_capture_never_formalize(self):
        self.batch()
        state = self.repos / MPS / "state"
        (state / "unrelated.json").write_text("{}")
        commit = self.commit_state()
        with self.assertRaises(review.formal.ReviewError):
            self.packet(commit=commit)
        (state / "unrelated.json").unlink()
        capture = next((state / "captures").glob("*.bin"))
        capture.write_bytes(b"damaged")
        commit = self.commit_state()
        with self.assertRaisesRegex(ValueError, "capture missing or changed"):
            self.packet(commit=commit)

    def test_quiet_formal_packet_cannot_receive_plain_pass(self):
        state = self.repos / MPS / "state"
        collect(state, MPS, date(2026, 10, 6), 0, 2, "quiet", COMMIT, adapter=adapter(MPS))
        out, m = self.packet()
        self.assertEqual(m["required_review_records"], [])
        self.assertNotIn("pass", m["allowed_verdicts"])

    def test_tampered_packet_refused(self):
        self.batch()
        out, m = self.packet()
        (out / "corpus_evidence.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            review.check_signoff(out, out / "signoff_template.json")

    def test_public_original_writer_is_retired_and_historical_path_is_preserved(self):
        text = (Path(remote.REPO) / ".github/workflows/vietnam_ministry_shadow.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertIn("  shadow:\n    if: false", text)
        self.assertIn("target_date:", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("--gate-dir", text)
        self.assertIn("--lookback 6 --cap 40", text)
        self.assertIn("--event-name", text)
        self.assertIn("--run-attempt", text)
        self.assertIn('--cron-utc "18:17"', text)
        self.assertIn("scheduled reliability state branch missing", text)
        self.assertIn('test -f "$dest/state/clock.json"', text)
        self.assertIn("ref: ${{ github.sha }}", text)
        self.assertIn("steps.preservation.outcome == 'success'", text)
        self.assertIn('--publication-list "${RUNNER_TEMP}/vn-ministry-successful-sources"', text)
        self.assertIn('done < "$publication_list"', text)
        self.assertIn("if: always()", text)
        self.assertIn("retention-days: 90", text)
        self.assertNotIn("*/state/", text)
        for slug in remote.SOURCES:
            self.assertIn("vn-ministry-state/%s/state/" % slug, text)
        self.assertIn('HEAD:refs/heads/${branch}', text)
        self.assertNotIn("--force", text)
        self.assertNotIn("strategy:", text)
