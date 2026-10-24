"""Government Office original PDFs: retrieve, validate and hash in memory.

Transport for the text lane only. The PDF host publishes no rules file: its
`/robots.txt` is answered by the object store with a 403 `AccessDenied` for a
bucket literally named `robots.txt`. Under RFC 9309 section 2.3.1.3 a 4xx on
robots.txt means "unavailable", which does not forbid access, while 5xx or a
network failure (2.3.1.4) forbids it. The shared Vietnam transport is stricter
(any 401/403 is "no basis"), so that reading is confined here, to exactly this
object-store signature on exactly this host, and is recorded with every
retrieval. Anything else on the robots path, and any refusal (401/403/429/5xx,
redirect, challenge, wrong type) on an object, stops retrieval.

Nothing here writes a file. The caller controls permitted private custody.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from core.collection import status as st
from scraper.sources.vn_shadow_http import (CHALLENGE_RE, MAX_ROBOTS_BYTES, Refusal,
    ShadowHttpAdapter, parse_robots, robots_crawl_delay, robots_rules, rules_file_problem, squash)

FAMILY = "vn_vpcp_official_documents_vi"
PDF_HOST = "datafiles.chinhphu.vn"
PDF_ROBOTS = "https://" + PDF_HOST + "/robots.txt"
REGISTER_HOST = "vpcp.chinhphu.vn"
REGISTER_INDEX = "https://" + REGISTER_HOST + "/van-ban-ban-hanh.htm"
MAX_PDF_BYTES = 5_000_000
OBJECT_PATH = re.compile(r"/cpp/files/vbpq/[0-9]{4}/[0-9]{1,2}/[A-Za-z0-9_.-]+\.pdf")
STORE_DENIAL = re.compile(rb"<Code>AccessDenied</Code>.*<BucketName>robots\.txt</BucketName>", re.S)


class _Retrieval(ShadowHttpAdapter):
    """Transport only: discovery and extraction belong to the metadata adapter."""

    def discover(self, window):
        raise NotImplementedError("discovery is the metadata adapter's job")

    def extract(self, capture):
        raise NotImplementedError("extraction is processing.vpcp_original_checks")


class OriginalsAdapter(_Retrieval):
    """Exact-URL retrieval on the PDF host; one robots read, then objects."""
    robots_url = PDF_ROBOTS

    def __init__(self, max_objects, **kwargs):
        super().__init__(SimpleNamespace(slug=FAMILY), max_requests=max_objects + 1, **kwargs)
        self.robots_basis = None

    def _challenged(self, headers, text):
        return bool(CHALLENGE_RE.search(text[:4096])) and not text.startswith("%PDF-")

    def open(self):
        """Classify robots for this host; raises Refusal when access is not shown."""
        read = {}

        def settle(raw):
            self._gate(raw)
            if raw.status in (404, 410):
                read["basis"] = "robots_absent"
            elif raw.status == 403 and raw.headers.get("content-type", "").lower().startswith(
                    "application/xml") and STORE_DENIAL.search(raw.body):
                read["basis"] = "robots_unavailable_object_store_403"
            elif raw.status == 200:
                problem = rules_file_problem(raw.body)
                if problem:
                    raise Refusal(st.UNEXPECTED_CONTENT_TYPE, "robots.txt is not a rules file: %s" % problem,
                                  PDF_ROBOTS, raw.status)
                groups = parse_robots(raw.body.decode("utf-8"))
                read["basis"], read["groups"] = "robots_rules_read", groups
                return robots_crawl_delay(groups)
            else:
                # 5xx/network are "unreachable" (complete disallow); any other 4xx
                # is not the recognised object-store signature, so not assumed.
                raise Refusal(st.AUTH_FAILURE if raw.status in (401, 403) else st.FETCH_FAILURE,
                              "robots.txt HTTP %d is not a permitted basis" % raw.status, PDF_ROBOTS, raw.status)
            return None

        self._rules, self._interval = [], max(self._interval, 2.0)
        self._get(PDF_ROBOTS, MAX_ROBOTS_BYTES, st.FETCH_FAILURE, settle=settle)
        self.robots_basis = read["basis"]
        if "groups" in read:
            self._rules = robots_rules(read["groups"])
            self._interval = max(self._interval, robots_crawl_delay(read["groups"]) or 0.0)

    def fetch(self, url):
        """One validated PDF as {sha256, bytes, content_type, retrieved_at, body}."""
        p = urlsplit(url)
        if not (p.scheme == "https" and p.netloc == PDF_HOST and OBJECT_PATH.fullmatch(p.path)
                and not p.query and not p.fragment):
            raise Refusal(st.FETCH_FAILURE, "attachment_reference_unsupported", url)
        if not self._permits(url):
            raise Refusal(st.AUTH_FAILURE, "robots_disallows_object", url)
        raw = self._get(url, MAX_PDF_BYTES, st.FETCH_FAILURE)
        self._gate(raw)
        if raw.status != 200:
            raise Refusal(st.AUTH_FAILURE if raw.status in (401, 403) else st.FETCH_FAILURE,
                          "HTTP %d" % raw.status, url, raw.status)
        ctype = raw.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/pdf" or not raw.body.startswith(b"%PDF-"):
            raise Refusal(st.UNEXPECTED_CONTENT_TYPE, "not_a_pdf", url, raw.status)
        declared = raw.headers.get("content-length", "")
        if declared.isdigit() and int(declared) != len(raw.body):
            raise Refusal(st.FETCH_FAILURE, "length_mismatch", url, raw.status)
        return {"sha256": hashlib.sha256(raw.body).hexdigest(), "bytes": len(raw.body),
                "content_type": ctype, "retrieved_at": raw.retrieved_at, "body": raw.body}


