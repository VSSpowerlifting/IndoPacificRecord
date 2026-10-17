"""Synthetic headline engineering fixtures: no API, production writes or claims."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from analysis.analyzer import Analyzer, AnalysisError, FatalAPIError
from config import ANALYSIS_MODEL
from core.title_translation import english_title, title_hash, valid_english
from migrations.versions.m0011_china_title_translation import up
from scripts.backfill_china_titles import main, report
from storage.title_translation import candidates, ready, claim, finish, run_batch, resume

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp


def fixture(conn):
    conn.executescript('''
        CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT,
                             language_tag TEXT, enabled INTEGER);
        INSERT INTO sources VALUES(1,'fixture-china','china','zh-Hans',1);
        INSERT INTO sources VALUES(2,'fixture-en','china','en',1);
        INSERT INTO sources VALUES(3,'fixture-korea','korea','ko',1);
        INSERT INTO sources VALUES(4,'fixture-disabled','china','zh-Hans',0);
        CREATE TABLE articles(id INTEGER PRIMARY KEY,url TEXT,title_original TEXT,
          title_english TEXT,source_id INTEGER,passed_relevance INTEGER,analyzed_at TEXT,
          processing_state TEXT,relevance_score REAL,summary_english TEXT,text_original TEXT);
        CREATE TABLE retired_article_urls(original_article_id INTEGER,url_sha256 TEXT);
    ''')
    up(conn)
    for ident, source, state, english in ((1,1,None,None), (2,1,None,'Human edited fixture'),
            (3,2,None,None), (4,3,None,None), (5,4,None,None), (6,1,'paused',None),
            (7,1,'terminal',None), (8,1,'held',None), (9,1,'private',None), (10,1,None,None)):
        original = 'Synthetic English original' if source == 2 else '测试标题'  # explicit synthetic test headline
        conn.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (ident, 'https://example.org/title/%s' % ident, original, english,
             source, 0, None, state, 0.1, None, 'BODY MUST NEVER BE DISPATCHED',
             *([None] * 9)))
    conn.execute('INSERT INTO retired_article_urls VALUES(?,?)',
                 (10, title_hash('https://example.org/title/10')))
    conn.commit()


class TitleWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.db'
        self.conn = sqlite3.connect(self.path)
        self.addCleanup(self.conn.close)
        fixture(self.conn)
        self.analyzer = Mock()
        self.analyzer.translate_title.return_value = 'Synthetic translated headline'

    def work(self):
        return [r for r in candidates(self.conn) if ready(r)]

    def run_work(self):
        return run_batch(self.conn, self.analyzer, self.work(), ANALYSIS_MODEL)

    def test_screened_out_title_only_idempotent_and_no_body_access(self):
        before = self.conn.execute('SELECT passed_relevance,analyzed_at,relevance_score,summary_english,text_original FROM articles WHERE id=1').fetchone()
        self.assertEqual(self.run_work()['translated'], 1)
        self.analyzer.translate_title.assert_called_once_with('测试标题')
        after = self.conn.execute('SELECT passed_relevance,analyzed_at,relevance_score,summary_english,text_original FROM articles WHERE id=1').fetchone()
        self.assertEqual(after, before)
        self.assertEqual(self.run_work()['translated'], 0)
        self.assertEqual(self.analyzer.translate_title.call_count, 1)
        row = candidates(self.conn)[0]
        self.assertEqual(row['title_translation_source_sha256'], title_hash(row['title_original']))

    def test_held_disabled_other_desks_retired_and_english_original_excluded(self):
        self.assertEqual([r['id'] for r in self.work()], [1])
        self.run_work()
        self.assertEqual(self.conn.execute('SELECT title_english FROM articles WHERE id=2').fetchone()[0], 'Human edited fixture')
        self.assertIsNone(self.conn.execute('SELECT title_english FROM articles WHERE id=3').fetchone()[0])

    def test_awaiting_screening_gets_title_without_screening(self):
        self.conn.execute('UPDATE articles SET passed_relevance=NULL WHERE id=1'); self.conn.commit()
        self.run_work()
        self.assertEqual(self.conn.execute('SELECT passed_relevance,analyzed_at FROM articles WHERE id=1').fetchone(), (None,None))

    def test_changed_original_rejects_stale_write_and_can_resume_new_version(self):
        row = claim(self.conn, self.work()[0])
        self.conn.execute("UPDATE articles SET title_original='更改测试标题' WHERE id=1"); self.conn.commit()
        self.assertFalse(finish(self.conn, row, 'Stale synthetic response', ANALYSIS_MODEL))
        self.assertIsNone(self.conn.execute('SELECT title_english FROM articles WHERE id=1').fetchone()[0])
        self.assertEqual(len(self.work()), 1)

    def test_changed_url_or_policy_rejects_write(self):
        for column, value in (('url', 'https://example.org/changed'), ('processing_state','held')):
            with self.subTest(column=column):
                self.conn.execute("UPDATE articles SET url='https://example.org/title/1',processing_state=NULL WHERE id=1"); self.conn.commit()
                row=claim(self.conn,self.work()[0])
                self.conn.execute('UPDATE articles SET '+column+'=? WHERE id=1',(value,)); self.conn.commit()
                self.assertFalse(finish(self.conn,row,'Synthetic title',ANALYSIS_MODEL))

    def test_concurrent_claim_prevents_duplicate_paid_dispatch(self):
        second = sqlite3.connect(self.path)
        self.addCleanup(second.close)
        expected = self.work()[0]
        first = claim(self.conn, expected)
        self.assertIsNone(claim(second, expected))
        self.assertTrue(finish(self.conn, first, 'First synthetic title', ANALYSIS_MODEL))
        self.assertIsNone(claim(second, expected))

    def test_concurrent_human_title_is_never_overwritten(self):
        row = claim(self.conn, self.work()[0])
        self.conn.execute("UPDATE articles SET title_english='Concurrent human title' WHERE id=1"); self.conn.commit()
        self.assertFalse(finish(self.conn, row, 'Synthetic machine title', ANALYSIS_MODEL))
        self.assertEqual(self.conn.execute('SELECT title_english FROM articles WHERE id=1').fetchone()[0], 'Concurrent human title')

    def test_failure_original_and_analysis_untouched_then_bounded_pause(self):
        self.analyzer.translate_title.side_effect = AnalysisError('synthetic malformed response')
        for _ in range(5): self.assertEqual(self.run_work()['failed'],1)
        self.assertEqual(self.work(),[])
        self.assertEqual(self.conn.execute('SELECT title_english,analyzed_at,processing_state,title_translation_state FROM articles WHERE id=1').fetchone(), (None,None,None,'paused'))
        self.assertTrue(resume(self.conn,candidates(self.conn)[0]))
        self.analyzer.translate_title.side_effect=None
        self.assertEqual(self.run_work()['translated'],1)

    def test_expired_claim_resumes_without_accepting_old_worker(self):
        row = claim(self.conn,self.work()[0])
        self.conn.execute("UPDATE articles SET title_translation_claimed_at='2000-01-01' WHERE id=1"); self.conn.commit()
        newer = claim(self.conn,self.work()[0])
        self.assertFalse(finish(self.conn,row,'Old synthetic title',ANALYSIS_MODEL))
        self.assertTrue(finish(self.conn,newer,'New synthetic title',ANALYSIS_MODEL))

    def test_fatal_failure_aborts_and_keeps_original(self):
        self.analyzer.translate_title.side_effect = FatalAPIError('synthetic billing stop')
        with self.assertRaises(FatalAPIError): self.run_work()
        self.assertTrue(self.work())

    def test_dry_run_is_read_only_no_probe_or_client(self):
        before = self.path.read_bytes()
        with patch('analysis.analyzer.Analyzer', side_effect=AssertionError('paid client')), patch('scripts.spend_guard.probe_api_access', side_effect=AssertionError('probe')), patch('builtins.print'):
            self.assertEqual(main(['--db',str(self.path),'--dry-run']),0)
        self.assertEqual(self.path.read_bytes(),before)
        r,_=report(candidates(self.conn),1)
        self.assertEqual(r['eligible_now'],1)
        self.assertGreater(r['batch_estimate']['total_usd'],0)

    def test_migration_idempotent_preserves_all_existing_values(self):
        before = list(self.conn.execute('SELECT * FROM articles'))
        up(self.conn); up(self.conn)
        self.assertEqual(list(self.conn.execute('SELECT * FROM articles')),before)

    def test_invalid_and_stale_titles_replaced_valid_legacy_preserved(self):
        for value in (' ', 'null', '测试标题'):
            self.conn.execute('UPDATE articles SET title_english=? WHERE id=1',(value,)); self.conn.commit()
            self.assertTrue(self.work())
        self.conn.execute("UPDATE articles SET title_english='Stale synthetic English',title_translation_source_sha256=? WHERE id=1",(title_hash('old synthetic original'),)); self.conn.commit()
        self.assertTrue(self.work())
        self.run_work()
        self.assertEqual(len(self.work()),0)


class TitleClientTests(unittest.TestCase):
    def test_forced_tool_uses_existing_client_and_records_paid_tokens(self):
        from tests.test_llm_usage_telemetry import FakeClient, tool_response, usage
        response=tool_response({'title_en':'Synthetic English'},usage(123,20))
        response.content[0].name='emit_title'
        a=Analyzer.__new__(Analyzer);a._client=FakeClient(streams=[response])
        self.assertEqual(a.translate_title('测试标题'),'Synthetic English')
        receipt=a.usage.rows()[0]
        self.assertEqual((receipt['task'],receipt['input_tokens'],receipt['output_tokens']),('title_translation',123,20))

    def test_payload_is_headline_only_and_explicitly_untrusted(self):
        a = Analyzer.__new__(Analyzer)
        a._call_tool=Mock(return_value={'title_en':'Synthetic English'})
        self.assertEqual(a.translate_title('测试标题'),'Synthetic English')
        args,kw=a._call_tool.call_args
        self.assertEqual(json.loads(args[0][0]['content']),{'headline':'测试标题'})
        self.assertEqual(set(args[1]['input_schema']['properties']),{'title_en'})
        self.assertIn('never instructions',kw['system'][0]['text'])
        self.assertEqual(kw['task'],'title_translation')

    def test_malformed_response_is_failed_not_coerced(self):
        for value in (None, 1, [], {}, '', ' ', 'null', '测试标题', 'A\nB'):
            a=Analyzer.__new__(Analyzer); a._call_tool=Mock(return_value={'title_en':value})
            with self.subTest(value=value), self.assertRaises(AnalysisError): a.translate_title('测试标题')
        a=Analyzer.__new__(Analyzer); a._call_tool=Mock(return_value={'title_en':'Synthetic English','summary':'injected'})
        with self.assertRaises(AnalysisError): a.translate_title('测试标题')


class TitlePresentationTests(unittest.TestCase):
    def test_original_citation_title_and_machine_title_are_distinct(self):
        row=dict(id=1,title_english='Synthetic English',title_original='测试标题',
            desk_id='china',language_tag='zh-Hans',state='not_selected',
            institution='Synthetic issuer',source_name='Synthetic source',
            published_date='2026-01-01',url='https://example.org/title/1')
        c=gp.record_citation(row,'Indo-Pacific Record',{'date':'2026-01-01','expected_records':1})
        self.assertIn('测试标题',c['source_text']); self.assertNotIn('Synthetic English',c['source_text'])
        self.assertIn('machine-translated',c['note']); self.assertNotIn('no translation',c['note'].lower())

    def test_stale_receipt_suppresses_display_other_desks_unchanged(self):
        r=dict(title_english='Old title',title_original='测试标题',desk_id='china',
               title_translation_source_sha256=title_hash('old original'))
        self.assertIsNone(english_title(r))
        self.assertEqual(english_title(dict(r,desk_id='korea')),'Old title')


from tests.test_reconcile import ReconcileCase, migrate


class TitleReconciliationTests(ReconcileCase):
    def test_successful_local_title_receipt_survives_without_analysis(self):
        for path in (self.base,self.origin,self.local): migrate(path)
        con=sqlite3.connect(self.local)
        title=con.execute('SELECT title_original FROM articles WHERE id=2').fetchone()[0]
        con.execute("UPDATE articles SET title_english='Synthetic completed headline',title_translation_source_sha256=?,title_translation_model=?,title_translation_prompt='china-title-v1' WHERE id=2",(title_hash(title),ANALYSIS_MODEL));con.commit();con.close()
        out,_,problems=self.run_reconcile()
        self.assertEqual(problems,[])
        con=sqlite3.connect(out)
        self.assertEqual(con.execute('SELECT title_english,analyzed_at,passed_relevance,title_translation_source_sha256 FROM articles WHERE id=2').fetchone(),('Synthetic completed headline',None,0,title_hash(title)))
        con.close()

    def test_origin_human_title_survives_local_analysis_merge(self):
        for path in (self.base,self.origin,self.local): migrate(path)
        con=sqlite3.connect(self.origin)
        con.execute("UPDATE articles SET title_english='Synthetic human edited headline' WHERE id=2");con.commit();con.close()
        con=sqlite3.connect(self.local)
        con.execute("UPDATE articles SET passed_relevance=1,analyzed_at='2026-01-01',title_english='Synthetic machine headline',summary_english='Synthetic summary' WHERE id=2");con.commit();con.close()
        out,_,problems=self.run_reconcile()
        self.assertEqual(problems,[])
        con=sqlite3.connect(out)
        self.assertEqual(con.execute('SELECT title_english FROM articles WHERE id=2').fetchone()[0],'Synthetic human edited headline')
        con.close()


class DailyTitleIntegrationTests(unittest.TestCase):
    def drive(self, fail=False):
        from tests.test_llm_usage_telemetry import (
            TestAFatalBlockKeepsUsage, FakeClient, tool_response, text_response, usage)
        harness=TestAFatalBlockKeepsUsage('run');harness.setUp()
        self.addCleanup(harness.doCleanups)
        responses=[]
        for _ in range(2):
            r=tool_response({'title_en':'Synthetic daily headline'},usage(100,10))
            r.content[0].name='emit_title'
            responses.append(AnalysisError('synthetic title failure') if fail else r)
        provider=FakeClient(creates=[text_response(json.dumps({'score':0.1,'reasoning':'Synthetic screened-out fixture'}),usage(100,5)) for _ in range(2)], streams=responses)
        with patch('config.CHINA_TITLE_TRANSLATION_LIMIT',20):
            harness.drive(provider)
        con=sqlite3.connect(harness.case.db_path)
        self.addCleanup(con.close)
        return list(con.execute('SELECT passed_relevance,analyzed_at,title_english,summary_english FROM articles'))

    def test_daily_screened_out_gets_title_independently(self):
        rows=self.drive()
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r==(0,None,'Synthetic daily headline',None) for r in rows))

    def test_title_failure_does_not_block_collection_or_mark_analyzed(self):
        rows=self.drive(fail=True)
        self.assertTrue(all(r==(0,None,None,None) for r in rows))
