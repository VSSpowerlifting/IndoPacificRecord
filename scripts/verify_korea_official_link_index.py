"""Independent, read-only Korea SQLite -> desk + full index -> Pages readback.

The Korea desk's automatically admitted official-link rail lists only the
newest DESK_LINK_LIMIT rows of the post-suppression set: live admitted
metadata minus the frozen five-plus-nine bibliography and minus identities
already published as records through the publication gate (exactly the set
the Korea writers check). The hub and month pages must carry every one of
those rows exactly once, in DB order. Never collects, writes the DB/output,
deploys or makes a publication decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

from core import official_link_index as link_index
from scripts.verify_regional_source_index_readback import (
    ReadbackHold, hub_link_count, https_exact, index_partition, latest_rows, need,
    read_page, verify_index,
)

DESK = "korea"
ROUTE = "korea.html"
MARKER = "data-korea-auto-official-link"
SCHEMA = "ipr-korea-official-link-index-readback/1"


def korea_index_rows(db_path):
    """The post-suppression auto rows, in loader (newest-first) order."""
    from core.korea_additional_public_links import load_additional_korea_official_links
    from core.korea_corpus_bridge import publication_gate
    from core.korea_official_live_links import load_live_korea_official_links
    from core.korea_public_bibliography import load_public_korea_links
    from scripts.reconcile_db import read_only
    frozen = {row["source_identity"] for row in
              load_public_korea_links() + load_additional_korea_official_links()}
    with read_only(str(db_path)) as db:
        records, _ = publication_gate(db)
    return load_live_korea_official_links(
        db_path, exclude=frozen | set(records.values()))


class KoreaAutoRowParser(HTMLParser):
    """Every li[data-korea-auto-official-link]: one external link, one date."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.active = None
        self.link_open = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if MARKER in a:
            need(tag == "li" and self.active is None,
                 "korea_auto_row_marker_misplaced_or_nested")
            self.active = {"source_identity": a[MARKER], "url": None, "day": None,
                           "label": "", "links": 0, "times": 0}
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
            raise ReadbackHold("korea_auto_row_marker_misplaced_or_nested")

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


def validate_rows(html, expected):
    """The page lists exactly `expected`, in order, with DB URL/date/label."""
    need(html.count(MARKER + "=") == len(expected),
         "rendered_official_source_count_disagrees_with_db")
    parser = KoreaAutoRowParser()
    parser.feed(html)
    parser.close()
    need(len(parser.rows) == len(expected),
         "rendered_official_source_count_disagrees_with_db")
    need(len({r["source_identity"] for r in expected}) == len(expected),
         "duplicate_source_id_in_db")
    need([r["source_identity"] for r in parser.rows] ==
         [r["source_identity"] for r in expected],
         "rendered_official_source_identity_or_order_disagrees_with_db")
    for row, registered in zip(parser.rows, expected):
        need(row["url"] == registered["source_url"]
             and row["day"] == registered["published_date"]
             and " ".join(row["label"].split()) == registered["neutral_label"],
             "html_link_date_or_neutral_label_differs_from_db")
    return len(parser.rows)


def index_routes(db_path, rows=None):
    rows = korea_index_rows(db_path) if rows is None else rows
    index_partition(DESK, rows)
    return [ROUTE] + link_index.index_routes(DESK, rows)


def verify(db_path, site_dir, *, pages_dir=None, rows=None):
    site_dir = Path(site_dir)
    need(site_dir.is_dir() and not site_dir.is_symlink(),
         "committed_site_directory_missing")
    if pages_dir is not None:
        need(Path(pages_dir).is_dir() and not Path(pages_dir).is_symlink(),
             "deployed_pages_checkout_missing")
    rows = korea_index_rows(db_path) if rows is None else list(rows)
    data, html = read_page(site_dir / ROUTE, "committed_korea_desk_page_missing")
    shown = latest_rows(DESK, rows)
    validate_rows(html, shown)
    hub_links = hub_link_count(html, DESK)
    need(hub_links == (1 if rows else 0),
         "desk_page_full_index_link_missing_or_repeated")
    index = verify_index(site_dir, DESK, rows, validate_rows, pages_dir=pages_dir)
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
            "desk_official_link_count": len(shown), "full_index": index}


def verify_https(db_path, site_dir, *, fetch=None):
    rows = korea_index_rows(db_path)
    routes = index_routes(db_path, rows)
    hashes = https_exact(site_dir, routes, DESK, fetch=fetch)
    receipt = verify(db_path, site_dir, rows=rows)
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
                  else "korea_official_link_index_readback_failed")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "site_deployed": False}), flush=True)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
