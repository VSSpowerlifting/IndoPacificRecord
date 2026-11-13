"""Fetch only public-safe signed outputs from private custody; no originals.

Activation is a separate owner act. Missing/failed families do not stop other
Daily desks. A snapshot is replayable; admission verifies its family MAC and
the current source-specific public policy, not the downloader's assertions.
"""
import json
import os
from pathlib import Path
import subprocess

from core.daily_sources import SOURCES, attended_pilot_gate
from processing.daily_intake import load_policy


_QUIET = ("fetched", "policy_disabled", "pilot_gate_closed")


LINKS_NAME = "sg_mindef_releases.links.json"


LINKS_REF = "state/singapore-mindef-links"


def _fetch(remote_path, path, ref="state/shared-daily"):
    """One signed envelope from a private state branch to ``path``; a status."""
    try:
        proc = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
            "repos/VSSpowerlifting/ipr-source-evidence-private/contents/" + remote_path +
            "?ref=" + ref], capture_output=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return "fetch_unavailable"
    if proc.returncode or len(proc.stdout) > 512000:
        return "fetch_failed" if proc.returncode else "envelope_too_large"
    try:
        envelope = json.loads(proc.stdout)
        if not isinstance(envelope, dict):
            raise ValueError("not an envelope object")
    except (ValueError, UnicodeError, RecursionError):
        return "envelope_malformed"
    # Authentication and public-field validation remain in the admitting code.
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_bytes(proc.stdout)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return "fetched"


def _report(results):
    """Expose failed delivery without blocking unrelated source admission."""
    failed = sum(status not in _QUIET for status in results.values())
    for family, status in results.items():
        if status not in _QUIET:
            # Never print API stderr or response bodies: they may be private.
            print("::warning title=Shared Daily handoff unavailable::%s: %s" % (family, status))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write("failed_families=%d\n" % failed)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("### Shared Daily output fetch\n\n")
            for family, status in results.items():
                fh.write("- `%s`: %s\n" % (family, status))
    return results


def main():
    if os.environ.get("IPR_PRIVATE_DAILY_ENABLED") != "true":
        return
    policy = load_policy()
    target = Path(os.environ["IPR_DAILY_INTAKE_DIR"])
    target.mkdir(parents=True, exist_ok=True)
    results = {}
    for family in SOURCES:
        path = target / (family + ".json")
        # A failed/disabled refresh must never leave a prior invocation's
        # envelope available for this run's public intake. Accepted DB rows
        # remain untouched; absence is not a signed withdrawal.
        path.unlink(missing_ok=True)
        gated, _identity = attended_pilot_gate(family)
        if gated and _identity is None:
            # Scheduled/ordinary runs skip an attended-only family cleanly.
            results[family] = "pilot_gate_closed"
            continue
        p = policy["sources"][family]
        if not all(p[k] for k in ("private_model_processing", "public_machine_explanation", "unattended_release")):
            results[family] = "policy_disabled"
            continue
        results[family] = _fetch("envelopes/" + family + ".json", path)
    # Singapore official-link parents (identity, URL, date and hashes only) are
    # a separate owner switch from machine output: a parent row is what a later
    # explanation binds to, and shows nothing to readers by itself.
    links = target / LINKS_NAME
    links.unlink(missing_ok=True)
    if os.environ.get("SG_MINDEF_LINKS_ENABLED") == "true":
        # Its own branch: the collector that signs links never contends with
        # the shared-processing writer of state/shared-daily.
        results[LINKS_NAME] = _fetch(LINKS_NAME, links, LINKS_REF)
    # Japan Coast Guard official-link parents: the same link-scope contract,
    # with its own owner switch and private state branch.
    from core import japan_jcg_links
    jcg = target / japan_jcg_links.LINKS_NAME
    jcg.unlink(missing_ok=True)
    if os.environ.get("JP_JCG_LINKS_ENABLED") == "true":
        results[japan_jcg_links.LINKS_NAME] = _fetch(
            japan_jcg_links.LINKS_NAME, jcg, japan_jcg_links.LINKS_REF)
    return _report(results)


if __name__ == "__main__":
    main()
