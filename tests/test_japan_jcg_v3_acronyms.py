"""JCG v3 analysis prompt: write acronyms as the cited passage does.

Synthetic offline contracts; no JCG text or reading is used. Six of eight held
v1/v2 readings spelled out an acronym that the cited passage leaves
unexpanded, and the unchanged single-passage token check held each one. v3
only adds an instruction. These tests prove the registration, the instruction
and that the validator still holds a genuine expansion, a contraction and a
name substitution, while an acronym kept as written passes.
"""
import json
import unittest

from analysis import japan_jcg_prompts as prompts
from core.daily_sources import SOURCES
from processing import daily_intake as d
from tests.test_japan_jcg_daily import FAMILY, TITLE, BODY
from tests.test_japan_jcg_v2_queue import record, v2_reading

V3 = "jp-jcg-relevance-v1+jp-jcg-analysis-v3"
V2 = "jp-jcg-relevance-v1+jp-jcg-analysis-v2"
V1 = "jp-jcg-relevance-v1+jp-jcg-analysis-v1"
# A synthetic passage pair that uses one unexpanded acronym (XRT) and one
# spelled-out term (search and rescue).
FIRST = "The JCG said its XRT unit held a routine joint exercise with two coast guard agencies."
SECOND = "The release describes the schedule for a planned search and rescue drill."
BODY_ACRONYM = FIRST + "\n\n" + SECOND


def v3_reading(one, two="The JCG describes the schedule for a planned search and rescue drill."):
    r = v2_reading(one=one, two=two, prompt_version=V3)
    r["facts"] = [dict(sentence=one, evidence=FIRST), dict(sentence=two, evidence=SECOND)]
    return r


def acronym_record():
    return dict(record(), body=BODY_ACRONYM)


class JcgV3Prompt(unittest.TestCase):
    def test_v3_is_emitted_first_and_earlier_versions_stay_admissible(self):
        self.assertEqual(prompts.VERSION, V3)
        self.assertEqual(prompts.ANALYSIS_VERSION, "jp-jcg-analysis-v3")
        self.assertEqual(SOURCES[FAMILY].prompt_versions, (V3, V2, V1))
        self.assertEqual(d.allowed_prompt_versions(FAMILY), (V3, V2, V1))

    def test_v3_instructs_acronyms_as_written_and_keeps_the_v2_checks(self):
        text = json.dumps(prompts.analysis_messages(TITLE, BODY))
        self.assertIn("Write every acronym, abbreviation and short form exactly as the "
                      "cited passage writes it", text)
        self.assertIn("never spell out an acronym or abbreviation that the passage "
                      "leaves unexpanded", text)
        self.assertIn("never shorten a term the passage spells out into an acronym", text)
        # The v2 rules are kept unchanged.
        self.assertIn("Set flag=false, flag_reason=null and flag_evidence_id=null", text)
        self.assertIn("FINAL CHECK before returning", text)
        self.assertIn("never borrow it from the title or another passage", text)

    def test_relevance_prompt_is_unchanged(self):
        self.assertEqual(prompts.RELEVANCE_VERSION, "jp-jcg-relevance-v1")


class UnchangedValidator(unittest.TestCase):
    """The single-passage token check is not relaxed for v3 readings."""

    def test_the_acronym_kept_as_written_passes(self):
        reading = v3_reading("The JCG says its XRT unit held a routine joint exercise.")
        self.assertIsInstance(d.english_official_quality(acronym_record(), reading), str)

    def test_genuine_substitutions_still_hold(self):
        for one, two, code in (
                # An invented expansion of an acronym the passage leaves unexpanded.
                ("The JCG says its Rapid Response Team held a routine joint exercise.",
                 None, "daily_name_or_office_unsupported"),
                # A contraction of a term the passage spells out.
                ("The JCG says its XRT unit held a routine joint exercise.",
                 "The JCG describes the schedule for a planned SAR drill.",
                 "daily_name_or_office_unsupported"),
                # A country absent from the cited passage.
                ("The JCG says its XRT unit held a routine joint exercise with Philippine agencies.",
                 None, "daily_name_or_office_unsupported")):
            with self.subTest(one=one, two=two):
                reading = v3_reading(one) if two is None else v3_reading(one, two)
                with self.assertRaises(d.IntakeHold) as caught:
                    d.english_official_quality(acronym_record(), reading)
                self.assertEqual(str(caught.exception), code)

    def test_an_unregistered_prompt_version_is_still_refused(self):
        self.assertNotIn("jp-jcg-relevance-v1+jp-jcg-analysis-v4",
                         d.allowed_prompt_versions(FAMILY))


if __name__ == "__main__":
    unittest.main()
