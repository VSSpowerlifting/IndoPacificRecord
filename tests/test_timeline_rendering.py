"""Publication/private-preview integration and browser accessibility contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from core import timelines as t
from scripts import validate_output
from tests.test_timelines import approve_fixture, pilot_without_mindef_evidence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp


class TimelineRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The pilot chronology cites Singapore MINDEF records and a Brief that
        # the production boundary withholds whole. Rendering/accessibility
        # contracts run under an explicit *synthetic* rights authority; the real
        # works remain held (tests.test_timelines.PilotIsHeldByRightsBoundary).
        rights = mock.patch('core.mindef_public_boundary.editorial_hold', return_value=False)
        rights.start(); cls.addClassCleanup(rights.stop)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        # Derived from the real pilot minus its MINDEF citations (see helper).
        draft_dir = cls.root / 'draft-timelines'
        draft_dir.mkdir()
        cls.pilot = draft_dir / 'maritime-cooperation-2026.json'
        fixture = pilot_without_mindef_evidence()
        # The only 'planned' evidence in the pilot was MINDEF's announcement, now
        # withheld. Keep the planned-basis rendering path covered with a
        # synthetic claim that reuses an already-verified PLA Daily excerpt.
        by_id = {e['id']: e for e in fixture['entries']}
        borrowed = dict(by_id['preparatory-meetings']['evidence'][0])
        borrowed.update(basis='planned', claim='Synthetic planned-basis rendering claim.')
        by_id['sea-phase']['evidence'].insert(0, borrowed)
        cls.pilot.write_text(json.dumps(fixture))
        cls.preview = cls.root / 'private'
        cls.public = cls.root / 'public'
        cls.approved = cls.root / 'approved'
        cls.sources = cls.root / 'timelines'
        cls.sources.mkdir()
        cls.snapshot = gp.snapshot_from_corpus(ROOT / 'pla_watch.db')
        cls.build(cls.preview, timelines_dir=cls.pilot.parent, review_timeline=cls.pilot)
        cls.build(cls.public, site_origin='https://fixture.test', allow_test_origin=True)
        sc = json.loads(cls.pilot.read_text())
        sc['title'] = '<script>Synthetic approval rendering fixture</script>'
        sc['editor_name'] = 'Fixture editor'
        approve_fixture(sc)
        (cls.sources / (sc['slug'] + '.json')).write_text(json.dumps(sc))
        cls.build(cls.approved, timelines_dir=cls.sources, site_origin='https://fixture.test', allow_test_origin=True)

    @classmethod
    def build(cls, out, **options):
        # Keep Timeline publication/asset fixtures independent of live dossiers.
        options.setdefault('dossiers_dir', cls.root / 'no-dossiers')
        return gp.build(out, 'Indo-Pacific Record', ROOT / 'pla_watch.db', snapshot=cls.snapshot, **options)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def detail(self, root=None):
        return (root or self.preview) / 'timeline/maritime-cooperation-2026.html'

    def test_maritime_water_asset_is_scoped_and_decorative(self):
        # The unapproved timeline and its image must not leak into public output.
        route = "assets/timelines/maritime-ocean-texture.webp"
        self.assertFalse((self.public / route).exists())
        for root in (self.preview, self.approved):
            self.assertTrue((root / route).is_file())
            self.assertEqual((root / route).read_bytes(),
                             (ROOT / "site" / route).read_bytes())
            html = self.detail(root).read_text()
            self.assertIn('tl-narrative--maritime', html)
            self.assertNotIn('tl-art-note', html)
            self.assertNotIn('Illustrative AI-generated ocean texture', html)
        css = (self.preview / "timelines.css").read_text()
        self.assertIn('assets/timelines/maritime-ocean-texture.webp', css)
        self.assertIn('@media(max-width:1050px)', css)

    def test_public_draft_exclusion_in_routes_links_feed_and_sitemap(self):
        self.assertFalse((self.public / 'timelines.html').exists())
        self.assertFalse((self.public / 'timeline').exists())
        for route in ('analysis.html', 'briefs/feed.xml', 'sitemap.xml', 'briefs/maritime-cooperation-2026.html', 'record/3924.html'):
            self.assertNotIn('timeline/', (self.public / route).read_text())
        errors = []
        validate_output._validate_timelines(self.public, errors)
        self.assertEqual(errors, [])

    def test_private_preview_is_unindexed_without_canonicals_sitemap_or_feed(self):
        for route in ('analysis.html', 'timelines.html', 'timeline/maritime-cooperation-2026.html'):
            text = (self.preview / route).read_text()
            self.assertIn('noindex, nofollow', text)
            self.assertNotIn('rel="canonical"', text)
            self.assertIn('unapproved and unpublished', text)
        self.assertFalse((self.preview / 'sitemap.xml').exists())
        self.assertFalse((self.preview / 'briefs/feed.xml').exists())
        errors = []
        validate_output._validate_timelines(self.preview, errors)
        self.assertIn('no approved timeline source', ' '.join(errors))

    def test_approved_fixture_links_and_metadata_are_indexable_and_escaped(self):
        text = self.detail(self.approved).read_text()
        self.assertIn('&lt;script&gt;Synthetic approval', text)
        self.assertNotIn('<script>Synthetic approval', text)
        self.assertIn('data-editorial-status="approved"', text)
        self.assertIn('href="https://fixture.test/timeline/maritime-cooperation-2026.html"', text)
        self.assertNotIn('noindex', text)
        self.assertIn('/timeline/maritime-cooperation-2026.html</loc>', (self.approved / 'sitemap.xml').read_text())
        self.assertIn('href="timelines.html"', (self.approved / 'analysis.html').read_text())
        self.assertIn('In Evidence Timelines', (self.approved / 'record/3924.html').read_text())
        self.assertIn('timeline/maritime-cooperation-2026.html', (self.approved / 'briefs/maritime-cooperation-2026.html').read_text())
        self.assertNotIn('timeline/', (self.approved / 'briefs/feed.xml').read_text())

    def test_deploy_gate_accepts_only_matching_approved_rendered_versions(self):
        from core.brief_collection import load_briefs, brief_entry
        from core.desk_registry import load_registry
        published, _ = load_briefs(ROOT / 'briefs', load_registry(), historical_numbers=range(1, 15))
        views, _ = t.load_timelines(ROOT / 'pla_watch.db', {slug:brief_entry(slug, sc) for slug, sc in published}, self.sources)
        with mock.patch('core.timelines.load_timelines', return_value=(views, [])):
            errors = []
            validate_output._validate_timelines(self.approved, errors)
            self.assertEqual(errors, [])
            page = self.detail(self.approved)
            before = page.read_text()
            try:
                page.write_text(before.replace('data-editorial-status="approved"', 'data-editorial-status="draft"'))
                errors = []
                validate_output._validate_timelines(self.approved, errors)
                self.assertIn('differs from its approved', ' '.join(errors))
            finally:
                page.write_text(before)

    def test_references_only_public_page_omits_publisher_text_and_local_body_links(self):
        from bs4 import BeautifulSoup
        sc = json.loads(self.pilot.read_text())
        doc = BeautifulSoup(self.detail(self.approved).read_text(), 'html.parser')
        private = BeautifulSoup(self.detail().read_text(), 'html.parser')
        self.assertFalse(doc.select('blockquote,.tl-original,.tl-translation,a[href*="record/"]'))
        self.assertTrue(private.select('blockquote,.tl-original,a[href*="record/"]'))
        for entry in sc['entries']:
            for ev in entry['evidence']:
                self.assertIsNotNone(doc.select_one('#source-%s' % ev['record_id']))
                self.assertIsNotNone(doc.find('a', href=ev['url']))
                self.assertNotIn(ev['excerpt'], doc.get_text())
        text = self.detail(self.approved).read_text()
        path = self.detail(self.approved)
        from core.brief_collection import load_briefs, brief_entry
        from core.desk_registry import load_registry
        published, _ = load_briefs(ROOT / 'briefs', load_registry(), historical_numbers=range(1, 15))
        views, _ = t.load_timelines(ROOT / 'pla_watch.db',
                                   {slug:brief_entry(slug, sc) for slug, sc in published}, self.sources)
        try:
            path.write_text(text.replace('</article>', '<a href="../record/3924.html">Body</a></article>', 1))
            with mock.patch('core.timelines.load_timelines', return_value=(views, [])):
                errors = []
                validate_output._validate_timelines(self.approved, errors)
                self.assertIn('exposes source text or full-body', ' '.join(errors))
        finally:
            path.write_text(text)

    def test_original_language_headline_is_escaped_in_native_evidence(self):
        from jinja2 import Environment, FileSystemLoader
        from tests.test_timelines import synthetic_timeline, write_db
        db = self.root / 'synthetic-headline.db'
        write_db(db)
        sc = synthetic_timeline()
        records = t.reconcile_sources(sc, db)
        related = {'synthetic-brief':dict(title='Fixture', url='briefs/fixture.html', issue=1)}
        view = t.timeline_view(sc, records, related, True)
        env = Environment(loader=FileSystemLoader(str(ROOT / 'site/preview/templates')), autoescape=True)
        env.filters['reader_date'] = gp.reader_date
        env.filters['month_name'] = lambda n:'September'
        text = env.get_template('timeline.html').render(timeline=view, timelines=[view], page='analysis.html', title='Fixture', nested=True,
                                                       maintainer=dict(name='Fixture', email='fixture@example.test'))
        self.assertIn('&lt;script&gt;Synthetic original headline&lt;/script&gt;', text)
        self.assertNotIn('<script>Synthetic original headline', text)

    def test_review_guards_precede_writes_even_with_symlink_destinations(self):
        spec = importlib.util.spec_from_file_location('timeline_renderer', ROOT / 'site/render.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        alias = self.root / 'production-alias'
        alias.symlink_to(ROOT / 'output', target_is_directory=True)
        for dest in (None, ROOT, ROOT / 'output', ROOT / 'output/nested', ROOT / 'timelines', alias):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                renderer.render_site(output_dir=dest, review_timeline=self.pilot)
        with self.assertRaises(ValueError):
            renderer.render_site('legacy', self.root / 'rejected', review_timeline=self.pilot)
        with self.assertRaises(ValueError):
            renderer.render_site(output_dir=self.root / 'rejected', review_timeline=self.pilot, site_origin='https://fixture.test')
        with self.assertRaises(ValueError):
            self.build(self.root / 'rejected', review_timeline=self.pilot, site_origin='https://fixture.test')
        self.assertFalse((self.root / 'rejected').exists())

    def test_deterministic_pages_styles_and_ledger(self):
        cases = [(self.preview, dict(timelines_dir=self.pilot.parent, review_timeline=self.pilot)),
                 (self.approved, dict(timelines_dir=self.sources, site_origin='https://fixture.test', allow_test_origin=True))]
        for original, options in cases:
            with self.subTest(surface=original.name):
                rebuilt = self.root / ('repeat-' + original.name)
                self.build(rebuilt, **options)
                first = {p.relative_to(original): p.read_bytes() for p in original.rglob('*') if p.is_file()}
                second = {p.relative_to(rebuilt): p.read_bytes() for p in rebuilt.rglob('*') if p.is_file()}
                self.assertEqual(first.keys(), second.keys())
                self.assertEqual(first, second)

    def test_detail_page_budget_and_no_additional_javascript(self):
        from core.frontend_budget import measure_page
        for page in (self.detail(), self.preview / 'timelines.html'):
            budget = measure_page(page, self.preview)
            self.assertLessEqual(budget['html_css_bytes'], 120000, budget)
            self.assertLessEqual(budget['js_bytes'], 10000, budget)
            self.assertEqual(budget['external'], [])
        self.assertIn('src="../reveal.js"', self.detail().read_text())

    def test_flowing_connectors_follow_wrapping_disclosures_and_resizing(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(self.detail().as_uri())
            page.evaluate('document.fonts.ready')
            # Deliberately long test-only titles and expanded evidence exercise
            # variable row heights without editing the canonical pilot.
            page.locator('.tl-entry h3').evaluate_all(
                '(els)=>els.forEach(e=>e.textContent += " — wrapped title fixture ".repeat(4))')
            page.locator('.tl-evidence').evaluate_all('(els)=>els.forEach(e=>e.open=true)')
            page.evaluate("document.documentElement.style.setProperty('--display', 'Georgia, serif')")
            for width in (1280, 1100, 1024, 768, 375, 320, 1280):
                page.set_viewport_size({'width': width, 'height': 900})
                with self.subTest(width=width):
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                    geometry = page.locator('.tl-entry').evaluate_all('''els=>els.map(e=>{
                        const box=s=>e.querySelector(s).getBoundingClientRect();
                        const rail=box('.tl-spine-segment'), branch=box('.tl-branch');
                        const card=box('.tl-entry-body');
                        return {railX:rail.x+rail.width/2, railBottom:rail.bottom,
                            railTop:rail.top, left:branch.left, right:branch.right,
                            top:branch.top, bottom:branch.bottom,
                            cardLeft:card.left, cardRight:card.right,
                            cardTop:card.top, cardBottom:card.bottom};
                    })''')
                    for i, g in enumerate(geometry):
                        left_card = width > 1050 and i % 2 == 0
                        self.assertAlmostEqual(g['right'] if left_card else g['left'], g['railX'], delta=.1)
                        self.assertAlmostEqual(g['left'] if left_card else g['right'],
                                               g['cardRight'] if left_card else g['cardLeft'], delta=.1)
                        self.assertGreater(g['bottom'], g['cardTop'])
                        self.assertLess(g['bottom'], g['cardBottom'])
                        if i < len(geometry) - 1:
                            self.assertAlmostEqual(g['railBottom'], geometry[i+1]['railTop'], delta=.1)
            # No timeline entrance transform may detach the static rail.
            self.assertEqual(page.locator('.tl-entry[data-reveal]').count(), 0)
            browser.close()

    def test_scope_and_planned_evidence_are_visible_without_context_disclosures(self):
        from bs4 import BeautifulSoup
        doc = BeautifulSoup(self.detail().read_text(), 'html.parser')
        self.assertIn('not an independently verified operational history', doc.select_one('.tl-hero').get_text())
        self.assertFalse(doc.select_one('.tl-context-tracks').has_attr('data-wide-open'))
        sea = doc.select_one('#sea-phase')
        self.assertIn('Planned activity:', sea.get_text())
        self.assertIn('Later report:', sea.get_text())
        self.assertEqual([a['href'] for a in doc.select('.tl-jump a')],
                         ['#tl-narrative-heading', '#tl-reconcile-1', '#tl-ledger-heading'])
        sc = json.loads(self.pilot.read_text())
        for entry in sc['entries']:
            rendered = doc.select_one('#' + entry['id'])
            self.assertEqual({a['href'] for a in rendered.select('.tl-citations a')},
                             {'#source-%s' % ev['record_id'] for ev in entry['evidence']})

    def test_offline_browser_mobile_keyboard_motion_print_and_primary_links(self):
        from playwright.sync_api import sync_playwright
        fixture = json.loads(self.pilot.read_text())
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as exc:
                self.skipTest('Chromium unavailable: %s' % str(exc).splitlines()[0])
            try:
                for width in (320, 375, 768, 1280):
                    for js, reduced in ((True, 'no-preference'), (False, 'no-preference'), (True, 'reduce')):
                        with self.subTest(width=width, js=js, reduced=reduced):
                            context = browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=js, reduced_motion=reduced)
                            context.route('https://fonts.**/*', lambda route: route.abort())
                            page = context.new_page()
                            page.goto(self.detail().as_uri())
                            self.assertEqual(page.locator('h1').count(), 1)
                            self.assertEqual(page.locator('.tl-spine>li').count(), len(fixture['entries']))
                            self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                            page.locator('.tl-evidence').first.locator('summary').click()
                            self.assertTrue(page.locator('.tl-evidence').first.evaluate('(e)=>e.open'))
                            self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                            ids = page.locator('[id]').evaluate_all('(els)=>els.map(e=>e.id)')
                            self.assertEqual(len(ids), len(set(ids)))
                            self.assertEqual(page.locator('a[href^="#"]').evaluate_all('(els)=>els.filter(e=>!document.getElementById(e.hash.slice(1))).length'), 0)
                            for anchor in page.locator('a[href*="record/"]').all():
                                target = (self.detail().parent / anchor.get_attribute('href')).resolve()
                                self.assertTrue(target.is_file(), target)
                            self.assertEqual(page.locator('.tl-ledger>ol>li').count(), len({ev['record_id'] for e in fixture['entries'] for ev in e['evidence']}))
                            for control in page.locator('.analysis-nav a,.tl-track a,.tl-evidence summary,.tl-citations a').all():
                                # Transform interpolation can round 40 CSS px down by 0.00002.
                                if control.is_visible():
                                    self.assertGreaterEqual(control.bounding_box()['height'], 39.99)
                            if not js or reduced == 'reduce':
                                for entry in page.locator('.tl-entry').all():
                                    self.assertEqual(entry.evaluate('(e)=>getComputedStyle(e).opacity'), '1')
                            if js:
                                page.evaluate("document.documentElement.classList.add('no-anim')")
                                for entry in page.locator('.tl-entry').all():
                                    self.assertEqual(entry.evaluate('(e)=>getComputedStyle(e).opacity'), '1')
                                page.emulate_media(media='print')
                                self.assertEqual(page.locator('.tl-overview').evaluate('(e)=>getComputedStyle(e).display'), 'none')
                                self.assertEqual(page.locator('.tl-entry').first.evaluate('(e)=>getComputedStyle(e).transform'), 'none')
                            context.close()
                context = browser.new_context(viewport={'width':375,'height':900})
                context.route('https://fonts.**/*', lambda route: route.abort())
                page = context.new_page();page.goto(self.detail().as_uri())
                page.keyboard.press('Tab');self.assertEqual(page.locator(':focus').inner_text(), 'Skip to content')
                page.keyboard.press('Enter')
                page.locator('.tl-evidence summary').first.focus()
                self.assertEqual(page.locator(':focus').evaluate('(e)=>getComputedStyle(e).outlineStyle'), 'solid')
                page.keyboard.press('Enter');self.assertTrue(page.locator('.tl-evidence').first.evaluate('(e)=>e.open'))
                page.locator('.tl-context-tracks>summary').click()
                page.locator('.tl-track a[href="#sea-phase"]').click()
                self.assertTrue(page.url.endswith('#sea-phase'))
                self.assertLess(page.locator('#sea-phase').bounding_box()['y'], 100)
                context.close()
            finally:
                browser.close()
