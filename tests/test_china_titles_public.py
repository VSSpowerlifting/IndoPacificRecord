"""Actual HTML/index/Chromium/export contracts after synthetic title completion.

Only a synthetic row in a disposable copy receives a fake title translation.
No real headline is translated and the tracked snapshot stays byte-identical.
"""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright
from scripts.reconcile_db import read_only
from migrations.versions.m0012_china_title_translation import up
from storage.title_translation import candidates, run_batch
from core.title_translation import title_hash
from config import ANALYSIS_MODEL
from core.frontend_budget import measure_page

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'site/preview'))
import generate_preview as gp


def build_fixture(destination):
    destination.mkdir(parents=True,exist_ok=True)
    db=destination/'fixture.db'
    with read_only(str(ROOT/'pla_watch.db')) as source:
        con=sqlite3.connect(db); source.backup(con)
    up(con)
    ident=1+max(con.execute('SELECT MAX(id) FROM articles').fetchone()[0],
                con.execute('SELECT MAX(original_article_id) FROM retired_article_urls').fetchone()[0])
    source=con.execute("SELECT id FROM sources WHERE desk_id='china' AND language_tag='zh-Hans' AND enabled=1 ORDER BY id LIMIT 1").fetchone()[0]
    con.execute('INSERT INTO articles(id,url,content_hash,source_id,title_original,text_original,published_date,passed_relevance) VALUES(?,?,?,?,?,?,?,?)',
        (ident,'https://example.org/synthetic-title-fixture',title_hash('synthetic'),source,
         '测试标题','Synthetic body must stay outside bulk exports','2026-10-17',0))
    english_source=con.execute("SELECT id FROM sources WHERE desk_id='china' AND language_tag='en' AND enabled=1 ORDER BY id LIMIT 1").fetchone()[0]
    con.execute('INSERT INTO articles(id,url,content_hash,source_id,title_original,title_english,text_original,published_date,passed_relevance) VALUES(?,?,?,?,?,?,?,?,?)',
        (ident+1,'https://example.org/synthetic-english-fixture',title_hash('synthetic English'),english_source,
         'Synthetic English original fixture','测试标题','Synthetic English body','2026-10-17',0))
    con.commit()
    analyzer=Mock(); analyzer.translate_title.return_value='Synthetic headline translation fixture'
    row=next(r for r in candidates(con) if r['id']==ident)
    assert run_batch(con,analyzer,[row],ANALYSIS_MODEL)['translated']==1
    con.close()
    out=destination/'site'
    gp.build(out,gp.PUBLIC_TITLE,db,snapshot=gp.snapshot_from_corpus(db),legacy_routes=True)
    return out,ident


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_): pass


class ChinaTitlePublicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=Path(tempfile.mkdtemp(prefix='ipr-china-title-public-'))
        cls.out,cls.ident=build_fixture(cls.temp)
        cls.compact=json.loads((cls.out/'corpus-index.json').read_text())
        cls.index=json.loads((cls.out/'archive-research-index.json').read_text())
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(cls.out)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.origin='http://127.0.0.1:%s'%cls.server.server_port
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join(5)
        shutil.rmtree(cls.temp)

    def test_html_both_indexes_original_citation_and_export_boundary(self):
        r=next(r for r in self.compact['records'] if r[0]==self.ident)
        self.assertEqual(r[4:6],['Synthetic headline translation fixture','测试标题'])
        research=next(r for r in self.index['records'] if r['id']=='record:'+str(self.ident))
        self.assertEqual(research['title'],r[4]);self.assertEqual(research['original_title'],r[5])
        self.assertIn('machine-translated',research['processing']);self.assertIn('human review',research['processing'])
        self.assertIsNone(research['text']);self.assertIsNone(research['summary']);self.assertIsNone(research['source_url'])
        html=(self.out/'record'/('%s.html'%self.ident)).read_text()
        self.assertIn('<title>Synthetic headline translation fixture',html)
        self.assertIn('Not selected for analysis',html)
        self.assertIn('The heading is a machine translation',html)
        self.assertIn('测试标题',html)
        self.assertNotIn('No translation and no summary',html)
        self.assertIn('Machine-translated title', (self.out/'archive.html').read_text())

    def test_english_original_with_wrong_language_rendering_uses_actual_headline_everywhere(self):
        ident=self.ident+1
        compact=next(r for r in self.compact['records'] if r[0]==ident)
        research=next(r for r in self.index['records'] if r['id']=='record:'+str(ident))
        self.assertEqual(compact[4:6],['Synthetic English original fixture']*2)
        self.assertEqual(research['title'],compact[4])
        self.assertIn('English-language original',research['processing'])
        html=(self.out/'record'/('%s.html'%ident)).read_text()
        self.assertIn('<title>Synthetic English original fixture',html)
        self.assertNotIn('The heading is a machine translation',html)

    def test_desktop_mobile_search_labels_citations_and_downloads(self):
        for width in (1280,375):
            context=self.browser.new_context(viewport={'width':width,'height':900})
            try:
                page=context.new_page(); errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(self.origin+'/archive.html?'+urlencode({'scope':'all','q':'Synthetic headline translation fixture'}),wait_until='networkidle')
                self.assertFalse(page.locator('#index-error').is_visible())
                row=page.locator('#results .record-row');self.assertEqual(row.count(),1)
                self.assertIn('测试标题',row.inner_text());self.assertIn('Machine-translated title',row.inner_text())
                self.assertIn('Not selected for analysis',row.inner_text())
                row.locator('input').check()
                if page.locator('#research-list').get_attribute('open') is None:
                    page.locator('#research-list > summary').click()
                for kind in ('json','csv'):
                    with page.expect_download() as download: page.locator('#export-'+kind).click()
                    text=Path(download.value.path()).read_text(encoding='utf-8-sig')
                    self.assertIn('Synthetic headline translation fixture',text)
                    self.assertIn('测试标题',text);self.assertIn('machine-translated',text)
                    self.assertNotIn('Synthetic body',text)
                row.locator('h3 a').click();page.wait_for_load_state('networkidle')
                self.assertEqual(page.locator('h1').inner_text(),'Synthetic headline translation fixture')
                self.assertIn('测试标题',page.locator('#cite-source-text').inner_text())
                self.assertEqual(errors,[])
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
            finally: context.close()

    def test_no_js_titles_and_script_budget(self):
        context=self.browser.new_context(java_script_enabled=False)
        try:
            page=context.new_page();page.goto(self.origin+'/record/%s.html'%self.ident)
            self.assertEqual(page.locator('h1').inner_text(),'Synthetic headline translation fixture')
            self.assertIn('测试标题',page.locator('body').inner_text())
        finally: context.close()
        self.assertLessEqual(measure_page(self.out/'archive.html',self.out)['js_bytes'],10000)
