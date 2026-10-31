"""Real preserved metadata, guarded admission, retry and shared presentation."""
import copy
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import japan_mod_official_links as gate
from core.regional_official_link_release import RegionalLinkHold
from core.regional_official_link_render import read_live_links
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0014_ph_nsc_regional_official_links as previous
from migrations.versions import m0020_japan_mod_official_links as migration
from scripts.admit_japan_mod_official_links import run
from scripts.verify_japan_mod_official_links import verify

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/japan_mod_official_links.json").read_text())
EVIDENCE = {k: v for k, v in FIXTURE.items() if k not in ("rows", "actions", "source_db_git_blob")}


def policy():
    return gate.load_policy()


def database():
    con = sqlite3.connect(":memory:")
    con.execute(migration.DDL)
    con.execute("ALTER TABLE " + migration.TEMP + " RENAME TO " + base.TABLE)
    con.execute(base.INDEX_DDL)
    migration.up(con)
    con.commit()
    return con


class JapanModAdmission(unittest.TestCase):
    def test_rss_date_uses_tokyo_day_when_schedule_crosses_japanese_midnight(self):
        self.assertTrue(gate.verified_rss_day("2026-10-28", "2026-10-27T22:40:00+00:00"))
        self.assertFalse(gate.verified_rss_day("2026-10-29", "2026-10-27T22:40:00+00:00"))
        self.assertFalse(gate.verified_rss_day("2026-02-31", "2026-10-27T22:40:00+00:00"))
        self.assertFalse(gate.verified_rss_day("2026-10-27", "2026-10-27T22:40:00"))

    def setUp(self):
        self.con = database()
        self.rows = copy.deepcopy(FIXTURE["rows"])
        self.approved = policy()

    def tearDown(self):
        self.con.close()

    def admit(self, rows=None, evidence=None):
        with patch.object(gate, "load_policy", return_value=self.approved):
            return gate.admit(self.con, self.rows if rows is None else rows,
                              EVIDENCE if evidence is None else evidence)

    def stored(self):
        return self.con.execute("SELECT * FROM regional_official_source_links ORDER BY source_identity").fetchall()

    def test_missing_policy_fails_before_writes_or_source_reads(self):
        held = dict(gate.load_policy(), standing_metadata_publication_authorized=False)
        with patch.object(gate, "load_policy", return_value=held), \
                patch("scripts.admit_japan_mod_official_links.candidates") as source:
            with self.assertRaisesRegex(RegionalLinkHold, "authorization_missing"):
                run("unused", "a" * 40, "must-not-be-created.sqlite")
            source.assert_not_called()
        self.assertEqual(self.stored(), [])

    def test_standing_source_grant_does_not_enable_production_intake(self):
        self.assertTrue(gate.require_authorization()["standing_metadata_publication_authorized"])
        with patch.dict(os.environ, {"JAPAN_MOD_OFFICIAL_LINKS_ENABLED": ""}), \
                patch("scripts.admit_japan_mod_official_links.candidates") as source:
            with self.assertRaisesRegex(RegionalLinkHold, "activation_missing"):
                run("unused", FIXTURE["source_commit"], ROOT / "pla_watch.db")
            source.assert_not_called()

    def test_exact_metadata_only_rows_repeat_idempotently_across_commits(self):
        self.assertEqual(self.admit()["new_official_links"], 7)
        before = self.stored()
        self.assertEqual(self.admit()["unchanged_official_links"], 7)
        later = dict(EVIDENCE, source_commit="b" * 40)
        rows = [dict(r, source_git_commit=later["source_commit"]) for r in self.rows]
        self.assertEqual(self.admit(rows, later)["new_official_links"], 0)
        self.assertEqual(self.stored(), before)
        with patch.object(gate, "load_policy", return_value=self.approved):
            links = read_live_links(self.con, "japan")
        self.assertEqual(len(links), 7)
        self.assertTrue(all(r["date_kind"] == gate.DATE_TYPE for r in links))
        self.assertTrue(all(r["publisher_label"] == "Japan Ministry of Defense" for r in links))
        self.assertFalse(any("original" in k for r in self.rows for k in r))

    def test_invalid_duplicate_foreign_challenged_or_injected_fields_rejected(self):
        cases = []
        for changed in (
            {"canonical_official_url": "https://evil.example/2026/10/23a.pdf"},
            {"canonical_official_url": "https://www.mod.go.jp/j/press/news/2026/10/23b.html"},
            {"official_issuer": "jp_joint_staff"},
            {"publisher_posted_date": "2026-02-31"},
            {"title_original": "Synthetic forbidden test field"},
            {"source_family": "jp_mod_siteupdate_ja"},
        ):
            cases.append([dict(self.rows[0], **changed)] + self.rows[1:])
        cases.append(self.rows[:-1] + [self.rows[0]])
        for rows in cases:
            with self.subTest(rows=rows[0]["source_identity"]):
                with self.assertRaises((ValueError, KeyError)):
                    self.admit(rows)
                self.assertEqual(self.stored(), [])

    def test_released_metadata_cannot_change_and_batch_rolls_back(self):
        self.admit(self.rows[1:], dict(EVIDENCE, eligible_links=6))
        before = self.stored()
        changed = copy.deepcopy(self.rows)
        changed[-1]["publisher_posted_date"] = "2026-10-24"
        stable = {k:v for k,v in changed[-1].items() if k not in ("source_git_commit", "metadata_version_sha256")}
        changed[-1]["metadata_version_sha256"] = gate.digest(stable)
        with self.assertRaisesRegex(RegionalLinkHold, "previously_released"):
            self.admit(changed)
        self.assertEqual(self.stored(), before)

    def test_daily_rebase_preserves_japan_rows_over_unrelated_writer(self):
        from scripts.reconcile_db import merge_japan_official_links
        self.admit()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local.sqlite"
            target = sqlite3.connect(local)
            self.con.backup(target)
            target.close()
            self.con.execute("ATTACH ':memory:' AS bse")
            self.con.execute("ATTACH ? AS loc", (str(local),))
            self.con.execute("CREATE TABLE bse.regional_official_source_links AS SELECT * FROM main.regional_official_source_links WHERE 0")
            self.con.execute("DELETE FROM main.regional_official_source_links")
            self.con.row_factory = sqlite3.Row
            merge_japan_official_links(self.con)
            self.assertEqual(len(self.stored()), 7)
            before = [tuple(r) for r in self.stored()]
            merge_japan_official_links(self.con)
            self.assertEqual([tuple(r) for r in self.stored()], before)

    def test_missing_owner_decision_cannot_be_replaced_by_boolean(self):
        self.approved["owner_decision_reference"] = None
        with self.assertRaisesRegex(RegionalLinkHold, "authorization_missing"):
            self.admit()

    def test_readback_and_pages_require_exact_fields_and_bytes(self):
        self.admit()
        with tempfile.TemporaryDirectory() as tmp, patch.object(gate, "load_policy", return_value=self.approved):
            root = Path(tmp)
            db = root / "db.sqlite"
            dest = sqlite3.connect(db)
            self.con.backup(dest)
            dest.close()
            rows = read_live_links(self.con, "japan")
            html = '<section class="regional-official-live-links">'
            for r in rows:
                html += ('<li data-regional-official-source-id="{source_identity}"><h3>'
                    '<a href="{canonical_official_url}" rel="noopener noreferrer">{label}</a>'
                    '</h3><p>Publisher: {publisher_label} · {date_kind} '
                    '<time datetime="{publisher_posted_date}">{publisher_posted_date}</time>'
                    ' · Official-link metadata only</p></li>').format(**r)
            html += '</section>'
            page = root / "japan.html"
            page.write_text(html)
            self.assertEqual(verify(db, page)["admitted_links"], 7)
            with patch("scripts.verify_japan_mod_official_links.subprocess.check_output", return_value=b"different"):
                with self.assertRaisesRegex(RegionalLinkHold, "pages_bytes"):
                    verify(db, page, pages_repo=root)
            with patch("scripts.verify_japan_mod_official_links.urlopen") as request:
                response = request.return_value.__enter__.return_value
                response.status = 200
                response.read.return_value = b"stale public page"
                with self.assertRaisesRegex(RegionalLinkHold, "https_bytes_disagree"):
                    verify(db, page, live=True)
                response.read.return_value = html.encode()
                self.assertEqual(verify(db, page, live=True)["admitted_links"], 7)
            page.write_text(html.replace('Publisher:', 'Unexpected copied prose Publisher:', 1))
            with self.assertRaisesRegex(RegionalLinkHold, "unapproved_content"):
                verify(db, page)

    def test_migration_preserves_other_desk_rows_and_is_idempotent(self):
        # Use the actual tracked production index in a scratch database.
        from scripts.reconcile_db import read_only
        with read_only(str(ROOT / "pla_watch.db")) as source:
            scratch = sqlite3.connect(":memory:")
            source.backup(scratch)
        before = {name: scratch.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
                  for (name,) in scratch.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        migration.up(scratch)
        migration.up(scratch)
        for name, rows in before.items():
            self.assertEqual(scratch.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall(), rows, name)
        scratch.close()


class JapanDailyReadbackPropagation(unittest.TestCase):
    def test_real_workflow_accepts_later_propagation_but_rejects_persistent_mismatch(self):
        workflow = (ROOT / ".github/workflows/daily_update.yml").read_text()
        step = workflow.split("      - name: Reconcile Japan SQLite, HTML and Pages\n", 1)[1]
        step = step.split("\n      - name:", 1)[0]
        script = step.split("        run: |\n", 1)[1]
        # Execute the actual bounded workflow with deterministic read outcomes,
        # no network, production writes or wall-clock sleeps.
        stubs = '''
readback_tries=0
git() { :; }
sleep() { :; }
python() {
  if [[ "$*" == *"--live"* ]]; then
    readback_tries=$((readback_tries + 1))
    printf '%s' "$readback_tries" > "$READBACK_COUNT"
    [ "$readback_tries" -ge "$READBACK_SUCCESS_AFTER" ]
  fi
}
'''
        for success_after, exit_code, tries in ((4, 0, 4), (99, 1, 12)):
            with self.subTest(success_after=success_after), tempfile.TemporaryDirectory() as tmp:
                count = Path(tmp) / "readbacks"
                env = dict(os.environ, READBACK_COUNT=str(count),
                           READBACK_SUCCESS_AFTER=str(success_after))
                result = subprocess.run(["bash", "-c", stubs + script], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.assertEqual(int(count.read_text()), tries)


@unittest.skipUnless(os.environ.get("JAPAN_MOD_FROZEN_REPLAY") == "1",
                     "frozen Git source replay is enabled by the PR source-evidence gate")
class JapanFrozenSourceReplay(unittest.TestCase):
    def test_genuine_latest_scheduled_state_and_first_seen_runs(self):
        rows, evidence = gate.candidates(ROOT, FIXTURE["source_commit"], fetch_run=FIXTURE["actions"].get)
        self.assertEqual(rows, FIXTURE["rows"])
        self.assertEqual(evidence, EVIDENCE)

    def test_success_status_without_authentic_source_lineage_is_rejected(self):
        actions = copy.deepcopy(FIXTURE["actions"])
        actions["40433531306"]["event"] = "workflow_dispatch"
        with self.assertRaisesRegex(RegionalLinkHold, "not_authenticated"):
            gate.candidates(ROOT, FIXTURE["source_commit"], fetch_run=actions.get)


if __name__ == "__main__":
    unittest.main()
