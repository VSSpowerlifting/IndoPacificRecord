"""Fictional review seals on disposable databases; no real source approval."""
import gc
import shutil
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from scripts import admit_vietnam_official_links as publisher
from scripts.verify_regional_source_index_readback import verify_vietnam_https, ReadbackHold
from core.regional_official_link_render import read_live_links
from tests import test_vietnam_official_link_admission as fixtures


class AtomicAdmission(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.VietnamAdmission()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.db = self.f.fixture.root / 'production-copy.db'
        shutil.copyfile(publisher.ROOT / 'pla_watch.db', self.db)
        # Other public schema capabilities must already exist before this
        # family-specific publisher, which correctly refuses unrelated upgrades.
        from migrations.runner import connect, apply_all
        with closing(connect(self.db)) as conn:
            apply_all(conn)
            # The live corpus now has three real MPS links. This fictional
            # review must start without those identities on its scratch copy.
            conn.execute("DELETE FROM regional_official_source_links "
                         "WHERE desk='vietnam' AND source_family=?", (fixtures.MPS,))
            conn.commit()
            self.unrelated = conn.execute("SELECT * FROM regional_official_source_links "
                                          "WHERE desk!='vietnam' ORDER BY source_family, source_identity").fetchall()
        self.before = self.db.read_bytes()
        self.sealed = fixtures.sealed(self.f.packet)

    def run_admit(self, sealed=None):
        return publisher.admit_atomic(self.db, self.f.repo, self.f.shas[fixtures.MPS],
            self.sealed if sealed is None else sealed, api=object(), secret=fixtures.KEY,
            as_of_utc=fixtures.NOW, expected_db_sha256=publisher.sha(self.db))

    def test_atomic_replay_preserves_unrelated_rows_and_idempotence(self):
        self.run_admit()
        with closing(sqlite3.connect(str(self.db))) as conn:
            self.assertEqual(conn.execute("select count(*) from regional_official_source_links where desk='vietnam'").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT * FROM regional_official_source_links "
                                          "WHERE desk!='vietnam' ORDER BY source_family, source_identity").fetchall(),
                             self.unrelated)
        after = self.db.read_bytes()
        self.run_admit()
        self.assertEqual(self.db.read_bytes(), after)

    def test_wal_failure_cleanup_and_replay_do_not_depend_on_garbage_collection(self):
        with closing(sqlite3.connect(str(self.db))) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
        before = self.db.read_bytes()
        enabled = gc.isenabled()
        gc.disable()
        try:
            with self.assertRaises(ValueError):
                self.run_admit({})
            self.assertEqual(self.db.read_bytes(), before)
            self.assertEqual(list(self.db.parent.glob('.vietnam-admission-*')), [])
            self.run_admit()
            after = self.db.read_bytes()
            self.run_admit()
            self.assertEqual(self.db.read_bytes(), after)
            self.assertEqual(list(self.db.parent.glob('.vietnam-admission-*')), [])
        finally:
            if enabled:
                gc.enable()

    def test_failed_review_or_independent_readback_never_replaces_database(self):
        with self.assertRaises(ValueError): self.run_admit({})
        self.assertEqual(self.db.read_bytes(), self.before)
        with patch.object(publisher, 'read_live_links', side_effect=ValueError('readback failed')):
            with self.assertRaises(ValueError): self.run_admit()
        self.assertEqual(self.db.read_bytes(), self.before)
        self.assertEqual(list(self.db.parent.glob('.vietnam-admission-*')), [])

    def test_concurrent_database_change_and_active_sidecars_hold(self):
        with self.assertRaisesRegex(ValueError, 'preimage'):
            publisher.admit_atomic(self.db, self.f.repo, self.f.shas[fixtures.MPS], self.sealed,
                api=object(), secret=fixtures.KEY, as_of_utc=fixtures.NOW, expected_db_sha256='0'*64)
        Path(str(self.db)+'-wal').write_bytes(b'active')
        with self.assertRaisesRegex(ValueError, 'sidecars'): self.run_admit()
        self.assertEqual(self.db.read_bytes(), self.before)

    def test_https_mismatch_and_empty_admission_cannot_prove_publication(self):
        site = self.f.fixture.root / 'site'; site.mkdir()
        (site/'vietnam.html').write_bytes(b'committed')
        with self.assertRaisesRegex(ReadbackHold, 'bytes_differ'):
            verify_vietnam_https(self.db, site, fetch=lambda url: b'old deployment')
        with self.assertRaisesRegex(ReadbackHold, 'no_admitted'):
            verify_vietnam_https(self.db, site, fetch=lambda url: b'committed')

    def test_sqlite_generated_html_and_independent_https_bytes_agree(self):
        self.run_admit()
        site = self.f.fixture.root / 'rendered'; site.mkdir()
        from jinja2 import Environment, select_autoescape
        from types import SimpleNamespace
        source = (publisher.ROOT/'site/preview/templates/desk.html').read_text()
        start = source.index("{% if desk.slug in ('philippines', 'indonesia', 'vietnam')",
                             source.index('{# Regional official-link index:'))
        end = source.index('{# US: first-party publisher URLs', start)
        with closing(sqlite3.connect(str(self.db))) as conn:
            data = Environment(autoescape=select_autoescape(default_for_string=True)).from_string(
                source[start:end]).render(desk=SimpleNamespace(slug='vietnam'),
                                         regional_official_links=read_live_links(conn,'vietnam')).encode()
        (site/'vietnam.html').write_bytes(data)
        receipt = verify_vietnam_https(self.db, site, fetch=lambda url: data)
        self.assertEqual(receipt['admitted_official_link_count'], 2)

    def test_cli_cannot_write_production_without_explicit_release(self):
        before = publisher.sha(publisher.ROOT/'pla_watch.db')
        with patch('builtins.print'):
            rc = publisher.main(['--database',str(publisher.ROOT/'pla_watch.db'),
                '--state-repo',str(self.f.repo),'--state-commit',self.f.shas[fixtures.MPS],
                '--signed-decision','missing.json','--expected-db-sha256',before])
        self.assertEqual(rc, 2)
        self.assertEqual(publisher.sha(publisher.ROOT/'pla_watch.db'),before)
