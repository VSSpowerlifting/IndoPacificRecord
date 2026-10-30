"""Synthetic expressions only: physical sanitation, retry and custody gates."""
import hashlib
import json
import sqlite3
import unittest
from unittest import mock

from core.mindef_public_boundary import (
    project, assert_projected, table_digests, editorial_hold,
)
from scripts.stage_mindef_public_projection import install_candidate
from tests import test_mindef_stage_projection as fixtures


class MINDEFPublicBoundary(unittest.TestCase):
    setUp = fixtures.StagedMINDEFSeparationTests.setUp
    run_stage = fixtures.StagedMINDEFSeparationTests.run_stage

    def test_physical_rebuild_and_write_guards_survive_reopen(self):
        self.run_stage()
        raw = self.public.read_bytes()
        for expression in (b'FAKE ORIGINAL TITLE', b'FAKE SOURCE BODY', b'FAKE SUMMARY'):
            self.assertNotIn(expression, raw)
        with sqlite3.connect(self.public) as con:
            self.assertEqual(con.execute('PRAGMA freelist_count').fetchone()[0], 0)
            for sql in (
                "UPDATE articles SET text_original='SYNTHETIC NEW BODY' WHERE id=101",
                "UPDATE articles SET summary_english='SYNTHETIC NEW SUMMARY' WHERE id=101",
                "INSERT INTO articles(id,source_id,text_original) VALUES(303,1,'SYNTHETIC NEW BODY')",
            ):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'MINDEF public expression withheld'):
                    con.execute(sql)
            for sql in ("UPDATE sources SET slug='other' WHERE id=1", "DELETE FROM sources WHERE id=1"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, 'MINDEF source identity is preserved'):
                    con.execute(sql)
            # A metadata-only admission is allowed. A newer identity requires
            # no engineering exception, but grants no source-text/model rights.
            con.execute("INSERT INTO articles(id,source_id,url,content_hash) "
                        "VALUES(303,1,'https://example.invalid/synthetic','SYNTHETIC HASH')")
            con.commit()
            assert_projected(con)

    def test_projection_retry_is_logically_idempotent(self):
        self.run_stage()
        with sqlite3.connect(self.public) as con:
            before = table_digests(con)
            project(con)
            self.assertEqual(before, table_digests(con))
            self.assertEqual(con.execute('SELECT count(*) FROM mindef_private_record_bindings').fetchone()[0], 1)

    def test_unreviewed_auxiliary_table_or_article_field_holds_entire_projection(self):
        with sqlite3.connect(self.source) as con:
            con.execute('CREATE TABLE new_evidence (body TEXT)')
        with self.assertRaisesRegex(ValueError, 'unreviewed public schema'):
            self.run_stage()
        self.assertFalse(self.private.exists())
        self.assertFalse(self.public.exists())
        with sqlite3.connect(self.source) as con:
            con.execute('DROP TABLE new_evidence')
            con.execute('ALTER TABLE articles ADD COLUMN new_expression TEXT')
        with self.assertRaisesRegex(ValueError, 'unreviewed article columns'):
            self.run_stage()

    def test_live_wal_is_refused_without_losing_source(self):
        wal = self.source.with_name(self.source.name + '-wal')
        wal.write_bytes(b'SYNTHETIC JOURNAL')
        before = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, 'quiescent'):
            self.run_stage()
        self.assertEqual(before, self.source.read_bytes())
        self.assertFalse(self.private.exists())

    def test_crash_rolls_back_all_staged_files(self):
        with mock.patch('scripts.stage_mindef_public_projection.project', side_effect=RuntimeError('synthetic crash')):
            with self.assertRaisesRegex(RuntimeError, 'synthetic crash'):
                self.run_stage()
        for path in (self.private, self.public, self.receipt):
            self.assertFalse(path.exists())

    def test_cutover_refuses_a_late_daily_change(self):
        self.run_stage()
        proof = self.base / 'restore.json'
        receipt = json.loads(self.receipt.read_text())
        proof.write_text(json.dumps({
            'durable_private_custody_confirmed': True,
            'restored_db_sha256': receipt['private_db_sha256'],
            'source_db_sha256': receipt['source_db_sha256'],
        }))
        with sqlite3.connect(self.source) as con:
            con.execute("UPDATE articles SET content_hash='SYNTHETIC LATE UPDATE' WHERE id=202")
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'baseline mismatch'):
            install_candidate(self.source, self.public, self.receipt, self.private, proof)
        self.assertEqual(before, hashlib.sha256(self.source.read_bytes()).hexdigest())

    def test_verified_install_and_crash_retry_are_idempotent(self):
        self.run_stage()
        proof = self.base / 'restore.json'
        receipt = json.loads(self.receipt.read_text())
        proof.write_text(json.dumps({
            'durable_private_custody_confirmed': True,
            'restored_db_sha256': receipt['private_db_sha256'],
            'source_db_sha256': receipt['source_db_sha256'],
            'private_git_commit': 'a' * 40,  # Explicitly synthetic local custody proof.
        }))
        install_candidate(self.source, self.public, self.receipt, self.private, proof)
        expected = self.source.read_bytes()
        retry = install_candidate(self.source, self.public, self.receipt, self.private, proof)
        self.assertTrue(retry['idempotent_retry'])
        self.assertEqual(expected, self.source.read_bytes())
        self.assertEqual(hashlib.sha256(expected).hexdigest(), receipt['public_candidate_db_sha256'])

    def test_exact_link_scope_and_signed_editorial_hold(self):
        approved = 'https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/'
        self.assertFalse(editorial_hold({'url': approved}))
        self.assertTrue(editorial_hold({'url': approved + '?other=1'}))
        self.assertTrue(editorial_hold({'sources': [{'source_id': 'sg_mindef_releases'}]}))
        self.assertFalse(editorial_hold({'url': 'https://www.mod.go.jp/example'}))

    def test_processing_hold_selects_exact_source_ids(self):
        from storage import db
        with mock.patch.object(db, 'DB_PATH', self.source):
            self.assertEqual(db.get_article_ids_for_source('sg_mindef_releases'), {101})
            self.assertEqual(db.get_article_ids_for_source('unrelated'), {202})

    def test_normal_daily_new_china_record_and_singapore_hold_retry(self):
        from tests.integration.test_pipeline_run import PipelineRunCase, scraper_factory, article
        from adapters.legacy import LegacyScraperAdapter
        case = PipelineRunCase()
        case.setUp()
        self.addCleanup(case.tearDown)
        url = 'https://example.invalid/synthetic-china-daily-retry'
        parsed = article(url, 'synthetic')
        adapter = scraper_factory(urls=[url], pages={url: 'synthetic page'}, parsed={url: parsed})
        with mock.patch('analysis.analyzer.Analyzer', side_effect=AssertionError('unexpected model spend')):
            for _ in range(2):
                case.run_pipeline({'china_mil_online': adapter},
                                  sources=['sg_mindef_releases', 'china_mil_online'])
        results = case.results()
        self.assertEqual(results['sg_mindef_releases']['status'], 'skipped_disabled')
        self.assertEqual(results['sg_mindef_releases']['fetched'], 0)
        with sqlite3.connect(case.db_path) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM articles').fetchone()[0], 1)
            self.assertEqual(con.execute('SELECT url FROM articles').fetchone()[0], url)
