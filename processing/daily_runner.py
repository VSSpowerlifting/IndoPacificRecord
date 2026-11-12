"""Private execution and public intake entry points for pipeline.py.

No collector, SDK or renderer is defined here. The private ledger contains
only version hashes, processing states and permitted machine outputs.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from core.daily_sources import SOURCES, source_for
from processing.daily_intake import (
    admit, bind_admitted_metadata, load_policy, need, process,
    sign_outputs, verified_source,
)


def private_run(spec, *, public_db, state_path, out_dir, no_analysis=False,
                source_identity=None, no_release=False):
    """spec is FAMILY,PRIVATE_GIT_CHECKOUT,IMMUTABLE_COMMIT."""
    from scripts.reconcile_db import read_only
    from processing.daily_intake import ROOT, digest, git, policy_binding
    family, repo, commit = spec.split(",", 2)
    need(source_for(family) is not None, "daily_source_family_invalid")
    if family == "sg_mindef_releases":
        # This execution path is dispatch-only. Refuse an unselected family run
        # BEFORE reading custody, updating state or invoking the model.
        from core.singapore_mindef_links import IDENTITY
        need(type(source_identity) is str and bool(IDENTITY.fullmatch(source_identity)),
             "daily_singapore_pilot_identity_required")
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
    preservation_holds = []
    processor_commit = git(ROOT, "rev-parse", "HEAD").decode().strip()

    def observe(identity, reading):
        # Persist before QA, including rejected/partial results. Routine runs
        # upload this existing private handoff directory on failure too. Never
        # put these readings in the queue or the signed public-safe envelope.
        record = next(r for r in eligible if r["source_identity"] == identity)
        prior = state.get(family + ":" + identity, {})
        version = digest({k: record[k] for k in (
            "metadata_version_sha256", "content_sha256", "capture_sha256")})
        target_dir = path.parent / "readings" / family
        snapshot = {
            "source_family": family, "source_identity": identity,
            "version": version, "source_git_commit": commit,
            **{k: record[k] for k in (
                "metadata_version_sha256", "content_sha256", "capture_sha256")},
            "processor_commit": processor_commit,
            "policy_sha256": policy_binding(policy["sources"][family]),
            "attempts_before": prior.get("attempts", 0),
            "prior_disposition": prior, "reading": reading,
        }
        # Unique private files preserve earlier attempts on repeated local
        # invocations. A retention failure must not erase the paid attempt:
        # persist accounting and hold this version before signing below.
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                    dir=target_dir, prefix=version + "-", suffix=".json",
                    delete=False) as retained:
                json.dump(snapshot, retained, ensure_ascii=False)
        except OSError:
            preservation_holds.append(identity)
        if no_release:
            readings[identity] = reading

    if family == "sg_mindef_releases":
        # A selected one-item pilot must not turn other historical ledger rows
        # into source_missing_or_metadata_changed holds. Process a temporary
        # per-identity view, then fold only the chosen entry back into custody.
        selected_key = family + ":" + source_identity
        selected_state = {selected_key: state[selected_key]} if selected_key in state else {}
        selected_state, usage = process(eligible, selected_state, family=family,
                                        policy=policy, reading_observer=observe)
        state.update(selected_state)
    else:
        state, usage = process(eligible, state, family=family, policy=policy,
                               reading_observer=observe)
    for identity in preservation_holds:
        state[family + ":" + identity].update(
            status="held", reason="private_reading_preservation_failed")
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
    if preservation_holds:
        result["holds"] = {identity: "private_reading_preservation_failed"
                           for identity in preservation_holds}
    if not no_release and policy["sources"][family]["public_machine_explanation"]:
        envelope = sign_outputs(state, family=family, policy=policy,
                                 key=os.environ.get("DAILY_OUTPUT_KEY", ""),
                                 selected_record=eligible[0] if family == "sg_mindef_releases" else None)
        target = Path(out_dir) / (family + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(envelope, sort_keys=True))
    return result


def intake_family(db_path, input_dir, family, *, policy=None):
    """Admit one family's independently signed envelope; None when none was delivered.

    Called by pipeline.run_governed_manual_sources, which turns the receipt
    (or the raised hold) into that source's run-result row. Nothing here
    isolates failures by swallowing them: a bad envelope raises, the caller
    records the fixed hold code, and the other families are dispatched on
    their own. Daily's existing main/Pages concurrency, migrations, commit and
    deploy gates own the resulting SQLite/site changes.
    """
    import sqlite3
    source = source_for(family)
    need(source is not None, "daily_source_family_invalid")
    from core.daily_sources import attended_pilot_gate
    gated, pilot = attended_pilot_gate(family)
    need(not gated or pilot is not None, "daily_attended_pilot_gate_closed")
    path = Path(input_dir) / (family + ".json")
    if not path.exists():
        return None
    need(path.stat().st_size <= 512000, "daily_envelope_too_large")
    envelope = json.loads(path.read_text())
    if gated:
        # Attended pilot: only the one named identity, in records or holds.
        packet = envelope.get("packet") if isinstance(envelope, dict) else None
        need(isinstance(packet, dict) and isinstance(packet.get("records"), list)
             and isinstance(packet.get("held"), list)
             and all(isinstance(r, dict) and r.get("source_identity") == pilot
                     for r in packet["records"])
             and all(h == pilot for h in packet["held"]),
             "daily_attended_pilot_identity_mismatch")
    policy = policy or load_policy()
    with sqlite3.connect(str(db_path), timeout=30) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        receipt = admit(conn, envelope, family=family, policy=policy,
                        key=os.environ.get(source.key_env, ""))
    # `admit` validated the packet shape before touching the database, so the
    # record list is well-formed here. Replayed records are neither admitted
    # nor held; the caller reports them as duplicates.
    return {"records": len(envelope["packet"]["records"]),
            "admitted": receipt["admitted"], "holds": list(receipt["holds"])}
