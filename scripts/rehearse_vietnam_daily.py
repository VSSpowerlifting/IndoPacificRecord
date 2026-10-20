#!/usr/bin/env python3
"""SIMULATED rehearsal of the Vietnam Desk daily pipeline, stage by stage.

Every stage replays fixture captures from disposable Git repositories through
core.vietnam_corpus_bridge into a scratch database (a schema clone, or a copy
of the tracked pla_watch.db for the render stage). Authentication is a fixture
check, the model is a scripted fake whose English is labelled synthetic, and
every sealed source-use decision is a test fixture signed with a fictional key.
It is not a live, scheduled or unattended run, writes nothing to pla_watch.db
or output/, and calls no paid model.

The stages are the assertions in tests/test_vietnam_daily_pipeline.py, run in
pipeline order; this script only orders them and writes a labelled receipt.

    .venv/bin/python scripts/rehearse_vietnam_daily.py --receipt /tmp/vn-rehearsal.json
"""
import argparse
import hashlib
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LABEL = "SIMULATED fixture rehearsal; not a live, scheduled or unattended run"
MODULE = "tests.test_vietnam_daily_pipeline"
STAGES = (
    ("rights_denied_standing_policy", "BridgeRuns.test_standing_policy_makes_no_model_call_and_no_write"),
    ("unpromoted_desk_refuses_grant", "BridgeRuns.test_grant_refused_while_registry_keeps_desk_shadow"),
    ("backfill_publish_and_zero_duplicate_rerun", "BridgeRuns.test_grant_publishes_with_provenance_and_rerun_adds_nothing"),
    ("rights_projection_withholds_original", "BridgeRuns.test_withheld_original_and_translation_never_reach_the_row"),
    ("source_mismatch_missing_body_wrong_date", "BridgeRuns.test_source_mismatch_missing_body_and_wrong_date"),
    ("model_failure_retry_escalation", "BridgeRuns.test_model_failure_retries_then_escalates_then_settles"),
    ("transient_failure_retry_publishes", "BridgeRuns.test_retry_after_transient_failure_publishes"),
    ("incomplete_translation_held", "BridgeRuns.test_incomplete_translation_is_held_retryable"),
    ("material_change_not_overwritten", "BridgeRuns.test_material_change_is_held_not_overwritten"),
    ("concurrent_commit_duplicate", "BridgeRuns.test_concurrent_commit_resolves_to_duplicate"),
    ("unauthenticated_source_aborts", "BridgeRuns.test_unauthenticated_source_aborts_before_any_write"),
    ("site_render_disclosures_and_guard", "VietnamRecordRender.test_record_page_discloses_withheld_original_and_machine_translation"),
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--receipt", required=True, help="JSON receipt path outside the repository")
    args = p.parse_args(argv)
    receipt = Path(args.receipt).resolve()
    if ROOT in receipt.parents:
        p.error("the receipt is rehearsal evidence; write it outside the repository")
    db = ROOT / "pla_watch.db"
    db_before = _sha(db)
    loader = unittest.TestLoader()
    stages = []
    for n, (name, test) in enumerate(STAGES, 1):
        result = unittest.TestResult()
        loader.loadTestsFromName("%s.%s" % (MODULE, test)).run(result)
        problems = [str(t) + ": " + tb.strip().splitlines()[-1]
                    for t, tb in result.failures + result.errors]
        stages.append({"stage": n, "name": name, "test": test,
                       "passed": result.wasSuccessful() and result.testsRun == 1,
                       "problems": problems})
        print("%2d %-44s %s" % (n, name, "pass" if stages[-1]["passed"] else "FAIL"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    out = {"label": LABEL, "repository_head": head,
           "ran_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "tracked_db_sha256_unchanged": _sha(db) == db_before,
           "stages": stages, "all_passed": all(s["passed"] for s in stages)}
    receipt.write_text(json.dumps(out, indent=2) + "\n")
    print(LABEL)
    return 0 if out["all_passed"] and out["tracked_db_sha256_unchanged"] else 1


if __name__ == "__main__":
    sys.exit(main())
