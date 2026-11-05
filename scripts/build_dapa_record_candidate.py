#!/usr/bin/env python3
"""Offline DAPA original-to-record candidate; prints hashes and counts only.

No source HTTP, model call, public data, editorial approval or publication.
Selected prose is written only to an explicit new 0600 private file.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.korea_dapa_record_candidate import (  # noqa: E402
    CandidateHold, build_candidate, write_private_input)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--db-sha256", required=True)
    p.add_argument("--source-identity", required=True)
    p.add_argument("--hwpx", type=Path, required=True)
    p.add_argument("--page-capture", type=Path,
                   help="preserved article page; replays the KOGL Type 0 mark")
    p.add_argument("--private-output", type=Path)
    p.add_argument("--as-of", type=datetime.fromisoformat,
                   help="timezone-aware ISO time for the embargo check")
    args = p.parse_args(argv)
    try:
        if args.as_of is not None and args.as_of.tzinfo is None:
            raise CandidateHold("as_of_requires_timezone")
        receipt, paragraphs = build_candidate(
            args.db, args.db_sha256, args.source_identity, args.hwpx, args.as_of,
            # absolute() keeps the capture's own symlink check; resolve() would not
            args.page_capture and args.page_capture.absolute())
        if args.private_output and receipt["status"] == "CANDIDATE":
            write_private_input(args.private_output, receipt, paragraphs)
    except CandidateHold as exc:
        print(json.dumps({"status": "HOLD", "reason_code": str(exc),
                          "network_requests": 0,
                          "publication_approved": False}, sort_keys=True))
        return 2
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "CANDIDATE" else 3


if __name__ == "__main__":
    sys.exit(main())
