"""
A test-only desk that is held out of the daily model queue.

Singapore was the audits' example of a held desk until it gained its own
analysis path (processing/screening.py). The held lanes still exist for any
desk added without one, so the audit contracts keep exercising them against
this fixture desk, registered only for the duration of a test.
"""

from dataclasses import replace
from unittest.mock import patch

from processing import screening

HELD_DESK = "held_fixture"
HELD_SOURCE = "held_fixture_src"

HELD_PROFILE = replace(
    screening.SINGAPORE_PROFILE, desk_id=HELD_DESK, daily_queue=False,
    build_analysis_messages=None, build_analysis_system_prompt=None,
    analysis_prompt_version=None)


def register_held_desk(case):
    """Register the held fixture desk for one TestCase."""
    patcher = patch.dict(screening._PROFILES, {HELD_DESK: HELD_PROFILE})
    patcher.start()
    case.addCleanup(patcher.stop)
