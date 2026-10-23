"""Government Office bibliographic records, never PDF or model input.

The portal's published first page is a bounded discovery window. Re-read all
VPCP entries in that window, including backdated and previously seen entries.
No hidden pagination endpoint, document body, cookie or attachment is fetched.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import (CandidateReference, CaptureResult,
    DiscoveryResult, ExtractedDocument, ExtractionResult)
from scraper.sources.vn_shadow_http import CHALLENGE_RE, Refusal, ShadowHttpAdapter, squash

FAMILY = "vn_vpcp_official_documents_vi"
INDEX = "https://vanban.chinhphu.vn/"
ISSUER = "Văn phòng Chính phủ"
PUBLISHER = "Cục Thông tin và Truyền thông Chính phủ"
MAX_DOCUMENTS = 15
METADATA_FIELDS = {"document_id", "document_number", "official_url", "issuer",
    "publisher", "signatory", "document_type", "issue_date", "issue_date_original",
    "effective_date", "subject", "attachments"}
TYPES = {"Công văn": "Official communication", "Thông báo": "Notice",
         "Quyết định": "Decision"}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def canonical_url(url):
    p = urlsplit(url)
    q = parse_qs(p.query, strict_parsing=True)
    need(p.scheme == "https" and p.netloc == "vanban.chinhphu.vn" and p.path == "/"
         and not p.fragment and set(q) == {"pageid", "docid"}
         and q["pageid"] == ["27160"] and len(q["docid"]) == 1
         and re.fullmatch(r"[1-9][0-9]{0,8}", q["docid"][0]), "document_url_invalid")
    return INDEX + "?pageid=27160&docid=" + q["docid"][0]


def identity(metadata):
    # Portal docid, not number/title, is the year-independent publisher key.
    return "vpcp-vi:" + metadata["document_id"]


def framed(html):
    need(not CHALLENGE_RE.search(html) and not re.search(
        r"document\.cookie\s*=.*location\.reload", html, re.I | re.S), "access_challenged")
    need(re.search(r"</html>\s*$", html, re.I), "incomplete_html")
    soup = BeautifulSoup(html, "html.parser")
    need(PUBLISHER in soup.get_text(" ", strip=True), "publisher_frame_changed")
    return soup


def listing(html):
    soup = framed(html)
    tables = soup.select("table.search-result")
    need(len(tables) == 1, "listing_table_missing")
    items = []
    for row in tables[0].select("tr"):
        code = row.select_one(".code")
        if code is None:
            continue
        stamps = row.select(".issued-date")
        need(stamps, "listing_date_missing")
        day = datetime.strptime(stamps[0].get_text(strip=True), "%d/%m/%Y").date().isoformat()
        url = canonical_url(urljoin(INDEX, code.find_parent("a")["href"]))
        items.append({"url": url, "date": day, "number": squash(code.get_text())})
    need(1 <= len(items) <= 50 and len({i["url"] for i in items}) == len(items),
         "listing_empty_duplicate_or_oversized")
    # Order is not an invariant: a backdated entry must never hold discovery.
    # Empty/truncated HTML must never turn into a quiet publishing day.
    need(len(items) == 50 or not soup.find("a", href=re.compile(r"Page\$2")),
         "listing_truncated")
    return items


def parse_document(html, url):
    url = canonical_url(url)
    soup = framed(html)
    nodes = soup.select(".Detail .Content > table")
    need(len(nodes) == 1, "document_metadata_missing")
    fields = {}
    for row in nodes[0].select("tr"):
        cells = row.find_all("td", recursive=False)
        need(len(cells) == 2, "metadata_row_changed")
        name = squash(cells[0].get_text(" ", strip=True))
        need(name not in fields, "metadata_field_duplicate")
        fields[name] = squash(cells[1].get_text(" ", strip=True))
    for name in ("Số ký hiệu", "Ngày ban hành", "Loại văn bản", "Cơ quan ban hành", "Người ký", "Trích yếu"):
        need(fields.get(name), "metadata_field_missing")
    # A foreign issuer is an exclusion, never inferred from a VPCP-looking URL/number.
    if fields["Cơ quan ban hành"] != ISSUER:
        return None
    need(fields["Loại văn bản"] in TYPES and "VPCP" in fields["Số ký hiệu"],
         "unsupported_document_type_or_number")
    day = datetime.strptime(fields["Ngày ban hành"], "%d-%m-%Y").date().isoformat()
    attachments = []
    for a in nodes[0].select("a.view-file[href]"):
        link = a["href"]
        p = urlsplit(link)
        need(p.scheme == "https" and p.netloc == "datafiles.chinhphu.vn"
             and re.fullmatch(r"/cpp/files/vbpq/[0-9]{4}/[0-9]{1,2}/[A-Za-z0-9_.-]+\.pdf", p.path)
             and not p.query and not p.fragment, "unsupported_attachment_reference")
        attachments.append(link)
    need(1 <= len(attachments) <= 5 and len(set(attachments)) == len(attachments),
         "attachment_references_missing_or_duplicate")
    result = {"document_id": parse_qs(urlsplit(url).query)["docid"][0],
        "document_number": fields["Số ký hiệu"], "official_url": url,
        "issuer": ISSUER, "publisher": PUBLISHER, "signatory": fields["Người ký"],
        "document_type": fields["Loại văn bản"], "issue_date": day,
        "issue_date_original": fields["Ngày ban hành"],
        "effective_date": fields.get("Ngày có hiệu lực"),
        "subject": fields["Trích yếu"], "attachments": attachments}
    need(all(len(v) <= 2000 for v in result.values() if isinstance(v, str)), "metadata_too_long")
    return result


class GovernmentOfficeAdapter(ShadowHttpAdapter):
    """Reuse the screened Vietnam transport, robots, spacing and request budget."""
    robots_url = INDEX + "robots.txt"

    def __init__(self, **kwargs):
        super().__init__(SimpleNamespace(slug=FAMILY), max_requests=17, **kwargs)
        self.listed = []
        self.listing_sha256 = None
        self.candidates_skipped = 0

    def _challenged(self, headers, text):
        return bool(CHALLENGE_RE.search(text) or re.search(
            r"document\.cookie\s*=.*location\.reload", text, re.I | re.S))

    def discover(self, window):
        try:
            self._load_robots(st.LISTING_FAILURE)
            need(self._permits(INDEX), "robots_disallows_listing")
            raw = self._get(INDEX, 1_000_000, st.LISTING_FAILURE)
            self.listed = listing(self._screen(raw, st.LISTING_FAILURE))
            self.listing_sha256 = hashlib.sha256(raw.body).hexdigest()
            # All visible VPCP entries are rechecked, even outside the date window.
            candidates = [i for i in self.listed if "VPCP" in i["number"]]
            # A heavy week caps the per-run budget instead of holding the source;
            # the newest entries come first and the cap is reported.
            candidates.sort(key=lambda i: i["date"], reverse=True)
            self.candidates_skipped = max(0, len(candidates) - MAX_DOCUMENTS)
            candidates = candidates[:MAX_DOCUMENTS]
            refs = [CandidateReference(i["url"], FAMILY, INDEX, i["date"]) for i in candidates]
            return DiscoveryResult(FAMILY, st.OK if refs else st.OK_NO_PUBLICATIONS, refs)
        except (Refusal, ValueError, KeyError, TypeError):
            return DiscoveryResult(FAMILY, st.LISTING_FAILURE, error_detail="vpcp_listing_held")

    def fetch(self, reference):
        try:
            need(reference.source_slug == FAMILY and canonical_url(reference.url) == reference.url
                 and reference.url in {i["url"] for i in self.listed}, "unlisted_document")
            need(self._permits(reference.url), "robots_disallows_document")
            raw = self._get(reference.url, 500_000, st.FETCH_FAILURE)
            html = self._screen(raw, st.FETCH_FAILURE)
            return CaptureResult(reference, st.OK, raw.url, final_url=raw.url,
                http_status=raw.status, content_type=raw.headers.get("content-type"),
                payload_bytes=len(raw.body), payload_sha256=hashlib.sha256(raw.body).hexdigest(),
                retrieved_at=raw.retrieved_at, body=html)
        except (Refusal, ValueError):
            return CaptureResult(reference, st.FETCH_FAILURE, reference.url, error_detail="vpcp_fetch_held")

    def extract(self, capture):
        try:
            need(capture.ok, "capture_failed")
            metadata = parse_document(capture.body, capture.requested_url)
            if metadata is None:
                return ExtractionResult(FAMILY, st.OK, [])
            need(metadata["issue_date"] == capture.reference.hint_published_date,
                 "listing_detail_date_mismatch")
            document = ExtractedDocument(capture.requested_url, FAMILY,
                metadata["subject"], "", metadata["issue_date"], "vi", metadata)
            return ExtractionResult(FAMILY, st.OK, [document])
        except (ValueError, KeyError, TypeError):
            return ExtractionResult(FAMILY, st.EXTRACTION_FAILURE, error_detail="vpcp_metadata_held")
