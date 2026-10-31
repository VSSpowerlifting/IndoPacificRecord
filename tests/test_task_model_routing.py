"""Offline task routing, source holds, accounting, and restart boundaries."""
import json
import unittest
from unittest import mock

from analysis.analyzer import AnalysisError, FatalAPIError
from analysis.fidelity import check
from analysis.usage import build_run_record
from tests.test_llm_usage_telemetry import (
    FakeClient, analyzer_for, text_response, tool_response, usage, status_error,
    RELEVANCE_JSON, SUMMARY_JSON, CATEGORY_JSON, SONNET,
)

CHEAP = "claude-haiku-5-5"


class TaskModelRouting(unittest.TestCase):
    def settings(self, **kwargs):
        return mock.patch.multiple("analysis.analyzer", **kwargs)

    def test_mixed_tasks_and_provenance_do_not_cross_worker_threads(self):
        class Client(FakeClient):
            def create(self, **kwargs):
                self.create_kwargs.append(kwargs)
                value = CATEGORY_JSON if kwargs['max_tokens'] == 500 else SUMMARY_JSON
                return text_response(value, usage(100, 20))
        c = Client(streams=[tool_response({'title_en':'T', 'body_en':'B'}, usage(100, 50))])
        a = analyzer_for(c)
        with self.settings(SUMMARY_MODEL=CHEAP, CATEGORIZATION_MODEL=SONNET), \
                mock.patch.object(a, 'score_relevance', return_value=(.9, 'source')):
            result = a.analyze('标题', '正文')
        self.assertEqual(len(c.create_kwargs), 2)
        self.assertEqual({(r['task'], r['model']) for r in a.usage.rows()},
                         {('translation',SONNET),('summary',CHEAP),('categorization',SONNET)})
        self.assertIn('summary='+CHEAP, result['model_id'])
        self.assertIn('translation='+SONNET, result['model_id'])
        self.assertEqual(result['summary_english'], 'Scripted summary.')

    def test_fidelity_fallback_charges_both_outputs_once(self):
        c = FakeClient(creates=[text_response(json.dumps({'summary':'A simulated submarine was tracked.'}), usage(120,20)),
                                text_response(json.dumps({'summary':'A Blue Force submarine was tracked before a simulated attack.'}), usage(140,30))])
        a = analyzer_for(c)
        with self.settings(SUMMARY_MODEL=CHEAP, FALLBACK_MODEL=SONNET, MODEL_FIDELITY_CANDIDATE_ENABLED=True):
            result = a.summarize('Training', 'The ship tracked a Blue Force submarine and simulated an attack.')
        self.assertNotIn('simulated submarine', result)
        self.assertEqual([k['model'] for k in c.create_kwargs], [CHEAP,SONNET])
        rows=a.usage.rows()
        self.assertEqual(sum(r['calls'] for r in rows),2)
        self.assertEqual(sum(r['failed_calls'] for r in rows),1)
        record=build_run_record(a.usage,run_date='2026-10-29',recorded_at='2026-10-29T00:00:00Z',run_status='completed',analysis_model=SONNET,relevance_model=CHEAP,articles_queued=1,articles_fully_analyzed=1)
        # Includes rejected cheap output and accepted fallback, through the one
        # pinned pricing table; no separate evaluation price implementation.
        self.assertAlmostEqual(record['estimated_cost_usd'], .000892)
        self.assertEqual(record['estimated_cost_per_analyzed_article_usd'],record['estimated_cost_usd'])

    def test_translation_fallback_preserves_rank_anchors(self):
        c=FakeClient(streams=[tool_response({'title_en':'T','body_en':'Senior sergeant; senior sergeant.'},usage(100,30)),
                              tool_response({'title_en':'T','body_en':'Grade A (一级上士); grade B (二级上士).'},usage(100,40))])
        a=analyzer_for(c)
        with self.settings(TRANSLATION_MODEL=CHEAP,FALLBACK_MODEL=SONNET,MODEL_FIDELITY_CANDIDATE_ENABLED=True):
            _,body=a.translate('标题','一级上士 / 二级上士')
        self.assertIn('二级上士',body)
        self.assertEqual([k['model'] for k in c.stream_kwargs],[CHEAP,SONNET])
        self.assertEqual(sum(r['failed_calls'] for r in a.usage.rows()),1)

    def test_category_invalid_schema_falls_back_without_coercion(self):
        for bad in [[], {'categories':['invented'],'significance':False},
                    {'categories':['taiwan'],'significance':'false'},
                    {'categories':['taiwan'],'significance':True,'significance_reason':None}]:
            with self.subTest(bad=bad):
                a=analyzer_for(FakeClient(creates=[text_response(json.dumps(bad),usage(10,2)), text_response(CATEGORY_JSON,usage(20,3))]))
                with self.settings(CATEGORIZATION_MODEL=CHEAP,FALLBACK_MODEL=SONNET,MODEL_FIDELITY_CANDIDATE_ENABLED=True):
                    self.assertEqual(a.categorize('T','B'),(['taiwan'],False,None))
                self.assertEqual(sum(r['failed_calls'] for r in a.usage.rows()),1)

    def test_relevance_bad_container_uses_fallback(self):
        c=FakeClient(creates=[text_response('[]',usage(1,1)),text_response(RELEVANCE_JSON,usage(2,2))])
        with self.settings(RELEVANCE_MODEL=CHEAP,FALLBACK_MODEL=SONNET):
            self.assertEqual(analyzer_for(c).score_relevance('T','B')[0],.9)
        self.assertEqual([k['model'] for k in c.create_kwargs],[CHEAP,SONNET])

    def test_transient_failure_can_fallback_but_account_failure_never_does(self):
        for code in [401,402,403,500]:
            c=FakeClient(creates=[status_error(code),text_response(SUMMARY_JSON,usage(1,1))])
            a=analyzer_for(c)
            with self.settings(SUMMARY_MODEL=CHEAP,FALLBACK_MODEL=SONNET):
                if code==500:
                    self.assertEqual(a.summarize('T','B'),'Scripted summary.')
                    self.assertEqual(len(c.create_kwargs),2)
                else:
                    with self.assertRaises(FatalAPIError):a.summarize('T','B')
                    self.assertEqual(len(c.create_kwargs),1)

    def test_same_model_fallback_is_not_dispatched_twice(self):
        c=FakeClient(creates=[text_response('{}',usage(1,1))])
        with self.settings(SUMMARY_MODEL=CHEAP,FALLBACK_MODEL=CHEAP):
            with self.assertRaises(AnalysisError):analyzer_for(c).summarize('T','B')
        self.assertEqual(len(c.create_kwargs),1)

    def test_double_rejection_holds_and_does_not_change_next_task_model(self):
        c=FakeClient(creates=[text_response('{}',usage(1,1)),text_response('{}',usage(2,2)),text_response(SUMMARY_JSON,usage(3,3))])
        a=analyzer_for(c)
        with self.settings(SUMMARY_MODEL=CHEAP,FALLBACK_MODEL=SONNET):
            with self.assertRaises(AnalysisError):a.summarize('T','B')
            self.assertEqual(a.summarize('T','B'),'Scripted summary.')
        self.assertEqual([k['model'] for k in c.create_kwargs],[CHEAP,SONNET,CHEAP])

    def test_failed_categories_cannot_be_persisted_as_complete(self):
        a=analyzer_for(FakeClient())
        with self.settings(MODEL_FIDELITY_CANDIDATE_ENABLED=True), \
             mock.patch.object(a,'score_relevance',return_value=(.9,'source')), \
             mock.patch.object(a,'translate',return_value=('T','B')), \
             mock.patch.object(a,'summarize',return_value='Summary.'), \
             mock.patch.object(a,'categorize',side_effect=AnalysisError('rejected')):
            result=a.analyze('标题','正文')
        self.assertEqual(result['summary_english'],'')
        self.assertTrue(result['passed_relevance'])

    def test_configuration_rollback_restores_incumbents_in_same_engine(self):
        a=analyzer_for(FakeClient(creates=[text_response(SUMMARY_JSON),text_response(SUMMARY_JSON)]))
        with self.settings(SUMMARY_MODEL=CHEAP):a.summarize('T','B')
        with self.settings(SUMMARY_MODEL='',FALLBACK_MODEL=''):a.summarize('T','B')
        self.assertEqual([k['model'] for k in a._client.create_kwargs],[CHEAP,SONNET])

    def test_existing_private_guard_rejects_override_before_dispatch(self):
        from processing.daily_intake import bound_private_calls
        from processing.daily_intake import IntakeHold
        a=analyzer_for(FakeClient(creates=[text_response(RELEVANCE_JSON)]))
        a._client.with_options=lambda **kwargs:a._client
        bound_private_calls(a,{'max_estimated_cost_usd_per_run':1})
        a.score_relevance('T','B')
        with self.settings(SUMMARY_MODEL=CHEAP,FALLBACK_MODEL=SONNET):
            with self.assertRaisesRegex(IntakeHold, 'daily_private_call_bound'):
                a._desk_summary_and_flag('T','B',mock.Mock(categories=(),analysis_system_prompt='source',build_analysis_messages=lambda *a:[]))
        self.assertEqual(len(a._client.create_kwargs),1)

    def test_client_retains_incumbent_sdk_retry_configuration(self):
        from analysis.analyzer import Analyzer
        with mock.patch('analysis.analyzer.ANTHROPIC_API_KEY','synthetic'), \
             mock.patch('analysis.analyzer.anthropic.Anthropic') as client:
            Analyzer()
        self.assertEqual(client.call_args.kwargs, {'api_key': 'synthetic'})


class FidelityChecks(unittest.TestCase):
    def test_simulation_attaches_to_its_source_entity(self):
        self.assertEqual(check('Blue Force submarine; simulated attack.','A simulated submarine.'),'unsupported_submarine_qualifier')
        self.assertIsNone(check('A simulated submarine.','A simulated submarine.'))
        self.assertIsNone(check('Blue Force submarine; simulated attack.','A Blue Force submarine; simulated attack.'))

    def test_live_force_is_not_live_fire(self):
        self.assertEqual(check('Live-force training with simulated strikes.','Live-fire training.'),'unsupported_live_fire')
        self.assertIsNone(check('Live-fire training.','Live-fire training.'))

    def test_chronology_swap_and_missing_translation_year(self):
        source='In 2005 he applied for a transfer. In 2008 he joined construction.'
        self.assertEqual(check(source,'He transferred in 2008.'),'transfer_chronology_changed')
        self.assertEqual(check(source,'He transferred in 2005.',translation=True),'source_chronology_missing')
        self.assertIsNone(check(source,'The article profiles his maintenance work.'))
        self.assertEqual(check('2005年。2008年。', 'In 2005.', translation=True),
                         'source_chronology_missing')

    def test_rank_byline_anchors_and_other_desk_language(self):
        self.assertEqual(check('一级上士与二级上士','Senior sergeants',translation=True),'source_rank_anchor_missing')
        self.assertEqual(check('解放军报记者 卢东方 ','By Lu Dongfang',translation=True),'source_byline_anchor_missing')
        self.assertIsNone(check('국방부','Ministry of National Defense',translation=True))


if __name__=='__main__':unittest.main()
