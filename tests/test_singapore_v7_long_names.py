"""MINDEF v7 analysis prompt: a short-form fallback for long names and offices.

Synthetic offline contracts; no MINDEF text or model reading is used. The
names below are invented apart from generic honorific and office words. Both
sg-analysis-v6 attempts held at daily_original_excerpt_prohibited: v6 asks for
every name and office exactly as written, but a visiting official's honorific
full name with office, a commander's office with name, or a lede rephrased in
its own order is alone 12 or more consecutive source words under the checker's
casefolded \\w+ words. v7 only adds an instruction. These tests prove the
registration, the instruction, that a short form whose words all occur in the
cited passage passes BOTH the excerpt check and the name/office check, that a
lede restructured after a MINDEF attribution opener passes, and that the
unchanged validator still holds the long span, a lede restated in order, an
activity-first or date-first opener (a capitalized opener the cited passage
lacks), an invented demonym and an ASCII possessive.
"""
import unittest

from analysis import singapore_daily_prompts as prompts
from core.daily_sources import SOURCES, _sg_output_check
from processing import daily_intake as d

FAMILY = "sg_mindef_releases"
V7 = "sg-relevance-v2+sg-analysis-v7"
EARLIER = tuple("sg-relevance-v2+sg-analysis-v%d" % n for n in range(2, 7))
TITLE = "Synthetic introductory visit fixture"
# Lede: host office and name, then a 22-word visiting office plus honorific
# name, then purpose, place and an abbreviated date.
LEDE = ("Minister for Defence Dr Fixture Host hosted Minister of Defence II of Brunei "
        "Darussalam Pehin Datu Example Major General (Retd) Dato Paduka Seri Haji Awang "
        "Sample bin Haji Testname on an introductory visit to Singapore on 21 Nov.")
# Second passage: an 18-word commander office plus honorific name.
CALL = ("Dr Fixture Host also called on Commander of the Royal Brunei Armed Forces Major "
        "General Dato Seri Pahlawan Haji Sample Fixturename bin Haji Example, who "
        "accompanied the visiting delegation.")
BODY = LEDE + "\n\n" + CALL

ONE = ("MINDEF said Dr Fixture Host received the Minister of Defence II of Brunei "
       "Darussalam in Singapore on 21 Nov for an introductory visit.")
TWO = ("According to MINDEF, the Commander of the Royal Brunei Armed Forces accompanied "
       "the delegation and also met Dr Fixture Host.")


def record():
    return {"source_family": FAMILY, "source_identity": "synthetic-v7-nr",
            "title": TITLE, "body": BODY, "content_sha256": "c" * 64}


def reading(one=ONE, two=TWO, version=V7):
    return dict(passed_relevance=True, requires_translation=False,
                summary_english=one + " " + two,
                facts=[dict(sentence=one, evidence=LEDE), dict(sentence=two, evidence=CALL)],
                categories=["military_diplomacy"], is_significant=False,
                significance_reasoning=None, model_id="synthetic-offline-rehearsal",
                prompt_version=version)


def longest_source_run(sentence):
    """Longest run of consecutive checker words shared with the source."""
    import re
    words = re.findall(r"\w+", sentence.casefold())
    source = " " + " ".join(re.findall(r"\w+", (TITLE + "\n" + BODY).casefold())) + " "
    return max(n for n in range(1, len(words) + 1)
               for i in range(len(words) - n + 1)
               if " " + " ".join(words[i:i + n]) + " " in source)


class SingaporeV7Prompt(unittest.TestCase):
    def test_v7_is_emitted_and_earlier_versions_stay_admissible(self):
        self.assertEqual(prompts.VERSION, V7)
        self.assertEqual(prompts.RELEVANCE_VERSION, "sg-relevance-v2")
        self.assertEqual(prompts.ANALYSIS_VERSION, "sg-analysis-v7")
        self.assertEqual(SOURCES[FAMILY].prompt_versions, EARLIER + (V7,))
        self.assertEqual(d.allowed_prompt_versions(FAMILY), EARLIER + (V7,))

    def test_v7_instructs_the_short_form_fallback_and_keeps_the_v6_rules(self):
        text = prompts.analysis_messages(TITLE, BODY)[0]["content"]
        self.assertIn("The 12-word rule counts every word of a name, honorific, rank and office", text)
        self.assertIn("would reproduce 12 or more consecutive source words, do not write the full form", text)
        self.assertIn("use a shorter accurate form whose every word appears in the cited passage", text)
        self.assertIn("Never restate the opening (lede) sentence of the release in its own order or wording", text)
        self.assertIn("Begin every sentence with exactly 'MINDEF' (for example MINDEF said) or "
                      "'According to MINDEF,' and never with any other capitalized word", text)
        self.assertIn("after the attribution opener, reorder the participants, activity, place and date", text)
        self.assertIn("After the opening attribution, state who did what and its status", text)
        # The activity-first steer and the conflicting v6 lead line are gone,
        # and no example names an office from a single real release (checked
        # on the instructions only; the fixture passages follow the newline).
        instructions = text.split("\n", 1)[0]
        self.assertNotIn("activity first", instructions)
        self.assertNotIn("Lead with who did what", instructions)
        self.assertNotIn("Brunei", instructions)
        self.assertIn("Do not write possessives or any word with an apostrophe", text)
        self.assertIn("spell and capitalize every word of it exactly as the cited passage does", text)
        # The v6 rules are kept unchanged.
        self.assertIn("together at most 60 words", text)
        self.assertIn("if the passage abbreviates a month (for example Oct), keep the abbreviation", text)
        self.assertIn("flag (false), flag_reason (null), flag_evidence_id (null)", text)
        self.assertIn("sequences of 12 source words", text)


class UnchangedValidator(unittest.TestCase):
    """The excerpt and single-passage token checks are not relaxed for v7."""

    def test_the_fixture_spans_are_long_enough_to_matter(self):
        import re
        visitor = LEDE[LEDE.index("Minister of Defence II"):LEDE.index(" on an")]
        commander = CALL[CALL.index("Commander"):CALL.index(",")]
        self.assertGreaterEqual(len(re.findall(r"\w+", visitor)), 12)
        self.assertGreaterEqual(len(re.findall(r"\w+", commander)), 12)

    def test_v7_short_forms_pass_the_excerpt_and_name_checks(self):
        for one in (ONE,
                    # A rank with the part of the name the passage uses.
                    "MINDEF said Dr Fixture Host received Major General (Retd) Testname, "
                    "the Minister of Defence II of Brunei Darussalam, on 21 Nov."):
            with self.subTest(one=one):
                self.assertLess(longest_source_run(one), 12)
                r = reading(one=one)
                self.assertIsInstance(d.english_official_quality(record(), r), str)
                self.assertIsNone(_sg_output_check(
                    {"model_flagged": False, "summary": r["summary_english"]}))

    def test_an_attribution_first_restructured_lede_passes(self):
        # The visitor becomes the subject after the MINDEF opener, so the lede
        # is not restated in its own order and no unexempted opener is added.
        one = ("MINDEF said the Minister of Defence II of Brunei Darussalam made an "
               "introductory visit to Singapore on 21 Nov and met Dr Fixture Host.")
        self.assertLess(longest_source_run(one), 12)
        r = reading(one=one)
        self.assertIsInstance(d.english_official_quality(record(), r), str)
        self.assertIsNone(_sg_output_check(
            {"model_flagged": False, "summary": r["summary_english"]}))

    def test_activity_first_and_date_first_openers_still_hold(self):
        # The checker exempts only The, According, It, This, MINDEF and the
        # publisher words, so a capitalized opener the passage lacks holds.
        for one in (
                "During an introductory visit on 21 Nov, MINDEF said, Dr Fixture Host "
                "received the Minister of Defence II of Brunei Darussalam.",
                "An introductory visit to Singapore on 21 Nov brought the Minister of "
                "Defence II of Brunei Darussalam to meet Dr Fixture Host, MINDEF said.",
                "On 21 Nov, MINDEF said, Dr Fixture Host received the Minister of "
                "Defence II of Brunei Darussalam on an introductory visit."):
            with self.subTest(one=one):
                self.assertLess(longest_source_run(one), 12)
                with self.assertRaises(d.IntakeHold) as caught:
                    d.english_official_quality(record(), reading(one=one))
                self.assertEqual(str(caught.exception), "daily_name_or_office_unsupported")

    def test_long_spans_and_genuine_substitutions_still_hold(self):
        for one, two, code in (
                # The visiting office with the honorific full name, as written.
                ("MINDEF said Dr Fixture Host hosted Minister of Defence II of Brunei "
                 "Darussalam Pehin Datu Example Major General (Retd) Dato Paduka Seri Haji "
                 "Awang Sample bin Haji Testname.", TWO, "daily_original_excerpt_prohibited"),
                # The commander's office with the honorific full name, as written.
                (ONE, "According to MINDEF, Commander of the Royal Brunei Armed Forces Major "
                 "General Dato Seri Pahlawan Haji Sample Fixturename bin Haji Example "
                 "accompanied the delegation.", "daily_original_excerpt_prohibited"),
                # The lede restated in its own order, without the long name.
                ("MINDEF said Minister for Defence Dr Fixture Host hosted Minister of "
                 "Defence II of Brunei Darussalam on an introductory visit.", TWO,
                 "daily_original_excerpt_prohibited"),
                # A short form with a demonym the passage does not contain.
                ("MINDEF said Dr Fixture Host received the Bruneian Minister of Defence II "
                 "in Singapore on 21 Nov.", TWO, "daily_name_or_office_unsupported"),
                # A short form with an ASCII possessive the passage does not contain.
                ("MINDEF said Dr Fixture Host received Brunei's Minister of Defence II "
                 "in Singapore on 21 Nov.", TWO, "daily_name_or_office_unsupported"),
                # An expanded month.
                ("MINDEF said Dr Fixture Host received the Minister of Defence II of "
                 "Brunei Darussalam in Singapore on 21 November.", TWO,
                 "daily_name_or_office_unsupported")):
            with self.subTest(one=one, two=two):
                with self.assertRaises(d.IntakeHold) as caught:
                    d.english_official_quality(record(), reading(one, two))
                self.assertEqual(str(caught.exception), code)

    def test_v6_outputs_remain_admissible_and_unregistered_versions_refused(self):
        r = reading(version="sg-relevance-v2+sg-analysis-v6")
        self.assertIsInstance(d.english_official_quality(record(), r), str)
        with self.assertRaises(d.IntakeHold) as caught:
            d.english_official_quality(record(), reading(version="sg-relevance-v2+sg-analysis-v8"))
        self.assertEqual(str(caught.exception), "daily_model_provenance_incomplete")


if __name__ == "__main__":
    unittest.main()
