"""
Desk-scoped relevance screening (processing/screening.py).

Singapore MINDEF releases were screened by the China Desk's two stages: a
keyword list of PLA vocabulary (with the US spelling "defense") and a model
prompt asking whether a Chinese-language article covers Chinese military
organisations. 13 of the 14 Singapore records screened by 2026-09-28 were
rejected by the model as "not Chinese military"; the 14th, an SAF discipline
notice, failed the keyword list.

These tests pin three things:

  * China screening is unchanged, byte for byte: the same prompt, the same
    system payload object, the same keyword verdicts. China's backlog order is
    unchanged; only the queue slots Singapore records used to take are freed.
  * Singapore is judged by its own declared scope, at both stages.
  * Singapore records run through the daily pipeline on their own path: the
    desk rubric, then one summary-and-flag call on the original English text,
    with no translation and no PLA taxonomy. They were held out of the daily
    queue from 2026-09-29 until that path existed; a desk without its own
    analysis is still held (tests/held_desk.py).

A mocked model cannot show that the Singapore rubric selects the right
releases; what it can show is that the rubric is what gets sent, and that a
verdict flows through unchanged. The fixtures are excerpts of stored records,
labelled from their text.
"""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "screening" /
     "desk_screening_records.json").read_text(encoding="utf-8"))
SG = {r["id"]: r for r in FIXTURES["singapore"]}
CN = {r["id"]: r for r in FIXTURES["china"]}

# Recorded on origin/main 89e48a2fe, before this change.
CHINA_MESSAGES_SHA256 = (
    "bb6581bae83d66373351ce41f789c0d9ace607ad2846dd9403826d0a39e8a443")
CHINA_SYSTEM_PAYLOAD_SHA256 = (
    "70437780cbe7d16922b1440e0c3f36721c091cc7f755157311945101409ffd69")
CHINA_SYSTEM_PROMPT_SHA256 = (
    "649ef54e1c6d7b8cc9cf8a0a057fff3507495643173bb879d8d037d7d80a2582")


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def article(rec: dict) -> dict:
    return {"url": rec["url"], "source_slug": rec["source_slug"],
            "title_original": rec["title_original"],
            "text_original": rec["text_original"]}


class FakeClient:
    """Records each messages.create call; answers with a scripted verdict."""

    def __init__(self, score=0.9, reasoning="scripted"):
        self.calls = []
        self.reply = json.dumps({"score": score, "reasoning": reasoning})
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text=self.reply)],
            stop_reason="end_turn", usage=None)


def fake_analyzer(client):
    from analysis.analyzer import Analyzer
    a = Analyzer.__new__(Analyzer)
    a._client = client
    return a


class TestChinaIsUnchanged(unittest.TestCase):

    def test_the_china_prompt_and_system_prompt_are_byte_identical(self):
        from analysis.analyzer import Analyzer
        from analysis.prompts import SYSTEM_PROMPT, build_relevance_messages
        self.assertEqual(_sha(build_relevance_messages("标题 T", "正文 B")),
                         CHINA_MESSAGES_SHA256)
        self.assertEqual(_sha(Analyzer._SYSTEM_WITH_CACHE),
                         CHINA_SYSTEM_PAYLOAD_SHA256)
        self.assertEqual(hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
                         CHINA_SYSTEM_PROMPT_SHA256)

    def test_every_china_source_and_an_unknown_one_get_the_china_profile(self):
        from processing.screening import CHINA_PROFILE, profile_for_source
        for slug in ("pla_daily", "mod_china", "xinhua_mil",
                     "global_times_mil", "china_mil_online",
                     "not_a_source", None):
            self.assertIs(profile_for_source(slug), CHINA_PROFILE, slug)

    def test_a_china_relevance_call_sends_what_it_always_sent(self):
        from analysis.analyzer import Analyzer
        from analysis.prompts import build_relevance_messages
        from processing.screening import CHINA_PROFILE
        rec = CN[4708]
        for profile in (None, CHINA_PROFILE):
            client = FakeClient()
            fake_analyzer(client).score_relevance(
                rec["title_original"], rec["text_original"], profile=profile)
            sent = client.calls[0]
            self.assertIs(sent["system"], Analyzer._SYSTEM_WITH_CACHE)
            self.assertEqual(sent["messages"], build_relevance_messages(
                rec["title_original"], rec["text_original"]))

    def test_china_keyword_verdicts_match_the_shared_keyword_filter(self):
        from processing.relevance import keyword_filter, passes_keyword_filter
        arts = [article(r) for r in CN.values()]
        passed, rejected = keyword_filter(arts)
        self.assertEqual([a["url"] for a in passed],
                         [a["url"] for a in arts if passes_keyword_filter(a)])
        # and the stored stage-1 outcome is reproduced
        self.assertEqual({a["url"] for a in rejected}, {CN[4719]["url"]})


class TestSingaporeIsJudgedByItsOwnScope(unittest.TestCase):

    def setUp(self):
        from processing.screening import profile_for_source
        self.profile = profile_for_source("sg_mindef_releases")

    def test_the_profile(self):
        self.assertEqual(self.profile.desk_id, "singapore")
        self.assertFalse(self.profile.keyword_prefilter)
        self.assertTrue(self.profile.daily_queue)
        self.assertFalse(self.profile.translates)

    def test_the_china_keyword_list_is_what_rejected_the_discipline_notice(self):
        from processing.relevance import keyword_filter, passes_keyword_filter
        notice = article(SG[4721])
        self.assertEqual(SG[4721]["stored_reasoning"], "failed keyword pre-filter")
        self.assertFalse(passes_keyword_filter(notice))
        passed, rejected = keyword_filter([article(r) for r in SG.values()])
        self.assertEqual(len(passed), len(SG))
        self.assertEqual(rejected, [])

    def test_the_prompt_carries_the_declared_scope_and_nothing_china_specific(self):
        from core.desk_registry import get_desk_registry
        scope = get_desk_registry().get("singapore").scope
        self.assertIn(scope, self.profile.system_prompt)
        rec = SG[4466]
        user = self.profile.build_messages(
            rec["title_original"], rec["text_original"])[0]["content"]
        text = self.profile.system_prompt + "\n" + user
        for china_only in ("Chinese-language article", "PLA, PAP, CCG",
                           "U.S. national security", "open-source intelligence",
                           "Chinese military or security topics"):
            self.assertNotIn(china_only, text)
        self.assertIn("Ministry of Defence (MINDEF)", user)
        self.assertIn(rec["title_original"], user)
        self.assertIn("neither required nor a reason to score higher", user)

    def test_a_singapore_call_sends_the_desk_prompt_and_its_own_system_prompt(self):
        from analysis.prompts import SYSTEM_PROMPT
        rec = SG[4425]
        client = FakeClient(score=0.92, reasoning="defence visit")
        score, reasoning = fake_analyzer(client).score_relevance(
            rec["title_original"], rec["text_original"], profile=self.profile)
        sent = client.calls[0]
        self.assertEqual(sent["system"], [{
            "type": "text", "text": self.profile.system_prompt,
            "cache_control": {"type": "ephemeral"}}])
        self.assertNotIn(SYSTEM_PROMPT, json.dumps(sent, ensure_ascii=False))
        self.assertEqual(sent["messages"], self.profile.build_messages(
            rec["title_original"], rec["text_original"]))
        self.assertEqual((score, reasoning), (0.92, "defence visit"))

    def test_the_fixtures_are_what_the_rubric_keys_on(self):
        """Labels come from the text; the relevant ones name defence matters."""
        for rid in (4466, 4472, 4425, 4426, 4721):
            rec = SG[rid]
            self.assertEqual(rec["label"], "relevant")
            text = (rec["title_original"] + " " + rec["text_original"]).lower()
            self.assertTrue(
                any(t in text for t in ("navy", "defence", "saf", "armed forces")),
                rid)
        self.assertEqual(SG[4631]["label"], "irrelevant")
        body = SG[4631]["text_original"].lower()
        self.assertIn("ageing", body)
        self.assertNotIn("saf", body.split())


class DeskClient:
    """
    A scripted model for the Singapore path. Answers the desk relevance call
    by the record's title and the desk analysis call with `analysis_reply`;
    any other call (a China prompt, a translation) fails the test.
    """

    def __init__(self, profile, scores, analysis_reply):
        self.profile = profile
        self.scores = scores
        self.analysis_reply = analysis_reply
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["system"][0]["text"]
        user = kwargs["messages"][0]["content"]
        if system == self.profile.system_prompt:
            title = next(t for t in self.scores if t in user)
            reply = json.dumps({"score": self.scores[title],
                                "reasoning": "scripted"})
        elif system == self.profile.analysis_system_prompt:
            reply = self.analysis_reply
        else:
            raise AssertionError("unexpected model call: %s" % system[:60])
        return SimpleNamespace(content=[SimpleNamespace(text=reply)],
                               stop_reason="end_turn", usage=None)


SUMMARY = json.dumps({
    "summary": "The RSN hosted a navy visit; MINDEF said it deepens ties.",
    "flag": False, "flag_reason": None})


class TestSingaporeRunsThroughTheDailyPipeline(unittest.TestCase):
    """Driven through the real pipeline.run() on a temporary database."""

    def setUp(self):
        from processing.screening import SINGAPORE_PROFILE
        from tests.integration.test_pipeline_run import PipelineRunCase
        self.profile = SINGAPORE_PROFILE
        self.case = PipelineRunCase("run")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        # A first offline run creates the source rows from the manifests.
        from tests.integration.test_pipeline_run import scraper_factory
        self.case.run_pipeline({"china_mil_online": scraper_factory(urls=[])})

    def seed(self, records):
        con = sqlite3.connect(str(self.case.db_path))
        sid = con.execute("SELECT id FROM sources WHERE slug=?",
                          ("sg_mindef_releases",)).fetchone()[0]
        for rec in records:
            con.execute(
                "INSERT INTO articles (source_id, url, title_original, "
                "text_original, published_date, content_hash, scraped_at) "
                "VALUES (?,?,?,?,?,?,datetime('now'))",
                (sid, rec["url"], rec["title_original"], rec["text_original"],
                 "2026-09-05", rec["url"]))
        con.commit()
        con.close()

    def run_with(self, client, exit_code=None):
        from unittest import mock
        from tests.integration.test_pipeline_run import scraper_factory
        analyzer = fake_analyzer(client)
        with mock.patch.object(self.case.pipeline, "ANTHROPIC_API_KEY", "test-key"), \
                mock.patch("analysis.analyzer.Analyzer", return_value=analyzer), \
                self.assertLogs("pipeline", level="INFO") as logs:
            try:
                self.case.run_pipeline(
                    {"china_mil_online": scraper_factory(urls=[])},
                    no_analysis=False)
            except SystemExit as exc:
                self.assertEqual(exc.code, exit_code)
            else:
                self.assertIsNone(exit_code)
        return "\n".join(logs.output)

    def rows(self):
        con = sqlite3.connect(str(self.case.db_path))
        con.row_factory = sqlite3.Row
        try:
            return {r["url"]: dict(r) for r in con.execute(
                "SELECT a.*, (SELECT count(*) FROM article_categories c "
                "             WHERE c.article_id = a.id) AS n_categories "
                "FROM articles a")}
        finally:
            con.close()

    def test_a_pass_is_summarised_in_english_and_a_reject_is_recorded(self):
        self.seed([SG[4466], SG[4631]])
        client = DeskClient(self.profile, {SG[4466]["title_original"]: 0.92,
                                           SG[4631]["title_original"]: 0.10},
                            SUMMARY)
        log = self.run_with(client)
        self.assertNotIn("Held out of the daily analysis queue", log)
        self.assertIn("0/0 new + 2/2 backlog", log)

        # Two relevance calls on the desk rubric and one analysis call: no
        # China prompt, no translation, no category call.
        systems = [c["system"][0]["text"] for c in client.calls]
        self.assertEqual(sorted(systems), sorted([
            self.profile.system_prompt, self.profile.system_prompt,
            self.profile.analysis_system_prompt]))
        analysis = [c for c in client.calls
                    if c["system"][0]["text"] == self.profile.analysis_system_prompt]
        self.assertEqual(analysis[0]["messages"], self.profile.build_analysis_messages(
            SG[4466]["title_original"], SG[4466]["text_original"]))

        rows = self.rows()
        passed, rejected = rows[SG[4466]["url"]], rows[SG[4631]["url"]]
        self.assertEqual(passed["passed_relevance"], 1)
        self.assertIsNotNone(passed["analyzed_at"])
        self.assertIsNone(passed["title_english"])
        self.assertIsNone(passed["text_english"])
        self.assertEqual(passed["summary_english"],
                         json.loads(SUMMARY)["summary"])
        self.assertEqual(passed["is_significant"], 0)
        self.assertIsNone(passed["significance_reasoning"])
        self.assertEqual(passed["prompt_version"], "sg-relevance-v1+sg-analysis-v1")
        self.assertEqual(passed["n_categories"], 0)
        self.assertEqual(rejected["passed_relevance"], 0)
        self.assertIsNone(rejected["analyzed_at"])
        self.assertIsNone(rejected["summary_english"])

    def test_a_failed_analysis_writes_nothing_and_is_retried_once(self):
        self.seed([SG[4466]])
        bad = DeskClient(self.profile, {SG[4466]["title_original"]: 0.92},
                         json.dumps({"summary": "", "flag": False}))
        # A run whose whole queue fails analysis exits non-zero and writes no
        # success marker, so a later cron window retries it.
        log = self.run_with(bad, exit_code=2)
        self.assertIn("passed relevance but produced no summary", log)
        self.assertIn("FATAL: 1 article(s) passed relevance but none produced", log)
        row = self.rows()[SG[4466]["url"]]
        self.assertEqual(row["passed_relevance"], 1)
        self.assertIsNone(row["analyzed_at"])
        self.assertIsNone(row["summary_english"])

        # The next run takes it as pending analysis and completes it.
        good = DeskClient(self.profile, {SG[4466]["title_original"]: 0.92},
                          SUMMARY)
        log = self.run_with(good)
        self.assertIn("0/0 new + 1/1 backlog", log)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[SG[4466]["url"]]
        self.assertIsNotNone(row["analyzed_at"])
        self.assertEqual(row["summary_english"], json.loads(SUMMARY)["summary"])

        # A third run has nothing left to do for it.
        idle = DeskClient(self.profile, {}, SUMMARY)
        self.run_with(idle)
        self.assertEqual(idle.calls, [])
        self.assertEqual(self.rows()[SG[4466]["url"]]["analyzed_at"],
                         row["analyzed_at"])

    def test_a_desk_without_its_own_analysis_is_still_held(self):
        # Singapore as it stood before its analysis path: the run re-syncs
        # each source's desk from the manifests, so the profile is swapped.
        from dataclasses import replace
        from unittest import mock
        from processing import screening
        from tests.held_desk import HELD_PROFILE
        held = replace(HELD_PROFILE, desk_id="singapore")
        patcher = mock.patch.dict(screening._PROFILES, {"singapore": held})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.seed([SG[4466]])
        client = DeskClient(self.profile, {}, SUMMARY)
        log = self.run_with(client)
        self.assertIn("Held out of the daily analysis queue: 1 singapore-desk", log)
        self.assertEqual(client.calls, [])
        self.assertIsNone(self.rows()[SG[4466]["url"]]["passed_relevance"])


class TestDeskAnalysisValidation(unittest.TestCase):
    """A paid response without a usable summary and flag writes nothing."""

    def analyse(self, reply, score=0.9):
        from processing.screening import SINGAPORE_PROFILE
        rec = SG[4466]
        client = DeskClient(SINGAPORE_PROFILE, {rec["title_original"]: score},
                            reply)
        result = fake_analyzer(client).analyze_record(
            rec["title_original"], rec["text_original"], SINGAPORE_PROFILE)
        return result, client

    def test_invalid_replies_leave_a_partial_result(self):
        for reply in ("not json",
                      json.dumps({"summary": "   ", "flag": False}),
                      json.dumps({"summary": "S.", "flag": "no"}),
                      json.dumps({"summary": "S."}),
                      json.dumps({"summary": "S.", "flag": True}),
                      json.dumps({"summary": "S.", "flag": True,
                                  "flag_reason": " "}),
                      json.dumps(["S."])):
            result, _ = self.analyse(reply)
            self.assertTrue(result["passed_relevance"], reply)
            self.assertNotIn("summary_english", result, reply)
            self.assertFalse(result["requires_translation"], reply)

    def test_a_flag_carries_its_reason_and_an_unflagged_reason_is_dropped(self):
        flagged, _ = self.analyse(json.dumps(
            {"summary": "S.", "flag": True, "flag_reason": "New acquisition."}))
        self.assertEqual(
            (flagged["is_significant"], flagged["significance_reasoning"]),
            (True, "New acquisition."))
        plain, _ = self.analyse(json.dumps(
            {"summary": "S.", "flag": False, "flag_reason": "ignored"}))
        self.assertEqual(
            (plain["is_significant"], plain["significance_reasoning"]),
            (False, None))

    def test_a_reject_makes_no_analysis_call(self):
        result, client = self.analyse(SUMMARY, score=0.2)
        self.assertFalse(result["passed_relevance"])
        self.assertNotIn("summary_english", result)
        self.assertEqual(len(client.calls), 1)

    def test_china_records_still_take_the_china_path(self):
        from processing.screening import CHINA_PROFILE
        a = fake_analyzer(FakeClient())
        seen = []
        a.analyze = lambda t, b: seen.append((t, b)) or "china"
        for profile in (None, CHINA_PROFILE):
            self.assertEqual(a.analyze_record("t", "b", profile), "china")
        self.assertEqual(seen, [("t", "b"), ("t", "b")])


class TestBackfillsKeepToTheChinaPath(unittest.TestCase):
    """
    Both backfill scripts run the China path (relevance, then translation
    from Chinese); Singapore drains through the daily pipeline instead.
    """

    def test_singapore_records_are_not_offered_to_the_unscored_backfill(self):
        import scripts.backfill_unscored as bf
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "b.db"
            con = sqlite3.connect(str(db))
            con.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
                CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER,
                    url TEXT, title_original TEXT, text_original TEXT,
                    published_date TEXT, passed_relevance INTEGER);
                INSERT INTO sources VALUES (1,'pla_daily','china'),
                                           (6,'sg_mindef_releases','singapore');
                INSERT INTO articles VALUES
                    (1,1,'u1','t','b','2026-09-05',NULL),
                    (2,6,'u2','t','b','2026-09-05',NULL),
                    (3,1,'u3','t','b','2026-09-05',NULL);
            """)
            con.commit()
            con.close()
            saved, bf.DB_PATH = bf.DB_PATH, db
            try:
                self.assertEqual([r["id"] for r in bf.fetch_unscored()], [1, 3])
                self.assertEqual([r["id"] for r in bf.fetch_unscored(limit=1)], [1])
            finally:
                bf.DB_PATH = saved

    def test_a_singapore_pass_is_never_offered_for_translation(self):
        import scripts.backfill_translations as bt
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            con = sqlite3.connect(str(db))
            con.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
                CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER,
                    title_original TEXT, text_original TEXT,
                    title_english TEXT, passed_relevance INTEGER);
                INSERT INTO sources VALUES (1,'pla_daily','china'),
                                           (6,'sg_mindef_releases','singapore');
                INSERT INTO articles VALUES
                    (1,1,'t','body',NULL,1),
                    (2,6,'t','a longer body',NULL,1),
                    (3,1,'t','b','T',1);
            """)
            con.commit()
            con.close()
            saved, bt.DB_PATH = bt.DB_PATH, db
            try:
                self.assertEqual([r["id"] for r in bt.fetch_stuck()], [1])
            finally:
                bt.DB_PATH = saved


class TestRescreenPlanAndProposal(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "snap.db"
        con = sqlite3.connect(str(self.db))
        con.executescript("""
            CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT, desk_id TEXT);
            CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id INTEGER,
                url TEXT, title_original TEXT, text_original TEXT,
                published_date TEXT, passed_relevance INTEGER,
                relevance_score REAL, relevance_reasoning TEXT,
                processing_state TEXT);
            INSERT INTO sources VALUES (1,'pla_daily','china'),
                                       (6,'sg_mindef_releases','singapore');
        """)
        rows = [
            (4466, 6, None, None, None),
            (4425, 6, 0, 0.4, SG[4425]["stored_reasoning"]),
            (4721, 6, 0, 0.0, "failed keyword pre-filter"),
            (4631, 6, 0, 0.0, SG[4631]["stored_reasoning"]),
            (4708, 1, None, None, None),
        ]
        for rid, sid, passed, score, why in rows:
            rec = SG.get(rid) or CN[rid]
            con.execute(
                "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                (rid, sid, rec["url"], rec["title_original"],
                 rec["text_original"], "2026-09-05", passed, score, why))
        con.commit()
        con.close()
        self.digest = hashlib.sha256(self.db.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_plan_lists_the_desk_records_by_stage_and_prices_them(self):
        from scripts.rescreen_desk import build_plan
        plan = build_plan(self.db, "singapore")
        self.assertEqual(plan["affected_ids"], [4425, 4466, 4631, 4721])
        self.assertEqual(plan["counts"], {"rejected_keyword": 1,
                                          "rejected_model": 2, "unscreened": 1})
        est = plan["estimate"]
        self.assertEqual(est["records"], 4)
        self.assertGreater(est["usd_ceiling"], est["usd_typical"])
        self.assertEqual(plan["db_sha256"], self.digest)

    def test_a_proposal_scores_relevance_only_and_writes_nothing(self):
        from scripts.rescreen_desk import build_proposal

        class ScriptedAnalyzer:
            calls = []

            def score_relevance(self, title, body, profile=None):
                self.calls.append(profile.desk_id)
                return (0.1, "not defence") if "ageing" in body else (0.9, "defence")

            def analyze(self, *a, **k):
                raise AssertionError("a proposal must never run full analysis")

        an = ScriptedAnalyzer()
        prop = build_proposal(self.db, "singapore", [4425, 4631], an)
        self.assertEqual(an.calls, ["singapore", "singapore"])
        verdicts = {r["id"]: r["proposed"]["passes_threshold"] for r in prop["records"]}
        self.assertEqual(verdicts, {4425: True, 4631: False})
        self.assertFalse(prop["applied"])
        self.assertEqual(prop["records"][0]["stored"]["stage"], "rejected_model")
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),
                         self.digest)

    def test_a_proposal_refuses_records_from_another_desk(self):
        from scripts.rescreen_desk import build_proposal
        with self.assertRaises(SystemExit):
            build_proposal(self.db, "singapore", [4708], object())


if __name__ == "__main__":
    unittest.main()
