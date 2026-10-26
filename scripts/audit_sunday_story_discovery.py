"""Inspect the exact Sunday discovery path without a model, SMTP or DB writes.

Only metadata/hashes leave this audit. It neither selects a story nor attests
source rights or complete government coverage. Run as a module.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

from config import DB_PATH
from core.brief_story_discovery import receipt
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.sunday_briefs_auto_writer import (
    choose_evidence, live_editorial_desks, prepare_discovery,
)
from storage.db import get_articles_for_desks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    end = date.fromisoformat(args.week_ending)
    if end.weekday() != 5:
        parser.error("week-ending must be Saturday")
    start = (end - timedelta(days=6)).isoformat()
    desks = live_editorial_desks()
    with read_only(args.db) as conn:
        rows = get_articles_for_desks(start, args.week_ending, desks, conn=conn)
    sidecar = build_draft(rows, desks=desks, week_start=start, week_ending=args.week_ending)
    inventory = []
    chosen = choose_evidence(sidecar, as_of=args.week_ending, db=args.db,
                             discovery_inventory=inventory)
    # No source-specific private roster is reconstructed by a public audit.
    # The runtime adds only its separately governed, exact-week research packet.
    packet = prepare_discovery(sidecar, chosen, [], inventory)
    report = {**receipt(packet), "week_start": start, "week_ending": args.week_ending,
              "research_scope": "production-only audit; no private packet supplied",
              "model_calls": 0, "email_sent": False}
    with os.fdopen(os.open(str(args.out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                   "w", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Weekly discovery audited: {} eligible records, {} suggested clusters; no model or email.".format(
        len(chosen), len(packet["clusters"])))


if __name__ == "__main__":
    main()
