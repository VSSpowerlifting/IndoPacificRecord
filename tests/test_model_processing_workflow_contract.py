"""Guard the consolidation of four historical model-validation PR workflows.

The single replacement preserves the union of the old path triggers, all test
modules, production SQLite readback and the no-write check. This is offline:
no network, secrets, tracked DB writes, model calls or site publication.
"""

import unittest
from pathlib import Path

from tests.test_pr_workflow_contract import _parse

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
NAME = "model_processing_contracts.yml"
OLD = (
    "default_relevance_value_contracts.yml",
    "relevance_tool_optin_contracts.yml",
    "model_parse_error_redaction_contracts.yml",
    "translation_tool_value_contracts.yml",
)
REQUIRED_TESTS = (
    "tests.test_relevance_json_value_validation",
    "tests.test_relevance_tool_optin",
    "tests.test_model_parse_error_redaction",
    "tests.test_llm_usage_telemetry",
    "tests.test_analysis_failure_causes",
    "tests.test_translation_tool_value_validation",
    "tests.test_model_processing_workflow_contract",
)
OLD_SOURCE_PATHS = (
    "analysis/analyzer.py",
    "config.py",
    "tests/test_relevance_json_value_validation.py",
    "tests/test_relevance_tool_optin.py",
    "tests/test_model_parse_error_redaction.py",
    "tests/test_translation_tool_value_validation.py",
    "docs/DEFAULT_RELEVANCE_VALUE_VALIDATION.md",
    "docs/RELEVANCE_TOOL_OPTIN.md",
    "docs/MODEL_PARSE_ERROR_REDACTION.md",
    "docs/TRANSLATION_TOOL_VALUE_VALIDATION.md",
)


class ModelProcessingWorkflow(unittest.TestCase):
    def setUp(self):
        self.doc = _parse((WORKFLOWS / NAME).read_text())
        self.job = self.doc["jobs"]["model-processing-offline"]
        self.steps = self.job["steps"]
        self.named = {step["name"]: step for step in self.steps}

    def test_only_read_only_pr_trigger_and_retained_union_of_paths(self):
        self.assertEqual(list(self.doc["on"]), ["pull_request"])
        trigger = self.doc["on"]["pull_request"]
        self.assertEqual(trigger["branches"], ["main"])
        paths = trigger["paths"]
        self.assertEqual(len(paths), len(set(paths)))
        for path in (*OLD_SOURCE_PATHS, "requirements.txt",
                     "scripts/audit_analysis_failure_causes.py",
                     "tests/test_llm_usage_telemetry.py",
                     "tests/test_analysis_failure_causes.py",
                     "tests/test_model_processing_workflow_contract.py",
                     *(f".github/workflows/{old}" for old in OLD),
                     ".github/workflows/" + NAME):
            self.assertIn(path, paths)
        self.assertEqual(self.doc["permissions"], {"contents": "read"})
        self.assertEqual(len(self.doc["jobs"]), 1)
        self.assertEqual(self.job["runs-on"], "ubuntu-24.04")
        self.assertLessEqual(self.job["timeout-minutes"], 20)

    def test_four_old_jobs_are_replaced_and_no_tests_were_dropped(self):
        for old in OLD:
            self.assertFalse((WORKFLOWS / old).exists(), old)
        check = self.named["Check relevance, translation, parse redaction and usage contracts"]
        command = check["run"]
        for module in REQUIRED_TESTS:
            self.assertIn("python -m unittest " + module + " -v", command)
        self.assertEqual(check["env"], {
            "ANTHROPIC_API_KEY": "",
            "RELEVANCE_TOOL_OUTPUT_ENABLED": "0",
        })

    def test_no_credentials_production_mutations_or_paid_calls(self):
        self.assertFalse(self.steps[0]["with"]["persist-credentials"])
        self.assertEqual(self.named["Set up Python 3.9"]["with"]["python-version"], "3.9")
        commands = "\n".join(str(step.get("run", "")) for step in self.steps)
        for forbidden in ("pipeline.py", "site/render.py",
                          "git push", "git commit", "actions-gh-pages",
                          "ANTHROPIC_API_KEY: ${{", "secrets.",
                          "migrations.cli", "playwright install"):
            self.assertNotIn(forbidden, commands)
        self.assertIn("pip install -r requirements.txt", commands)

    def test_audit_and_database_output_guards_remain(self):
        baseline = self.named["Pin original archive and require absent sidecars"]["run"]
        audit = self.named["Preserve translation failure-cause SQLite readback"]["run"]
        final = self.named["Verify tracked archive, sidecars and public output untouched"]["run"]
        self.assertIn("sha256sum pla_watch.db", baseline)
        self.assertIn("test ! -e pla_watch.db-wal", baseline)
        self.assertIn("test ! -e pla_watch.db-shm", baseline)
        self.assertIn("scripts/audit_analysis_failure_causes.py --db pla_watch.db", audit)
        for text in ('report["model_calls"] == 0', 'report["writes"] == 0',
                     'report["root_causes_established"] is False',
                     'report["model_spend_authorized"] is False',
                     "1856, 1857, 1944"):
            self.assertIn(text, audit)
        for text in ("sha256sum -c", "git diff --exit-code -- pla_watch.db output/",
                     "git status --porcelain", "test ! -e pla_watch.db-wal",
                     "test ! -e pla_watch.db-shm"):
            self.assertIn(text, final)
        self.assertIn("!cancelled()", self.named[
            "Verify tracked archive, sidecars and public output untouched"]["if"])


if __name__ == "__main__":
    unittest.main()
