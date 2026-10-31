"""Exact admitted Japan metadata -> rendered desk -> optional Pages readback.

Existing curated historical references are outside the admitted feed section.
This verifies public fields and full page bytes, never publisher PDF contents.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path
from urllib.request import urlopen

from bs4 import BeautifulSoup
from core.regional_official_link_render import load_admitted_links
from core.regional_official_link_release import need


def verify(db, page, *, pages_repo=None, live=False):
    raw = Path(page).read_bytes()
    rows = load_admitted_links(db, "japan")
    soup = BeautifulSoup(raw, "html.parser")
    sections = soup.select("section.regional-official-live-links")
    need(len(sections) == (1 if rows else 0), "japan_feed_section_mismatch")
    items = sections[0].select("li[data-regional-official-source-id]") if rows else []
    need(len(items) == len(rows), "japan_html_count_mismatch")
    for item, row in zip(items, rows):
        anchors, dates = item.select("a"), item.select("time")
        need(item["data-regional-official-source-id"] == row["source_identity"]
             and len(anchors) == len(dates) == 1
             and anchors[0].get("href") == row["canonical_official_url"]
             and anchors[0].get_text(strip=True) == row["label"]
             and {"noopener", "noreferrer"} <= set(anchors[0].get("rel", []))
             and dates[0].get("datetime") == row["publisher_posted_date"]
             and dates[0].get_text(strip=True) == row["publisher_posted_date"],
             "japan_html_identity_or_date_mismatch")
        expected = (row["label"] + " Publisher: " + row["publisher_label"] + " · "
            + row["date_kind"] + " " + row["publisher_posted_date"] + " · Official-link metadata only")
        need(" ".join(item.get_text(" ", strip=True).split()) == expected,
             "japan_html_unapproved_content")
    if pages_repo is not None:
        published = subprocess.check_output(["git", "-C", str(pages_repo), "show", "origin/gh-pages:japan.html"])
        need(published == raw, "japan_pages_bytes_disagree")
    if live:
        with urlopen("https://indopacificrecord.org/japan.html", timeout=30) as response:
            need(response.status == 200 and response.read() == raw, "japan_https_bytes_disagree")
    return {"admitted_links": len(rows), "html_sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default="pla_watch.db")
    p.add_argument("--page", default="output/japan.html")
    p.add_argument("--pages-repo")
    p.add_argument("--live", action="store_true")
    args = p.parse_args(argv)
    print(verify(args.db, args.page, pages_repo=args.pages_repo, live=args.live))


if __name__ == "__main__":
    main()
