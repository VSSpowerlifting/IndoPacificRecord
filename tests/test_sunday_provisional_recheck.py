"""Sunday reconciliation of a Saturday provisional draft (no network, no model).

The Saturday packet is rendered by the real handoff code and Dylan's revision
by the real DOCX writer; only the read-only database lookups are patched.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from contextlib import ExitStack, nullcontext
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from core.brief_editorial_evidence import load_editorial_evidence
from scripts.import_brief_manuscript import extract
from scripts.sunday_editor_docx import render_editor_docx
from scripts.sunday_editorial_handoff import render_packet
from scripts.weekly_briefs_saturday_audit import (
    RECHECK_SCHEMA, load_recheck_receipt, main, parse_saturday_packet, sunday_recheck,
    write_private_receipt,
)
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold as base_scaffold
from tests.test_sunday_automatic_story_selection import selected

NY = ZoneInfo("America/New_York")
SUNDAY = datetime(2026, 10, 11, 15, 0, tzinfo=NY)
AUDIT = "scripts.weekly_briefs_saturday_audit."
BODY = {1: "a" * 300, 2: "b" * 300}


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
            "publication_authorized": False}


def saturday_packet(receipt):
    m = selected()
    m["_story_discovery"] = receipt
    return render_packet(scaffold(), manuscript=m, as_of=SAT,
                         research_evidence=load_editorial_evidence(SAT, SAT),
                         saturday_provisional=True)


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

    def fake_choose(self, sidecar, *, as_of, db, discovery_inventory):
        self.assertEqual(as_of, SAT)
        discovery_inventory.extend(dict(r) for r in self.inventory)
        desks = {r["id"]: r["desk"] for r in self.inventory}
        return [({"id": i, "desk_id": desks[i]}, body) for i, body in self.bodies.items()]

    def run_recheck(self, **kwargs):
        sidecar = dict(scaffold(), source_trail=self.current_trail)
        with ExitStack() as stack:
            stack.enter_context(patch(AUDIT + "live_editorial_desks",
                                      return_value=["china", "japan", "vietnam"]))
            stack.enter_context(patch(AUDIT + "read_only", return_value=nullcontext(None)))
            stack.enter_context(patch(AUDIT + "get_articles_for_desks", return_value=[]))
            stack.enter_context(patch(AUDIT + "build_draft", return_value=sidecar))
            stack.enter_context(patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                                      side_effect=self.fake_choose))
            return sunday_recheck(SAT, packet_path=self.packet, revised_docx=self.docx,
                                  marker_path=self.marker, now=SUNDAY, **kwargs)

    def test_unchanged_week_passes_and_binds_exact_docx_bytes(self):
        public, private = self.run_recheck()
        self.assertEqual(public["status"], "SUNDAY_RECHECKED")
        self.assertEqual(public["schema"], RECHECK_SCHEMA)
        self.assertEqual(public["revised_manuscript_sha256"],
                         hashlib.sha256(self.docx.read_bytes()).hexdigest())
        self.assertEqual(public["saturday_packet_sha256"],
                         hashlib.sha256(self.packet.read_bytes()).hexdigest())
        self.assertEqual(public["research_pins_need_human_verification"], 1)
        self.assertFalse(public["publication_authorized"])
        self.assertFalse(public["complete_week_claimed"])
        self.assertTrue(all(v == [] for v in private["diff"].values()))

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
        }
        for key, mutate in cases.items():
            with self.subTest(key=key):
                self.setUp()
                if key == "newly_eligible_originals":
                    self.inventory.append({"id": 9003, "desk": "china", "date": "2026-10-06",
                                           "reason": "eligible"})
                mutate()
                public, private = self.run_recheck()
                self.assertEqual(public["status"], "HELD")
                self.assertIn(key, public["hold_reasons"])
                self.assertGreater(public["counts"][key], 0)
                self.assertTrue(private["diff"][key])
                self.assertNotIn("diff", public)

    def test_owner_acknowledges_exact_diff_only(self):
        self.inventory.append({"id": 9001, "desk": "china", "date": SAT, "reason": "eligible"})
        held, _ = self.run_recheck()
        self.assertEqual(held["status"], "HELD")
        wrong, _ = self.run_recheck(acknowledge="0" * 64)
        self.assertEqual(wrong["status"], "HELD")
        passed, _ = self.run_recheck(acknowledge=held["diff_sha256"])
        self.assertEqual(passed["status"], "SUNDAY_RECHECKED")
        self.assertTrue(passed["owner_acknowledged_changes"])
        # A further change alters the digest, so the old acknowledgement lapses.
        self.inventory.append({"id": 9002, "desk": "china", "date": SAT, "reason": "eligible"})
        again, _ = self.run_recheck(acknowledge=held["diff_sha256"])
        self.assertEqual(again["status"], "HELD")

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
                held, _ = self.run_recheck()
                self.assertEqual(held["status"], "HELD")
                self.assertIn("revised_manuscript_has_unresolved_comments_or_tracked_changes",
                              held["hold_reasons"])
                # No acknowledgement can clear an unresolved editorial question.
                self.assertEqual(self.run_recheck(acknowledge=held["diff_sha256"])[0]["status"],
                                 "HELD")

    def test_refuses_without_sunday_marker_or_on_saturday(self):
        for value in ("2026-10-10", "2026-10-12", ""):
            with self.subTest(marker=value):
                self.marker.write_text(value, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Sunday production update"):
                    self.run_recheck()
        self.marker.write_text("2026-10-11", encoding="utf-8")
        saturday = datetime(2026, 10, 10, 20, tzinfo=NY)
        with self.assertRaises(ValueError), patch(AUDIT + "live_editorial_desks"):
            sunday_recheck(SAT, packet_path=self.packet, revised_docx=self.docx,
                           marker_path=self.marker, now=saturday)

    def test_refuses_non_provisional_or_receiptless_packets(self):
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
        _, private = self.run_recheck()
        path = self.tmp / "receipt.json"
        write_private_receipt(path, private)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            write_private_receipt(path, private)

    def test_cli_prints_counts_only_and_exits_three_on_hold(self):
        import io
        from contextlib import redirect_stdout
        self.inventory.append({"id": 9001, "desk": "china", "date": SAT, "reason": "eligible"})
        out = io.StringIO()
        receipt = self.tmp / "r.json"
        with patch(AUDIT + "sunday_recheck",
                   side_effect=lambda *a, acknowledge, **k: self.run_recheck(
                       acknowledge=acknowledge)), redirect_stdout(out):
            code = main(["--saturday", SAT, "--saturday-packet", str(self.packet),
                         "--revised-docx", str(self.docx), "--receipt-out", str(receipt)])
        self.assertEqual(code, 3)
        printed = out.getvalue()
        self.assertIn('"HELD"', printed)
        self.assertNotIn("9001", printed)  # exact IDs stay in the private receipt
        late = json.loads(receipt.read_text())["diff"]["late_saturday_arrivals"]
        self.assertEqual(late, [["int", "9001"]])


class ImporterGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        text = saturday_packet(saturday_receipt(scaffold()["source_trail"]))
        self.docx = self.tmp / "dylan.docx"
        self.docx.write_bytes(render_editor_docx(text))
        self.sha = hashlib.sha256(self.docx.read_bytes()).hexdigest()

    def receipt(self, **changes):
        data = {"schema": RECHECK_SCHEMA, "status": "SUNDAY_RECHECKED",
                "revised_manuscript_sha256": self.sha, "publication_authorized": False}
        data.update(changes)
        path = self.tmp / ("r%d.json" % len(list(self.tmp.iterdir())))
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def extract(self, path=None, recheck=None):
        return extract(path or self.docx, expected_sha256=hashlib.sha256(
            (path or self.docx).read_bytes()).hexdigest(), title_index=0, subtitle_index=1,
            body_start=2, body_stop=3, provisional_recheck=recheck)

    def test_provisional_docx_needs_matching_passed_recheck(self):
        with self.assertRaisesRegex(ValueError, "Sunday recheck receipt"):
            self.extract()
        for bad in ({"status": "HELD"}, {"revised_manuscript_sha256": "0" * 64},
                    {"schema": "other"}, {"publication_authorized": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.extract(recheck=self.receipt(**bad))
        result = self.extract(recheck=self.receipt())
        self.assertEqual(result["manuscript_sha256"], self.sha)

    def test_ordinary_docx_unaffected(self):
        text = render_packet(scaffold(), manuscript=manuscript(), as_of=SAT,
                             research_evidence=load_editorial_evidence(SAT, SAT))
        path = self.tmp / "ordinary.docx"
        path.write_bytes(render_editor_docx(text))
        self.assertIn("manuscript_sha256", self.extract(path))

    def test_consumer_check_directly(self):
        self.assertEqual(load_recheck_receipt(self.receipt(), manuscript_sha256=self.sha)
                         ["status"], "SUNDAY_RECHECKED")


if __name__ == "__main__":
    unittest.main()
