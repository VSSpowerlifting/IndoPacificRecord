#!/usr/bin/env python3
"""Read-only Japan MOD PDF original replay; emits safe hashes/status only.

Supply a privately held *exact* PDF and an authenticated shadow-state commit.
This tool does not fetch ministry pages, write originals, invoke a model,
create a Record, or change the production database / public site.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.japan_mod_original_replay import (  # noqa: E402
    JapanOriginalHold, replay_private_pdf, safe_cli_receipt)


def official_run(run_id):
    """Fetch trusted Actions run metadata; fail closed when gh is unavailable."""
    raw = subprocess.check_output(
        ["gh", "api", "repos/VSSpowerlifting/IndoPacificRecord/actions/runs/" +
         str(run_id)], stderr=subprocess.DEVNULL)
    return json.loads(raw)


def run(argv=None, *, fetch_run=official_run):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--source-repo", type=Path, default=ROOT)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--source-identity", required=True)
    p.add_argument("--local-pdf", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        receipt, _private_text = replay_private_pdf(
            args.source_repo, args.source_commit, args.source_identity,
            args.local_pdf, fetch_run=fetch_run)
    except (JapanOriginalHold, OSError, ValueError, TypeError,
            subprocess.CalledProcessError):
        print(json.dumps({"status": "HOLD",
                          "reason": "japan_original_fidelity_not_authenticated",
                          "model_input_authorized": False,
                          "publication_authorized": False}))
        return 2
    print(safe_cli_receipt(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
