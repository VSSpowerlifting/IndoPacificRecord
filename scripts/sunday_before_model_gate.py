"""Fail-closed Sunday production-corpus preflight before LLM and SMTP.

The full independent audit already exists in sunday_corpus_readiness. This
small adapter makes its result an ACTUAL gate in the Sunday editorial workflow,
rather than a separately visible informational report.

For current-week Sunday, require the complete Saturday window, exact Sunday
successful daily marker, and usable full text from at least two real production
desks. A historical replay can assess the archive snapshot, but CANNOT attest
that the old Sunday collection completed: keep that distinction explicit.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DB_PATH
from scripts.sunday_corpus_readiness import ReadinessError, inspect, iso_day

NY = ZoneInfo("America/New_York")
MARKER = Path(".github/state/last_daily_run_date.txt")
CURRENT_READY = "candidate_for_no_send_model_preview_not_approved"
IGNORABLE_HISTORICAL_ISSUE = "same_sunday_success_marker_missing_or_stale"


class BeforeModelRefused(ValueError):
    """An archive-only audit cannot safely support this drafting attempt."""


def gate(*, week_ending, as_of, review_local_day, database=DB_PATH,
         marker_path=MARKER, research_packet=None):
    saturday = iso_day(week_ending)
    observed = iso_day(review_local_day)
    if saturday.weekday() != 5:
        raise BeforeModelRefused("reporting end must be Saturday")
    sunday = saturday + timedelta(days=1)
    if observed < sunday:
        raise BeforeModelRefused(
            "reporting Saturday has not ended and Sunday's update has not completed"
        )

    report = inspect(
        week_ending=week_ending, as_of=as_of, review_day=review_local_day,
        database=database, marker_path=marker_path,
    )
    unmet = list(report["unmet_gates"])
    research_support = False
    offered_research_count = 0
    if research_packet is not None:
        # Use only the existing exact-week publisher-family-validated private
        # notes. Typed research may support a DRAFT, never production admission.
        from core.brief_editorial_evidence import load_editorial_evidence
        packet = Path(research_packet)
        if (packet.name != week_ending + ".json" or not packet.is_file()
                or packet.is_symlink() or packet.parent.is_symlink()):
            raise BeforeModelRefused("invalid exact-week private research packet")
        notes = load_editorial_evidence(week_ending, as_of, directory=packet.parent)
        offered_research_count = len(notes)
        production = set(report["desks_with_usable_text"])
        research_support = (len(production) == 1 and any(
            note["desk"] not in production for note in notes))
        if research_support:
            unmet = [issue for issue in unmet if
                     issue != "fewer_than_two_desks_with_usable_source_text"]
    if observed == sunday:
        # Sunday must have an actual same-Sunday successful collection marker.
        # Two stored desk names do not suffice without full text from BOTH.
        if unmet or (report["machine_preflight_verdict"] != CURRENT_READY
                     and not research_support):
            raise BeforeModelRefused(
                "current Sunday corpus is not model-ready: " +
                ", ".join(unmet or ["audit_not_ready"])
            )
        scope = "current_sunday_collection_marker_and_corpus_checked"
    else:
        # A later workflow_dispatch may preview a historical week. The
        # repository's current success marker does not reconstruct the old
        # day's collection receipt, and must never be presented as proof.
        # Still reject missing/ineligible full-text sources from that week.
        blockers = [x for x in unmet if x != IGNORABLE_HISTORICAL_ISSUE]
        if blockers:
            raise BeforeModelRefused(
                "historical archive lacks usable model inputs: " +
                ", ".join(blockers)
            )
        scope = "historical_snapshot_only_sunday_collection_unattested"

    # Do not print article texts, titles, URLs or complete source rosters.
    return {
        "reporting_saturday": week_ending,
        "pre_model_scope": scope,
        "production_desks_with_usable_text": report["desks_with_usable_text"],
        "usable_text_records": report["usable_text_records"],
        "sunday_collection_verified_for_this_execution": observed == sunday,
        "research_supported_editorial_draft_only": research_support,
        "typed_research_candidates": offered_research_count,
        "model_output_reviewed": False,
        "external_research_reviewed": False,
        "editor_delivery_authorized": False,
        "publication_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", default=None,
                        help="NY-local review date; omitted on production runner")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--marker", type=Path, default=MARKER)
    parser.add_argument("--research-packet", type=Path,
                        help="validated exact-week private editor-safe research notes")
    args = parser.parse_args(argv)
    today = (args.review_local_day or
             datetime.now(NY).date().isoformat())
    try:
        result = gate(week_ending=args.week_ending, as_of=args.as_of,
                      review_local_day=today, database=args.db,
                      marker_path=args.marker, research_packet=args.research_packet)
    except (BeforeModelRefused, ReadinessError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
