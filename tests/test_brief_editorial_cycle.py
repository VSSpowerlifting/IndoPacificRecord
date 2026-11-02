"""The Sunday receipt gates cycle-derived Briefs by participation, not by date or label."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core import brief_contract as contract
from core.brief_editorial_cycle import (
    COUNT_KEYS, KEY, PROVENANCE_KEY, SCHEMA, cycle_provenance, manuscript_digest,
    receipt_problems,
)
from core.desk_registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
WEEK = "2026-11-07"
PRIMARY = "IPR-" + WEEK
COMPANION = PRIMARY + "-coast-guard"
TRAIL = [{"record_id": "CN-1", "desk": "china", "date": "2026-11-03",
          "url": "https://www.mod.gov.cn/example"}]


def sidecar(**fields):
    """An independently authored Brief: no cycle provenance, no receipt."""
    draft = {"week_start": "2026-11-01", "week_ending": WEEK, "title": "Fixture",
             "manuscript_sha256": "a" * 64, "source_trail": TRAIL}
    draft.update(fields)
    return draft


def cycle(identity=PRIMARY, **fields):
    """A manuscript derived from the weekend cycle Brief ``identity``."""
    return sidecar(**{PROVENANCE_KEY: cycle_provenance(identity)}, **fields)


def reconciled(draft=None, **receipt):
    draft = draft or cycle()
    body = {
        "schema": SCHEMA, "status": "SUNDAY_RECHECKED",
        "identity": draft.get(PROVENANCE_KEY, {}).get("identity", PRIMARY),
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


def graft(draft, receipt_from):
    """``draft`` carrying another manuscript's receipt."""
    return dict(draft, **{KEY: receipt_from[KEY]})


class Participation(unittest.TestCase):
    def test_accepted_briefs_are_independent_and_unchanged(self):
        paths = sorted((ROOT / "briefs").glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(brief=path.name):
                self.assertNotIn(PROVENANCE_KEY, data)
                self.assertNotIn(KEY, data)
                self.assertEqual(receipt_problems(data), [])

    def test_independent_brief_keeps_existing_safeguards_in_any_week(self):
        # No date cut-over: a later independent Brief needs no Sunday receipt,
        # even when it cites exactly the sources a cycle Brief of that week cites.
        for week in (WEEK, "2026-11-14", "2027-01-02"):
            with self.subTest(week=week):
                self.assertEqual(receipt_problems(sidecar(week_ending=week)), [])
        self.assertEqual(cycle()["source_trail"], sidecar()["source_trail"])
        self.assertEqual(receipt_problems(sidecar()), [])
        self.assertTrue(receipt_problems(cycle()))

    def test_cycle_derived_brief_needs_its_own_receipt(self):
        for draft in (cycle(), cycle(manuscript_sha256=None), cycle(COMPANION)):
            with self.subTest(identity=draft[PROVENANCE_KEY]["identity"]):
                self.assertEqual(receipt_problems(draft),
                                 ["cycle-derived Brief requires its own Sunday "
                                  "reconciliation receipt"])
                self.assertEqual(receipt_problems(reconciled(draft)), [])

    def test_derived_versions_cannot_reuse_the_primary_receipt(self):
        primary = reconciled()
        variants = {
            # Split from the primary's packet: same identity, different manuscript.
            "companion from the primary packet": cycle(title="Coast guard companion"),
            # Drafted from its own #946 packet.
            "companion from its own packet": cycle(COMPANION),
            "human rewrite": cycle(title="Rewritten", author="Another writer",
                                   manuscript_sha256="e" * 64),
            "analyst-reconciled version": cycle(body_paragraphs=["Reconciled with analyst"]),
        }
        for name, draft in variants.items():
            with self.subTest(variant=name):
                self.assertTrue(receipt_problems(graft(draft, primary)))
                self.assertEqual(receipt_problems(reconciled(draft)), [])
        self.assertEqual(receipt_problems(graft(cycle(COMPANION), primary)),
                         ["Sunday reconciliation receipt is for a different cycle Brief"])

    def test_stripping_provenance_breaks_the_receipt(self):
        good = reconciled()
        stripped = {k: v for k, v in good.items() if k != PROVENANCE_KEY}
        self.assertEqual(receipt_problems(stripped),
                         ["Sunday reconciliation receipt lacks its editorial cycle provenance"])
        # Re-pointing the marker at another Brief cannot keep the old receipt either.
        moved = dict(good, **{PROVENANCE_KEY: cycle_provenance(COMPANION)})
        self.assertTrue(receipt_problems(moved))

    def test_malformed_or_foreign_week_provenance_is_refused(self):
        marker = cycle_provenance(PRIMARY)
        for bad in (None, "IPR-" + WEEK, dict(marker, schema="other"),
                    dict(marker, week_ending="2026-11-14"), dict(marker, extra=1),
                    {"schema": marker["schema"], "identity": "IPR-" + WEEK + "-Bad_Slug",
                     "week_ending": WEEK},
                    # A cycle week is a real Saturday, not any ten characters.
                    {"schema": marker["schema"], "identity": "IPR-not-a-week",
                     "week_ending": "not-a-week"},
                    {"schema": marker["schema"], "identity": "IPR-2026-11-06",
                     "week_ending": "2026-11-06"}):
            with self.subTest(marker=bad):
                self.assertEqual(receipt_problems(sidecar(**{PROVENANCE_KEY: bad})),
                                 ["invalid weekend editorial cycle provenance"])
        later = cycle("IPR-2026-11-14")
        self.assertEqual(receipt_problems(later),
                         ["weekend editorial cycle provenance is for a different reporting week"])


class ReceiptContract(unittest.TestCase):
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
    NEEDS = "cycle-derived Brief requires its own Sunday reconciliation receipt"

    def accepted(self, **fields):
        source = json.loads(sorted((ROOT / "briefs").glob("*.json"))[0].read_text())
        return dict(source, **fields)

    def test_validate_brief_and_readiness_enforce_the_receipt_on_cycle_briefs(self):
        registry = load_registry()
        source = self.accepted(editorial_status="approved")
        marker = cycle_provenance("IPR-" + source["week_ending"])
        derived = dict(source, **{PROVENANCE_KEY: marker})
        self.assertIn(self.NEEDS, contract.validate_brief(derived, registry))
        draft = dict(derived, editorial_status="draft")
        self.assertNotIn(self.NEEDS, contract.validate_brief(draft, registry))
        self.assertIn(self.NEEDS, contract.validate_readiness(draft, registry))

    def test_independent_brief_validates_exactly_as_before(self):
        # Same sources, same week, no provenance: the existing gates alone apply.
        registry = load_registry()
        source = self.accepted()
        for fields in ({}, {"editorial_status": "draft"}):
            independent = dict(source, **fields)
            with self.subTest(fields=fields):
                self.assertEqual(receipt_problems(independent), [])
                problems = (contract.validate_brief(independent, registry)
                            + contract.validate_readiness(independent, registry))
                self.assertFalse([p for p in problems if "Sunday" in p or "cycle" in p],
                                 problems)

    def test_readiness_recomputes_the_week_inventory(self):
        from scripts import author_brief
        good = reconciled(cycle(source_trail=[], **{"source_mode": "source_linked"}))
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
