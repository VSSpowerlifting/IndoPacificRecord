"""Finite-feed continuity and provider recovery; only measured source fixtures."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.collection.vietnam_rss_frontier import stitch
from scraper.sources.vn_shadow_http import Raw
from scripts import vietnam_mps_rss_history as history
from tests.test_vn_ministry_adapters import FIX, adapter, MPS


class RSSFrontier(unittest.TestCase):
    def setUp(self):
        self.a = adapter(MPS)
        payload = (FIX / 'mps-rss-34.bin').read_bytes()
        self.items, _ = self.a._rss(Raw(self.a.profile.listing, 200,
            {'content-type': 'application/xml'}, payload, False, '2026-10-06T00:00:00+00:00'))

    def snap(self, items, day):
        return {'items': copy.deepcopy(items), 'sha256': str(day),
                'retrieved_at': '2026-10-%02dT00:00:00+00:00' % day}

    def test_overlapping_feed_recovers_late_item_and_keeps_older_window(self):
        # An actual Oct 5 item appears behind another Oct 5 item on the next
        # simulated observation. No fabricated publisher identity/text/date.
        old = [self.items[0]] + self.items[2:]
        newer = self.items[:3]
        selected, chain = stitch([self.snap(old, 6), self.snap(newer, 7)],
                                 '2026-09-30', '2026-10-05')
        self.assertEqual({i['url'] for i in selected}, {i['url'] for i in self.items[:5]})
        self.assertEqual(chain, ['6', '7'])

    def test_complete_turnover_cannot_be_called_a_quiet_day(self):
        with self.assertRaisesRegex(ValueError, 'no surviving identity'):
            stitch([self.snap(self.items[4:], 6), self.snap(self.items[:3], 7)],
                   '2026-09-30', '2026-10-05')

    def test_unknown_window_boundary_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'no proven window boundary'):
            stitch([self.snap(self.items[:3], 6)], '2026-09-30', '2026-10-05')

    def test_disappearance_above_new_tail_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'disappeared'):
            stitch([self.snap(self.items, 6), self.snap([self.items[0], self.items[2]], 7)],
                   '2026-09-30', '2026-10-05')

    def test_date_drift_order_drift_and_budget_are_refused(self):
        changed = copy.deepcopy(self.items[:3])
        changed[0]['rss_instant_utc'] = self.items[1]['rss_instant_utc']
        with self.assertRaisesRegex(ValueError, 'timestamp changed'):
            stitch([self.snap(self.items, 6), self.snap(changed, 7)],
                   '2026-09-30', '2026-10-05')
        with self.assertRaisesRegex(ValueError, 'newest-first'):
            stitch([self.snap(list(reversed(self.items)), 6)], '2026-10-06', '2026-10-06')
        with self.assertRaises(ValueError):
            stitch([self.snap(self.items, 6)] * 65, '2026-10-01', '2026-10-05')

    def test_replaying_unchanged_snapshots_is_idempotent(self):
        a, _ = stitch([self.snap(self.items, 6)], '2026-10-01', '2026-10-05')
        b, _ = stitch([self.snap(self.items, 6), self.snap(self.items, 7)],
                       '2026-10-01', '2026-10-05')
        self.assertEqual(a, b)

    def zip_case(self):
        payload = (FIX / 'mps-rss-34.bin').read_bytes()
        cap = {'role': 'listing', 'url': self.a.profile.listing, 'http_status': 200,
               'payload_bytes': len(payload), 'payload_sha256': hashlib.sha256(payload).hexdigest(),
               'content_type': 'application/xml', 'retrieved_at': '2026-10-06T00:00:00+00:00'}
        row = {'run_id': '1234567-1', 'source_slug': MPS, 'health': 'fail',
               'collector_commit': 'a' * 40, 'target_date_source': 'schedule-slot', 'captures': [cap]}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr(history.MEMBER + 'ledger/20261006T000001+0000-1234567-1.json', json.dumps(row))
            z.writestr(history.MEMBER + 'captures/' + cap['payload_sha256'] + '.bin', payload)
        payload = buf.getvalue()
        artifact = {'id': 123, 'name': 'vietnam-ministry-shadow-1234567-1', 'expired': False,
                    'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(), 'size_in_bytes': len(payload)}
        run = {'id': 1234567, 'run_attempt': 1, 'event': 'schedule', 'path': history.WORKFLOW,
               'status': 'completed', 'conclusion': 'failure', 'head_sha': 'a' * 40,
               'run_started_at': '2026-10-05T23:59:00Z', 'updated_at': '2026-10-06T00:01:00Z'}
        class API:
            def get(self, path):
                return {'total_count': 1, 'artifacts': [artifact]} if '/artifacts?' in path else run
        return payload, artifact, run, API()

    def test_provider_digest_and_attempt_are_required_before_recovery(self):
        payload, artifact, run, api = self.zip_case()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '1234567-1.zip'
            path.write_bytes(payload)
            feeds, proof = history.recovery(self.a, tmp, api)
            self.assertEqual(len(feeds), 1)
            self.assertEqual(proof[0]['historical_health'], 'fail')
            self.assertEqual(self.a.evidence[0]['role'], 'recovery_listing')
            for field, bad in [('digest', 'sha256:' + '0' * 64), ('expired', True)]:
                old = artifact[field]; artifact[field] = bad
                with self.assertRaises(ValueError): history.recovery(self.a, tmp, api)
                artifact[field] = old
            run['head_sha'] = 'b' * 40
            with self.assertRaisesRegex(ValueError, 'provenance'):
                history.recovery(self.a, tmp, api)

    def test_wrong_workflow_and_changed_zip_are_refused(self):
        payload, _, run, api = self.zip_case()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '1234567-1.zip'; path.write_bytes(payload)
            run['path'] = 'unrelated.yml'
            with self.assertRaises(ValueError): history.recovery(self.a, tmp, api)
            run['path'] = history.WORKFLOW
            path.write_bytes(payload + b'tamper')
            with self.assertRaises(ValueError): history.recovery(self.a, tmp, api)

    def test_provider_digested_malformed_zip_is_a_bounded_source_failure(self):
        _, artifact, _, api = self.zip_case()
        payload = b'not a ZIP'
        artifact.update(digest='sha256:'+hashlib.sha256(payload).hexdigest(),size_in_bytes=len(payload))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'1234567-1.zip').write_bytes(payload)
            with self.assertRaisesRegex(ValueError,'malformed authenticated'):
                history.recovery(self.a,tmp,api)
