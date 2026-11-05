"""Delivery failures cannot masquerade as fresh signed inputs or stop peers."""
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import fetch_daily_machine_outputs as fetch
from processing.daily_intake import load_policy


class FetchOutputs(unittest.TestCase):
    def run_fetch(self, outcomes, policy=None, heartbeat='2026-11-03T04:05:06Z'):
        root = Path(self.tmp.name)
        for family in fetch.SOURCES:
            (root / (family + '.json')).write_text('old envelope')
        env = {'IPR_PRIVATE_DAILY_ENABLED': 'true',
               'IPR_DAILY_INTAKE_DIR': str(root),
               'GITHUB_OUTPUT': str(root / 'outputs'),
               'GITHUB_STEP_SUMMARY': str(root / 'summary')}
        with patch.dict(os.environ, env), patch.object(fetch, 'load_policy', return_value=policy or load_policy()), patch.object(fetch.subprocess, 'run', side_effect=outcomes) as call, \
                patch.object(fetch, '_collector_heartbeat', return_value=heartbeat) as self.beat_call:
            result = fetch.main()
        return root, result, call

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    @staticmethod
    def response(body=b'{"packet":{},"mac":"test-only"}', code=0):
        return subprocess.CompletedProcess([], code, body, b'private stderr must never be logged')

    def test_failure_removes_stale_envelope_and_continues_peers(self):
        root, result, call = self.run_fetch([self.response(code=1), self.response(), self.response()])
        families = list(fetch.SOURCES)
        self.assertFalse((root / (families[0] + '.json')).exists())
        self.assertEqual(result[families[0]], 'fetch_failed')
        self.assertEqual(json.loads((root / (families[1] + '.json')).read_bytes()), {'packet': {}, 'mac': 'test-only'})
        self.assertEqual(call.call_count, 3)
        self.assertEqual((root / 'outputs').read_text(), 'failed_families=1\n')
        self.assertNotIn('private stderr', (root / 'summary').read_text())
        self.assertFalse(list(root.glob('*.tmp')))

    def test_timeout_unavailable_and_oversize_never_leave_old_input(self):
        for failure in [subprocess.TimeoutExpired('gh', 45), OSError('unavailable'), self.response(b'x' * 512001)]:
            with self.subTest(failure=type(failure).__name__):
                root, result, _ = self.run_fetch([failure, self.response(), self.response()])
                self.assertFalse((root / 'ph_afp_articles.json').exists())
                self.assertNotEqual(result['ph_afp_articles'], 'fetched')

    def test_malformed_nonobject_and_invalid_encoding_are_isolated(self):
        nested = b'{"value":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}'
        for body in [b'{', b'[]', b'null', b'"value"', b'\xff', nested]:
            with self.subTest(body=body):
                root, result, _ = self.run_fetch([self.response(body), self.response(), self.response()])
                self.assertEqual(result['ph_afp_articles'], 'envelope_malformed')
                self.assertFalse((root / 'ph_afp_articles.json').exists())
                self.assertEqual(result['id_kemhan_news'], 'fetched')

    def test_policy_disabled_removes_stale_input_without_api_call(self):
        policy = copy.deepcopy(load_policy())
        policy['sources']['ph_afp_articles']['unattended_release'] = False
        root, result, call = self.run_fetch([self.response(), self.response()], policy)
        self.assertEqual(result['ph_afp_articles'], 'policy_disabled')
        self.assertFalse((root / 'ph_afp_articles.json').exists())
        self.assertEqual(call.call_count, 2)
        self.assertEqual((root / 'outputs').read_text(), 'failed_families=0\n')

    def test_annotations_do_not_disclose_response_or_stderr(self):
        from contextlib import redirect_stdout
        from io import StringIO
        stream = StringIO()
        with redirect_stdout(stream):
            self.run_fetch([self.response(b'private malformed bytes'), self.response(), self.response()])
        self.assertIn('Shared Daily handoff unavailable', stream.getvalue())
        self.assertNotIn('private malformed bytes', stream.getvalue())
        self.assertNotIn('private stderr', stream.getvalue())

    def test_collector_heartbeat_sidecar_is_written_per_family_and_never_signed(self):
        root, result, _ = self.run_fetch([self.response(), self.response(), self.response()])
        for family in fetch.SOURCES:
            sidecar = root / (family + '.collection.json')
            self.assertEqual(json.loads(sidecar.read_text()),
                             {'collector_last_run_at': '2026-11-03T04:05:06Z'})
        self.assertEqual([c.args[0] for c in self.beat_call.call_args_list],
                         [s.custody_ref for s in fetch.SOURCES.values()])
        self.assertFalse(list(root.glob('*.tmp')))
        self.assertIn('collector heartbeat: ok', (root / 'summary').read_text())

    def test_heartbeat_is_recorded_even_when_the_envelope_fetch_fails(self):
        root, result, _ = self.run_fetch([self.response(code=1), self.response(), self.response()])
        self.assertEqual(result['ph_afp_articles'], 'fetch_failed')
        self.assertTrue((root / 'ph_afp_articles.collection.json').exists())

    def test_unreadable_heartbeat_is_a_warning_not_a_delivery_failure(self):
        from contextlib import redirect_stdout
        from io import StringIO
        stream = StringIO()
        for bad in (None, 'not-a-date', '2026-11-03 04:05:06', 'x' * 100):
            with self.subTest(bad=bad), redirect_stdout(stream):
                root, result, _ = self.run_fetch(
                    [self.response(), self.response(), self.response()], heartbeat=bad)
                self.assertFalse((root / 'ph_afp_articles.collection.json').exists())
                self.assertEqual(result['ph_afp_articles'], 'fetched')
                self.assertEqual((root / 'outputs').read_text().splitlines()[-1], 'failed_families=0')
        self.assertIn('Shared Daily collector heartbeat unavailable', stream.getvalue())

    def test_stale_heartbeat_never_survives_a_refresh(self):
        root = Path(self.tmp.name)
        for family in fetch.SOURCES:
            fetch.write_heartbeat(root, family, '2026-01-01T00:00:00Z')
        policy = copy.deepcopy(load_policy())
        policy['sources']['ph_afp_articles']['unattended_release'] = False
        root, result, _ = self.run_fetch([self.response(), self.response()], policy, heartbeat=None)
        self.assertEqual(result['ph_afp_articles'], 'policy_disabled')
        for family in fetch.SOURCES:
            self.assertFalse((root / (family + '.collection.json')).exists(), family)

    def test_heartbeat_query_reads_commit_metadata_only(self):
        ok = subprocess.CompletedProcess([], 0, b'2026-11-03T04:05:06Z\n', b'private stderr')
        with patch.object(fetch.subprocess, 'run', return_value=ok) as call:
            self.assertEqual(fetch._collector_heartbeat('archive/ph-nsc'), '2026-11-03T04:05:06Z')
        argv = call.call_args.args[0]
        self.assertIn('repos/%s/commits?sha=archive/ph-nsc&per_page=1' % fetch.PRIVATE_REPO, argv)
        self.assertIn('.[0].commit.committer.date', argv)
        self.assertFalse(any('contents' in part for part in argv))
        for failure in (subprocess.CompletedProcess([], 1, b'', b'x'), OSError('gh'),
                        subprocess.TimeoutExpired('gh', 45)):
            with patch.object(fetch.subprocess, 'run', side_effect=[failure]
                              if not isinstance(failure, subprocess.CompletedProcess)
                              else None, return_value=failure):
                self.assertIsNone(fetch._collector_heartbeat('archive/ph-nsc'))

    def test_existing_health_gate_reports_fetch_failure_after_delivery(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/daily_update.yml').read_text()
        self.assertIn('id: shared_daily_fetch', workflow)
        health = workflow[workflow.index('      - name: Health gate'):]
        self.assertIn('steps.shared_daily_fetch.outputs.failed_families', health)
        self.assertIn('Shared Daily handoff failed', health)
        self.assertLess(workflow.index('- name: Deploy to GitHub Pages'), workflow.index('- name: Health gate'))

    def test_partial_refresh_preserves_accepted_peer_and_admits_healthy_source(self):
        """Synthetic MACs/fixtures exercise the real fetch -> admission boundary."""
        from tests.test_reconcile import migrate
        from tests.test_migrations import build_legacy_db
        from processing import daily_intake as intake
        from processing.daily_runner import intake_family
        from tests.test_philippines_shared_daily import record, reading, fake_analyzer

        policy = load_policy()
        keys = {family: 'synthetic-' + family * 3 for family in fetch.SOURCES}

        def public_intake(db, root):
            # Runtime migration 3: pipeline.run_governed_manual_sources dispatches
            # each family on its own through intake_family. A family whose
            # envelope the fetch removed returns None and is absent here; the
            # others report the same admitted/holds receipt as before.
            result = {}
            for family in fetch.SOURCES:
                receipt = intake_family(db, root, family, policy=policy)
                if receipt is not None:
                    result[family] = {k: receipt[k] for k in ('admitted', 'holds')}
            return result

        envelopes = {}
        records = {}
        for family, label in [('ph_afp_articles', 'AFP'), ('ph_nsc_official_statements', 'NSC')]:
            item = record()
            item.update(source_family=family, source_identity=label.lower() + ':1')
            if label == 'NSC':
                item.update(official_issuer=None, official_publisher='ph_nsc',
                            canonical_official_url='https://nsc.gov.ph/2026/10/19/synthetic-test/')
            reply = reading()
            reply['summary_english'] = reply['summary_english'].replace('AFP', label)
            for fact in reply['facts']:
                fact['sentence'] = fact['sentence'].replace('AFP', label)
            state, _ = intake.process([item], {}, family=family, policy=policy,
                                      analyzer_factory=lambda: fake_analyzer(reply))
            self.assertEqual(state[family + ':' + item['source_identity']]['status'], 'complete')
            envelopes[family] = intake.sign_outputs(state, family=family, policy=policy, key=keys[family])
            records[family] = item
        envelopes['id_kemhan_news'] = intake.sign_outputs({}, family='id_kemhan_news',
                                                         policy=policy, key=keys['id_kemhan_news'])
        env = {fetch.SOURCES[f].key_env: key for f, key in keys.items()}
        for failed in records:
            with self.subTest(failed=failed):
                db = Path(self.tmp.name) / (failed + '.db')
                build_legacy_db(db)
                migrate(db)
                with sqlite3.connect(db) as conn:
                    for item in records.values():
                        conn.execute('INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                            item['source_family'], item['source_identity'], 'philippines',
                            item['canonical_official_url'], item['publisher_posted_date'],
                            item['official_issuer'], item['official_publisher'], None, 'c' * 40,
                            item['metadata_version_sha256'], item['source_run'], 'official_link_only',
                            'd' * 64, '2026-10-19T00:00:00Z'))
                    intake.admit(conn, envelopes[failed], family=failed, policy=policy, key=keys[failed])
                    old = conn.execute('SELECT * FROM daily_machine_records').fetchone()
                outcomes = [self.response(code=1) if f == failed else
                            self.response(json.dumps(envelopes[f]).encode()) for f in fetch.SOURCES]
                root, result, _ = self.run_fetch(outcomes)
                with patch.dict(os.environ, env):
                    admitted = public_intake(db, root)
                    second = public_intake(db, root)
                healthy = next(f for f in records if f != failed)
                self.assertNotIn(failed, admitted)
                self.assertEqual(admitted[healthy], {'admitted': 1, 'holds': []})
                self.assertEqual(second[healthy], {'admitted': 0, 'holds': []})
                self.assertEqual(admitted['id_kemhan_news'], {'admitted': 0, 'holds': []})
                with sqlite3.connect(db) as conn:
                    self.assertEqual(conn.execute('SELECT * FROM daily_machine_records WHERE source_family=?',
                                                  (failed,)).fetchone(), old)
                self.assertEqual(result[failed], 'fetch_failed')

    def test_health_shell_notifies_for_failure_and_accepts_quiet_or_skipped_fetch(self):
        import textwrap
        workflow = (Path(__file__).resolve().parents[1] /
                    '.github/workflows/daily_update.yml').read_text()
        health = workflow.split('      - name: Health gate\n', 1)[1]
        shell = textwrap.dedent(health.split('        run: |\n', 1)[1])
        root = Path(self.tmp.name)
        (root / 'scripts').mkdir()
        # Isolate the unchanged liveness check; execute the actual Health shell.
        (root / 'scripts/check_source_liveness.py').write_text('raise SystemExit(0)\n')
        import sys
        (root / 'bin').mkdir()
        (root / 'bin/python').symlink_to(sys.executable)
        for count in ('1', '0', ''):
            env = dict(os.environ, SHARED_DAILY_FETCH_FAILURES=count, TODAY_NY='2026-11-03',
                       PATH=str(root / 'bin') + os.pathsep + os.environ['PATH'])
            result = subprocess.run(['bash', '-c', shell], cwd=root, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1 if count == '1' else 0, result.stderr)
            self.assertEqual('::error title=Shared Daily handoff failed::' in result.stdout,
                             count == '1')


if __name__ == '__main__':
    unittest.main()
