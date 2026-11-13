"""Japan Coast Guard English releases in the shared Daily lane: synthetic offline contracts.

No JCG text, media or capture is used or committed. Bodies are synthetic
English placeholders, custody is a throw-away git repository, and the model is
a fake returning a fixed reading. Nothing here spends money, contacts the
publisher or touches a production database.
"""
import hashlib
import html
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from core import japan_jcg_links as links
from core import japan_jcg_rights as rights
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
THIRD = "Both agencies will review the drill results together after the exercise concludes."
BODY = FIRST + "\n\n" + SECOND + "\n\n" + THIRD
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


def article_html(title, body, day):
    """A synthetic JCG release page in the publisher's structure (no JCG text)."""
    paragraphs = "".join("<p>" + html.escape(p) + "</p>" for p in body.split("\n\n"))
    return ('<html><head><title>x</title></head><body><main><article class="main-article">'
            '<section class="topics topics-article"><h1 class="entry-title">' + html.escape(title)
            + '</h1><time>' + day + '</time><div class="topics-article__main tich-text">'
            + paragraphs + '</div></section></article></main>'
            '<footer>Copyright (c) Synthetic footer notice. All rights reserved.</footer>'
            '</body></html>').encode()


def policy_page(clauses=rights.POLICY_CLAUSES, extra=""):
    """A synthetic terms page carrying the reviewed clause strings only."""
    return ("<html><body><main>" + "".join("<p>" + c + "</p>" for c in clauses)
            + extra + "</main></body></html>").encode()


def iso(when):
    return when.isoformat()


def request(url, raw, when):
    return {"requested_url": url, "final_url": url, "method": "GET", "form": None,
            "http_status": 200, "retrieved_at": iso(when), "capture_sha256": hashlib.sha256(raw).hexdigest(),
            "content_type": "text/html; charset=UTF-8", "payload_bytes": len(raw)}


def build_custody(root, rows=None, *, remote=REMOTE, branch="archive/japan-jcg",
                  omit_capture=(), corrupt_capture=(), stored_text=None,
                  policy=b"", policy_at=None, ledger_result="ok"):
    """A synthetic private custody checkout; returns (repo path, pinned commit).

    ``rows`` are (identity, title, body, day, metadata) tuples; the URL is the
    family's canonical article URL unless metadata carries ``_url``. Each row
    gets a synthetic raw HTML capture and a collector ledger request in its
    first-seen run, and the run captures the synthetic terms page, as the
    collector does. Overrides: ``omit_capture`` leaves a row's bytes out,
    ``corrupt_capture`` alters them after hashing, ``stored_text`` stores a
    different text than the capture holds, ``policy`` replaces (or with None
    omits) the terms capture and ``policy_at`` dates it.
    """
    rows = rows if rows is not None else [(IDENT, TITLE, BODY, DAY, META)]
    stored_text = stored_text or {}
    now = datetime.now(timezone.utc)
    repo = Path(root) / "custody"
    (repo / "state/captures").mkdir(parents=True)
    (repo / "state/ledger").mkdir()
    requests_ = []

    def keep(raw, corrupt=False):
        digest = hashlib.sha256(raw).hexdigest()
        (repo / "state/captures" / (digest + ".bin")).write_bytes(raw + b" " if corrupt else raw)
        return digest

    with sqlite3.connect(str(repo / "state/shadow.db")) as conn:
        conn.execute("CREATE TABLE shadow_records (url TEXT PRIMARY KEY, source_slug TEXT,"
                     " title_original TEXT, text_original TEXT, published_date TEXT,"
                     " language_tag TEXT, publication_kind TEXT, content_sha256 TEXT,"
                     " capture_sha256 TEXT, retrieved_at TEXT, first_seen_run TEXT,"
                     " source_identity TEXT, metadata_json TEXT)")
        for ident, title, body, day, meta in rows:
            meta = dict(meta)
            url = meta.pop("_url", links.canonical_url(ident))
            raw = article_html(title, body, day)
            capture = hashlib.sha256(raw).hexdigest()
            if ident not in omit_capture:
                keep(raw, corrupt=ident in corrupt_capture)
            requests_.append(request(url, raw, now))
            text = stored_text.get(ident, body)
            conn.execute("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (url, FAMILY, title, text, day, "en", "english_official_press_release",
                          sha(text), capture, "2026-11-01T00:00:00Z", RUN,
                          ident, json.dumps(meta)))
    conn.close()
    if policy is not None:
        raw = policy_page() if policy == b"" else policy
        keep(raw)
        requests_.insert(0, request(rights.POLICY_URL, raw, policy_at or now))
    (repo / "state/ledger" / ("20261101T000000-" + RUN + ".json")).write_text(json.dumps({
        "run_id": RUN, "result": ledger_result, "finished_utc": iso(now),
        "requests": requests_}))
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["checkout", "-q", "-b", branch], check=True)
    subprocess.run(git + ["add", "state"], check=True)
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
            # With the owner switch off, neither the parent links nor the
            # machine envelope is fetched, although the committed policy is on.
            self.assertEqual(result[FAMILY], "public_switch_off")
            self.assertNotIn(links.LINKS_NAME, result)
            self.assertNotIn("envelopes/" + FAMILY + ".json",
                             [c.args[0] for c in call.call_args_list])
            os.environ["JP_JCG_LINKS_ENABLED"] = "true"
            try:
                result = fetch.main()
            finally:
                os.environ.pop("JP_JCG_LINKS_ENABLED", None)
            self.assertEqual(result[FAMILY], "fetched")
            self.assertEqual(result[links.LINKS_NAME], "fetched")
            self.assertIn("envelopes/" + FAMILY + ".json",
                          [c.args[0] for c in call.call_args_list])
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


class JcgRightsQualification(unittest.TestCase):
    """The standing-rights replay (#1015) blocks signing and model input alike."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def held(self, code, rows=None, **custody):
        repo, head = build_custody(self.tmp, rows, **custody)
        records = links.with_title_hash(d.verified_source(repo, head, FAMILY))
        holds = {r["source_identity"]: r["jcg_scope_hold"] for r in records}
        self.assertEqual(holds[IDENT], code)
        self.assertTrue(_jcg_known_hold([r for r in records if r["source_identity"] == IDENT][0]))
        envelope = links.sign_links(records, key="k" * 40)
        self.assertNotIn(IDENT, [l["source_identity"] for l in envelope["packet"]["links"]])
        factory = Mock()
        state, _ = d.process([r for r in records if r["source_identity"] == IDENT], {},
                             family=FAMILY, policy=policy(), analyzer_factory=factory)
        factory.assert_not_called()
        self.assertNotEqual(state.get(FAMILY + ":" + IDENT, {}).get("status"), "complete")
        return records

    def test_bound_capture_current_terms_and_clean_item_qualify_and_sign(self):
        repo, head = build_custody(self.tmp)
        records = links.with_title_hash(d.verified_source(repo, head, FAMILY))
        self.assertIsNone(records[0]["jcg_scope_hold"])
        envelope = links.sign_links(records, key="k" * 40)
        self.assertEqual([l["source_identity"] for l in envelope["packet"]["links"]], [IDENT])
        factory = Mock(return_value=analyzer())
        state, _ = d.process(records, {}, family=FAMILY, policy=policy(), analyzer_factory=factory)
        factory.assert_called()

    def test_missing_capture_blocks(self):
        self.held("jcg_rights_capture_missing", omit_capture={IDENT})

    def test_capture_bytes_not_matching_their_hash_block(self):
        self.held("jcg_rights_capture_hash_mismatch", corrupt_capture={IDENT})

    def test_stored_text_not_reproduced_by_the_capture_blocks(self):
        self.held("jcg_rights_stored_text_not_bound_to_capture",
                  stored_text={IDENT: BODY + " An inserted sentence the publisher never wrote."})

    def test_capture_without_a_successful_ledger_request_blocks(self):
        self.held("jcg_rights_capture_not_authenticated", ledger_result="fetch_failure")

    def test_missing_terms_capture_blocks(self):
        self.held("jcg_rights_policy_capture_missing", policy=None)

    def test_changed_terms_block(self):
        self.held("jcg_rights_policy_terms_changed_or_incomplete",
                  policy=policy_page(rights.POLICY_CLAUSES[1:]))
        shutil.rmtree(Path(self.tmp) / "custody")
        self.held("jcg_rights_policy_conflicting_restriction",
                  policy=policy_page(extra="<p>本コンテンツの転載を禁止します。</p>"))

    def test_stale_terms_capture_blocks(self):
        old = datetime.now(timezone.utc) - timedelta(days=8)
        self.held("jcg_rights_standing_license_missing_changed_or_stale", policy_at=old)

    def test_quoted_third_party_prose_blocks(self):
        quote = (FIRST + "\n\n" + SECOND + ' The visiting commandant said "our two services will '
                 'keep training together on every patrol route across the region this year."')
        self.held("jcg_rights_item_third_party_text", [(IDENT, TITLE, quote, DAY, META)])
        shutil.rmtree(Path(self.tmp) / "custody")
        statement = BODY + " The full text of the statement by the partner agency follows."
        self.held("jcg_rights_item_third_party_text", [(IDENT, TITLE, statement, DAY, META)])

    def test_short_quoted_names_are_first_party_prose(self):
        body = BODY + ' Crews boarded the patrol vessel "SYNTHETIC" to realize a "free and open sea".'
        repo, head = build_custody(self.tmp, [(IDENT, TITLE, body, DAY, META)])
        (record,) = d.verified_source(repo, head, FAMILY)
        self.assertIsNone(record["jcg_scope_hold"])

    def test_rights_notation_in_the_body_blocks_but_the_site_footer_does_not(self):
        # Every synthetic page carries a footer copyright notice (see article_html).
        body = BODY + " Photo courtesy of a partner agency."
        self.held("jcg_rights_item_rights_notation", [(IDENT, TITLE, body, DAY, META)])

    def test_privacy_or_secrecy_marker_blocks(self):
        body = BODY + " Details of the confidential schedule were withheld."
        self.held("jcg_rights_item_privacy_or_secrecy", [(IDENT, TITLE, body, DAY, META)])

    def test_a_replay_failure_is_a_hold_not_an_exception(self):
        with patch.object(rights, "_parser", side_effect=ImportError("synthetic")):
            self.held("jcg_rights_replay_failed")

    def test_qualification_reuses_the_standing_contract(self):
        from core import standing_source_rights as standing
        repo, head = build_custody(self.tmp)
        with patch.object(standing, "qualify_standing_text",
                          wraps=standing.qualify_standing_text) as contract:
            d.verified_source(repo, head, FAMILY)
        (call,) = contract.call_args_list
        self.assertEqual(call.kwargs["kind"], "original_text")
        self.assertEqual(call.args[0]["source_family"], FAMILY)
        self.assertEqual(call.kwargs["proposed_sha256"], sha(BODY))
        self.assertEqual(POLICIES[FAMILY]["policy_url"], rights.POLICY_URL)
        self.assertEqual(POLICIES[FAMILY]["policy_id"], rights.POLICY_ID)

    def test_collector_captures_the_terms_page_into_custody(self):
        from scraper.sources import jp_jcg_en
        self.assertEqual(jp_jcg_en.POLICY_URL, rights.POLICY_URL)
        self.assertEqual(links.TERMS_URL, rights.POLICY_URL)


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

    def test_rollback_switch_stops_admission_against_an_admitted_parent(self):
        """JP_JCG_LINKS_ENABLED=false after a parent was admitted: no machine
        envelope is fetched, a stale one is removed, and the pipeline reports
        the family inactive without calling intake. Switch on: it admits."""
        import os
        import pipeline
        from core.collection.status import SKIPPED_DISABLED
        from tests.test_manual_source_definitions import FakeRegistry
        from scripts import fetch_daily_machine_outputs as fetch
        conn = self.connect()
        count = lambda: conn.execute(
            "SELECT COUNT(*) FROM daily_machine_records WHERE source_family=?", (FAMILY,)).fetchone()[0]
        self.assertEqual(conn.execute("SELECT public_scope FROM " + links.TABLE
                                      + " WHERE source_identity=?", (IDENT,)).fetchone()[0],
                         "official_link_only")
        intake_dir = Path(self.tmp) / "intake"
        intake_dir.mkdir()
        stale = intake_dir / (FAMILY + ".json")
        env = {"IPR_PRIVATE_DAILY_ENABLED": "true", "IPR_DAILY_INTAKE_DIR": str(intake_dir),
               SOURCES[FAMILY].key_env: self.key}
        for switch in (None, "false", "TRUE", "1"):
            with self.subTest(switch=switch), patch.dict(os.environ, env), \
                    patch.object(d, "load_policy", return_value=self.p), \
                    patch.object(fetch, "load_policy", return_value=self.p), \
                    patch.object(fetch, "_fetch", return_value="fetched") as fetched:
                os.environ.pop("JP_JCG_LINKS_ENABLED", None)
                if switch is not None:
                    os.environ["JP_JCG_LINKS_ENABLED"] = switch
                stale.write_text(json.dumps(self.envelope))
                result = fetch.main()
                self.assertEqual(result[FAMILY], "public_switch_off")
                self.assertFalse(stale.exists())
                self.assertNotIn("envelopes/" + FAMILY + ".json",
                                 [c.args[0] for c in fetched.call_args_list])
                # Even if a stale envelope survived, the pipeline never reads it.
                stale.write_text(json.dumps(self.envelope))
                intake = Mock()
                entry = pipeline._daily_admission(FAMILY, intake=intake)
                self.assertEqual(entry.inactive_reason(), "owner public switch is off")
                with patch.object(pipeline, "_governed_admissions",
                                  return_value={"jp_jcg_press_en": entry}):
                    errors = []
                    rows = pipeline.run_governed_manual_sources(
                        ["jp_jcg_press_en"], 1, FakeRegistry("japan_jcg"), errors)
                self.assertEqual(errors, [])
                self.assertEqual([(r.status, r.error_detail) for r in rows],
                                 [(SKIPPED_DISABLED, "owner public switch is off")])
                intake.assert_not_called()
                self.assertEqual(count(), 0)
        # Positive control: the same envelope is admitted once the switch is on.
        from processing import daily_runner
        with patch.dict(os.environ, {**env, "JP_JCG_LINKS_ENABLED": "true"}), \
                patch.object(d, "load_policy", return_value=self.p), \
                patch.object(daily_runner, "load_policy", return_value=self.p), \
                patch.object(pipeline, "DB_PATH", self.db):
            entry = pipeline._daily_admission(FAMILY)
            self.assertIsNone(entry.inactive_reason())
            entry.admit(1)
        self.assertEqual(count(), 1)

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


IDENT2 = "jcg-en:90002"
QUOTED = (FIRST + "\n\n" + SECOND + ' The visiting commandant said "our two services will '
          'keep training together on every patrol route across the region this year."')


def commit_run(repo, run_id, *, terms, raw=None):
    """Commit a later collector run to custody; returns the new pinned commit.

    ``terms`` is "ok" (a fresh capture of the synthetic terms page) or the
    failure status the collector records in listing_report["site_terms"]; a
    failed attempt keeps the publisher's 503 evidence, as _request does (a
    timeout keeps none); ``raw``
    replaces the captured terms page. The
    run itself succeeds and adds no new rows, as a quiet collector day does.
    """
    now = datetime.now(timezone.utc)
    if terms == "ok":
        raw = raw or policy_page()
        (repo / "state/captures" / (hashlib.sha256(raw).hexdigest() + ".bin")).write_bytes(raw)
        attempts = [request(rights.POLICY_URL, raw, now)]
    elif terms == "timeout":
        attempts = []  # _request keeps no evidence when no response arrives
    else:
        attempts = [dict(request(rights.POLICY_URL, b"<html></html>", now), http_status=503)]
    (repo / "state/ledger" / (now.strftime("%Y%m%dT%H%M%S%f") + "-" + run_id + ".json")).write_text(
        json.dumps({"run_id": run_id, "result": "ok_no_publications", "finished_utc": iso(now),
                    "listing_report": {"site_terms": terms}, "requests": attempts}))
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["add", "state"], check=True)
    subprocess.run(git + ["commit", "-qm", "run " + run_id], check=True)
    return subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


class JcgPolicyEvidenceTransitions(unittest.TestCase):
    """Two policy-evidence transitions through the existing handoff and queue.

    Private side: the collector workflow's link-bridge step
    (scripts/japan_jcg_links.py sign), then processing.daily_runner.private_run,
    which the shared Daily processing workflow runs with --private-daily-state
    handoff/queues/F.json and --private-daily-out handoff/envelopes. Public
    side: scripts/fetch_daily_machine_outputs.py (its private-branch read
    served from the handoff directory), the link admit CLI, then
    pipeline._daily_admission. Policy, key and switch values are synthetic;
    the model is a fake; nothing contacts the publisher or GitHub.
    """

    def setUp(self):
        import os
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "public.db"
        build_legacy_db(self.db)
        migrate(self.db)
        meta2 = dict(META, source_identity=IDENT2)
        self.repo, self.head = build_custody(
            self.tmp, [(IDENT, TITLE, BODY, DAY, META), (IDENT2, TITLE + " two", QUOTED, DAY, meta2)])
        self.p = policy()
        self.key = "synthetic-japan-jcg-key-" * 2
        records = links.with_title_hash(d.verified_source(self.repo, self.head, FAMILY))
        holds = {r["source_identity"]: r["jcg_scope_hold"] for r in records}
        self.assertEqual(holds, {IDENT: None, IDENT2: "jcg_rights_item_third_party_text"})
        # IDENT2's parent stands in for one admitted before its item-level
        # replay held it: the case that leaves an item-specific rights hold in
        # the private queue rather than outside it.
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            parents = links.admit_links(conn, [dict(r, jcg_scope_hold=None) for r in records],
                                        now="2026-11-12T00:00:00Z")
        self.assertEqual(sorted(parents["admitted"]), [IDENT, IDENT2])
        self.handoff = self.tmp / "handoff"
        self.queue = self.handoff / "queues" / (FAMILY + ".json")
        self.envelopes = self.handoff / "envelopes"
        self.public_in = self.tmp / "public-machine-outputs"
        self.model = analyzer()
        self.factory = Mock(return_value=self.model)
        self.env = patch.dict(os.environ, {"DAILY_OUTPUT_KEY": self.key,
                                           SOURCES[FAMILY].key_env: self.key,
                                           "JP_JCG_LINKS_ENABLED": "true"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.handoff.mkdir()
        signed = self.sign_links(self.head)
        self.assertEqual([l["source_identity"] for l in signed["packet"]["links"]], [IDENT])

    def collector_run(self, run_id, *, terms, raw=None):
        """A later collector run committed to custody, then its link-bridge step."""
        head = commit_run(self.repo, run_id, terms=terms, raw=raw)
        self.sign_links(head)
        return head

    def sign_links(self, head):
        from scripts import japan_jcg_links as bridge
        with patch("sys.stdout"):
            code = bridge.main(["sign", "--source-checkout", str(self.repo), "--source-commit", head,
                                "--output", str(self.handoff / "jp_jcg_press_en.links.json")])
        self.assertEqual(code, 0)  # the collector workflow step succeeds
        return json.loads((self.handoff / "jp_jcg_press_en.links.json").read_text())

    def shared_processing(self, head):
        """One shared Daily processing run on a pinned custody commit."""
        from processing import daily_runner
        with patch.object(daily_runner, "load_policy", return_value=self.p), \
             patch("analysis.analyzer.Analyzer", self.factory), \
             patch.object(d, "bound_private_calls", return_value=None), \
             patch("analysis.usage.build_run_record", return_value=[]):
            daily_runner.private_run(FAMILY + "," + str(self.repo) + "," + head,
                                     public_db=self.db, state_path=self.queue,
                                     out_dir=self.envelopes)
        state = json.loads(self.queue.read_text())
        envelope = json.loads((self.envelopes / (FAMILY + ".json")).read_text())
        return state, envelope

    def public_daily(self):
        """The public Daily: fetch, admit link parents, then govern admission."""
        import os
        import pipeline
        from processing import daily_runner
        from scripts import fetch_daily_machine_outputs as fetch
        from scripts import japan_jcg_links as bridge

        def private_branch(remote_path, path, ref="state/shared-daily"):
            source = self.handoff / remote_path  # envelopes/F.json or the links file
            if not source.exists():
                return "fetch_failed"
            shutil.copyfile(source, path)
            return "fetched"

        env = {"IPR_PRIVATE_DAILY_ENABLED": "true", "IPR_DAILY_INTAKE_DIR": str(self.public_in)}
        with patch.dict(os.environ, env), \
                patch.object(fetch, "load_policy", return_value=self.p), \
                patch.object(d, "load_policy", return_value=self.p), \
                patch.object(daily_runner, "load_policy", return_value=self.p), \
                patch.object(fetch, "_fetch", side_effect=private_branch), \
                patch.object(pipeline, "DB_PATH", self.db), patch("sys.stdout"):
            results = fetch.main()
            self.assertEqual(results[FAMILY], "fetched")
            self.assertEqual(results[links.LINKS_NAME], "fetched")
            self.assertEqual(bridge.main(["admit", "--database", str(self.db), "--envelope",
                                          str(self.public_in / links.LINKS_NAME)]), 0)
            self.assertIsNone(pipeline._daily_admission(FAMILY).inactive_reason())
            # The governed dispatcher writes this result as the family's
            # source_run_results row: the operator report's per-source line.
            from core.registry import get_registry
            self.errors = []
            [outcome] = pipeline.run_governed_manual_sources(
                [FAMILY], 1, get_registry(), self.errors)
        envelope = json.loads((self.public_in / (FAMILY + ".json")).read_text())
        with sqlite3.connect(str(self.db)) as conn:
            public = [r[0] for r in conn.execute(
                "SELECT source_identity FROM daily_machine_records WHERE source_family=? "
                "AND publication_state!='held'", (FAMILY,))]
            parents = [r[0] for r in conn.execute(
                "SELECT source_identity FROM " + links.TABLE + " WHERE public_scope="
                "'official_link_only' ORDER BY source_identity")]
        self.assertEqual(parents, [IDENT, IDENT2])  # parents stay admitted throughout
        return {"records": len(envelope["packet"]["records"]),
                "outcome": outcome}, public

    def outage_run(self, run_id, *, failure, terms_only=False):
        """A real collector run (scripts/shadow_collect_desk.main) into custody.

        ``failure`` is how the publisher fails: "503", "403", "timeout",
        "host" (robots.txt unreachable, so nothing else is requested) or
        "listing" (the listing alone returns 503). The
        terms page and listing both fail unless ``terms_only``. The run's
        state is committed and the link-bridge step signs, as the private
        workflow does after the collector step. Returns (exit code, ledger
        entry, pinned commit).
        """
        import contextlib
        import functools
        import io
        import requests as http
        from scraper.sources.jp_jcg_en import JCGEnglishAdapter, LISTING, POLICY_URL
        from scripts import shadow_collect_desk as runner
        from tests.test_japan_jcg_manual_shadow_gate import HOST, MemorySession, Response
        state = self.repo / "state"
        with sqlite3.connect(str(state / "shadow.db")) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS shadow_meta (desk TEXT)")
            if not conn.execute("SELECT 1 FROM shadow_meta").fetchone():
                conn.execute("INSERT INTO shadow_meta VALUES ('japan_jcg')")
        session = MemorySession()
        failing = {"host": [HOST + "/robots.txt"], "listing": [LISTING]}.get(
            failure, [POLICY_URL] if terms_only else [POLICY_URL, LISTING])
        if failure in ("503", "403", "listing"):
            for url in failing:
                session.pages[url] = Response(url, b"<html></html>",
                                              503 if failure == "listing" else int(failure))
        else:
            serve = session.request
            error = http.Timeout("synthetic") if failure == "timeout" else \
                http.ConnectionError("synthetic")

            def request(method, url, data, headers, **kwargs):
                if url in failing:
                    session.calls.append(url)
                    raise error
                return serve(method, url, data, headers, **kwargs)
            session.request = request
        adapter = functools.partial(JCGEnglishAdapter, session=session, sleeper=lambda _: None)
        before = set((state / "ledger").iterdir())
        with patch.dict(runner.DESKS, {"japan_jcg": ("jp_jcg", adapter, "shadow/japan-jcg")}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = runner.main([
                "--desk", "japan_jcg", "--state-dir", str(state), "--lookback-days", "9",
                "--cap", "20", "--run-id", run_id, "--event-name", "workflow_dispatch",
                "--run-attempt", "1", "--target-date", "2026-11-12"])
        [ledger] = set((state / "ledger").iterdir()) - before
        entry = json.loads(ledger.read_text())
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(git + ["add", "state"], check=True)
        subprocess.run(git + ["commit", "-qm", "attempt " + run_id], check=True)
        head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True).stdout.strip()
        if code == 0:  # the workflow signs links only after a successful collector step
            self.sign_links(head)
        return code, entry, head

    def test_an_outage_run_holds_the_queued_output_and_valid_evidence_resumes_it(self):
        one = FAMILY + ":" + IDENT
        state, queued = self.shared_processing(self.head)
        self.assertEqual([r["source_identity"] for r in queued["packet"]["records"]], [IDENT])
        output = state[one]["output"]
        calls = self.model.analyze_record.call_count
        # The terms page and listing both return 503. The collector records a
        # failed run (no shadow day) but exits 0, so the existing handoff runs:
        # the link bridge signs no new parent and shared processing re-signs.
        code, entry, lapsed = self.outage_run("89-1", failure="503")
        self.assertEqual(code, 0)
        self.assertEqual((entry["result"], entry["health"], entry["listing_report"]["site_terms"],
                          entry["jcg_source_outage_hold"], entry["inserted"]),
                         ("fetch_failure", "fail", "fetch_failure", True, 0))
        self.assertFalse((self.repo / "state/clock.json").exists())
        bridge = json.loads((self.handoff / links.LINKS_NAME).read_text())
        self.assertEqual(bridge["packet"]["links"], [])
        self.assertEqual(bridge["packet"]["source_evidence"],
                         {"site_terms": "fetch_failure", "listing": "fetch_failure"})
        state, envelope = self.shared_processing(lapsed)
        self.assertEqual((state[one]["status"], state[one]["held_from"], state[one]["reason"]),
                         ("held", "complete", "jcg_rights_policy_capture_failed"))
        self.assertEqual((envelope["packet"]["records"], envelope["packet"]["held"]), ([], [IDENT2]))
        self.assertEqual(self.model.analyze_record.call_count, calls)  # no model spend
        # The public Daily admits nothing from the previously queued envelope,
        # and the family's run-result row reports the outage, not a quiet day.
        receipt, public = self.public_daily()
        self.assertEqual((receipt["records"], public), (0, []))
        self.assertEqual(receipt["outcome"].status, "fetch_failure")
        self.assertTrue(receipt["outcome"].error_detail.startswith("jcg_site_terms_unavailable"))
        self.assertTrue(any("jcg_site_terms_unavailable" in e for e in self.errors))
        # Valid evidence returns: the unchanged item resumes without a model call.
        restored = self.collector_run("90-1", terms="ok")
        state, envelope = self.shared_processing(restored)
        self.assertEqual((state[one]["status"], state[one]["attempts"]), ("complete", 0))
        self.assertEqual(state[one]["output"]["summary"], output["summary"])
        self.assertEqual(self.model.analyze_record.call_count, calls)
        receipt, public = self.public_daily()
        self.assertEqual((receipt["records"], public), (1, [IDENT]))
        self.assertEqual(receipt["outcome"].status, "ok")

    def test_an_outage_keeps_already_public_records_and_reports_each_failure(self):
        self.shared_processing(self.head)
        self.assertEqual(self.public_daily()[1], [IDENT])
        with sqlite3.connect(str(self.db)) as conn:
            before = conn.execute("SELECT * FROM daily_machine_records").fetchall()
        for n, (failure, terms, status, refused) in enumerate((
                ("503", "fetch_failure", "fetch_failure", False),
                ("timeout", "timeout", "timeout", False),
                ("403", "auth_failure", "auth_failure", True),
                ("host", "not_reached", "fetch_failure", False))):
            with self.subTest(failure):
                code, entry, head = self.outage_run("8%d-1" % n, failure=failure)
                self.assertEqual((code, entry["health"], entry["listing_report"]["site_terms"]),
                                 (0, "fail", terms))
                _, envelope = self.shared_processing(head)
                self.assertNotIn(IDENT, envelope["packet"]["held"])  # nothing is withdrawn
                receipt, public = self.public_daily()
                self.assertEqual(public, [IDENT])
                self.assertEqual(receipt["outcome"].status, status)
                self.assertEqual(receipt["outcome"].error_detail.split(":")[0],
                                 "jcg_site_terms_access_refused" if refused
                                 else "jcg_site_terms_unavailable")
        with sqlite3.connect(str(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT * FROM daily_machine_records").fetchall(), before)

    def test_a_terms_page_refusal_alone_is_on_the_operator_report(self):
        one = FAMILY + ":" + IDENT
        self.shared_processing(self.head)
        code, entry, head = self.outage_run("89-1", failure="403", terms_only=True)
        self.assertEqual((code, entry["health"], entry["result"], entry["listing_report"]["site_terms"]),
                         (0, "ok", "ok_no_publications", "auth_failure"))
        self.assertNotIn("jcg_source_outage_hold", entry)
        state, _ = self.shared_processing(head)
        self.assertEqual(state[one]["reason"], "jcg_rights_policy_capture_failed")
        receipt, public = self.public_daily()
        self.assertEqual((public, receipt["outcome"].status), ([], "auth_failure"))
        self.assertEqual(receipt["outcome"].error_detail,
                         "jcg_site_terms_access_refused: site terms auth_failure, listing "
                         "ok_no_publications; queued outputs held, public records unchanged")

    def test_a_listing_failure_with_valid_terms_still_fails_the_collector(self):
        signed = (self.handoff / links.LINKS_NAME).read_text()
        # Terms captured, listing 503: not an outage hold. The collector step
        # fails as before, so the workflow neither signs nor re-processes.
        code, entry, _ = self.outage_run("89-1", failure="listing")
        self.assertEqual((code, entry["result"], entry["listing_report"]["site_terms"]),
                         (1, "fetch_failure", "ok"))
        self.assertNotIn("jcg_source_outage_hold", entry)
        self.assertEqual((self.handoff / links.LINKS_NAME).read_text(), signed)

    def test_failed_terms_capture_blocks_a_queued_output_and_valid_terms_resume_it(self):
        one, two = FAMILY + ":" + IDENT, FAMILY + ":" + IDENT2
        # The first model attempt fails QA, so the resumed item carries attempts.
        self.model.analyze_record.side_effect = [reading(summary_english="Too short."), reading()]

        # Run 1: valid terms. IDENT is retriable after one failed attempt;
        # IDENT2 is held for its own third-party prose and never reaches the model.
        state, envelope = self.shared_processing(self.head)
        self.assertEqual((state[one]["status"], state[one]["attempts"]), ("retriable", 1))
        self.assertEqual(state[two]["reason"], "jcg_rights_item_third_party_text")
        self.assertEqual(self.model.analyze_record.call_count, 1)

        # Run 2: valid terms; the retry succeeds and a signed output is queued
        # against the admitted parent. The public Daily has not run yet.
        state, queued = self.shared_processing(self.head)
        self.assertEqual((state[one]["status"], state[one]["attempts"]), ("complete", 1))
        self.assertEqual([r["source_identity"] for r in queued["packet"]["records"]], [IDENT])
        self.assertEqual(self.model.analyze_record.call_count, 2)
        output = state[one]["output"]

        # Transition 1: the next collector run fails the terms capture, and
        # shared processing runs on that pin before the public Daily.
        lapsed = self.collector_run("89-1", terms="fetch_failure")
        # The link-bridge step signs an empty set and exits 0, so the collector
        # workflow concludes success and triggers shared processing.
        bridge = json.loads((self.handoff / links.LINKS_NAME).read_text())
        self.assertEqual(bridge["packet"]["links"], [])
        state, envelope = self.shared_processing(lapsed)
        self.assertEqual(state[one], {**state[one], "status": "held", "held_from": "complete",
                                      "reason": "jcg_rights_policy_capture_failed",
                                      "attempts": 1, "output": output})
        self.assertEqual(state[two]["reason"], "jcg_rights_item_third_party_text")
        self.assertNotIn("held_from", state[two])
        self.assertEqual(envelope["packet"]["records"], [])
        self.assertEqual(envelope["packet"]["held"], [IDENT2])
        self.assertEqual(self.model.analyze_record.call_count, 2)
        # The fetched envelope is the re-signed one: the old output is gone
        # from it, and the public Daily admits nothing against the parent.
        receipt, public = self.public_daily()
        self.assertEqual((receipt["records"], public), (0, []))
        # The lapse persists while no later run captures valid terms.
        state, envelope = self.shared_processing(lapsed)
        self.assertEqual(state[one]["reason"], "jcg_rights_policy_capture_failed")
        self.assertEqual(self.public_daily()[1], [])

        # Transition 2: a later run captures the unchanged terms again. The
        # unchanged item resumes as it was: same attempts, same output, no
        # new model call. IDENT2's item-specific hold is not reopened.
        restored = self.collector_run("90-1", terms="ok")
        state, envelope = self.shared_processing(restored)
        self.assertEqual(state[one]["status"], "complete")
        self.assertEqual(state[one]["attempts"], 1)
        self.assertNotIn("held_from", state[one])
        self.assertNotIn("reason", state[one])
        self.assertEqual({k: v for k, v in state[one]["output"].items() if k != "policy_sha256"},
                         {k: v for k, v in output.items() if k != "policy_sha256"})
        self.assertEqual(self.model.analyze_record.call_count, 2)
        self.assertEqual(state[two]["reason"], "jcg_rights_item_third_party_text")
        self.assertEqual([r["source_identity"] for r in envelope["packet"]["records"]], [IDENT])
        self.assertEqual(envelope["packet"]["held"], [IDENT2])
        receipt, public = self.public_daily()
        self.assertEqual((receipt["records"], public), (1, [IDENT]))

    def test_a_retriable_item_resumes_with_its_attempts(self):
        one = FAMILY + ":" + IDENT
        # A retriable item with two failed attempts lapses and resumes retriable.
        self.model.analyze_record.side_effect = [reading(summary_english="Too short.")] * 2 + [reading()]
        self.shared_processing(self.head)
        state, _ = self.shared_processing(self.head)
        self.assertEqual((state[one]["status"], state[one]["attempts"]), ("retriable", 2))
        calls = self.model.analyze_record.call_count
        state, envelope = self.shared_processing(self.collector_run("89-1", terms="timeout"))
        self.assertEqual((state[one]["status"], state[one]["held_from"], state[one]["attempts"]),
                         ("held", "retriable", 2))
        self.assertEqual(self.model.analyze_record.call_count, calls)
        self.assertEqual(envelope["packet"]["records"], [])
        state, envelope = self.shared_processing(self.collector_run("90-1", terms="ok"))
        self.assertEqual(self.model.analyze_record.call_count, calls + 1)
        self.assertEqual((state[one]["status"], state[one]["attempts"]), ("complete", 2))

    def test_a_public_record_stays_public_through_a_lapse(self):
        self.shared_processing(self.head)
        self.assertEqual(self.public_daily()[1], [IDENT])
        _, envelope = self.shared_processing(self.collector_run("89-1", terms="fetch_failure"))
        self.assertNotIn(IDENT, envelope["packet"]["held"])
        self.assertEqual(self.public_daily()[1], [IDENT])

    def test_changed_terms_are_not_a_resumable_lapse(self):
        one = FAMILY + ":" + IDENT
        self.shared_processing(self.head)
        changed = self.collector_run("89-1", terms="ok",
                                     raw=policy_page(rights.POLICY_CLAUSES[1:]))
        state, envelope = self.shared_processing(changed)
        self.assertEqual(state[one]["reason"], "jcg_rights_policy_terms_changed_or_incomplete")
        self.assertNotIn("held_from", state[one])
        self.assertEqual(envelope["packet"]["held"], [IDENT, IDENT2])
        # Valid terms later do not resume it: a changed policy needs review.
        state, envelope = self.shared_processing(self.collector_run("90-1", terms="ok"))
        self.assertEqual(state[one]["reason"], "jcg_rights_policy_terms_changed_or_incomplete")
        self.assertEqual(envelope["packet"]["records"], [])


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
