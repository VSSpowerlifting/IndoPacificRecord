"""Shared production pipeline with scripted models and disposable DB/site.

This proves persistence, renderer compatibility and queue recovery. It is not
real model execution, collector acceptance, factual qualification or publication.
"""
import hashlib
import sqlite3
from pathlib import Path
from unittest import mock

from tests.integration.test_pipeline_run import PipelineRunCase, article, scraper_factory
from tests.test_llm_usage_telemetry import (
    FakeClient, analyzer_for, text_response, tool_response, usage,
    RELEVANCE_JSON, SUMMARY_JSON, CATEGORY_JSON, SONNET,
)

CHEAP='claude-haiku-5-5'


class TaskModelPipeline(PipelineRunCase):
    def setUp(self):
        super().setUp()
        # The tiny corpus does not include records cited by the real approved
        # dossier. Omit that unrelated product in this fixture only.
        loader=mock.patch('core.dossiers.load_dossiers',return_value=([],[]))
        loader.start();self.addCleanup(loader.stop)

    def client(self, rejected_categories=False):
        class RoutedClient(FakeClient):
            def create(client, **kwargs):
                client.create_kwargs.append(kwargs)
                if kwargs['max_tokens']==1000:
                    return text_response(SUMMARY_JSON,usage(100,20))
                if len(client.create_kwargs)==1:
                    return text_response(RELEVANCE_JSON,usage(100,20))
                return text_response('[]' if rejected_categories else CATEGORY_JSON,usage(100,20))
            def stream(client, **kwargs):
                return super().stream(**kwargs)
        return RoutedClient(streams=[tool_response({'title_en':'Synthetic training report', 'body_en':'Synthetic source for an offline pipeline contract.'},usage(100,50))])

    def test_rejection_restart_completion_and_no_duplicate_dispatch_or_record(self):
        url='http://www.81.cn/x/model-contract.html'
        adapters={'pla_daily':scraper_factory(urls=[url],pages={url:'<html/>'},parsed={url:article(url)})}
        c=self.client(rejected_categories=True)
        a=analyzer_for(c)
        with mock.patch('analysis.analyzer.SUMMARY_MODEL',CHEAP), \
             mock.patch('analysis.analyzer.FALLBACK_MODEL',''), \
             mock.patch('analysis.analyzer.Analyzer',return_value=a), \
             mock.patch.object(self.pipeline,'ANTHROPIC_API_KEY','synthetic'):
            with self.assertRaises(SystemExit):self.run_pipeline(adapters,no_analysis=False)
        con=sqlite3.connect(self.db_path)
        self.assertEqual(con.execute('select count(*) from articles').fetchone()[0],1)
        self.assertIsNone(con.execute('select analyzed_at from articles').fetchone()[0])
        self.assertEqual(con.execute('select passed_relevance from articles').fetchone()[0],1)
        con.close()
        c=self.client()
        a=analyzer_for(c)
        with mock.patch('analysis.analyzer.SUMMARY_MODEL',CHEAP), \
             mock.patch('analysis.analyzer.FALLBACK_MODEL',''), \
             mock.patch('analysis.analyzer.Analyzer',return_value=a), \
             mock.patch.object(self.pipeline,'ANTHROPIC_API_KEY','synthetic'):
            self.run_pipeline(adapters,no_analysis=False)
        con=sqlite3.connect(self.db_path)
        row=con.execute('select id,analyzed_at,summary_english,model_id from articles').fetchone()
        self.assertIsNotNone(row[1]);self.assertEqual(row[2],'Scripted summary.')
        self.assertIn('summary='+CHEAP,row[3]);self.assertIn('translation='+SONNET,row[3])
        self.assertEqual(con.execute('select count(*) from articles').fetchone()[0],1)
        con.close()
        pages=list(self.out_dir.rglob('*.html'))
        self.assertTrue(pages)
        self.assertTrue(any('Scripted summary.' in p.read_text() for p in pages))
        before=len(c.create_kwargs)+len(c.stream_kwargs)
        with mock.patch('analysis.analyzer.Analyzer',return_value=a), \
             mock.patch.object(self.pipeline,'ANTHROPIC_API_KEY','synthetic'):
            self.run_pipeline(adapters,no_analysis=False)
        self.assertEqual(len(c.create_kwargs)+len(c.stream_kwargs),before)
        self.assertEqual(hashlib.sha256((Path(__file__).resolve().parents[2]/'pla_watch.db').read_bytes()).hexdigest(),self.tracked_db_digest)
