"""Government Office original-PDF lane: access basis, validation, header rules, fail-closed.

The real PDFs are not in Git. Real-document acceptance is (a) the recorded
SHA-256 of both 2026-10-22 originals, checked by the runner probe workflow and,
when `VPCP_ORIGINAL_DIR` points at them, here; and (b) synthetic PDFs built
in-test for every negative case. Synthetic faults never prove live operation.
"""
import hashlib
import io
import json
import os
import sqlite3
import unittest
from pathlib import Path

from core.collection import status as st
from core.collection.vietnam_government_documents import FAMILY, INDEX, digest, identity, parse_document
from core.collection.vietnam_vpcp_originals import (OriginalsAdapter, PDF_ROBOTS)
from processing import pdf_text
from scraper.sources.vn_shadow_http import Raw, Refusal
from tests.test_vietnam_government_documents import FIX, SHA, database, metadata

NOW = "2026-10-23T16:00:00Z"
PDF_10790 = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/10790_vpcp-cn_22102026_1-signed.signed.pdf"
PDF_545 = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/545_tb-vpcp_22102026_1-signed.signed.pdf"
REAL = {PDF_10790: ("b4ed9b383d46331baff568eaf30d191d8fae302fb9bb99f3aa9e3f675184e2df", 288630, 4),
        PDF_545: ("f37efe49b108798c500389c7ea2dad7715f38f416c68add853ed94fe41b940ea", 1009619, 5)}
STORE_403 = (b'<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied.'
             b'</Message><BucketName>robots.txt</BucketName><Resource>/robots.txt</Resource></Error>')


def make_pdf(*page_texts):
    """A minimal valid PDF; an empty string makes a page with no text layer."""
    objs, kids = [b"", b""], []
    for text in page_texts:
        stream = (b"BT /F1 12 Tf 20 100 Td (" + text.encode("ascii") + b") Tj ET") if text else b""
        page, content = len(objs) + 1, len(objs) + 2
        kids.append(b"%d 0 R" % page)
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Contents %d 0 R "
                    b"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>" % content)
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count %d >>" % len(kids)
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.7\n")
    for number, body in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, start))
    return out.getvalue()


GOOD = make_pdf("Synthetic PDF fixture text. " * 2)


class FakeTransport:
    """Offline `_get` for an adapter; `routes` maps URL to (status, headers, body)."""
    def install(self, adapter, routes):
        def _get(url, limit, generic, settle=None):
            status, headers, body = routes[url]
            raw = Raw(url, status, {k.lower(): v for k, v in headers.items()}, body, len(body) > limit, NOW)
            adapter.request_log.append({"url": url, "status": status})
            if settle:
                settle(raw)
            return raw
        adapter._get = _get
        return adapter


def pdf_response(body=GOOD, ctype="application/pdf"):
    return (200, {"content-type": ctype, "content-length": str(len(body))}, body)


def originals(routes, robots=(403, {"content-type": "application/xml"}, STORE_403)):
    adapter = FakeTransport().install(OriginalsAdapter(6), {PDF_ROBOTS: robots, **routes})
    adapter.open()
    return adapter


class AccessBasis(unittest.TestCase):
    def test_object_store_403_on_robots_is_unavailable_not_a_rule(self):
        self.assertEqual(originals({}).robots_basis, "robots_unavailable_object_store_403")

    def test_only_the_exact_object_store_signature_is_accepted(self):
        for status, headers, body in [
                (403, {"content-type": "text/html"}, b"<html>Forbidden</html>"),
                (403, {"content-type": "application/xml"}, b"<Error><Code>AccessDenied</Code></Error>"),
                (403, {"content-type": "application/xml"}, STORE_403.replace(b"robots.txt</Bucket", b"other</Bucket")),
                (401, {"content-type": "application/xml"}, STORE_403),
                (500, {"content-type": "text/plain"}, b""), (503, {"content-type": "text/plain"}, b""),
                (302, {"content-type": "text/plain", "location": "/x"}, b"")]:
            with self.subTest(status=status), self.assertRaises(Refusal):
                originals({}, robots=(status, headers, body))

    def test_a_published_rules_file_still_governs(self):
        adapter = originals({PDF_545: pdf_response()}, robots=(200, {"content-type": "text/plain"},
            b"User-agent: *\nDisallow: /cpp/files/\n"))
        self.assertEqual(adapter.robots_basis, "robots_rules_read")
        with self.assertRaises(Refusal) as ctx:
            adapter.fetch(PDF_545)
        self.assertEqual(ctx.exception.detail, "robots_disallows_object")
        self.assertEqual(originals({PDF_545: pdf_response()}, robots=(404, {}, b"")).robots_basis, "robots_absent")

    def test_html_masquerading_as_robots_is_refused(self):
        with self.assertRaises(Refusal):
            originals({}, robots=(200, {"content-type": "text/html"}, b"<html>app shell</html>"))


class ObjectValidation(unittest.TestCase):
    def test_valid_pdf_is_hashed_and_nothing_is_written(self):
        got = originals({PDF_545: pdf_response()}).fetch(PDF_545)
        self.assertEqual((got["sha256"], got["bytes"], got["content_type"]),
                         (hashlib.sha256(GOOD).hexdigest(), len(GOOD), "application/pdf"))
        source = (Path(__file__).parents[1] / "core/collection/vietnam_vpcp_originals.py").read_text()
        self.assertNotIn("open(", source.replace("def open(", "").replace(".open()", ""))
        self.assertNotIn("write_bytes", source)

    def test_refusals_stop_the_object(self):
        cases = {"forbidden": ((403, {"content-type": "application/xml"}, STORE_403), st.AUTH_FAILURE),
                 "unauthorized": ((401, {}, b""), st.AUTH_FAILURE), "missing": ((404, {}, b""), st.FETCH_FAILURE),
                 "html_200": (pdf_response(b"<html>Not found</html>", "text/html"), st.UNEXPECTED_CONTENT_TYPE),
                 "wrong_type": (pdf_response(GOOD, "application/octet-stream"), st.UNEXPECTED_CONTENT_TYPE),
                 "no_magic": (pdf_response(b"HELLO", "application/pdf"), st.UNEXPECTED_CONTENT_TYPE),
                 "oversized": (pdf_response(b"%PDF-" + b"0" * 5_000_001), st.OVERSIZED_RESPONSE),
                 "truncated": ((200, {"content-type": "application/pdf", "content-length": "99999"}, GOOD), st.FETCH_FAILURE),
                 "redirect": ((302, {"location": "https://evil.example/x.pdf"}, b""), st.DISALLOWED_REDIRECT)}
        for name, (response, status) in cases.items():
            with self.subTest(name), self.assertRaises(Refusal) as ctx:
                originals({PDF_545: response}).fetch(PDF_545)
            self.assertEqual(ctx.exception.status, status)

    def test_only_exact_government_object_urls_are_requested(self):
        adapter = originals({})
        for url in ["http://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/a.pdf", "https://evil.example/cpp/files/vbpq/2026/10/a.pdf",
                    "https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/a.pdf?x=1", "https://datafiles.chinhphu.vn/other/a.pdf",
                    "https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/a.docx"]:
            with self.subTest(url), self.assertRaises(Refusal):
                adapter.fetch(url)
        self.assertEqual(len(adapter.request_log), 1)  # robots only


