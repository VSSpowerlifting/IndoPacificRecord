"""Offline tests replay exact official captures; never connect to a source."""
import hashlib
import io
import requests
import json
import socket
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import CollectionWindow, CandidateReference
from core.manifests import load_all_desks, load_manifest
from scraper.sources import desk_shadow_http as http
from scraper.sources.id_kemhan import KemhanAdapter, LISTING as ID_LISTING, article_url as id_url
from scraper.sources.kr_policy_briefing import KoreaPolicyAdapter, LISTING as KR_LISTING, article_url as kr_url, hwpx_text
from scripts import shadow_collect_desk as runner
from scripts import review_desk_shadow as reviewer

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests/fixtures/indonesia_korea"
ROWS = json.loads((FIX / "requests.json").read_text())
TARGET = date(2026, 10, 6)


def fixture(name):
    return (FIX / name).read_bytes()


class Response:
    def __init__(self, url, payload, status=200, ctype="text/html; charset=UTF-8", headers=None):
        self.url, self.payload, self.status_code = url, payload, status
        self.headers = {"Content-Type": ctype, **(headers or {})}

    def iter_content(self, chunk_size):
        for pos in range(0, len(self.payload), chunk_size):
            yield self.payload[pos:pos + chunk_size]

    def close(self):
        pass


class Session:
    def __init__(self, mutations=None):
        self.calls, self.mutations = [], mutations or {}
        self.timeouts = []

    def request(self, method, url, data, headers, **kwargs):
        assert self.trust_env is False
        assert headers["User-Agent"] == http.USER_AGENT
        assert headers["Accept-Encoding"] == "identity"
        assert kwargs["allow_redirects"] is False
        self.calls.append((method, url, data))
        self.timeouts.append((url, kwargs["timeout"]))
        if url in self.mutations:
            value = self.mutations[url]
            if isinstance(value, Exception):
                raise value
            return value
        for row in ROWS:
            original_url = row["url"]
            if "pressReleaseView.do" in original_url:
                original_url = kr_url(original_url)
            if original_url != url:
                continue
            if "pressReleaseList.do" in url and row.get("form") != data:
                continue
            if "capture" in row:
                headers = row.get("headers", {})
                ctype = next((v for k, v in headers.items() if k.lower() == "content-type"), "text/html")
                return Response(url, fixture(row["capture"]), row["status"], ctype)
        raise AssertionError("unrecorded request: " + repr((method, url, data)))


def adapter(desk, mutations=None):
    name, cls, _ = runner.DESKS[desk]
    source = load_manifest(ROOT / "shadow" / name / "manifest.json").sources[0]
    session = Session(mutations)
    return cls(source, session=session, sleeper=lambda _: None), session


class Case(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(socket.socket, "connect", side_effect=AssertionError("real network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)


class Evidence(Case):
    def test_all_capture_bytes_match_the_native_request_ledger(self):
        for row in ROWS:
            if "capture" in row:
                data = fixture(row["capture"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
                self.assertEqual(len(data), row["bytes"])

    def test_indonesia_manifest_is_absent_from_production_despite_public_directory(self):
        # Korea left this shadow pair through the owner activation
        # (scripts/korea_daily_activation.py); Indonesia remains shadow.
        self.assertNotIn("indonesia", load_all_desks())
        entries = {d["slug"]: d for d in json.loads(
            (ROOT / "desks/registry.json").read_text())["desks"]}
        for slug in ("indonesia",):
            entry = entries[slug]
            self.assertTrue(entry["public"])
            self.assertEqual(entry["status"], "shadow")
            self.assertIsNone(entry["manifest"])
            self.assertFalse(entry["has_production_records"])

    def test_korean_ministry_policy_blocks_the_publication_paths(self):
        rules, _ = http.robots_policy(fixture("mnd-robots.bin").decode())
        self.assertFalse(http.robots_allows(rules, "https://www.mnd.go.kr/mnd/167/subview.do"))
        self.assertTrue(http.robots_allows(rules, "https://www.mnd.go.kr/mnd/index.do"))

    def test_portal_and_kemhan_policies_allow_the_declared_routes(self):
        for name, url in [("kemhan-robots.bin", ID_LISTING), ("korea-policy.bin", KR_LISTING)]:
            rules, delay = http.robots_policy(fixture(name).decode())
            self.assertTrue(http.robots_allows(rules, url))
            self.assertEqual(delay, 2)

    def test_longest_rule_allow_tie_named_group_and_crawl_delay(self):
        rules, delay = http.robots_policy("User-agent: *\nDisallow: /\nUser-agent: IndoPacificRecord\nDisallow: /secret*\nAllow: /secret/public$\nCrawl-delay: 4.5\n")
        self.assertTrue(http.robots_allows(rules, "https://www.korea.kr/briefing/"))
        self.assertFalse(http.robots_allows(rules, "https://www.korea.kr/secret/file"))
        self.assertTrue(http.robots_allows(rules, "https://www.korea.kr/secret/public"))
        self.assertEqual(delay, 4.5)


class Indonesia(Case):
    def test_discovery_retains_every_current_day_news_item(self):
        a, session = adapter("indonesia")
        result = a.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 1)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(a.listing_report["pages_walked"], 1)

    def test_pagination_walks_only_the_published_next_link(self):
        a, session = adapter("indonesia")
        result = a.discover(CollectionWindow(TARGET, 6))
        self.assertEqual(result.status, st.OK)
        self.assertGreater(len(result.references), 1)
        self.assertEqual(a.listing_report["pages_walked"], 2)
        self.assertEqual(session.calls[-1][1], ID_LISTING + "/page/2")

    def test_original_body_keeps_prose_wrapped_by_malformed_image_markup(self):
        a, _ = adapter("indonesia")
        ref = a.discover(CollectionWindow(TARGET, 0)).references[0]
        result = a.extract(a.fetch(ref))
        self.assertEqual(result.status, st.OK)
        doc = result.documents[0]
        self.assertTrue(doc.text_original.startswith("Jakarta –"))
        self.assertTrue(doc.text_original.endswith("(Biro Infohan Setjen Kemhan)"))
        self.assertNotIn("Statistik Pengunjung", doc.text_original)
        self.assertEqual(doc.published_date, "2026-10-06")
        self.assertEqual(doc.extra["date_precision"], "day")
        self.assertIsNone(doc.extra["issuer"])

    def test_second_real_article_extracts_by_the_same_body_rule(self):
        a, _ = adapter("indonesia")
        url = next(r["url"] for r in ROWS if r.get("capture") == "kemhan-article-2.bin")
        doc = a.parse_article(fixture("kemhan-article-2.bin").decode(), url)
        self.assertTrue(doc.has_usable_text)
        self.assertEqual(doc.published_date, id_url(url)[1])

    def test_future_window_is_healthy_empty(self):
        a, _ = adapter("indonesia")
        self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 7), 0)).status, st.OK_NO_PUBLICATIONS)

    def test_markup_loss_is_failure_not_silence(self):
        a, _ = adapter("indonesia", {ID_LISTING: Response(ID_LISTING, b"<html></html>")})
        self.assertEqual(a.discover(CollectionWindow(TARGET)).status, st.LISTING_FAILURE)

    def test_missing_next_page_is_failure(self):
        soup = BeautifulSoup(fixture("kemhan-news.bin"), "html.parser")
        for anchor in soup.select('a[href="' + ID_LISTING + '/page/2"]'):
            anchor.decompose()
        a, _ = adapter("indonesia", {ID_LISTING: Response(ID_LISTING, str(soup).encode())})
        self.assertEqual(a.discover(CollectionWindow(TARGET, 6)).status, st.LISTING_FAILURE)

    def test_repeated_page_fails_without_partial_candidates(self):
        url = ID_LISTING + "/page/2"
        payload = fixture("kemhan-news.bin").replace(b'>1</a>', b'>2</a>')
        a, _ = adapter("indonesia", {url: Response(url, payload)})
        result = a.discover(CollectionWindow(TARGET, 6))
        self.assertFalse(result.ok)
        self.assertEqual(result.references, [])

    def test_date_mismatch_and_foreign_url_are_refused(self):
        a, _ = adapter("indonesia")
        row = next(r for r in ROWS if r.get("capture") == "kemhan-article.bin")
        with self.assertRaises(ValueError):
            a.parse_article(fixture("kemhan-article.bin").decode().replace("6 Oktober 2026", "5 Oktober 2026"), row["url"])
        with self.assertRaises(ValueError):
            id_url(row["url"].replace("www.kemhan.go.id", "tni.mil.id"))


class Korea(Case):
    def test_native_current_day_discovery_fetch_and_document_extraction(self):
        a, session = adapter("korea")
        result = a.discover(CollectionWindow(TARGET))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 1)
        capture = a.fetch(result.references[0])
        extracted = a.extract(capture)
        self.assertEqual(extracted.status, st.OK)
        self.assertEqual(extracted.documents[0].published_date, "2026-10-06")
        self.assertEqual(len(session.calls), 4)
        self.assertFalse(any("mnd.go.kr" in c[1] for c in session.calls))

    def test_filtered_listing_preserves_all_listed_mnd_identities(self):
        a, session = adapter("korea")
        page = a.parse_listing(fixture("korea-filtered.bin").decode(),
                               (KR_LISTING, {"repCode": "A00005", "pageIndex": "1",
                                             "startDate": "2026-09-01", "endDate": "2026-10-06"}), 1)
        self.assertEqual(len(page.items), 20)
        self.assertEqual(page.next_request[1]["pageIndex"], "2")
        self.assertTrue(all(urlsplit(i["url"]).netloc == "www.korea.kr" for i in page.items))
        self.assertEqual(session.calls, [])

    def test_real_hwpx_documents_extract_as_original_korean(self):
        a, _ = adapter("korea")
        for n in (1, 2):
            row = next(r for r in ROWS if r.get("capture") == "korea-article-%d.bin" % n)
            url = kr_url(row["url"])
            body = fixture("korea-document-%d.bin" % n)
            a.documents[url] = (body, {"capture_sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": row["retrieved_at"]})
            doc = a.parse_article(fixture("korea-article-%d.bin" % n).decode(), url)
            self.assertEqual(doc.text_original, hwpx_text(body))
            self.assertIn(doc.title_original, doc.text_original)
            self.assertEqual(doc.extra["issuer"], "국방부")
            self.assertEqual(doc.extra["publisher"], "대한민국 정책브리핑")
            self.assertEqual(doc.extra["body_scope"], "published_hwpx_text")
            self.assertNotIn("이 자료는 국방부의 보도자료를 전재", doc.text_original)

    def test_iframe_html_cannot_become_a_body_without_its_document(self):
        a, _ = adapter("korea")
        row = next(r for r in ROWS if r.get("capture") == "korea-article-1.bin")
        with self.assertRaisesRegex(ValueError, "not retrieved"):
            a.parse_article(fixture("korea-article-1.bin").decode(), kr_url(row["url"]))

    def test_real_empty_search_is_healthy_without_a_pagination_block(self):
        a, _ = adapter("korea")
        self.assertEqual(a.discover(CollectionWindow(date(2026, 10, 5))).status, st.OK_NO_PUBLICATIONS)

    def test_filter_loss_and_missing_empty_marker_are_failures(self):
        a, _ = adapter("korea")
        form = {"repCode": "A00005", "pageIndex": "1", "startDate": "2026-10-05", "endDate": "2026-10-05"}
        text = fixture("korea-empty.bin").decode()
        for bad in (text.replace('class="no_data"', 'class=""'), text.replace('value="A00005"', 'value=""')):
            with self.assertRaises(ValueError):
                a.parse_listing(bad, (KR_LISTING, form), 1)

    def test_malformed_or_entity_xml_is_refused(self):
        with self.assertRaises(ValueError):
            hwpx_text(b"<html>not a document</html>")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("Contents/section0.xml", '<!DOCTYPE x [<!ENTITY y "z">]><x/>')
        with self.assertRaises(ValueError):
            hwpx_text(stream.getvalue())


class Access(Case):
    def test_mnd_article_connection_failure_recovers_exact_original_once(self):
        korean, session = adapter("korea")
        ref = korean.discover(CollectionWindow(TARGET, 0)).references[0]
        original_request = session.request
        failures = [ref.url]

        def once(method, url, **kwargs):
            if failures and url == failures[0]:
                failures.pop()
                session.calls.append((method, url, kwargs["data"]))
                raise requests.ConnectionError("synthetic connection reset")
            return original_request(method, url, **kwargs)

        session.request = once
        result = korean.extract(korean.fetch(ref))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(korean.transport_retries, 1)
        self.assertEqual([url for _, url, _ in session.calls].count(ref.url), 2)
        self.assertEqual([e["requested_url"] for e in korean.evidence].count(ref.url), 1)
        # The budget is collection-wide, not multiplied by the number of sources.
        session.mutations[ref.url] = requests.ConnectionError("still unavailable")
        self.assertEqual(korean.fetch(ref).status, st.FETCH_FAILURE)
        self.assertEqual([url for _, url, _ in session.calls].count(ref.url), 3)

    def test_mnd_attachment_timeout_can_recover_without_refetching_article(self):
        korean, session = adapter("korea")
        ref = korean.discover(CollectionWindow(TARGET, 0)).references[0]
        original_request = session.request
        failed = []

        def once(method, url, **kwargs):
            if "/common/download.do" in url and not failed:
                failed.append(url)
                session.calls.append((method, url, kwargs["data"]))
                raise requests.Timeout("synthetic document timeout")
            return original_request(method, url, **kwargs)

        session.request = once
        self.assertEqual(korean.extract(korean.fetch(ref)).status, st.OK)
        self.assertEqual(korean.transport_retries, 1)
        self.assertEqual([url for _, url, _ in session.calls].count(ref.url), 1)

    def test_mnd_access_tls_and_malformed_body_failures_never_retry(self):
        for failure in (
            requests.exceptions.SSLError("synthetic invalid TLS certificate"),
            Response(KR_LISTING, b"forbidden", 403),
            Response(KR_LISTING, b"unavailable", 503),
            Response(KR_LISTING, b"", 302),
            Response(KR_LISTING, b'<html><title>Just a moment</title></html>'),
            Response(KR_LISTING, b"<html>truncated"),
        ):
            with self.subTest(failure=type(failure).__name__):
                korean, session = adapter("korea", {KR_LISTING: failure})
                self.assertFalse(korean.discover(CollectionWindow(TARGET, 0)).ok)
                self.assertEqual(korean.transport_retries, 0)
                self.assertEqual([url for _, url, _ in session.calls].count(KR_LISTING), 1)

    def test_korea_robots_timeout_is_extended_for_only_one_request(self):
        korean, korean_session = adapter("korea")
        self.assertEqual(korean.discover(CollectionWindow(TARGET, 0)).status, st.OK)
        self.assertEqual(korean_session.timeouts[0],
                         ("https://www.korea.kr/robots.txt", 45))
        self.assertTrue(all(timeout == 30 for _, timeout in korean_session.timeouts[1:]))
        indonesia, indonesia_session = adapter("indonesia")
        self.assertEqual(indonesia.discover(CollectionWindow(TARGET, 0)).status, st.OK)
        self.assertTrue(all(timeout == 30 for _, timeout in indonesia_session.timeouts))

    def test_korea_robots_first_timeout_retries_once_then_discovers(self):
        robots = "https://www.korea.kr/robots.txt"
        korean, session = adapter("korea")
        original_request = session.request
        first = [True]

        def once(method, url, data, headers, **kwargs):
            if first[0] and url == robots:
                first[0] = False
                session.calls.append((method, url, data))
                session.timeouts.append((url, kwargs["timeout"]))
                raise requests.Timeout("transient synthetic robots timeout")
            return original_request(method, url, data, headers, **kwargs)

        session.request = once
        outcome = korean.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(outcome.status, st.OK)
        self.assertEqual(korean.robots_status, "read")
        self.assertEqual(korean.robots_timeout_retries, 1)
        self.assertEqual([url for _, url, _ in session.calls].count(robots), 2)
        self.assertEqual(session.timeouts[:2], [(robots, 45), (robots, 45)])
        self.assertEqual([x["requested_url"] for x in korean.evidence].count(robots), 1)
        self.assertEqual(session.calls[-1][1], KR_LISTING)

    def test_korea_robots_timeout_twice_fails_closed_with_no_listing(self):
        robots = "https://www.korea.kr/robots.txt"
        korean, session = adapter("korea", {robots: requests.Timeout("synthetic")})
        outcome = korean.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(outcome.status, st.TIMEOUT)
        self.assertEqual(outcome.references, [])
        self.assertIsNone(korean.robots_status)
        self.assertEqual(korean.robots_timeout_retries, 1)
        self.assertIn("after one bounded retry", outcome.error_detail)
        self.assertEqual(session.calls, [("GET", robots, None)] * 2)
        self.assertEqual(session.timeouts, [(robots, 45)] * 2)
        self.assertEqual(korean.evidence, [])

    def test_korea_robots_permission_denial_is_never_retried(self):
        robots = "https://www.korea.kr/robots.txt"
        korean, session = adapter(
            "korea", {robots: Response(robots, b"forbidden", 403, "text/plain")})
        result = korean.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(korean.robots_timeout_retries, 0)
        self.assertEqual(session.calls, [("GET", robots, None)])
        self.assertEqual([e["requested_url"] for e in korean.evidence], [robots])

    def test_korea_listing_timeout_retries_once_then_fails_closed(self):
        korean, session = adapter(
            "korea", {KR_LISTING: requests.Timeout("synthetic listing timeout")})
        outcome = korean.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(outcome.status, st.TIMEOUT)
        self.assertEqual(korean.robots_timeout_retries, 0)
        self.assertEqual(korean.transport_retries, 1)
        self.assertEqual([url for _, url, _ in session.calls].count(KR_LISTING), 2)
        self.assertEqual(len(session.calls), 3)

    def test_indonesia_robots_timeout_remains_single_attempt(self):
        robots = "https://www.kemhan.go.id/robots.txt"
        ind, session = adapter("indonesia", {robots: requests.Timeout("synthetic")})
        outcome = ind.discover(CollectionWindow(TARGET, 0))
        self.assertEqual(outcome.status, st.TIMEOUT)
        self.assertEqual(session.calls, [("GET", robots, None)])
        self.assertEqual(session.timeouts, [(robots, 30)])

    def test_policy_refusal_causes_no_listing_request(self):
        url = "https://www.kemhan.go.id/robots.txt"
        a, session = adapter("indonesia", {url: Response(url, b"User-agent: *\nDisallow: /", ctype="text/plain")})
        result = a.discover(CollectionWindow(TARGET))
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(len(session.calls), 1)

    def test_unreadable_or_html_robots_is_never_permission(self):
        url = "https://www.kemhan.go.id/robots.txt"
        for response in (Response(url, b"denied", 403, "text/plain"), Response(url, b"<html></html>")):
            a, session = adapter("indonesia", {url: response})
            self.assertFalse(a.discover(CollectionWindow(TARGET)).ok)
            self.assertEqual(len(session.calls), 1)

    def test_redirect_and_http_200_challenge_are_refused(self):
        for response, status in [(Response(ID_LISTING, b"", 302), st.DISALLOWED_REDIRECT),
                                 (Response(ID_LISTING, b'<html><title>Just a moment</title></html>'), st.ACCESS_CHALLENGED)]:
            a, _ = adapter("indonesia", {ID_LISTING: response})
            self.assertEqual(a.discover(CollectionWindow(TARGET)).status, status)

    def test_fetch_cannot_bypass_discovery(self):
        a, session = adapter("indonesia")
        result = a.fetch(CandidateReference(ID_LISTING, a.slug))
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(session.calls, [])


class Runner(Case):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"

    def go(self, run_id="r1", mutations=None, cap=40):
        a, _ = adapter("indonesia", mutations)
        return runner.run("indonesia", self.state, TARGET, 0, cap, run_id, "collector-sha", adapter=a)

    def test_original_records_captures_clock_and_append_only_ledger(self):
        entry = self.go()
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(entry["inserted"], 1)
        self.assertEqual(len(entry["requests"]), 3)
        before = {p: p.read_bytes() for p in (self.state / "ledger").glob("*.json")}
        clock = (self.state / "clock.json").read_bytes()
        second = self.go("r2")
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(clock, (self.state / "clock.json").read_bytes())
        self.assertEqual(len(list((self.state / "ledger").glob("*.json"))), 2)
        for p, body in before.items():
            self.assertEqual(p.read_bytes(), body)
        for p in (self.state / "captures").glob("*.bin"):
            self.assertEqual(p.stem, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_failure_preserves_evidence_without_starting_clock_or_corpus(self):
        entry = self.go(mutations={ID_LISTING: Response(ID_LISTING, b"denied", 403)})
        self.assertEqual(entry["result"], st.AUTH_FAILURE)
        self.assertFalse((self.state / "clock.json").exists())
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertEqual(len(entry["requests"]), 2)

    def test_extraction_failure_does_not_store_a_partial_batch(self):
        row = next(r for r in ROWS if r.get("capture") == "kemhan-article.bin")
        payload = fixture(row["capture"]).replace(b"6 Oktober 2026", b"5 Oktober 2026")
        entry = self.go(mutations={row["url"]: Response(row["url"], payload)})
        self.assertEqual(entry["result"], st.EXTRACTION_FAILURE)
        self.assertEqual(entry["inserted"], 0)
        self.assertFalse((self.state / "shadow.db").exists())

    def test_failure_after_one_complete_release_rolls_back_the_whole_batch(self):
        soup = BeautifulSoup(fixture("korea-filtered.bin"), "html.parser")
        links = soup.select('a[href*="pressReleaseView.do"][href*="pageIndex="]')
        for link in links[2:]:
            link.parent.decompose()
        soup.select_one('#mainForm input[name="startDate"]')["value"] = "2026-10-02"
        soup.select_one(".result strong").string = "2"
        for link in soup.select(".paging a[onclick]"):
            if "pageLink(" in link["onclick"]:
                link.parent.decompose()
        document = next(r["url"] for r in ROWS if r.get("capture") == "korea-document-2.bin")
        a, _ = adapter("korea", {KR_LISTING: Response(KR_LISTING, str(soup).encode()),
                                  document: Response(document, b"<html>unavailable</html>")})
        entry = runner.run("korea", self.state, TARGET, 4, adapter=a)
        self.assertEqual(entry["selected"], 2)
        self.assertEqual(entry["extracted"], 1)
        self.assertEqual(entry["inserted"], 0)
        self.assertFalse((self.state / "shadow.db").exists())
        self.assertFalse((self.state / "clock.json").exists())

    def test_ambiguous_rerun_is_refused_before_state_creation(self):
        from contextlib import redirect_stderr
        with redirect_stderr(io.StringIO()):
            code = runner.main(["--desk", "indonesia", "--state-dir", str(self.state),
                                "--event-name", "schedule", "--cron-utc", "07:10", "--run-attempt", "2"])
        self.assertEqual(code, 2)
        self.assertFalse(self.state.exists())

    def test_wrong_desk_cannot_reuse_an_existing_corpus(self):
        self.go()
        with self.assertRaisesRegex(ValueError, "another desk"):
            runner.run("korea", self.state, TARGET)

    def test_korea_stores_both_capture_types_and_explicit_republication_metadata(self):
        a, _ = adapter("korea")
        entry = runner.run("korea", self.state, TARGET, 0, adapter=a)
        self.assertEqual(entry["result"], st.OK)
        self.assertEqual(len(entry["requests"]), 4)
        with sqlite3.connect(self.state / "shadow.db") as db:
            metadata = json.loads(db.execute("SELECT metadata_json FROM shadow_records").fetchone()[0])
        self.assertEqual(metadata["issuer"], "국방부")
        self.assertEqual(metadata["body_scope"], "published_hwpx_text")
        path = self.state / "captures" / (metadata["document_capture_sha256"] + ".bin")
        self.assertEqual(hwpx_text(path.read_bytes()), hwpx_text(fixture("korea-document-1.bin")))

    def test_window_over_cap_fails_before_body_fetch(self):
        a, session = adapter("indonesia")
        entry = runner.run("indonesia", self.state, TARGET, 6, 1, adapter=a)
        self.assertEqual(entry["result"], st.LISTING_FAILURE)
        self.assertEqual(entry["selected"], 0)
        self.assertEqual(len(session.calls), 3)
        self.assertFalse((self.state / "clock.json").exists())

    def test_reviewer_exports_originals_read_only_without_human_sign_off(self):
        self.go()
        before = reviewer.hash_files(self.state)
        report = reviewer.review(self.state, "indonesia", Path(self.tmp.name) / "packet", TARGET)
        self.assertEqual(report["records"], 1)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["mode"], "rehearsal")
        self.assertFalse(report["human_review_completed"])
        self.assertFalse(report["promotion_authorized"])
        self.assertEqual(reviewer.hash_files(self.state), before)
        protected = Path(self.tmp.name) / "other-checkout"
        with mock.patch.object(reviewer, "git", return_value=("worktree " + str(protected) + "\n").encode()):
            with self.assertRaisesRegex(ValueError, "outside collector"):
                reviewer.review(self.state, "indonesia", protected / "packet", TARGET)

    def test_reviewer_reports_capture_corruption_and_a_missing_logical_day(self):
        self.go()
        capture = next((self.state / "captures").glob("*.bin"))
        capture.write_bytes(b"")
        report = reviewer.review(self.state, "indonesia", Path(self.tmp.name) / "packet", date(2026, 10, 7))
        self.assertTrue(report["findings"])
        self.assertEqual(report["missing_successful_days"], ["2026-10-07"])

    def test_formal_review_reads_pinned_git_objects_and_refuses_foreign_branches(self):
        import subprocess
        self.go()
        repo = Path(self.tmp.name) / "git-state"
        repo.mkdir()
        import shutil
        shutil.copytree(self.state, repo / "state")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
        git("init")
        git("checkout", "--orphan", reviewer.BRANCHES["indonesia"])
        git("add", "state")
        git("-c", "user.name=Fixture rehearsal", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture state only")
        commit = git("rev-parse", "HEAD").decode().strip()
        (repo / "state/clock.json").write_text("uncommitted fixture corruption")
        export = Path(self.tmp.name) / "export"
        tree = reviewer.export_commit(repo, commit, "indonesia", export)
        report = reviewer.review(export / "state", "indonesia", Path(self.tmp.name) / "packet", TARGET, commit, tree)
        self.assertEqual(report["mode"], "formal_commit_snapshot")
        self.assertEqual(report["findings"], [])
        with self.assertRaises(subprocess.CalledProcessError):
            reviewer.export_commit(repo, commit, "korea", Path(self.tmp.name) / "wrong")
        (repo / "unexpected").write_text("fixture contamination")
        git("add", "unexpected")
        git("-c", "user.name=Fixture rehearsal", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Fixture contamination")
        bad_commit = git("rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(ValueError, "outside state"):
            reviewer.export_commit(repo, bad_commit, "indonesia", Path(self.tmp.name) / "contaminated")

    def test_legacy_public_workflow_is_a_retired_no_source_tombstone(self):
        raw = (ROOT / ".github/workflows/indonesia_korea_shadow.yml").read_text()
        self.assertIn("workflow_dispatch:", raw)
        self.assertNotIn("  schedule:", raw)
        self.assertNotIn("shadow/korea-policy-briefing", raw)
        self.assertNotIn("scripts/shadow_collect_desk.py", raw)
        self.assertNotIn("git push", raw)
        self.assertNotIn("git clone", raw)

    def test_repository_paths_and_symlink_state_are_refused(self):
        with self.assertRaises(ValueError):
            runner.assert_isolated(ROOT / "shadow/test-state")
        link = Path(self.tmp.name) / "link"
        link.symlink_to(self.state)
        with self.assertRaises(ValueError):
            runner.assert_isolated(link)
        protected = Path(self.tmp.name) / "other-collector-checkout"
        with mock.patch.object(runner.subprocess, "check_output", return_value="worktree " + str(protected) + "\n"):
            with self.assertRaises(ValueError):
                runner.assert_isolated(protected / "state")

    def test_no_relevance_translation_or_production_storage_in_runner(self):
        import ast
        source = (ROOT / "scripts/shadow_collect_desk.py").read_text()
        tree = ast.parse(source)
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertFalse(any("pla_watch.db" in s or "output/" in s for s in strings))


class RetiredPublicWorkflow(unittest.TestCase):
    def test_no_live_korea_collection_route_survives(self):
        raw = (ROOT / ".github/workflows/indonesia_korea_shadow.yml").read_text()
        self.assertEqual(raw.count("workflow_dispatch:"), 1)
        self.assertNotIn("schedule:", raw)
        self.assertNotIn("--state-dir", raw)
        self.assertNotIn("shadow/korea-policy-briefing", raw)



if __name__ == "__main__":
    unittest.main()
