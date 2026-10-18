"""Offline ceiling and opaque-retry controls for the authorized release only."""
from contextlib import contextmanager
from decimal import Decimal
import json
from types import SimpleNamespace as NS
import unittest

from core.title_translation import SYSTEM, TOOL
from scripts.china_title_release_batch import (CAP, ReservedMessages, charged,
                                               reserve, settle)


def request():
    return dict(model='claude-sonnet-4-6', max_tokens=512, temperature=0.0,
                system=[{'type': 'text', 'text': SYSTEM}], tools=[TOOL],
                tool_choice={'type': 'tool', 'name': 'emit_title'},
                messages=[{'role': 'user', 'content': json.dumps({'headline': 'synthetic headline'})}])


def response():
    return NS(id='synthetic', usage=NS(input_tokens=500, output_tokens=50,
              cache_creation_input_tokens=0, cache_read_input_tokens=0,
              inference_geo='global', service_tier='standard'))


class TitleReleaseBudget(unittest.TestCase):
    def test_reservation_survives_crash_reload_and_blocks_next_batch(self):
        ledger = {'batches': []}
        reserve(ledger, 20)
        ledger = json.loads(json.dumps(ledger))
        self.assertEqual(charged(ledger), Decimal('2.01'))
        with self.assertRaises(RuntimeError):
            reserve(ledger, 10)
        self.assertEqual(len(ledger['batches']), 1)
        reserve(ledger, 9)
        self.assertLessEqual(charged(ledger), CAP)

    def test_reports_settle_but_missing_failures_retain_full_allowance(self):
        ledger = {'batches': []}
        batch = reserve(ledger, 20)
        first = batch['requests'][1]
        first['model'] = 'claude-sonnet-4-6'
        settle(first, response())
        self.assertAlmostEqual(float(charged(ledger)), 1.91225)
        self.assertEqual(first['usage']['output_tokens'], 50)
        self.assertNotIn('charged_usd', batch['requests'][2])

    def test_unexpected_usage_never_refunds(self):
        for usage in (None, NS(), NS(input_tokens=None,output_tokens=None),
                      NS(input_tokens=True,output_tokens=1),
                      NS(input_tokens=100000,output_tokens=50)):
            with self.subTest(usage=usage):
                entry = {'model': 'claude-sonnet-4-6', 'reserved_usd': '.1'}
                r = response(); r.usage = usage
                with self.assertRaises(RuntimeError):
                    settle(entry, r)
                self.assertNotIn('charged_usd', entry)

    def test_residency_surcharge_and_unknown_geo_are_charged_conservatively(self):
        for geo in ('us',None):
            entry={'model':'claude-sonnet-4-6','reserved_usd':'.1'}
            r=response();r.usage.inference_geo=geo
            settle(entry,r)
            self.assertEqual(Decimal(entry['charged_usd']),Decimal('.002475'))
            self.assertEqual(entry['pricing_uncertain'],geo is None)
        for change in ({'service_tier':'priority'},{'inference_geo':'unexpected'}):
            entry={'model':'claude-sonnet-4-6','reserved_usd':'.1'}
            r=response()
            for key,value in change.items():setattr(r.usage,key,value)
            with self.assertRaises(RuntimeError):settle(entry,r)
            self.assertNotIn('charged_usd',entry)

    def test_only_fixed_envelope_reaches_one_paid_request(self):
        class Fake:
            calls = 0
            def count_tokens(self, **kw):
                return NS(input_tokens=500)
            @contextmanager
            def stream(self, **kw):
                self.assert_tier = kw['service_tier']
                self.calls += 1
                yield NS(get_final_message=response)
        fake = Fake()
        entry = {'reserved_usd': '.1'}
        client = ReservedMessages(fake, [entry])
        for update in ({'max_tokens': 513}, {'system': []}, {'tools': []},
                       {'extra_headers': {'x': 'y'}},
                       {'messages': [{'role': 'user', 'content': 'x'*5000}]}):
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                with client.stream(**dict(request(), **update)):
                    self.fail('out-of-envelope request admitted')
        self.assertEqual(fake.calls, 0)
        with client.stream(**request()) as stream:
            self.assertEqual(stream.get_final_message().id, 'synthetic')
        self.assertEqual(fake.calls, 1)
        self.assertEqual(fake.assert_tier,'standard_only')
        self.assertIn('charged_usd', entry)
        with self.assertRaises(RuntimeError):
            with client.stream(**request()):
                self.fail('second call admitted without reservation')

    def test_count_gate_failure_makes_no_paid_call(self):
        fake = NS(count_tokens=lambda **kw: NS(input_tokens=4097))
        with self.assertRaises(RuntimeError):
            with ReservedMessages(fake, [{'reserved_usd': '.1'}]).stream(**request()):
                self.fail('token admission passed')

    def test_transport_failure_stays_reserved(self):
        class Fake:
            def count_tokens(self, **kw):
                return NS(input_tokens=500)
            @contextmanager
            def stream(self, **kw):
                raise ConnectionError('ambiguous synthetic failure')
                yield
        entry = {'reserved_usd': '.1'}
        with self.assertRaises(ConnectionError):
            with ReservedMessages(Fake(), [entry]).stream(**request()):
                self.fail('connection passed')
        self.assertNotIn('charged_usd', entry)


if __name__ == '__main__':
    unittest.main()
