"""Synthetic private processing recovery; no source access or paid calls."""
import copy
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from processing import daily_intake as intake, daily_runner as runner
from tests.test_indonesia_shared_daily import FAMILY, KEY, analyzer, policy, reading, record


class ProcessingRecovery(unittest.TestCase):
    def test_deferred_retry_retains_diagnostic_and_history_without_another_call(self):
        older = dict(record(), source_identity="kemhan:/synthetic-older.html")
        key = FAMILY + ":" + older["source_identity"]
        version = intake.digest({k: older[k] for k in (
            "metadata_version_sha256", "content_sha256", "capture_sha256")})
        prior = dict(version=version, status="retriable", attempts=3,
                     reason="analysis_or_quality_failed",
                     quality_hold="daily_name_or_office_unsupported")
        state = {key: prior}
        before = copy.deepcopy(state)
        fake = analyzer()
        result, _ = intake.process([record(), older], state, family=FAMILY,
            policy=policy(), analyzer_factory=lambda: fake)
        self.assertEqual(result[key], prior)
        self.assertEqual(state, before)
        fake.analyze_record.assert_called_once()
        # On a quiet cycle the same retry can use its remaining budget.
        fake = analyzer(dict(reading(), summary_english="Invalid."))
        result, _ = intake.process([record(), older], result, family=FAMILY,
            policy=policy(), analyzer_factory=lambda: fake)
        self.assertEqual((result[key]["status"], result[key]["attempts"]), ("retriable", 4))
        self.assertEqual(result[key]["quality_hold"], "daily_summary_invalid")

    def invoke(self, root, fake, *, no_release=False):
        db = root / "public.db"
        sqlite3.connect(db).close()
        def process(*args, **kwargs):
            return intake.process(*args, **kwargs, analyzer_factory=lambda: fake)
        with patch.object(runner, "verified_source", return_value=[record()]), \
             patch.object(runner, "bind_admitted_metadata", return_value=[record()]), \
             patch.object(runner, "load_policy", side_effect=policy), \
             patch.object(runner, "process", side_effect=process), \
             patch.dict(os.environ, {"DAILY_OUTPUT_KEY": KEY}):
            return runner.private_run(FAMILY + ",unused," + "c" * 40,
                public_db=db, state_path=root / "queue.json", out_dir=root / "envelopes",
                no_release=no_release)

    def test_routine_rejected_readings_remain_private_and_version_bound(self):
        rejected = dict(reading(), summary_english="Invalid.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for attempt in range(2):
                self.invoke(root, analyzer(rejected))
            snapshots = [json.loads(p.read_text()) for p in (root / "readings" / FAMILY).glob("*.json")]
            self.assertEqual(sorted(s["attempts_before"] for s in snapshots), [0, 1])
            for snapshot in snapshots:
                self.assertEqual(snapshot["reading"], rejected)
                self.assertEqual(snapshot["version"], intake.digest({k: record()[k] for k in (
                    "metadata_version_sha256", "content_sha256", "capture_sha256")}))
                self.assertEqual(snapshot["source_git_commit"], "c" * 40)
                self.assertEqual(snapshot["policy_sha256"], intake.digest(policy()["sources"][FAMILY]))
                self.assertEqual(len(snapshot["processor_commit"]), 40)
            queue = json.loads((root / "queue.json").read_text())
            entry = next(iter(queue.values()))
            self.assertEqual((entry["status"], entry["attempts"]), ("retriable", 2))
            self.assertEqual(entry["quality_hold"], "daily_summary_invalid")
            envelope = json.loads((root / "envelopes" / (FAMILY + ".json")).read_text())
            self.assertEqual(envelope["packet"]["records"], [])
            for path in (root / "queue.json", root / "envelopes" / (FAMILY + ".json")):
                self.assertNotIn(rejected["facts"][0]["evidence_translation"], path.read_text())
            self.assertFalse((root / "queue.reading.json").exists())

    def test_no_release_compatibility_and_completed_output_never_reprocessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.invoke(root, analyzer(), no_release=True)
            self.assertEqual(json.loads((root / "queue.reading.json").read_text()),
                             {record()["source_identity"]: reading()})
            before = (root / "queue.json").read_bytes()
            self.assertFalse((root / "envelopes").exists())
            fake = analyzer()
            self.invoke(root, fake)
            fake.analyze_record.assert_not_called()
            self.assertEqual((root / "queue.json").read_bytes(), before)
            self.assertEqual(len(list((root / "readings" / FAMILY).glob("*.json"))), 1)
            envelope = json.loads((root / "envelopes" / (FAMILY + ".json")).read_text())
            self.assertEqual(len(envelope["packet"]["records"]), 1)

    def test_downloaded_private_archive_recovers_reading_and_attempt_binding(self):
        rejected = dict(reading(), summary_english="Invalid.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "handoff"
            root.mkdir()
            self.invoke(root, analyzer(rejected))
            original = next((root / "readings" / FAMILY).glob("*.json"))
            retained_bytes = original.read_bytes()
            archive_path = Path(tmp) / "private-artifact.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for path in root.rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(root))
            original.unlink()  # Recovery must use the downloaded archive.
            recovered = Path(tmp) / "downloaded"
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(recovered)
            snapshots = list((recovered / "readings" / FAMILY).glob("*.json"))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].read_bytes(), retained_bytes)
            saved = json.loads(snapshots[0].read_text())
            self.assertEqual(saved["reading"], rejected)
            self.assertEqual(saved["source_family"], FAMILY)
            self.assertEqual(saved["source_identity"], record()["source_identity"])
            self.assertEqual(saved["source_git_commit"], "c" * 40)
            for field in ("metadata_version_sha256", "content_sha256", "capture_sha256"):
                self.assertEqual(saved[field], record()[field])
            self.assertEqual(saved["version"], intake.digest({k: saved[k] for k in (
                "metadata_version_sha256", "content_sha256", "capture_sha256")}))
            queue = json.loads((recovered / "queue.json").read_text())
            entry = queue[FAMILY + ":" + saved["source_identity"]]
            self.assertEqual(entry["version"], saved["version"])
            self.assertEqual(entry["attempts"], saved["attempts_before"] + 1)
            self.assertEqual(entry["quality_hold"], "daily_summary_invalid")
            envelope = (recovered / "envelopes" / (FAMILY + ".json")).read_text()
            self.assertEqual(json.loads(envelope)["packet"]["records"], [])
            for private_field in ("evidence", "evidence_translation", "reading", "prior_disposition"):
                self.assertNotIn('"' + private_field + '"', envelope)
            self.assertNotIn(rejected["facts"][0]["evidence_translation"], envelope)
            accepted, _ = intake.process([record()], {}, family=FAMILY,
                policy=policy(), analyzer_factory=analyzer)
            output = next(iter(accepted.values()))["output"]
            for private_field in ("evidence", "evidence_translation", "reading", "prior_disposition"):
                with self.subTest(private_field=private_field), self.assertRaises(intake.IntakeHold):
                    intake.validate_output(dict(output, **{private_field: saved}),
                                           FAMILY, policy()["sources"][FAMILY])

    def test_retention_failure_accounts_for_attempt_and_holds_before_signing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.invoke(root, analyzer(dict(reading(), summary_english="Invalid.")))
            envelope_path = root / "envelopes" / (FAMILY + ".json")
            with patch("tempfile.NamedTemporaryFile", side_effect=OSError("synthetic disk failure")):
                result = self.invoke(root, analyzer(dict(reading(), summary_english="Invalid.")))
            self.assertEqual(result["holds"], {record()["source_identity"]: "private_reading_preservation_failed"})
            entry = next(iter(json.loads((root / "queue.json").read_text()).values()))
            self.assertEqual(entry["attempts"], 2)
            self.assertEqual((entry["status"], entry["reason"]),
                             ("held", "private_reading_preservation_failed"))
            self.assertEqual(json.loads(envelope_path.read_text())["packet"]["records"], [])
            fake = analyzer()
            self.invoke(root, fake)
            fake.analyze_record.assert_not_called()

    def test_qa_pass_with_failed_retention_keeps_output_private_and_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("tempfile.NamedTemporaryFile", side_effect=OSError("synthetic disk failure")):
                self.invoke(root, analyzer())
            entry = next(iter(json.loads((root / "queue.json").read_text()).values()))
            self.assertEqual(entry["status"], "held")
            self.assertEqual(entry["output"]["summary"], reading()["summary_english"])
            self.assertEqual(entry["attempts"], 0)
            envelope = json.loads((root / "envelopes" / (FAMILY + ".json")).read_text())
            self.assertEqual(envelope["packet"]["records"], [])


if __name__ == "__main__":
    unittest.main()
