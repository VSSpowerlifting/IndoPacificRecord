"""MND-labeled releases republished by Korea Policy Briefing; not an MND wire.

The government portal's own robots policy governs this separate host. No
request is made to mnd.go.kr. HWPX attachments are read as bounded ZIP/XML;
iframe shells and metadata summaries are never used as release bodies.
"""
import hashlib
import io
import re
import sys
import zipfile
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import ListingShadowAdapter, Page, Refused
from scraper.sources.id_kemhan import one
from scraper.sources.iso39 import date_py39

HOST = "www.korea.kr"
LISTING = "https://" + HOST + "/briefing/pressReleaseList.do"
ISSUER = "국방부"
MULTIPLE_HWPX_ATTACHMENTS = "multiple_hwpx_attachments"


class MultipleHwpxAttachments(ValueError):
    """A release page publishes more than one valid HWPX attachment.

    Which variant (for example ``_게시`` or ``_제공``) is the release body is
    an owner decision. Nothing is selected or downloaded: the release is
    reported for review with every attachment link it published.
    """

    def __init__(self, title, published, attachments):
        super().__init__("%d published HWPX attachments; no variant is selected "
                         "automatically (owner review required)" % len(attachments))
        self.title, self.published = title, published
        self.attachments = tuple(sorted(attachments))  # (url, label) pairs


def document_link(url):
    """Return the validated Policy Briefing HWPX download URL, or refuse."""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if (parts.netloc != HOST or parts.scheme != "https" or parts.path != "/common/download.do" or
            set(query) != {"fileId", "tblKey"} or query["tblKey"] != ["GMN"] or
            len(query["fileId"]) != 1 or not query["fileId"][0].isdigit()):
        raise ValueError("unexpected document link")
    return url


def article_url(url):
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    ids = query.get("newsId", [])
    if (parts.scheme != "https" or parts.netloc != HOST or parts.fragment or
            parts.path != "/briefing/pressReleaseView.do" or len(ids) != 1 or
            not re.fullmatch(r"[0-9]+", ids[0])):
        raise ValueError("not a Policy Briefing release URL")
    return "https://" + HOST + parts.path + "?newsId=" + ids[0]


def hwpx_text(payload):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 200 or len({i.filename for i in entries}) != len(entries):
                raise ValueError("oversized or duplicate-member HWPX archive")
            if sum(i.file_size for i in entries) > 10_000_000:
                raise ValueError("expanded HWPX archive exceeds limit")
            sections = sorted((i for i in entries if re.fullmatch(r"Contents/section[0-9]+\.xml", i.filename)),
                              key=lambda i: int(re.search(r"[0-9]+", i.filename)[0]))
            if not sections:
                raise ValueError("no HWPX document sections")
            paragraphs = []
            for section in sections:
                raw = archive.read(section)
                xml = raw.decode("utf-8", "strict")
                if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                    raise ValueError("XML declarations refused")
                root = ET.fromstring(xml)
                for p in root.iter():
                    if p.tag.rsplit("}", 1)[-1] == "p":
                        # Direct runs only: table-cell paragraphs are visited in
                        # their own turn, never duplicated inside their parent.
                        strings = ["".join(t.itertext()) for run in p
                                   if run.tag.rsplit("}", 1)[-1] == "run" for t in run
                                   if t.tag.rsplit("}", 1)[-1] == "t"]
                        line = "".join(strings).strip()
                        if line:
                            paragraphs.append(line)
            if not paragraphs:
                raise ValueError("HWPX carries no original text")
            return "\n".join(paragraphs)
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError, KeyError) as exc:
        raise ValueError("invalid HWPX document: " + type(exc).__name__)


class KoreaPolicyAdapter(ListingShadowAdapter):
    host, listing = HOST, LISTING
    # The Oct 12 2026 scheduled run timed out before robots completed.
    # Allow one extra, identically scoped robots GET after a transient timeout.
    # One additional transport retry TOTAL across listing/article/HWPX requests
    # per collection addresses the Oct 18 ConnectionError without replaying a
    # whole batch. Denials, TLS errors, redirects and invalid bodies never retry.
    # Parent transport still checks robots and enforces delay on every request.
    ROBOTS_TIMEOUT = 45

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.documents = {}
        self.attachment_refusals = {}
        self.attachment_ambiguities = {}
        self.robots_timeout_retries = 0
        self.transport_retries = 0

    def _request(self, url, form=None, robots=False, binary=False):
        if not robots:
            try:
                return super()._request(url, form=form, binary=binary)
            except Refused as exc:
                cause = exc.__cause__
                if (self.transport_retries >= 1 or
                        not isinstance(cause, (requests.Timeout, requests.ConnectionError)) or
                        isinstance(cause, requests.exceptions.SSLError)):
                    raise
                self.transport_retries += 1
                print("Korea MND transient transport failure; one bounded retry after crawl delay",
                      file=sys.stderr)
                return super()._request(url, form=form, binary=binary)
        try:
            return super()._request(url, form=form, robots=True, binary=False)
        except Refused as exc:
            if exc.status != st.TIMEOUT or self.robots_timeout_retries >= 1:
                raise
            self.robots_timeout_retries += 1
            # No document requests can occur without a fresh, valid robots
            # response; the parent records last_request and enforces delay.
            print("Korea robots GET timed out; one bounded retry after crawl delay",
                  file=sys.stderr)
            try:
                return super()._request(url, form=form, robots=True, binary=False)
            except Refused as last:
                if last.status == st.TIMEOUT:
                    raise Refused(st.TIMEOUT,
                                  "robots request timed out after one bounded retry") from last
                raise

    def discover(self, window):
        self.robots_timeout_retries = 0
        self.transport_retries = 0
        self.attachment_refusals = {}
        self.attachment_ambiguities = {}
        return super().discover(window)

    def first_request(self, window):
        from datetime import timedelta
        self.documents = {}
        return self.listing, {"repCode": "A00005", "pageIndex": "1",
                              "startDate": (window.target_date - timedelta(days=window.lookback_days)).isoformat(),
                              "endDate": window.target_date.isoformat()}

    def parse_listing(self, text, request, number):
        soup = BeautifulSoup(text, "html.parser")
        form = one(soup.select("form#mainForm"), "published search form")
        if form.get("action") != "/briefing/pressReleaseList.do" or form.get("method", "").lower() != "post":
            raise ValueError("search-form contract changed")
        for key, value in request[1].items():
            if one(form.select('input[name="' + key + '"]'), key).get("value") != value:
                raise ValueError("server did not retain requested search filter")
        if one(soup.select('label[for="A00005"]'), "ministry filter").get_text(strip=True) != ISSUER:
            raise ValueError("ministry code changed")
        items = []
        total_text = one(soup.select(".result strong"), "search-result count").get_text(strip=True).replace(",", "")
        if not total_text.isdigit():
            raise ValueError("unknown search-result count")
        total = int(total_text)
        for anchor in soup.select('a[href*="pressReleaseView.do"][href*="pageIndex="]'):
            source = one(anchor.select(".source"), "listing source").find_all("span", recursive=False)
            if len(source) != 2 or source[1].get_text(strip=True) != ISSUER:
                raise ValueError("ministry filter returned another issuer")
            published = date_py39(source[0].get_text(strip=True).replace(".", "-")).isoformat()
            if not request[1]["startDate"] <= published <= request[1]["endDate"]:
                raise ValueError("search returned a date outside the requested window")
            title = one(anchor.select("strong"), "release title").get_text(" ", strip=True)
            items.append({"url": article_url(urljoin(self.listing, anchor["href"])),
                          "date": published, "title": title})
        if not items:
            # A missing list alone is a failure; the site's explicit empty-state
            # marker is required (checked against the captured empty response).
            if (not soup.select(".list_type .no_data") or
                    one(soup.select(".result strong"), "result count").get_text(strip=True) != "0"):
                raise ValueError("missing release list without explicit empty marker")
            return Page([], declared_total=0)
        paging = one(soup.select(".paging"), "pagination")
        current = paging.select("a.on")
        if current and (len(current) != 1 or current[0].get_text(strip=True) != str(number)):
            raise ValueError("wrong search-page number")
        pages = [int(m[1]) for a in paging.select("a[onclick]")
                 for m in [re.fullmatch(r"pageLink\(([0-9]+)\); return false;", a["onclick"])] if m]
        if any(n > number for n in pages) and number + 1 not in pages:
            raise ValueError("search pagination omits next page")
        form_data = dict(request[1], pageIndex=str(number + 1))
        return Page(items, (self.listing, form_data) if number + 1 in pages else None, total)

    def metadata(self, text, url):
        soup = BeautifulSoup(text, "html.parser")
        canonical = one(soup.select('link[rel="canonical"]'), "canonical release link").get("href")
        if canonical != article_url(url):
            raise ValueError("canonical release identity disagrees")
        title = one(soup.select(".view_title h1"), "release title").get_text(" ", strip=True)
        info = one(soup.select(".variety .info"), "release provenance")
        published = date_py39(one(info.select("span:first-child"), "release date").get_text(strip=True).replace(".", "-")).isoformat()
        issuer = one(info.select('a.gotosite[href="/news/ministryNewsList.do?repCode=A00005"]'), "release issuer")
        if not issuer.get_text(strip=True).startswith(ISSUER):
            raise ValueError("release issuer changed")
        labels = {}
        for a in soup.select('a[href*="/common/download.do"]'):
            label = a.get_text(strip=True)
            if label.lower().endswith(".hwpx"):
                labels.setdefault(urljoin(url, a["href"]), label)
        if not labels:
            raise ValueError("exactly one published HWPX attachment required; other formats unmeasured")
        # Every published HWPX link must meet the document contract before
        # anything else is decided; one invalid link refuses the release.
        for link in labels:
            document_link(link)
        if len(labels) > 1:
            raise MultipleHwpxAttachments(title, published, labels.items())
        return title, published, next(iter(labels))

    def titles_match(self, listed, collected):
        # The portal detail heading can repeat ASCII spaces from the listing.
        # Compare only; keep original titles and every other character intact.
        return re.sub(r" {2,}", " ", listed) == re.sub(r" {2,}", " ", collected)

    def fetch(self, reference):
        self.attachment_ambiguities.pop(reference.url, None)
        capture = super().fetch(reference)
        if capture.status == st.OK:
            try:
                hint = self.references[reference.url]
                try:
                    title, published, url = self.metadata(capture.body, reference.url)
                except MultipleHwpxAttachments as ambiguous:
                    # Held for owner review only when the captured page is the
                    # listed release; a disagreeing page is an ordinary failure.
                    if (not self.titles_match(hint["title"], ambiguous.title) or
                            ambiguous.published != hint["date"]):
                        raise ValueError("release metadata disagrees with listing")
                    # No attachment is requested and no variant is chosen.
                    self.attachment_ambiguities[reference.url] = {
                        "reason": MULTIPLE_HWPX_ATTACHMENTS, "detail": str(ambiguous),
                        "attachment_urls": [link for link, _ in ambiguous.attachments],
                        "attachment_labels": [label for _, label in ambiguous.attachments]}
                    raise
                if not self.titles_match(hint["title"], title) or published != hint["date"]:
                    raise ValueError("release metadata disagrees with listing")
                try:
                    payload = self._request(url, binary=True)
                except Refused as exc:
                    # The release page is captured and agrees with the listing;
                    # only its attachment request was refused. Record which
                    # component failed. The runner alone decides what follows.
                    self.attachment_refusals[reference.url] = dict(
                        getattr(exc, "response_facts", {}), status=exc.status)
                    raise
                self.documents[reference.url] = (payload, dict(self.evidence[-1]))
            except (Refused, ValueError) as exc:
                capture.status = exc.status if isinstance(exc, Refused) else st.EXTRACTION_FAILURE
                capture.error_detail = str(exc)
        return capture

    def parse_article(self, text, url):
        title, published, document_url = self.metadata(text, url)
        if url not in self.documents:
            raise ValueError("release attachment not retrieved; iframe is not body text")
        payload, evidence = self.documents[url]
        prose = hwpx_text(payload)
        return ExtractedDocument(url, self.slug, title, prose, published, "ko", {
            "source_identity": "korea-policy:" + parse_qs(urlsplit(url).query)["newsId"][0],
            "publisher": "대한민국 정책브리핑", "issuer": ISSUER,
            "publication_kind": "syndicated_press_release", "body_scope": "published_hwpx_text",
            "attachments_collected": True, "document_url": document_url,
            "document_capture_sha256": evidence["capture_sha256"],
            "document_retrieved_at": evidence["retrieved_at"],
        })
