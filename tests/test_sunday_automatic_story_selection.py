"""Same-call Sunday editorial triage; no extra paid call, mail or publication."""
from __future__ import annotations

import copy
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.brief_editorial_evidence import load_editorial_evidence
from scripts.sunday_briefs_auto_writer import (
    compose, validate_manuscript, writing_schema,
)
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold
from tests.test_weekly_briefs_auto_writer import evidence

ROOT = Path(__file__).resolve().parents[1]


def score(significance, strength, novelty, connection, timeliness):
    return dict(strategic_significance=significance, evidence_strength=strength,
                analytical_novelty=novelty, cross_desk_connection=connection,
                timeliness=timeliness)


def selected():
    draft = manuscript()
    draft["story_selection"] = {
        "candidates": [
            {"slug": "official-military-cooperation", "thesis":
             "Examine the specific official security cooperation measures that "
             "were announced during the reporting week.",
             "limitation": "The accounts do not prove subsequent implementation "
             "or independent operational outcomes.",
             "production_ids": [1], "research_ids": ["JP-W41-01"],
             "scores": score(5, 4, 4, 4, 5)},
            {"slug": "secondary-cooperation", "thesis":
             "Compare the reported development with the neighboring security "
             "initiatives appearing in another official account.",
             "limitation": "A source-linked public-security synopsis cannot "
             "establish completed military integration.",
             "production_ids": [2], "research_ids": ["VN-MPS-1791199100"],
             "scores": score(2, 3, 3, 1, 3)},
        ],
        "selected_slug": "official-military-cooperation",
        "selection_rationale": "The first option has stronger dated source evidence "
        "and a narrower claim; the second relies on weaker implied connections.",
    }
    return draft


class AutomaticStorySelectionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.research = load_editorial_evidence(SAT, SAT)

    def test_schema_requires_ranked_story_only_for_automatic_sunday(self):
        schema = writing_schema(
            [1, 2], supplemental_ids=["JP-W41-01"],
            automatic_story_selection=True)
        self.assertIn("story_selection", schema["required"])
        self.assertEqual(schema["properties"]["story_selection"]
                         ["properties"]["candidates"]["maxItems"], 3)
        self.assertNotIn("story_selection", writing_schema([1, 2])["required"])

    def test_one_true_story_is_allowed_and_no_approval_is_inferred(self):
        draft = selected()
        self.assertIs(validate_manuscript(
            draft, evidence(), supplemental=self.research,
            automatic_story_selection=True), draft)
        draft["story_selection"]["candidates"] = draft["story_selection"]["candidates"][:1]
        self.assertIs(validate_manuscript(
            draft, evidence(), supplemental=self.research,
            automatic_story_selection=True), draft)

    def test_rejects_forged_duplicate_unscored_unrelated_options(self):
        cases = [
            ("duplicate-candidate", lambda x: x["candidates"].append(
                copy.deepcopy(x["candidates"][0])), "duplicate"),
            ("fabricated-numeric", lambda x: x["candidates"][0]
             ["production_ids"].append(999999), "unavailable"),
            ("fabricated-research", lambda x: x["candidates"][0]
             ["research_ids"].append("JP-NOT-IN-WEEK"), "unavailable"),
            ("lost-scores", lambda x: x["candidates"][0]
             ["scores"].pop("timeliness"), "scores"),
            ("wrong-lead", lambda x: x.update(selected_slug="secondary-cooperation"),
             "highest-scoring"),
            ("fake-lead", lambda x: x.update(selected_slug="invented-story"),
             "selected"),
        ]
        for label, change, match in cases:
            with self.subTest(label=label):
                draft = selected()
                change(draft["story_selection"])
                with self.assertRaisesRegex(ValueError, match):
                    validate_manuscript(
                        draft, evidence(), supplemental=self.research,
                        automatic_story_selection=True)

    def test_selected_story_must_appear_in_actual_opening_citations(self):
        draft = selected()
        draft["story_selection"]["candidates"][0]["production_ids"] = [2]
        draft["story_selection"]["candidates"][0]["research_ids"] = []
        with self.assertRaisesRegex(ValueError, "opening"):
            validate_manuscript(
                draft, evidence(), supplemental=self.research,
                automatic_story_selection=True)

    def test_selection_and_manuscript_use_same_single_tool_call(self):
        offered = []
        response = SimpleNamespace(
            stop_reason="tool_use", content=[SimpleNamespace(
                type="tool_use", name="compose_editorial_draft",
                input=selected())])
        stream = lambda **kw: (
            offered.append(kw),
            nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]
        fake = SimpleNamespace(messages=SimpleNamespace(stream=stream))
        with patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                   return_value=evidence()):
            draft = compose(
                scaffold(), SAT, client=fake, supplemental=self.research,
                automatic_story_selection=True)
        self.assertEqual(len(offered), 1)
        self.assertEqual(draft["story_selection"]["selected_slug"],
                         "official-military-cooperation")
        self.assertIn("AUTOMATIC STORY SELECTION", offered[0]["messages"][0]["content"])
        self.assertEqual(offered[0]["model"], "claude-sonnet-4-6")

    def test_scheduled_handoff_activates_selection_without_parallel_pipeline(self):
        handoff = (ROOT / "scripts/sunday_editorial_handoff.py").read_text()
        workflow = (ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml").read_text()
        self.assertEqual(handoff.count("automatic_story_selection=args.full_week"), 2)
        self.assertIn("python -m scripts.sunday_editorial_handoff", workflow)
        self.assertNotIn("python -m scripts.regional_theme_proposals", workflow)
        self.assertIn("SUNDAY_SEND", workflow)


if __name__ == "__main__":
    unittest.main()
