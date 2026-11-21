"""Independent, read-only IPR regional SQLite → HTML → Pages parity gate.

The gate never collects official sites, writes source DB/output, or makes any
publication permission decision. It proves exactly which metadata-only links
the approved regional index contains and whether the rendered page reflects
those rows, without mistaking static publisher directories or shadow records
for admitted records. A deploy job may optionally check its isolated gh-pages
checkout byte-for-byte against committed generated HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from core import official_link_index as link_index
from core.regional_official_link_render import DESK_TO_FAMILY, load_admitted_links

ROUTES = {"philippines": "philippines.html", "indonesia": "indonesia.html",
          "vietnam": "vietnam.html"}
SCHEMA = "ipr-regional-source-link-readback/1"
LIVE_ORIGIN = "https://indopacificrecord.org"


class ReadbackHold(ValueError):
    """Fixed error code; does not include publisher-controlled HTML text."""


def need(ok, reason):
    if not ok:
        raise ReadbackHold(reason)


class MetadataOnlySourceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section_depth = 0
        self.sections = 0
        self.active = None
        self.link_open = False
        self.rows = []

    @staticmethod
    def attrs(pairs):
        return dict(pairs)

    def handle_starttag(self, tag, attrs):
        a = self.attrs(attrs)
        if tag == "section" and self.section_depth == 0:
            if a.get("data-source-scope") == "official-link-only":
                need("regional-official-live-links" in a.get("class", "").split(),
                     "unexpected_official_link_section_identity")
                self.sections += 1
                need(self.sections == 1, "duplicate_regional_source_section")
                self.section_depth = 1
                return
        elif tag == "section" and self.section_depth:
            self.section_depth += 1
            return
        if tag == "li" and "data-regional-official-source-id" in a:
            need(self.section_depth > 0, "source_index_row_outside_section")
        if not self.section_depth:
            return
        if tag == "li":
            need(self.active is None, "nested_official_source_li")
            need("data-regional-official-source-id" in a,
                 "unidentified_regional_source_row")
            self.active = {"source_identity": a[
                "data-regional-official-source-id"], "url": None,
                           "day": None, "label": "", "links": 0, "times": 0,
                           "explanation": None}
        elif self.active is not None and tag == "a":
            if re.fullmatch(r"record/[1-9][0-9]*\.html", a.get("href") or ""):
                need(self.active["explanation"] is None,
                     "more_than_one_published_explanation")
                self.active["explanation"] = a["href"]
                return
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

    def handle_data(self, data):
        if self.active is not None and self.link_open:
            self.active["label"] += data

    def handle_endtag(self, tag):
        if not self.section_depth:
            return
        if tag == "a":
            self.link_open = False
        elif tag == "li":
            need(self.active is not None, "missing_official_source_identity")
            need(self.active["links"] == 1 and self.active["times"] == 1,
                 "incomplete_official_source_row")
            self.rows.append(self.active)
            self.active = None
        elif tag == "section":
            need(self.active is None, "unclosed_official_source_row")
            self.section_depth -= 1

    def close(self):
        super().close()
        need(self.active is None and self.section_depth == 0,
             "unclosed_regional_source_html")


def validate_page(actual_html, expected, *, explanations=None, ordered=False):
    parser = MetadataOnlySourceParser()
    parser.feed(actual_html)
    parser.close()
    need((parser.sections == 1) == bool(expected),
         "regional_source_section_presence_disagrees_with_db")
    need(len(parser.rows) == len(expected),
         "rendered_official_source_count_disagrees_with_db")
    expected_by_id = {r["source_identity"]: r for r in expected}
    need(len(expected_by_id) == len(expected), "duplicate_source_id_in_db")
    need(len({r["canonical_official_url"] for r in expected}) == len(expected),
         "official_url_shared_by_source_identities")
    seen = set()
    for row in parser.rows:
        sid = row["source_identity"]
        need(sid not in seen and sid in expected_by_id,
             "html_contains_unadmitted_or_duplicate_source_id")
        seen.add(sid)
        registered = expected_by_id[sid]
        if row["explanation"] is not None:
            need(row["explanation"] == (explanations or {}).get(sid),
                 "explanation_does_not_match_admitted_source_version")
        need(row["url"] == registered["canonical_official_url"] and
             row["day"] == registered["publisher_posted_date"] and
             row["label"].strip() == registered["label"],
             "html_link_date_or_neutral_label_differs_from_db")
    need(seen == set(expected_by_id),
         "admitted_source_missing_from_site")
    if ordered:
        need([r["source_identity"] for r in parser.rows] ==
             [r["source_identity"] for r in expected],
             "rendered_official_source_order_disagrees_with_db")
    return len(seen)


class OfficialLinkHubParser(HTMLParser):
    """The month list of an official-link index hub, and nothing else."""

    def __init__(self, desk):
        super().__init__(convert_charrefs=True)
        self.desk = desk
        self.lists = 0
        self.total = None
        self.months = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        need(a.get("data-source-scope") != "official-link-only"
             and not {"data-regional-official-source-id",
                      "data-korea-auto-official-link"} & set(a),
             "official_link_index_hub_contains_source_rows")
        if "data-official-link-index" in a:
            need(tag == "ol" and a["data-official-link-index"] == self.desk,
                 "official_link_index_hub_identity_differs")
            self.lists += 1
            self.total = a.get("data-official-link-total")
        if "data-official-link-month" in a:
            need(tag == "li" and self.lists == 1 and self.active is None,
                 "official_link_index_hub_month_outside_list")
            self.active = {"month": a["data-official-link-month"],
                           "count": a.get("data-official-link-month-count"),
                           "hrefs": []}
        elif tag == "a" and self.active is not None:
            self.active["hrefs"].append(a.get("href"))

    def handle_endtag(self, tag):
        if tag == "li" and self.active is not None:
            self.months.append(self.active)
            self.active = None

    def close(self):
        super().close()
        need(self.active is None and self.lists == 1,
             "official_link_index_hub_list_missing_or_repeated")


def read_page(path, reason):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), reason)
    try:
        data = path.read_bytes()
        return data, data.decode("utf-8")
    except (OSError, UnicodeError):
        raise ReadbackHold("committed_page_unavailable_or_non_utf8") from None


def month_inventory(root, desk):
    folder = Path(root) / link_index.month_dir(desk)
    if not folder.exists() and not folder.is_symlink():
        return []
    need(folder.is_dir() and not folder.is_symlink(),
         "official_link_index_month_folder_invalid")
    return sorted(p.name for p in folder.iterdir())


def index_partition(desk, rows):
    try:
        return link_index.partition(desk, rows)
    except link_index.IndexHold:
        raise ReadbackHold("admitted_rows_not_indexable_by_official_date") from None


def latest_rows(desk, rows):
    try:
        return link_index.latest(desk, rows)
    except link_index.IndexHold:
        raise ReadbackHold("admitted_rows_not_indexable_by_official_date") from None


def verify_index(site_dir, desk, rows, check_rows, *, pages_dir=None):
    """Hub + month pages carry every admitted row once, in DB order.

    `check_rows(html, month_rows)` validates one month page's rows exactly
    and in order. With `pages_dir`, every index route and the month folder
    inventory must be byte-identical in the deployed checkout.
    """
    months = index_partition(desk, rows)
    hub_route = link_index.hub_route(desk)
    roots = [Path(site_dir)] + ([Path(pages_dir)] if pages_dir is not None else [])
    if not months:
        for root in roots:
            need(not (root / hub_route).exists() and not month_inventory(root, desk),
                 "official_link_index_present_without_admitted_rows")
        return {"hub": None, "months": {}, "admitted_official_link_count": 0}
    expected_names = sorted(month + ".html" for month, _ in months)
    for root in roots:
        need(month_inventory(root, desk) == expected_names,
             "official_link_index_month_pages_disagree_with_db")
    hub_data, hub_html = read_page(Path(site_dir) / hub_route,
                                   "official_link_index_hub_missing")
    hub = OfficialLinkHubParser(desk)
    hub.feed(hub_html)
    hub.close()
    need(hub.total == str(len(rows)),
         "official_link_index_hub_total_disagrees_with_db")
    need([(m["month"], m["count"], m["hrefs"]) for m in hub.months] ==
         [(month, str(len(items)), [link_index.month_route(desk, month)])
          for month, items in months],
         "official_link_index_hub_months_disagree_with_db")
    hashes = {hub_route: hashlib.sha256(hub_data).hexdigest()}
    pages = {hub_route: hub_data}
    for month, items in months:
        route = link_index.month_route(desk, month)
        data, html = read_page(Path(site_dir) / route,
                               "official_link_index_month_page_missing")
        check_rows(html, items)
        pages[route] = data
        hashes[route] = hashlib.sha256(data).hexdigest()
    if pages_dir is not None:
        for route, data in pages.items():
            deployed = Path(pages_dir) / route
            need(deployed.is_file() and not deployed.is_symlink()
                 and deployed.read_bytes() == data,
                 "deployed_pages_route_differs_from_committed_site")
    return {"hub": hub_route,
            "months": {month: len(items) for month, items in months},
            "admitted_official_link_count": len(rows),
            "page_sha256": hashes}


def https_fetcher(label, limit=500000):
    """Fixed-origin GET without redirects, bounded size, exact status."""
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": "IPR-Publication-Readback/1"})
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            need(response.status == 200 and response.geturl() == url,
                 label + "_https_status_or_origin_differs")
            data = response.read(limit + 1)
            need(len(data) <= limit, label + "_https_page_oversized")
            return data
    return fetch


def https_exact(site_dir, routes, label, fetch=None):
    """Every route's live bytes equal the committed bytes; returns hashes."""
    fetch = fetch or https_fetcher(label)
    hashes = {}
    for route in routes:
        expected, _ = read_page(Path(site_dir) / route,
                                "committed_regional_desk_page_missing")
        actual = fetch(LIVE_ORIGIN + "/" + route)
        need(isinstance(actual, bytes) and len(actual) <= 500000,
             label + "_https_page_oversized")
        need(actual == expected, label + "_https_bytes_differ_from_committed_output")
        hashes[route] = hashlib.sha256(actual).hexdigest()
    return hashes


def vietnam_explanations(db_path, expected):
    """Read existing admission bindings; never infer identity from prose.

    This is readback of the committed corpus, not a new rights decision or a
    public-record count. VPCP's bibliography must still pin the metadata version
    reviewed with the explanation, as at the transactional admission boundary.
    """
    from scripts.reconcile_db import read_only
    from core.collection.vietnam_government_documents import digest
    from core.vietnam_official_link_admission import exact_url
    with read_only(str(db_path)) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                            "AND name='vietnam_article_provenance'").fetchone():
            return {}
        rows = conn.execute(
            "SELECT p.article_id,p.source_family,p.source_identity,"
            "p.canonical_official_url,p.content_sha256,p.qa_json,"
            "a.url,a.content_hash,a.passed_relevance,a.summary_english,s.slug "
            "FROM vietnam_article_provenance p JOIN articles a ON a.id=p.article_id "
            "JOIN sources s ON s.id=a.source_id").fetchall()
    by_id = {r["source_identity"]: r for r in expected}
    result = {}
    for aid, family, sid, url, content, raw_qa, article_url, article_hash, relevant, summary, slug in rows:
        if sid not in by_id:
            continue
        row = by_id[sid]
        proof = json.loads(raw_qa)
        need(sid not in result and family == slug and family in (
                "vn_mps_foreign_affairs_vi", "vn_vpcp_official_documents_vi")
             and url == article_url == row["canonical_official_url"]
             and content == article_hash and relevant == 1 and bool(summary)
             and isinstance(proof, dict) and proof.get("outcome") == "published",
             "explanation_does_not_match_admitted_source_version")
        exact_url(family, sid, url)
        if family == "vn_vpcp_official_documents_vi":
            document = proof.get("details", {}).get("VPCP_DOCUMENT", {})
            need("document" in row and document.get("metadata_sha256") == digest(row["document"])
                 and proof.get("second_pass", {}).get("ok") is True,
                 "explanation_does_not_match_admitted_source_version")
        result[sid] = "record/%s.html" % aid
    return result


def verify(db_path, site_dir, *, pages_dir=None, require_records=False,
           required_desks=()):
    site_dir = Path(site_dir)
    need(site_dir.is_dir() and not site_dir.is_symlink(),
         "committed_site_directory_missing")
    pages_dir = Path(pages_dir) if pages_dir is not None else None
    if pages_dir is not None:
        need(pages_dir.is_dir() and not pages_dir.is_symlink(),
             "deployed_pages_checkout_missing")
    # Preserve existing AFP/Kemhan callers; Vietnam is checked explicitly via
    # --require-desk vietnam once that independently governed release is made.
    defaults = ("philippines", "indonesia")
    required = set(defaults) if require_records else set()
    need(all(desk in ROUTES for desk in required_desks),
         "unknown_required_regional_source_desk")
    required.update(required_desks)
    result = {
        "schema": SCHEMA,
        "metadata_only": True,
        "source_database_changed": False,
        "rendered_html_changed": False,
        "actual_pages_deployed_by_this_check": False,
        "site_bytes_match_deployed_checkout": pages_dir is not None,
        "source_families": {},
    }
    for desk in dict.fromkeys(defaults + tuple(required_desks)):
        route = ROUTES[desk]
        path = site_dir / route
        need(path.is_file() and not path.is_symlink(),
             "committed_regional_desk_page_missing")
        expected = load_admitted_links(db_path, desk)
        try:
            data = path.read_bytes()
            html = data.decode("utf-8")
        except (OSError, UnicodeError):
            raise ReadbackHold("committed_page_unavailable_or_non_utf8") from None
        explanations = vietnam_explanations(db_path, expected) if desk == "vietnam" else {}
        index = None
        if desk in link_index.INDEX_DESKS:
            # The desk page lists exactly the newest DESK_LINK_LIMIT rows in
            # DB order; the hub and month pages carry every admitted row.
            shown = latest_rows(desk, expected)
            validate_page(html, shown, explanations=explanations, ordered=True)
            if expected:
                need(html.count('href="%s"' % link_index.hub_route(desk)) == 1,
                     "desk_page_full_index_link_missing_or_repeated")
            index = verify_index(
                site_dir, desk, expected,
                lambda page, items: validate_page(page, items, ordered=True),
                pages_dir=pages_dir)
            count = index["admitted_official_link_count"]
        else:
            count = validate_page(html, expected, explanations=explanations)
        if desk in required:
            need(count > 0, "claimed_live_desk_has_no_admitted_source_links")
        if pages_dir is not None:
            deployed = pages_dir / route
            need(deployed.is_file() and not deployed.is_symlink()
                 and deployed.read_bytes() == data,
                 "deployed_pages_route_differs_from_committed_site")
        result["source_families"][DESK_TO_FAMILY[desk]] = {
            "desk": desk,
            "page": route,
            "admitted_official_link_count": count,
            "page_sha256": hashlib.sha256(data).hexdigest(),
            "released_source_original_text": False,
        }
        if index is not None:
            result["source_families"][DESK_TO_FAMILY[desk]].update(
                desk_official_link_count=len(shown), full_index=index)
    return result


def index_routes(db_path, desk):
    """Site-relative desk + index routes this DB requires, for writer gates."""
    need(desk in link_index.INDEX_DESKS and desk in ROUTES,
         "unknown_required_regional_source_desk")
    rows = load_admitted_links(db_path, desk)
    try:
        return [ROUTES[desk]] + link_index.index_routes(desk, rows)
    except link_index.IndexHold:
        raise ReadbackHold("admitted_rows_not_indexable_by_official_date") from None


def verify_https(db_path, site_dir, desk, *, fetch=None):
    """Live desk + full-index bytes equal committed bytes and the DB rows."""
    routes = index_routes(db_path, desk)
    hashes = https_exact(site_dir, routes, desk, fetch=fetch)
    receipt = verify(db_path, site_dir, required_desks=(desk,))
    family = receipt["source_families"][DESK_TO_FAMILY[desk]]
    return {"https_origin": LIVE_ORIGIN, "routes": routes, "page_sha256": hashes,
            "admitted_official_link_count": family["admitted_official_link_count"]}


def verify_philippines_original_routes(db_path, pages_dir):
    """Page-only writers may link an original only after shared site delivery."""
    from bs4 import BeautifulSoup
    from core.daily_machine_records import load

    records = [r for r in load(db_path) if r["desk_id"] == "philippines" and r["original_text"]]
    if not records:
        return
    pages_dir = Path(pages_dir)
    archive_path = pages_dir / "archive-research-index.json"
    need(archive_path.is_file(), "philippines_original_archive_missing_on_pages")
    rows = {r["id"]: r for r in json.loads(archive_path.read_bytes())["records"]}
    for record in records:
        path = pages_dir / record["record_path"]
        need(path.is_file(), "philippines_original_record_missing_on_pages")
        page = BeautifulSoup(path.read_bytes(), "html.parser")
        title = page.select_one("h1")
        paragraphs = page.select('section[aria-labelledby="record-text"] div.original p')
        row = rows.get("machine:" + record["source_identity"])
        need(title and title.get_text() == record["original_title"]
             and [p.get_text() for p in paragraphs] == record["original_text"].split("\n\n")
             and row and row["title"] == record["original_title"]
             and row["ipr_url"] == "https://indopacificrecord.org/" + record["record_path"],
             "philippines_original_version_differs_on_pages")


def verify_vietnam_https(db_path, site_dir, *, fetch=None):
    """Independent fixed-origin HTTP readback, requiring exact committed bytes."""
    if fetch is None:
        import urllib.request
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        def fetch(url):
            req = urllib.request.Request(url, headers={"User-Agent": "IPR-Publication-Readback/1"})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
                need(response.status == 200 and response.geturl() == url,
                     "vietnam_https_status_or_origin_differs")
                data = response.read(500001)
                need(len(data) <= 500000, "vietnam_https_page_oversized")
                return data
    expected = (Path(site_dir) / "vietnam.html").read_bytes()
    actual = fetch("https://indopacificrecord.org/vietnam.html")
    need(actual == expected, "vietnam_https_bytes_differ_from_committed_output")
    rows = load_admitted_links(db_path, "vietnam")
    need(bool(rows), "vietnam_https_has_no_admitted_records")
    validate_page(actual.decode("utf-8"), rows,
                  explanations=vietnam_explanations(db_path, rows))
    return {"https_url": "https://indopacificrecord.org/vietnam.html",
            "page_sha256": hashlib.sha256(actual).hexdigest(),
            "admitted_official_link_count": len(rows)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--site-dir", required=True, type=Path)
    p.add_argument("--deployed-dir", type=Path)
    p.add_argument("--require-records", action="store_true",
                   help="Require nonempty verified links in BOTH regional desks")
    p.add_argument("--require-desk", choices=sorted(ROUTES), action="append",
                   default=[],
                   help="Require admitted links for this desk; may be repeated")
    p.add_argument("--vietnam-https", action="store_true")
    indexed = sorted(set(link_index.INDEX_DESKS) & set(ROUTES))
    p.add_argument("--https-desk", choices=indexed, action="append", default=[],
                   help="Read back this desk page and its full index over HTTPS")
    p.add_argument("--print-routes", choices=indexed,
                   help="Print the desk and index routes the DB requires, one per line")
    args = p.parse_args(argv)
    try:
        if args.print_routes:
            print("\n".join(index_routes(args.db, args.print_routes)))
            return 0
        receipt = verify(args.db, args.site_dir, pages_dir=args.deployed_dir,
                         require_records=args.require_records,
                         required_desks=args.require_desk)
        if args.vietnam_https:
            receipt["vietnam_https"] = verify_vietnam_https(args.db, args.site_dir)
        for desk in args.https_desk:
            receipt[desk + "_https"] = verify_https(args.db, args.site_dir, desk)
    except (ReadbackHold, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, ReadbackHold)
                  else "regional_source_index_readback_failed")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "site_deployed": False}), flush=True)
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
