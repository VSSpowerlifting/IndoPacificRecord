"""Incumbent request/acceptance contract, with no provider or production writes.

Request digests were captured by executing the exact pre-PR base analyzer and
prompts with FakeClient. Candidate message digests pin the evaluated PR revision.
They are fixed oracles, not recomputed expectations from the code under test.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import analysis.analyzer as engine
from analysis import fidelity, prompts
from tests.test_llm_usage_telemetry import (
    FakeClient, analyzer_for, text_response, tool_response, status_error,
    RELEVANCE_JSON, SUMMARY_JSON, CATEGORY_JSON, SONNET, HAIKU,
)

CONTRACT = json.loads((Path(__file__).parent / 'fixtures' /
                       'task_model_incumbent_contract.json').read_text())
CHEAP = 'claude-haiku-5-5'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


class IncumbentBehavior(unittest.TestCase):
    def setUp(self):
        settings = mock.patch.multiple(
            engine, ANALYSIS_MODEL=SONNET, RELEVANCE_MODEL=HAIKU,
            TRANSLATION_MODEL='', SUMMARY_MODEL='', CATEGORIZATION_MODEL='',
            FALLBACK_MODEL='', MODEL_FIDELITY_CANDIDATE_ENABLED=False,
            RELEVANCE_TOOL_OUTPUT_ENABLED=False)
        settings.start()
        self.addCleanup(settings.stop)

    def test_empty_overrides_match_frozen_base_requests_and_results(self):
        cases = [
            ('relevance', 'score_relevance', text_response(RELEVANCE_JSON), False),
            ('translation', 'translate', tool_response({
                'title_en': 'Translated title', 'body_en': 'Translated body.'}), True),
            ('summary', 'summarize', text_response(SUMMARY_JSON), False),
            ('categorization', 'categorize', text_response(CATEGORY_JSON), False),
        ]
        for task, method, response, streamed in cases:
            with self.subTest(task=task):
                c = FakeClient(**{'streams' if streamed else 'creates': [response]})
                result = getattr(analyzer_for(c), method)(*CONTRACT['input'])
                self.assertEqual(json.loads(json.dumps(result)), CONTRACT['results'][task])
                request = (c.stream_kwargs if streamed else c.create_kwargs)[0]
                self.assertEqual(digest(request), CONTRACT['requests'][task])
        self.assertEqual(hashlib.sha256(Path(prompts.__file__).read_bytes()).hexdigest(),
                         CONTRACT['source_sha256']['analysis/prompts.py'])
        self.assertEqual(analyzer_for(FakeClient())._china_prompt_version, 'v1')

    def test_fallback_uses_exact_incumbent_request_for_every_task(self):
        # Each first response fails an incumbent check. Model selection alone
        # must not select the evaluated prompts or stricter acceptance rules.
        cases = [
            ('relevance', 'score_relevance', text_response('{}'),
             text_response(RELEVANCE_JSON), 'RELEVANCE_MODEL', HAIKU, False),
            ('translation', 'translate', tool_response({'title_en': '', 'body_en': ''}),
             tool_response({'title_en': 'Translated title', 'body_en': 'Translated body.'}),
             'TRANSLATION_MODEL', SONNET, True),
            ('summary', 'summarize', text_response('{}'), text_response(SUMMARY_JSON),
             'SUMMARY_MODEL', SONNET, False),
            ('categorization', 'categorize', text_response('invalid JSON'),
             text_response(CATEGORY_JSON), 'CATEGORIZATION_MODEL', SONNET, False),
        ]
        for task, method, bad, good, override, incumbent, streamed in cases:
            with self.subTest(task=task):
                c = FakeClient(**{'streams' if streamed else 'creates': [bad, good]})
                with mock.patch.multiple(engine, **{override: CHEAP, 'FALLBACK_MODEL': incumbent}):
                    result = getattr(analyzer_for(c), method)(*CONTRACT['input'])
                self.assertEqual(json.loads(json.dumps(result)), CONTRACT['results'][task])
                requests = c.stream_kwargs if streamed else c.create_kwargs
                self.assertEqual(len(requests), 2)
                self.assertEqual(digest(requests[1]), CONTRACT['requests'][task])

    def test_category_acceptance_remains_incumbent_with_overrides_and_fallback(self):
        cases = [
            ({'categories': ['invented', 'taiwan', 'taiwan'], 'significance': 'false'},
             (['taiwan', 'taiwan'], True, None)),
            ({'categories': ['taiwan']}, (['taiwan'], False, None)),
            ({'categories': [], 'significance': True}, ([], True, None)),
        ]
        for payload, expected in cases:
            for fallback in (False, True):
                with self.subTest(payload=payload, fallback=fallback):
                    responses = ([text_response('invalid JSON')] if fallback else [])
                    responses.append(text_response(json.dumps(payload)))
                    c = FakeClient(creates=responses)
                    with mock.patch.multiple(engine, CATEGORIZATION_MODEL=CHEAP,
                                             FALLBACK_MODEL=SONNET if fallback else ''):
                        self.assertEqual(analyzer_for(c).categorize('T', 'B'), expected)
                    self.assertEqual(len(c.create_kwargs), 2 if fallback else 1)

    def test_false_byline_hold_and_semantic_guards_are_inactive_by_default(self):
        c = FakeClient(streams=[tool_response({'title_en': 'Report',
                    'body_en': 'By PLA Daily reporter Lu Dongfang.'})],
                       creates=[text_response('{"summary":"A simulated submarine."}')])
        a = analyzer_for(c)
        with mock.patch.multiple(engine, TRANSLATION_MODEL=CHEAP, SUMMARY_MODEL=CHEAP,
                                 FALLBACK_MODEL=SONNET), \
                mock.patch('analysis.fidelity.check', side_effect=AssertionError('candidate ran')):
            self.assertEqual(a.translate('标题', '解放军报记者 卢东方 ')[1],
                             'By PLA Daily reporter Lu Dongfang.')
            self.assertEqual(a.summarize('Training', 'Blue Force submarine; simulated attack.'),
                             'A simulated submarine.')
        self.assertEqual(len(c.stream_kwargs) + len(c.create_kwargs), 2)

    def test_category_failure_retains_good_summary_even_after_fallback_exhaustion(self):
        for fallback in ('', CHEAP):
            with self.subTest(fallback=fallback):
                class Client(FakeClient):
                    def create(client, **kwargs):
                        client.create_kwargs.append(kwargs)
                        return text_response(SUMMARY_JSON if kwargs['max_tokens'] == 1000
                                             else 'invalid JSON')
                a = analyzer_for(Client())
                with mock.patch.object(a, 'score_relevance', return_value=(.9, 'source')), \
                        mock.patch.object(a, 'translate', return_value=('T', 'B')), \
                        mock.patch.object(engine, 'FALLBACK_MODEL', fallback):
                    result = a.analyze('标题', '正文')
                self.assertEqual(result['summary_english'], 'Scripted summary.')
                self.assertEqual(result['categories'], [])
                self.assertFalse(result['is_significant'])
                self.assertEqual(result['prompt_version'], 'v1')
                self.assertEqual(len(a._client.create_kwargs), 3 if fallback else 2)

    def test_existing_summary_json_repair_remains_inside_task_before_fallback(self):
        c = FakeClient(creates=[text_response('invalid JSON')],
                       streams=[tool_response({'summary': 'Repaired summary.'}, name='emit_summary')])
        with mock.patch.object(engine, 'FALLBACK_MODEL', CHEAP):
            self.assertEqual(analyzer_for(c).summarize('T', 'B'), 'Repaired summary.')
        self.assertEqual([r['model'] for r in c.create_kwargs + c.stream_kwargs], [SONNET, SONNET])

    def test_existing_fatal_and_response_safeguards_survive_candidate_off(self):
        for bad in (status_error(403), text_response(SUMMARY_JSON, stop='max_tokens'),
                    text_response(SUMMARY_JSON, stop='refusal')):
            with self.subTest(bad=bad), mock.patch.object(engine, 'FALLBACK_MODEL', CHEAP):
                c = FakeClient(creates=[bad, text_response(SUMMARY_JSON)])
                if isinstance(bad, BaseException):
                    with self.assertRaises(engine.FatalAPIError):
                        analyzer_for(c).summarize('T', 'B')
                    self.assertEqual(len(c.create_kwargs), 1)
                else:
                    self.assertEqual(analyzer_for(c).summarize('T', 'B'), 'Scripted summary.')
                    self.assertEqual(len(c.create_kwargs), 2)

    def test_incumbent_non_object_summary_exception_is_not_newly_reclassified(self):
        c = FakeClient(creates=[text_response('[]')])
        with mock.patch.object(engine, 'FALLBACK_MODEL', CHEAP):
            with self.assertRaises(AttributeError):
                analyzer_for(c).summarize('T', 'B')
        self.assertEqual(len(c.create_kwargs), 1)

    def test_evaluated_prompts_are_preserved_only_under_explicit_candidate_optin(self):
        for builder, expected in CONTRACT['evaluated_prompt_messages_sha256'].items():
            with self.subTest(builder=builder):
                self.assertEqual(digest(getattr(fidelity, builder)(*CONTRACT['input'])), expected)
        c = FakeClient(streams=[tool_response({'title_en': 'Report', 'body_en': 'By Lu Dongfang.'})])
        a = analyzer_for(c)
        with mock.patch.object(engine, 'MODEL_FIDELITY_CANDIDATE_ENABLED', True):
            self.assertEqual(a._china_prompt_version, 'v2-source-fidelity')
            with self.assertRaisesRegex(engine.AnalysisError, 'source_byline_anchor_missing'):
                a.translate('标题', '解放军报记者 卢东方 ')
        with mock.patch.object(engine, 'MODEL_FIDELITY_CANDIDATE_ENABLED', True):
            with self.assertRaisesRegex(engine.AnalysisError, 'Invalid categorization'):
                analyzer_for(FakeClient(creates=[text_response('{"categories":[],"significance":"false"}')])).categorize('T', 'B')

    def test_candidate_configuration_requires_exact_explicit_optin(self):
        for value, expected in ((None, 'False'), ('true', 'False'), ('1', 'True')):
            with self.subTest(value=value):
                env = dict(os.environ)
                env.pop('MODEL_FIDELITY_CANDIDATE_ENABLED', None)
                if value is not None:
                    env['MODEL_FIDELITY_CANDIDATE_ENABLED'] = value
                result = subprocess.run([sys.executable, '-c',
                    'import config; print(config.MODEL_FIDELITY_CANDIDATE_ENABLED)'],
                    env=env, check=True, capture_output=True, text=True)
                self.assertEqual(result.stdout.strip(), expected)
        workflow = (Path(__file__).parents[1] / '.github/workflows/daily_update.yml').read_text()
        self.assertNotIn('MODEL_FIDELITY_CANDIDATE_ENABLED', workflow)


if __name__ == '__main__':
    unittest.main()
