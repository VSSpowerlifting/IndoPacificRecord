"""Strict offline shadow source workflow binding contracts. No collector or network."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import audit_shadow_workflow_bindings as audit


class BindingContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = audit.validate()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-workflow-binding-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = json.loads((audit.ROOT / "config/shadow_source_workflow_bindings.json").read_text())
        self.config = copy.deepcopy(config)
        self.manifest_paths = sorted({x["manifest"] for x in config["sources"]})
        self.workflow_paths = sorted(
            {x["workflow"] for x in config["sources"]
             if x["workflow"] and x["workflow"].startswith(".github/")}
            | {".github/workflows/indonesia_korea_shadow.yml",
               ".github/workflows/ph_afp_shadow.yml",
               ".github/workflows/vietnam_ministry_shadow.yml"}
        )
        for path in self.manifest_paths + self.workflow_paths:
            dst = self.root / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(audit.ROOT / path, dst)
        self.write_config()

    def write_config(self):
        path = self.root / "config/shadow_source_workflow_bindings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.config), encoding="utf-8")

    def report(self):
        self.write_config()
        return audit.validate(self.root)

    def test_real_repository_has_exact_explicit_coverage(self):
        result = self.original
        self.assertEqual(12, result["manifests_checked"])
        self.assertEqual(17, result["source_families_checked"])
        self.assertFalse(result["all_runs_attested"])
        self.assertFalse(result["shadow_promotion_authorized"])
        self.assertFalse(result["editorial_publication_authorized"])
        self.assertFalse(result["production_eligible"])
        self.assertEqual(0, result["writes"])
        self.assertEqual(len(result["sources"]), 17)
        dapa = next(row for row in result["sources"]
                    if row["source_slug"] == "kr_policy_dapa_releases")
        self.assertEqual(dapa["evidence"], "private_schedule_declared_external_runs_unverified")
        self.assertEqual(dapa["trigger"], "private_scheduled")
        self.assertEqual(dapa["cron"], "17 22 * * *")
        self.assertFalse(dapa["production_eligible"])

    def test_declaration_cli_works_without_project_import_path(self):
        import os
        import subprocess
        import sys
        run_env=os.environ.copy()
        run_env.pop('PYTHONPATH',None)
        p=subprocess.run([sys.executable,str(audit.ROOT/'scripts/audit_shadow_workflow_bindings.py'),
                          '--root',str(audit.ROOT)],cwd=self.root,env=run_env,
                         text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['source_families_checked'],17)

    def test_synthetic_mirror_preserves_count_without_modifications(self):
        result = self.report()
        self.assertEqual(result["source_families_checked"], 17)
        self.assertTrue(all(not s["run_attested"] for s in result["sources"]))

    def test_private_dapa_schedule_cannot_claim_another_repo_branch_or_frequency(self):
        row = next(x for x in self.config["sources"]
                   if x["source_slug"] == "kr_policy_dapa_releases")
        for field, value in (("workflow", row["workflow"].replace("ipr-source-evidence-private", "IndoPacificRecord")),
                             ("state_branch", "shadow/korea-policy-briefing"),
                             ("cron", "17 * * * *")):
            original = row[field]
            row[field] = value
            with self.assertRaisesRegex(audit.BindingError, "private schedule limited"):
                self.report()
            row[field] = original

    def test_missing_source_binding_is_a_hard_error(self):
        self.config["sources"].pop()
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_duplicate_source_binding_is_a_hard_error(self):
        self.config["sources"].append(copy.deepcopy(self.config["sources"][0]))
        with self.assertRaisesRegex(audit.BindingError, "duplicate"):
            self.report()

    def test_new_source_in_existing_manifest_fails_closed(self):
        name = self.root / "shadow/id_kemhan/manifest.json"
        d = json.loads(name.read_text())
        second = copy.deepcopy(d["sources"][0])
        second["slug"] = "id_kemhan_new"
        d["sources"].append(second)
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_new_manifest_family_cannot_be_silently_ignored(self):
        name = self.root / "shadow/new_candidate/manifest.json"
        name.parent.mkdir(parents=True)
        d = json.loads((self.root / "shadow/id_kemhan/manifest.json").read_text())
        d["sources"][0]["slug"] = "new_candidate_source"
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "coverage drift"):
            self.report()

    def test_promoted_shadow_manifest_cannot_claim_safe_shadow_state(self):
        name = self.root / "shadow/id_kemhan/manifest.json"
        d = json.loads(name.read_text())
        d["desk"]["active"] = True
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "admission status"):
            self.report()

    def test_afp_source_is_pending_private_handoff(self):
        row = next(x for x in self.original["sources"]
                   if x["source_slug"] == "ph_afp_articles")
        self.assertEqual(row["trigger"], "private_handoff_pending")
        self.assertEqual(row["evidence"], "private_handoff_pending_external_runs_unverified")
        self.assertFalse(row["run_attested"])
        self.assertFalse(row["production_eligible"])
        self.assertNotIn("  schedule:", (self.root / ".github/workflows/ph_afp_shadow.yml").read_text())

    def test_reintroduced_afp_schedule_is_rejected(self):
        path = self.root / ".github/workflows/ph_afp_shadow.yml"
        original = path.read_text()
        path.write_text(original.replace("on:\n", "on:\n  schedule:\n    - cron: '40 6 * * *'\n", 1))
        with self.assertRaisesRegex(audit.BindingError, "private AFP handoff still"):
            self.report()

    def test_reintroduced_afp_manual_dispatch_is_rejected(self):
        path = self.root / ".github/workflows/ph_afp_shadow.yml"
        original = path.read_text()
        path.write_text(original.replace("on:\n", "on:\n  workflow_dispatch:\n", 1))
        with self.assertRaisesRegex(audit.BindingError, "private AFP handoff still"):
            self.report()

    def test_manual_only_workflow_cannot_gain_schedule_without_review(self):
        name = self.root / ".github/workflows/vietnam_shadow.yml"
        s = name.read_text()
        self.assertIn("on:\n", s)
        name.write_text(s.replace("on:\n", "on:\n  schedule:\n    - cron: '35 17 * * *'\n", 1))
        with self.assertRaisesRegex(audit.BindingError, "manual-only binding"):
            self.report()

    def test_mnd_private_schedule_cannot_claim_indonesia_branch(self):
        item = next(s for s in self.config["sources"]
                    if s["source_slug"] == "kr_policy_mnd_releases")
        self.assertEqual(item["trigger"], "private_scheduled")
        item["state_branch"] = "shadow/indonesia-kemhan"
        with self.assertRaisesRegex(audit.BindingError, "private schedule limited"):
            self.report()

    def test_indonesia_external_handoff_is_not_live_attestation(self):
        record = next(x for x in self.original["sources"]
                      if x["source_slug"] == "id_kemhan_news")
        self.assertEqual(record["trigger"], "private_handoff_pending")
        self.assertEqual(record["state_branch"], "shadow/indonesia-kemhan")
        self.assertIsNone(record["workflow"])
        self.assertIsNone(record["cron"])
        self.assertEqual(record["evidence"], "private_handoff_pending_external_runs_unverified")
        self.assertIs(record["run_attested"], False)
        self.assertIs(record["production_eligible"], False)

    def test_other_sources_cannot_claim_private_handoff(self):
        unrelated = next(x for x in self.config["sources"]
                         if x["source_slug"] == "ph_nsc_official_statements")
        unrelated.update(trigger="private_handoff_pending", workflow=None, cron=None)
        with self.assertRaisesRegex(audit.BindingError,
                                    "limited to exact Indonesia Kemhan or Philippines AFP"):
            self.report()

    def test_afp_reintroduced_writer_is_rejected(self):
        path = self.root / ".github/workflows/ph_afp_shadow.yml"
        path.write_text(path.read_text() + "\n      - run: git push origin HEAD:refs/heads/shadow/ph-afp\n")
        with self.assertRaisesRegex(audit.BindingError, "private AFP handoff still"):
            self.report()

    def test_indonesia_legacy_writer_reintroduced_fails_handoff(self):
        name = self.root / ".github/workflows/indonesia_korea_shadow.yml"
        raw = name.read_text()
        name.write_text(raw + "\nstate_branch=shadow/indonesia-kemhan\n")
        with self.assertRaisesRegex(audit.BindingError, "private Indonesia handoff still"):
            self.report()

    def test_indonesia_public_schedule_reintroduced_fails_handoff(self):
        name = self.root / ".github/workflows/indonesia_korea_shadow.yml"
        raw = name.read_text()
        name.write_text(raw.replace("on:\n",
                                    "on:\n  schedule:\n    - cron: '17 17 * * *'\n", 1))
        with self.assertRaisesRegex(audit.BindingError, "private Indonesia handoff still"):
            self.report()

    def test_vietnam_ministry_swapped_branch_fails_routing(self):
        source = next(s for s in self.config["sources"]
                      if s["source_slug"] == "vn_mps_foreign_affairs_vi")
        source["state_branch"] = "shadow/vietnam-moit-energy"
        with self.assertRaisesRegex(audit.BindingError, "private schedule limited"):
            self.report()

    def test_private_vietnam_declaration_refuses_a_revived_public_writer(self):
        path=self.root/".github/workflows/vietnam_ministry_shadow.yml"
        original=path.read_text()
        for revived in (original.replace("    if: false", "    if: true", 1),
                        original.replace("on:\n", "on:\n  schedule:\n    - cron: '17 18 * * *'\n", 1)):
            path.write_text(revived)
            with self.assertRaisesRegex(audit.BindingError,"public original writer"):
                self.report()

    def test_research_only_journal_cannot_claim_hidden_workflow(self):
        item = next(s for s in self.config["sources"]
                    if s["source_slug"] == "vn_national_defence_journal_en")
        item["workflow"] = ".github/workflows/vietnam_shadow.yml"
        with self.assertRaisesRegex(audit.BindingError, "research-only source"):
            self.report()

    def test_invalid_or_traversing_workflow_path_refused(self):
        item = self.config["sources"][0]
        item["workflow"] = ".github/workflows/../../shadow/id_kemhan/manifest.json"
        with self.assertRaises(audit.BindingError):
            self.report()

    def test_duplicate_source_slug_in_manifest_refused(self):
        name = self.root / "shadow/jp_mod/manifest.json"
        d = json.loads(name.read_text())
        d["sources"][1]["slug"] = d["sources"][0]["slug"]
        name.write_text(json.dumps(d))
        with self.assertRaisesRegex(audit.BindingError, "duplicate shadow source"):
            self.report()

    def test_schema_or_evidence_label_drift_is_refused(self):
        self.config["status"] = "live_healthy"
        with self.assertRaisesRegex(audit.BindingError, "non-live evidence label"):
            self.report()

    def test_workflow_cron_parser_ignores_non_trigger_crons(self):
        snippet = "\n".join([
            "# on:\n#   schedule:\n#     - cron: '40 6 * * *'",
            "on:", "  workflow_dispatch:",
            "jobs:", "  sample:", "    steps:",
            "      - run: 'echo schedule: cron: 40 6 * * *'"
        ])
        self.assertEqual([], audit.workflow_crons(snippet))
        self.assertEqual(["40 6 * * *"], audit.workflow_crons(
            "on:\n  schedule:\n    - cron: '40 6 * * *'\n  workflow_dispatch:\n"))


if __name__ == "__main__":
    unittest.main()
