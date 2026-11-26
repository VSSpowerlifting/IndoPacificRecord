"""USCC v2 analysis prompt: sentence openers and no possessives.

Synthetic offline contracts; no USCC text or model reading is used. All three
v1 attempts held at daily_name_or_office_unsupported. The unchanged
single-passage token check exempts only the openers The, According, It and
This, the label USCC and the Commission's own name words; the passages write
possessives with a typographic apostrophe (U+2019). A faithful reading that
types an ASCII possessive (People's, Commission's, USCC's) or opens with
another capitalized word (During) therefore carries a token the cited passage
does not contain. v2 only adds an instruction. These tests prove the
registration, the instruction, and that the validator still holds those
readings while a v2-compliant reading passes.
"""
import json
import unittest

from analysis import uscc_daily_prompts as prompts
from core.daily_sources import SOURCES
from processing import daily_intake as d

FAMILY = "us_uscc_press_en"
V2 = "us-uscc-relevance-v1+us-uscc-analysis-v2"
V1 = "us-uscc-relevance-v1+us-uscc-analysis-v1"
TITLE = "Invented commission delegation announcement"
# Invented passages in the structure observed: typographic possessives, a
# date range and a second passage with discussion detail.
P1 = ("The Commission’s delegation traveled to Example City from November 10 to 14 "
      "and met officials of the People’s Republic of China during the visit.")
P2 = ("Commissioners also discussed export controls and supply chain resilience with "
      "Example City business leaders on the trip.")
BODY = P1 + "\n\n" + P2

ONE = ("The USCC said a delegation visited Example City from November 10 to 14 "
       "and met officials from China.")
TWO = ("According to the USCC, Commissioners discussed export controls and supply "
       "chain resilience with business leaders in Example City.")


def record():
    return {"source_family": FAMILY, "source_identity": "uscc-press:synthetic-v2",
            "title": TITLE, "body": BODY, "content_sha256": "c" * 64}


def reading(one=ONE, two=TWO, version=V2):
    return dict(passed_relevance=True, requires_translation=False,
                summary_english=one + " " + two,
                facts=[dict(sentence=one, evidence=P1), dict(sentence=two, evidence=P2)],
                categories=["commission_activity"], is_significant=False,
                significance_reasoning=None, model_id="synthetic-offline-rehearsal",
                prompt_version=version)


class UsccV2Prompt(unittest.TestCase):
    def test_v2_is_emitted_first_and_v1_stays_admissible(self):
        self.assertEqual(prompts.VERSION, V2)
        self.assertEqual(prompts.RELEVANCE_VERSION, "us-uscc-relevance-v1")
        self.assertEqual(prompts.ANALYSIS_VERSION, "us-uscc-analysis-v2")
        self.assertEqual(SOURCES[FAMILY].prompt_versions, (V2, V1))
        self.assertEqual(d.allowed_prompt_versions(FAMILY), (V2, V1))
        self.assertEqual(SOURCES[FAMILY].released_prompt_versions, ())

    def test_v2_instructs_openers_no_possessives_and_single_passage_names(self):
        text = prompts.analysis_messages(TITLE, BODY)[0]["content"]
        self.assertIn("Begin every sentence with exactly 'The USCC' or 'According to the USCC,'", text)
        self.assertIn("not During, On, In, After, While or a name", text)
        self.assertIn("Never write a possessive or any word with an apostrophe", text)
        self.assertIn("never the USCC's delegation", text)
        self.assertIn("in the ONE passage you cite for that sentence", text)
        self.assertIn("Never copy 12 or more consecutive words of the source", text)
        self.assertIn("Do not end a sentence with an abbreviation that has its own period", text)
        # The v1 rules are kept unchanged.
        self.assertIn("exact abbreviation USCC", text)
        self.assertIn("the two summary sentences TOGETHER at most 60 words", text)
        self.assertIn("Do not combine evidence from different passages for one sentence", text)

    def test_relevance_prompt_and_system_prompt_are_unchanged(self):
        text = json.dumps(prompts.relevance_messages(TITLE, BODY))
        self.assertNotIn("possessive", text + prompts.system_prompt())


class UnchangedValidator(unittest.TestCase):
    """The single-passage token and excerpt checks are not relaxed for v2."""

    def test_a_v2_compliant_reading_passes(self):
        self.assertIsInstance(d.english_official_quality(record(), reading()), str)

    def test_v1_style_readings_still_hold(self):
        for one, two, code in (
                # ASCII possessives of a name, the Commission and the USCC.
                ("The USCC said a delegation visited Example City from November 10 to 14 "
                 "and met People's Republic of China officials.", TWO,
                 "daily_name_or_office_unsupported"),
                ("The USCC said the Commission's delegation visited Example City from "
                 "November 10 to 14.", TWO, "daily_name_or_office_unsupported"),
                ("The USCC's delegation visited Example City from November 10 to 14, "
                 "the USCC said.", TWO, "daily_name_or_office_unsupported"),
                # A capitalized opener the cited passage does not contain.
                (ONE, "During the trip, the USCC said Commissioners discussed export "
                 "controls with business leaders in Example City.",
                 "daily_name_or_office_unsupported"),
                # A demonym absent from the cited passage.
                ("The USCC said a delegation visited Example City from November 10 to 14 "
                 "and met Chinese officials.", TWO, "daily_name_or_office_unsupported"),
                # Twelve consecutive source words, though attributed.
                ("The USCC said its delegation traveled to Example City from November 10 "
                 "to 14 and met officials from China.", TWO,
                 "daily_original_excerpt_prohibited")):
            with self.subTest(one=one, two=two):
                with self.assertRaises(d.IntakeHold) as caught:
                    d.english_official_quality(record(), reading(one, two))
                self.assertEqual(str(caught.exception), code)

    def test_v1_outputs_remain_admissible_and_unregistered_versions_refused(self):
        self.assertIsInstance(d.english_official_quality(record(), reading(version=V1)), str)
        with self.assertRaises(d.IntakeHold) as caught:
            d.english_official_quality(
                record(), reading(version="us-uscc-relevance-v1+us-uscc-analysis-v3"))
        self.assertEqual(str(caught.exception), "daily_model_provenance_incomplete")


if __name__ == "__main__":
    unittest.main()
