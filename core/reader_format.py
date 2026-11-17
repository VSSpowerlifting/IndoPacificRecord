"""Reader-facing number and date formats shared by the renderer and its tests.

Standard library only, so a contract test that renders a slice of a preview
template in a bare Jinja environment (some CI jobs install nothing but Jinja)
uses exactly the production filters.
"""
from __future__ import annotations

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def reader_date(iso: str) -> str:
    """`2026-08-08` -> `8 August 2026`.

    Day–month–year, per the standing reader-facing date convention
    (`DECISION_LOG.md` 2026-07-09): week-ending labels read "4 July 2026", and
    ISO `YYYY-MM-DD` is kept for tabular and metadata contexts. The convention
    governs date FORM; the American-English ruling of 2026-08-16 governs
    spelling, and does not reach it.

    An explicit month table rather than `strftime`, so the rendered string is
    identical on every machine regardless of locale — determinism is a tested
    property of this build.
    """
    year, month, day = (int(part) for part in iso.split("-"))
    return "%d %s %d" % (day, MONTHS[month - 1], year)


def count(n):
    """Thousands separators for an integer; anything else unchanged."""
    return "{:,}".format(n) if isinstance(n, int) else n
