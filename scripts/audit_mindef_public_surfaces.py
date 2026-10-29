#!/usr/bin/env python3
"""Read-only inventory of Singapore MINDEF publication exposure.

Reports aggregates and paths only: never prints original text, titles, summaries,
or unapproved source URLs. Neither a permission verdict nor a history purge.
Use --enforce when a rights-cleared public projection is ready for release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.mindef_permissions import APPROVED_MINDEF_LINKS, MINDEF_SOURCE_SLUG
from scripts.audit_generated_record_text import CapturedTextParser
from scripts.reconcile_db import read_only

TEXT_FIELDS = ("title_original", "title_english", "text_original", "text_english",
               "summary_english", "relevance_reasoning", "significance_reasoning")


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_mindef_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.hostname in ("www.mindef.gov.sg", "mindef.gov.sg")


class OutboundLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bad = 0
        self.approved = 0

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for key, url in attrs:
            if key == "href" and _is_mindef_url(url):
                if url in APPROVED_MINDEF_LINKS:
                    self.approved += 1
                else:
                    self.bad += 1


def audit(db_path, output_dir):
    db_path, output_dir = Path(db_path), Path(output_dir)
    if not db_path.is_file() or not output_dir.is_dir():
        raise ValueError("public database or rendered output directory missing")
    before = _sha256(db_path)
    with read_only(db_path) as con:
        con.row_factory = sqlite3.Row
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("database integrity check failed")
        cols = {r["name"] for r in con.execute("PRAGMA table_info(articles)")}
        required = {"id", "source_id", "url", *TEXT_FIELDS}
        if not required.issubset(cols):
            raise ValueError("articles schema missing required public exposure fields")
        rows = [dict(r) for r in con.execute(
            "SELECT a.id, a.url, a.title_original, a.title_english, "
            "a.text_original, a.text_english, a.summary_english, "
            "a.relevance_reasoning, a.significance_reasoning FROM articles a "
            "JOIN sources s ON a.source_id=s.id WHERE s.slug=? ORDER BY a.id",
            (MINDEF_SOURCE_SLUG,))]
    if before != _sha256(db_path):
        raise ValueError("database changed during read-only audit")

    nonempty = {name: sum(bool((r[name] or "").strip()) for r in rows)
                for name in TEXT_FIELDS}
    body_pages, pages_absent = 0, 0
    for row in rows:
        path = output_dir / "record" / (str(row["id"]) + ".html")
        if not path.is_file():
            pages_absent += 1
            continue
        parser = CapturedTextParser()
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
        body_pages += bool(parser.has_original_container
                           and " ".join(parser.fragments).strip())

    approved_links = unapproved_links = 0
    bad_routes = []
    for path in sorted(output_dir.rglob("*.html")):
        if path.is_symlink():
            raise ValueError("symlink encountered in rendered HTML")
        scanner = OutboundLinks()
        scanner.feed(path.read_text(encoding="utf-8"))
        scanner.close()
        approved_links += scanner.approved
        unapproved_links += scanner.bad
        if scanner.bad:
            bad_routes.append(path.relative_to(output_dir).as_posix())

    # Generated JSON can contain URLs later rendered as links by client-side
    # search/archive code. Count occurrences as potential exposure, not as
    # already-observed clickable HTML anchors.
    json_url_occurrences = 0
    json_routes = []
    for path in sorted(output_dir.rglob("*.json")):
        if path.is_symlink():
            raise ValueError("symlink encountered in rendered JSON")
        raw = path.read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError("invalid generated JSON: " +
                             path.relative_to(output_dir).as_posix())
        stack = [parsed]
        count = 0
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
            elif isinstance(value, str) and "mindef.gov.sg" in value:
                # A source URL embedded in a citation string is not an exact
                # authorized hyperlink. Treat it conservatively, without
                # printing the text. Exact URL fields retain the two grants.
                if value not in APPROVED_MINDEF_LINKS:
                    count += 1
        if count:
            json_url_occurrences += count
            json_routes.append(path.relative_to(output_dir).as_posix())

    public_original_fields = sum(nonempty.values())
    eligible = (public_original_fields == 0 and body_pages == 0
                and unapproved_links == 0 and json_url_occurrences == 0)
    return {
        "schema": "ipr-singapore-mindef-public-exposure/1",
        "surface": "tracked-working-tree-not-git-history-or-live-pages",
        "source_slug": MINDEF_SOURCE_SLUG,
        "db_sha256_before_after": before,
        "source_records": len(rows),
        "nonempty_db_fields": nonempty,
        "rendered_source_body_pages": body_pages,
        "missing_record_pages": pages_absent,
        "approved_outbound_link_count": approved_links,
        "unapproved_outbound_link_count": unapproved_links,
        "potential_unapproved_json_url_occurrences": json_url_occurrences,
        "json_routes_with_potential_unapproved_urls": json_routes[:25],
        "unapproved_link_routes": bad_routes[:25],
        "unapproved_route_list_truncated": len(bad_routes) > 25,
        "release_eligible_from_this_scan": eligible,
        "historical_repository_and_cdn_exposure_not_audited": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    parser.add_argument("--enforce", action="store_true",
                        help="Fail the release gate unless current files are safe")
    args = parser.parse_args(argv)
    report = audit(args.db, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.enforce and not report["release_eligible_from_this_scan"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
