"""Shared-renderer publication, discovery and actual browser reading flow."""
import copy
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

from core import dossiers as d
from core.archive_research import dossier_records
from core.dossier_contract import read_dossier
from scripts import validate_output
from tests.test_dossiers import PILOT, ROOT, approve_fixture, fixture_decisions

sys.path.insert(0,str(ROOT/'site/preview'))
import generate_preview as gp


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):
        pass


class DossierRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.tmp.name)
        cls.snapshot=gp.snapshot_from_corpus(ROOT/'pla_watch.db')
        cls.private=cls.root/'private';cls.public=cls.root/'public';cls.approved=cls.root/'approved'
        cls.build(cls.private,review_dossier=PILOT)
        cls.build(cls.public,site_origin='https://fixture.test',allow_test_origin=True)
        cls.sc=approve_fixture(read_dossier(PILOT))
        cls.sc['title']='Synthetic approved dossier & discovery fixture'
        # Rebind the synthetic title before preparing its synthetic authority.
        from core.dossier_contract import dossier_content_digest
        cls.sc['approval']['content_sha256']=dossier_content_digest(cls.sc)
        cls.sources=cls.root/'dossiers';cls.sources.mkdir()
        (cls.sources/(cls.sc['slug']+'.json')).write_text(json.dumps(cls.sc))
        with fixture_decisions(cls.sc):
            cls.build(cls.approved,dossiers_dir=cls.sources,site_origin='https://fixture.test',allow_test_origin=True)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(cls.private)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:%s/'%cls.server.server_port

    @classmethod
    def build(cls,out,**options):
        return gp.build(out,'Indo-Pacific Record',ROOT/'pla_watch.db',snapshot=cls.snapshot,**options)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.tmp.cleanup()

    def detail(self,root):
        return root/'dossier/maritime-cooperation-2026.html'

    def test_complete_real_private_draft_no_original_text_and_noindex(self):
        html=self.detail(self.private).read_text()
        for text in ['preparation-and-opening','sea-phase-plan-and-report','replenishment-limit',
                     'event-ministry-interval','event-conclusion','Human review has not occurred',
                     'Source-use decision required','noindex, nofollow']:
            self.assertIn(text,html)
        self.assertNotIn('rel="canonical"',html)
        self.assertFalse((self.private/'sitemap.xml').exists())
        self.assertNotIn('<blockquote',html)
        for text in ['stored_original_sha256','text_original','中新','Ng Yen Meng']:
            self.assertNotIn(text,html)
        self.assertEqual(self.private.stat().st_mode & 0o777,0o700)

    def test_draft_zero_public_routes_discovery_backlinks_feed_or_text(self):
        self.assertFalse((self.public/'dossier').exists())
        self.assertFalse((self.public/'dossiers.css').exists())
        self.assertFalse((self.public/'timeline').exists())
        self.assertNotIn('value="living_dossier"',(self.public/'archive.html').read_text())
        marker=read_dossier(PILOT)['overview']
        for path in self.public.rglob('*'):
            if path.suffix in ('.html','.xml','.json'):
                text=path.read_text()
                self.assertNotIn('dossier/maritime-cooperation-2026.html',text,str(path))
                self.assertNotIn(marker,text,str(path))
        errors=[];validate_output._validate_dossiers(self.public,errors)
        self.assertEqual(errors,[])

    def test_synthetic_approved_same_path_once_in_discovery_and_backlinks(self):
        html=self.detail(self.approved).read_text()
        self.assertIn('Synthetic approved dossier &amp; discovery fixture',html)
        self.assertIn('data-editorial-status="approved"',html)
        self.assertIn('rel="canonical"',html)
        self.assertNotIn('content="noindex',html)
        self.assertIn('dossier/maritime-cooperation-2026.html',(self.approved/'analysis.html').read_text())
        rows=json.loads((self.approved/'archive-research-index.json').read_text())['records']
        found=[r for r in rows if r['record_type']=='living_dossier']
        self.assertEqual(len(found),1)
        self.assertIsNone(found[0]['text']);self.assertIsNone(found[0]['source_url'])
        self.assertIsNone(found[0]['original_title'])
        self.assertEqual((self.approved/'sitemap.xml').read_text().count('/dossier/maritime-cooperation-2026.html</loc>'),1)
        self.assertNotIn('/dossier/',(self.approved/'briefs/feed.xml').read_text())
        for route in ['record/3924.html','record/4102.html','record/4164.html','record/4466.html','record/4472.html','briefs/maritime-cooperation-2026.html']:
            self.assertIn('../dossier/maritime-cooperation-2026.html',(self.approved/route).read_text())
        self.assertFalse((self.approved/'timeline').exists())
        self.assertIn('value="living_dossier"',(self.approved/'archive.html').read_text())
        with fixture_decisions(self.sc),mock.patch.object(validate_output,'REPO_ROOT',ROOT),mock.patch('core.dossiers.DOSSIERS_DIR',self.sources):
            # Validator passes an explicit directory, so intercept only the
            # default source location while retaining the actual loader.
            actual=d.load_dossiers
            def loader(db,related,source_dir,*args,**kwargs):
                return actual(db,related,self.sources,*args,**kwargs)
            with mock.patch('core.dossiers.load_dossiers',side_effect=loader):
                errors=[];validate_output._validate_dossiers(self.approved,errors)
                self.assertEqual(errors,[])

    def test_invalid_asserted_approved_stops_shared_build(self):
        with self.assertRaisesRegex(ValueError,'publication_validation_failed'):
            self.build(self.root/'forged',dossiers_dir=self.sources)

    def test_preview_cannot_be_given_origin_or_overwrite(self):
        for options in [dict(site_origin='https://fixture.test',allow_test_origin=True),{}]:
            with self.subTest(options=options),self.assertRaises(ValueError):
                self.build(self.private,review_dossier=PILOT,**options)

    def test_deploy_gate_rejects_private_or_stale_dossier(self):
        errors=[];validate_output._validate_dossiers(self.private,errors)
        self.assertTrue(any('no approved dossier' in e for e in errors))

    def test_dossier_render_and_projection_deterministic(self):
        second=self.root/'deterministic'
        self.build(second,review_dossier=PILOT)
        for name in ['dossier/maritime-cooperation-2026.html','dossiers.css','archive-research-index.json']:
            self.assertEqual((second/name).read_bytes(),(self.private/name).read_bytes())

    def test_browser_reading_links_keyboard_copy_fallback_print_and_responsive(self):
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[];failed=[];requests=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.on('response',lambda r:failed.append(r.url) if r.status>=400 else None)
            page.on('request',lambda r:requests.append(r.url))
            page.goto(self.url+'dossier/maritime-cooperation-2026.html')
            page.wait_for_function('document.fonts.status === "loaded"')
            self.assertEqual(page.locator('h1').count(),1)
            self.assertTrue(page.evaluate('document.fonts.check(\'20px "Instrument Serif"\')'))
            self.assertTrue(page.evaluate('document.fonts.check(\'20px "Source Serif 4"\')'))
            summary=page.locator('#finding-preparation-and-opening summary')
            summary.focus();page.keyboard.press('Enter')
            self.assertTrue(page.locator('#finding-preparation-and-opening details').get_attribute('open') is not None)
            self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'),'none')
            page.locator('#finding-preparation-and-opening .ds-cites a').first.click()
            self.assertEqual(page.url.split('#')[-1],'source-3924')
            page.locator('#source-3924 a[href="../record/3924.html"]').click()
            self.assertTrue(page.url.endswith('/record/3924.html'))
            page.go_back()
            copy=page.locator('button[data-copy="dossier-citation"]')
            page.evaluate('Object.defineProperty(navigator,"clipboard",{value:{writeText:()=>Promise.reject(new Error("fixture-denied"))},configurable:true})')
            copy.click();page.wait_for_function('document.querySelector(".cite-status").textContent.includes("selectable")')
            self.assertIn('unapproved draft',page.evaluate('getSelection().toString()'))
            page.evaluate('navigator.clipboard.writeText=(text)=>{window.fixtureCopied=text;return Promise.resolve()}')
            copy.click();page.wait_for_function('document.querySelector(".cite-status").textContent.includes("clipboard")')
            self.assertEqual(page.evaluate('window.fixtureCopied'),page.locator('#dossier-citation').inner_text())
            soup=BeautifulSoup(self.detail(self.private).read_text(),'html.parser')
            ids=[e['id'] for e in soup.select('[id]')]
            self.assertEqual(len(ids),len(set(ids)))
            for link in soup.select('article a[href^="#"]'):
                self.assertIn(link['href'][1:],ids)
            self.assertEqual(len(soup.select('.ds-ledger > li')),5)
            for link in soup.select('article a[href^="../"]'):
                self.assertTrue((self.private/'dossier'/link['href']).resolve().is_file(),link['href'])
            for width in [1280,375,320]:
                page.set_viewport_size({'width':width,'height':900})
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
            page.emulate_media(reduced_motion='reduce')
            self.assertEqual(page.locator('h1').evaluate('(e)=>getComputedStyle(e).opacity'),'1')
            page.emulate_media(media='print')
            self.assertEqual(page.locator('.ds-contents').evaluate('(e)=>getComputedStyle(e).display'),'none')
            page.locator('details').evaluate_all('(all)=>all.forEach(e=>e.open=false)')
            self.assertEqual(page.locator('.ds-evidence').first.evaluate('(e)=>getComputedStyle(e.parentElement,"::details-content").contentVisibility'),'visible')
            self.assertEqual(errors,[]);self.assertEqual(failed,[])
            self.assertEqual([r for r in requests if not r.startswith(self.url)],[])
            # The native disclosures and citations remain usable without JS.
            nojs=browser.new_context(java_script_enabled=False)
            p=nojs.new_page();p.goto(self.url+'dossier/maritime-cooperation-2026.html')
            p.locator('#finding-preparation-and-opening summary').click()
            self.assertIsNotNone(p.locator('#finding-preparation-and-opening details').get_attribute('open'))
            self.assertTrue(p.locator('#dossier-citation').is_visible())
            nojs.close()
            browser.close()

    def test_approved_dossier_uses_existing_archive_query_citation_and_export(self):
        from playwright.sync_api import sync_playwright
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(self.approved)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch()
                context=browser.new_context(accept_downloads=True)
                page=context.new_page()
                page.goto('http://127.0.0.1:%s/archive.html?scope=published&record_type=living_dossier&keywords=synthetic'%server.server_port,wait_until='networkidle')
                self.assertFalse(page.locator('#research-error').is_visible())
                row=page.locator('#results .record-row')
                self.assertEqual(row.count(),1)
                self.assertIn('Synthetic approved dossier',row.locator('h3').inner_text())
                row.locator('summary').click()
                self.assertIn('Living Dossier',row.locator('.archive-citation').inner_text())
                row.locator('input').check()
                self.assertEqual(page.locator('#selection-count').inner_text(),'1')
                if page.locator('#research-list').get_attribute('open') is None:
                    page.locator('#research-list > summary').click()
                with page.expect_download() as download:
                    page.locator('#export-json').click()
                export=json.loads(Path(download.value.path()).read_text())['records']
                self.assertEqual(len(export),1)
                self.assertEqual(export[0]['record_type'],'living_dossier')
                self.assertIsNone(export[0]['text']);self.assertIsNone(export[0]['original_title'])
                context.close();browser.close()
        finally:
            server.shutdown();server.server_close();thread.join()
