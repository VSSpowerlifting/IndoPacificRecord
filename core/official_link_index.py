"""Bounded desk lists and full month indexes for admitted official links.

Indonesia, Korea and Philippines desk pages show only the newest
DESK_LINK_LIMIT admitted official-link rows; the U.S. desk shows only the
newest GROUP_LINK_LIMITS rows of each publisher. The full admitted set moves
to a hub route listing months and one page per publisher-posted month. This
module is pure: it never reads the database, fetches publishers or changes
which rows are admitted. It only slices and partitions rows that callers
already loaded in their canonical newest-first order (merge_groups only
interleaves lists that are each already in that order), and it refuses
(IndexHold) rather than re-sorting input that is out of order, duplicated or
carries a malformed official date.
"""
from __future__ import annotations

import re
from datetime import date

DESK_LINK_LIMIT = 60
# Month pages are not split. At about 430 B per row, one month page reaches
# the 120,000 B HTML+CSS delivery cap at roughly 100-110 rows. A denser month
# (a backfill or a faster publisher pace) makes the budget gate hold the
# writer, which fails closed; it never truncates a month. Splitting months is
# a separate design change.
INDEX_DESKS = ("indonesia", "korea", "philippines", "us-indopacific")
# The official date each desk's rows are ordered and partitioned by.
DAY_KEYS = {"indonesia": "publisher_posted_date", "korea": "published_date",
            "philippines": "publisher_posted_date",
            "us-indopacific": "published_date"}
# The attribute that identifies each row in rendered markup. The U.S. desk
# keeps one attribute per publisher (USCC, Treasury, BIS, in DESK_GROUPS
# order), on its desk sections and on its month pages alike.
ROW_MARKERS = {"indonesia": "data-regional-official-source-id",
               "korea": "data-korea-auto-official-link",
               "philippines": "data-regional-official-source-id",
               "us-indopacific": ("data-uscc-official-link",
                                  "data-us-treasury-official-link",
                                  "data-us-bis-official-link")}
DESK_NAMES = {"indonesia": "Indonesia", "korea": "South Korea",
              "philippines": "Philippines",
              "us-indopacific": "US Indo-Pacific Reference Desk"}
# Desks whose bounded desk list is shown in fixed publisher groups, as
# (anchor id, publisher_label) pairs in display order; each group keeps the
# canonical newest-first order. The Philippines desk lists AFP, then NSC; its
# month pages keep one combined list. Coupling: a row whose publisher_label is
# in no group raises IndexHold, which stops the whole site render (not only
# this desk). Admitting a new Philippines publisher therefore needs a reviewed
# change that adds its group here first.
#
# The U.S. desk keeps three separate publisher sections (USCC, Treasury, BIS),
# each with its own copy and disclosures; its rows come from three loaders and
# are tagged and interleaved by merge_groups. Admitting a further U.S.
# publisher likewise needs a group here first.
DESK_GROUPS = {"philippines": (("ph-afp-links", "Armed Forces of the Philippines"),
                               ("ph-nsc-links", "National Security Council")),
               "us-indopacific": (
                   ("uscc-official-links",
                    "U.S.-China Economic and Security Review Commission"),
                   ("us-treasury-official-links", "U.S. Department of the Treasury"),
                   ("us-bis-official-links",
                    "U.S. Department of Commerce · Bureau of Industry and Security"))}
# Desks that bound each publisher group separately instead of the combined
# list: the desk lists the newest N rows of every group. The U.S. desk lists
# 10 per publisher. Measured on 26 Nov 2026 (tests/test_official_link_index.py,
# U.S. growth test): with 200 rows per publisher on slugs longer than the real
# ones, five 90-word USCC machine explanations listed and a badge on every
# listed USCC row, us-indopacific.html is 116,261 B HTML+CSS, 3,739 B under its
# 120,000 B cap (the committed page, 26 Nov, is 101,079 B). At most
# 3 x 10 rows are listed, however long the admitted lists grow. The U.S. Desk
# distribution and BIS readbacks require at least 10 USCC and 10 Treasury rows
# on the desk page, so this is the floor.
GROUP_LINK_LIMITS = {"us-indopacific": 10}
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


def group_latest(desk: str, rows) -> list:
    """One publisher's rows that a per-group desk lists: its newest N.

    `rows` are a single publisher's admitted rows in canonical newest-first
    order (as its loader returns them); readbacks of one publisher use this
    without loading the other groups.
    """
    limit = GROUP_LINK_LIMITS.get(_desk(desk))
    if limit is None:
        raise IndexHold("desk %r does not bound its publisher groups" % desk)
    return _checked(desk, rows)[:limit]


def merge_groups(desk: str, groups) -> list:
    """Tag each publisher's rows with its group label and interleave them.

    `groups` holds one row list per DESK_GROUPS entry, in that order, each
    already newest first. Rows are copied with `publisher_label` set, then
    stably ordered newest official date first, so rows of one day keep group
    order and, within a group, loader order. A list out of order, or an
    identity repeated within or across groups, is a hold.
    """
    pairs = DESK_GROUPS.get(_desk(desk))
    groups = list(groups)
    if not pairs or len(groups) != len(pairs):
        raise IndexHold("desk %r rows do not match its publisher groups" % desk)
    merged = []
    for (_anchor, label), rows in zip(pairs, groups):
        tagged = [dict(row, publisher_label=label) for row in rows]
        merged += _checked(desk, tagged)
    merged.sort(key=lambda row: day_of(desk, row), reverse=True)
    return _checked(desk, merged)


def grouped(desk: str, rows) -> list:
    """Rows in the desk page's display order: its publisher groups, if any.

    Identity for desks without groups. A row outside every declared group is
    a hold, never silently dropped or appended.
    """
    rows = _checked(desk, rows)
    groups = DESK_GROUPS.get(desk)
    if not groups:
        return rows
    ordered = [row for _anchor, label in groups for row in rows
               if row.get("publisher_label") == label]
    if len(ordered) != len(rows):
        raise IndexHold("admitted row outside the desk's publisher groups")
    return ordered


def desk_listing(desk: str, rows) -> list:
    """The latest rows the desk page lists, in the order it lists them."""
    limit = GROUP_LINK_LIMITS.get(_desk(desk))
    if limit is None:
        return grouped(desk, latest(desk, rows))
    rows = grouped(desk, rows)
    return [row for _anchor, label in DESK_GROUPS[desk]
            for row in [r for r in rows if r.get("publisher_label") == label][:limit]]


def desk_groups(desk: str, rows, shown) -> list:
    """The desk page's publisher groups of its bounded list.

    Each group carries its total admitted rows, its rows in `shown` (the
    bounded desk listing) and, when some of its rows fall outside that list,
    the month page holding the newest of them, so a group with no listed row
    still has a working path. Empty for desks without groups.
    """
    listed = {r["source_identity"] for r in shown}
    groups = []
    for anchor, label in DESK_GROUPS.get(_desk(desk), ()):
        every = [r for r in rows if r.get("publisher_label") == label]
        hidden = [r for r in every if r["source_identity"] not in listed]
        older = None
        if hidden:
            month = day_of(desk, hidden[0])[:7]
            older = {"label": month_label(month),
                     "route": month_route(desk, month)}
        groups.append({"id": anchor, "name": label, "total": len(every),
                       "rows": [r for r in shown
                                if r.get("publisher_label") == label],
                       "older": older})
    return groups


def desk_context(desk: str, rows):
    """The desk template's official_link_index: None without admitted rows.

    `shown` is the bounded desk list's length and `hub` the full index; a
    desk with publisher groups also gets `groups` of its bounded rows.
    """
    if not rows:
        return None
    shown = desk_listing(desk, rows)
    context = {"total": len(rows), "shown": len(shown), "hub": hub_route(desk)}
    if desk in DESK_GROUPS:
        context["groups"] = desk_groups(desk, rows, shown)
    return context


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
