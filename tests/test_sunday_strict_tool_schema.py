"""Offline contracts for the complete Sunday strict-tool request.

Reference (checked 2026-10-27):
https://platform.claude.com/docs/en/build-with-claude/structured-outputs#json-schema-limitations
Unknown schema constructs fail closed;
this checks the subset we use, not provider-side grammar compilation or prose.
"""
import copy
import itertools
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.brief_editorial_evidence import load_editorial_evidence
from core.brief_story_discovery import (
    NoQualifyingStory, discovery_packet, validate_selection,
)
from scripts.sunday_briefs_auto_writer import compose, validate_manuscript
from tests.briefs_narrative_fixtures import article_manuscript, legacy_manuscript
from tests.test_briefs_editorial_evidence import SAT, scaffold
from tests.test_sunday_story_discovery import decision, proposal
from tests.test_weekly_briefs_auto_writer import evidence


class CapturedRequest(Exception):
    """Stop at the transport boundary without a network/model request."""


class StrictToolSchemaTests(unittest.TestCase):
    def assert_compatible(self, schema, path="input_schema"):
        allowed = {"type", "properties", "required", "additionalProperties",
                   "items", "enum", "minItems", "description", "anyOf"}
        self.assertIsInstance(schema, dict, path)
        self.assertFalse(set(schema) - allowed, (path, set(schema) - allowed))
        if "type" in schema:
            types = schema["type"]
            types = types if isinstance(types, list) else [types]
            self.assertTrue(types, path)
            self.assertTrue(set(types) <= {
                "object", "array", "string", "integer", "number", "boolean", "null"}, path)
        if schema.get("type") == "object":
            self.assertIs(schema.get("additionalProperties"), False, path)
            self.assertEqual(set(schema["required"]), set(schema["properties"]), path)
        if "minItems" in schema:
            self.assertIs(type(schema["minItems"]), int, path)
            self.assertIn(schema["minItems"], (0, 1), path)
        if "enum" in schema:
            self.assertTrue(schema["enum"], path)
            self.assertTrue(all(v is None or type(v) in (str, int, float, bool)
                                for v in schema["enum"]), path)
        for name, child in schema.get("properties", {}).items():
            self.assert_compatible(child, path + ".properties." + name)
        if "items" in schema:
            self.assert_compatible(schema["items"], path + ".items")
        for index, child in enumerate(schema.get("anyOf", [])):
            self.assert_compatible(child, path + ".anyOf[{}]".format(index))

    def test_actual_assembled_request_across_all_writer_modes(self):
        research = load_editorial_evidence(SAT, SAT)
        for automatic, article, supplemental in itertools.product((False, True), repeat=3):
            with self.subTest(automatic=automatic, article=article, supplemental=supplemental):
                stream = Mock(side_effect=CapturedRequest)
                client = SimpleNamespace(messages=SimpleNamespace(stream=stream))
                with patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                           return_value=evidence()), patch(
                        "core.daily_machine_records.editorial_candidates", return_value=[]):
                    with self.assertRaises(CapturedRequest):
                        compose(scaffold(), SAT, client=client,
                                supplemental=research if supplemental else (),
                                automatic_story_selection=automatic, article_first=article)
                stream.assert_called_once()
                request = stream.call_args.kwargs
                self.assertEqual(request["model"], "claude-sonnet-4-6")
                self.assertEqual(request["max_tokens"], 5400 if automatic else 4600)
                self.assertEqual(request["tool_choice"],
                                 {"type": "tool", "name": "compose_editorial_draft"})
                self.assertEqual(len(request["tools"]), 1)
                tool = request["tools"][0]
                self.assertIs(tool["strict"], True)
                schema = tool["input_schema"]
                self.assert_compatible(schema)
                props = schema["properties"]
                self.assertEqual("article" in props, article)
                self.assertEqual("story_selection" in props, automatic)
                citations = (props["article"]["items"]["properties"] if article
                             else props["citations"]["properties"])
                numeric = citations["citations"] if article else citations["development"]
                self.assertEqual(numeric["items"]["enum"], [1, 2])
                self.assertEqual("editorial_focus" in props, supplemental)
                if supplemental:
                    external = (citations["supplemental_citations"] if article else
                                props["supplemental_citations"]["properties"]["development"])
                    self.assertEqual(external["items"]["enum"], sorted(r["id"] for r in research))

    def test_recursive_check_rejects_nested_unsupported_keywords_and_min_items(self):
        for keyword, value in (("maxItems", 5), ("uniqueItems", True),
                               ("minimum", 0), ("maximum", 5), ("minItems", 2)):
            with self.subTest(keyword=keyword):
                nested = {"type": "array", "items": {"anyOf": [
                    {"type": "array", "items": {"type": "integer"}, keyword: value}]}}
                with self.assertRaises(AssertionError):
                    self.assert_compatible(nested)


class LocalSelectionConstraintsTests(unittest.TestCase):
    def setUp(self):
        self.research = load_editorial_evidence(SAT, SAT)[:1]
        self.packet = discovery_packet(evidence(), self.research)
        option = proposal(self.packet, [1, self.research[0]["id"]],
                          values=(2, 2, 2, 2, 2), readiness="review", connection=True)
        source = next(s for s in self.packet["sources"] if s["id"] == 2)
        option["counterevidence_ids"] = [2]
        option["evidence_notes"].append({"id": 2, "excerpt": source["excerpts"][0][:40]})
        self.selection = decision([option], None)
        validate_selection(self.selection, self.packet)

    def test_candidate_and_evidence_note_bounds_still_reject_invalid_output(self):
        selection = copy.deepcopy(self.selection)
        selection["candidates"] *= 6
        with self.assertRaisesRegex(ValueError, "up to five"):
            validate_selection(selection, self.packet)
        for count in (0, 11):
            with self.subTest(notes=count):
                selection = copy.deepcopy(self.selection)
                option = selection["candidates"][0]
                option["evidence_notes"] = (option["evidence_notes"] * 4)[:count]
                with self.assertRaisesRegex(ValueError, "content evidence notes"):
                    validate_selection(selection, self.packet)

    def test_uniqueness_of_production_research_and_counterevidence_is_still_required(self):
        for field in ("production_ids", "research_ids", "counterevidence_ids"):
            with self.subTest(field=field):
                selection = copy.deepcopy(self.selection)
                selection["candidates"][0][field] *= 2
                with self.assertRaisesRegex(ValueError, "source IDs|counterevidence"):
                    validate_selection(selection, self.packet)

    def test_all_score_ranges_and_integer_types_are_still_required(self):
        for field in self.selection["candidates"][0]["scores"]:
            for value in (-1, 6, True, 2.5, "4"):
                with self.subTest(field=field, value=value):
                    selection = copy.deepcopy(self.selection)
                    selection["candidates"][0]["scores"][field] = value
                    with self.assertRaisesRegex(ValueError, "0..5 integers"):
                        validate_selection(selection, self.packet)

    def test_valid_note_and_score_boundaries_remain_accepted(self):
        selection = copy.deepcopy(self.selection)
        option = selection["candidates"][0]
        option["evidence_notes"] += [option["evidence_notes"][0]] * 7
        validate_selection(selection, self.packet)
        for value in (0, 5):
            option["scores"] = dict.fromkeys(option["scores"], value)
            validate_selection(selection, self.packet)

    def test_exact_source_identities_and_content_anchors_remain_required(self):
        for field, bad in (("production_ids", 999), ("production_ids", True),
                           ("research_ids", "JP-UNAVAILABLE"), ("counterevidence_ids", 999)):
            with self.subTest(field=field, bad=bad):
                selection = copy.deepcopy(self.selection)
                selection["candidates"][0][field] = [bad]
                with self.assertRaises(ValueError):
                    validate_selection(selection, self.packet)
        selection = copy.deepcopy(self.selection)
        selection["candidates"][0]["evidence_notes"][0]["excerpt"] = (
            "An invented content anchor that no offered source contains.")
        with self.assertRaisesRegex(ValueError, "not present"):
            validate_selection(selection, self.packet)

    def test_abstention_and_manuscript_citation_integrity_remain_required(self):
        invalid = copy.deepcopy(self.selection)
        invalid["selected_slug"] = invalid["candidates"][0]["slug"]
        with self.assertRaisesRegex(ValueError, "must explicitly abstain"):
            validate_selection(invalid, self.packet)
        for article in (False, True):
            with self.subTest(article=article):
                manuscript = article_manuscript() if article else legacy_manuscript()
                manuscript["story_selection"] = decision([], None)
                with self.assertRaises(NoQualifyingStory):
                    validate_manuscript(manuscript, evidence(), automatic_story_selection=True)
                manuscript.pop("story_selection")
                if article:
                    manuscript["article"][0]["citations"] = [999]
                else:
                    manuscript["citations"]["development"] = [999]
                with self.assertRaisesRegex(ValueError, "source ids"):
                    validate_manuscript(manuscript, evidence())
