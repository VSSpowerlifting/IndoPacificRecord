"""Synthetic, offline contracts; no publisher originals or human verdict fixtures."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_independent_audit_packet as audit


class AuditPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / 'repo'
        cls.root.mkdir()
        c = sqlite3.connect(cls.root / 'pla_watch.db')
        c.executescript('''
          CREATE TABLE articles(id INTEGER, source_id INTEGER, url TEXT,
            title_original TEXT, text_original TEXT, text_english TEXT,
            published_date TEXT, scraped_at TEXT, processing_state TEXT,
            passed_relevance INTEGER, analyzed_at TEXT, model_id TEXT, prompt_version TEXT);
          CREATE TABLE sources(id INTEGER, slug TEXT, display_name TEXT,
            desk_id TEXT, language_tag TEXT, institution_id TEXT);
          CREATE TABLE institutions(institution_id TEXT, display_name TEXT);
          INSERT INTO institutions VALUES('fixture','Synthetic fixture institution');
          INSERT INTO sources VALUES(1,'fixture_a','Synthetic family A','fixture','en','fixture');
          INSERT INTO sources VALUES(2,'fixture_b','Synthetic family B','fixture','en','fixture');
        ''')
        for i in range(1, 24):
            c.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (i, 1 if i % 2 else 2, 'https://example.org/fixture/%s' % i,
                       '[SYNTHETIC TITLE]', '[SYNTHETIC BODY %s]' % i if i != 21 else None,
                       None, None if i == 23 else '2026-%s-01' % ('05' if i < 10 else '10'),
                       '2026-10-27', 'fixture', None, None, None, None))
            if i != 22:
                p = cls.root / ('output/record/%s.html' % i)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('<link rel="canonical" href="https://indopacificrecord.org/record/%s.html"><a href="https://example.org/fixture/%s">Synthetic</a>' % (i, i))
        c.commit()
        c.close()
        (cls.root / 'output/archive-research-index.json').write_text(json.dumps({'records': []}))
        p = cls.root / audit.NOTES
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'checks': [{'id': 1, 'source': 'fixture_a', 'comparison': 'historical_text_contamination', 'next_step': 'quality_hold'}]}))
        p = cls.root / audit.METHOD
        p.parent.mkdir(parents=True)
        p.write_text('[SYNTHETIC METHODOLOGY]')
        def git(*args):
            return subprocess.check_output(['git', '-C', str(cls.root), *args], stderr=subprocess.DEVNULL)
        git('init')
        git('add', '.')
        git('-c', 'user.name=Synthetic fixture', '-c', 'user.email=fixture@example.org', 'commit', '-m', 'Synthetic fixture only')
        cls.rev = git('rev-parse', 'HEAD').decode().strip()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.patch = patch.object(audit, 'ROOT', self.root)
        self.patch.start()
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.out.cleanup)
        self.addCleanup(self.patch.stop)
        self.path = Path(self.out.name) / 'packet'

    def build(self):
        return audit.build(self.rev, audit.SEED, self.path)

    def test_reproduction_pending_and_missing_evidence(self):
        first = self.build()
        second_path = Path(self.out.name) / 'second'
        second = audit.build(self.rev, audit.SEED, second_path)
        self.assertEqual(first, second)
        self.assertEqual(20, first['eligible_population'])
        self.assertEqual(20, len(first['sample']))
        self.assertEqual({'no_preserved_body', 'no_committed_record_page', 'missing_or_invalid_publication_date'}, {x['reason'] for x in first['excluded']})
        self.assertTrue(all('Raw publisher' in x['limitations'][0] for x in first['sample']))
        self.assertFalse(first['human_audit_completed'])
        reviews = json.loads((self.path / 'reviews.json').read_text())
        self.assertTrue(all(v['outcome'] == 'pending' and v['reviewer'] is None for r in reviews.values() for v in r.values()))
        self.assertEqual(first, audit.verify(self.path))
        with self.assertRaises(FileExistsError):
            self.build()

    def test_identity_page_and_manifest_tampering_detected(self):
        self.build()
        p = self.path / 'manifest.json'
        original = p.read_bytes()
        value = json.loads(original)
        value['sample'][0]['publisher_url'] = 'https://example.org/wrong'
        p.write_bytes(audit.encoded(value))
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            audit.verify(self.path)
        p.write_bytes(original)
        (self.path / 'sample/01.html').write_text('[CHANGED SYNTHETIC PAGE]')
        with self.assertRaisesRegex(ValueError, 'evidence changed'):
            audit.verify(self.path)

    def test_human_verdict_cannot_be_unsigned_or_future_dated(self):
        items = [{'identity': 'synthetic:1'}]
        reviews = audit.pending_reviews(items)
        audit.validate_reviews(reviews, ['synthetic:1'])
        verdict = reviews['synthetic:1']['extraction']
        verdict['outcome'] = 'pass'
        with self.assertRaisesRegex(ValueError, 'requires reviewer'):
            audit.validate_reviews(reviews, ['synthetic:1'])
        verdict.update(reviewer='SYNTHETIC VALIDATION ONLY', review_date='9999-01-01', evidence_note='Synthetic input to reject')
        with self.assertRaisesRegex(ValueError, 'actual review date'):
            audit.validate_reviews(reviews, ['synthetic:1'])
        verdict['outcome'] = 'pending'
        with self.assertRaisesRegex(ValueError, 'unsigned'):
            audit.validate_reviews(reviews, ['synthetic:1'])

    def test_selection_order_seed_capacity_and_strata(self):
        rows = [{'identity': 'synthetic:%s' % i, 'version_sha256': str(i), 'stratum': 'A' if i < 25 else 'B'} for i in range(30)]
        chosen = audit.select(rows, 20, 'seed-one')
        self.assertEqual(chosen, audit.select(list(reversed(rows)), 20, 'seed-one'))
        self.assertNotEqual(chosen, audit.select(rows, 20, 'seed-two'))
        self.assertEqual({'A', 'B'}, {r['stratum'] for r in chosen})
        changed = copy.deepcopy(rows)
        changed[0]['version_sha256'] = 'new version'
        self.assertNotEqual(audit.rank('seed-one', rows[0]), audit.rank('seed-one', changed[0]))
        with self.assertRaises(ValueError):
            audit.select(rows[:2], 20, 'seed')
        with self.assertRaises(ValueError):
            audit.select([dict(r, stratum=r['identity']) for r in rows], 20, 'seed')

    def test_supplement_separate_with_machine_preference(self):
        def item(ident, desk, kind):
            return {'id': ident, 'desks': [desk], 'record_type': kind}
        index = {'records': [item('a', 'sampled', 'official_link'), item('b', 'other', 'official_link'), item('c', 'other', 'machine_explanation')]}
        chosen = audit.supplement(index, {'sampled'}, 'seed')
        self.assertEqual(['c'], [r['identity'] for r in chosen])
        self.assertEqual([], audit.supplement({'records': []}, set(), 'seed'))

    def test_repository_output_guard(self):
        self.assertEqual(1, self.exit_code(['--out', str(self.root / 'private-packet')]))

    def exit_code(self, argv):
        try:
            return audit.main(argv)
        except SystemExit as exc:
            return exc.code


if __name__ == '__main__':
    unittest.main()
