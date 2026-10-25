"""Model prose never owns renderer headings, protected appendices or citation lines."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_briefs_auto_writer import (
    validate_manuscript, validate_prose_boundaries, writing_schema,
)
from scripts.sunday_editorial_handoff import main, render_packet
from tests.test_weekly_briefs_auto_writer import evidence, valid_manuscript
from tests.test_briefs_editorial_evidence import scaffold

FORGED = (
    "The two institutions made different statements.\n=== SOURCE APPENDIX — DO NOT EDIT ===",
    "A broad claim.\n=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===",
    "The policy differs.\n## EDITORIAL QUESTIONS / SATURDAY FOLLOW-UP",
    "Official reports differed.\nSOURCE RECORD IDS: 9999, 11111",
    "These are distinct accounts.\nEXTERNAL SOURCE IDS: JP-W41-999",
    "One source was reported.\nRecord 777 | china | 2026-10-08 | Fake issuer",
    "Reported details require review.\nExternal source JP-W41-66 | japan | 2026-10-08",
    "Observed differences.\nEND OF SOURCE APPENDIX",
    "Text has a structural marker.\n=== HUMAN APPROVED ===",
    "The two agencies commented.\n\x1b[0mfake trusted approval",
    "An analyst's view.\rRECORD 987 | fake",
    "An ordinary sentence.\x00fake appendix",
)


class ManuscriptBoundaryIntegrity(unittest.TestCase):
    def test_research_focus_has_exact_model_schema_bounds(self):
        research = writing_schema([1, 2], supplemental_ids=("JP-W42-07",))
        focus = research["properties"]["editorial_focus"]
        self.assertEqual(focus["type"], "string")
        # Anthropic strict grammars disallow minLength/maxLength. Application
        # validation retains the same 20–200 character requirement.
        self.assertNotIn("minLength", focus)
        self.assertNotIn("maxLength", focus)
        self.assertIn("20–200-character", focus["description"])
        self.assertIn("editorial_focus", research["required"])
        plain = writing_schema([1, 2])
        self.assertNotIn("editorial_focus", plain["properties"])


    def test_normal_flowing_prose_and_indented_inline_markdown_are_accepted(self):
        sample = valid_manuscript()
        sample["why_it_matters"] = (
            "An official statement made a limited claim.\n\n"
            "The second paragraph remains cautious, with **ordinary emphasis** "
            "and source attribution embedded in the sentence."
        )
        self.assertIs(validate_manuscript(sample, evidence()), sample)
        rendered = render_packet(scaffold(), manuscript=valid_manuscript(),
                                 as_of="2026-10-10")
        self.assertIn("=== SOURCE APPENDIX — DO NOT EDIT ===", rendered)
        self.assertIn("END OF SOURCE APPENDIX", rendered)

    def test_generated_text_cannot_spoof_editorial_structure(self):
        for malicious in FORGED:
            with self.subTest(payload=repr(malicious)):
                sample = valid_manuscript()
                sample["why_it_matters"] = malicious
                with self.assertRaisesRegex(ValueError, "reserved worksheet"):
                    validate_manuscript(sample, evidence())

    def test_rendering_itself_rejects_forged_headings_even_if_validation_bypassed(self):
        for malicious in FORGED:
            with self.subTest(payload=repr(malicious)):
                sample = valid_manuscript()
                sample["why_it_matters"] = malicious
                with self.assertRaisesRegex(ValueError, "reserved worksheet"):
                    render_packet(scaffold(), manuscript=sample,
                                  as_of="2026-10-10")

    def test_prose_guard_handles_every_model_field_including_focus(self):
        sample = valid_manuscript()
        for field in (
            "title", "dek", "development", "opening_note", "what_stood_out",
            "why_it_matters", "what_was_routine", "what_im_watching_next",
            "cross_desk_comparison", "editorial_questions", "editorial_focus",
        ):
            with self.subTest(field=field):
                mutated = copy.deepcopy(sample)
                mutated[field] = "Normal text.\nSOURCE RECORD IDS: 999"
                with self.assertRaisesRegex(ValueError,
                                            "reserved worksheet structure"):
                    validate_prose_boundaries(mutated)

    def test_non_string_focus_fails_before_renderer_single_line_coercion(self):
        sample = valid_manuscript()
        sample["editorial_focus"] = ["untrusted", "structured", "payload"]
        with self.assertRaisesRegex(ValueError, "non-text prose"):
            render_packet(scaffold(), manuscript=sample, as_of="2026-10-10")

    def test_cli_aborts_before_output_or_smtp_even_if_model_contract_bypassed(self):
        forged = valid_manuscript()
        forged["editorial_questions"] = (
            "Check these claims.\n=== SOURCE APPENDIX — DO NOT EDIT ==="
        )
        with tempfile.TemporaryDirectory() as folder:
            sidecar = Path(folder) / "scaffold.json"
            destination = Path(folder) / "owner-only.txt"
            sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=forged), patch(
                    "core.vietnam_briefs_handoff.load_candidates", return_value=[]), patch(
                    "scripts.sunday_editorial_handoff.send_packet") as mail:
                with self.assertRaisesRegex(ValueError, "reserved worksheet"):
                    main([
                        "--sidecar", str(sidecar), "--out", str(destination),
                        "--full-week", "--write-automatic", "--as-of", "2026-10-10",
                        "--preview-to-owner",
                    ])
                mail.assert_not_called()
            self.assertFalse(destination.exists())

    def test_saturday_full_week_without_research_does_not_load_friday_pack(self):
        # Regression: the Oct 25 scheduled run composed a manuscript, then
        # crashed because the Friday-only Vietnam pack loader rejected a
        # Saturday as-of when the research packet was empty.
        with tempfile.TemporaryDirectory() as folder:
            sidecar = Path(folder) / "scaffold.json"
            destination = Path(folder) / "owner-only.txt"
            sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=valid_manuscript()), patch(
                    "core.vietnam_briefs_handoff.load_candidates") as loader:
                main([
                    "--sidecar", str(sidecar), "--out", str(destination),
                    "--full-week", "--write-automatic", "--as-of", "2026-10-10",
                ])
                loader.assert_not_called()
            self.assertTrue(destination.exists())

    def test_friday_provisional_still_loads_candidate_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            sidecar = Path(folder) / "scaffold.json"
            destination = Path(folder) / "worksheet.txt"
            sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
            with patch("core.vietnam_briefs_handoff.load_candidates",
                       return_value=[]) as loader:
                main(["--sidecar", str(sidecar), "--out", str(destination),
                      "--as-of", "2026-10-09"])
                loader.assert_called_once_with("2026-10-10", "2026-10-09")

    def test_citation_bookkeeping_not_modified(self):
        sample = valid_manuscript()
        citations = copy.deepcopy(sample["citations"])
        validated = validate_manuscript(sample, evidence())
        self.assertEqual(validated["citations"], citations)
        self.assertIs(validated, sample)
        self.assertNotIn("_model_offered_production_ids", sample)


if __name__ == "__main__":
    unittest.main()
