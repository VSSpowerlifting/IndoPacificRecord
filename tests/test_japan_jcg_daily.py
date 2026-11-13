"""Japan Coast Guard English releases in the shared Daily lane: synthetic offline contracts.

No JCG text, media or capture is used or committed. Bodies are synthetic
English placeholders, custody is a throw-away git repository, and the model is
a fake returning a fixed reading. Nothing here spends money, contacts the
publisher or touches a production database.
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import japan_jcg_links as links
from core.daily_sources import SOURCES, _jcg_known_hold, _jcg_output_check
from core.standing_source_rights import POLICIES
from migrations.versions import m0022_singapore_mindef_source_records as m22
from migrations.versions import m0023_japan_jcg_source_records as m23
from processing import daily_intake as d
from processing.screening import JAPAN_JCG_DAILY_PROFILE, profile_for_source
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "jp_jcg_press_en"
IDENT = "jcg-en:90001"
URL = "https://www.kaiho.mlit.go.jp/e/topics_archive/article90001.html"
TITLE = "Synthetic coast guard fixture title"
FIRST = "The JCG announced a routine joint exercise between two coast guard agencies."
SECOND = "The release describes the schedule for a planned search and rescue drill."
BODY = FIRST + "\n\n" + SECOND
DAY = "2026-10-28"
RUN = "88-1"
REMOTE = "https://github.com/" + d.PRIVATE_REPO
META = {"source_identity": IDENT, "publication_kind": "english_official_press_release",
        "body_scope": "published_html_text_only", "attachments_collected": False,
        "attachment_urls": [], "extraction_profile": links.EXTRACTION_PROFILE}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def policy(enabled=True):
    p = d.load_policy()
    flag = bool(enabled)
    p["sources"][FAMILY].update(private_model_processing=flag, public_machine_explanation=flag,
                                unattended_release=flag)
    if enabled:
        p["sources"][FAMILY]["owner_decision"] = "synthetic test policy only"
    return p


def reading(**extra):
    one = "The JCG says it held a routine joint exercise between two coast guard agencies."
    two = "The JCG describes the schedule for a planned search and rescue drill."
    r = dict(passed_relevance=True, requires_translation=False, summary_english=one + " " + two,
             facts=[dict(sentence=one, evidence=FIRST), dict(sentence=two, evidence=SECOND)],
             categories=["military_diplomacy"], is_significant=False, significance_reasoning=None,
             model_id="synthetic-offline-rehearsal",
             prompt_version="jp-jcg-relevance-v1+jp-jcg-analysis-v1")
    r.update(extra)
    return r


def analyzer(reply=None):
    a = Mock()
    a.analyze_record.return_value = reading() if reply is None else reply
    a.usage.rows.return_value = []
    return a


def build_custody(root, rows=None, *, remote=REMOTE, branch="archive/japan-jcg"):
    """A synthetic private custody checkout; returns (repo path, pinned commit).

    ``rows`` are (identity, title, body, day, metadata) tuples; the URL is the
    family's canonical article URL unless metadata carries ``_url``.
    """
    rows = rows if rows is not None else [(IDENT, TITLE, BODY, DAY, META)]
    repo = Path(root) / "custody"
    (repo / "state").mkdir(parents=True)
    with sqlite3.connect(str(repo / "state/shadow.db")) as conn:
        conn.execute("CREATE TABLE shadow_records (url TEXT PRIMARY KEY, source_slug TEXT,"
                     " title_original TEXT, text_original TEXT, published_date TEXT,"
                     " language_tag TEXT, publication_kind TEXT, content_sha256 TEXT,"
                     " capture_sha256 TEXT, retrieved_at TEXT, first_seen_run TEXT,"
                     " source_identity TEXT, metadata_json TEXT)")
        for ident, title, body, day, meta in rows:
            meta = dict(meta)
            url = meta.pop("_url", links.canonical_url(ident))
            conn.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (url, FAMILY, title, body, day, "en", "english_official_press_release",
                          sha(body), sha("capture:" + ident), "2026-11-01T00:00:00Z", RUN,
                          ident, json.dumps(meta)))
    conn.close()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["checkout", "-q", "-b", branch], check=True)
    subprocess.run(git + ["add", "state/shadow.db"], check=True)
    subprocess.run(git + ["commit", "-qm", "synthetic"], check=True)
    subprocess.run(git + ["remote", "add", "origin", remote], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    return repo, head


class JcgDefinition(unittest.TestCase):
    def test_family_is_registered_and_activated_within_its_budget(self):
        s = SOURCES[FAMILY]
        self.assertEqual((s.desk_id, s.label, s.publisher, s.custody_ref, s.language),
                         ("japan", "JCG", "Japan Coast Guard", "archive/japan-jcg", "en"))
        self.assertTrue(s.desk_registered)
        committed = d.load_policy()["sources"][FAMILY]
        for switch in ("private_model_processing", "public_machine_explanation",
                       "unattended_release"):
            self.assertIs(committed[switch], True)
        self.assertEqual(committed["excluded_source_identities"], [])
        self.assertEqual((committed["max_records_per_run"],
                          committed["max_estimated_cost_usd_per_run"]), (1, 0.35))
        import pipeline
        self.assertIn(FAMILY, pipeline._governed_admissions())
        self.assertEqual(s.key_env, links.KEY_ENV)

    def test_family_boundary_is_exactly_the_standing_text_policy(self):
        """The link module admits nothing the PR #1015 rights policy excludes."""
        rights = POLICIES[FAMILY]
        self.assertEqual(rights["permitted_scopes"], frozenset(("original_text",)))
        for excluded in ("original_pdf", "original_media", "embedded_assets"):
            self.assertIn(excluded, rights["excluded_scopes"])
        self.assertTrue(rights["requires_attribution"])
        self.assertEqual(rights["policy_url"], links.TERMS_URL)
        self.assertEqual("https://" + rights["official_host"] + rights["official_path_prefix"],
                         links.URL_PREFIX)
        self.assertEqual(rights["desk"], SOURCES[FAMILY].desk_id)
        self.assertEqual(links.canonical_url(IDENT), URL)
        from scraper.sources import jp_jcg_en
        self.assertEqual(jp_jcg_en.PILOT_BEGIN, links.FAMILY_BEGIN)
        self.assertIn(URL, links.attribution(URL))
        self.assertIn("Japan Coast Guard", links.attribution(URL))

    def test_profile_is_source_level_and_evidence_bound(self):
        from analysis.analyzer import _evidence_bound, _fact_only
        self.assertIs(profile_for_source(FAMILY), JAPAN_JCG_DAILY_PROFILE)
        self.assertEqual(JAPAN_JCG_DAILY_PROFILE.desk_id, "japan")
        self.assertFalse(JAPAN_JCG_DAILY_PROFILE.daily_queue)
        self.assertTrue(_evidence_bound(JAPAN_JCG_DAILY_PROFILE))
        self.assertFalse(_fact_only(JAPAN_JCG_DAILY_PROFILE))
        pair = (JAPAN_JCG_DAILY_PROFILE.prompt_version + "+"
                + JAPAN_JCG_DAILY_PROFILE.analysis_prompt_version)
        self.assertEqual((pair,), SOURCES[FAMILY].prompt_versions)

    def test_prompts_name_only_the_coast_guard_and_exclude_attachments(self):
        from analysis import japan_jcg_prompts as prompts
        text = prompts.system_prompt() + json.dumps(prompts.analysis_messages(TITLE, BODY)) \
            + json.dumps(prompts.relevance_messages(TITLE, BODY))
        self.assertIn("Japan Coast Guard", text)
        self.assertNotIn("MINDEF", text)
        self.assertNotIn("Singapore", text)
        self.assertIn("you have not seen it", prompts.system_prompt())

    def test_output_check_requires_attribution_and_no_flag(self):
        ok = {"model_flagged": False, "summary": "The JCG said a drill took place."}
        self.assertIsNone(_jcg_output_check(ok))
        self.assertIsNone(_jcg_output_check({**ok, "summary": "Japan Coast Guard said so."}))
        for bad in ({**ok, "model_flagged": True}, {**ok, "summary": "A drill took place."}):
            self.assertEqual(_jcg_output_check(bad), "daily_japan_jcg_flag_or_attribution_held")

    def test_workflow_and_fetcher_are_off_until_the_owner_switch(self):
        workflow = (ROOT / ".github/workflows/daily_update.yml").read_text()
        self.assertIn("vars.JP_JCG_LINKS_ENABLED == 'true'", workflow)
        self.assertEqual(workflow.count("secrets.DAILY_JP_JCG_PRESS_EN_KEY"), 2)
        from scripts import fetch_daily_machine_outputs as fetch
        with tempfile.TemporaryDirectory() as tmp, patch.object(fetch, "_fetch") as call, \
                patch.dict("os.environ", {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                          "IPR_DAILY_INTAKE_DIR": tmp}, clear=False):
            import os
            os.environ.pop("JP_JCG_LINKS_ENABLED", None)
            os.environ.pop("SG_MINDEF_LINKS_ENABLED", None)
            call.return_value = "fetched"
            result = fetch.main()
            # The reading envelope follows the committed policy; the link
            # envelope still waits for its own owner switch.
            self.assertEqual(result[FAMILY], "fetched")
            self.assertNotIn(links.LINKS_NAME, result)
            os.environ["JP_JCG_LINKS_ENABLED"] = "true"
            try:
                result = fetch.main()
            finally:
                os.environ.pop("JP_JCG_LINKS_ENABLED", None)
            self.assertEqual(result[links.LINKS_NAME], "fetched")
            self.assertEqual(call.call_args.args[2], links.LINKS_REF)


class JcgCustody(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def test_verified_source_binds_identity_and_hashes(self):
        repo, head = build_custody(self.tmp)
        (record,) = d.verified_source(repo, head, FAMILY)
        self.assertEqual((record["source_identity"], record["canonical_official_url"],
                          record["publisher_posted_date"], record["official_issuer"]),
                         (IDENT, URL, DAY, links.ISSUER))
        self.assertEqual(record["content_sha256"], sha(BODY))
        self.assertIsNone(record["jcg_scope_hold"])
        self.assertFalse(_jcg_known_hold(record))
        self.assertEqual(record["body"], BODY)

    def test_wrong_remote_or_branch_is_refused(self):
        repo, head = build_custody(self.tmp, remote="https://github.com/example/other")
        with self.assertRaises(d.IntakeHold):
            d.verified_source(repo, head, FAMILY)
        shutil.rmtree(repo)
        repo, head = build_custody(self.tmp, branch="archive/another-family")
        with self.assertRaises(subprocess.CalledProcessError):
            d.verified_source(repo, head, FAMILY)

    def test_rows_outside_the_html_text_scope_are_held_and_never_signed(self):
        rows = [(IDENT, TITLE, BODY, DAY, META),
                ("jcg-en:90002", TITLE, BODY + " two", DAY, {**META, "attachments_collected": True}),
                ("jcg-en:90003", TITLE, BODY + " three", DAY, {**META, "body_scope": "pdf_text"}),
                ("jcg-en:90004", TITLE, BODY + " four", DAY, {})]
        repo, head = build_custody(self.tmp, rows)
        records = links.with_title_hash(d.verified_source(repo, head, FAMILY))
        holds = {r["source_identity"]: r["jcg_scope_hold"] for r in records}
        self.assertEqual(holds, {IDENT: None,
                                 "jcg-en:90002": "jcg_link_attachment_collected",
                                 "jcg-en:90003": "jcg_link_body_scope_not_html_text",
                                 "jcg-en:90004": "jcg_link_body_scope_not_html_text"})
        self.assertEqual(sorted(r["source_identity"] for r in records if _jcg_known_hold(r)),
                         ["jcg-en:90002", "jcg-en:90003", "jcg-en:90004"])
        envelope = links.sign_links(records, key="k" * 40)
        self.assertEqual([l["source_identity"] for l in envelope["packet"]["links"]], [IDENT])
        self.assertEqual(set(envelope["packet"]["links"][0]), set(links.LINK_FIELDS))
        self.assertNotIn(TITLE, json.dumps(envelope))
        self.assertNotIn(FIRST, json.dumps(envelope))

    def test_superseded_extraction_and_attachment_residue_are_held_in_custody(self):
        # The three originals preserved before profile 2 carry their PDF link
        # label in the text; replayed 9465/9477/9519 under profile 2 do not.
        old = {k: v for k, v in META.items() if k != "extraction_profile"}
        rows = [(IDENT, TITLE, BODY, DAY, META),
                ("jcg-en:90005", TITLE, BODY + " five", DAY, old),
                ("jcg-en:90006", TITLE, BODY + "\n\nSynthetic support summary (PDF:665KB)", DAY, META),
                ("jcg-en:90007", TITLE, BODY + " Synthetic overview\uff08PDF:269 KB\uff09", DAY, META),
                ("jcg-en:90008", TITLE, BODY + " Synthetic support (PDF: 390 KB)", DAY, META),
                ("jcg-en:90009", TITLE, "", DAY, META)]
        repo, head = build_custody(self.tmp, rows)
        records = links.with_title_hash(d.verified_source(repo, head, FAMILY))
        holds = {r["source_identity"]: r["jcg_scope_hold"] for r in records}
        self.assertEqual(holds, {IDENT: None,
                                 "jcg-en:90005": "jcg_link_extraction_profile_superseded",
                                 "jcg-en:90006": "jcg_link_attachment_label_in_text",
                                 "jcg-en:90007": "jcg_link_attachment_label_in_text",
                                 "jcg-en:90008": "jcg_link_attachment_label_in_text",
                                 "jcg-en:90009": "jcg_link_body_missing"})
        envelope = links.sign_links(records, key="k" * 40)
        self.assertEqual([l["source_identity"] for l in envelope["packet"]["links"]], [IDENT])
        factory = Mock()
        held = [r for r in records if r["source_identity"] != IDENT]
        state, _ = d.process(held, {}, family=FAMILY, policy=policy(), analyzer_factory=factory)
        factory.assert_not_called()

    def test_prose_mentioning_pdf_without_a_size_label_is_not_held(self):
        body = BODY + " The JCG said the agencies would exchange PDF manuals next year."
        repo, head = build_custody(self.tmp, [(IDENT, TITLE, body, DAY, META)])
        (record,) = d.verified_source(repo, head, FAMILY)
        self.assertIsNone(record["jcg_scope_hold"])

    def test_custody_profile_mirrors_the_collector(self):
        from scraper.sources import jp_jcg_en
        self.assertEqual(links.EXTRACTION_PROFILE, jp_jcg_en.EXTRACTION_PROFILE)
        self.assertEqual(links.FAMILY_BEGIN, jp_jcg_en.PILOT_BEGIN)

    def test_a_held_scope_row_never_reaches_the_model(self):
        repo, head = build_custody(self.tmp, [
            (IDENT, TITLE, BODY, DAY, {**META, "attachments_collected": True})])
        records = d.verified_source(repo, head, FAMILY)
        factory = Mock()
        state, _ = d.process(records, {}, family=FAMILY, policy=policy(), analyzer_factory=factory)
        factory.assert_not_called()
        self.assertNotEqual(state.get(FAMILY + ":" + IDENT, {}).get("status"), "complete")

    def test_disabled_policy_holds_before_any_analyzer(self):
        repo, head = build_custody(self.tmp)
        factory = Mock()
        off = d.load_policy()
        off["sources"][FAMILY].update(private_model_processing=False,
                                      public_machine_explanation=False, unattended_release=False)
        state, _ = d.process(d.verified_source(repo, head, FAMILY), {}, family=FAMILY,
                             policy=off, analyzer_factory=factory)
        self.assertEqual(state[FAMILY + ":" + IDENT]["reason"], "model_rights_held")
        factory.assert_not_called()


class JcgAdmission(unittest.TestCase):
    """Source -> analysis -> authenticated admission -> reader, on a scratch DB."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.db = Path(self.tmp) / "scratch.db"
        build_legacy_db(self.db)
        migrate(self.db)
        self.repo, self.head = build_custody(self.tmp)
        self.p = policy()
        self.key = "synthetic-japan-jcg-key-" * 2
        conn = self.connect()
        self.records = links.with_title_hash(d.verified_source(self.repo, self.head, FAMILY))
        with conn:
            self.parent = links.admit_links(conn, self.records, now="2026-11-12T00:00:00Z")
        self.assertEqual(self.parent["admitted"], [IDENT])
        self.bound = d.bind_admitted_metadata(self.records, conn, source_repo=self.repo)
        self.assertEqual([r["source_identity"] for r in self.bound], [IDENT])
        self.state, _ = d.process(self.bound, {}, family=FAMILY, policy=self.p,
                                  analyzer_factory=analyzer)
        self.assertEqual(self.state[FAMILY + ":" + IDENT]["status"], "complete")
        self.envelope = d.sign_outputs(self.state, family=FAMILY, policy=self.p, key=self.key)
        for k in ("title", "body", "jcg_scope_hold"):
            self.assertNotIn(k, self.envelope["packet"]["records"][0])

    def connect(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(conn.close)
        return conn

    def admit(self, conn):
        return d.admit(conn, self.envelope, family=FAMILY, policy=self.p, key=self.key)

    def reader(self, policy_=None):
        from core import daily_machine_records as reader
        with patch.object(reader, "load_policy", return_value=policy_ or self.p):
            return reader.load(self.db)

    def raw_insert(self, conn, identity=IDENT, family=FAMILY):
        row = dict(zip(d.PUBLIC_FIELDS, [family, identity] + ["a" * 64] * 3
                       + ["e" * 40, "1-1", "JCG s.", "[]", 0, None, "m", "v", "q" * 64, "p" * 64]))
        cols = ["categories_json" if k == "categories" else k for k in row]
        conn.execute("INSERT INTO daily_machine_records (" + ",".join(cols) + ") VALUES ("
                     + ",".join("?" * len(cols)) + ")", list(row.values()))

    def test_m0023_applied_and_trigger_requires_the_jcg_parent(self):
        conn = self.connect()
        self.assertTrue(m23.is_already_applied(conn))
        self.assertTrue(m22.is_already_applied(conn))
        self.assertTrue(SOURCES[FAMILY].admission_ready(conn))
        with self.assertRaises(sqlite3.IntegrityError) as caught:
            self.raw_insert(conn, "jcg-en:77777")
        self.assertIn("daily_machine_record_parent_missing", str(caught.exception))
        # A held parent is not a parent.
        conn.execute("UPDATE " + links.TABLE + " SET public_scope='held'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.raw_insert(conn)
        # The Singapore predicate still applies after the re-issue.
        with self.assertRaises(sqlite3.IntegrityError):
            self.raw_insert(conn, "synthetic-release", "sg_mindef_releases")

    def test_m0023_is_idempotent_and_reported_by_the_runner(self):
        conn = self.connect()
        before = conn.execute("SELECT * FROM " + links.TABLE).fetchall()
        m23.up(conn)
        self.assertEqual(conn.execute("SELECT * FROM " + links.TABLE).fetchall(), before)
        from migrations import runner
        report = [f for f in dir(runner) if f in ("verify", "integrity_report", "status")]
        self.assertTrue(report)

    def test_table_admits_only_canonical_article_urls(self):
        conn = self.connect()
        cols = ("source_identity,canonical_official_url,publisher_posted_date,source_git_commit,"
                "metadata_version_sha256,content_sha256,capture_sha256,title_sha256,"
                "first_seen_run,official_issuer,public_scope,admitted_at_utc")

        def insert(ident, url, issuer=links.ISSUER, day=DAY):
            conn.execute("INSERT INTO " + links.TABLE + " (" + cols + ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (ident, url, day, "e" * 40, "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                          "1-1", issuer, "official_link_only", "2026-11-12T00:00:00Z"))
        for ident, url in (
                ("jcg-en:90010", "https://www.kaiho.mlit.go.jp/e/topics_archive/article90010.pdf"),
                ("jcg-en:90010", "https://www.kaiho.mlit.go.jp/info/kouhou/article90010.html"),
                ("jcg-en:90010", "https://www.kaiho.mlit.go.jp/e/topics_archive/article90011.html"),
                ("jcg-en:90010", "https://www.kaiho.mlit.go.jp/e/topics_archive/article90010.html?x=1"),
                ("jcg-en:0901", "https://www.kaiho.mlit.go.jp/e/topics_archive/article0901.html"),
                ("jcg-en:9x", "https://www.kaiho.mlit.go.jp/e/topics_archive/article9x.html"),
                ("mod:90010", "https://www.kaiho.mlit.go.jp/e/topics_archive/article90010.html")):
            with self.subTest(url=url, ident=ident), self.assertRaises(sqlite3.IntegrityError):
                insert(ident, url)
        with self.assertRaises(sqlite3.IntegrityError):
            insert("jcg-en:90010", links.canonical_url("jcg-en:90010"), issuer="jp_mod")
        with self.assertRaises(sqlite3.IntegrityError):
            insert("jcg-en:90010", links.canonical_url("jcg-en:90010"), day="2026-08-31")
        insert("jcg-en:90010", links.canonical_url("jcg-en:90010"))

    def test_admission_reaches_the_reader_with_only_permitted_components(self):
        conn = self.connect()
        self.assertEqual(self.admit(conn)["admitted"], 1)
        (row,) = self.reader()
        self.assertEqual((row["url"], row["source_label"], row["publisher"], row["issuer"],
                          row["desk_id"], row["published_date"], row["machine_only"]),
                         (URL, "JCG", "Japan Coast Guard", "Japan Coast Guard", "japan", DAY, True))
        self.assertIn("JCG", row["summary"])
        stored = " ".join(str(v) for t in (links.TABLE, "daily_machine_records")
                          for r in conn.execute("SELECT * FROM " + t) for v in r if v is not None)
        for needle in (TITLE, FIRST, SECOND):
            self.assertNotIn(needle, stored)

    def test_admission_is_idempotent(self):
        conn = self.connect()
        self.assertEqual(self.admit(conn)["admitted"], 1)
        self.assertEqual(self.admit(conn)["admitted"], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM daily_machine_records").fetchone()[0], 1)
        with conn:
            summary = links.admit_links(conn, self.records)
        self.assertEqual((summary["admitted"], summary["unchanged"], summary["held"]),
                         ([], [IDENT], []))

    def test_policy_off_or_excluded_identity_means_nothing_is_public(self):
        conn = self.connect()
        self.admit(conn)
        conn.commit()
        self.assertEqual(self.reader(policy(False)), [])
        excluded = policy()
        excluded["sources"][FAMILY]["excluded_source_identities"] = [IDENT]
        self.assertEqual(self.reader(excluded), [])
        self.assertEqual(len(self.reader()), 1)

    def test_drifted_original_withdraws_the_record_from_readers(self):
        conn = self.connect()
        self.admit(conn)
        conn.commit()
        changed = [{**self.records[0], "content_sha256": sha("edited")}]
        changed[0]["metadata_version_sha256"] = links.version_hash(changed[0])
        with conn:
            summary = links.admit_links(conn, changed)
        self.assertEqual(summary["held"], [IDENT])
        self.assertEqual(self.reader(), [])

    def test_signed_link_envelope_round_trip_and_tamper_refusal(self):
        fresh = Path(self.tmp) / "fresh.db"
        build_legacy_db(fresh)
        migrate(fresh)
        envelope = links.sign_links(self.records, key=self.key)
        with sqlite3.connect(str(fresh)) as conn:
            summary = links.admit_signed_links(conn, envelope, key=self.key)
            self.assertEqual(summary["admitted"], [IDENT])
            self.assertEqual(links.read_parent(conn, IDENT)["canonical_official_url"], URL)
            for bad_key in ("other-key-" * 5, "short"):
                with self.assertRaises(links.LinkRefused):
                    links.admit_signed_links(conn, envelope, key=bad_key)
            tampered = json.loads(json.dumps(envelope))
            tampered["packet"]["links"][0]["publisher_posted_date"] = "2026-10-29"
            with self.assertRaises(links.LinkRefused):
                links.admit_signed_links(conn, tampered, key=self.key)
        conn.close()
        # The machine-output MAC domain cannot authenticate a link envelope.
        self.assertNotEqual(envelope["mac"], self.envelope["mac"])

    def test_link_refusals_write_nothing(self):
        conn = self.connect()
        base = self.records[0]

        def variant(**change):
            r = {**base, "source_identity": "jcg-en:90020",
                 "canonical_official_url": links.canonical_url("jcg-en:90020"), **change}
            r["metadata_version_sha256"] = links.version_hash(r)
            return r
        cases = {
            "jcg_link_url_not_canonical": variant(
                canonical_official_url="https://www.kaiho.mlit.go.jp/e/topics_archive/a.pdf"),
            "jcg_link_date_invalid": variant(publisher_posted_date="2026-08-31"),
            "jcg_link_attachment_collected": variant(jcg_scope_hold="jcg_link_attachment_collected"),
            "jcg_link_identity_invalid": variant(source_identity="jcg-ja:90020"),
        }
        for reason, record in cases.items():
            with self.subTest(reason=reason), conn:
                summary = links.admit_links(conn, [record])
                self.assertEqual(list(summary["refused"].values()), [reason])
        self.assertEqual(conn.execute("SELECT count(*) FROM " + links.TABLE).fetchone()[0], 1)

    def test_original_text_in_a_reading_is_refused_before_signing(self):
        leaked = reading(summary_english=FIRST + " " + SECOND, facts=[
            dict(sentence=FIRST, evidence=FIRST), dict(sentence=SECOND, evidence=SECOND)])
        state, _ = d.process(self.bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(leaked))
        self.assertNotEqual(state[FAMILY + ":" + IDENT]["status"], "complete")

    def test_unattributed_or_flagged_output_is_held(self):
        unattributed = "It held a routine joint exercise between two coast guard agencies."
        bad = reading(summary_english=unattributed + " " + reading()["facts"][1]["sentence"],
                      facts=[dict(sentence=unattributed, evidence=FIRST), reading()["facts"][1]])
        state, _ = d.process(self.bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(bad))
        self.assertEqual(state[FAMILY + ":" + IDENT]["quality_hold"], "daily_attribution_missing")
        flagged = reading(is_significant=True, significance_reasoning="JCG note.",
                          flag_evidence=SECOND)
        state, _ = d.process(self.bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(flagged))
        envelope = d.sign_outputs(state, family=FAMILY, policy=self.p, key=self.key)
        conn = self.connect()
        result = d.admit(conn, envelope, family=FAMILY, policy=self.p, key=self.key)
        self.assertEqual(result, {"admitted": 0,
                                  "holds": ["daily_japan_jcg_flag_or_attribution_held"]})
        self.assertEqual(conn.execute("SELECT count(*) FROM daily_machine_records").fetchone()[0], 0)

    def test_cli_admits_a_signed_envelope_and_reports_a_missing_one(self):
        fresh = Path(self.tmp) / "cli.db"
        build_legacy_db(fresh)
        migrate(fresh)
        path = Path(self.tmp) / links.LINKS_NAME
        path.write_text(json.dumps(links.sign_links(self.records, key=self.key)))
        env = {"PATH": __import__("os").environ["PATH"], links.KEY_ENV: self.key}
        cli = [sys.executable, str(ROOT / "scripts/japan_jcg_links.py"), "admit",
               "--database", str(fresh)]
        proc = subprocess.run(cli + ["--envelope", str(path)], capture_output=True, text=True, env=env)
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["admitted"]), (0, 1), proc.stderr)
        proc = subprocess.run(cli + ["--envelope", str(path) + ".absent"], capture_output=True,
                              text=True, env=env)
        self.assertEqual(json.loads(proc.stdout), {"status": "no_link_envelope_delivered"})
        proc = subprocess.run(cli + ["--envelope", str(path)], capture_output=True, text=True,
                              env={**env, links.KEY_ENV: "wrong-key-" * 5})
        self.assertEqual((proc.returncode, json.loads(proc.stdout)),
                         (1, {"status": "held", "reason": "jcg_link_envelope_mac_invalid"}))
        self.assertNotIn(self.key, proc.stdout + proc.stderr)


class JcgRenderedDelivery(unittest.TestCase):
    """Real build: source -> analysis -> admission -> Record page, Japan Desk, Archive.

    Runs the chain on a scratch copy of the tracked database and renders with
    the production preview generator. The tracked database and production
    output are untouched; the release and its model reading are synthetic.
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as gp
        from core import daily_machine_records as reader
        if not Path(gp.TRACKED_DB).exists():
            raise unittest.SkipTest("tracked database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="jcg-delivery-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.tracked = Path(gp.TRACKED_DB)
        cls.tracked_before = hashlib.sha256(cls.tracked.read_bytes()).hexdigest()
        db = cls.tmp / "scratch.db"
        shutil.copy(gp.TRACKED_DB, db)
        migrate(db)
        repo, head = build_custody(str(cls.tmp))
        p = policy()
        key = "synthetic-japan-jcg-key-" * 2
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON")
        records = links.with_title_hash(d.verified_source(repo, head, FAMILY))
        with conn:
            links.admit_links(conn, records, now="2026-11-12T00:00:00Z")
        bound = d.bind_admitted_metadata(records, conn, source_repo=repo)
        state, _ = d.process(bound, {}, family=FAMILY, policy=p, analyzer_factory=analyzer)
        env = d.sign_outputs(state, family=FAMILY, policy=p, key=key)
        cls.admitted = d.admit(conn, env, family=FAMILY, policy=p, key=key)
        conn.close()
        briefs = cls.tmp / "briefs"
        briefs.mkdir()
        with patch.object(reader, "load_policy", return_value=p):
            cls.rows = [r for r in reader.load(db) if r["desk_id"] == "japan"]
            cls.out = cls.tmp / "build"
            gp.build(cls.out, "Japan delivery test", db, snapshot=gp.snapshot_from_corpus(db),
                     briefs_dir=briefs, dossiers_dir=cls.tmp / "no-dossiers")
        cls.record_path = cls.rows[0]["record_path"] if cls.rows else None

    def page(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_admitted_one_record_and_tracked_database_untouched(self):
        self.assertEqual(self.admitted, {"admitted": 1, "holds": []})
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(hashlib.sha256(self.tracked.read_bytes()).hexdigest(), self.tracked_before)

    def test_record_page_carries_the_licence_attribution_and_edited_notice(self):
        page = self.page(self.record_path)
        self.assertIn("Japan Desk", page)
        self.assertNotIn("Philippines Desk", page)
        self.assertIn("../japan.html", page)
        for sentence in (r["sentence"] for r in reading()["facts"]):
            self.assertIn(sentence, page)
        self.assertIn("data-pdl-attribution", page)
        self.assertIn("Source: Japan Coast Guard website (", page)
        self.assertIn(URL, page)
        self.assertIn("Public Data License (Version 1.0)", page)
        self.assertIn("created by Indo-Pacific Record", page)
        self.assertIn("was not created by the Government of Japan", page)
        self.assertIn("Machine-generated from the English source", page)
        self.assertIn(self.rows[0]["content_sha256"], page)

    def test_other_desks_record_pages_do_not_gain_the_japan_notice(self):
        others = [p for p in (self.out / "record").glob("source-*.html")
                  if p.name != Path(self.record_path).name]
        for path in others:
            self.assertNotIn("data-pdl-attribution", path.read_text(encoding="utf-8"))

    def test_japan_desk_lists_the_record_with_attribution(self):
        desk = self.page("japan.html")
        self.assertIn("data-japan-machine-explanations", desk)
        self.assertIn(self.record_path, desk)
        self.assertIn(URL, desk)
        self.assertIn("Source: Japan Coast Guard website", desk)
        self.assertIn("edited content, not statements made by the Government of Japan", desk)
        self.assertIn("linked documents and media are not republished", desk)

    def test_archive_index_carries_the_record(self):
        self.assertIn('value="machine_explanation"', self.page("archive.html"))
        self.assertIn(self.record_path, self.page("archive-research-index.json"))

    def test_no_original_title_or_body_text_reaches_any_public_file(self):
        needles = (TITLE, FIRST, SECOND)
        leaks = []
        for path in self.out.rglob("*"):
            if path.is_file() and path.suffix in {".html", ".json", ".js", ".xml", ".txt", ".csv"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(n in text for n in needles):
                    leaks.append(str(path.relative_to(self.out)))
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
