"""Offline proof: manual Sunday delivery resends EXACT verified owner-reviewed bytes."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_editorial_handoff import packet_identity, render_packet
from scripts.sunday_send_reviewed_packet import (
    ReviewedHandoffRefused, handoff, inspect_reviewed_attachment,
    main, validate_file,
)
from tests.test_briefs_editorial_evidence import scaffold
from tests.test_weekly_briefs_auto_writer import valid_manuscript

WEEK = "2026-10-10"
SUNDAY = datetime(2026, 10, 11, 19, 17, tzinfo=timezone.utc)
THURSDAY = datetime(2026, 10, 15, 19, 17, tzinfo=timezone.utc)


def create_reviewed_packet(folder):
    path = Path(folder) / "IPR-Briefs-Editorial-2026-10-10.txt"
    text = render_packet(
        scaffold(), manuscript=valid_manuscript(), as_of=WEEK,
    )
    path.write_bytes(text.encode("utf-8"))
    return path


class ReviewedPacketManualHandoff(unittest.TestCase):
    def test_default_dry_run_has_receipt_and_no_model_or_smtp(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            with patch.dict(os.environ, {}, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as email:
                receipt = handoff(file, WEEK, now=SUNDAY)
            self.assertEqual(receipt["attachment_sha256"],
                             hashlib.sha256(file.read_bytes()).hexdigest())
            self.assertEqual(receipt["week_ending"], WEEK)
            self.assertFalse(receipt["email_sent"])
            self.assertFalse(receipt["automated_model_called"])
            self.assertFalse(receipt["exact_owner_approval_matches"])
            self.assertFalse(receipt["publication_authorized"])
            email.assert_not_called()

    def test_exact_reviewed_file_digest_and_week_both_required_to_send(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            true_digest = hashlib.sha256(file.read_bytes()).hexdigest()
            for wrong_week, wrong_digest in (
                ("", true_digest), ("2026-10-03", true_digest),
                (WEEK, ""), (WEEK, "A" * 64), (WEEK, "0" * 64),
                (WEEK, true_digest + " "),
            ):
                with self.subTest(wrong_week=wrong_week, digest=wrong_digest):
                    with patch.dict(os.environ, {
                        "IPR_SUNDAY_OWNER_REVIEWED_WEEK": wrong_week,
                        "IPR_SUNDAY_OWNER_REVIEWED_SHA256": wrong_digest,
                    }, clear=True), patch(
                        "scripts.sunday_send_reviewed_packet.send_packet"
                    ) as smtp:
                        with self.assertRaisesRegex(
                            ReviewedHandoffRefused, "exact approved"
                        ):
                            handoff(file, WEEK, send=True,
                                    owner_confirmed=True, now=SUNDAY)
                        smtp.assert_not_called()

    def test_mutation_after_owner_review_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            expected = hashlib.sha256(file.read_bytes()).hexdigest()
            text = file.read_text(encoding="utf-8")
            file.write_text(text.replace("Two institutions described",
                                         "Three institutions described"),
                            encoding="utf-8")
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": expected,
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaises(ReviewedHandoffRefused):
                    handoff(file, WEEK, send=True, owner_confirmed=True, now=SUNDAY)
                send.assert_not_called()

    def test_valid_approved_send_uses_exact_snapshot_and_never_generates(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            approved_bytes = file.read_bytes()
            digest = hashlib.sha256(approved_bytes).hexdigest()
            captured = []
            def fake_send(path, week_ending, *, provisional=False, full_week=False,
                          owner_released=False):
                # The owner's confirmed exact-digest approval is the release.
                self.assertTrue(owner_released)
                captured.append((week_ending, path.read_bytes(), full_week, provisional))
                self.assertNotEqual(path, file)
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet",
                side_effect=fake_send,
            ) as send:
                output = handoff(file, WEEK, send=True,
                                 owner_confirmed=True, now=SUNDAY)
            self.assertEqual(captured, [(WEEK, approved_bytes, True, True)])
            self.assertEqual(send.call_count, 1)
            self.assertTrue(output["email_sent"])
            self.assertFalse(output["automated_model_called"])
            self.assertFalse(output["publication_authorized"])

    def test_historical_manual_send_requires_additional_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaisesRegex(
                    ReviewedHandoffRefused, "allow-historical-send"
                ):
                    handoff(file, WEEK, send=True,
                            owner_confirmed=True, now=THURSDAY)
                self.assertFalse(
                    handoff(file, WEEK, now=THURSDAY)["email_sent"]
                )
                self.assertTrue(handoff(
                    file, WEEK, send=True, owner_confirmed=True,
                    historical_override=True, now=THURSDAY,
                )["email_sent"])
                self.assertEqual(send.call_count, 1)

    def test_manual_send_refuses_parallel_friday_or_same_owner_recipient(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            approved = hashlib.sha256(file.read_bytes()).hexdigest()
            baseline = {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": approved,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }
            for override, expected in (
                ({"IPR_EDITOR_DELIVERY_ENABLED": "true"}, "IPR_EDITOR_DELIVERY_ENABLED"),
                ({"IPR_SUNDAY_EDITOR_DELIVERY_ENABLED": "true"}, "IPR_SUNDAY_EDITOR_DELIVERY_ENABLED"),
                ({"IPR_PREVIEW_TO": "EDITOR@example.com"}, "differ"),
                ({"IPR_PREVIEW_TO": ""}, "distinct configured"),
                ({"IPR_EDITOR_TO": ""}, "distinct configured"),
            ):
                with self.subTest(override=override), patch.dict(
                    os.environ, dict(baseline, **override), clear=True
                ), patch("scripts.sunday_send_reviewed_packet.send_packet") as smtp:
                    with self.assertRaisesRegex(ReviewedHandoffRefused, expected):
                        handoff(file, WEEK, send=True,
                                owner_confirmed=True, now=SUNDAY)
                    smtp.assert_not_called()

    def test_no_confirmation_means_no_smtp_even_when_digest_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, {
                "IPR_SUNDAY_OWNER_REVIEWED_WEEK": WEEK,
                "IPR_SUNDAY_OWNER_REVIEWED_SHA256": digest,
                "IPR_EDITOR_TO": "editor@example.com",
                "IPR_PREVIEW_TO": "owner@example.com",
            }, clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaises(ReviewedHandoffRefused):
                    handoff(file, WEEK, send=True,
                            owner_confirmed=False, now=SUNDAY)
                send.assert_not_called()

    def test_malformed_packet_or_week_refuses_before_smtp(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            content = file.read_text(encoding="utf-8")
            for changed in (
                content.replace("Packet: IPR-2026-10-10",
                                "Packet: IPR-2026-10-03"),
                content.replace("Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED",
                                "Status: APPROVED"),
                content.replace("END OF SOURCE APPENDIX", "MISSING END"),
                content + "FORGED EXTRA AFTER END",
                content.replace("=== SOURCE APPENDIX — DO NOT EDIT ===", ""),
                content.replace("=== SOURCE APPENDIX — DO NOT EDIT ===",
                                "=== SOURCE APPENDIX — DO NOT EDIT ===\n"
                                "=== SOURCE APPENDIX — DO NOT EDIT ==="),
                "not an editorial packet",
            ):
                with self.subTest(changed=changed[:65]):
                    file.write_text(changed, encoding="utf-8")
                    with self.assertRaises(ReviewedHandoffRefused):
                        validate_file(file, WEEK, now=SUNDAY)
            file.write_text(content, encoding="utf-8")
            for bad in ("2026-10-09", "2026-10-17", "2026-10-10 ", "no"):
                with self.subTest(week=bad), self.assertRaises(ReviewedHandoffRefused):
                    validate_file(file, bad, now=SUNDAY)
            with self.assertRaisesRegex(ReviewedHandoffRefused,
                                        "has not ended"):
                validate_file(file, WEEK, now=datetime(
                    2026, 10, 10, 19, tzinfo=timezone.utc
                ))

    def test_symlink_and_binary_and_oversize_files_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            link = Path(folder) / "alias.txt"
            link.symlink_to(file)
            with self.assertRaisesRegex(ReviewedHandoffRefused, "symlink"):
                validate_file(link, WEEK, now=SUNDAY)
            invalid = Path(folder) / "invalid.txt"
            invalid.write_bytes(b"\xff" * 20)
            with self.assertRaises(ReviewedHandoffRefused):
                validate_file(invalid, WEEK, now=SUNDAY)
            oversize = Path(folder) / "huge.txt"
            oversize.write_bytes(b"Z" * 3_000_001)
            with self.assertRaisesRegex(ReviewedHandoffRefused, "large"):
                validate_file(oversize, WEEK, now=SUNDAY)

    def test_cli_defaults_to_offline_and_has_no_send_control_in_dry_run(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            with patch("scripts.sunday_send_reviewed_packet.send_packet") as send:
                with patch("scripts.sunday_send_reviewed_packet.datetime") as clock:
                    clock.now.return_value = SUNDAY
                    self.assertEqual(main([
                        "--packet", str(file), "--week-ending", WEEK,
                    ]), 0)
                send.assert_not_called()
            with self.assertRaises(SystemExit):
                main(["--packet", str(file), "--week-ending", WEEK,
                      "--confirm-owner-reviewed"])


def create_additional_packet(folder, slug="taiwan-strait-drills"):
    path = Path(folder) / ("IPR-Briefs-Editorial-2026-10-10-%s.txt" % slug)
    text = render_packet(
        scaffold(), manuscript=valid_manuscript(), as_of=WEEK,
        companion_slug=slug,
    )
    path.write_bytes(text.encode("utf-8"))
    return path


class AdditionalBriefAndNamedEditor(unittest.TestCase):
    """A second Brief of the same week is a distinct, separately approved file."""

    APPROVED_ENV = {
        "IPR_EDITOR_TO": "editor@example.com",
        "IPR_PREVIEW_TO": "owner@example.com",
    }

    def test_identity_helper_keeps_primary_and_refuses_unsafe_slugs(self):
        self.assertEqual(packet_identity(WEEK), "IPR-2026-10-10")
        self.assertEqual(packet_identity(WEEK, "second-story"),
                         "IPR-2026-10-10-second-story")
        for bad in ("", "Second", "-lead", "a b", "a/b", "x" * 81, "2026-10-10"):
            with self.subTest(slug=bad), self.assertRaises(ValueError):
                packet_identity(WEEK, bad)

    def test_additional_worksheet_validates_with_its_own_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            primary = create_reviewed_packet(folder)
            extra = create_additional_packet(folder)
            receipt = handoff(extra, WEEK, now=SUNDAY)
            self.assertEqual(receipt["packet_identity"],
                             "IPR-2026-10-10-taiwan-strait-drills")
            self.assertEqual(receipt["companion_slug"], "taiwan-strait-drills")
            self.assertFalse(receipt["email_sent"])
            primary_receipt = handoff(primary, WEEK, now=SUNDAY)
            self.assertEqual(primary_receipt["packet_identity"], "IPR-2026-10-10")
            self.assertIsNone(primary_receipt["companion_slug"])
            # Separate files, separate digests: one approval never covers both.
            self.assertNotEqual(receipt["attachment_sha256"],
                                primary_receipt["attachment_sha256"])

    def test_additional_worksheet_with_wrong_week_or_bad_slug_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_additional_packet(folder)
            content = file.read_text(encoding="utf-8")
            for changed in (
                content.replace("Packet: IPR-2026-10-10-taiwan-strait-drills",
                                "Packet: IPR-2026-10-03-taiwan-strait-drills"),
                content.replace("Packet: IPR-2026-10-10-taiwan-strait-drills",
                                "Packet: IPR-2026-10-10-Taiwan"),
                content.replace("Packet: IPR-2026-10-10-taiwan-strait-drills",
                                "Packet: IPR-2026-10-10-"),
            ):
                with self.subTest(changed=changed.splitlines()[1]):
                    file.write_text(changed, encoding="utf-8")
                    with self.assertRaises(ReviewedHandoffRefused):
                        validate_file(file, WEEK, now=SUNDAY)

    def test_primary_approval_digest_cannot_release_the_additional_brief(self):
        with tempfile.TemporaryDirectory() as folder:
            primary = create_reviewed_packet(folder)
            extra = create_additional_packet(folder)
            primary_digest = hashlib.sha256(primary.read_bytes()).hexdigest()
            with patch.dict(os.environ, dict(
                self.APPROVED_ENV,
                IPR_SUNDAY_OWNER_REVIEWED_WEEK=WEEK,
                IPR_SUNDAY_OWNER_REVIEWED_SHA256=primary_digest,
            ), clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                with self.assertRaisesRegex(ReviewedHandoffRefused, "exact approved"):
                    handoff(extra, WEEK, send=True, owner_confirmed=True, now=SUNDAY)
                send.assert_not_called()

    def test_additional_send_passes_identity_and_named_editor(self):
        with tempfile.TemporaryDirectory() as folder:
            extra = create_additional_packet(folder)
            digest = hashlib.sha256(extra.read_bytes()).hexdigest()
            with patch.dict(os.environ, dict(
                self.APPROVED_ENV,
                IPR_SUNDAY_OWNER_REVIEWED_WEEK=WEEK,
                IPR_SUNDAY_OWNER_REVIEWED_SHA256=digest,
            ), clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                receipt = handoff(extra, WEEK, send=True, owner_confirmed=True,
                                  editor_to="Ana@Example.com", now=SUNDAY)
            send.assert_called_once()
            kwargs = send.call_args.kwargs
            self.assertEqual(kwargs["companion_slug"], "taiwan-strait-drills")
            self.assertEqual(kwargs["editor_to"], "Ana@Example.com")
            self.assertTrue(kwargs["owner_released"])
            self.assertTrue(receipt["email_sent"])
            self.assertEqual(receipt["assigned_editor"], "Ana@Example.com")

    def test_named_editor_recorded_on_dry_run_and_checked_against_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    handoff(file, WEEK, editor_to="ana@example.com",
                            now=SUNDAY)["assigned_editor"],
                    "ana@example.com")
                with self.assertRaises(ValueError):
                    handoff(file, WEEK, editor_to="a@example.com, b@example.com",
                            now=SUNDAY)
            # The dry run catches an owner-as-editor slip before any approval step.
            with patch.dict(os.environ, self.APPROVED_ENV, clear=True):
                with self.assertRaisesRegex(ReviewedHandoffRefused, "differ"):
                    handoff(file, WEEK, editor_to="Owner@Example.com", now=SUNDAY)
            with patch.dict(os.environ, dict(
                self.APPROVED_ENV,
                IPR_SUNDAY_OWNER_REVIEWED_WEEK=WEEK,
                IPR_SUNDAY_OWNER_REVIEWED_SHA256=digest,
            ), clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                for editor, expected in (
                    ("OWNER@example.com", "differ"),
                    ("two@example.com, three@example.com", "distinct configured"),
                ):
                    with self.subTest(editor=editor), self.assertRaisesRegex(
                        ReviewedHandoffRefused, expected
                    ):
                        handoff(file, WEEK, send=True, owner_confirmed=True,
                                editor_to=editor, now=SUNDAY)
                send.assert_not_called()

    def test_primary_send_without_editor_keeps_the_old_call(self):
        with tempfile.TemporaryDirectory() as folder:
            file = create_reviewed_packet(folder)
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(os.environ, dict(
                self.APPROVED_ENV,
                IPR_SUNDAY_OWNER_REVIEWED_WEEK=WEEK,
                IPR_SUNDAY_OWNER_REVIEWED_SHA256=digest,
            ), clear=True), patch(
                "scripts.sunday_send_reviewed_packet.send_packet"
            ) as send:
                receipt = handoff(file, WEEK, send=True, owner_confirmed=True,
                                  now=SUNDAY)
            self.assertEqual(set(send.call_args.kwargs),
                             {"provisional", "full_week", "owner_released"})
            self.assertEqual(receipt["assigned_editor"], "editor@example.com")



class AdditionalBriefWorksheetCommand(unittest.TestCase):
    """The handoff CLI writes an additional worksheet without composing or sending."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.sidecar = root / "draft.json"
        self.sidecar.write_text(json.dumps(scaffold()), encoding="utf-8")
        self.manuscript = root / "second.json"
        self.manuscript.write_text(json.dumps(valid_manuscript()), encoding="utf-8")
        self.out = root / "IPR-Briefs-Editorial-2026-10-10-second-story.txt"

    def run_cli(self, *extra):
        from scripts.sunday_editorial_handoff import main as handoff_main
        return handoff_main(["--sidecar", str(self.sidecar), "--out", str(self.out),
                             *extra])

    def test_writes_reviewable_worksheet_addressed_to_any_editor(self):
        with patch("scripts.sunday_editorial_handoff.send_packet") as email, patch(
                "scripts.sunday_briefs_auto_writer.compose") as compose:
            self.run_cli("--companion-slug", "second-story",
                         "--manuscript", str(self.manuscript))
        email.assert_not_called()
        compose.assert_not_called()
        text = self.out.read_text(encoding="utf-8")
        self.assertIn("Packet: IPR-2026-10-10-second-story\n", text)
        self.assertIn("EDITOR: Edit the writing sections", text)
        self.assertNotIn("DYLAN:", text)
        receipt = handoff(self.out, WEEK, now=SUNDAY)
        self.assertEqual(receipt["companion_slug"], "second-story")
        # The primary worksheet still addresses Dylan exactly as before.
        primary = render_packet(scaffold(), manuscript=valid_manuscript(), as_of=WEEK)
        self.assertIn("DYLAN: Edit the writing sections", primary)

    def test_editor_return_is_checked_only_against_its_own_original(self):
        from scripts.validate_editorial_return import (
            ReturnValidationError, validate_return,
        )
        companion = create_additional_packet(self.folder.name, "second-story").read_text(
            encoding="utf-8")
        primary = render_packet(scaffold(), manuscript=valid_manuscript(), as_of=WEEK)
        edited = companion.replace("## WORKING TITLE\n", "## WORKING TITLE\nEditor note: shorter. ", 1)
        self.assertEqual(validate_return(companion, edited)["packet"],
                         "Packet: IPR-2026-10-10-second-story")
        with self.assertRaisesRegex(ReturnValidationError, "immutable header"):
            validate_return(primary, edited)

    def test_refuses_existing_output_rather_than_overwriting(self):
        self.out.write_text("reviewed bytes", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_cli("--companion-slug", "second-story",
                         "--manuscript", str(self.manuscript))
        self.assertEqual(self.out.read_text(encoding="utf-8"), "reviewed bytes")

    def test_refuses_composition_email_and_half_specified_requests(self):
        cases = (
            ("--companion-slug", "second-story"),
            ("--manuscript", str(self.manuscript)),
            ("--companion-slug", "Second Story", "--manuscript", str(self.manuscript)),
            ("--companion-slug", "second-story", "--manuscript", str(self.manuscript),
             "--write-automatic", "--as-of", WEEK),
            ("--companion-slug", "second-story", "--manuscript", str(self.manuscript),
             "--send"),
            ("--companion-slug", "second-story", "--manuscript", str(self.manuscript),
             "--preview-to-owner"),
        )
        for extra in cases:
            with self.subTest(extra=extra), patch(
                    "scripts.sunday_editorial_handoff.send_packet") as email, \
                    patch("sys.stderr"), self.assertRaises(SystemExit):
                self.run_cli(*extra)
            email.assert_not_called()
            self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
