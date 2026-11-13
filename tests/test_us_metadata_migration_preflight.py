"""USCC/Treasury production writer must repair pending schema before admission.

Since runtime migration 4 (docs/desks/MIGRATION.md) that writer is the
scheduled Daily workflow: its one migration step runs before the pipeline step
whose governed admissions import the preserved listing metadata. The two
family workflows keep only their pull-request rehearsal.

Real tracked SQLite bytes are copied into a disposable temp; never modify main.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.verify_db_current import classify

ROOT = Path(__file__).resolve().parents[1]
TRACKED = ROOT / "pla_watch.db"
DAILY = ROOT / ".github/workflows/daily_update.yml"
RETIRED_WRITERS = [
    ROOT / ".github/workflows/uscc_verified_official_links_release.yml",
    ROOT / ".github/workflows/treasury_verified_official_links_release.yml",
]


class USMetadataMigrationPreflight(unittest.TestCase):
    def test_daily_migrates_and_verifies_before_the_governed_us_admissions(self):
        yaml = DAILY.read_text(encoding="utf-8")
        migrate = yaml.index("run: python -m migrations.cli --apply")
        verify = yaml.index("run: python scripts/verify_db_current.py")
        clone_uscc = yaml.index("--branch shadow/uscc-press")
        clone_treasury = yaml.index("--branch shadow/us-treasury-press")
        pipeline_step = yaml.index("python pipeline.py")
        self.assertLess(migrate, verify)
        self.assertLess(verify, clone_uscc)
        self.assertLess(clone_uscc, clone_treasury)
        self.assertLess(clone_treasury, pipeline_step)
        # The pipeline step is handed both clones; the admissions run there.
        self.assertIn("IPR_USCC_SOURCE_CHECKOUT: ${{ runner.temp }}/uscc-preserved-metadata", yaml)
        self.assertIn("IPR_US_TREASURY_SOURCE_CHECKOUT: ${{ runner.temp }}/treasury-preserved-metadata", yaml)
        # Daily's existing commit step carries the database and the rendered site.
        self.assertLess(pipeline_step, yaml.index("git add pla_watch.db output/"))

    def test_the_separate_release_writers_keep_only_their_pr_rehearsal(self):
        for p in RETIRED_WRITERS:
            with self.subTest(workflow=p.name):
                yaml = p.read_text(encoding="utf-8")
                self.assertIn("isolated-render-contract", yaml)
                self.assertIn("if: github.event_name == 'pull_request'", yaml)
                self.assertIn("persist-credentials: false", yaml)
                for retired in ("production-metadata-page-only", "git push",
                                "contents: write", "git add -- pla_watch.db",
                                "\nschedule:", "  schedule:", "  workflow_run:",
                                "  workflow_dispatch:", "  push:",
                                "concurrency:"):
                    self.assertNotIn(retired, yaml)

    def test_disposable_preflight_repairs_partial_migration_without_data_loss(self):
        # Reproduce the exact observed production failure mode: one migration
        # was merged on main, and the stored schema ledger was missing a row.
        self.assertTrue(TRACKED.is_file())
        before_hash = hashlib.sha256(TRACKED.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix="ipr-us-schema-preflight-") as directory:
            db = Path(directory) / "archive-copy.sqlite"
            shutil.copyfile(TRACKED, db)
            with sqlite3.connect(str(db)) as con:
                counts_before = {
                    tbl: con.execute("SELECT COUNT(*) FROM " + tbl).fetchone()[0]
                    for tbl in ("articles", "sources", "scrape_runs")
                }
                con.execute("DELETE FROM schema_migrations WHERE version='0008'")
                con.commit()
                self.assertEqual(classify(con), "partially_applied")
            # Run precisely the repair command both U.S. workflows invoke,
            # against ONLY this temporary copy. The real DB is untouched.
            repaired = subprocess.run(
                [sys.executable, "-m", "migrations.cli",
                 "--apply", "--db", str(db)],
                cwd=ROOT, text=True, capture_output=True,
            )
            self.assertEqual(repaired.returncode, 0,
                "disposable SQLite repair failure: " +
                (repaired.stdout + repaired.stderr)[-2500:])
            with sqlite3.connect(str(db)) as con:
                self.assertEqual(classify(con), "fully_current")
                after = {tbl: con.execute("SELECT COUNT(*) FROM " + tbl).fetchone()[0]
                         for tbl in counts_before}
                # The repair also syncs desk configuration, which may add a
                # newly configured source row; no existing row is lost.
                self.assertEqual(after["articles"], counts_before["articles"])
                self.assertEqual(after["scrape_runs"], counts_before["scrape_runs"])
                self.assertGreaterEqual(after["sources"], counts_before["sources"])
                self.assertEqual(con.execute("PRAGMA quick_check").fetchone()[0],
                                 "ok")
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM schema_migrations WHERE version='0008'"
                ).fetchone()[0], 1)
        self.assertEqual(hashlib.sha256(TRACKED.read_bytes()).hexdigest(),
                         before_hash)
        self.assertFalse((ROOT / "pla_watch.db-wal").exists())
        self.assertFalse((ROOT / "pla_watch.db-shm").exists())


if __name__ == "__main__":
    unittest.main()
