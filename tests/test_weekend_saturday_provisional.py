"""Saturday provisional draft contracts: mocked model and simulated SMTP only."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from core.brief_editorial_evidence import load_editorial_evidence
from scripts.sunday_before_model_gate import BeforeModelRefused, gate
from scripts.sunday_briefs_auto_writer import (
    SATURDAY_PROVISIONAL_CUTOFF, compose, cutoff_statement,
)
from scripts.sunday_corpus_readiness import ReadinessError, evaluate
from scripts.sunday_editorial_handoff import (
    SATURDAY_PROVISIONAL_MARK, is_saturday_provisional, main, render_packet,
    send_packet,
)
from scripts.sunday_editor_readable import SATURDAY_NOTE, prose_only_html, prose_only_text
from scripts.weekly_briefs_sunday_window import (
    SundayHandoffRefused, resolve_saturday_provisional,
)
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold
from tests.test_sunday_automatic_story_selection import selected
from tests.test_sunday_corpus_readiness import row
from tests.test_weekly_briefs_auto_writer import evidence

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def packet(saturday_provisional=True):
    return render_packet(scaffold(), manuscript=manuscript(), as_of=SAT,
                         research_evidence=load_editorial_evidence(SAT, SAT),
                         saturday_provisional=saturday_provisional)


def simulated_send(text, *, saturday_provisional=True):
    """Send through a mocked SMTP_SSL with fake recipients; return the message."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "IPR-Briefs-{}.txt".format(SAT)
        path.write_text(text, encoding="utf-8")
        fake_mail = MagicMock()
        fake_mail.__enter__.return_value = fake_mail
        env = {"IPR_EDITOR_TO": "dylan@example.org", "IPR_SMTP_USER": "ben@example.org",
               "IPR_SMTP_APP_PASSWORD": "abcdefghijklmnop",
               "IPR_SUNDAY_OWNER_REVIEWED_WEEK": SAT,
               "IPR_SUNDAY_OWNER_REVIEWED_SHA256": hashlib.sha256(path.read_bytes()).hexdigest()}
        with patch.dict("os.environ", env), \
                patch("scripts.sunday_editorial_handoff.require_owner_review"), \
                patch("scripts.sunday_editorial_handoff.require_exact_reviewed_manuscript"), \
                patch("scripts.sunday_editorial_handoff.smtplib.SMTP_SSL") as smtp:
            smtp.return_value.__enter__.return_value = fake_mail
            send_packet(path, SAT, full_week=True, saturday_provisional=saturday_provisional)
            return fake_mail.send_message.call_args.args[0]


class SaturdayProvisionalPacket(unittest.TestCase):
    def test_header_marks_provisional_and_is_detected_from_header_only(self):
        text = packet()
        head = text.split("\n\n", 1)[0]
        self.assertIn("AS-OF CUT-OFF: {} ({})".format(SAT, SATURDAY_PROVISIONAL_MARK), head)
        self.assertNotIn("SATURDAY COMPLETE", head)
        self.assertTrue(is_saturday_provisional(text))
        ordinary = packet(saturday_provisional=False)
        self.assertFalse(is_saturday_provisional(ordinary))
        # The mark quoted in the body is not a header claim.
        self.assertFalse(is_saturday_provisional(
            ordinary + "\n\n(" + SATURDAY_PROVISIONAL_MARK + ")\n"))

    def test_provisional_packet_requires_saturday_cutoff(self):
        with self.assertRaisesRegex(ValueError, "Saturday cut-off"):
            render_packet(scaffold(), manuscript=manuscript(), as_of="2026-10-09",
                          research_evidence=load_editorial_evidence(SAT, "2026-10-09"),
                          saturday_provisional=True)

    def test_word_copy_labels_and_tags_the_draft(self):
        from docx import Document
        from scripts.sunday_editor_docx import (
            SATURDAY_PROVISIONAL_KEYWORD, SATURDAY_PROVISIONAL_LABEL, render_editor_docx,
        )
        document = Document(BytesIO(render_editor_docx(packet())))
        body = "\n".join(p.text for p in document.paragraphs)
        self.assertIn(SATURDAY_PROVISIONAL_LABEL, body)
        footer = document.sections[0].footer.paragraphs[0].text
        self.assertTrue(footer.startswith(SATURDAY_PROVISIONAL_LABEL))
        self.assertIn("NOT APPROVED FOR PUBLICATION", footer)
        self.assertIn(SATURDAY_PROVISIONAL_KEYWORD, document.core_properties.keywords)
        ordinary = Document(BytesIO(render_editor_docx(packet(saturday_provisional=False))))
        self.assertNotIn(SATURDAY_PROVISIONAL_LABEL,
                         "\n".join(p.text for p in ordinary.paragraphs))
        self.assertNotIn(SATURDAY_PROVISIONAL_KEYWORD, ordinary.core_properties.keywords or "")

    def test_readable_prose_carries_caveat_only_when_provisional(self):
        text = packet()
        self.assertIn(SATURDAY_NOTE.strip(), prose_only_text(text))
        self.assertIn("Saturday provisional draft", prose_only_html(text))
        self.assertNotIn(SATURDAY_NOTE.strip(), prose_only_text(packet(saturday_provisional=False)))


class SaturdayProvisionalDelivery(unittest.TestCase):
    def test_simulated_dylan_email_is_labelled_and_attaches_exact_bytes(self):
        text = packet()
        message = simulated_send(text)
        self.assertEqual(message["To"], "dylan@example.org")
        self.assertIn("Saturday provisional draft for language edits", message["Subject"])
        plain = message.get_body(preferencelist=("plain",)).get_content()
        html = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn(SATURDAY_NOTE.strip(), plain)
        self.assertIn("Saturday provisional draft", html)
        attachments = list(message.iter_attachments())
        self.assertEqual(attachments[0].get_payload(decode=True), text.encode("utf-8"))
        self.assertTrue(attachments[1].get_filename().endswith(".docx"))

    def test_mode_must_match_packet_header_in_both_directions(self):
        with self.assertRaisesRegex(ValueError, "must match"):
            simulated_send(packet(), saturday_provisional=False)
        with self.assertRaisesRegex(ValueError, "must match"):
            simulated_send(packet(saturday_provisional=False), saturday_provisional=True)

    def test_cli_requires_full_week_for_saturday_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "sidecar.json"
            import json
            sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
            with patch("sys.stderr"), self.assertRaises(SystemExit) as stop:
                main(["--sidecar", str(sidecar), "--out", str(Path(tmp) / "o.txt"),
                      "--write-automatic", "--as-of", SAT, "--saturday-provisional"])
            self.assertEqual(stop.exception.code, 2)


class SaturdayProvisionalWriter(unittest.TestCase):
    def test_cutoff_wording_never_claims_a_complete_week(self):
        self.assertEqual(cutoff_statement(SAT, SAT, saturday_provisional=True),
                         SATURDAY_PROVISIONAL_CUTOFF)
        self.assertNotIn("has elapsed", SATURDAY_PROVISIONAL_CUTOFF)
        self.assertIn("Do not describe the week as complete", SATURDAY_PROVISIONAL_CUTOFF)
        with self.assertRaisesRegex(ValueError, "Saturday cutoff"):
            cutoff_statement("2026-10-09", SAT, saturday_provisional=True)

    def test_compose_requires_automatic_selection(self):
        with self.assertRaisesRegex(ValueError, "automatic selection"):
            compose(scaffold(), SAT, client=object(), saturday_provisional=True)

    def test_mocked_single_model_call_receives_provisional_cutoff(self):
        offered = []
        response = SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(
            type="tool_use", name="compose_editorial_draft", input=selected())])
        stream = lambda **kw: (offered.append(kw), nullcontext(
            SimpleNamespace(get_final_message=lambda: response)))[1]
        fake = SimpleNamespace(messages=SimpleNamespace(stream=stream))
        with patch("scripts.sunday_briefs_auto_writer.choose_evidence", return_value=evidence()):
            compose(scaffold(), SAT, client=fake,
                    supplemental=load_editorial_evidence(SAT, SAT),
                    automatic_story_selection=True, saturday_provisional=True)
        self.assertEqual(len(offered), 1)
        instruction = offered[0]["messages"][0]["content"]
        self.assertIn(SATURDAY_PROVISIONAL_CUTOFF, instruction)
        self.assertNotIn("Saturday has elapsed", instruction)


class SaturdayProvisionalReadiness(unittest.TestCase):
    ROWS = [row(1, "china", "2026-10-08"), row(2, "singapore", "2026-10-07")]

    def assess(self, *, as_of=SAT, review_day=SAT, marker=SAT):
        return evaluate(rows=self.ROWS, desks=["china", "singapore"], week_ending=SAT,
                        as_of=as_of, review_day=review_day, marker=marker,
                        provisional=True)

    def test_saturday_marker_is_the_only_provisional_marker(self):
        report = self.assess()
        self.assertEqual(report["unmet_gates"], [])
        for stale in ("", "2026-10-09"):
            with self.subTest(marker=stale):
                self.assertEqual(self.assess(marker=stale)["unmet_gates"],
                                 ["saturday_provisional_marker_missing_or_stale"])

    def test_provisional_check_only_on_the_reporting_saturday(self):
        for kwargs in ({"review_day": "2026-10-11", "marker": "2026-10-11"},
                       {"as_of": "2026-10-09", "review_day": SAT}):
            with self.subTest(**kwargs), self.assertRaises(ReadinessError):
                self.assess(**kwargs)

    def test_gate_accepts_saturday_and_refuses_other_days(self):
        with patch("scripts.sunday_before_model_gate.inspect", return_value=self.assess()):
            result = gate(week_ending=SAT, as_of=SAT, review_local_day=SAT,
                          saturday_provisional=True)
        self.assertEqual(result["pre_model_scope"],
                         "saturday_provisional_collection_marker_and_corpus_checked")
        self.assertTrue(result["saturday_collection_verified_for_this_execution"])
        self.assertFalse(result["sunday_collection_verified_for_this_execution"])
        self.assertFalse(result["editor_delivery_authorized"])
        for as_of, day in ((SAT, "2026-10-11"), (SAT, "2026-10-09"), ("2026-10-09", SAT)):
            with self.subTest(as_of=as_of, day=day), self.assertRaisesRegex(
                    BeforeModelRefused, "only on the reporting Saturday"):
                gate(week_ending=SAT, as_of=as_of, review_local_day=day,
                     saturday_provisional=True)

    def test_gate_refuses_stale_saturday_marker(self):
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=self.assess(marker="2026-10-09")), \
                self.assertRaisesRegex(BeforeModelRefused,
                                       "saturday_provisional_marker_missing_or_stale"):
            gate(week_ending=SAT, as_of=SAT, review_local_day=SAT,
                 saturday_provisional=True)


class SaturdayProvisionalWindow(unittest.TestCase):
    def test_verified_saturday_collection_resolves_its_own_week(self):
        # 2026-10-10 is EDT (UTC-4); 23:30 local is 03:30 UTC Sunday.
        result = resolve_saturday_provisional(
            collection_day=SAT, now=datetime(2026, 10, 11, 3, 30, tzinfo=UTC),
            saturday_daily_marker="2026-10-10")
        self.assertEqual(result, {"IPR_SUNDAY_WEEK_START": "2026-10-04",
                                  "IPR_SUNDAY_AS_OF": "2026-10-10",
                                  "IPR_SUNDAY_WEEK_END": "2026-10-10",
                                  "IPR_SUNDAY_SHOULD_SEND": "true"})
        # After the November change New York is UTC-5.
        winter = resolve_saturday_provisional(
            collection_day="2026-11-07", now=datetime(2026, 11, 8, 4, 30, tzinfo=UTC),
            saturday_daily_marker="2026-11-07")
        self.assertEqual(winter["IPR_SUNDAY_WEEK_END"], "2026-11-07")

    def test_late_saturday_collection_whose_job_starts_on_sunday_keeps_its_week(self):
        # The clock is Sunday; the verified collection, not the clock, decides.
        result = resolve_saturday_provisional(
            collection_day=SAT, now=datetime(2026, 10, 11, 0, 40, tzinfo=NY),
            saturday_daily_marker=SAT)
        self.assertEqual(result["IPR_SUNDAY_WEEK_END"], SAT)

    def test_refusals(self):
        saturday = datetime(2026, 10, 10, 12, tzinfo=NY)
        cases = [
            ({"collection_day": SAT, "now": datetime(2026, 10, 10, 12),
              "saturday_daily_marker": SAT}, "timezone"),
            ({"collection_day": "2026-10-11", "now": datetime(2026, 10, 11, 12, tzinfo=NY),
              "saturday_daily_marker": "2026-10-11"}, "Saturday collection"),
            ({"collection_day": "", "now": saturday,
              "saturday_daily_marker": SAT}, "missing or invalid"),
            ({"collection_day": "2026-10-10T00:00", "now": saturday,
              "saturday_daily_marker": SAT}, "missing or invalid"),
            ({"collection_day": SAT, "now": datetime(2026, 10, 12, 0, 5, tzinfo=NY),
              "saturday_daily_marker": SAT}, "stale or from the future"),
            ({"collection_day": SAT, "now": datetime(2026, 10, 9, 23, tzinfo=NY),
              "saturday_daily_marker": SAT}, "stale or from the future"),
            ({"collection_day": SAT, "now": saturday,
              "saturday_daily_marker": "2026-10-09"}, "success marker"),
            # A Sunday collection already moved the marker on.
            ({"collection_day": SAT, "now": datetime(2026, 10, 11, 9, tzinfo=NY),
              "saturday_daily_marker": "2026-10-11"}, "success marker"),
            ({"collection_day": SAT, "now": saturday,
              "saturday_daily_marker": ""}, "success marker"),
            ({"collection_day": SAT, "now": saturday, "saturday_daily_marker": SAT,
              "friday_delivery_enabled": True}, "parallel services"),
        ]
        for kwargs, match in cases:
            with self.subTest(match=match, kwargs=kwargs), \
                    self.assertRaisesRegex(SundayHandoffRefused, match):
                resolve_saturday_provisional(**kwargs)


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/sunday_briefs_editorial_handoff.yml"


def workflow_jobs():
    src = WORKFLOW.read_text(encoding="utf-8")
    head, body = src.split("\njobs:\n", 1)
    jobs, name = {}, None
    for line in body.splitlines():
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            name = line.strip()[:-1]
            jobs[name] = ""
        elif name:
            jobs[name] += line + "\n"
    return head, jobs


class WeekendWorkflowContracts(unittest.TestCase):
    def test_runs_only_after_the_daily_collection_and_only_when_enabled(self):
        head, jobs = workflow_jobs()
        self.assertIn('workflow_run:\n    workflows: ["Daily PLA Watch Update"]\n'
                      "    types: [completed]\n    branches: [main]", head)
        self.assertIn("if: vars.IPR_WEEKEND_EDITORIAL_ENABLED == 'true' && "
                      "github.event_name == 'workflow_run'", jobs["weekend-collection"])
        self.assertIn("--marker .github/state/last_daily_run_date.txt", jobs["weekend-collection"])
        # #957 uses a different variable; the two PRs must not share one switch.
        self.assertNotIn("IPR_SATURDAY_SUNDAY_CYCLE_ENABLED", WORKFLOW.read_text(encoding="utf-8"))

    def test_reruns_are_refused_before_any_paid_or_email_step(self):
        _, jobs = workflow_jobs()
        self.assertIn('[[ "$GITHUB_RUN_ATTEMPT" == "1" ]]', jobs["weekend-collection"])
        handoff = jobs["sunday-editor-handoff"]
        refuse = handoff.index('os.environ.get("GITHUB_RUN_ATTEMPT") != "1"')
        self.assertLess(refuse, handoff.index("python -m scripts.sunday_editorial_handoff"))

    def test_provisional_mode_reaches_the_gate_and_the_manuscript(self):
        _, jobs = workflow_jobs()
        handoff = jobs["sunday-editor-handoff"]
        self.assertIn('provisional = os.environ["IPR_EVENT"] == "workflow_run"', handoff)
        self.assertIn("resolve_saturday_provisional(", handoff)
        self.assertIn('IPR_SUNDAY_WEEK_END"] != os.environ["IPR_WEEKEND_WEEK"]', handoff)
        self.assertEqual(handoff.count("args+=(--saturday-provisional"), 2)
        # The gate judges the verified collection day, not the runner clock.
        self.assertIn('--review-local-day "$IPR_COLLECTION_DAY"', handoff)
        self.assertIn('collection_day=os.environ["IPR_WEEKEND_COLLECTION_DAY"]', handoff)

    def test_draft_reads_the_exact_verified_corpus_commit(self):
        _, jobs = workflow_jobs()
        trigger, handoff = jobs["weekend-collection"], jobs["sunday-editor-handoff"]
        self.assertIn("corpus_sha: ${{ steps.verify.outputs.corpus_sha }}", trigger)
        self.assertIn("collection_day: ${{ steps.verify.outputs.collection_day }}", trigger)
        # rev-parse runs after the marker check, in the same step.
        self.assertLess(trigger.index("--marker .github/state/last_daily_run_date.txt"),
                        trigger.index('echo "corpus_sha=$(git rev-parse HEAD)"'))
        self.assertIn("ref: ${{ needs.weekend-collection.outputs.corpus_sha || 'main' }}",
                      handoff)
        self.assertNotIn("ref: main", handoff)
        self.assertLess(handoff.index("python -m scripts.sunday_before_model_gate"),
                        handoff.index("python -m scripts.sunday_editorial_handoff"))

    def test_sunday_writes_metadata_only(self):
        _, jobs = workflow_jobs()
        notice = jobs["weekend-sunday-recheck-notice"]
        self.assertIn("if: needs.weekend-collection.outputs.mode == 'sunday'", notice)
        for forbidden in ("secrets.", "ANTHROPIC", "SMTP", "upload-artifact",
                          "sunday_editorial_handoff", "checkout"):
            self.assertNotIn(forbidden, notice)
        self.assertIn("--saturday $WEEK_ENDING", notice)
        self.assertNotIn("upload-artifact", WORKFLOW.read_text(encoding="utf-8"))

    def test_saturday_draft_is_reserved_once_before_the_model_call(self):
        head, jobs = workflow_jobs()
        trigger, handoff = jobs["weekend-collection"], jobs["sunday-editor-handoff"]
        self.assertIn("reservation: ${{ steps.verify.outputs.reservation }}", trigger)
        self.assertIn("actions: read", trigger)
        # Every free gate runs first; the named marker sits just before the model.
        gate = handoff.index("python -m scripts.sunday_before_model_gate")
        marker = handoff.index(
            "- name: Model attempt ${{ needs.weekend-collection.outputs.reservation }}")
        model = handoff.index("python -m scripts.sunday_editorial_handoff")
        self.assertLess(gate, marker)
        self.assertLess(marker, model)
        between = handoff[marker:model]
        self.assertIn("if: env.IPR_SATURDAY_PROVISIONAL == 'true'", between)
        self.assertIn('"ipr-weekend-saturday-$IPR_SUNDAY_WEEK_END"', between)
        self.assertIn('"$GITHUB_RUN_ATTEMPT" == "1"', between)
        self.assertEqual(between.count("- name:"), 2)  # marker, then the model step
        # The reservation is run history, not a stored file: no artifact at all.
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", src)
        self.assertNotIn("ipr-weekend-reservation", src)
        # Serialised runs, and no write access to the repository.
        self.assertIn("concurrency:\n  group: ipr-sunday-editorial-handoff\n"
                      "  cancel-in-progress: false", head)
        self.assertNotIn("contents: write", src)


if __name__ == "__main__":
    unittest.main()
