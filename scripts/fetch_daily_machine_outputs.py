"""Fetch only public-safe signed outputs from private custody; no originals.

Activation is a separate owner act. Missing/failed families do not stop other
Daily desks. A snapshot is replayable; admission verifies its family MAC and
the current source-specific public policy, not the downloader's assertions.
"""
import json
import os
from pathlib import Path
import subprocess

from processing.daily_intake import REFS, load_policy


def main():
    if os.environ.get("IPR_PRIVATE_DAILY_ENABLED") != "true":
        return
    policy = load_policy()
    target = Path(os.environ["IPR_DAILY_INTAKE_DIR"])
    target.mkdir(parents=True, exist_ok=True)
    for family in REFS:
        p = policy["sources"][family]
        if not all(p[k] for k in ("private_model_processing", "public_machine_explanation", "unattended_release")):
            continue
        try:
            proc = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw+json",
                "repos/VSSpowerlifting/ipr-source-evidence-private/contents/envelopes/" + family +
                ".json?ref=state/shared-daily"], capture_output=True, timeout=45)
        except (OSError, subprocess.TimeoutExpired):
            print("Daily private output unavailable:", family)
            continue
        if proc.returncode or len(proc.stdout) > 512000:
            print("Daily private output unavailable:", family)
            continue
        try:
            json.loads(proc.stdout)
        except ValueError:
            print("Daily private output malformed:", family)
            continue
        (target / (family + ".json")).write_bytes(proc.stdout)


if __name__ == "__main__":
    main()
