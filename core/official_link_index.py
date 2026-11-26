"""Bounded desk lists and full month indexes for admitted official links.

Indonesia, Korea and Philippines desk pages show only the newest
DESK_LINK_LIMIT admitted official-link rows. The full admitted set moves to a hub route listing months
and one page per publisher-posted month. This module is pure: it never reads
the database, fetches publishers or changes which rows are admitted. It only
slices and partitions rows that callers already loaded in their canonical
newest-first order, and it refuses (IndexHold) rather than re-sorting input
that is out of order, duplicated or carries a malformed official date.
"""
from __future__ import annotations

import re
from datetime import date

DESK_LINK_LIMIT = 60
INDEX_DESKS = ("indonesia", "korea", "philippines")
# The official date each desk's rows are ordered and partitioned by.
DAY_KEYS = {"indonesia": "publisher_posted_date", "korea": "published_date",
            "philippines": "publisher_posted_date"}
# The attribute that identifies each row in rendered markup.
ROW_MARKERS = {"indonesia": "data-regional-official-source-id",
               "korea": "data-korea-auto-official-link",
               "philippines": "data-regional-official-source-id"}
DESK_NAMES = {"indonesia": "Indonesia", "korea": "South Korea",
              "philippines": "Philippines"}
# Desks whose bounded desk list is shown in fixed publisher groups (matched on
# publisher_label), each group keeping the canonical newest-first order. The
# Philippines desk lists AFP, then NSC; its month pages keep one combined list.
DESK_GROUPS = {"philippines": ("Armed Forces of the Philippines",
                               "National Security Council")}
_DAY = re.compile(r"\A(\d{4})-(\d{2})-(\d{2})\Z")
_MONTH = re.compile(r"\A\d{4}-(0[1-9]|1[0-2])\Z")


class IndexHold(ValueError):
    """The admitted rows cannot be bounded or indexed without guessing."""


def _desk(desk: str) -> str:
    if desk not in INDEX_DESKS:
        raise IndexHold("no bounded official-link index for desk %r" % desk)
    return desk


def hub_route(desk: str) -> str:
    return "%s-official-links.html" % _desk(desk)


def month_dir(desk: str) -> str:
    return "%s-official-links" % _desk(desk)


def month_route(desk: str, month: str) -> str:
    if not _MONTH.match(str(month)):
        raise IndexHold("malformed index month %r" % (month,))
    return "%s/%s.html" % (month_dir(desk), month)


def month_label(month: str) -> str:
    if not _MONTH.match(str(month)):
        raise IndexHold("malformed index month %r" % (month,))
    return date(int(month[:4]), int(month[5:]), 1).strftime("%B %Y")


def day_of(desk: str, row: dict) -> str:
    day = row.get(DAY_KEYS[_desk(desk)])
    match = _DAY.match(str(day or ""))
    if not match:
        raise IndexHold("admitted row %r has no valid official date"
                        % (row.get("source_identity"),))
    try:
        date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as exc:
        raise IndexHold("admitted row %r has an impossible official date"
                        % (row.get("source_identity"),)) from exc
    return day


def _checked(desk: str, rows) -> list:
    rows = list(rows)
    seen = set()
    previous = None
    for row in rows:
        identity = row.get("source_identity")
        if not identity or identity in seen:
            raise IndexHold("admitted rows repeat or omit source identity %r"
                            % (identity,))
        seen.add(identity)
        day = day_of(desk, row)
        if previous is not None and day > previous:
            raise IndexHold("admitted rows are not newest-first by official date")
        previous = day
    return rows


def latest(desk: str, rows) -> list:
    """The newest DESK_LINK_LIMIT rows, in the caller's canonical order."""
    return _checked(desk, rows)[:DESK_LINK_LIMIT]


def grouped(desk: str, rows) -> list:
    """Rows in the desk page's display order: its publisher groups, if any.

    Identity for desks without groups. A row outside every declared group is
    a hold, never silently dropped or appended.
    """
    rows = _checked(desk, rows)
    groups = DESK_GROUPS.get(desk)
    if not groups:
        return rows
    ordered = [row for group in groups for row in rows
               if row.get("publisher_label") == group]
    if len(ordered) != len(rows):
        raise IndexHold("admitted row outside the desk's publisher groups")
    return ordered


def desk_listing(desk: str, rows) -> list:
    """The latest rows the desk page lists, in the order it lists them."""
    return grouped(_desk(desk), latest(desk, rows))


def partition(desk: str, rows) -> list:
    """[(YYYY-MM, rows)] newest month first; every row exactly once."""
    months = []
    for row in _checked(desk, rows):
        month = day_of(desk, row)[:7]
        if not months or months[-1][0] != month:
            months.append((month, []))
        months[-1][1].append(row)
    return months


def index_routes(desk: str, rows) -> list:
    """Hub plus every month route; empty when nothing is admitted."""
    months = partition(desk, rows)
    if not months:
        return []
    return [hub_route(desk)] + [month_route(desk, m) for m, _ in months]
