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

from core.regional_official_link_render import DESK_TO_FAMILY, load_admitted_links

ROUTES = {"philippines": "philippines.html", "indonesia": "indonesia.html",
          "vietnam": "vietnam.html"}
SCHEMA = "ipr-regional-source-link-readback/1"


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


def validate_page(actual_html, expected, *, explanations=None):
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
    return len(seen)


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
    return result


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
    args = p.parse_args(argv)
    try:
        receipt = verify(args.db, args.site_dir, pages_dir=args.deployed_dir,
                         require_records=args.require_records,
                         required_desks=args.require_desk)
        if args.vietnam_https:
            receipt["vietnam_https"] = verify_vietnam_https(args.db, args.site_dir)
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
