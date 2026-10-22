"""Governed Korean MND corpus bridge: admission, replay, exclusions, drift.

Fixtures are the four already-public released KOGL texts and a migrated
scratch database. No Korean text is invented and nothing touches pla_watch.db.
"""
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core import korea_corpus_bridge as bridge
from core.korea_published_originals import (
    INDEX, ORIGINAL_DIR, PublishedKoreaHold,
)
from migrations.runner import apply_all, connect
from tests.test_migrations import build_legacy_db

ROOT = Path(__file__).resolve().parent.parent
LIVE = {"korea": SimpleNamespace(status="live",
                                 manifest_path="desks/korea/manifest.json")}
SHADOW = {"korea": SimpleNamespace(status="shadow", manifest_path=None)}
EXPECTED_HEADING_LINE = {"156784297": 6, "156785286": 5,
                         "156785444": 5, "156785691": 5}


# Fixed four-release scenario fixture. The production release index grows daily;
# new official releases must not silently change the cases under test.
FIXTURE_IDENTITIES = frozenset({
    "korea-policy:156784297", "korea-policy:156785286",
    "korea-policy:156785444", "korea-policy:156785691",
})


def released():
    records = json.loads(INDEX.read_text(encoding="utf-8"))["records"]
    selected = [r for r in records if r["source_identity"] in FIXTURE_IDENTITIES]
    if {r["source_identity"] for r in selected} != FIXTURE_IDENTITIES:
        raise AssertionError("Korea four-release test fixture incomplete")
    return selected


def activate(conn, enabled=1, desk="korea", access="manual"):
    conn.execute(
        "INSERT INTO sources (slug, display_name, base_url, language, desk_id, "
        "enabled, access_method, language_tag) VALUES (?, ?, ?, 'ko', ?, ?, ?, 'ko') "
        # Upsert: once the desk is activated, sync_desk_config has already
        # inserted the manifest's row and the fixture only sets its state.
        "ON CONFLICT(slug) DO UPDATE SET desk_id=excluded.desk_id, "
        "enabled=excluded.enabled, access_method=excluded.access_method",
        (bridge.SOURCE_SLUG, "ROK MND via Policy Briefing",
         "https://www.korea.kr/", desk, enabled, access))
    conn.commit()


def admit_metadata(conn, rec, **overrides):
    row = {
        "source_identity": rec["source_identity"],
        "canonical_official_url": rec["official_url"],
        "publisher_posted_date": rec["publisher_posted_date"],
        "source_git_commit": rec["source_git_commit"],
        "source_db_sha256": "1" * 64, "candidate_version_sha256": "2" * 64,
        "original_title_sha256": "3" * 64,
        "original_text_sha256": rec["original_text_sha256"],
        "publisher_html_sha256": rec["source_html_sha256"],
        "original_hwpx_sha256": "4" * 64, "official_issuer": "kr_mnd",
        "official_republisher": "kr_policy_briefing", "source_language": "ko",
        "authority_tier": "B", "originality": "syndicated",
        "public_scope": "official_link_only",
        "admitted_at_utc": "2026-10-19T00:00:00Z",
        "released_at_utc": "2026-10-19T00:00:00Z",
    }
    row.update(overrides)
    cols = ", ".join(row)
    conn.execute("INSERT INTO korea_official_source_records (%s) VALUES (%s)"
                 % (cols, ", ".join("?" * len(row))), list(row.values()))
    conn.commit()


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db_path = root / "scratch.db"
        build_legacy_db(self.db_path)
        self.conn = connect(self.db_path)
        apply_all(self.conn)
        self.conn.isolation_level = None
        self.dir = root / "originals"
        self.dir.mkdir()
        self.records = released()
        for rec in self.records:
            nid = rec["source_identity"].split(":")[1]
            shutil.copyfile(ORIGINAL_DIR / (nid + ".txt"), self.dir / (nid + ".txt"))
        self.index = root / "index.json"
        self.write_index(self.records)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def write_index(self, records):
        self.index.write_text(json.dumps(
            {"schema": "ipr-korea-public-original-text-index/1",
             "records": records}), encoding="utf-8")

    def run_bridge(self, excluded=None, **kw):
        return bridge.apply(self.conn, index=self.index, original_dir=self.dir,
                            excluded={} if excluded is None else excluded,
                            registry=kw.pop("registry", LIVE), **kw)

    def snapshot(self):
        return (
            [tuple(r) for r in self.conn.execute(
                "SELECT id, url, content_hash, title_original, text_original, "
                "published_date FROM articles ORDER BY id")],
            [tuple(r) for r in self.conn.execute(
                "SELECT * FROM korea_corpus_admissions ORDER BY source_identity")],
        )

    def korea_rows(self):
        return self.conn.execute(
            "SELECT a.id, a.url, a.title_original, a.text_original, "
            "a.published_date, a.passed_relevance, s.desk_id FROM articles a "
            "JOIN sources s ON s.id=a.source_id WHERE s.slug=?",
            (bridge.SOURCE_SLUG,)).fetchall()


class TestDocumentHeading(unittest.TestCase):
    def test_heading_is_line_after_distribution_timestamp(self):
        for nid, line in EXPECTED_HEADING_LINE.items():
            text = (ORIGINAL_DIR / (nid + ".txt")).read_text(encoding="utf-8")
            found = bridge.document_heading(text)
            self.assertIsNotNone(found, nid)
            self.assertEqual(found[0], line, nid)
            self.assertEqual(found[1], text.splitlines()[line].strip())

    def test_missing_distribution_label_is_unidentifiable(self):
        text = (ORIGINAL_DIR / "156785444.txt").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertIsNone(bridge.document_heading(
            "\n".join(l for l in lines if l.strip() != "배포")))
        # A subtitle bullet directly after the timestamp is never promoted.
        del lines[5]
        self.assertIsNone(bridge.document_heading("\n".join(lines)))


class TestAdmission(BridgeCase):
    def test_new_admission_is_source_pinned(self):            # scenario 1, 16
        activate(self.conn)
        rec = next(r for r in self.records
                   if r["source_identity"] == "korea-policy:156785444")
        admit_metadata(self.conn, rec)
        receipt = self.run_bridge()
        self.assertEqual([a["source_identity"] for a in receipt["admitted"]],
                         ["korea-policy:156785444"])
        (aid, url, title, text, date, passed, desk), = self.korea_rows()
        raw = (ORIGINAL_DIR / "156785444.txt").read_bytes()
        self.assertEqual(url, rec["official_url"])
        self.assertEqual(text, raw.decode("utf-8"))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), rec["original_text_sha256"])
        self.assertEqual(title, raw.decode("utf-8").splitlines()[5].strip())
        self.assertEqual(date, rec["publisher_posted_date"])
        self.assertIsNone(passed)
        self.assertEqual(desk, "korea")
        led = self.conn.execute(
            "SELECT article_id, state, original_text_sha256, policy_sha256, "
            "release_decision_sha256, document_heading_sha256 "
            "FROM korea_corpus_admissions WHERE source_identity=?",
            (rec["source_identity"],)).fetchone()
        self.assertEqual(led[:5], (aid, "admitted", rec["original_text_sha256"],
                                   rec["policy_sha256"],
                                   rec["release_decision_sha256"]))
        self.assertEqual(led[5], hashlib.sha256(title.encode()).hexdigest())
        self.assertEqual(bridge.renderable_article_ids(self.conn), {aid})
        self.assertNotIn("text_original", json.dumps(receipt))
        self.assertNotIn(title, json.dumps(receipt, ensure_ascii=False))

    def test_replay_writes_nothing(self):                     # scenario 2, 15
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        first = self.run_bridge()
        self.assertEqual(len(first["admitted"]), 4)
        before = self.snapshot()
        for _ in range(3):
            again = self.run_bridge()
            self.assertEqual(again["admitted"], [])
            self.assertEqual(len(again["unchanged"]), 4)
        self.assertEqual(self.snapshot(), before)
        ids = [r[0] for r in self.korea_rows()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_admission_is_bounded_and_resumes(self):           # scenario 10
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        first = self.run_bridge(max_admissions=1)
        self.assertEqual((len(first["admitted"]), len(first["deferred"])), (1, 3))
        second = self.run_bridge(max_admissions=10)
        self.assertEqual(len(second["admitted"]), 3)
        self.assertEqual(len(self.korea_rows()), 4)

    def test_late_metadata_imports_on_next_run(self):          # scenario 10
        activate(self.conn)
        rec = self.records[0]
        first = self.run_bridge()
        self.assertIn({"source_identity": rec["source_identity"],
                       "reason": "korea_metadata_admission_missing"}, first["held"])
        self.assertEqual(self.korea_rows(), [])
        admit_metadata(self.conn, rec)
        second = self.run_bridge()
        self.assertIn(rec["source_identity"],
                      [a["source_identity"] for a in second["admitted"]])


class TestFailClosed(BridgeCase):
    def test_altered_text_refuses_whole_run(self):            # scenario 5
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        path = self.dir / "156785444.txt"
        path.write_bytes(path.read_bytes() + b"\n")
        before = self.snapshot()
        with self.assertRaises(PublishedKoreaHold):
            self.run_bridge()
        self.assertEqual(self.snapshot(), before)

    def test_metadata_digest_disagreement_is_held(self):       # scenario 5
        activate(self.conn)
        rec = self.records[0]
        admit_metadata(self.conn, rec, original_text_sha256="5" * 64)
        receipt = self.run_bridge()
        self.assertIn({"source_identity": rec["source_identity"],
                       "reason": "korea_original_text_digest_mismatch"},
                      receipt["held"])
        self.assertEqual(self.korea_rows(), [])

    def test_unreleased_metadata_is_held(self):
        activate(self.conn)
        rec = self.records[0]
        admit_metadata(self.conn, rec, public_scope="held",
                       admitted_at_utc=None, released_at_utc=None)
        receipt = self.run_bridge()
        self.assertIn({"source_identity": rec["source_identity"],
                       "reason": "korea_metadata_scope_mismatch"}, receipt["held"])
        self.assertEqual(self.korea_rows(), [])

    def test_unidentifiable_heading_is_held_not_guessed(self):
        activate(self.conn)
        rec = dict(self.records[0])
        nid = rec["source_identity"].split(":")[1]
        path = self.dir / (nid + ".txt")
        text = path.read_text(encoding="utf-8")
        changed = "\n".join(l for l in text.splitlines() if l.strip() != "배포")
        path.write_text(changed, encoding="utf-8")
        rec["original_text_sha256"] = hashlib.sha256(
            changed.encode("utf-8")).hexdigest()
        self.write_index([rec])
        admit_metadata(self.conn, rec)
        receipt = self.run_bridge()
        self.assertEqual(receipt["held"], [{"source_identity": rec["source_identity"],
                                            "reason": "korea_heading_unidentifiable"}])
        self.assertEqual(self.korea_rows(), [])

    def test_gates_refuse_without_activation(self):           # scenario 13
        # Once the desk is activated apply_all syncs the manifest's source
        # row; remove it to model a database that never received it.
        self.conn.execute("DELETE FROM sources WHERE slug=?", (bridge.SOURCE_SLUG,))
        before = self.snapshot()
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_source_not_registered"):
            self.run_bridge()
        activate(self.conn, enabled=0)
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_source_not_activated"):
            self.run_bridge()
        self.conn.execute("UPDATE sources SET enabled=1, access_method='html' "
                          "WHERE slug=?", (bridge.SOURCE_SLUG,))
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_source_not_activated"):
            self.run_bridge()
        self.conn.execute("UPDATE sources SET access_method='manual' WHERE slug=?",
                          (bridge.SOURCE_SLUG,))
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_desk_not_live"):
            self.run_bridge(registry=SHADOW)
        self.assertEqual(self.snapshot(), before)

    def test_repository_registry_gate_matches_activation_state(self):
        """Until the owner activation change the real registry refuses; after
        it, the registry gate passes and only the database gates remain."""
        activate(self.conn)
        if (ROOT / "desks/korea/manifest.json").is_file():
            self.assertIsInstance(bridge.check_gates(self.conn), int)
            return
        with self.assertRaisesRegex(bridge.BridgeHold, "korea_desk_not_live"):
            bridge.apply(self.conn, index=self.index, original_dir=self.dir,
                         excluded={})


class TestExclusions(BridgeCase):
    def test_repository_exclusions_admit_only_the_unreviewed_release(self):  # scenario 6, 8
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        receipt = self.run_bridge(excluded=bridge.excluded_identities())
        reasons = {e["source_identity"]: e["reason"] for e in receipt["excluded"]}
        self.assertEqual(reasons["korea-policy:156784297"], "excluded_frozen_baseline")
        for nid in ("156785286", "156785444"):
            self.assertEqual(reasons["korea-policy:" + nid],
                             "excluded_reviewed_english")
        # An unreviewed English draft handoff alone does not strand a release.
        self.assertNotIn("korea-policy:156785691", reasons)
        self.assertEqual([a["source_identity"] for a in receipt["admitted"]],
                         ["korea-policy:156785691"])

    def test_research_hold_and_reviewed_releases_always_excluded(self):
        excluded = bridge.excluded_identities(frozen=set())
        self.assertEqual(excluded["korea-policy:156785161"], "excluded_research_hold")
        from core.korea_english_publication import public_registry
        for row, _, _ in public_registry():
            self.assertIn(row["source_identity"], excluded)

    def test_dapa_never_enters_corpus(self):                   # scenario 7
        activate(self.conn)
        self.conn.execute(
            "INSERT INTO korea_official_source_records (source_identity, "
            "canonical_official_url, publisher_posted_date, source_git_commit, "
            "source_db_sha256, candidate_version_sha256, original_title_sha256, "
            "original_text_sha256, publisher_html_sha256, original_hwpx_sha256, "
            "official_issuer, official_republisher, source_language, "
            "authority_tier, originality) VALUES ('korea-dapa-policy:156785254', "
            "'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785254', "
            "'2026-10-15', ?, ?, ?, ?, ?, ?, ?, 'kr_dapa', 'kr_policy_briefing', "
            "'ko', 'B', 'syndicated')",
            ("a" * 40,) + tuple(c * 64 for c in "bcdefg"))
        self.run_bridge()
        self.assertEqual(self.korea_rows(), [])
        self.assertIsNone(self.conn.execute(
            "SELECT 1 FROM korea_corpus_admissions WHERE source_identity "
            "LIKE 'korea-dapa%'").fetchone())


class TestWithdrawal(BridgeCase):
    def setUp(self):
        super().setUp()
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        self.run_bridge()
        self.ids = bridge.renderable_article_ids(self.conn)

    def test_removed_from_release_index_is_withdrawn(self):
        self.write_index(self.records[1:])
        gone = self.records[0]["source_identity"]
        receipt = self.run_bridge()
        self.assertEqual([w["source_identity"] for w in receipt["withdrawn"]], [gone])
        aid = receipt["withdrawn"][0]["article_id"]
        self.assertNotIn(aid, bridge.renderable_article_ids(self.conn))
        self.assertIn(aid, bridge.withdrawn_article_ids(self.conn))
        # Restoring the index never silently republishes a withdrawn record.
        self.write_index(self.records)
        self.run_bridge()
        self.assertNotIn(aid, bridge.renderable_article_ids(self.conn))

    def test_revoked_release_and_changed_version_are_withdrawn(self):
        a, b = self.records[0], self.records[1]
        self.conn.execute(
            "UPDATE korea_official_source_records SET public_scope='held' "
            "WHERE source_identity=?", (a["source_identity"],))
        self.conn.execute(
            "UPDATE korea_official_source_records SET original_text_sha256=? "
            "WHERE source_identity=?", ("6" * 64, b["source_identity"]))
        receipt = self.run_bridge()
        reasons = {w["source_identity"]: w["reason"] for w in receipt["withdrawn"]}
        self.assertEqual(reasons, {a["source_identity"]: "source_release_revoked",
                                   b["source_identity"]: "source_version_changed"})
        self.assertEqual(len(bridge.renderable_article_ids(self.conn)), 2)

    def test_later_reviewed_english_supersedes_the_machine_record(self):
        ident = self.records[0]["source_identity"]
        receipt = self.run_bridge(excluded={ident: "excluded_reviewed_english"})
        self.assertEqual([(w["source_identity"], w["reason"]) for w in receipt["withdrawn"]],
                         [(ident, "superseded_by_reviewed_english")])
        self.assertIn(receipt["withdrawn"][0]["article_id"],
                      bridge.withdrawn_article_ids(self.conn))


if __name__ == "__main__":
    unittest.main()
