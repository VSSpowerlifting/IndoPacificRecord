"""Fetch only public-safe signed outputs from private custody; no originals.

Activation is a separate owner act. Missing/failed families do not stop other
Daily desks. A snapshot is replayable; admission verifies its family MAC and
the current source-specific public policy, not the downloader's assertions.
"""
import json
import os
from pathlib import Path
import subprocess

from core.daily_sources import SOURCES
from processing.daily_intake import PRIVATE_REPO, load_policy
from processing.daily_runner import heartbeat_path, write_heartbeat


def _collector_heartbeat(ref):
    """Committer date (UTC) of the newest commit on a custody branch, else None.

    The private collector preserves one commit per run on this branch, so its
    head date says when the collector last ran, whether or not the publisher
    had anything new. Metadata only: no file content is requested and stderr
    is never surfaced. Any failure returns None (unknown, not "stalled").
    """
    try:
        proc = subprocess.run(
            ["gh", "api", "repos/%s/commits?sha=%s&per_page=1" % (PRIVATE_REPO, ref),
             "--jq", ".[0].commit.committer.date"],
            capture_output=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode:
        return None
    return proc.stdout.decode("utf-8", "replace").strip() or None


def _record_heartbeat(target, family, source):
    """Write the unsigned heartbeat sidecar; return 'ok' or 'unavailable'."""
    from processing.daily_intake import IntakeHold
    stamp = _collector_heartbeat(source.custody_ref)
    try:
        write_heartbeat(target, family, stamp)
    except (IntakeHold, OSError):
        return "unavailable"
    return "ok"


def _report(results, heartbeats=None):
    """Expose failed delivery without blocking unrelated source admission.

    A heartbeat that could not be read is a warning only: it is not a delivery
    failure and says nothing about whether the collector is running.
    """
    failed = sum(status not in ("fetched", "policy_disabled")
                 for status in results.values())
    for family, status in results.items():
        if status not in ("fetched", "policy_disabled"):
            # Never print API stderr or response bodies: they may be private.
            print("::warning title=Shared Daily handoff unavailable::%s: %s" % (family, status))
    for family, status in (heartbeats or {}).items():
        if status != "ok":
            print("::warning title=Shared Daily collector heartbeat unavailable::%s" % family)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("failed_families=%d\n" % failed)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("### Shared Daily output fetch\n\n")
            for family, status in results.items():
                fh.write("- `%s`: %s (collector heartbeat: %s)\n"
                         % (family, status, (heartbeats or {}).get(family, "not checked")))
    return results


def main():
    if os.environ.get("IPR_PRIVATE_DAILY_ENABLED") != "true":
        return
    policy = load_policy()
    target = Path(os.environ["IPR_DAILY_INTAKE_DIR"])
    target.mkdir(parents=True, exist_ok=True)
    results = {}
    heartbeats = {}
    for family, source in SOURCES.items():
        path = target / (family + ".json")
        # A failed/disabled refresh must never leave a prior invocation's
        # envelope available for this run's public intake. Accepted DB rows
        # remain untouched; absence is not a signed withdrawal. The same holds
        # for the heartbeat: a stale one would hide a stalled collector.
        path.unlink(missing_ok=True)
        heartbeat_path(target, family).unlink(missing_ok=True)
        p = policy["sources"][family]
        if not all(p[k] for k in ("private_model_processing", "public_machine_explanation", "unattended_release")):
            results[family] = "policy_disabled"
            continue
        # Independent of the envelope outcome: a missing envelope and a stopped
        # collector are different facts and must both stay observable.
        heartbeats[family] = _record_heartbeat(target, family, source)
        try:
            proc = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                "repos/VSSpowerlifting/ipr-source-evidence-private/contents/envelopes/" + family +
                ".json?ref=state/shared-daily"], capture_output=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired):
            results[family] = "fetch_unavailable"
            continue
        if proc.returncode or len(proc.stdout) > 512000:
            results[family] = "fetch_failed" if proc.returncode else "envelope_too_large"
            continue
        try:
            envelope = json.loads(proc.stdout)
            if not isinstance(envelope, dict):
                raise ValueError("not an envelope object")
        except (ValueError, UnicodeError, RecursionError):
            results[family] = "envelope_malformed"
            continue
        # Authentication and public-field validation remain in admit().
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_bytes(proc.stdout)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        results[family] = "fetched"
    return _report(results, heartbeats)


if __name__ == "__main__":
    main()
