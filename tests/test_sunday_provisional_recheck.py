"""Sunday reconciliation of the week's manuscript (no network, no model).

The editorial packet is rendered by the real handoff code and Dylan's revision
by the real DOCX writer; only the read-only database lookups and the local
policy/inventory fingerprints are patched.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import unittest
from contextlib import ExitStack, nullcontext, redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from core.brief_analyst_feedback import reconcile_feedback
from core.brief_analyst_packet import build_packet
from core.brief_editorial_cycle import (
    KEY, PROVENANCE_KEY, SCHEMA, cycle_provenance, digest, receipt_problems,
)
from core.brief_editorial_evidence import load_editorial_evidence
from scripts.import_brief_manuscript import VISIBLE_SIGNALS, cycle_signals, extract
from scripts.import_brief_manuscript import main as import_main
from scripts.sunday_editor_docx import render_editor_docx
from scripts.sunday_editorial_handoff import render_packet
from scripts.weekly_briefs_saturday_audit import (
    main, packet_kind, parse_saturday_packet, sunday_recheck, write_private_receipt,
)
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold as base_scaffold
from tests.test_sunday_automatic_story_selection import selected

NY = ZoneInfo("America/New_York")
SUNDAY = datetime(2026, 10, 11, 15, 0, tzinfo=NY)
AUDIT = "scripts.weekly_briefs_saturday_audit."
BODY = {1: "a" * 300, 2: "b" * 300}
POLICY = {"DECISION_LOG.md": "1" * 64}
REVIEW = {"reviewed_by": "Owner", "review_reference": "source review note 1"}


def scaffold():
    """The shared fixture, with its records dated inside the Oct 4-10 week."""
    draft = base_scaffold()
    for entry, day in zip(draft["source_trail"], ("2026-10-05", "2026-10-06")):
        entry["date"] = day
    return draft


def saturday_receipt(trail):
    first, second = trail[0], trail[1]
    inventory = [{"id": e["record_id"], "desk": e["desk"], "date": e["date"],
                  "reason": "eligible"} for e in trail]
    inventory.append({"id": "JP-W41-01", "desk": "japan", "date": SAT,
                      "reason": "official_link_lane_not_full_text_evidence"})
    pins = [{"id": e["record_id"], "desk": e["desk"], "lane": "production_record",
             "body_sha256": hashlib.sha256(BODY[n].encode()).hexdigest(), "cluster": "c1"}
            for n, e in ((1, first), (2, second))]
    pins.append({"id": "VN-MPS-1791199100", "desk": "vietnam", "lane": "private_research",
                 "body_sha256": "f" * 64, "cluster": "c2"})
    return {"schema": "ipr-sunday-discovery/1", "inventory": inventory,
            "source_pins": pins, "source_accuracy_verified": False,
            "publication_authorized": False, "policy_sha256": digest(POLICY)}


def saturday_packet(receipt, *, provisional=True):
    m = selected()
    m["_story_discovery"] = receipt
    return render_packet(scaffold(), manuscript=m, as_of=SAT,
                         research_evidence=load_editorial_evidence(SAT, SAT),
                         saturday_provisional=provisional)


class SundayRecheck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.trail = scaffold()["source_trail"]
        self.receipt = saturday_receipt(self.trail)
        self.text = saturday_packet(self.receipt)
        self.packet = self.tmp / "sat.txt"
        self.packet.write_text(self.text, encoding="utf-8")
        self.docx = self.tmp / "dylan.docx"
        self.docx.write_bytes(render_editor_docx(self.text))
        self.marker = self.tmp / "marker.txt"
        self.marker.write_text("2026-10-11\n", encoding="utf-8")
        # Refreshed Sunday state; defaults reproduce Saturday exactly.
        self.inventory = [dict(r) for r in self.receipt["inventory"]]
        self.bodies = {self.trail[0]["record_id"]: BODY[1], self.trail[1]["record_id"]: BODY[2]}
        self.current_trail = [dict(e) for e in self.trail]
        self.policy = dict(POLICY)
        self.week_inventory = {"sources": {"record:1": "2" * 64}, "policy": POLICY}
        self.candidate = dict(scaffold(), manuscript_sha256=self.docx_sha())

    def docx_sha(self):
        return hashlib.sha256(self.docx.read_bytes()).hexdigest()

    def fake_choose(self, sidecar, *, as_of, db, discovery_inventory):
        self.assertEqual(as_of, SAT)
        discovery_inventory.extend(dict(r) for r in self.inventory)
        desks = {r["id"]: r["desk"] for r in self.inventory}
        return [({"id": i, "desk_id": desks[i]}, body) for i, body in self.bodies.items()]

    def run_recheck(self, *, review=True, now=SUNDAY, **kwargs):
        sidecar = dict(scaffold(), source_trail=self.current_trail)
        kwargs.setdefault("candidate", self.candidate)
        kwargs.setdefault("revised_docx", self.docx)
        if review:
            kwargs = dict(REVIEW, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(patch(AUDIT + "live_editorial_desks",
                                      return_value=["china", "japan", "vietnam"]))
            stack.enter_context(patch(AUDIT + "read_only", return_value=nullcontext(None)))
            stack.enter_context(patch(AUDIT + "get_articles_for_desks", return_value=[]))
            stack.enter_context(patch(AUDIT + "build_draft", return_value=sidecar))
            stack.enter_context(patch(AUDIT + "policy_snapshot", side_effect=lambda: self.policy))
            stack.enter_context(patch(AUDIT + "inventory",
                                      side_effect=lambda *a, **k: self.week_inventory))
            stack.enter_context(patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                                      side_effect=self.fake_choose))
            return sunday_recheck(SAT, packet_path=self.packet, marker_path=self.marker,
                                  now=now, **kwargs)

    def test_unchanged_week_passes_and_binds_exact_manuscript_and_docx(self):
        public, private, reconciled = self.run_recheck()
        self.assertEqual(public["status"], "SUNDAY_RECHECKED")
        self.assertEqual(public["schema"], SCHEMA)
        self.assertEqual(public["packet_kind"], "saturday_provisional")
        self.assertEqual(public["collection_day"], "2026-10-11")
        self.assertEqual(public["revised_manuscript_sha256"], self.docx_sha())
        self.assertEqual(public["packet_sha256"],
                         hashlib.sha256(self.packet.read_bytes()).hexdigest())
        self.assertEqual(public["inventory_sha256"], digest(self.week_inventory))
        self.assertEqual(public["research_pins_need_human_verification"], 1)
        self.assertEqual(public["source_claim_review"],
                         {"reviewed_by": "Owner", "reference": "source review note 1"})
        self.assertIsNone(public["change_review"])
        self.assertFalse(public["publication_authorized"])
        self.assertFalse(public["complete_week_claimed"])
        self.assertTrue(all(v == [] for v in private["diff"].values()))
        # The reconciled candidate is what the shared publication contract checks.
        self.assertEqual(reconciled[KEY], public)
        self.assertEqual(receipt_problems(reconciled), [])
        edited = dict(reconciled, title="Changed after the recheck")
        self.assertTrue(receipt_problems(edited))

    def test_complete_week_packet_is_reconciled_the_same_way(self):
        self.text = saturday_packet(self.receipt, provisional=False)
        self.packet.write_text(self.text, encoding="utf-8")
        self.docx.write_bytes(render_editor_docx(self.text))
        self.candidate = dict(scaffold(), manuscript_sha256=self.docx_sha())
        public, _, reconciled = self.run_recheck()
        self.assertEqual(public["packet_kind"], "complete_week")
        self.assertEqual(receipt_problems(reconciled), [])

    def test_recheck_stamps_the_packet_provenance_into_the_bound_manuscript(self):
        provenance = cycle_provenance("IPR-" + SAT)
        for marked in (False, True):
            candidate = dict(self.candidate)
            if marked:
                candidate[PROVENANCE_KEY] = provenance
            with self.subTest(candidate_marked=marked):
                _, _, reconciled = self.run_recheck(candidate=candidate)
                self.assertEqual(reconciled[PROVENANCE_KEY], provenance)
                self.assertEqual(receipt_problems(reconciled), [])
                stripped = {k: v for k, v in reconciled.items() if k != PROVENANCE_KEY}
                self.assertTrue(receipt_problems(stripped))

    def test_recheck_refuses_another_briefs_provenance(self):
        other = cycle_provenance("IPR-" + SAT + "-coast-guard")
        with self.assertRaisesRegex(ValueError, "provenance is for another Brief"):
            self.run_recheck(candidate=dict(self.candidate, **{PROVENANCE_KEY: other}))
        # A revised DOCX drafted from the companion's packet cannot be
        # reconciled under the primary packet.
        companion = self.text.replace("Packet: IPR-" + SAT + "\n",
                                      "Packet: IPR-" + SAT + "-coast-guard\n")
        self.docx.write_bytes(render_editor_docx(companion))
        with self.assertRaisesRegex(ValueError, "another Brief's editorial cycle provenance"):
            self.run_recheck(candidate=dict(scaffold(), manuscript_sha256=self.docx_sha()))

    def test_additional_brief_keeps_its_own_identity_and_analyst_return(self):
        # #946: an additional Brief of the week is IPR-<Saturday>-<slug>.
        primary = "Packet: IPR-" + SAT + "\n"
        self.assertEqual(self.text.count(primary), 1)
        self.text = self.text.replace(primary, "Packet: IPR-" + SAT + "-coast-guard\n")
        self.packet.write_text(self.text, encoding="utf-8")
        self.docx.write_bytes(render_editor_docx(self.text))
        self.candidate = dict(scaffold(), manuscript_sha256=self.docx_sha())
        public, _, reconciled = self.run_recheck()
        self.assertEqual(public["identity"], "IPR-" + SAT + "-coast-guard")
        self.assertEqual(receipt_problems(reconciled), [])
        analyst = {"assignment_sha256": "4" * 64, "feedback_sha256": "5" * 64,
                   "state": "ANALYSIS_RECONCILED"}
        with self.assertRaisesRegex(ValueError, "not for this Brief"):
            self.run_recheck(analyst=dict(analyst, packet="IPR-" + SAT))
        bound = self.run_recheck(analyst=dict(analyst, packet="IPR-" + SAT + "-coast-guard"))[0]
        self.assertNotIn("packet", bound["analyst"])
        for bad in ("IPR-" + SAT + "-Coast", "IPR-" + SAT + "-", "IPR-" + SAT + "x"):
            with self.subTest(identity=bad):
                self.packet.write_text(self.text.replace("IPR-" + SAT + "-coast-guard", bad),
                                       encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "requested Saturday edition"):
                    self.run_recheck()
                self.assertTrue(receipt_problems(dict(reconciled, **{
                    KEY: dict(reconciled[KEY], identity=bad)})))

    def test_packet_kind_comes_from_the_packet_head(self):
        self.assertEqual(packet_kind(self.text.split("\n\n", 1)[0]), "saturday_provisional")
        with self.assertRaises(ValueError):
            packet_kind("INDO-PACIFIC RECORD | BRIEFS EDITORIAL WORKSHEET")

    def test_packet_parser_reads_only_appendix_and_receipt(self):
        parsed = parse_saturday_packet(self.packet, saturday=date(2026, 10, 10))
        self.assertEqual(len(parsed["records"]), len(self.trail))
        self.assertEqual(len(parsed["production_pins"]), 2)
        self.assertIn(("str", "JP-W41-01"), parsed["inventory"])

    def test_each_drift_category_holds(self):
        first = self.trail[0]["record_id"]
        cases = {
            "late_saturday_arrivals": lambda: self.inventory.append(
                {"id": 9001, "desk": "china", "date": SAT, "reason": "eligible"}),
            "backdated_arrivals": lambda: self.inventory.append(
                {"id": 9002, "desk": "china", "date": "2026-10-05", "reason": "eligible"}),
            "removed_from_week": lambda: self.inventory.pop(),
            "eligibility_or_metadata_changed": lambda: self.inventory[0].update(
                reason="rights_withdrawn"),
            "pinned_original_changed": lambda: self.bodies.update({first: "changed " * 50}),
            "pinned_original_no_longer_eligible": lambda: self.bodies.pop(first),
            "newly_eligible_originals": lambda: self.bodies.update({9003: "c" * 300}),
            "appendix_records_changed": lambda: self.current_trail.pop(),
            "policy_or_source_versions_changed": lambda: self.policy.update(
                {"config/sources.json": "3" * 64}),
        }
        for key, mutate in cases.items():
            with self.subTest(key=key):
                self.setUp()
                if key == "newly_eligible_originals":
                    self.inventory.append({"id": 9003, "desk": "china", "date": "2026-10-06",
                                           "reason": "eligible"})
                mutate()
                public, private, reconciled = self.run_recheck()
                self.assertEqual(public["status"], "HELD")
                self.assertIsNone(reconciled)
                self.assertIn(key, public["hold_reasons"])
                self.assertGreater(public["counts"][key], 0)
                self.assertTrue(private["diff"][key])
                self.assertNotIn("diff", public)

    def test_packet_without_policy_fingerprint_needs_adjudication(self):
        del self.receipt["policy_sha256"]
        self.packet.write_text(saturday_packet(self.receipt), encoding="utf-8")
        held = self.run_recheck()[0]
        self.assertEqual(held["status"], "HELD")
        self.assertEqual(held["counts"]["policy_or_source_versions_changed"], 1)

    def test_owner_acknowledges_exact_diff_only(self):
        self.inventory.append({"id": 9001, "desk": "china", "date": SAT, "reason": "eligible"})
        held = self.run_recheck()[0]
        self.assertEqual(held["status"], "HELD")
        wrong = self.run_recheck(acknowledge="0" * 64)[0]
        self.assertEqual(wrong["status"], "HELD")
        # An acknowledgement without a named human review does not clear drift.
        unnamed = self.run_recheck(acknowledge=held["diff_sha256"], review=False)[0]
        self.assertEqual(unnamed["status"], "HELD")
        passed, _, reconciled = self.run_recheck(acknowledge=held["diff_sha256"])
        self.assertEqual(passed["status"], "SUNDAY_RECHECKED")
        self.assertEqual(passed["change_review"]["diff_sha256"], held["diff_sha256"])
        self.assertEqual(receipt_problems(reconciled), [])
        # A further change alters the digest, so the old acknowledgement lapses.
        self.inventory.append({"id": 9002, "desk": "china", "date": SAT, "reason": "eligible"})
        again = self.run_recheck(acknowledge=held["diff_sha256"])[0]
        self.assertEqual(again["status"], "HELD")

    def test_named_source_review_is_required(self):
        held = self.run_recheck(review=False)[0]
        self.assertEqual(held["status"], "HELD")
        self.assertIn("source_to_claim_human_review_missing", held["hold_reasons"])

    def test_candidate_must_be_this_week_and_this_docx(self):
        for candidate in (dict(self.candidate, week_ending="2026-10-03"),
                          dict(self.candidate, manuscript_sha256="0" * 64)):
            with self.subTest(candidate=candidate["week_ending"]), \
                    self.assertRaises(ValueError):
                self.run_recheck(candidate=candidate)
        # A frozen manuscript cannot be reconciled without its revised DOCX.
        with self.assertRaisesRegex(ValueError, "revised manuscript DOCX missing"):
            self.run_recheck(revised_docx=None)

    def test_held_analyst_return_holds(self):
        analyst = {"assignment_sha256": "4" * 64, "feedback_sha256": "5" * 64, "state": "HELD",
                   "packet": "IPR-" + SAT}
        held = self.run_recheck(analyst=analyst)[0]
        self.assertIn("analyst_return_held", held["hold_reasons"])
        passed, _, reconciled = self.run_recheck(analyst=dict(analyst, state="REVIEWED"))
        self.assertEqual(passed["status"], "SUNDAY_RECHECKED")
        self.assertEqual(receipt_problems(reconciled), [])

    def rewrite_docx(self, *, document=None, extra=None):
        source = self.tmp / "src.docx"
        shutil.copy(self.docx, source)
        with ZipFile(source) as old, ZipFile(self.docx, "w") as new:
            for item in old.infolist():
                data = old.read(item.filename)
                if item.filename == "word/document.xml" and document:
                    data = document(data)
                new.writestr(item, data)
            for name, data in (extra or {}).items():
                new.writestr(name, data)

    def test_comments_and_tracked_changes_are_hard_holds(self):
        w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
        comment = ('<w:comments {}><w:comment w:id="0"><w:p><w:r><w:t>Source?</w:t>'
                   '</w:r></w:p></w:comment></w:comments>').format(w).encode()
        tracked = lambda xml: xml.replace(
            b"<w:body>", b'<w:body><w:p><w:ins w:id="1"><w:r><w:t>new</w:t></w:r></w:ins></w:p>', 1)
        for name, kwargs in (("comment", {"extra": {"word/comments.xml": comment}}),
                             ("tracked", {"document": tracked})):
            with self.subTest(name=name):
                self.setUp()
                self.rewrite_docx(**kwargs)
                self.candidate = dict(scaffold(), manuscript_sha256=self.docx_sha())
                held = self.run_recheck()[0]
                self.assertEqual(held["status"], "HELD")
                self.assertIn("revised_manuscript_has_unresolved_comments_or_tracked_changes",
                              held["hold_reasons"])
                # No acknowledgement can clear an unresolved editorial question.
                self.assertEqual(self.run_recheck(acknowledge=held["diff_sha256"])[0]["status"],
                                 "HELD")

    def test_needs_a_collection_after_the_week_ended(self):
        for value in ("2026-10-10", "2026-10-12", "", "not-a-date"):
            with self.subTest(marker=value):
                self.marker.write_text(value, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "since the week ended"):
                    self.run_recheck()
        # Dylan's revision may come back on Monday; Monday's collection covers the week.
        self.marker.write_text("2026-10-12", encoding="utf-8")
        monday = datetime(2026, 10, 12, 15, tzinfo=NY)
        self.assertEqual(self.run_recheck(now=monday)[0]["collection_day"], "2026-10-12")
        self.marker.write_text("2026-10-11", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_recheck(now=datetime(2026, 10, 10, 20, tzinfo=NY))

    def test_refuses_receiptless_packets(self):
        ordinary = render_packet(scaffold(), manuscript=manuscript(), as_of=SAT,
                                 research_evidence=load_editorial_evidence(SAT, SAT))
        no_receipt = self.text.replace(
            "DISCOVERY RECEIPT (private, no source body): ", "DISCOVERY NOTE: ")
        for label, text in (("ordinary", ordinary), ("no receipt", no_receipt)):
            with self.subTest(label=label):
                self.packet.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.run_recheck()

    def test_receipt_is_private_and_never_overwritten(self):
        private = self.run_recheck()[1]
        path = self.tmp / "receipt.json"
        write_private_receipt(path, private)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            write_private_receipt(path, private)

    def cli(self, *extra):
        out = io.StringIO()
        private = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, private)
        candidate = self.tmp / "candidate.json"
        candidate.write_text(json.dumps(self.candidate), encoding="utf-8")
        receipt, sidecar = private / "r.json", private / "s.json"
        with patch(AUDIT + "sunday_recheck",
                   side_effect=lambda *a, packet_path, candidate, revised_docx, marker_path,
                   **k: self.run_recheck(**k)), redirect_stdout(out):
            code = main(["--saturday", SAT, "--saturday-packet", str(self.packet),
                         "--candidate", str(candidate), "--revised-docx", str(self.docx),
                         "--receipt-out", str(receipt), "--sidecar-out", str(sidecar),
                         *extra])
        return code, out.getvalue(), receipt, sidecar

    def test_cli_prints_counts_only_and_exits_three_on_hold(self):
        self.inventory.append({"id": 9001, "desk": "china", "date": SAT, "reason": "eligible"})
        code, printed, receipt, sidecar = self.cli("--reviewed-by", "Owner",
                                                   "--review-reference", "note")
        self.assertEqual(code, 3)
        self.assertIn('"HELD"', printed)
        self.assertNotIn("9001", printed)  # exact IDs stay in the private receipt
        self.assertNotIn("Owner", printed)
        late = json.loads(receipt.read_text())["diff"]["late_saturday_arrivals"]
        self.assertEqual(late, [["int", "9001"]])
        self.assertFalse(sidecar.exists())

    def test_cli_writes_reconciled_sidecar_on_pass(self):
        code, _, receipt, sidecar = self.cli("--reviewed-by", "Owner",
                                             "--review-reference", "note")
        self.assertEqual(code, 0)
        self.assertEqual(stat.S_IMODE(os.stat(sidecar).st_mode), 0o600)
        self.assertEqual(receipt_problems(json.loads(sidecar.read_text())), [])

    def analyst_files(self, kind="accepted", week=SAT):
        """A real #956 assignment and owner-reconciled report, nothing mocked."""
        from tests import test_brief_analyst_review as analyst
        text = analyst.worksheet().replace("IPR-2026-11-07", "IPR-" + week)
        manifest = build_packet(text, **analyst.config(text))[0]
        returned = analyst.memo(manifest)
        revised = text.replace(analyst.BEFORE, analyst.AFTER) if kind == "accepted" else text
        report = reconcile_feedback(manifest, returned, revised,
                                    decisions=[analyst.decision(kind)],
                                    owner_review=analyst.owner(returned, revised))
        paths = (self.tmp / "manifest-{}-{}.json".format(kind, week),
                 self.tmp / "feedback-{}-{}.json".format(kind, week))
        for path, data in zip(paths, (manifest, report)):
            path.write_text(json.dumps(data), encoding="utf-8")
        return manifest, report, paths

    def test_cli_binds_a_reconciled_analyst_report(self):
        manifest, report, (m, f) = self.analyst_files()
        code, printed, _, sidecar = self.cli("--reviewed-by", "Owner", "--review-reference",
                                             "note", "--analyst-manifest", str(m),
                                             "--analyst-feedback", str(f))
        self.assertEqual(code, 0)
        bound = json.loads(sidecar.read_text())
        self.assertEqual(bound[KEY]["analyst"], {
            "assignment_sha256": manifest["manifest_sha256"],
            "feedback_sha256": report["feedback_sha256"], "state": "ANALYSIS_RECONCILED"})
        self.assertEqual(receipt_problems(bound), [])
        self.assertNotIn("Fixture owner", printed)

    def test_cli_holds_on_an_unresolved_analyst_finding(self):
        _, report, (m, f) = self.analyst_files("unresolved")
        self.assertEqual(report["state"], "HELD")
        code, printed, receipt, sidecar = self.cli("--reviewed-by", "Owner", "--review-reference",
                                                   "note", "--analyst-manifest", str(m),
                                                   "--analyst-feedback", str(f))
        self.assertEqual(code, 3)
        self.assertIn("analyst_return_held", printed)
        self.assertFalse(sidecar.exists())

    def test_cli_refuses_altered_foreign_or_unpaired_analyst_files(self):
        manifest, report, (m, f) = self.analyst_files("unresolved")
        forged = self.tmp / "forged.json"
        forged.write_text(json.dumps(dict(report, state="ANALYSIS_RECONCILED")), encoding="utf-8")
        _, _, (other_m, other_f) = self.analyst_files(week="2026-10-03")
        for label, extra in (("forged state", ("--analyst-manifest", str(m), "--analyst-feedback", str(forged))),
                             ("other week", ("--analyst-manifest", str(other_m), "--analyst-feedback", str(other_f))),
                             ("mismatched pair", ("--analyst-manifest", str(m), "--analyst-feedback", str(other_f))),
                             ("manifest only", ("--analyst-manifest", str(m)))):
            with self.subTest(label=label):
                with self.assertRaises(SystemExit) as stop:
                    self.cli("--reviewed-by", "Owner", "--review-reference", "note", *extra)
                self.assertEqual(stop.exception.code, 2)

    def test_both_paths_pass_shared_publication_validation_only_as_reconciled(self):
        from core import brief_contract as contract
        from core.desk_registry import load_registry
        self.candidate.update(collection="Indo-Pacific Record Briefs", brief_schema=1)
        _, _, (m, f) = self.analyst_files()
        gate = ("reconcil", "receipt", "Saturday")
        for label, extra in (("no analyst", ()),
                             ("analyst", ("--analyst-manifest", str(m),
                                          "--analyst-feedback", str(f)))):
            with self.subTest(path=label):
                code, _, _, sidecar = self.cli("--reviewed-by", "Owner",
                                               "--review-reference", "note", *extra)
                self.assertEqual(code, 0)
                approved = dict(json.loads(sidecar.read_text()), editorial_status="approved",
                                issue_number=21)
                problems = contract.validate_brief(approved, load_registry())
                self.assertFalse([p for p in problems if any(g in p for g in gate)], problems)
                edited = contract.validate_brief(dict(approved, title="Edited after Sunday"),
                                                 load_registry())
                self.assertIn("Sunday reconciliation does not bind this exact final "
                              "manuscript/week", edited)

    def test_cli_refuses_receipts_inside_the_repository(self):
        candidate = self.tmp / "candidate.json"
        candidate.write_text(json.dumps(self.candidate), encoding="utf-8")
        inside = Path(__file__).resolve().parent / "never-written.json"
        with self.assertRaises(SystemExit) as stop:
            main(["--saturday", SAT, "--saturday-packet", str(self.packet),
                  "--candidate", str(candidate), "--receipt-out", str(inside),
                  "--sidecar-out", str(self.tmp / "s.json")])
        self.assertEqual(stop.exception.code, 2)
        self.assertFalse(inside.exists())


PRIMARY = "IPR-" + SAT
COMPANION = PRIMARY + "-coast-guard"


def edit_in_word(data, *, author="A different writer"):
    """Load-modify-save as an editor would: drop every visible cycle label,
    change the stated author and clear the keywords."""
    from docx import Document
    document = Document(io.BytesIO(data))
    containers = [document] + [part for section in document.sections
                               for part in (section.header, section.footer)]
    for container in containers:
        for paragraph in list(container.paragraphs):
            if any(signal in paragraph.text for signal in VISIBLE_SIGNALS):
                paragraph._element.getparent().remove(paragraph._element)
    document.core_properties.author = author
    document.core_properties.keywords = ""
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def without_custom_property(data):
    """Rewrite the package without the custom-properties part and its references."""
    source, out = ZipFile(io.BytesIO(data)), io.BytesIO()
    with ZipFile(out, "w") as target:
        for info in source.infolist():
            if info.filename == "docProps/custom.xml":
                continue
            body = source.read(info.filename)
            if info.filename in ("_rels/.rels", "[Content_Types].xml"):
                body = re.sub(rb'<(Relationship|Override)[^>]*docProps/custom\.xml"/>', b"", body)
            target.writestr(info, body)
    return out.getvalue()


def drop_hidden_carriers(data, *, docvar=None):
    """Rewrite the package without the custom property; drop or change the docVar."""
    source, out = ZipFile(io.BytesIO(without_custom_property(data))), io.BytesIO()
    with ZipFile(out, "w") as target:
        for info in source.infolist():
            body = source.read(info.filename)
            if info.filename == "word/settings.xml":
                text = body.decode()
                start, end = text.find("<w:docVars>"), text.find("</w:docVars>")
                if docvar is None:
                    text = text[:start] + text[end + len("</w:docVars>"):]
                else:
                    text = text.replace(PRIMARY + '"', docvar + '"')
                body = text.encode()
            target.writestr(info, body)
    return out.getvalue()


class ImportCarriesCycleProvenance(unittest.TestCase):
    """Labels in the DOCX are presentation; hidden provenance is carried forward
    and the sidecar receipt is the gate. Import fails closed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.provisional = saturday_packet(saturday_receipt(scaffold()["source_trail"]))
        self.ordinary = render_packet(scaffold(), manuscript=manuscript(), as_of=SAT,
                                      research_evidence=load_editorial_evidence(SAT, SAT))

    def write(self, data):
        path = self.tmp / "m.docx"
        path.write_bytes(data)
        return path

    def extract(self, data, **declared):
        path = self.write(data)
        return extract(path, expected_sha256=hashlib.sha256(data).hexdigest(),
                       title_index=0, subtitle_index=1, body_start=2, body_stop=3, **declared)

    def test_writer_hides_the_identity_only_in_saturday_provisional_drafts(self):
        with ZipFile(io.BytesIO(render_editor_docx(self.provisional))) as archive:
            self.assertEqual(cycle_signals(archive), ([PRIMARY, PRIMARY], True))
            self.assertIn("docProps/custom.xml", archive.namelist())
        with ZipFile(io.BytesIO(render_editor_docx(self.ordinary))) as archive:
            self.assertEqual(cycle_signals(archive), ([], False))
            self.assertNotIn("docProps/custom.xml", archive.namelist())

    def test_provisional_draft_imports_with_its_provenance(self):
        result = self.extract(render_editor_docx(self.provisional))
        self.assertEqual(result[PROVENANCE_KEY], cycle_provenance(PRIMARY))
        self.assertIn("manuscript_sha256", result)

    def test_word_edits_that_remove_labels_or_change_the_author_keep_provenance(self):
        edited = edit_in_word(render_editor_docx(self.provisional))
        from docx import Document
        properties = Document(io.BytesIO(edited)).core_properties
        self.assertEqual(properties.author, "A different writer")
        with ZipFile(io.BytesIO(edited)) as archive:
            # Every visible signal is gone; only the hidden carriers remain.
            self.assertEqual(cycle_signals(archive), ([PRIMARY, PRIMARY], False))
        self.assertEqual(self.extract(edited)[PROVENANCE_KEY], cycle_provenance(PRIMARY))
        with self.assertRaisesRegex(ValueError, "cannot be imported as an independent Brief"):
            self.extract(edited, independent=True)

    def test_one_surviving_carrier_is_enough(self):
        edited = edit_in_word(without_custom_property(render_editor_docx(self.provisional)))
        self.assertEqual(self.extract(edited)[PROVENANCE_KEY], cycle_provenance(PRIMARY))

    def test_without_hidden_provenance_import_needs_an_honest_declaration(self):
        labelled = drop_hidden_carriers(render_editor_docx(self.provisional))
        with self.assertRaisesRegex(ValueError, "declare --saturday-packet or --independent"):
            self.extract(labelled)
        # A visible label still marks the draft as cycle-derived.
        with self.assertRaisesRegex(ValueError, "cannot be imported as an independent Brief"):
            self.extract(labelled, independent=True)
        self.assertEqual(self.extract(labelled, saturday_packet=self.provisional)[PROVENANCE_KEY],
                         cycle_provenance(PRIMARY))
        bare = edit_in_word(labelled)
        with self.assertRaisesRegex(ValueError, "declare --saturday-packet or --independent"):
            self.extract(bare)

    def test_legacy_complete_week_and_independent_manuscripts(self):
        # Activation stays off: an ordinary packet's DOCX carries no provenance,
        # and imports only once its origin is declared.
        data = render_editor_docx(self.ordinary)
        with self.assertRaisesRegex(ValueError, "declare --saturday-packet or --independent"):
            self.extract(data)
        independent = self.extract(data, independent=True)
        self.assertNotIn(PROVENANCE_KEY, independent)
        self.assertEqual(receipt_problems(dict(scaffold(), **independent)), [])
        declared = self.extract(data, saturday_packet=self.ordinary)
        self.assertEqual(declared[PROVENANCE_KEY], cycle_provenance(PRIMARY))
        self.assertTrue(receipt_problems(dict(scaffold(), **declared)))

    def test_conflicting_provenance_is_refused(self):
        data = render_editor_docx(self.provisional)
        companion = self.provisional.replace("Packet: " + PRIMARY + "\n",
                                              "Packet: " + COMPANION + "\n")
        with self.assertRaisesRegex(ValueError, "different Brief than the packet"):
            self.extract(data, saturday_packet=companion)
        with self.assertRaisesRegex(ValueError, "carriers disagree"):
            # The docVar now says companion; the custom property still says primary.
            source, out = ZipFile(io.BytesIO(data)), io.BytesIO()
            with ZipFile(out, "w") as target:
                for info in source.infolist():
                    body = source.read(info.filename)
                    if info.filename == "word/settings.xml":
                        body = body.replace(PRIMARY.encode() + b'"', COMPANION.encode() + b'"')
                    target.writestr(info, body)
            self.extract(out.getvalue())
        with self.assertRaisesRegex(ValueError, "not a weekend editorial cycle"):
            self.extract(drop_hidden_carriers(data, docvar="IPR-not-a-week"))
        with self.assertRaisesRegex(ValueError, "not both"):
            self.extract(data, saturday_packet=self.provisional, independent=True)
        with self.assertRaisesRegex(ValueError, "no single Packet"):
            self.extract(data, saturday_packet="no header here")

    def test_cli_requires_one_declaration_and_writes_nothing_on_refusal(self):
        path = self.write(render_editor_docx(self.ordinary))
        packet = self.tmp / "packet.txt"
        packet.write_text(self.ordinary, encoding="utf-8")
        out = self.tmp / "out.json"
        args = [str(path), "--expected-sha256", hashlib.sha256(path.read_bytes()).hexdigest(),
                "--title-index", "0", "--subtitle-index", "1", "--body-start", "2",
                "--body-stop", "3", "--out", str(out)]
        for extra in ([], ["--independent", "--saturday-packet", str(packet)]):
            with self.subTest(extra=extra), redirect_stdout(io.StringIO()), \
                    patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as stop:
                import_main(args + extra)
            self.assertEqual(stop.exception.code, 2)
            self.assertFalse(out.exists())
        import_main(args + ["--saturday-packet", str(packet)])
        self.assertEqual(json.loads(out.read_text())[PROVENANCE_KEY], cycle_provenance(PRIMARY))


if __name__ == "__main__":
    unittest.main()
