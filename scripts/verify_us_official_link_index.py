"""Independent, read-only U.S. SQLite -> desk + full index -> Pages readback.

The U.S. Indo-Pacific desk lists only the newest GROUP_LINK_LIMITS rows of
each admitted U.S. official-link publisher (USCC, Treasury, BIS), each in its
own section under its own row marker. The hub and month pages must carry every
admitted row of all three publishers exactly once, newest first, each under
its own publisher's marker, URL, date and neutral label. PACOM's static index
is not part of this index. Never collects, writes the DB/output, deploys or
makes a publication decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from core import official_link_index as link_index
from scripts.verify_regional_source_index_readback import (
    ReadbackHold, hub_link_count, https_exact, index_partition, need, read_page,
    verify_index,
)

DESK = "us-indopacific"
ROUTE = "us-indopacific.html"
SCHEMA = "ipr-us-official-link-index-readback/1"
# (row marker, (desk anchor id, publisher_label)) in display order.
GROUPS = tuple(zip(link_index.ROW_MARKERS[DESK], link_index.DESK_GROUPS[DESK]))
MARKERS = tuple(marker for marker, _ in GROUPS)
MARKER_OF = {label: marker for marker, (_anchor, label) in GROUPS}
# Copy or markers of other desks' indexes that must never reach U.S. routes.
FOREIGN = ("data-regional-official-source-id", "data-korea-auto-official-link",
           "Verified Korean government references", "정책브리핑",
           "Verified official-source links admitted",
           "korea-automatically-admitted-official-links",
           "regional-official-live-links")


def us_group_rows(db_path):
    """Each publisher's admitted rows, in its loader's newest-first order."""
    from core.us_bis_authenticated_metadata import load_public_links as bis
    from core.us_treasury_official_metadata import load_public_links as treasury
    from core.uscc_official_metadata import load_public_links as uscc
    return (uscc(db_path), treasury(db_path), bis(db_path))


def merged_rows(groups):
    try:
        return link_index.merge_groups(DESK, groups)
    except link_index.IndexHold:
        raise ReadbackHold("admitted_rows_not_indexable_by_official_date") from None


def group_latest(rows):
    try:
        return link_index.group_latest(DESK, rows)
    except link_index.IndexHold:
        raise ReadbackHold("admitted_rows_not_indexable_by_official_date") from None


class USRowParser(HTMLParser):
    """Every U.S. official-link row: one external link and one date each."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.active = None
        self.link_open = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        marked = [m for m in MARKERS if m in a]
        if marked:
            need(len(marked) == 1 and tag == "li" and self.active is None,
                 "us_official_row_marker_misplaced_or_nested")
            self.active = {"marker": marked[0], "source_identity": a[marked[0]],
                           "url": None, "day": None, "label": "", "links": 0,
                           "times": 0}
        elif self.active is not None and tag == "a":
            self.active["links"] += 1
            need(self.active["links"] == 1, "more_than_one_official_source_url")
            need({"noopener", "noreferrer"}.issubset(
                set((a.get("rel") or "").split())),
                "official_external_link_rel_missing")
            self.active["url"] = a.get("href")
            self.link_open = True
        elif self.active is not None and tag == "time":
            self.active["times"] += 1
            need(self.active["times"] == 1, "more_than_one_official_source_date")
            self.active["day"] = a.get("datetime")
        elif self.active is not None and tag == "li":
            raise ReadbackHold("us_official_row_marker_misplaced_or_nested")

    def handle_data(self, data):
        if self.active is not None and self.link_open:
            self.active["label"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self.link_open = False
        elif tag == "li" and self.active is not None:
            need(self.active["links"] == 1 and self.active["times"] == 1,
                 "incomplete_official_source_row")
            self.rows.append(self.active)
            self.active = None

    def close(self):
        super().close()
        need(self.active is None, "unclosed_official_source_row")


def parse_rows(html):
    parser = USRowParser()
    parser.feed(html)
    parser.close()
    need(sum(html.count(m + "=") for m in MARKERS) == len(parser.rows),
         "rendered_official_source_count_disagrees_with_db")
    return parser.rows


def check_rows(parsed, expected):
    """`parsed` rows are exactly `expected`, in order, each under its marker."""
    need(len(parsed) == len(expected),
         "rendered_official_source_count_disagrees_with_db")
    need([(r["marker"], r["source_identity"]) for r in parsed] ==
         [(MARKER_OF.get(r.get("publisher_label")), r["source_identity"])
          for r in expected],
         "rendered_official_source_identity_order_or_publisher_disagrees_with_db")
    for row, registered in zip(parsed, expected):
        need(row["url"] == registered["source_url"]
             and row["day"] == registered["published_date"]
             and " ".join(row["label"].split()) == registered["neutral_label"],
             "html_link_date_or_neutral_label_differs_from_db")
    return len(parsed)


def check_no_foreign_copy(html):
    need(not any(text in html for text in FOREIGN),
         "us_official_link_route_carries_another_desk_index_copy")
    need("title_original" not in html and "text_original" not in html,
         "us_official_link_route_carries_source_text_fields")


def validate_month_rows(html, expected):
    check_no_foreign_copy(html)
    return check_rows(parse_rows(html), expected)


def validate_desk(html, groups, rows):
    """Each publisher section lists exactly its group_latest rows.

    Also the index note of every non-empty section: shown/total, its older
    month link when rows are hidden, and one hub link per non-empty section.
    """
    parsed = parse_rows(html)
    shown = []
    expected_hub_links = 0
    for (marker, (anchor, label)), group in zip(GROUPS, groups):
        tagged = [dict(r, publisher_label=label) for r in group]
        latest = group_latest(tagged)
        check_rows([r for r in parsed if r["marker"] == marker], latest)
        shown += latest
        if not group:
            need('data-official-link-group="%s"' % anchor not in html,
                 "desk_index_note_without_admitted_rows")
            continue
        expected_hub_links += 1
        note = 'data-official-link-group="%s" data-official-link-index-note="%d/%d"' % (
            anchor, len(latest), len(group))
        need(html.count(note) == 1, "desk_index_note_disagrees_with_db")
        hidden = [r for r in tagged if r["source_identity"] not in
                  {s["source_identity"] for s in latest}]
        if hidden:
            month = link_index.day_of(DESK, hidden[0])[:7]
            need('<a href="%s">' % link_index.month_route(DESK, month) in html,
                 "desk_older_month_link_missing")
    need(len(parsed) == len(shown),
         "rendered_official_source_count_disagrees_with_db")
    hub_links = hub_link_count(html, DESK)
    need(hub_links == (expected_hub_links if rows else 0),
         "desk_page_full_index_link_missing_or_repeated")
    return len(shown)


def index_routes(db_path, rows=None):
    rows = merged_rows(us_group_rows(db_path)) if rows is None else rows
    index_partition(DESK, rows)
    return [ROUTE] + link_index.index_routes(DESK, rows)


def verify(db_path, site_dir, *, pages_dir=None, groups=None):
    site_dir = Path(site_dir)
    need(site_dir.is_dir() and not site_dir.is_symlink(),
         "committed_site_directory_missing")
    if pages_dir is not None:
        need(Path(pages_dir).is_dir() and not Path(pages_dir).is_symlink(),
             "deployed_pages_checkout_missing")
    groups = us_group_rows(db_path) if groups is None else tuple(groups)
    rows = merged_rows(groups)
    data, html = read_page(site_dir / ROUTE, "committed_us_desk_page_missing")
    shown = validate_desk(html, groups, rows)
    hub_data, hub_html = (read_page(site_dir / link_index.hub_route(DESK),
                                    "official_link_index_hub_missing")
                          if rows else (None, ""))
    check_no_foreign_copy(hub_html)
    need(not any(m + "=" in hub_html for m in MARKERS),
         "official_link_index_hub_contains_source_rows")
    index = verify_index(site_dir, DESK, rows, validate_month_rows,
                         pages_dir=pages_dir)
    if pages_dir is not None:
        deployed = Path(pages_dir) / ROUTE
        need(deployed.is_file() and not deployed.is_symlink()
             and deployed.read_bytes() == data,
             "deployed_pages_route_differs_from_committed_site")
    return {"schema": SCHEMA, "metadata_only": True,
            "source_database_changed": False, "rendered_html_changed": False,
            "actual_pages_deployed_by_this_check": False,
            "site_bytes_match_deployed_checkout": pages_dir is not None,
            "page": ROUTE, "page_sha256": hashlib.sha256(data).hexdigest(),
            "admitted_official_link_count": len(rows),
            "admitted_by_publisher": {label: len(group) for (_m, (_a, label)), group
                                      in zip(GROUPS, groups)},
            "desk_official_link_count": shown, "full_index": index}


def verify_https(db_path, site_dir, *, fetch=None):
    groups = us_group_rows(db_path)
    rows = merged_rows(groups)
    routes = index_routes(db_path, rows)
    hashes = https_exact(site_dir, routes, DESK, fetch=fetch)
    receipt = verify(db_path, site_dir, groups=groups)
    return {"https_origin": "https://indopacificrecord.org", "routes": routes,
            "page_sha256": hashes,
            "admitted_official_link_count": receipt["admitted_official_link_count"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--site-dir", type=Path)
    p.add_argument("--deployed-dir", type=Path)
    p.add_argument("--https", action="store_true")
    p.add_argument("--print-routes", action="store_true",
                   help="Print the desk and index routes the DB requires, one per line")
    args = p.parse_args(argv)
    try:
        if args.print_routes:
            print("\n".join(index_routes(args.db)))
            return 0
        need(args.site_dir is not None, "committed_site_directory_missing")
        receipt = verify(args.db, args.site_dir, pages_dir=args.deployed_dir)
        if args.https:
            receipt["https"] = verify_https(args.db, args.site_dir)
    except (ReadbackHold, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, ReadbackHold)
                  else "us_official_link_index_readback_failed")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "site_deployed": False}), flush=True)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
