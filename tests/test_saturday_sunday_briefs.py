"""Offline cycle regression: no real model, SMTP, corpus mutation or release."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import saturday_sunday_briefs as cycle
from scripts.sunday_briefs_auto_writer import article_instruction
from scripts.sunday_editorial_handoff import render_packet
from scripts.sunday_send_reviewed_packet import validate_file
from tests.briefs_narrative_fixtures import article_manuscript, scaffold, evidence
from tests.test_sunday_story_discovery import source

SAT = "2026-10-10"
SATURDAY = datetime.fromisoformat("2026-10-10T13:00:00-04:00")
SUNDAY = datetime.fromisoformat("2026-10-11T16:00:00-04:00")


def snapshot(sources=None):
    return {"week_start": "2026-10-04", "week_ending": SAT,
            "sources": sources or {"record:1": "a"}, "policy": {"policy": "b"},
            "desks": ["china", "singapore"]}


def state():
    return {"schema": cycle.SCHEMA, "identity": "IPR-" + SAT,
            "status": "SATURDAY_PROVISIONAL", "inventory": snapshot(),
            "packet_sha256": "a" * 64,
            "window": {"week_start": "2026-10-04", "week_ending": SAT}}


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.marker = self.directory / "marker"
        self.marker.write_text(SAT)

    def test_calendar_marker_early_late_and_naive_clock(self):
        for marker in ("", "2026-10-09", "2026-10-11"):
            self.marker.write_text(marker)
            with self.assertRaisesRegex(ValueError, "marker"):
                cycle.collection_window(SAT, "saturday", now=SATURDAY, marker_path=self.marker)
        self.marker.write_text(SAT)
        for clock in (datetime.fromisoformat("2026-10-10T12:29:00-04:00"),
                      SUNDAY, datetime(2026, 10, 10, 13)):
            with self.assertRaises(ValueError):
                cycle.collection_window(SAT, "saturday", now=clock, marker_path=self.marker)
        late = datetime.fromisoformat("2026-10-11T02:30:00+00:00")
        self.assertEqual(cycle.collection_window(SAT, "saturday", now=late,
                         marker_path=self.marker)["collection_day"], SAT)

    def test_dst_local_target(self):
        for day, clock in (("2027-03-20", "2027-03-20T16:30:00+00:00"),
                           ("2027-11-13", "2027-11-13T17:30:00+00:00")):
            self.marker.write_text(day)
            result = cycle.collection_window(day, "saturday", now=datetime.fromisoformat(clock),
                                             marker_path=self.marker)
            self.assertEqual(result["collection_day"], day)
            self.assertFalse(result["capture_completeness_verified"])

    def test_provisional_prompt_and_worksheet_never_claim_saturday_complete(self):
        text = render_packet(scaffold(), manuscript=article_manuscript(), as_of=SAT,
                             saturday_provisional=True)
        self.assertIn("SATURDAY PROVISIONAL; DAY NOT COMPLETE", text)
        self.assertNotIn("SATURDAY COMPLETE", text)
        prompt = article_instruction("2026-10-04", SAT, SAT, [1, 2], [], "evidence", "",
                                     saturday_provisional=True)
        self.assertIn("Saturday has NOT ended", prompt)
        self.assertNotIn("Saturday has elapsed", prompt)
        self.assertEqual(text.splitlines()[1], "Packet: IPR-" + SAT)
        packet = self.directory / "draft.txt"
        packet.write_text(text)
        validate_file(packet, SAT, now=SATURDAY, saturday_provisional=True)
        with self.assertRaisesRegex(ValueError, "has not ended"):
            validate_file(packet, SAT, now=SATURDAY)

    def test_same_day_sunday_marker_and_accepted_draft_required(self):
        with self.assertRaisesRegex(ValueError, "marker"):
            cycle.reconcile(state(), scaffold(), marker_path=self.marker, now=SUNDAY)
        self.marker.write_text("2026-10-11")
        s = state(); s["status"] = "PREPARED_NO_MODEL"
        with self.assertRaisesRegex(ValueError, "accepted Saturday"):
            cycle.reconcile(s, scaffold(), marker_path=self.marker, now=SUNDAY)

    def test_full_inventory_backdated_source_and_original_status_or_rights_drift_hold(self):
        self.marker.write_text("2026-10-11")
        variants = [snapshot({"record:1": "a", "record:late-saturday": "late"}),
                    snapshot({"record:1": "changed-original-or-hold"}),
                    {**snapshot(), "policy": {"policy": "new-rights"}},
                    {**snapshot(), "desks": ["china", "japan"]}]
        for current in variants:
            with self.subTest(current=current), patch.object(cycle, "inventory", return_value=current):
                r = cycle.reconcile(state(), scaffold(), marker_path=self.marker, now=SUNDAY,
                                    reviewed_by="Synthetic owner", review_reference="fixture review")
                self.assertEqual(r["status"], "HELD")
                self.assertFalse(r["program_verified_facts"])

    def test_exact_diff_human_adjudication_allows_resolved_late_evidence(self):
        self.marker.write_text("2026-10-11")
        current = snapshot({"record:1": "a", "record:late-saturday": "late"})
        manuscript = scaffold()
        decisions = {"added:record:late-saturday": {
            "disposition": "resolved", "reason": "Owner compared original; routine unrelated notice.",
            "reviewed_by": "Synthetic owner", "reference": "fixture review 1",
            "inventory_sha256": cycle.digest(current),
            "manuscript_sha256": cycle.manuscript_digest(manuscript)}}
        with patch.object(cycle, "inventory", return_value=current):
            r = cycle.reconcile(state(), manuscript, marker_path=self.marker, now=SUNDAY,
                                reviewed_by="Synthetic owner", review_reference="fixture claim check",
                                decisions=decisions)
            self.assertEqual(r["status"], "SUNDAY_RECHECKED")
            decisions["added:record:late-saturday"]["manuscript_sha256"] = "wrong"
            self.assertEqual(cycle.reconcile(state(), manuscript, marker_path=self.marker, now=SUNDAY,
                reviewed_by="Synthetic owner", review_reference="fixture", decisions=decisions)["status"], "HELD")

    def test_recheck_does_not_infer_review_and_exact_final_prose_is_bound(self):
        self.marker.write_text("2026-10-11")
        manuscript = scaffold()
        with patch.object(cycle, "inventory", return_value=snapshot()):
            held = cycle.reconcile(state(), manuscript, marker_path=self.marker, now=SUNDAY)
            self.assertEqual(held["status"], "HELD")
            receipt = cycle.reconcile(state(), manuscript, marker_path=self.marker, now=SUNDAY,
                                      reviewed_by="Synthetic owner", review_reference="fixture source check")
            manuscript["saturday_sunday_cycle"] = receipt
            self.assertEqual(cycle.readiness_problems(manuscript), [])
            manuscript["title"] = "A changed assertion"
            self.assertTrue(cycle.readiness_problems(manuscript))

    def test_provisional_receipt_reaches_actual_author_readiness(self):
        from scripts.author_brief import readiness_problems
        manuscript = scaffold()
        manuscript["saturday_sunday_cycle"] = {"schema": cycle.SCHEMA, "status": "SATURDAY_PROVISIONAL"}
        # Existing factual/publication gates remain in addition to the cycle hold.
        with patch("scripts.author_brief.validate_readiness", return_value=[]), \
             patch("scripts.author_brief.read_only"), \
             patch("scripts.author_brief.get_articles_for_desks", return_value=[]):
            self.assertIn("Saturday provisional manuscript requires Sunday reconciliation",
                          readiness_problems(manuscript, [], "unused"))

    def test_prepare_reuses_accepted_draft_and_never_pays_twice(self):
        from contextlib import nullcontext
        rows = [source(1, "china"), source(2, "singapore")]
        target = self.directory / "cycle"; target.mkdir(mode=0o700)
        with patch.object(cycle, "live_editorial_desks", return_value=["china", "singapore"]), \
             patch.object(cycle, "read_only", return_value=nullcontext(None)), \
             patch.object(cycle, "get_articles_for_desks", return_value=rows), \
             patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_briefs_auto_writer.choose_evidence", return_value=evidence()), \
             patch("scripts.sunday_briefs_auto_writer.compose", return_value=article_manuscript()) as model:
            first = cycle.prepare(SAT, target, marker_path=self.marker, now=SATURDAY, execute_model=True)
            second = cycle.prepare(SAT, target, marker_path=self.marker, now=SATURDAY, execute_model=True)
            self.assertEqual(first, second)
            self.assertEqual(model.call_count, 1)
            self.assertTrue((target / ("IPR-Briefs-Editorial-" + SAT + ".docx")).is_file())

    def test_preparation_no_model_is_safe_and_repeatable(self):
        from contextlib import nullcontext
        rows = [source(1, "china"), source(2, "singapore")]
        target = self.directory / "cycle"; target.mkdir(mode=0o700)
        with patch.object(cycle, "live_editorial_desks", return_value=["china", "singapore"]), \
             patch.object(cycle, "read_only", return_value=nullcontext(None)), \
             patch.object(cycle, "get_articles_for_desks", return_value=rows), \
             patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_briefs_auto_writer.choose_evidence", return_value=evidence()), \
             patch("scripts.sunday_briefs_auto_writer.compose") as model:
            for _ in range(2):
                self.assertEqual(cycle.prepare(SAT, target, marker_path=self.marker, now=SATURDAY)["status"],
                                 "PREPARED_NO_MODEL")
            model.assert_not_called()
            saved = json.loads((target / ("IPR-" + SAT + ".scaffold.json")).read_text())
            self.assertEqual(saved["saturday_sunday_cycle"]["status"], "SATURDAY_PROVISIONAL")

    def test_private_outputs_reject_own_or_sibling_git_checkout(self):
        sibling = self.directory / "sibling"; sibling.mkdir()
        (sibling / ".git").write_text("gitdir: elsewhere")
        for directory in (cycle.ROOT / "private-output", sibling / "private-output"):
            with self.assertRaisesRegex(ValueError, "outside"):
                cycle.private_directory(directory)

    def delivery_state(self):
        packet_name = "IPR-Briefs-Editorial-" + SAT + ".txt"
        packet = render_packet(scaffold(), manuscript=article_manuscript(), as_of=SAT,
                               saturday_provisional=True)
        cycle.write_private(self.directory / packet_name, packet)
        return {**state(), "packet_file": packet_name,
                "packet_sha256": cycle.hashlib.sha256(packet.encode()).hexdigest()}

    def test_editor_no_send_rehearsal_is_safe_and_default(self):
        s = self.delivery_state()
        with patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            r = cycle.deliver(s, self.directory, now=SATURDAY, marker_path=self.marker)
            self.assertFalse(r["email_sent"])
            smtp.assert_not_called()

    def test_editor_once_only_reservation_and_ambiguous_failure_hold(self):
        s = self.delivery_state()
        env = {"IPR_EDITOR_TO": "editor@example.invalid", "IPR_PREVIEW_TO": "owner@example.invalid",
               "IPR_EDITOR_DELIVERY_ENABLED": "false", "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "false"}
        with patch.object(cycle, "inventory", return_value=snapshot()), \
             patch.dict(os.environ, env), patch("scripts.sunday_editorial_handoff.send_packet",
                                                side_effect=RuntimeError("simulated SMTP failure")) as smtp:
            kwargs = dict(now=SATURDAY, marker_path=self.marker, send=True,
                          owner_confirmed=True, approved_sha256=s["packet_sha256"])
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                cycle.deliver(s, self.directory, **kwargs)
            with self.assertRaises(FileExistsError):
                cycle.deliver(s, self.directory, **kwargs)
            self.assertEqual(smtp.call_count, 1)
        receipts = list(self.directory.glob("dispatch-*.json"))
        self.assertEqual(len(receipts), 1)
        self.assertNotIn("EDITOR_SENT", receipts[0].read_text())

    def test_editor_exact_approval_and_legacy_mutual_exclusion(self):
        s = self.delivery_state()
        kwargs = dict(now=SATURDAY, marker_path=self.marker, send=True,
                      owner_confirmed=True, approved_sha256=s["packet_sha256"])
        with patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            with self.assertRaisesRegex(ValueError, "exact attachment"):
                cycle.deliver(s, self.directory, **{**kwargs, "approved_sha256": "wrong"})
            with patch.dict(os.environ, {"IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "true"}):
                with self.assertRaisesRegex(ValueError, "legacy"):
                    cycle.deliver(s, self.directory, **kwargs)
            smtp.assert_not_called()

    def test_mock_editor_delivery_freezes_the_exact_file_before_send(self):
        s = self.delivery_state()
        env = {"IPR_EDITOR_TO": "editor@example.invalid", "IPR_PREVIEW_TO": "owner@example.invalid",
               "IPR_EDITOR_DELIVERY_ENABLED": "false", "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "false"}
        def simulated_send(packet, week, **kwargs):
            self.assertEqual(cycle.hashlib.sha256(packet.read_bytes()).hexdigest(), s["packet_sha256"])
            self.assertTrue(kwargs["saturday_provisional"])
            self.assertTrue(kwargs["owner_released"])
            self.assertEqual(week, SAT)
        with patch.object(cycle, "inventory", return_value=snapshot()), \
             patch.dict(os.environ, env), patch("scripts.sunday_editorial_handoff.send_packet", simulated_send):
            r = cycle.deliver(s, self.directory, now=SATURDAY, marker_path=self.marker,
                              send=True, owner_confirmed=True, approved_sha256=s["packet_sha256"])
            self.assertEqual(r["status"], "EDITOR_SENT")

    def test_full_week_legacy_behavior_and_workflow_freeze_preserved(self):
        old = render_packet(scaffold(), manuscript=article_manuscript(), as_of=SAT)
        self.assertIn("SATURDAY COMPLETE", old)
        yaml = (cycle.ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml").read_text()
        self.assertIn("IPR_SATURDAY_SUNDAY_CYCLE_ENABLED != 'true'", yaml)

    def test_actual_sqlite_week_inventory_includes_late_original_and_machine_state(self):
        database = self.directory / "fixture.db"
        with sqlite3.connect(database) as conn:
            conn.executescript("""
              CREATE TABLE sources(id INTEGER, slug TEXT, display_name TEXT, desk_id TEXT, language TEXT);
              CREATE TABLE articles(id INTEGER, source_id INTEGER, published_date TEXT,
                                    text_original TEXT, processing_state TEXT);
              CREATE TABLE regional_official_source_links(source_family TEXT,source_identity TEXT,
                                    publisher_posted_date TEXT);
              CREATE TABLE daily_machine_records(source_family TEXT,source_identity TEXT,
                                    summary TEXT,publication_state TEXT);
              INSERT INTO sources VALUES(1,'fixture','Fixture official source','china','en');
              INSERT INTO articles VALUES(1,1,'2026-10-08','original text','complete');
              INSERT INTO regional_official_source_links VALUES('fixture','official:1','2026-10-10');
              INSERT INTO daily_machine_records VALUES('fixture','official:1','machine explanation','released');
            """)
        before = cycle.inventory(SAT, database=database, desks=["china"], root=self.directory)
        with sqlite3.connect(database) as conn:
            conn.execute("INSERT INTO articles VALUES(2,1,'2026-10-10','late Saturday original','complete')")
        late = cycle.inventory(SAT, database=database, desks=["china"], root=self.directory)
        self.assertEqual(cycle.compare(before, late)["added"], ["record:2"])
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE articles SET text_original='changed original',processing_state='paused' WHERE id=1")
            conn.execute("UPDATE daily_machine_records SET summary='changed explanation',publication_state='held'")
        changed = cycle.inventory(SAT, database=database, desks=["china"], root=self.directory)
        self.assertEqual(cycle.compare(late, changed)["changed"], ["machine:fixture:official:1", "record:1"])

    def test_editor_delivery_holds_fresh_source_or_permissions_drift(self):
        s = self.delivery_state()
        for current in (snapshot({"record:1": "changed"}), {**snapshot(), "policy": {"policy": "changed"}}):
            with patch.object(cycle, "inventory", return_value=current), \
                 patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
                with self.assertRaisesRegex(ValueError, "permissions changed"):
                    cycle.deliver(s, self.directory, now=SATURDAY, marker_path=self.marker,
                                  send=True, owner_confirmed=True, approved_sha256=s["packet_sha256"])
                smtp.assert_not_called()

    def test_shared_release_contract_refuses_tagged_provisional_approval(self):
        from core.brief_contract import validate_brief
        from core.desk_registry import load_registry
        manuscript = scaffold()
        manuscript.update(collection="Indo-Pacific Record Briefs", editorial_status="approved", issue_number=99,
                          saturday_sunday_cycle={"schema": cycle.SCHEMA, "status": "SATURDAY_PROVISIONAL"})
        self.assertIn("Saturday provisional manuscript requires Sunday reconciliation",
                      validate_brief(manuscript, load_registry(), unreconciled=frozenset()))

    def test_explicit_model_abstention_preserves_private_decision_without_retry(self):
        from contextlib import nullcontext
        from core.brief_story_discovery import NoQualifyingStory
        target = self.directory / "cycle"; target.mkdir(mode=0o700)
        rows = [source(1, "china"), source(2, "singapore")]
        with patch.object(cycle, "live_editorial_desks", return_value=["china", "singapore"]), \
             patch.object(cycle, "read_only", return_value=nullcontext(None)), \
             patch.object(cycle, "get_articles_for_desks", return_value=rows), \
             patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_briefs_auto_writer.choose_evidence", return_value=evidence()), \
             patch("scripts.sunday_briefs_auto_writer.compose", side_effect=NoQualifyingStory(
                 {"selection_rationale": "No supported new development in fixture."})) as model:
            for _ in range(2):
                r = cycle.prepare(SAT, target, marker_path=self.marker, now=SATURDAY, execute_model=True)
                self.assertEqual(r["status"], "ABSTAINED_NO_QUALIFYING_STORY")
            self.assertEqual(model.call_count, 1)
            self.assertTrue((target / ("IPR-" + SAT + ".selection.json")).is_file())
            self.assertFalse(list(target.glob("*.txt")))

    def test_no_analyst_flow_from_draft_through_return_to_sunday_receipt(self):
        from contextlib import nullcontext
        from scripts.validate_editorial_return import validate_return
        target = self.directory / "cycle"; target.mkdir(mode=0o700)
        rows = [source(1, "china"), source(2, "singapore")]
        with patch.object(cycle, "live_editorial_desks", return_value=["china", "singapore"]), \
             patch.object(cycle, "read_only", return_value=nullcontext(None)), \
             patch.object(cycle, "get_articles_for_desks", return_value=rows), \
             patch.object(cycle, "inventory", return_value=snapshot()), \
             patch("scripts.sunday_briefs_auto_writer.choose_evidence", return_value=evidence()), \
             patch("scripts.sunday_briefs_auto_writer.compose", return_value=article_manuscript()), \
             patch("scripts.sunday_editorial_handoff.send_packet") as smtp:
            accepted = cycle.prepare(SAT, target, marker_path=self.marker, now=SATURDAY, execute_model=True)
            self.assertEqual(cycle.deliver(accepted, target, now=SATURDAY,
                                          marker_path=self.marker)["status"], "EDITOR_PREPARED")
            original = (target / accepted["packet_file"]).read_text()
            returned = original.replace("## WORKING TITLE\n", "## WORKING TITLE\nRevised editorial title: ", 1)
            validate_return(original, returned)
            # Controlled conversion remains a human authoring operation; the
            # test does not pretend to infer claim support from an editor edit.
            final = json.loads((target / ("IPR-" + SAT + ".scaffold.json")).read_text())
            final["title"] = "Source-checked synthetic final title"
            self.marker.write_text("2026-10-11")
            receipt = cycle.reconcile(accepted, final, marker_path=self.marker, now=SUNDAY,
                                      reviewed_by="Synthetic source reviewer",
                                      review_reference="fixture exact final claim review")
            final["saturday_sunday_cycle"] = receipt
            self.assertEqual(cycle.readiness_problems(final), [])
            self.assertFalse(receipt["publication_authorized"])
            smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
