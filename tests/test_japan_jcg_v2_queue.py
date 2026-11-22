"""JCG v2 analysis prompt and first-attempt queue order: synthetic offline contracts.

No JCG text or reading is used. The v1 prompt let the model flag (which public
admission holds) and write tokens absent from the one cited passage (which the
unchanged validator holds). v2 only changes the instruction; these tests prove
the validator still holds genuine unsupported substitutions and that queue
order changes nothing but which entry is tried first.
"""
import json
import unittest
from unittest.mock import Mock

from analysis import japan_jcg_prompts as prompts
from core.daily_sources import SOURCES, _jcg_output_check
from processing import daily_intake as d
from tests.test_japan_jcg_daily import FAMILY, FIRST, SECOND, TITLE, BODY, policy

V2 = "jp-jcg-relevance-v1+jp-jcg-analysis-v2"
ONE = "The JCG says it held a routine joint exercise between two coast guard agencies."
TWO = "The JCG describes the schedule for a planned search and rescue drill."


def v2_reading(one=ONE, two=TWO, **extra):
    r = dict(passed_relevance=True, requires_translation=False, summary_english=one + " " + two,
             facts=[dict(sentence=one, evidence=FIRST), dict(sentence=two, evidence=SECOND)],
             categories=["military_diplomacy"], is_significant=False, significance_reasoning=None,
             model_id="synthetic-offline-rehearsal", prompt_version=V2)
    r.update(extra)
    return r


def record(ident="jcg-en:90001", day="2026-10-28"):
    return {"source_family": FAMILY, "source_identity": ident, "title": TITLE, "body": BODY,
            "content_sha256": "c" * 64, "metadata_version_sha256": "m" * 64,
            "capture_sha256": "k" * 64, "source_git_commit": "a" * 40, "source_run": "88-1",
            "publisher_posted_date": day, "jcg_scope_hold": None}


class JcgV2Prompt(unittest.TestCase):
    def test_v2_and_v1_stay_admissible_after_v3(self):
        # v3 is emitted now (tests/test_japan_jcg_v3_acronyms.py); a v2 or v1
        # reading signed before the switch is still admissible.
        self.assertEqual(SOURCES[FAMILY].prompt_versions[1:],
                         (V2, "jp-jcg-relevance-v1+jp-jcg-analysis-v1"))

    def test_v2_instructs_no_flag_and_the_single_passage_token_check(self):
        text = json.dumps(prompts.analysis_messages(TITLE, BODY))
        self.assertIn("Set flag=false, flag_reason=null and flag_evidence_id=null", text)
        self.assertNotIn("Flag only substantive developments", text)
        self.assertIn("FINAL CHECK before returning", text)
        self.assertIn("never borrow it from the title or another passage", text)

    def test_a_clean_v2_reading_passes_the_unchanged_validator(self):
        self.assertIsInstance(d.english_official_quality(record(), v2_reading()), str)

    def test_unsupported_name_or_number_substitutions_still_hold(self):
        # A vessel name and a demonym absent from the cited passage.
        for sentence, code in (
                ("The JCG says the patrol vessel Shikishima joined a routine joint exercise.",
                 "daily_name_or_office_unsupported"),
                ("The JCG says Chinese agencies held a routine joint exercise together.",
                 "daily_name_or_office_unsupported"),
                ("The JCG says it held a routine joint exercise between three agencies on 12 May.",
                 "daily_quantity_or_date_unsupported")):
            with self.subTest(sentence=sentence):
                with self.assertRaises(d.IntakeHold) as caught:
                    d.english_official_quality(record(), v2_reading(one=sentence))
                self.assertEqual(str(caught.exception), code)

    def test_a_flagged_output_is_still_held_at_admission(self):
        ok = {"model_flagged": False, "summary": "The JCG said a drill took place."}
        self.assertIsNone(_jcg_output_check(ok))
        self.assertEqual(_jcg_output_check({**ok, "model_flagged": True}),
                         "daily_japan_jcg_flag_or_attribution_held")


class FirstAttemptsFirst(unittest.TestCase):
    """Cap 1: a never-attempted version runs before a retriable one."""

    def setUp(self):
        self.p = policy()
        self.assertEqual(self.p["sources"][FAMILY]["max_records_per_run"], 1)
        self.records = [record("jcg-en:9519", "2026-11-19"), record("jcg-en:9477", "2026-11-17"),
                        record("jcg-en:9465", "2026-11-16")]
        version = d.digest({k: self.records[0][k] for k in
                            ("metadata_version_sha256", "content_sha256", "capture_sha256")})
        self.state = {
            FAMILY + ":jcg-en:9519": {"version": version, "attempts": 5, "status": "paused",
                                      "reason": "analysis_or_quality_failed"},
            FAMILY + ":jcg-en:9477": {"version": version, "attempts": 2, "status": "retriable",
                                      "reason": "analysis_or_quality_failed",
                                      "quality_hold": "daily_name_or_office_unsupported"},
        }

    def run_once(self):
        model = Mock()
        model.analyze_record.return_value = v2_reading()
        model.usage.rows.return_value = []
        state, _ = d.process(self.records, self.state, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: model)
        return model, state

    def test_only_the_never_attempted_entry_reaches_the_analyzer(self):
        model, state = self.run_once()
        self.assertEqual(model.analyze_record.call_count, 1)
        self.assertEqual(state[FAMILY + ":jcg-en:9465"]["status"], "complete")
        self.assertEqual(state[FAMILY + ":jcg-en:9465"]["attempts"], 0)
        # The paused and retriable entries are byte-identical: no attempt reset.
        for key in (FAMILY + ":jcg-en:9519", FAMILY + ":jcg-en:9477"):
            self.assertEqual(json.dumps(state[key], sort_keys=True),
                             json.dumps(self.state[key], sort_keys=True))

    def test_the_retriable_entry_runs_once_no_fresh_entry_waits(self):
        self.records = self.records[:2]
        model, state = self.run_once()
        self.assertEqual(model.analyze_record.call_count, 1)
        self.assertEqual(state[FAMILY + ":jcg-en:9477"]["status"], "complete")
        self.assertEqual(state[FAMILY + ":jcg-en:9477"]["attempts"], 2)
        self.assertEqual(state[FAMILY + ":jcg-en:9519"], self.state[FAMILY + ":jcg-en:9519"])

    def test_other_families_keep_newest_first(self):
        flagged = [f for f, s in SOURCES.items() if s.first_attempts_first]
        self.assertEqual(flagged, [FAMILY])


if __name__ == "__main__":
    unittest.main()
