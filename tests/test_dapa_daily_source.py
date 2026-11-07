"""DAPA in the shared daily lifecycle: synthetic offline contracts only.

No capture, HWPX or Korean source prose is used or committed. Bodies are
synthetic English placeholders; the model is a fake returning a fixed reading.
"""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.daily_sources import SOURCES, _dapa_approved_input, _dapa_known_hold, _dapa_output_check
from migrations.versions import m0021_dapa_daily_machine_parent as m21
from processing import daily_intake as d
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate

FAMILY = "kr_policy_dapa_releases"
IDENT = "korea-dapa-policy:100000001"
URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=100000001"
TITLE = "Synthetic DAPA fixture title"
FIRST = "Synthetic placeholder paragraph describing an acquisition meeting in general terms."
SECOND = "Synthetic placeholder paragraph describing a second, unrelated program review step."
BODY = FIRST + "\n\n" + SECOND


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def policy(enabled=True):
    p = d.load_policy()
    if enabled:
        p["sources"][FAMILY].update(private_model_processing=True, public_machine_explanation=True,
                                    unattended_release=True, owner_decision="synthetic test policy only")
    return p


def record(**extra):
    r = dict(source_family=FAMILY, source_identity=IDENT, metadata_version_sha256="a" * 64,
             content_sha256="c" * 64, capture_sha256="d" * 64, source_git_commit="e" * 40,
             source_run="42-1", title=TITLE, body=BODY, canonical_official_url=URL,
             publisher_posted_date="2026-10-28", official_issuer="kr_dapa",
             official_publisher=None, official_republisher="kr_policy_briefing",
             first_seen_run="42-1", dapa_status="CANDIDATE", dapa_reasons=[])
    r.update(extra)
    return r


def reading(**extra):
    one = "DAPA says it held a meeting on acquisition matters."
    two = "DAPA describes a separate review step for another program."
    r = dict(passed_relevance=True, requires_translation=False, summary_english=one + " " + two,
             facts=[dict(sentence=one, evidence=FIRST,
                         evidence_translation="Private synthetic rendering of the first passage."),
                    dict(sentence=two, evidence=SECOND,
                         evidence_translation="Private synthetic rendering of the second passage.")],
             categories=["modernization"], is_significant=False, significance_reasoning=None,
             model_id="synthetic-offline-rehearsal",
             prompt_version="kr-dapa-relevance-v1+kr-dapa-analysis-v1")
    r.update(extra)
    return r


def analyzer(reply=None):
    a = Mock()
    a.analyze_record.return_value = reading() if reply is None else reply
    a.usage.rows.return_value = []
    return a


def insert_parent(conn, scope="official_link_only", text_sha="c" * 64, page_sha="d" * 64):
    released = "2026-11-07T00:00:00Z" if scope == "official_link_only" else None
    conn.execute(
        "INSERT INTO korea_official_source_records (source_identity,canonical_official_url,"
        "publisher_posted_date,source_git_commit,source_db_sha256,candidate_version_sha256,"
        "original_title_sha256,original_text_sha256,publisher_html_sha256,original_hwpx_sha256,"
        "official_issuer,official_republisher,source_language,authority_tier,originality,"
        "public_scope,admitted_at_utc,released_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (IDENT, URL, "2026-10-28", "e" * 40, "f" * 64, "a" * 64, sha(TITLE), text_sha, page_sha,
         "9" * 64, "kr_dapa", "kr_policy_briefing", "ko", "B", "syndicated", scope, released, released))


class DapaAdapters(unittest.TestCase):
    def test_model_input_is_only_lead_and_body_in_order(self):
        private = {"_paragraphs": [
            dict(index=3, role="quotation", text="Q"), dict(index=2, role="body", text="B"),
            dict(index=0, role="lead", text="L"), dict(index=4, role="annotation", text="N")]}
        self.assertEqual(_dapa_approved_input(private, {}), "L\n\nB")
        self.assertEqual(_dapa_approved_input({}, {}), "")

    def test_known_hold_covers_refused_and_non_candidate_versions(self):
        self.assertTrue(_dapa_known_hold(record(source_identity="korea-dapa-policy:156787071")))
        for status in ("HOLD", "REFUSED"):
            self.assertTrue(_dapa_known_hold(record(dapa_status=status)))
        self.assertFalse(_dapa_known_hold(record()))
        output = {k: v for k, v in record().items() if k != "dapa_status"}
        self.assertFalse(_dapa_known_hold(output))

    def test_output_requires_dapa_attribution_and_no_flag(self):
        self.assertIsNone(_dapa_output_check({"model_flagged": False, "summary": "DAPA says x."}))
        self.assertEqual(_dapa_output_check({"model_flagged": True, "summary": "DAPA says x."}),
                         "daily_dapa_flag_or_attribution_held")
        self.assertEqual(_dapa_output_check({"model_flagged": False, "summary": "It says x."}),
                         "daily_dapa_flag_or_attribution_held")

    def test_links_bind_the_private_to_production_version_hash(self):
        """Synthetic pinned repo: the record version must equal the parent's
        candidate_version_sha256, or admission can never bind (found offline)."""
        import subprocess
        from core.daily_sources import _dapa_links
        from core.korea_dapa_private_to_production import version_hash
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "state").mkdir()
            with sqlite3.connect(str(repo / "state/shadow.db")) as conn:
                conn.execute("CREATE TABLE shadow_records (source_slug, source_identity, url,"
                             " published_date, first_seen_run, capture_sha256, content_sha256,"
                             " metadata_json)")
                conn.executemany("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?)", [
                    (FAMILY, IDENT, URL, "2026-10-28", "42-1", "d" * 64, "c" * 64,
                     '{"document_capture_sha256": "%s"}' % ("9" * 64)),
                    (FAMILY, IDENT[:-1] + "2", URL[:-1] + "2", "2026-10-28", "42-1",
                     "d" * 64, "c" * 64, "{}")])
            conn.close()
            git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run(git[:3] + ["init", "-q"], check=True)
            subprocess.run(git + ["add", "state/shadow.db"], check=True)
            subprocess.run(git + ["commit", "-qm", "synthetic"], check=True)
            head = subprocess.run(git[:3] + ["rev-parse", "HEAD"], check=True,
                                  capture_output=True, text=True).stdout.strip()
            pinned, missing = _dapa_links(repo, head, SOURCES[FAMILY])
        self.assertEqual(pinned["metadata_version_sha256"], version_hash({
            "source_identity": IDENT, "canonical_official_url": URL,
            "publisher_posted_date": "2026-10-28", "original_text_sha256": "c" * 64,
            "publisher_html_sha256": "d" * 64, "original_hwpx_sha256": "9" * 64}))
        self.assertEqual((pinned["dapa_status"], pinned["dapa_reasons"]),
                         ("HOLD", ["capture_missing_at_pin"]))
        self.assertNotIn("_paragraphs", pinned)
        self.assertEqual((missing["dapa_status"], missing["dapa_reasons"]),
                         ("HOLD", ["document_capture_missing"]))

    def test_family_is_not_desk_registered_until_activation(self):
        self.assertFalse(SOURCES[FAMILY].desk_registered)
        self.assertTrue(all(s.desk_registered for f, s in SOURCES.items() if f != FAMILY))


class DapaLifecycle(unittest.TestCase):
    def test_committed_policy_holds_before_any_analyzer(self):
        factory = Mock()
        state, _ = d.process([record()], {}, family=FAMILY, policy=policy(False),
                             analyzer_factory=factory)
        self.assertEqual(state[FAMILY + ":" + IDENT]["reason"], "model_rights_held")
        factory.assert_not_called()
        with self.assertRaises(d.IntakeHold):
            d.sign_outputs(state, family=FAMILY, policy=policy(False), key="k" * 40)

    def test_held_candidate_and_excluded_identity_never_reach_model(self):
        factory = Mock()
        held = record(dapa_status="HOLD", dapa_reasons=["joint_release_masthead"])
        state, _ = d.process([held], {}, family=FAMILY, policy=policy(), analyzer_factory=factory)
        self.assertEqual(state[FAMILY + ":" + IDENT]["reason"], "source_semantic_anomaly")
        factory.assert_not_called()

    def test_quality_holds_flags_and_missing_attribution(self):
        unattributed = "It held a meeting on acquisition matters."
        cases = (
            (reading(is_significant=True, significance_reasoning="x"), None),
            (reading(facts=[dict(reading()["facts"][0], sentence=unattributed), reading()["facts"][1]],
                     summary_english=unattributed + " " + reading()["facts"][1]["sentence"]),
             "daily_attribution_missing"),
        )
        for bad, code in cases:
            state, _ = d.process([record()], {}, family=FAMILY, policy=policy(),
                                 analyzer_factory=lambda bad=bad: analyzer(bad))
            entry = state[FAMILY + ":" + IDENT]
            self.assertNotEqual(entry["status"], "complete")
            if code:
                self.assertEqual(entry["quality_hold"], code)


class DapaAdmission(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "scratch.db"
        build_legacy_db(self.db)
        migrate(self.db)
        self.p = policy()
        state, _ = d.process([record()], {}, family=FAMILY, policy=self.p, analyzer_factory=analyzer)
        self.assertEqual(state[FAMILY + ":" + IDENT]["status"], "complete")
        self.key = "synthetic-dapa-key-" * 3
        self.envelope = d.sign_outputs(state, family=FAMILY, policy=self.p, key=self.key)
        for k in ("title", "body"):
            self.assertNotIn(k, self.envelope["packet"]["records"][0])

    def connect(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(conn.close)
        return conn

    def raw_insert(self, conn, family=FAMILY, identity=IDENT):
        row = dict(zip(d.PUBLIC_FIELDS, [family, identity] + ["a" * 64] * 3
                       + ["e" * 40, "1-1", "DAPA s.", "[]", 0, None, "m", "v", "q" * 64, "p" * 64]))
        cols = ["categories_json" if k == "categories" else k for k in row]
        conn.execute("INSERT INTO daily_machine_records (" + ",".join(cols) + ") VALUES ("
                     + ",".join("?" * len(cols)) + ")", list(row.values()))

    def test_m0021_is_applied_and_triggers_require_the_family_parent(self):
        conn = self.connect()
        self.assertTrue(m21.is_already_applied(conn))
        self.assertNotIn("FOREIGN KEY", conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='daily_machine_records'").fetchone()[0].upper())
        self.assertEqual(d.admit(conn, self.envelope, family=FAMILY, policy=self.p, key=self.key),
                         {"admitted": 0, "holds": ["daily_admitted_source_version_mismatch"]})
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.raw_insert(conn)
        insert_parent(conn, scope="held")
        self.assertEqual(d.admit(conn, self.envelope, family=FAMILY, policy=self.p, key=self.key),
                         {"admitted": 0, "holds": ["daily_admitted_source_version_mismatch"]})
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.raw_insert(conn)

    def test_admission_binds_link_only_parent_and_reader_rebinds_version(self):
        conn = self.connect()
        with conn:
            insert_parent(conn)
        self.assertEqual(d.admit(conn, self.envelope, family=FAMILY, policy=self.p,
                                 key=self.key)["admitted"], 1)
        conn.close()
        from core import daily_machine_records as reader
        with patch.object(reader, "load_policy", return_value=self.p):
            rows = reader.load(self.db)
            self.assertEqual([(r["url"], r["source_label"], r["machine_only"]) for r in rows],
                             [(URL, "DAPA", True)])
            with sqlite3.connect(str(self.db)) as c:
                c.execute("UPDATE korea_official_source_records SET original_text_sha256=?", ("0" * 64,))
            self.assertEqual(reader.load(self.db), [])
        with patch.object(reader, "load_policy", return_value=policy(False)):
            self.assertEqual(reader.load(self.db), [])

    def test_admission_refuses_unmigrated_schema(self):
        conn = self.connect()
        with conn:
            insert_parent(conn)
        with patch.object(m21, "is_already_applied", return_value=False):
            with self.assertRaisesRegex(d.IntakeHold, "daily_migration_required"):
                d.admit(conn, self.envelope, family=FAMILY, policy=self.p, key=self.key)

    def test_other_families_still_need_their_regional_link(self):
        conn = self.connect()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.raw_insert(conn, family="ph_afp_articles", identity="afp:1")


if __name__ == "__main__":
    unittest.main()
