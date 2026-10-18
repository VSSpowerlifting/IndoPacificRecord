"""Draft-only mixed research admission never promotes a public country desk."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_briefs_auto_writer import choose_evidence

SAT = "2026-10-17"
ROOT = Path(__file__).resolve().parents[1]


def row(ident, desk):
    return {
        "id": ident,
        "desk_id": desk,
        "published_date": "2026-10-16",
        "text_english": "Verified original-language source representation. " * 9,
        "text_original": None,
        "analyzed_at": None,
        "is_significant": False,
    }


def select(rows, *, research_desks=()):
    offered = [{"record_id": item["id"]} for item in rows]
    sidecar = {
        "week_start": "2026-10-11",
        "week_ending": SAT,
        "desks": ["china", "singapore"],
        "source_trail": offered,
    }
    with patch("scripts.sunday_briefs_auto_writer.read_only"):
        with patch("scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                   return_value=rows):
            with patch("scripts.sunday_briefs_auto_writer.trail_entry",
                       side_effect=lambda item: {"record_id": item["id"]}):
                return choose_evidence(
                    sidecar, as_of=SAT, db=Path("/no-read"),
                    research_desks=research_desks)


class SundayMixedResearchDraftContracts(unittest.TestCase):
    def test_original_two_live_desk_path_unchanged(self):
        chosen = select([row(1, "china"), row(2, "singapore")])
        self.assertEqual({r["desk_id"] for r, _ in chosen},
                         {"china", "singapore"})

    def test_one_production_desk_without_research_remains_held(self):
        with self.assertRaisesRegex(ValueError, "fewer than two"):
            select([row(1, "china")])

    def test_separate_typed_research_desk_supports_unapproved_draft(self):
        chosen = select([row(1, "china")], research_desks=("japan",))
        self.assertEqual([r["id"] for r, _ in chosen], [1])
        # External sources are never added to numeric production source rows.
        self.assertEqual(len(chosen), 1)

    def test_same_desk_or_no_actual_production_cannot_bypass(self):
        for rows, research_desks in (
            ([row(1, "china")], ("china",)),
            ([], ("japan", "indonesia")),
        ):
            with self.subTest(rows=rows, research_desks=research_desks):
                with self.assertRaisesRegex(ValueError, "fewer than two"):
                    select(rows, research_desks=research_desks)

    def test_workflow_uses_editor_safe_packet_before_model_or_send(self):
        workflow = (ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
                    ).read_text(encoding="utf-8")
        scope = workflow.index(
            "- name: Separate Vietnam private-model and editor-email research scope")
        preflight = workflow.index(
            "- name: Require Sunday source readiness with verified editorial research")
        model = workflow.index(
            "- name: Generate source-cited Sunday manuscript")
        self.assertLess(scope, preflight)
        self.assertLess(preflight, model)
        section = workflow[preflight:model]
        self.assertIn("--research-packet \"$PRIVATE_WEEK_PACKET\"", section)
        self.assertIn("steps.editor_scope.outputs.packet", section)
        self.assertNotIn("send_packet", section)


if __name__ == "__main__":
    unittest.main()
