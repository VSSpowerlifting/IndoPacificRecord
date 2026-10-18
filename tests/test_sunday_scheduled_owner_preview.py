"""No-send contracts for explicitly opted-in scheduled Sunday owner previews."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.weekly_briefs_sunday_window import (
    SundayHandoffRefused, resolve_sunday_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
SATURDAY = "2026-10-10"
SUNDAY = datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc)


class ScheduledOwnerPreviewContracts(unittest.TestCase):
    def test_scheduled_owner_preview_requires_no_editor_authorization(self):
        accepted = resolve_sunday_handoff(
            event="schedule", now=SUNDAY, send_email=False,
            scheduled_owner_preview=True, sunday_daily_marker="2026-10-11",
            pilot_owner_reviewed_week="", pilot_owner_reviewed_sha256="",
            friday_delivery_enabled=True,
        )
        self.assertEqual(accepted["IPR_SUNDAY_WEEK_END"], SATURDAY)
        self.assertEqual(accepted["IPR_SUNDAY_SHOULD_SEND"], "false")

    def test_conflicting_send_and_preview_refused(self):
        with self.assertRaisesRegex(SundayHandoffRefused, "cannot both"):
            resolve_sunday_handoff(
                event="schedule", now=SUNDAY, send_email=True,
                scheduled_owner_preview=True, sunday_daily_marker="2026-10-11",
                pilot_owner_reviewed_week=SATURDAY,
                pilot_owner_reviewed_sha256="a" * 64,
            )

    def test_oct18_schedule_is_editor_only_despite_legacy_preview_flag(self):
        # The October 11 live failure combined both true modes. The workflow
        # now pins scheduled previews off; manual previews are still opt-in.
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SUNDAY_OWNER_PREVIEW: 'false'", workflow)
        self.assertNotIn("vars.IPR_SUNDAY_OWNER_PREVIEW_ENABLED", workflow)
        result = resolve_sunday_handoff(
            event="schedule",
            now=datetime(2026, 10, 18, 19, 17, tzinfo=timezone.utc),
            send_email=True,
            scheduled_owner_preview=False,
            sunday_daily_marker="2026-10-18",
            friday_delivery_enabled=False,
        )
        self.assertEqual(result["IPR_SUNDAY_WEEK_END"], "2026-10-17")
        self.assertEqual(result["IPR_SUNDAY_SHOULD_SEND"], "true")
        with self.assertRaisesRegex(SundayHandoffRefused, "parallel services"):
            resolve_sunday_handoff(
                event="schedule",
                now=datetime(2026, 10, 18, 19, 17, tzinfo=timezone.utc),
                send_email=True,
                scheduled_owner_preview=False,
                sunday_daily_marker="2026-10-18",
                friday_delivery_enabled=True,
            )

    def test_preview_still_requires_real_sunday_collection(self):
        for marker in ("", "2026-10-10", "2026-10-12"):
            with self.subTest(marker=marker), self.assertRaisesRegex(
                    SundayHandoffRefused, "success marker"):
                resolve_sunday_handoff(
                    event="schedule", now=SUNDAY, send_email=False,
                    scheduled_owner_preview=True,
                    sunday_daily_marker=marker,
                )

    def test_scheduled_editor_send_is_default_but_manual_stays_opt_in(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "if: github.event_name == 'workflow_dispatch' || "
            "github.event_name == 'schedule'", src,
        )
        self.assertIn(
            "SUNDAY_SEND: ${{ github.event_name == 'schedule' || "
            "(github.event_name == 'workflow_dispatch' && "
            "vars.IPR_SUNDAY_EDITOR_DELIVERY_ENABLED == 'true' && "
            "inputs.send_email == true) }}", src,
        )
        # This default must NOT weaken the first-edition human approval,
        # both scheduled-mode exclusivity and the Sunday corpus freshness.
        self.assertIn('IPR_SUNDAY_OWNER_REVIEWED_SHA256', src)
        self.assertIn("SUNDAY_OWNER_PREVIEW: 'false'", src)
        self.assertNotIn("vars.IPR_SUNDAY_OWNER_PREVIEW_ENABLED", src)
        self.assertIn('last_daily_run_date.txt', src)
        self.assertIn('friday_delivery_enabled=os.environ[', src)

    def test_workflow_sends_preview_only_to_owner_and_checks_both_modes(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("SUNDAY_OWNER_PREVIEW: 'false'", src)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.preview_to_owner == true", src)
        self.assertNotIn("vars.IPR_SUNDAY_OWNER_PREVIEW_ENABLED", src)
        # Preview intent must reach preflight, the Vietnam email-scope gate,
        # and final handoff. Three checks are intentional, not duplicate sends.
        self.assertEqual(src.count("env.SUNDAY_OWNER_PREVIEW == 'true' ||"), 3)
        self.assertIn("scheduled_owner_preview=os.environ[", src)
        self.assertIn('IPR_EDITOR_SEND_REQUESTED: ${{ env.SUNDAY_SEND == \'true\' }}', src)
        self.assertIn('if os.environ["IPR_EDITOR_SEND_REQUESTED"] == "true":', src)
        self.assertIn('owner.casefold() == editor.casefold()', src)
        self.assertIn("args+=(--preview-to-owner)", src)
        self.assertIn("args+=(--send)", src)
        self.assertIn('[[ "$IPR_PREVIEW_REQUESTED" != "true" ]]', src)
        self.assertLess(src.index("Preflight private owner preview"),
                        src.index("Require Sunday source readiness with verified editorial research"))
        self.assertLess(src.index("Separate Vietnam private-model and editor-email research scope"),
                        src.index("Require Sunday source readiness with verified editorial research"))
        self.assertLess(src.index("Require Sunday source readiness with verified editorial research"),
                        src.index("Generate source-cited Sunday manuscript"))
        self.assertLess(src.index("Attest Japan research offer"), src.index("Generate source-cited Sunday manuscript"))
        self.assertIn("last_daily_run_date.txt", src)
        self.assertIn("IPR_SUNDAY_OWNER_REVIEWED_SHA256", src)
        self.assertIn("permissions:" + chr(10) + "  contents: read", src)
        self.assertNotIn("actions/upload-artifact", src)
        self.assertNotIn("git push", src)


if __name__ == "__main__":
    unittest.main()
