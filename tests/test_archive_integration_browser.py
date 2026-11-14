"""Required Chromium contracts against a real isolated production render."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode, urlsplit

from playwright.sync_api import sync_playwright
from core.frontend_budget import measure_page

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class ArchiveIntegrationBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix='ipr-production-archive-'))
        cls.site = cls.temp / 'site'
        gp.build(cls.site, gp.PUBLIC_TITLE, ROOT / 'pla_watch.db',
                 snapshot=gp.snapshot_from_corpus(ROOT / 'pla_watch.db'), legacy_routes=True,
                 site_origin='https://indopacificrecord.org')
        cls.compact = json.loads((cls.site / 'corpus-index.json').read_text())
        cls.index = json.loads((cls.site / 'archive-research-index.json').read_text())
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=str(cls.site)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.origin = 'http://127.0.0.1:%d' % cls.server.server_port
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop()
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(5)
        shutil.rmtree(cls.temp)

    def context(self, **kwargs):
        context = self.browser.new_context(**kwargs)
        self.addCleanup(context.close)
        return context

    def open(self, page, query):
        page.goto(self.origin + '/archive.html?' + urlencode(query), wait_until='networkidle')
        self.assertFalse(page.locator('#index-error').is_visible())
        self.assertFalse(page.locator('#research-error').is_visible())

    def test_legacy_urls_preserve_every_filter_order_and_page(self):
        data = self.compact
        first = data['records'][0]; source = data['sources'][first[2]]
        cases = [dict(scope='all'), dict(scope='all',page='2'), dict(scope='all',sort='old'),
                 dict(scope='focus'), dict(scope='all',source=source['code']),
                 dict(scope='all',desk=source['desk']['code']),
                 dict(scope='all',institution=data['institutions'][source['institution']]['code']),
                 dict(scope='all',language=data['languages'][source['language']]['code']),
                 dict(scope='all',status=data['states'][first[3]]['code']),
                 dict(scope='all',trail='1'), dict(scope='all',q=first[4][:12]),
                 dict(scope='all',**{'from':first[1], 'to':first[1]})]
        original_only = next(r for r in data['records'] if not r[4] and r[5])
        # Legacy title matching must not duplicate an absent English title.
        cases.append(dict(scope='all', q=original_only[5]+' '+original_only[5]))
        page = self.context().new_page()
        for query in cases:
            with self.subTest(query=query):
                expected = []
                for r in data['records']:
                    s = data['sources'][r[2]]
                    values = dict(source=s['code'],desk=s['desk']['code'],status=data['states'][r[3]]['code'],
                                  institution=data['institutions'][s['institution']]['code'],language=data['languages'][s['language']]['code'])
                    if query.get('scope')=='focus' and r[0] not in data['focus_ids']: continue
                    if any(query.get(k) and query[k]!=v for k,v in values.items()): continue
                    if query.get('q') and query['q'].lower() not in (r[4]+' '+r[5]).lower(): continue
                    if query.get('trail') and r[0] not in data['trail_ids']: continue
                    if query.get('from') and r[1]<query['from'] or query.get('to') and r[1]>query['to']: continue
                    expected.append('record/%d.html' % r[0])
                if query.get('sort')=='old': expected.reverse()
                start=(int(query.get('page','1'))-1)*50
                expected=expected[start:start+50]
                self.open(page,query)
                self.assertEqual(page.locator('#results h3 a').evaluate_all('(xs)=>xs.map(x=>x.getAttribute("href"))'), expected)

    def test_published_search_citations_selection_exports_and_history(self):
        context = self.context(permissions=['clipboard-read','clipboard-write'])
        page = context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
        self.open(page,dict(scope='published',record_type='human_analysis',q='Laos',keywords='Laos'))
        self.assertIn('Title contains: Laos',page.locator('#chips').inner_text())
        self.assertIn('Keywords',page.locator('#chips').inner_text())
        links=page.locator('#results h3 a')
        self.assertGreater(links.count(),0)
        href=links.first.get_attribute('href')
        record=next(r for r in self.index['records'] if r['ipr_url']==href)
        # Keep full CI offline: follow the actual canonical link into the
        # isolated mirror of the same real generated article, not a fixture.
        page.route(href, lambda route: route.fulfill(status=302,
                   headers={'location':self.origin+urlsplit(href).path}))
        with page.expect_navigation(): links.first.click()
        self.assertEqual(urlsplit(page.url).path,urlsplit(href).path)
        page.go_back(wait_until='networkidle')
        row=page.locator('#results .record-row').first
        row.locator('summary').click()
        self.assertEqual(row.locator('.archive-citation').inner_text(),record['citation'])
        row.locator('details button').click()
        self.assertEqual(page.evaluate('navigator.clipboard.readText()'),record['citation'])
        row.locator('input').check()
        self.assertEqual(page.locator('#selection-count').inner_text(),'1')
        for extension in ('csv','json'):
            with page.expect_download() as download: page.locator('#export-'+extension).click()
            raw=Path(download.value.path()).read_text(encoding='utf-8-sig')
            self.assertIn(record['citation'],raw) if extension=='json' else self.assertIn('citation',raw)
            if extension=='json':
                exported=json.loads(raw)
                self.assertEqual(exported['records'],[record])
                self.assertEqual(exported['corpus_digest'],self.index['digest'])
        kept = page.locator('#selected-list .record-row')
        self.assertEqual(kept.count(),1)
        self.assertEqual(kept.locator('h3 a').get_attribute('href'),href)
        kept.locator('input').click()
        self.assertEqual(page.locator('#selection-count').inner_text(),'0')
        self.assertFalse(page.locator('#results input').first.is_checked())
        self.assertTrue(page.locator('#research-list > summary').evaluate('e=>e===document.activeElement'))
        page.locator('#results input').first.check()
        page.reload(wait_until='networkidle')
        self.assertEqual(page.locator('#selection-count').inner_text(),'1')
        self.assertTrue(page.locator('#results input').first.is_checked())
        page.locator('#f-scope').select_option('all')
        page.wait_for_url('**scope=all**')
        page.go_back(wait_until='networkidle')
        self.assertEqual(page.locator('#f-scope').input_value(),'published')
        self.assertEqual(errors,[])

    def title_matches(self, q, scope):
        """Python statement of browse.js `matches()` + `inScope()` for a title query."""
        out = []
        for r in self.index['records']:
            m = self.index['display'].get(r['id'])
            title = ('' if m and not m['english'] else r['title'] or '') + ' ' + (r['original_title'] or '')
            if q.lower() not in title.lower(): continue
            if scope == 'published' or m and (scope == 'all' or m['focus']): out.append(r)
        return out

    def test_home_search_reaches_briefs_and_cited_records_by_keyboard(self):
        brief = next(r for r in self.index['records'] if r['id'].startswith('analysis:') and r['source'] == 'Indo-Pacific Record Briefs')
        cited = next(r for r in self.index['records'] if r['id'].startswith('cited:'))
        for width in (1280, 375):
            for record in (brief, cited):
                with self.subTest(width=width, record=record['id']):
                    page = self.context(viewport={'width': width, 'height': 900}).new_page()
                    page.goto(self.origin + '/index.html', wait_until='networkidle')
                    page.locator('#home-q').fill(record['title']); page.keyboard.press('Enter')
                    page.wait_for_url('**scope=published**'); page.wait_for_load_state('networkidle')
                    self.assertEqual(page.locator('#f-scope').input_value(), 'published')
                    self.assertEqual(page.locator('#f-q').input_value(), record['title'])
                    row = page.locator('#results .record-row').filter(has=page.locator('h3 a[href="%s"]' % record['ipr_url'])).first
                    self.assertTrue(row.is_visible())
                    row.locator('summary').focus(); page.keyboard.press('Enter')
                    self.assertEqual(row.locator('.archive-citation').inner_text(), record['citation'])
                    self.assertFalse(page.locator('#scope-more').is_visible())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)

    def test_narrower_scope_counts_published_matches_and_widens_keeping_the_search(self):
        cited = next(r for r in self.index['records'] if r['id'].startswith('cited:') and not self.title_matches(r['title'], 'all'))
        page = self.context().new_page(); self.open(page, dict(q=cited['title']))
        extra = len(self.title_matches(cited['title'], 'published'))
        self.assertTrue(page.locator('#no-results').is_visible())
        self.assertFalse(page.locator('#no-results button[value=clear]').is_visible())
        more = page.locator('#scope-more button')
        self.assertEqual(more.inner_text(), 'Search all published material (%d more)' % extra)
        self.assertEqual(page.locator('#result-live').text_content(), 'No records match. · ' + more.inner_text())
        more.focus(); page.keyboard.press('Enter'); page.wait_for_url('**scope=published**')
        self.assertIn('q=', page.url)
        self.assertEqual(page.locator('#results .record-row').count(), extra)
        self.assertTrue(page.locator('#f-q').evaluate('e=>e===document.activeElement'))
        self.assertFalse(page.locator('#scope-more').is_visible())
        page.go_back(wait_until='networkidle')
        self.assertEqual(page.locator('#f-scope').input_value(), 'focus')
        # A non-empty narrower result still says what the wider scope adds.
        word = next(w for w in ('Laos', 'Taiwan', 'Japan', 'Philippines', 'Navy')
                    if self.title_matches(w, 'all') and len(self.title_matches(w, 'published')) > len(self.title_matches(w, 'all')))
        self.open(page, dict(scope='all', q=word))
        shown, wider = len(self.title_matches(word, 'all')), len(self.title_matches(word, 'published'))
        self.assertIn(' of %s preserved records' % format(shown, ','), page.locator('#result-range').inner_text())
        self.assertEqual(page.locator('#scope-more button').inner_text(), 'Search all published material (%d more)' % (wider - shown))
        # A genuine no-match offers only to clear, and keeps the scope.
        self.open(page, dict(scope='all', q='zzqxjvk-no-such-title'))
        self.assertFalse(page.locator('#scope-more').is_visible())
        clear = page.locator('#no-results button[value=clear]'); self.assertTrue(clear.is_visible())
        clear.click(); page.wait_for_load_state('networkidle')
        self.assertEqual(page.locator('#f-q').input_value(), ''); self.assertEqual(page.locator('#f-scope').input_value(), 'all')

    def test_mobile_disclosure_focus_overflow_and_clipboard_fallback(self):
        for width in (320,375,768,1280):
            with self.subTest(width=width):
                context=self.context(viewport={'width':width,'height':900},reduced_motion='reduce')
                page=context.new_page(); self.open(page,dict(scope='all'))
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                panel=page.locator('#research-list')
                if width<=680:
                    self.assertFalse(panel.evaluate('e=>e.open'))
                    self.assertLessEqual(panel.bounding_box()['height'],50)
                checkbox=page.locator('#results input').first
                checkbox.focus(); before=page.evaluate('scrollY'); checkbox.press('Space')
                self.assertEqual(page.locator('#selection-count').inner_text(),'1')
                self.assertTrue(checkbox.evaluate('e=>e===document.activeElement'))
                self.assertEqual(page.evaluate('scrollY'),before)
                self.assertEqual(panel.evaluate('e=>e.open'),width>680)
                self.assertEqual(page.locator('#selection-note').get_attribute('aria-live'),'polite')
                self.assertFalse(page.locator('#selection-note').evaluate('e=>!!e.closest("details")'))
                self.assertIn('Exports',page.locator('#selection-note').inner_text())
                if width<=680:
                    panel.locator(':scope > summary').focus(); panel.locator(':scope > summary').press('Enter')
                    self.assertTrue(panel.evaluate('e=>e.open'))
                    panel.locator(':scope > summary').press('Space'); self.assertFalse(panel.evaluate('e=>e.open'))
                row=page.locator('#results .record-row').first; row.locator('summary').click()
                page.evaluate('Object.defineProperty(navigator,"clipboard",{value:{writeText:()=>Promise.reject(Error("denied"))},configurable:true})')
                row.locator('details button').click()
                self.assertEqual(page.evaluate('getSelection().toString()'),row.locator('.archive-citation').inner_text())
                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)

    def test_stale_research_index_fails_closed_without_erasing_server_content(self):
        page=self.context().new_page()
        stale=dict(self.index); stale['records']=[]
        page.route('**/archive-research-index.json*',lambda route:route.fulfill(json=stale))
        page.goto(self.origin+'/archive.html?scope=published',wait_until='networkidle')
        self.assertTrue(page.locator('#index-error').is_visible())
        self.assertEqual(page.locator('#results .record-row').count(),50)
        self.assertEqual(page.locator('#results [data-from-index]').count(),0)
        self.assertFalse(page.locator('#controls').is_visible())

    def test_official_hold_is_visible_before_opening_provenance(self):
        self.assertTrue(self.index['holds'])
        ident, hold = next(iter(self.index['holds'].items()))
        record = next(r for r in self.index['records'] if r['id']==ident)
        page = self.context().new_page()
        self.open(page,dict(scope='published',record_type='official_link',q=record['title']))
        row = page.locator('#results .record-row').filter(has_text=hold).first
        self.assertTrue(row.locator('.archive-hold').is_visible())
        self.assertEqual(row.locator('.archive-hold').inner_text(),hold)
        self.assertFalse(row.locator('details').evaluate('e=>e.open'))

    def test_invalid_query_is_reported_and_no_javascript_keeps_week_browsing(self):
        page=self.context().new_page(); page.goto(self.origin+'/archive.html?keywords=%22unclosed',wait_until='networkidle')
        self.assertTrue(page.locator('#research-error').is_visible())
        self.assertEqual(page.locator('#results .record-row').count(),50)
        page=self.context(java_script_enabled=False,viewport={'width':375,'height':900}).new_page()
        page.goto(self.origin+'/archive.html')
        self.assertFalse(page.locator('#controls').is_visible())
        self.assertEqual(page.locator('#results .record-row').count(),50)
        page.locator('a[href="corpus.html"]').first.click()
        page.locator('a[href^="week-"]').first.click()
        self.assertGreater(page.locator('a[href^="record/"]').count(),0)

    def test_complete_raw_page_budget_includes_shell_and_has_no_remote_dependencies(self):
        measured=measure_page(self.site/'archive.html',self.site)
        self.assertLessEqual(measured['js_bytes'],10000)
        self.assertLessEqual((self.site/'browse.js').stat().st_size,9500)
        self.assertLessEqual(measured['html_css_bytes'],300000)
        self.assertEqual(measured['external'],[])
        self.assertEqual(measured['js'],['browse.js','shell.js'])
