"""Production render under real decisions: the two bound Dossiers return, held works stay held.

No authority is mocked here. False-hold evidence: on main 4f49720ad5 a clean
production render omitted both approved Dossiers although each MINDEF record
they cite is bound by an exact owner SOURCE_USES grant. Briefs No. 15, 16 and
17 carry MINDEF publisher titles in their signed sidecars and must stay held,
as must the unapproved Maritime Cooperation timeline.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp  # noqa: E402

HELD_BRIEFS = ('maritime-cooperation-2026', 'trident-resolve-regional-scale-specific-chinese-tasks',
               'xiangshan-security-frames-defense-ties')
DOSSIERS = ('china-singapore-naval-cooperation', 'maritime-cooperation-2026')


class ProductionDossierRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'site'
        gp.build(cls.out, 'Indo-Pacific Record', ROOT / 'pla_watch.db',
                 snapshot=gp.snapshot_from_corpus(ROOT / 'pla_watch.db'),
                 site_origin='https://indopacificrecord.org')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bound_dossiers_and_their_discovery_render(self):
        for slug in DOSSIERS:
            self.assertTrue((self.out / 'dossier' / (slug + '.html')).is_file(), slug)
        collection = (self.out / 'dossiers.html').read_text(encoding='utf-8')
        analysis = (self.out / 'analysis.html').read_text(encoding='utf-8')
        self.assertIn('href="dossiers.html"', analysis)
        for slug in DOSSIERS:
            self.assertIn('dossier/%s.html' % slug, collection)
        case = (self.out / 'dossier/maritime-cooperation-2026.html').read_text(encoding='utf-8')
        self.assertIn('china-singapore-naval-cooperation.html', case)

    def test_mindef_held_works_stay_held(self):
        analysis = (self.out / 'analysis.html').read_text(encoding='utf-8')
        for slug in HELD_BRIEFS:
            self.assertFalse((self.out / 'briefs' / (slug + '.html')).exists(), slug)
            self.assertNotIn('briefs/%s.html' % slug, analysis)
        self.assertFalse(list(self.out.glob('timeline*/maritime-cooperation-2026*')))
        for slug in DOSSIERS:
            page = (self.out / 'dossier' / (slug + '.html')).read_text(encoding='utf-8')
            self.assertNotIn('Related approved analysis', page)
            for held in HELD_BRIEFS:
                self.assertNotIn('briefs/%s.html' % held, page)

    def test_no_mindef_publisher_title_reaches_public_bytes(self):
        titles = set()
        for path in (ROOT / 'briefs').glob('*.json'):
            sidecar = json.loads(path.read_text(encoding='utf-8'))
            for entry in sidecar.get('source_trail', []) if isinstance(sidecar, dict) else []:
                if entry.get('source_id') == 'sg_mindef_releases':
                    titles.update(v for v in (entry.get('title_original'), entry.get('title')) if v)
        self.assertTrue(titles)
        for path in self.out.rglob('*'):
            if path.is_file() and path.suffix in ('.html', '.json', '.xml', '.txt', '.js'):
                raw = path.read_text(encoding='utf-8', errors='ignore')
                for title in titles:
                    self.assertNotIn(title, raw, path.relative_to(self.out).as_posix())


if __name__ == '__main__':
    unittest.main()
