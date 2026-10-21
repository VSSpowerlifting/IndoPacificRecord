"""Private execution and public intake entry points for pipeline.py.

No collector, SDK or renderer is defined here. The private ledger contains
only version hashes, processing states and permitted machine outputs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from processing.daily_intake import (
    REFS, IntakeHold, admit, bind_admitted_metadata, load_policy, need, process,
    sign_outputs, verified_source,
)


def private_run(spec, *, public_db, state_path, out_dir, no_analysis=False,
                source_identity=None, no_release=False):
    """spec is FAMILY,PRIVATE_GIT_CHECKOUT,IMMUTABLE_COMMIT."""
    from scripts.reconcile_db import read_only
    from processing.daily_intake import ROOT
    family, repo, commit = spec.split(",", 2)
    need(family in REFS, "daily_source_family_invalid")
    policy = load_policy()
    records = verified_source(repo, commit, family)
    with read_only(str(public_db)) as conn:
        eligible = bind_admitted_metadata(records, conn, source_repo=repo)
    if source_identity:
        eligible = [r for r in eligible if r["source_identity"] == source_identity]
        need(len(eligible) == 1, "daily_selected_identity_not_admitted")
    if no_analysis:
        return {"source_family": family, "source_commit": commit,
                "verified": len(records), "bound_public_links": len(eligible),
                "usage": [], "model_calls_enabled": False}
    path = Path(state_path)
    need(ROOT not in path.resolve().parents and ROOT not in Path(out_dir).resolve().parents,
         "private_daily_state_must_remain_outside_public_checkout")
    state = json.loads(path.read_text()) if path.exists() else {}
    readings = {}
    observer = (lambda identity, reading: readings.update({identity: reading})) if no_release else None
    state, usage = process(eligible, state, family=family, policy=policy, reading_observer=observer)
    if readings:
        # Explicit private-only verification; supporting source spans never
        # enter the queue, a public envelope, logs or the public checkout.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix(".reading.json").write_text(json.dumps(readings, ensure_ascii=False))
    # Atomic private state write: failed runs preserve the previous queue.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)
    if usage:
        from analysis.usage import write_run_record
        write_run_record(usage, str(path.with_suffix(".usage.json")))
    result = {"source_family": family, "source_commit": commit,
              "verified": len(records), "bound_public_links": len(eligible),
              "usage": usage, "model_calls_enabled": policy["sources"][family]["private_model_processing"]}
    if not no_release and policy["sources"][family]["public_machine_explanation"]:
        envelope = sign_outputs(state, family=family, policy=policy,
                                 key=os.environ.get("DAILY_OUTPUT_KEY", ""))
        target = Path(out_dir) / (family + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(envelope, sort_keys=True))
    return result


def public_intake(db_path, input_dir):
    """Consume independently signed source snapshots; isolate family failures.

    Called before shared rendering. Daily's existing main/Pages concurrency,
    migrations, commit and deploy gates own the resulting SQLite/site changes.
    """
    import sqlite3
    policy = load_policy()
    result = {}
    for family in REFS:
        path = Path(input_dir) / (family + ".json")
        if not path.exists():
            continue  # quiet/unactivated source is not an error
        try:
            need(path.stat().st_size <= 512000, "daily_envelope_too_large")
            envelope = json.loads(path.read_text())
            with sqlite3.connect(str(db_path), timeout=30) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                result[family] = admit(conn, envelope, family=family, policy=policy,
                    key=os.environ.get("DAILY_" + family.upper() + "_KEY", ""))
        except (IntakeHold, ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            result[family] = {"holds": ["daily_source_intake_failed"]}
    return result
