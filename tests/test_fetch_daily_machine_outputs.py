"""Delivery failures cannot masquerade as fresh signed inputs or stop peers."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import fetch_daily_machine_outputs as fetch
from processing.daily_intake import load_policy


class FetchOutputs(unittest.TestCase):
    def run_fetch(self, outcomes, policy=None):
        root = Path(self.tmp.name)
        for family in fetch.SOURCES:
            (root / (family + '.json')).write_text('old envelope')
        env = {'IPR_PRIVATE_DAILY_ENABLED': 'true',
               'IPR_DAILY_INTAKE_DIR': str(root),
               'GITHUB_OUTPUT': str(root / 'outputs'),
               'GITHUB_STEP_SUMMARY': str(root / 'summary')}
        with patch.dict(os.environ, env), patch.object(fetch, 'load_policy', return_value=policy or load_policy()), patch.object(fetch.subprocess, 'run', side_effect=outcomes) as call:
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
        for body in [b'{', b'[]', b'null', b'"value"', b'\xff']:
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

    def test_existing_health_gate_reports_fetch_failure_after_delivery(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/daily_update.yml').read_text()
        self.assertIn('id: shared_daily_fetch', workflow)
        health = workflow[workflow.index('      - name: Health gate'):]
        self.assertIn('steps.shared_daily_fetch.outputs.failed_families', health)
        self.assertIn('Shared Daily handoff failed', health)
        self.assertLess(workflow.index('- name: Deploy to GitHub Pages'), workflow.index('- name: Health gate'))


if __name__ == '__main__':
    unittest.main()
