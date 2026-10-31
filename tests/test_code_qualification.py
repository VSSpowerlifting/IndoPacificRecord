"""Offline Daily decisions: disposable Git snapshots and authenticated API mocks.

No production workflows, source fetches, model calls or tracked DB writes.
"""
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from types import SimpleNamespace

from scripts import code_qualification as q
from scripts.validate_output import validate
from tests.test_pr_workflow_contract import _parse

ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENT = "a" * 64


class LocalGit(q.Git):
    def obtain(self, revision):
        # All immutable candidate objects already exist in this disposable repo.
        self.run("cat-file", "-e", revision + "^{commit}")


class API:
    def __init__(self, run, job):
        self.run, self.job = run, job
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "actions/workflows/pr_offline_checks.yml":
            return {"id": 12, "path": q.WORKFLOW, "state": "active"}
        if path.startswith("actions/workflows/12/runs?"):
            return {"workflow_runs": [self.run]}
        if path == "actions/runs/42/attempts/2/jobs?per_page=100":
            return {"total_count": 1, "jobs": [self.job]}
        raise AssertionError("Unexpected API call: " + path)


class QualificationSnapshots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git = LocalGit(self.root)
        self.git.run("init", "-q")
        self.git.run("config", "user.name", "Qualification test")
        self.git.run("config", "user.email", "qualification@example.invalid")
        for path, content in {
            "pipeline.py": "# original code\n",
            q.WORKFLOW: (ROOT / q.WORKFLOW).read_text(),
            ".github/workflows/daily_update.yml": (ROOT / ".github/workflows/daily_update.yml").read_text(),
            "pla_watch.db": "original snapshot",
            "output/index.html": "original render",
            "output/data/articles.json": "[]",
        }.items():
            self.write(path, content)
        self.commit("base")
        self.base = self.git.revision()
        self.write("pipeline.py", "# reviewed change\n")
        self.commit("PR head")
        self.head = self.git.revision()
        # Build a genuine two-parent synthetic merge without sharing any refs.
        tree = self.git.run("rev-parse", "HEAD^{tree}").decode().strip()
        self.synthetic = self.git.run("commit-tree", tree, "-p", self.base,
                                   "-p", self.head, "-m", "synthetic PR merge").decode().strip()
        # A squash merge on main need not retain the synthetic merge or PR head.
        self.git.run("checkout", "--detach", self.base)
        self.git.run("read-tree", "--reset", "-u", tree)
        self.commit("reviewed squash merge")
        self.current = self.git.revision()
        self.tested = self.current
        self.run = {"id": 42, "run_attempt": 2, "workflow_id": 12,
                    "repository": {"full_name": q.REPOSITORY},
                    "head_repository": {"full_name": q.REPOSITORY},
                    "event": "push", "head_branch": "main", "path": q.WORKFLOW,
                    "status": "completed", "conclusion": "success", "head_sha": self.tested}
        self.job = {"id": 99, "run_id": 42, "run_attempt": 2, "name": "offline-checks",
                    "status": "completed", "conclusion": "success", "head_sha": self.tested,
                    "labels": ["ubuntu-24.04"], "steps": [
                        {"name": name, "status": "completed", "conclusion": "success"}
                        for name in (*q.REQUIRED_STEPS,
                                     f"Qualification environment {ENVIRONMENT}")]}
        self.api = API(self.run, self.job)

    def write(self, path, content):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    def commit(self, message):
        self.git.run("add", ".")
        self.git.run("commit", "-qm", message)

    def decision(self, environment=ENVIRONMENT, workflow=None):
        return q.decide(self.api, self.git, environment, workflow or self.current)

    def test_trusted_full_main_push_with_exact_equivalent_inputs(self):
        result = self.decision()
        self.assertTrue(result["reused"], result)
        self.assertEqual(result["current"], self.current)
        self.assertEqual(result["evidence"]["tested"], self.tested)
        self.assertEqual(result["evidence"]["attempt"], 2)
        self.assertIn("attempts/2/jobs", self.api.calls[-1])

    def test_data_growth_and_operational_state_do_not_requalify_code(self):
        before = self.git.inputs(self.current)
        for path in ("pla_watch.db", "output/index.html", "output/data/articles.json",
                     "output/record/new-98765.html", "output/week-2026-11-02.html",
                     ".github/state/last_daily_run_date.txt", ".github/state/llm_usage.jsonl"):
            self.write(path, "legitimate later snapshot")
        self.commit("routine data growth")
        self.assertEqual(before, self.git.inputs(self.git.revision()))
        self.assertTrue(self.decision()["reused"])

    def test_all_unknown_execution_inputs_invalidate(self):
        paths = ("pipeline.py", "requirements.txt", "uv.lock", q.WORKFLOW,
                 "tests/test_new.py", "migrations/999_new.sql", "site/preview/templates/base.html",
                 "analysis/prompts/new.txt", "config/source_policy.json", "desks/china/manifest.json",
                 "docs/source-rights.md", "output/new.py", "output/assets/new.js",
                 "output/the-pla-watch/posts/2026-08-15.json", "state/unknown.json")
        for path in paths:
            with self.subTest(path=path):
                prior = self.git.revision()
                self.write(path, "changed behavior")
                self.commit("changed input")
                result = self.decision()
                self.assertFalse(result["reused"])
                self.assertIn("execution inputs changed", result["reason"])
                self.git.run("checkout", "--detach", prior)

    def test_deleted_input_and_mutable_path_mode_change_invalidate(self):
        (self.root / "pipeline.py").unlink()
        self.commit("removed code")
        self.assertFalse(self.decision()["reused"])
        self.git.run("checkout", "--detach", self.current)
        self.git.run("update-index", "--chmod=+x", "output/index.html")
        self.git.run("commit", "-qm", "executable generated path")
        self.assertFalse(self.decision()["reused"])

    def test_wrong_repository_workflow_event_revision_attempt_or_runner(self):
        mutations = (
            ("run", "repository", {"full_name": "attacker/fork"}),
            ("run", "head_repository", {"full_name": "attacker/fork"}),
            ("run", "workflow_id", 13), ("run", "path", ".github/workflows/forged.yml"),
            ("run", "event", "workflow_dispatch"), ("run", "head_sha", self.base),
            ("run", "event", "pull_request"), ("run", "head_branch", "attacker"),
            ("job", "run_attempt", 1), ("job", "run_id", 43),
            ("job", "head_sha", self.base), ("job", "labels", ["self-hosted"]),
        )
        for kind, key, value in mutations:
            with self.subTest(kind=kind, key=key):
                target = getattr(self, kind)
                before = copy.deepcopy(target[key])
                target[key] = value
                self.assertFalse(self.decision()["reused"])
                target[key] = before

    def test_failed_skipped_cancelled_incomplete_and_focused_checks_rejected(self):
        for target in (self.run, self.job, *self.job["steps"]):
            for conclusion in ("failure", "skipped", "cancelled", None):
                with self.subTest(target=target.get("name", "run"), conclusion=conclusion):
                    target["conclusion"] = conclusion
                    self.assertFalse(self.decision()["reused"])
            target["conclusion"] = "success"
        self.run["status"] = "in_progress"
        self.assertFalse(self.decision()["reused"])
        self.run["status"] = "completed"
        # A success badge cannot override the scope recalculated from Git.
        for mode in ("focused", "docs"):
            with patch.object(self.git, "scope", return_value=q.classify(["README.md"]) if mode == "docs"
                              else q.classify(["site/preview/timelines.css"])):
                self.assertFalse(self.decision()["reused"])

    def test_forged_or_missing_environment_receipt_rejected(self):
        receipt = self.job["steps"][-1]
        for name in ("qualified", f"Qualified inputs {self.synthetic} environment {ENVIRONMENT}",
                     f"Qualification environment {'b' * 64}"):
            with self.subTest(name=name):
                receipt["name"] = name
                self.assertFalse(self.decision()["reused"])
        self.job["steps"].pop()
        self.assertFalse(self.decision()["reused"])

    def test_pr_cannot_forge_a_trusted_synthetic_tree_or_workflow_revision(self):
        tree = self.git.run("rev-parse", self.tested + "^{tree}").decode().strip()
        foreign = self.git.run("commit-tree", tree, "-m", "unrelated root").decode().strip()
        merge = self.git.run("commit-tree", tree, "-p", foreign, "-p", self.head,
                             "-m", "wrong base").decode().strip()
        self.run.update(event="pull_request", head_sha=self.head)
        self.job["head_sha"] = self.head
        # Even an equivalent tree with hand-crafted merge parents and a green
        # full job cannot authenticate the PR's actually executed workflow.
        self.job["steps"][-1]["name"] = f"Qualified inputs {merge} environment {ENVIRONMENT}"
        result = self.decision()
        self.assertFalse(result["reused"])
        self.assertIn("trusted main-push", result["reason"])

    def test_wrong_main_revision_even_with_equal_tree_is_rejected(self):
        self.run["head_sha"] = self.synthetic
        self.job["head_sha"] = self.synthetic
        result = self.decision()
        self.assertFalse(result["reused"])
        self.assertIn("not an ancestor", result["reason"])

    def test_main_data_lane_uses_exact_same_closed_input_classification(self):
        from scripts.pr_ci_scope import main_push_scope, Scope
        self.write("output/record/new-123.html", "new rendered record")
        self.commit("data advance")
        self.assertEqual(main_push_scope(self.root, self.current, self.git.revision(),
                                        ["output/record/new-123.html"]), Scope("data", False, False))
        prior = self.git.revision()
        self.write("output/new-code.js", "code")
        self.commit("unknown generated directory file")
        self.assertEqual(main_push_scope(self.root, prior, self.git.revision(),
                                        ["output/new-code.js"]).mode, "full")

    def test_genuine_current_db_growth_still_passes_mandatory_runtime_check(self):
        from tests.test_migrations import build_legacy_db
        from tests.test_reconcile import migrate, add_run, add_article
        db = self.root / "pla_watch.db"
        db.unlink()
        build_legacy_db(db)
        migrate(db)
        add_run(db, 98765)
        add_article(db, 98765, 98765, "qualification-fixture")
        # Checkpoint disposable WAL before committing its self-contained image.
        with sqlite3.connect(db) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        for sidecar in self.root.glob("pla_watch.db-*"):
            sidecar.unlink()
        self.commit("valid production snapshot growth")
        self.assertTrue(self.decision()["reused"])
        checked = subprocess.run([sys.executable, str(ROOT / "scripts/verify_db_current.py"),
                                  "--db", str(db)], capture_output=True)
        self.assertEqual(checked.returncode, 0, checked.stderr.decode())
        self.assertIn(b"integrity and foreign keys clean", checked.stdout)

    def test_current_environment_and_executing_daily_version_must_match(self):
        for environment in (None, "", "b" * 64):
            self.assertFalse(self.decision(environment)["reused"])
        self.write(".github/workflows/daily_update.yml", "different workflow")
        self.commit("workflow advanced since queue trigger")
        self.assertIn("executing Daily workflow differs", self.decision()["reason"])

    def test_unavailable_forged_or_incomplete_api_evidence_falls_back(self):
        for response in ({}, {"total_count": 2, "jobs": [self.job]}):
            with patch.object(self.api, "get", side_effect=lambda path: response):
                self.assertFalse(self.decision()["reused"])
        for failure in (OSError("offline"), TimeoutError("unavailable")):
            with patch.object(self.api, "get", side_effect=failure):
                self.assertFalse(self.decision()["reused"])
        self.api.run = dict(self.run, conclusion="failure")
        self.assertFalse(self.decision()["reused"])

    def test_replay_required_when_source_replay_was_applicable(self):
        with patch.object(self.git, "scope", return_value=q.classify(["tests/test_topic_pilot.py"])):
            self.assertFalse(self.decision()["reused"])
            self.job["steps"].append({"name": "Replay all frozen pilot sources and independent review excerpts",
                                      "status": "completed", "conclusion": "success"})
            self.assertTrue(self.decision()["reused"])

    def test_dirty_or_untracked_inputs_cannot_reuse(self):
        self.write("pipeline.py", "uncommitted executable")
        self.assertFalse(self.decision()["reused"])
        self.git.run("restore", "pipeline.py")
        self.write("untracked.py", "untracked executable")
        self.assertFalse(self.decision()["reused"])

    def test_qualified_code_does_not_validate_broken_current_output(self):
        self.write("output/index.html", "{{ broken render }}")
        self.write("output/data/articles.json", "not json")
        self.commit("broken data/render snapshot")
        self.assertTrue(self.decision()["reused"])
        errors, _ = validate(self.root / "output")
        self.assertTrue(any("unrendered Jinja" in e for e in errors))
        self.assertTrue(any("does not parse" in e for e in errors))

    def test_qualified_code_does_not_validate_broken_current_database(self):
        (self.root / "pla_watch.db").unlink()
        with sqlite3.connect(self.root / "pla_watch.db") as db:
            db.execute("CREATE TABLE incorrect (id INTEGER)")
        self.commit("invalid production schema")
        self.assertTrue(self.decision()["reused"])
        result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_db_current.py"),
                                 "--db", str(self.root / "pla_watch.db")], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"not fully current", result.stderr)


class ResolvedEnvironment(unittest.TestCase):
    def test_resolved_packages_native_libraries_and_image_invalidate(self):
        image = {"ImageOS": "ubuntu24", "ImageVersion": "20261031.1",
                 "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64"}
        distribution = SimpleNamespace(metadata={"Name": "dependency"}, version="1.0",
                                       read_text=lambda name: "wheel hashes" if name == "RECORD" else None)
        pw = MagicMock()
        browser = pw.return_value.__enter__.return_value.chromium.launch.return_value
        browser.version = "123.0"
        with patch.dict(os.environ, image), \
                patch.dict(sys.modules, {"playwright.sync_api": SimpleNamespace(sync_playwright=pw)}), \
                patch.object(q.importlib.metadata, "distributions", return_value=[distribution]), \
                patch.object(q.subprocess, "check_output", return_value="native=1\n") as system:
            original = q.environment_identity()
            self.assertEqual(original, q.environment_identity())
            distribution.version = "2.0"
            self.assertNotEqual(original, q.environment_identity())
            distribution.version = "1.0"
            system.return_value = "native=2\n"
            self.assertNotEqual(original, q.environment_identity())
            system.return_value = "native=1\n"
            with patch.dict(os.environ, {"ImageVersion": "20261101.1"}):
                self.assertNotEqual(original, q.environment_identity())
            browser.version = "124.0"
            self.assertNotEqual(original, q.environment_identity())
            browser.close.assert_called()

    def test_unavailable_environment_selects_full_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github-output"
            with patch.object(sys, "argv", ["qualification", "environment", "--github-output", str(output)]), \
                    patch.object(q, "environment_identity", side_effect=OSError("unavailable")):
                q.main()
            self.assertEqual(output.read_text(), "digest=\n")


class DailyCaller(unittest.TestCase):
    def setUp(self):
        self.doc = _parse((ROOT / ".github/workflows/daily_update.yml").read_text())
        self.steps = self.doc["jobs"]["update"]["steps"]
        self.named = {s["name"]: s for s in self.steps}

    def test_only_development_suite_is_conditional_on_reuse(self):
        suite = self.named["Run offline test suite"]
        self.assertIn("steps.qualification.outputs.reused != 'true'", suite["if"])
        for name in ("Apply database migrations", "Verify database schema and invariants",
                     "Reconciliation contract check", "Run pipeline", "Validate rendered output",
                     "Assert offline tests left the tracked database unchanged",
                     "Deploy to GitHub Pages", "Reconcile Vietnam SQLite, HTML and Pages",
                     "Reconcile Japan SQLite, HTML and Pages"):
            self.assertNotIn("qualification", self.named[name].get("if", ""))
            self.assertNotIn("continue-on-error", self.named[name])
        self.assertEqual(self.doc["permissions"]["actions"], "read")
        env = self.named["Resolve trusted full qualification"]["env"]
        self.assertEqual(env["DAILY_WORKFLOW_SHA"], "${{ github.workflow_sha }}")

    def test_fallback_failure_stops_before_collection_or_spending(self):
        # Execute the actual workflow fallback shell under Actions' bash -e
        # semantics with a disposable failing Python. Later collection cannot run.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / "python"
            fake.write_text("#!/bin/sh\nexit 17\n")
            fake.chmod(0o755)
            command = self.named["Run offline test suite"]["run"]
            result = subprocess.run(["bash", "-e", "-c", command + "\ntouch collected-or-spent"],
                                    cwd=root, env=dict(os.environ, PATH=temp + os.pathsep + os.environ["PATH"]))
            self.assertEqual(result.returncode, 17)
            self.assertFalse((root / "collected-or-spent").exists())
        # Each real consumer retains Actions' implicit success() gating.
        for name in ("Run pipeline", "Fetch permitted shared Daily machine outputs",
                     "Admit Vietnam Daily handoff", "Collect Vietnam Government Office bibliographic records",
                     "Admit authorized Japan MOD news official links"):
            self.assertNotIn("always()", self.named[name]["if"])
            self.assertNotIn("failure()", self.named[name]["if"])

    def test_failure_recovery_is_still_gated_on_actual_collection(self):
        recovery = self.named["Persist scraped articles (if pipeline failed)"]
        self.assertIn("failure()", recovery["if"])
        self.assertIn("steps.pipeline.outcome == 'success'", recovery["if"])
        self.assertIn("steps.pipeline.outcome == 'failure'", recovery["if"])
        self.assertIn("git add pla_watch.db\n", recovery["run"])
        self.assertNotIn("git add pla_watch.db output/", recovery["run"])


if __name__ == "__main__":
    unittest.main()
