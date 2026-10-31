"""Current source-use holds outrank configuration and historical qualification."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from core.viewmodel import PublicView, SourceView

ROOT = Path(__file__).resolve().parents[1]


class CollectionHoldViews(unittest.TestCase):
    def test_mindef_hold_survives_enabled_and_disabled_configuration(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                source = SourceView('sg_mindef_releases', 'Synthetic source',
                                    'singapore', enabled, True)
                self.assertIn('on hold', source.collection_hold)
                self.assertTrue(source.collection_label.startswith('On hold'))
                self.assertEqual(source.enabled, enabled)

    def test_other_sources_keep_their_configuration_and_status(self):
        source = SourceView('synthetic_other', 'Synthetic source',
                            'singapore', True, True)
        self.assertIsNone(source.collection_hold)
        self.assertEqual(source.collection_label, 'Enabled')
        view = PublicView(ROOT / 'pla_watch.db')
        for desk in view.desk_directory().desks:
            if desk.slug != 'singapore':
                self.assertEqual(desk.status_label, desk.entry.status_label)

    def test_mixed_desk_does_not_claim_all_collection_is_held(self):
        desk = PublicView(ROOT / 'pla_watch.db').desk_detail('singapore')
        source = SourceView('synthetic_other', 'Synthetic source',
                            'singapore', True, True)
        mixed = replace(desk, sources=desk.sources + [source])
        self.assertFalse(mixed.collection_on_hold)
        self.assertEqual(mixed.status_label, mixed.entry.status_label)
        self.assertTrue(desk.collection_on_hold)
        self.assertEqual(desk.status, desk.entry.status)
        self.assertEqual(desk.enabled_source_count, desk.entry.enabled_source_count)

    def test_old_successful_outcome_cannot_override_hold(self):
        view = PublicView(ROOT / 'pla_watch.db')
        source = replace(view.source_detail('sg_mindef_releases'),
                         latest_status='ok', latest_run_at='2026-10-28 12:00:00')
        env = Environment(loader=FileSystemLoader(
            str(ROOT / 'site/preview/templates')), autoescape=True)
        for name in ('script_lang', 'count', 'source_type_label'):
            env.filters[name] = lambda value: value
        env.filters['status_label'] = lambda value: 'Collected'
        env.filters['status_prose'] = lambda value: 'Synthetic historical success.'
        html = env.get_template('source.html').render(
            source=source, source_desk=view.desk_detail('singapore'),
            desks=view.desk_directory(), snapshot={}, maintainer={})
        text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
        self.assertIn('As of 2026-10-28 12:00:00: Collected', text)
        self.assertIn('Historical outcome only', text)
        self.assertIn('On hold — configured enabled', text)
        self.assertNotIn('Live — collecting', text)


class CollectionHoldRendered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='ipr-hold-display-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.out = Path(cls.temp.name) / 'site'
        subprocess.run([sys.executable, str(ROOT / 'site/render.py'),
                        '--out', str(cls.out), '--site-origin',
                        'https://indopacificrecord.org'], cwd=ROOT,
                       check=True, capture_output=True, text=True)

    def page(self, route):
        return BeautifulSoup((self.out / route).read_text(), 'html.parser')

    def test_desk_has_no_current_collection_claim(self):
        page = self.page('singapore.html')
        text = page.get_text(' ', strip=True)
        self.assertIn('Historical records — new collection on hold', text)
        self.assertNotIn('Live — collecting', text)
        self.assertNotIn('new records are now collected', text)
        self.assertNotIn('This desk is live.', text)
        self.assertIn('On hold — configured enabled', text)
        self.assertIn('Sources configured enabled — collection on hold', text)
        # Historical source/analysis counts remain available, without implying
        # that withheld machine readings are public or new work may run.
        desk = PublicView(ROOT / 'pla_watch.db').desk_detail('singapore')
        stats = {r.dt.get_text(): r.dd.get_text() for r in page.select('.stat-row')}
        self.assertEqual(stats['Source records'], str(desk.record_count))
        self.assertEqual(stats['Historically analyzed records'], str(desk.analyzed_count))
        self.assertIn('No separate Day 30 human checkpoint review is on record', text)
        self.assertIn('Owner sign-off', text)

    def test_source_labels_and_historical_result_respect_current_hold(self):
        page = self.page('source/sg_mindef_releases.html')
        text = page.get_text(' ', strip=True)
        self.assertNotIn('Live — collecting', text)
        self.assertNotIn('Enabled for collection Yes', text)
        self.assertIn('On hold — configured enabled', text)
        self.assertIn('Historical outcome only', text)
        source = PublicView(ROOT / 'pla_watch.db').source_detail('sg_mindef_releases')
        if source.latest_status:
            self.assertIn('As of ' + source.latest_run_at, text)
        for region in (page.select_one('.eyebrow'), page.select_one('.lede'),
                       page.select_one('.atlas-spine')):
            self.assertIsNotNone(region)
            self.assertIn('collection on hold', region.get_text())
