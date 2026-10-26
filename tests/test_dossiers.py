"""Real frozen-source reconciliation; synthetic authority is test-only."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from core import dossiers as d, dossier_decisions
from core.dossier_contract import read_dossier, validate_dossier_shape, dossier_content_digest
from scripts.reconcile_db import read_only

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / 'dossiers/maritime-cooperation-2026.json'


def draft_fixture(sc):
    """Exercise unapproved paths independently of the real publication status."""
    sc = copy.deepcopy(sc)
    sc.update(editorial_status='draft', editor_name='Pending human editorial review', reviewed_on=None)
    sc.pop('approval', None)
    for source in sc['sources']:
        source['source_use_decision_ref'] = None
    return sc


def approve_fixture(sc):
    """An explicitly synthetic editorial assertion, never sufficient authority."""
    sc['editorial_status'] = 'approved'
    sc['editor_name'] = 'Synthetic fixture editor'
    sc['reviewed_on'] = sc['updated_on']
    for s in sc['sources']:
        s['source_use_decision_ref'] = 'Synthetic fixture source-use decision'
    sc['approval'] = dict(approved_by=sc['editor_name'], approved_on=sc['updated_on'],
        reference='Synthetic test approval; no real human decision', content_sha256=dossier_content_digest(sc))
    return sc


def fixture_decisions(sc):
    return mock.patch.multiple(dossier_decisions,
        SOURCE_USES={'Synthetic fixture source-use decision': {
            s['record_id']: dict(d.source_binding(s), public_fields=sorted(d.PUBLIC_FIELDS)) for s in sc['sources']}},
        PUBLICATIONS={sc['slug']: dict(content_sha256=dossier_content_digest(sc), approval=sc['approval'])})


class DossierSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.frozen = cls.root / 'frozen.db'
        # The original is NEVER opened through sqlite3.connect.
        with read_only(ROOT / 'pla_watch.db') as con, sqlite3.connect(cls.frozen) as target:
            con.backup(target)
        cls.original = draft_fixture(read_dossier(PILOT))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        authority = mock.patch.multiple(dossier_decisions, SOURCE_USES={}, PUBLICATIONS={})
        authority.start(); self.addCleanup(authority.stop)
        self.sc = copy.deepcopy(self.original)
        self.case = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.case.cleanup)
        self.case_root = Path(self.case.name)
        self.db = self.case_root / 'input.db'
        shutil.copyfile(self.frozen, self.db)

    def test_real_draft_exact_sources_safe_projection_and_chronology(self):
        records = d.reconcile_dossier_sources(self.sc, self.db)
        self.assertEqual(sorted(records), [3924, 4102, 4164, 4466, 4472])
        for rec in records.values():
            self.assertEqual(set(rec), {'id', 'url', 'published_on', 'desk', 'source_name', 'institution_name', 'language'})
        self.assertEqual(len(d.chronology_view(self.sc, records)), 6)
        self.assertEqual(len(d.publication_holds(self.sc)), 6)

    def test_identity_mutations_name_affected_findings(self):
        for field, value in [('desk', 'singapore'), ('source_id', 'other_source'),
            ('institution_id', 'other_institution'), ('language', 'en'),
            ('published_on', '2026-09-07'), ('url', 'https://example.org/changed')]:
            with self.subTest(field=field):
                sc = copy.deepcopy(self.sc)
                sc['sources'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'identity_mismatch.*preparation-and-opening'):
                    d.reconcile_dossier_sources(sc, self.db)

    def test_body_version_mutation_is_rejected_without_printing_body(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE articles SET text_original='Changed synthetic body' WHERE id=3924")
        with self.assertRaisesRegex(ValueError, 'version_mismatch.*preparation-and-opening') as caught:
            d.reconcile_dossier_sources(self.sc, self.db)
        self.assertNotIn('Changed synthetic body', str(caught.exception))

    def test_missing_source_is_actionable(self):
        with sqlite3.connect(self.db) as c:
            c.execute('DELETE FROM articles WHERE id=3924')
        with self.assertRaisesRegex(ValueError, 'unavailable_evidence.*3924.*preparation-and-opening'):
            d.reconcile_dossier_sources(self.sc, self.db)

    def test_screening_rejection_disabled_and_retired_are_held(self):
        for sql, args, expected in [
            ('UPDATE articles SET passed_relevance=0 WHERE id=3924', (), 'ineligible_source'),
            ("UPDATE sources SET enabled=0 WHERE slug='pla_daily'", (), 'ineligible_source'),
            ('INSERT INTO retired_article_urls VALUES (?,?,?,?,?)',
             (hashlib.sha256(self.sc['sources'][0]['url'].encode()).hexdigest(),3924,'pla_daily','2026-10-23','a'*64), 'ineligible_source_retired')]:
            with self.subTest(sql=sql):
                shutil.copyfile(self.frozen,self.db)
                with sqlite3.connect(self.db) as c:
                    c.execute(sql,args)
                with self.assertRaisesRegex(ValueError,expected):
                    d.reconcile_dossier_sources(self.sc,self.db)

    def test_dangling_support_and_counterevidence_fail_shape(self):
        for field in ('source_record_ids','counterevidence_ids'):
            sc=copy.deepcopy(self.sc)
            sc['sections'][0]['claims'][0][field]=[999999]
            with self.assertRaisesRegex(ValueError,'absent from the source ledger'):
                validate_dossier_shape(sc)

    def test_chronology_content_mismatch_holds_instead_of_drifting(self):
        records=d.reconcile_dossier_sources(self.sc,self.db)
        self.sc['chronology']['content_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'chronology_version_mismatch'):
            d.chronology_view(self.sc,records)

    def test_reported_windows_share_exact_inclusive_axis_and_bound_sources(self):
        records = d.reconcile_dossier_sources(self.sc, self.db)
        chronology = d.chronology_view(self.sc, records)
        view = d.reading_view(self.sc, records, chronology)
        comparison = view['comparison']
        self.assertEqual([day['iso'] for day in comparison['days']],
                         ['2026-09-%02d' % n for n in range(3, 10)])
        china, singapore = comparison['windows']
        self.assertEqual(china['source_ids'], [4164])
        self.assertEqual(singapore['source_ids'], [4466, 4472])
        self.assertEqual(china['cells'], [True] * 7)
        self.assertEqual(singapore['cells'], [False, False] + [True] * 5)
        self.assertEqual(china['end'], singapore['end'])
        self.assertEqual([c['ordinal'] for c in view['findings'].values()],
                         ['%02d' % n for n in range(1, 9)])
        for rec in view['ledger']:
            self.assertEqual([c['id'] for c in rec['findings']],
                             d.affected_findings(self.sc, rec['id']))
        for event in view['chronology_entries']:
            self.assertTrue(event['findings'], event['id'])

    def test_window_claim_chronology_or_citation_drift_is_rejected(self):
        records = d.reconcile_dossier_sources(self.sc, self.db)
        chronology = d.chronology_view(self.sc, records)
        for change in ('claim_date', 'chronology_date', 'claim_sources', 'chronology_sources'):
            sc, entries = copy.deepcopy(self.sc), copy.deepcopy(chronology)
            claim = next(c for s in sc['sections'] for c in s['claims'] if c['id'] == 'ministry-window')
            entry = next(e for e in entries if e['id'] == 'ministry-interval')
            if change == 'claim_date': claim['event_period']['start'] = '2026-09-04'
            if change == 'chronology_date': entry['event']['start'] = '2026-09-04'
            if change == 'claim_sources': claim['source_record_ids'] = [3924]
            if change == 'chronology_sources': entry['evidence'][0]['record_id'] = 3924
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'reported_window_binding_mismatch.*ministry-window'):
                d.reported_windows(sc, entries)

    def test_approval_like_assertions_have_no_authority(self):
        approve_fixture(self.sc)
        validate_dossier_shape(self.sc)
        records=d.reconcile_dossier_sources(self.sc,self.db)
        holds=d.publication_holds(self.sc)
        self.assertEqual([h['code'] for h in holds], ['source_use_hold']*5+['editorial_hold'])
        with fixture_decisions(self.sc):
            self.assertEqual(d.publication_holds(self.sc),[])

    def test_reuse_decision_is_exact_source_and_public_field_scoped(self):
        approve_fixture(self.sc)
        with fixture_decisions(self.sc):
            grant=dossier_decisions.SOURCE_USES['Synthetic fixture source-use decision'][3924]
            for field,value in [('url','https://example.org/changed'),('stored_original_sha256','0'*64),('public_fields',['original_text'])]:
                prior=copy.deepcopy(grant[field]);grant[field]=value
                self.assertEqual(d.publication_holds(self.sc)[0]['code'],'source_use_hold')
                grant[field]=prior

    def test_editorial_changes_invalidate_synthetic_approval(self):
        approve_fixture(self.sc)
        for mutate in [lambda s:s.update(overview='Changed editorial overview.'),
            lambda s:s['scope'].update(included='Changed scope.'),
            lambda s:s['chronology'].update(content_sha256='0'*64),
            lambda s:s['sources'][0].update(source_use_decision_ref='Changed receipt'),
            lambda s:s['sections'][0]['claims'][0].update(limits='Changed qualification.')]:
            sc=copy.deepcopy(self.sc);mutate(sc)
            with self.assertRaisesRegex(ValueError,'digest no longer matches'):
                validate_dossier_shape(sc)

    def test_source_check_preserves_database_bytes_and_leaves_no_sidecars(self):
        before=hashlib.sha256(self.db.read_bytes()).digest()
        d.reconcile_dossier_sources(self.sc,self.db)
        self.assertEqual(before,hashlib.sha256(self.db.read_bytes()).digest())
        self.assertEqual(sorted(p.name for p in self.case_root.iterdir()),['input.db'])

    def test_registered_identifiers_do_not_widen_route_slugs(self):
        validate_dossier_shape(self.sc)
        self.sc['slug']='not_a_route'
        with self.assertRaisesRegex(ValueError,'unsafe stable slug'):
            validate_dossier_shape(self.sc)

    def test_preview_path_boundaries(self):
        for path in [ROOT/'new-review',ROOT/'output/new-review',Path('relative-review'),self.case_root]:
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'new_external_destination'):
                d.validate_review_destination(path)
        link=self.case_root/'alias';link.symlink_to(self.case_root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'new_external_destination'):
            d.validate_review_destination(link/'new-child')
        other=self.case_root/'other-repository';other.mkdir();(other/'.git').write_text('gitdir: fixture')
        with self.assertRaisesRegex(ValueError,'new_external_destination'):
            d.validate_review_destination(other/'new-child')
        self.assertEqual(d.validate_review_destination(self.case_root/'new-child'),(self.case_root/'new-child').resolve())

    def test_publication_loader_refuses_forgery_and_draft_overwrite(self):
        folder=self.case_root/'dossiers';folder.mkdir()
        file=folder/(self.sc['slug']+'.json')
        related={slug:dict(slug=slug) for slug in self.sc['related_briefs']}
        file.write_text(json.dumps(self.sc))
        self.assertEqual(d.load_dossiers(self.db,related,folder)[0],[])
        approve_fixture(self.sc);file.write_text(json.dumps(self.sc))
        with self.assertRaisesRegex(ValueError,'publication_validation_failed'):
            d.load_dossiers(self.db,related,folder)
        with fixture_decisions(self.sc):
            draft=copy.deepcopy(self.original);file.write_text(json.dumps(draft))
            with self.assertRaisesRegex(ValueError,'unapproved_revision_would_replace'):
                d.load_dossiers(self.db,related,folder)

    def test_separate_draft_timeline_cannot_be_public_related_work(self):
        self.sc['related_timelines']=['maritime-cooperation-2026']
        folder=self.case_root/'dossiers';folder.mkdir()
        file=folder/(self.sc['slug']+'.json');file.write_text(json.dumps(self.sc))
        related={slug:dict(slug=slug) for slug in self.sc['related_briefs']}
        with self.assertRaisesRegex(ValueError,'related_timeline_not_approved'):
            d.load_dossiers(self.db,related,folder,file)

    def test_separate_revision_reviews_without_replacing_approved_canonical(self):
        folder=self.case_root/'dossiers';folder.mkdir();drafts=folder/'drafts';drafts.mkdir()
        approved=approve_fixture(copy.deepcopy(self.sc))
        canonical=folder/(self.sc['slug']+'.json');canonical.write_text(json.dumps(approved))
        revision=copy.deepcopy(self.original)
        revision['overview']='Synthetic private revision of the dossier overview.'
        candidate=drafts/canonical.name;candidate.write_text(json.dumps(revision))
        related={slug:dict(slug=slug) for slug in self.sc['related_briefs']}
        with fixture_decisions(approved):
            public,_=d.load_dossiers(self.db,related,folder)
            private,_=d.load_dossiers(self.db,related,folder,candidate)
        self.assertEqual(public[0]['overview'],approved['overview'])
        self.assertEqual(private[0]['overview'],revision['overview'])
        self.assertTrue(private[0]['is_review'])
        self.assertEqual(len(private),1)
        self.assertEqual(json.loads(canonical.read_text()),approved)


THEMATIC = ROOT / 'dossiers/china-singapore-naval-cooperation.json'


class ThematicDossierSources(unittest.TestCase):
    """Link-only official pages, derived chronology and case-study binding."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / 'frozen.db'
        with read_only(ROOT / 'pla_watch.db') as con, sqlite3.connect(cls.db) as target:
            con.backup(target)
        cls.original = read_dossier(THEMATIC)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        authority = mock.patch.multiple(dossier_decisions, SOURCE_USES={}, PUBLICATIONS={})
        authority.start(); self.addCleanup(authority.stop)
        self.sc = copy.deepcopy(self.original)

    def test_real_draft_is_unapproved_and_every_source_is_held(self):
        self.assertEqual(self.sc['editorial_status'], 'draft')
        self.assertNotIn('approval', self.sc)
        holds = d.publication_holds(self.sc)
        self.assertEqual({h.get('external_id') for h in holds if 'external_id' in h},
                         {x['id'] for x in self.sc['external_sources']})
        self.assertEqual({h.get('record_id') for h in holds if 'record_id' in h},
                         {s['record_id'] for s in self.sc['sources']})
        self.assertIn('editorial_hold', [h['code'] for h in holds])

    def test_external_sources_are_registered_institutions_and_link_only(self):
        externals = d.reconcile_external_sources(self.sc, self.db)
        self.assertEqual(sorted(externals), sorted(x['id'] for x in self.sc['external_sources']))
        for ext in externals.values():
            self.assertTrue(ext['institution_name'])
            self.assertRegex(ext['url'], r'^https?://')
            for field in ('text', 'title', 'text_original', 'stored_original_sha256'):
                self.assertNotIn(field, ext)
        self.sc['external_sources'][0]['institution_id'] = 'not-a-registered-institution'
        with self.assertRaisesRegex(ValueError, 'unknown_external_institution'):
            d.reconcile_external_sources(self.sc, self.db)

    def test_derived_chronology_orders_by_event_and_keeps_interpretation_out(self):
        entries = d.derived_chronology(self.sc)
        claims = {c['id']: c for s in self.sc['sections'] for c in s['claims']}
        self.assertTrue(entries)
        self.assertEqual(entries, sorted(entries, key=lambda e: (e['event']['start'], e['event']['end'], e['id'])))
        for entry in entries:
            claim = claims[entry['derived_from']]
            self.assertNotEqual(claim['claim_kind'], 'editorial_interpretation')
            self.assertEqual([e['record_id'] for e in entry['evidence']],
                             claim['source_record_ids'] + claim.get('external_source_ids', []))
            # Publication dates are never substituted for event dates.
            self.assertTrue(all(e['published_on'] is None for e in entry['evidence']))
        self.assertTrue(any(e['record_id'].startswith('x') for entry in entries for e in entry['evidence']))

    def test_case_study_must_be_rendered_alongside(self):
        view = dict(slug=self.sc['slug'], case_studies=['maritime-cooperation-2026'], case_study_views=[])
        with self.assertRaisesRegex(ValueError, 'case_study_not_published'):
            d.link_case_studies([view])
        case = dict(slug='maritime-cooperation-2026', case_studies=[], case_study_views=[],
                    parent_dossiers=[], kind='living', kind_label='Living Dossier')
        d.link_case_studies([view, case])
        self.assertEqual(view['case_study_views'], [case])
        self.assertEqual(case['parent_dossiers'], [view])
        self.assertEqual((case['kind'], case['kind_label']), ('case_study', 'Exercise case study'))
