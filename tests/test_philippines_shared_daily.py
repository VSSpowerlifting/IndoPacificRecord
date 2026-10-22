"""Synthetic offline contracts; no source access, paid calls or publication."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from processing import daily_intake as d
from processing.screening import PHILIPPINES_PROFILE, UNSUPPORTED_PROFILE, profile_for_source, profile_for_desk


def policy():
    p = d.load_policy()
    p["sources"]["ph_afp_articles"].update(private_model_processing=True,
        public_machine_explanation=True, unattended_release=True,
        owner_decision="synthetic test policy only")
    return p


def record():
    body = "A routine exercise is planned for 23 October. The announcement does not establish that training has taken place."
    return dict(source_family="ph_afp_articles", source_identity="afp:1",
        metadata_version_sha256="a" * 64, content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        capture_sha256="b" * 64, source_git_commit="c" * 40, source_run="123-1",
        title="Synthetic source fixture", body=body,
        canonical_official_url="https://www.afp.mil.ph/news/synthetic-test",
        publisher_posted_date="2026-10-19", official_issuer="ph_afp",
        official_publisher="ph_afp", official_republisher=None, first_seen_run="123-1")


def reading():
    first = "AFP reports an exercise planned for 23 October."
    second = "AFP describes planned activity without reporting its outcome."
    return dict(passed_relevance=True, requires_translation=False,
        summary_english=first + " " + second,
        facts=[dict(sentence=first, evidence="A routine exercise is planned for 23 October."),
               dict(sentence=second, evidence="The announcement does not establish that training has taken place.")],
        is_significant=False, categories=["exercises"], significance_reasoning=None,
        model_id="synthetic-model", prompt_version="ph-relevance-v1+ph-analysis-v10")


def fake_analyzer(reply=None):
    a = Mock()
    a.analyze_record.return_value = reading() if reply is None else reply
    a.usage.rows.return_value = []
    return a


class SharedDaily(unittest.TestCase):
    def test_geographic_topic_requires_explicit_source_support(self):
        r = record()
        reading = fake_analyzer().analyze_record(r["title"], r["body"], None)
        reading["categories"] = ["south_china_sea"]
        with self.assertRaisesRegex(d.IntakeHold, "daily_topic_unsupported"):
            d.quality_check(r, reading)
        r["body"] += " The source also names the West Philippine Sea."
        d.quality_check(r, reading)

    def test_explicit_profiles_and_fail_closed_fallback(self):
        for slug in d.REFS:
            self.assertIs(profile_for_source(slug), PHILIPPINES_PROFILE)
        for slug in ("unknown-source", None):
            self.assertIs(profile_for_source(slug), UNSUPPORTED_PROFILE)
        for desk in (None, "unknown", "vietnam"):
            self.assertIs(profile_for_desk(desk), UNSUPPORTED_PROFILE)
        self.assertEqual(profile_for_desk("korea").desk_id, "korea")
        self.assertFalse(profile_for_desk("korea").daily_queue)
        self.assertFalse(PHILIPPINES_PROFILE.translates)
        self.assertFalse(PHILIPPINES_PROFILE.daily_queue)

    def test_real_shared_analyzer_routes_english_without_translation(self):
        from analysis.analyzer import Analyzer
        a = Analyzer.__new__(Analyzer)
        r = reading()
        reply = dict(summary=r["summary_english"], flag=False, flag_reason=None,
                     categories=r["categories"], facts=r["facts"], flag_evidence=None)
        with patch.object(a, "_call", side_effect=[json.dumps(dict(score=.9, reasoning="Synthetic relevance.")), json.dumps(reply)]) as call, \
             patch.object(a, "translate", side_effect=AssertionError("translation prohibited")), \
             patch.object(a, "categorize", side_effect=AssertionError("China categories prohibited")):
            result = a.analyze_record(record()["title"], record()["body"], PHILIPPINES_PROFILE)
        self.assertEqual(result["categories"], ["exercises"])
        self.assertEqual(result["facts"], r["facts"])
        self.assertFalse(result["requires_translation"])
        self.assertIn("Philippines", call.call_args_list[0].kwargs["system"][0]["text"])
        self.assertIsNone(result["text_english"])

    def test_passage_references_supply_exact_original_evidence(self):
        from analysis.analyzer import Analyzer
        from analysis.philippines_prompts import analysis_messages, evidence_passages
        item = record()
        passages = evidence_passages(item["body"])
        self.assertEqual(len(passages), 1)
        self.assertEqual(passages[0][1], item["body"])
        self.assertIn('"passages"', analysis_messages(item["title"], item["body"])[0]["content"])
        source_reply = reading()
        reply = dict(summary=source_reply["summary_english"], flag=False,
                     flag_reason=None, flag_evidence_id=None,
                     categories=source_reply["categories"],
                     facts=[{"sentence": f["sentence"], "evidence_id": "P1"}
                            for f in source_reply["facts"]])
        a = Analyzer.__new__(Analyzer)
        with patch.object(a, "_call", side_effect=[
                json.dumps(dict(score=.9, reasoning="Synthetic relevance.")),
                json.dumps(reply)]):
            result = a.analyze_record(item["title"], item["body"], PHILIPPINES_PROFILE)
        self.assertEqual([f["evidence"] for f in result["facts"]], [item["body"]] * 2)
        self.assertNotIn("evidence_id", json.dumps(result))
        self.assertTrue(d.quality_check(item, result))

    def test_unknown_passage_reference_fails_closed(self):
        from analysis.analyzer import Analyzer
        source_reply = reading()
        reply = dict(summary=source_reply["summary_english"], flag=False,
                     flag_reason=None, flag_evidence_id=None,
                     categories=source_reply["categories"],
                     facts=[{"sentence": f["sentence"], "evidence_id": "P999"}
                            for f in source_reply["facts"]])
        a = Analyzer.__new__(Analyzer)
        a._usage = Mock()  # usage is a read-only property on Analyzer
        with patch.object(a, "_call", side_effect=[
                json.dumps(dict(score=.9, reasoning="Synthetic relevance.")),
                json.dumps(reply)]):
            result = a.analyze_record(record()["title"], record()["body"],
                                      PHILIPPINES_PROFILE)
        self.assertTrue(result["passed_relevance"])
        self.assertNotIn("summary_english", result)
        a.usage.mark_failed.assert_called_once()

    def test_long_paragraph_windows_are_exact_bounded_original_spans(self):
        from analysis.philippines_prompts import evidence_passages
        body = ("A source describes planned maritime security cooperation and "
                "emphasizes that no delivery has occurred. " * 20)
        passages = evidence_passages(body)
        self.assertGreater(len(passages), 2)
        self.assertEqual([ref for ref, _ in passages],
                         ["P" + str(i + 1) for i in range(len(passages))])
        self.assertTrue(all(20 <= len(span) <= 480 and span in body
                            for _, span in passages))

    def test_version_twelve_requests_short_original_paraphrases(self):
        from analysis.philippines_prompts import analysis_messages
        from processing.screening import PHILIPPINES_PROFILE
        prompt = analysis_messages(record()["title"], record()["body"])[0]["content"]
        self.assertEqual(PHILIPPINES_PROFILE.analysis_prompt_version, "ph-analysis-v12")
        self.assertIn("8–11 words each", prompt)
        self.assertIn("at most 11 words", prompt)
        self.assertIn("rephrase facts", prompt)

    def test_version_twelve_preserves_legacy_public_outputs(self):
        for version in ("ph-relevance-v1+ph-analysis-v10",
                        "ph-relevance-v1+ph-analysis-v11",
                        "ph-relevance-v1+ph-analysis-v12"):
            good = reading()
            good["prompt_version"] = version
            state, _ = d.process([record()], {}, family="ph_afp_articles",
                                 policy=policy(),
                                 analyzer_factory=lambda: fake_analyzer(good))
            self.assertEqual(state["ph_afp_articles:afp:1"]["status"], "complete")
            signed = d.sign_outputs(state, family="ph_afp_articles",
                                    policy=policy(), key="synthetic-key-" * 4)
            self.assertEqual(signed["packet"]["records"][0]["prompt_version"],
                             version)

    def test_unsupported_profile_never_dispatches(self):
        from analysis.analyzer import Analyzer, AnalysisError
        a = Analyzer.__new__(Analyzer)
        with patch.object(a, "analyze") as call:
            with self.assertRaises(AnalysisError):
                a.analyze_record("x", "y", UNSUPPORTED_PROFILE)
        call.assert_not_called()

    def test_legacy_relevance_helper_cannot_bypass_private_intake(self):
        from processing.relevance import llm_relevance_check
        a = Mock()
        for slug in (*d.REFS, "unknown-source"):
            result = llm_relevance_check([dict(source_slug=slug, title_original="x", text_original="y")], a)
            self.assertEqual(result[0][1], 0.0)
        a.score_relevance.assert_not_called()

    def test_default_rights_stop_before_analyzer_construction(self):
        factory = Mock(side_effect=AssertionError("paid call"))
        p = policy(); p["sources"]["ph_afp_articles"]["private_model_processing"] = False
        state, usage = d.process([record()], {}, family="ph_afp_articles", policy=p, analyzer_factory=factory)
        self.assertEqual(state["ph_afp_articles:afp:1"]["reason"], "model_rights_held")
        self.assertEqual(usage, [])
        factory.assert_not_called()

    def test_owner_excluded_trial_never_processes_or_signs(self):
        r = record(); r["source_identity"] = "afp:1418"
        factory = Mock(side_effect=AssertionError("excluded paid call"))
        state, usage = d.process([r], {}, family="ph_afp_articles", policy=policy(), analyzer_factory=factory)
        self.assertEqual(state["ph_afp_articles:afp:1418"]["reason"], "owner_excluded_source_identity")
        self.assertEqual(usage, [])
        factory.assert_not_called()
        envelope = d.sign_outputs(state, family="ph_afp_articles", policy=policy(), key="k"*32)
        self.assertEqual(envelope["packet"]["records"], [])

    def test_shared_private_model_guard_bounds_calls_and_cost(self):
        from config import RELEVANCE_MODEL
        p = policy()["sources"]["ph_afp_articles"]
        a = Mock(); underlying = a._call
        d.bound_private_calls(a, p)
        a._call([], task="relevance", model=RELEVANCE_MODEL, max_tokens=500)
        a._call([], task="summary", max_tokens=2200)
        with self.assertRaisesRegex(d.IntakeHold, "call_bound"):
            a._call([], task="summary", max_tokens=2200)
        self.assertEqual(underlying.call_count, 2)
        a = Mock(); client = a._client; underlying = a._call
        d.bound_private_calls(a, p)
        client.with_options.assert_called_once_with(max_retries=0)
        with self.assertRaisesRegex(d.IntakeHold, "spend_bound"):
            a._call([{"content": "x"*400000}], task="relevance", model=RELEVANCE_MODEL, max_tokens=500)
        underlying.assert_not_called()

    def test_afp_standing_rights_do_not_cover_republished_material(self):
        r = record(); r["official_republisher"] = "third_party"
        factory = Mock(side_effect=AssertionError("rights-held paid call"))
        state, _ = d.process([r], {}, family="ph_afp_articles", policy=policy(), analyzer_factory=factory)
        self.assertEqual(state["ph_afp_articles:afp:1"]["reason"], "source_rights_not_first_party")
        factory.assert_not_called()

    def test_ninety_word_limit_includes_flag_explanation(self):
        r = reading()
        r.update(is_significant=True, significance_reasoning="AFP " + "word "*90)
        with self.assertRaisesRegex(d.IntakeHold, "explanation_word_limit"):
            d.quality_check(record(), r)

    def test_numeric_evidence_ignores_sentence_punctuation_but_not_value(self):
        source = "An exercise is planned for 23 October 2026 and involves 125 specialists."
        item = record(); item.update(body=source, content_sha256=hashlib.sha256(source.encode()).hexdigest())
        r = reading()
        first = "AFP reports an exercise planned for 23 October 2026."
        second = "AFP describes plans involving 125 specialists."
        r.update(summary_english=first + " " + second,
                 facts=[dict(sentence=s, evidence=source) for s in (first, second)])
        self.assertTrue(d.quality_check(item, r))
        second = second.replace("125", "25")
        r.update(summary_english=first + " " + second,
                 facts=[dict(sentence=s, evidence=source) for s in (first, second)])
        with self.assertRaisesRegex(d.IntakeHold, "quantity_or_date_unsupported"):
            d.quality_check(item, r)

    def test_quiet_nsc_is_a_noop(self):
        state, usage = d.process([], {}, family="ph_nsc_official_statements", policy=d.load_policy())
        self.assertEqual((state, usage), ({}, []))

    def test_passing_machine_record_is_unattended_and_replayable(self):
        a = fake_analyzer()
        state, _ = d.process([record()], {}, family="ph_afp_articles", policy=policy(), analyzer_factory=lambda: a)
        self.assertEqual(state["ph_afp_articles:afp:1"]["status"], "complete")
        replay, _ = d.process([record()], state, family="ph_afp_articles", policy=policy(), analyzer_factory=lambda: a)
        self.assertEqual(state, replay)
        self.assertEqual(a.analyze_record.call_count, 1)
        serialized = json.dumps(state)
        self.assertNotIn(record()["body"], serialized)
        self.assertNotIn(record()["title"], serialized)
        self.assertNotIn('"facts"', serialized)

    def test_revision_holds_without_paid_calls(self):
        state, _ = d.process([record()], {}, family="ph_afp_articles", policy=policy(), analyzer_factory=fake_analyzer)
        r = record(); r["content_sha256"] = "e" * 64
        factory = Mock(side_effect=AssertionError("paid call"))
        state, _ = d.process([r], state, family="ph_afp_articles", policy=policy(), analyzer_factory=factory)
        self.assertEqual(state["ph_afp_articles:afp:1"]["reason"], "source_version_changed")

    def test_missing_source_withdraws_only_affected_output(self):
        p = policy()
        state, _ = d.process([record()], {}, family="ph_afp_articles", policy=p, analyzer_factory=fake_analyzer)
        state, _ = d.process([], state, family="ph_afp_articles", policy=p)
        envelope = d.sign_outputs(state, family="ph_afp_articles", policy=p, key="synthetic-key-"*4)
        self.assertEqual(envelope["packet"]["records"], [])
        self.assertEqual(envelope["packet"]["held"], ["afp:1"])

    def test_failed_analysis_retries_then_pauses_reversibly(self):
        from analysis.analyzer import AnalysisError
        a = fake_analyzer(); a.analyze_record.side_effect = AnalysisError("synthetic failure")
        state = {}
        for _ in range(8):
            state, _ = d.process([record()], state, family="ph_afp_articles", policy=policy(), analyzer_factory=lambda: a)
        self.assertEqual(a.analyze_record.call_count, 5)
        self.assertEqual(state["ph_afp_articles:afp:1"]["status"], "paused")
        d.resume(state, "ph_afp_articles:afp:1")
        self.assertEqual(state["ph_afp_articles:afp:1"]["attempts"], 0)
        self.assertEqual(state["ph_afp_articles:afp:1"]["status"], "pending")

    def test_item_failure_does_not_block_next_record_and_cap_is_bounded(self):
        p = policy(); p["sources"]["ph_afp_articles"]["max_records_per_run"] = 2
        bad = reading(); bad["summary_english"] = ""
        a = fake_analyzer(); a.analyze_record.side_effect = [bad, reading()]
        r2 = record(); r2["source_identity"] = "afp:2"
        r3 = record(); r3["source_identity"] = "afp:3"
        state, _ = d.process([record(), r2, r3], {}, family="ph_afp_articles", policy=p, analyzer_factory=lambda: a)
        self.assertEqual(state["ph_afp_articles:afp:1"]["status"], "retriable")
        self.assertEqual(state["ph_afp_articles:afp:2"]["status"], "complete")
        self.assertEqual(state["ph_afp_articles:afp:3"]["status"], "pending")

    def test_quality_rejects_unsupported_facts_and_incomplete_analysis(self):
        changes = [dict(requires_translation=True), dict(facts=[]), dict(categories=["political_work"])]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(d.IntakeHold):
                d.quality_check(record(), {**reading(), **change})
        for old, new in (("23", "24"), ("planned", "delivered"), ("AFP", "NSC")):
            r = reading(); r["summary_english"] = r["summary_english"].replace(old,new)
            for fact in r["facts"]: fact["sentence"] = fact["sentence"].replace(old,new)
            with self.subTest(new=new), self.assertRaises(d.IntakeHold):
                d.quality_check(record(), r)

    def test_signed_intake_rights_version_and_no_originals(self):
        from migrations.versions.m0015_daily_machine_records import up
        from core.regional_official_link_release import SCHEMA_SQL
        p = policy(); key = "synthetic-test-key-" * 3
        state, _ = d.process([record()], {}, family="ph_afp_articles", policy=p, analyzer_factory=fake_analyzer)
        envelope = d.sign_outputs(state, family="ph_afp_articles", policy=p, key=key)
        conn = sqlite3.connect(":memory:"); conn.executescript(SCHEMA_SQL); up(conn)
        r = record()
        conn.execute("INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            r["source_family"], r["source_identity"], "philippines", r["canonical_official_url"],
            r["publisher_posted_date"], "ph_afp", "ph_afp", None, "c"*40, "a"*64, "123-1",
            "official_link_only", "d"*64, "2026-10-19T00:00:00Z"))
        conn.commit()
        for badkey in ("x"*32, ""):
            with self.assertRaises(d.IntakeHold): d.admit(conn,envelope,family="ph_afp_articles",policy=p,key=badkey)
        denied = copy.deepcopy(p)
        denied["sources"]["ph_afp_articles"]["public_machine_explanation"] = False
        with self.assertRaises(d.IntakeHold):
            d.admit(conn,envelope,family="ph_afp_articles",policy=denied,key=key)
        with self.assertRaises(d.IntakeHold):
            d.admit(conn,envelope,family="ph_nsc_official_statements",policy=p,key=key)
        self.assertEqual(d.admit(conn,envelope,family="ph_afp_articles",policy=p,key=key)["admitted"],1)
        self.assertEqual(d.admit(conn,envelope,family="ph_afp_articles",policy=p,key=key)["admitted"],0)
        bad = copy.deepcopy(envelope); bad["packet"]["records"][0]["body"] = "restricted"
        with self.assertRaises(d.IntakeHold): d.admit(conn,bad,family="ph_afp_articles",policy=p,key=key)
        self.assertEqual(conn.execute("SELECT count(*) FROM daily_machine_records").fetchone()[0],1)
        withdrawn, _ = d.process([], state, family="ph_afp_articles", policy=p)
        hold = d.sign_outputs(withdrawn, family="ph_afp_articles", policy=p, key=key)
        d.admit(conn, hold, family="ph_afp_articles", policy=p, key=key)
        d.admit(conn, envelope, family="ph_afp_articles", policy=p, key=key)
        self.assertEqual(conn.execute("SELECT publication_state FROM daily_machine_records").fetchone()[0], "held")
        conn.close()

    def test_public_intake_isolates_bad_family_envelope(self):
        from processing.daily_runner import public_intake
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "ph_nsc_official_statements.json").write_text('{"packet":null,"mac":"bad"}')
            result = public_intake(Path(tmp) / "scratch.db", tmp)
        self.assertIn("ph_nsc_official_statements", result)
        self.assertNotIn("ph_afp_articles", result)

    def test_disabled_fetch_never_calls_private_api(self):
        from scripts.fetch_daily_machine_outputs import main
        with patch.dict("os.environ", {"IPR_PRIVATE_DAILY_ENABLED": "false"}), patch("subprocess.run") as call:
            main()
        call.assert_not_called()

    def test_machine_record_uses_existing_template_without_publisher_originals(self):
        # Exercises the production machine partial without a DB or paid call.
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        env = Environment(loader=FileSystemLoader(d.ROOT / "site/preview/templates"),
                          autoescape=select_autoescape(['html']))
        # The full shared template has registered filters; reuse the real env
        # created by build in the production compatibility suite. Here the
        # included machine projection alone proves the non-disclosure surface.
        html = env.get_template('_machine_explanation.html').render(record=dict(
            source_label='AFP', source_identity='afp:1', summary=reading()['summary_english'],
            model_flagged=False, publisher='ph_afp', published_date='2026-10-19',
            url=record()['canonical_official_url'], source_git_commit='c'*40,
            content_sha256=record()['content_sha256'], source_run='123-1',
            model_id='synthetic-model', prompt_version='ph-relevance-v1+ph-analysis-v10'))
        self.assertIn('Machine summary', html)
        self.assertNotIn(record()['body'], html)
        self.assertNotIn(record()['title'], html)
        self.assertIn('No translation was needed', html)


from tests.test_reconcile import ReconcileCase, migrate


class MachineRecordReconciliation(ReconcileCase):
    """A concurrent main update must preserve the local Daily publication."""

    def setUp(self):
        super().setUp()
        self.p = policy()
        state, _ = d.process([record()], {}, family="ph_afp_articles", policy=self.p,
                             analyzer_factory=fake_analyzer)
        self.key = "synthetic-reconcile-key-" * 3
        self.envelope = d.sign_outputs(state, family="ph_afp_articles", policy=self.p, key=self.key)
        for path in (self.origin, self.local):
            migrate(path)
            with sqlite3.connect(str(path)) as conn:
                r = record()
                conn.execute("INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    r["source_family"], r["source_identity"], "philippines", r["canonical_official_url"],
                    r["publisher_posted_date"], "ph_afp", "ph_afp", None, "c"*40, "a"*64,
                    "123-1", "official_link_only", "d"*64, "2026-10-19T00:00:00Z"))
            conn.close()  # immutable reconciliation inputs must include committed WAL data
        with sqlite3.connect(str(self.local)) as conn:
            d.admit(conn, self.envelope, family="ph_afp_articles", policy=self.p, key=self.key)
        conn.close()

    def test_local_output_survives_main_reconciliation_and_replay(self):
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        with sqlite3.connect(str(out)) as conn:
            self.assertEqual(conn.execute("SELECT summary FROM daily_machine_records").fetchone()[0],
                             reading()["summary_english"])
            self.assertEqual(d.admit(conn, self.envelope, family="ph_afp_articles", policy=self.p,
                                     key=self.key)["admitted"], 0)

    def test_conflicting_already_released_version_stops_reconciliation(self):
        with sqlite3.connect(str(self.origin)) as conn:
            d.admit(conn, self.envelope, family="ph_afp_articles", policy=self.p, key=self.key)
            conn.execute("UPDATE daily_machine_records SET summary='Conflicting synthetic machine record'")
        conn.close()  # checkpoint the immutable merge input, including its WAL
        with self.assertRaisesRegex(ValueError, "daily_machine_record_version_conflict"):
            self.run_reconcile()


if __name__ == "__main__":
    unittest.main()
