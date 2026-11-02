"""The Sunday reconciliation receipt is a publication gate, not a DOCX label."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import brief_contract as contract
from core.brief_editorial_cycle import (
    COUNT_KEYS, CUTOVER_WEEK, KEY, SCHEMA, manuscript_digest, receipt_problems,
)
from core.desk_registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
WEEK = CUTOVER_WEEK


def sidecar(**fields):
    draft = {"week_start": "2026-11-01", "week_ending": WEEK, "title": "Fixture",
             "manuscript_sha256": "a" * 64}
    draft.update(fields)
    return draft


def reconciled(draft=None, **receipt):
    draft = draft or sidecar()
    body = {
        "schema": SCHEMA, "status": "SUNDAY_RECHECKED", "identity": "IPR-" + WEEK,
        "week_ending": draft["week_ending"], "collection_day": "2026-11-08",
        "packet_kind": "saturday_provisional", "packet_sha256": "b" * 64,
        "manuscript_sha256": manuscript_digest(draft),
        "revised_manuscript_sha256": draft.get("manuscript_sha256"),
        "inventory_sha256": "c" * 64, "diff_sha256": "d" * 64,
        "counts": dict.fromkeys(COUNT_KEYS, 0), "change_review": None,
        "source_claim_review": {"reviewed_by": "Owner", "reference": "note"},
        "analyst": None, "hold_reasons": [],
        "unresolved_comments_or_tracked_changes": 0,
        "research_pins_need_human_verification": 0,
        "complete_week_claimed": False, "publication_authorized": False,
        "program_verified_facts": False,
    }
    body.update(receipt)
    return dict(draft, **{KEY: body})


class ReceiptContract(unittest.TestCase):
    def test_accepted_briefs_before_the_cutover_are_unchanged(self):
        paths = sorted((ROOT / "briefs").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(brief=path.name):
                self.assertLess(data["week_ending"], CUTOVER_WEEK)
                self.assertEqual(receipt_problems(data), [])

    def test_post_cutover_brief_needs_a_receipt_whatever_the_docx_said(self):
        # A label-stripped DOCX leaves no trace in the sidecar; the week alone decides.
        self.assertTrue(receipt_problems(sidecar()))
        self.assertTrue(receipt_problems(sidecar(manuscript_sha256=None)))
        self.assertEqual(receipt_problems(reconciled()), [])

    def test_receipt_binds_the_exact_manuscript_and_docx(self):
        good = reconciled()
        self.assertTrue(receipt_problems(dict(good, title="Edited after Sunday")))
        self.assertTrue(receipt_problems(dict(good, manuscript_sha256="e" * 64)))
        # Approval metadata may be added without invalidating the receipt.
        self.assertEqual(receipt_problems(dict(good, editorial_status="approved",
                                               issue_number=21)), [])

    def test_receipt_cannot_predate_the_week_or_claim_release(self):
        for change in ({"collection_day": WEEK}, {"status": "HELD"},
                       {"week_ending": "2026-10-31"}, {"identity": "IPR-2026-10-31"},
                       {"packet_kind": "draft"}, {"complete_week_claimed": True},
                       {"publication_authorized": True}, {"program_verified_facts": True},
                       {"unresolved_comments_or_tracked_changes": 1},
                       {"source_claim_review": None}, {"inventory_sha256": "x"}):
            with self.subTest(change=change):
                self.assertTrue(receipt_problems(reconciled(**change)))

    def test_drift_needs_an_exact_diff_adjudication(self):
        counts = dict.fromkeys(COUNT_KEYS, 0)
        counts["policy_or_source_versions_changed"] = 1
        self.assertTrue(receipt_problems(reconciled(counts=counts)))
        review = {"reviewed_by": "Owner", "reference": "note", "diff_sha256": "0" * 64}
        self.assertTrue(receipt_problems(reconciled(counts=counts, change_review=review)))
        review["diff_sha256"] = "d" * 64
        self.assertEqual(receipt_problems(reconciled(counts=counts, change_review=review)), [])
        # An adjudication with nothing to adjudicate is inconsistent accounting.
        self.assertTrue(receipt_problems(reconciled(change_review=review)))

    def test_held_or_unbound_analyst_return_blocks(self):
        bound = {"assignment_sha256": "1" * 64, "feedback_sha256": "2" * 64}
        self.assertTrue(receipt_problems(reconciled(analyst=dict(bound, state="HELD"))))
        self.assertTrue(receipt_problems(reconciled(analyst={"state": "REVIEWED"})))
        self.assertEqual(receipt_problems(reconciled(analyst=dict(bound, state="REVIEWED"))), [])


class SharedValidation(unittest.TestCase):
    def test_validate_brief_and_readiness_enforce_the_receipt(self):
        registry = load_registry()
        source = json.loads(sorted((ROOT / "briefs").glob("*.json"))[0].read_text())
        source["week_ending"] = WEEK
        source["editorial_status"] = "approved"
        approved = contract.validate_brief(source, registry)
        self.assertIn("requires a Sunday reconciliation receipt for the complete reporting week",
                      approved)
        draft = dict(source, editorial_status="draft")
        self.assertNotIn("requires a Sunday reconciliation receipt for the complete reporting week",
                         contract.validate_brief(draft, registry))
        self.assertIn("requires a Sunday reconciliation receipt for the complete reporting week",
                      contract.validate_readiness(draft, registry))

    def test_readiness_recomputes_the_week_inventory(self):
        from scripts import author_brief
        good = reconciled(sidecar(source_trail=[], **{"source_mode": "source_linked"}))
        with patch.object(author_brief, "validate_readiness", return_value=[]), \
                patch("core.brief_source_linked.is_source_linked", return_value=True), \
                patch("scripts.weekly_briefs_saturday_audit.inventory_sha256",
                      return_value="c" * 64):
            self.assertEqual(author_brief.readiness_problems(good, [], ":memory:"), [])
        with patch.object(author_brief, "validate_readiness", return_value=[]), \
                patch("core.brief_source_linked.is_source_linked", return_value=True), \
                patch("scripts.weekly_briefs_saturday_audit.inventory_sha256",
                      return_value="9" * 64):
            self.assertEqual(author_brief.readiness_problems(good, [], ":memory:"),
                             ["Sunday source inventory or rights/policy files changed; "
                              "reconcile again"])


if __name__ == "__main__":
    unittest.main()
