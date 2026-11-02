"""Offline Track C routing: fake identities, injected transports, no live send."""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.brief_analyst_feedback import reconcile_feedback
from core.brief_analyst_packet import build_packet, digest
from core.brief_analyst_return import extract_memo
from scripts import brief_editorial_routing as routing
from scripts import saturday_sunday_briefs as cycle
from scripts.sunday_editorial_handoff import render_packet
from scripts.sunday_editor_readable import editable_sections
from tests.briefs_narrative_fixtures import article_manuscript, scaffold

SAT = "2026-10-10"
SATURDAY = datetime.fromisoformat("2026-10-10T13:00:00-04:00")
AFTER_DEADLINE = datetime.fromisoformat("2026-10-10T19:00:00-04:00")
SUNDAY = datetime.fromisoformat("2026-10-11T16:00:00-04:00")
EDITOR, OWNER, ANALYST = "editor@example.invalid", "owner@example.invalid", "analyst@example.invalid"
PRIOR = "https://official.example.gov/2025/prior"
ENV = {"IPR_EDITOR_TO": EDITOR, "IPR_PREVIEW_TO": OWNER,
       "IPR_EDITOR_DELIVERY_ENABLED": "false", "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "false"}


def snapshot():
    return {"week_start": "2026-10-04", "week_ending": SAT, "sources": {"record:1": "a"},
            "policy": {"policy": "b"}, "desks": ["china", "singapore"]}


def roster(**changes):
    entry = {"id": "analyst-1", "email": ANALYST, "consent_reference": "fixture consent record 2026-10",
             "scope": routing.SCOPE, "revoked": False, "available_weeks": [SAT]}
    entry.update(changes)
    return {"schema": routing.ROSTER_SCHEMA, "analysts": [entry]}


def assignment(worksheet, deadline="2026-10-10T18:00:00-04:00"):
    sources = [{"id": "record:2", "url": "https://example.com/2", "version_sha256": "a" * 64,
                "evidence_basis": "reviewed_original", "access_note": "Synthetic original inspected; links only.",
                "original_review_reference": "fixture independent original review",
                "distribution_reference": "fixture source-specific owner link decision"}]
    distribution = {"owner_confirmed": True, "reviewed_by": "Fixture owner",
                    "reference": "fixture explicit distribution decision",
                    "worksheet_sha256": digest(worksheet), "source_pins_sha256": digest(sources),
                    "scope": routing.SCOPE}
    return build_packet(worksheet,
        thesis="The draft argues this synthetic statement changes an existing regional commitment.",
        questions=[{"question": "Does the statement add a binding commitment beyond the earlier official announcement?",
                    "why_it_matters": "If the commitment was already announced, the current novelty claim must be narrowed.",
                    "source_ids": ["record:2"]}],
        sources=sources, distribution=distribution, deadline=deadline)


def daily_event(**run):
    base = {"name": routing.UPSTREAM_NAME, "path": routing.UPSTREAM_PATH, "event": "schedule",
            "head_branch": "main", "conclusion": "success", "status": "completed", "run_attempt": 1,
            "id": 42, "head_repository": {"full_name": "example/ipr"}}
    base.update(run)
    return {"workflow_run": base, "repository": {"full_name": "example/ipr"}}


def daily_jobs(**steps):
    names = dict.fromkeys(routing.REQUIRED_STEPS, "success")
    names.update(steps)
    return {"total_count": 1, "jobs": [{"name": "update", "conclusion": "success",
            "steps": [{"name": k, "conclusion": v} for k, v in names.items()]}]}


class DailyCompletionTests(unittest.TestCase):
    def check(self, phase, now, event=None, jobs=None, marker=None):
        return routing.daily_completion(event or daily_event(), jobs or daily_jobs(), phase=phase,
                                        repo="example/ipr", marker=marker or now.date().isoformat(), now=now)

    def test_saturday_and_sunday_success_bind_the_reporting_week(self):
        self.assertEqual(self.check("saturday", SATURDAY)["week_ending"], SAT)
        sunday = self.check("sunday", SUNDAY)
        self.assertEqual((sunday["week_ending"], sunday["collection_day"]), (SAT, "2026-10-11"))

    def test_wrong_day_and_skipped_green_retry_are_silent_no_ops(self):
        for phase, now in (("saturday", SUNDAY), ("sunday", SATURDAY),
                           ("saturday", datetime.fromisoformat("2026-10-09T13:00:00-04:00"))):
            with self.assertRaises(routing.NoNewCollection):
                self.check(phase, now)
        skipped = daily_jobs(**{"Run pipeline": "skipped", "Record successful run": "skipped"})
        for phase, now in (("saturday", SATURDAY), ("sunday", SUNDAY)):
            with self.assertRaises(routing.NoNewCollection):
                self.check(phase, now, jobs=skipped)

    def test_rerun_dispatch_failure_and_stale_marker_refuse(self):
        for run in ({"run_attempt": 2}, {"event": "workflow_dispatch"}, {"head_branch": "feature"},
                    {"conclusion": "failure"}, {"head_repository": {"full_name": "fork/ipr"}}):
            with self.assertRaises(routing.DailyCompletionRefused) as caught:
                self.check("saturday", SATURDAY, event=daily_event(**run))
            self.assertNotIsInstance(caught.exception, routing.NoNewCollection)
        with self.assertRaisesRegex(routing.DailyCompletionRefused, "skipped or failed"):
            self.check("sunday", SUNDAY, jobs=daily_jobs(**{"Deploy to GitHub Pages": "skipped"}))
        with self.assertRaisesRegex(routing.DailyCompletionRefused, "Sunday marker"):
            self.check("sunday", SUNDAY, marker=SAT)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.marker = self.directory / "marker"
        self.marker.write_text(SAT)
        self.worksheet = render_packet(scaffold(), manuscript=article_manuscript(), as_of=SAT,
                                       saturday_provisional=True)
        name = "IPR-Briefs-Editorial-" + SAT + ".txt"
        cycle.write_private(self.directory / name, self.worksheet)
        self.state = {"schema": cycle.SCHEMA, "identity": "IPR-" + SAT, "status": "SATURDAY_PROVISIONAL",
                      "inventory": snapshot(), "packet_file": name, "packet_sha256": digest(self.worksheet),
                      "window": {"week_start": "2026-10-04", "week_ending": SAT}}
        self.manifest, self.docx, self.brief = assignment(self.worksheet)
        for target in (patch.object(cycle, "inventory", return_value=snapshot()),
                       patch.object(routing, "inventory", return_value=snapshot()),
                       patch.dict(os.environ, ENV)):
            target.start()
            self.addCleanup(target.stop)

    def dispatch(self, transport=None, **changes):
        kwargs = dict(manifest=self.manifest, docx=self.docx, brief=self.brief, roster=roster(),
                      transport=transport or MagicMock(), owner_confirmed=True,
                      approved_manifest_sha256=self.manifest["manifest_sha256"],
                      marker_path=self.marker, now=SATURDAY)
        kwargs.update(changes)
        return routing.dispatch_analyst(self.state, self.directory, **kwargs)

    def deliver(self, now=SATURDAY, approved=None, send=True, smtp=None):
        with patch("scripts.sunday_editorial_handoff.send_packet", smtp or MagicMock()) as mock:
            result = cycle.deliver(self.state, self.directory, now=now, marker_path=self.marker,
                                   send=send, owner_confirmed=True, analyst_routing=True,
                                   approved_sha256=approved or self.state["packet_sha256"])
        return result, mock

    def reconcile(self, disposition="accepted"):
        article = dict(editable_sections(self.worksheet))["ARTICLE"]
        before = article.split("\n\n")[0].split(". ")[0]
        after = "The synthetic statement repeats an earlier commitment"
        revised = self.worksheet.replace(before, after, 1) if disposition == "accepted" else self.worksheet
        returned = extract_memo(self.manifest, {"assignment_id": self.manifest["assignment_id"],
                                "worksheet_sha256": self.manifest["worksheet_sha256"],
                                "text": "Earlier official announcement already contains this. " + PRIOR})
        decision = {"finding_id": "memo", "disposition": disposition,
                    "reason": "Independent source comparison supports narrowing.",
                    "source_checks": [{"source_id": "new:prior", "url": PRIOR, "version_sha256": "b" * 64,
                                       "reviewed_by": "Fixture owner",
                                       "review_reference": "fixture prior official original inspected",
                                       "assessment": "supports_correction" if disposition == "accepted"
                                       else "inconclusive"}],
                    "change": {"before": before, "after": after} if disposition == "accepted" else None,
                    "candidate_lesson": None, "error_type": None, "serious": False}
        owner = {"owner_confirmed": True, "reviewed_by": "Fixture owner",
                 "review_reference": "fixture original comparison by human", "reviewed_on": SAT,
                 "return_receipt_sha256": returned["return_receipt_sha256"],
                 "revised_worksheet_sha256": digest(revised)}
        feedback = reconcile_feedback(self.manifest, returned, revised, decisions=[decision], owner_review=owner)
        return returned, feedback, revised

    def test_no_eligible_analyst_keeps_provisional_delivery_unchanged(self):
        transport = MagicMock()
        for changes in ({"consent_reference": "short"}, {"revoked": True}, {"available_weeks": ["2026-10-17"]},
                        {"scope": "full-source-bodies"}, {"email": EDITOR}, {"email": OWNER}):
            result = self.dispatch(transport, roster=roster(**changes))
            self.assertEqual(result["status"], "NO_ANALYST")
        transport.assert_not_called()
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()),
                         ["IPR-Briefs-Editorial-" + SAT + ".txt", "marker"])
        self.assertEqual(routing.route(self.state, self.directory, now=SATURDAY)["route"], "NO_ANALYST")
        result, smtp = self.deliver()
        self.assertEqual((result["status"], result["analyst_route"]), ("EDITOR_SENT", "NO_ANALYST"))
        frozen = smtp.call_args[0][0]
        self.assertEqual(frozen.name, self.state["packet_file"])

    def test_owner_must_approve_exact_manifest_and_transport_has_no_default(self):
        transport = MagicMock()
        with self.assertRaisesRegex(ValueError, "exact assignment manifest"):
            self.dispatch(transport, approved_manifest_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "exact assignment manifest"):
            self.dispatch(transport, owner_confirmed=False)
        with self.assertRaisesRegex(ValueError, "injected"):
            self.dispatch("smtp-default")  # anything not callable, i.e. no built-in mailer
        transport.assert_not_called()
        self.assertFalse(list(self.directory.glob("analyst-*")))

    def test_slug_identity_late_deadline_and_passed_deadline_refused(self):
        slug = copy.deepcopy(self.manifest)
        slug["packet"] = "IPR-" + SAT + "-second-item"
        slug["manifest_sha256"] = digest({k: v for k, v in slug.items() if k != "manifest_sha256"})
        with self.assertRaisesRegex(ValueError, "exact weekly packet identity"):
            self.dispatch(manifest=slug, approved_manifest_sha256=slug["manifest_sha256"])
        late, _, _ = assignment(self.worksheet, deadline="2026-10-10T21:30:00-04:00")
        with self.assertRaisesRegex(ValueError, "9 p.m."):
            self.dispatch(manifest=late, approved_manifest_sha256=late["manifest_sha256"])
        with self.assertRaisesRegex(ValueError, "already passed"):
            self.dispatch(now=AFTER_DEADLINE)

    def test_weekly_cap_and_uncertain_send_never_resend(self):
        transport = MagicMock(side_effect=RuntimeError("simulated transport failure"))
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.dispatch(transport)
        with self.assertRaises(FileExistsError):
            self.dispatch(transport)
        other = roster(email="second@example.invalid", id="analyst-2")
        with self.assertRaises(FileExistsError):
            self.dispatch(transport, roster=other)
        self.assertEqual(transport.call_count, 1)
        self.assertFalse(list(self.directory.glob("delivered-*")))
        self.assertEqual(routing.route(self.state, self.directory, now=SATURDAY)["route"], "AWAIT_ANALYST")
        with self.assertRaisesRegex(ValueError, "AWAIT_ANALYST"):
            self.deliver()

    def test_missing_return_after_deadline_sends_provisional(self):
        transport = MagicMock()
        self.assertEqual(self.dispatch(transport)["status"], "ANALYST_SENT")
        kwargs = transport.call_args.kwargs
        self.assertEqual((kwargs["recipient"], kwargs["assignment_id"]), (ANALYST, self.manifest["assignment_id"]))
        result, smtp = self.deliver(now=AFTER_DEADLINE)
        self.assertEqual(result["analyst_route"], "DELIVER_PROVISIONAL")
        self.assertEqual(result["packet_sha256"], self.state["packet_sha256"])
        smtp.assert_called_once()

    def test_return_without_feedback_or_held_feedback_blocks_dylan(self):
        self.dispatch()
        returned, held, revised = self.reconcile("unresolved")
        self.assertEqual(held["state"], "HELD")
        routing.record_return(self.directory, SAT, returned)
        for now in (SATURDAY, AFTER_DEADLINE):
            self.assertEqual(routing.route(self.state, self.directory, now=now)["route"], "HELD")
        routing.record_feedback(self.directory, SAT, held, revised)
        smtp = MagicMock()
        with self.assertRaisesRegex(ValueError, "held by analyst routing: HELD"):
            self.deliver(now=AFTER_DEADLINE, smtp=smtp)
        smtp.assert_not_called()

    def test_reconciled_revision_goes_to_dylan_only_with_its_exact_sha(self):
        self.dispatch()
        returned, feedback, revised = self.reconcile()
        self.assertEqual(feedback["state"], "ANALYSIS_RECONCILED")
        routing.record_return(self.directory, SAT, returned)
        with self.assertRaises(FileExistsError):
            routing.record_return(self.directory, SAT, returned)
        with self.assertRaisesRegex(ValueError, "owner reconciled"):
            routing.record_feedback(self.directory, SAT, feedback, revised + "\n")
        routing.record_feedback(self.directory, SAT, feedback, revised)
        decision = routing.route(self.state, self.directory, now=SATURDAY)
        self.assertEqual(decision["route"], "DELIVER_REVISED")
        smtp = MagicMock()
        with self.assertRaisesRegex(ValueError, "exact attachment SHA"):
            self.deliver(smtp=smtp)  # owner approved only the provisional SHA
        smtp.assert_not_called()

        def sent(packet, week, **kwargs):
            self.assertEqual(packet.name, self.state["packet_file"])
            self.assertEqual(packet.read_text(encoding="utf-8"), revised)
        result, _ = self.deliver(approved=feedback["revised_worksheet_sha256"], smtp=MagicMock(side_effect=sent))
        self.assertEqual((result["status"], result["analyst_route"]), ("EDITOR_SENT", "DELIVER_REVISED"))
        self.assertEqual(result["packet_sha256"], feedback["revised_worksheet_sha256"])
        # A later return or retry never yields a second editor send for the week.
        with self.assertRaises(FileExistsError):
            self.deliver(approved=feedback["revised_worksheet_sha256"])

    def test_tampered_revision_or_receipt_refused(self):
        self.dispatch()
        returned, feedback, revised = self.reconcile()
        routing.record_return(self.directory, SAT, returned)
        routing.record_feedback(self.directory, SAT, feedback, revised)
        path = routing._revised(self.directory, SAT)
        os.chmod(path, 0o600)
        path.write_text(revised + "tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revised manuscript changed"):
            routing.route(self.state, self.directory, now=SATURDAY)
        receipt = routing._paths(self.directory, SAT)["return"]
        data = json.loads(receipt.read_text())
        data["findings"] = []
        receipt.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "stored analyst return changed"):
            routing.route(self.state, self.directory, now=SATURDAY)

    def test_ephemeral_or_shared_storage_refused(self):
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.directory)}):
            with self.assertRaisesRegex(ValueError, "ephemeral"):
                routing.durable_directory(self.directory)
            with self.assertRaisesRegex(ValueError, "ephemeral"):
                self.deliver()
        os.chmod(self.directory, 0o755)
        self.addCleanup(os.chmod, self.directory, 0o700)
        with self.assertRaises(ValueError):
            routing.durable_directory(self.directory)

    def test_legacy_flags_still_refuse_routed_delivery(self):
        with patch.dict(os.environ, {"IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "true"}):
            with self.assertRaisesRegex(ValueError, "legacy"):
                self.deliver()

    def test_pilot_env_guard_below_send_packet_binds_the_revised_bytes(self):
        self.dispatch()
        returned, feedback, revised = self.reconcile()
        routing.record_return(self.directory, SAT, returned)
        routing.record_feedback(self.directory, SAT, feedback, revised)
        smtp_env = {"IPR_SMTP_USER": "sender@example.invalid", "IPR_SMTP_APP_PASSWORD": "abcdabcdabcdabcd",
                    "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
                    "IPR_SUNDAY_OWNER_REVIEWED_SHA256": self.state["packet_sha256"]}
        approved = feedback["revised_worksheet_sha256"]
        with patch.dict(os.environ, smtp_env), \
             patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as server:
            with self.assertRaises(Exception):
                cycle.deliver(self.state, self.directory, now=SATURDAY, marker_path=self.marker, send=True,
                              owner_confirmed=True, analyst_routing=True, approved_sha256=approved)
            server.assert_not_called()
        # The refused attempt consumed the once-only editor reservation; a
        # fresh store with the correct pilot SHA shows the real mail path.
        for receipt in self.directory.glob("dispatch-*.json"):
            if json.loads(receipt.read_text()).get("packet_sha256") == approved:
                receipt.unlink()
        smtp_env["IPR_SUNDAY_OWNER_REVIEWED_SHA256"] = approved
        with patch.dict(os.environ, smtp_env), \
             patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as server:
            result = cycle.deliver(self.state, self.directory, now=SATURDAY, marker_path=self.marker, send=True,
                                   owner_confirmed=True, analyst_routing=True, approved_sha256=approved)
        self.assertEqual(result["status"], "EDITOR_SENT")
        message = server.return_value.__enter__.return_value.send_message.call_args[0][0]
        self.assertEqual(message["To"], EDITOR)
        attached = [part.get_payload(decode=True) for part in message.iter_attachments()
                    if part.get_filename() == self.state["packet_file"]]
        self.assertEqual(attached, [revised.encode("utf-8")])


if __name__ == "__main__":
    unittest.main()
