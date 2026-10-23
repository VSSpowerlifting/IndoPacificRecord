"""Real publisher metadata replay; synthetic faults never prove live operation."""
import copy
import hashlib
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from core.collection import status as st
from core.collection.vietnam_government_documents import (FAMILY, INDEX, ISSUER,
    GovernmentOfficeAdapter, canonical_url, digest, listing, parse_document)
from core.regional_official_link_render import read_live_links
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0013_vietnam_regional_official_links as vn
from migrations.versions import m0014_ph_nsc_regional_official_links as nsc
from migrations.versions import m0018_government_document_metadata as migration
from processing import government_document_intake as intake
from scripts.collect_vietnam_government_documents import collect
from scraper.sources.vn_shadow_http import Raw, Refusal

FIX = Path(__file__).parent / "fixtures/vietnam_government_documents"
NOW = "2026-10-23T16:00:00Z"
SHA = "a" * 40


def metadata(ident="220077"):
    return parse_document((FIX / ("doc" + ident + ".html")).read_text(),
                          INDEX + "?pageid=27160&docid=" + ident)


def database():
    conn = sqlite3.connect(":memory:")
    for m in (base, vn, nsc, migration):
        m.up(conn)
    return conn


class ReplayAdapter(GovernmentOfficeAdapter):
    """Real parsers/robots policy, explicitly offline transport."""
    def _get(self, url, limit, generic, settle=None):
        if url == INDEX + "robots.txt":
            raw = Raw(url, 200, {"content-type": "text/plain"}, b"User-agent: *\nAllow: /", False, NOW)
        elif url == INDEX:
            raw = Raw(url, 200, {"content-type": "text/html"}, (FIX / "listing.html").read_bytes(), False, NOW)
        else:
            ident = url.rsplit("=", 1)[1]
            file = FIX / ("doc" + ident + ".html")
            raw = Raw(url, 200 if file.exists() else 404, {"content-type": "text/html"},
                file.read_bytes() if file.exists() else b"", False, NOW)
        self.request_log.append({"url": url, "status": raw.status})
        if settle:
            settle(raw)
        return raw


class GovernmentDocuments(unittest.TestCase):
    def setUp(self):
        self.conn = database()
        self.addCleanup(self.conn.close)

    def admit(self, records=None):
        return intake.admit(self.conn, [(m, "b" * 64) for m in records or [metadata()]],
            source_sha=SHA, run_id="offline-fixture", observed_utc=NOW)

    def test_authentic_metadata_and_different_issuer(self):
        power, aviation = metadata(), metadata("220078")
        self.assertEqual((power["document_number"], power["issuer"], power["signatory"]),
                         ("10790/VPCP-CN", ISSUER, "Đặng Xuân Phong"))
        self.assertEqual((aviation["document_type"], aviation["signatory"]), ("Thông báo", "Nguyễn Danh Huy"))
        self.assertEqual(power["issue_date"], "2026-10-22")
        self.assertIsNone(power["effective_date"])
        self.assertNotEqual(power["publisher"], power["issuer"])
        self.assertIsNone(parse_document((FIX / "other.html").read_text(),
            INDEX + "?pageid=27160&docid=220076"))

    def test_url_identity_rejects_ssrf_and_ambiguous_queries(self):
        for url in ["http://vanban.chinhphu.vn/?pageid=27160&docid=220077",
                    INDEX + "?pageid=27160&docid=220077&docid=220078",
                    INDEX + "?pageid=27160&docid=220077#other", "https://evil.example/?pageid=27160&docid=1"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url)
        self.assertEqual(canonical_url(INDEX + "?docid=220077&pageid=27160"), metadata()["official_url"])

    def test_real_listing_and_fail_closed_framing(self):
        raw = (FIX / "listing.html").read_text()
        self.assertEqual(len(listing(raw)), 50)
        for bad in ["<html></html>", raw.replace("</html>", ""),
                    raw.replace('class="code"', 'class="changed"'),
                    raw.replace("<html>", '<html><title>Just a moment</title>')]:
            with self.subTest(), self.assertRaises(ValueError):
                listing(bad)

    def test_metadata_ambiguity_and_attachment_host_are_held(self):
        raw = (FIX / "doc220077.html").read_text()
        for bad in [raw.replace("22-10-2026", "31-02-2026"),
                    raw.replace("datafiles.chinhphu.vn", "127.0.0.1"),
                    raw.replace(".pdf\"", ".exe\""),
                    raw.replace("Công văn", "Nghị định"),
                    raw.replace("</table>", "<tr><td>Người ký</td><td>conflict</td></tr></table>")]:
            with self.subTest(), self.assertRaises(ValueError):
                parse_document(bad, metadata()["official_url"])

    def test_idempotency_revision_history_and_shared_store(self):
        self.assertEqual(self.admit()["new"], 1)
        self.assertEqual(self.admit()["unchanged"], 1)
        revised = metadata(); revised["signatory"] += " (synthetic revision)"
        self.assertEqual(self.admit([revised])["revised"], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM official_document_versions").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM regional_official_source_links").fetchone()[0], 1)
        public = read_live_links(self.conn, "vietnam")
        self.assertEqual(public[0]["document"]["signatory"], revised["signatory"])

    def test_changed_unrelated_subject_withdraws_projection(self):
        self.admit()
        changed = metadata(); changed["subject"] = "Synthetic routine personnel appointment"
        self.assertEqual(self.admit([changed])["filtered"], 1)
        self.assertEqual(read_live_links(self.conn, "vietnam"), [])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM official_document_versions").fetchone()[0], 2)

    def test_rollback_leaves_no_partial_publication(self):
        bad = metadata("220078"); bad["issuer"] = "different institution"
        with self.assertRaises(ValueError):
            with self.conn:
                self.admit([metadata(), bad])
        self.assertEqual(read_live_links(self.conn, "vietnam"), [])

    def test_no_body_translation_or_model_use(self):
        m = metadata(); m["body"] = "unapproved"
        with self.assertRaises(ValueError): self.admit([m])
        from processing.screening import profile_for_source
        profile = profile_for_source(FAMILY)
        self.assertFalse(profile.daily_queue)
        with self.assertRaises(LookupError): profile.build_messages("title", "body")
        self.assertFalse(intake.policy()["external_model_transmission"])

    def test_corrupt_current_metadata_cannot_render(self):
        self.admit()
        self.conn.execute("UPDATE official_document_versions SET metadata_json='{}'")
        with self.assertRaises(ValueError): read_live_links(self.conn, "vietnam")

    def test_live_transport_refuses_redirect_html_pdf_and_size(self):
        adapter = GovernmentOfficeAdapter()
        for raw in [Raw(INDEX, 302, {"location": "https://evil.example"}, b"", False, NOW),
                    Raw(INDEX, 200, {"content-type": "application/pdf"}, b"%PDF", False, NOW),
                    Raw(INDEX, 200, {"content-type": "text/html"}, b"", True, NOW)]:
            with self.subTest(), self.assertRaises(Refusal):
                adapter._screen(raw, st.LISTING_FAILURE)

    def test_robots_refusal_no_body_request(self):
        adapter = GovernmentOfficeAdapter()
        raw = Raw(INDEX + "robots.txt", 403, {"content-type": "text/plain"}, b"no", False, NOW)
        with patch.object(adapter, "_exchange", return_value=raw) as exchange:
            result = collect(self.conn, adapter, source_sha=SHA, run_id="robots-refused", observed_utc=NOW)
        self.assertEqual(result["status"], "held")
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual(read_live_links(self.conn, "vietnam"), [])

    def test_replay_partial_retry_zero_new_and_no_attachment_requests(self):
        first = ReplayAdapter()
        report = collect(self.conn, first, source_sha=SHA, run_id="offline-1", observed_utc=NOW)
        self.assertEqual(report["new"], 2)
        self.assertEqual(report["status"], "partial")  # Other detail fixtures intentionally absent.
        second = collect(self.conn, ReplayAdapter(), source_sha=SHA, run_id="offline-2", observed_utc=NOW)
        self.assertEqual(second["new"], 0)
        self.assertEqual(second["unchanged"], 2)
        self.assertTrue(all(r["url"].startswith(INDEX) for r in first.request_log))
        self.assertEqual(second["model_calls"], 0)

    def test_lost_overlap_records_gap_and_resumes_and_attempt_is_persisted(self):
        previous = {"listing_ids": [INDEX + "?pageid=27160&docid=1"]}
        self.conn.execute("INSERT INTO official_document_collection_runs VALUES (?,?,?,?,?,?)",
            (FAMILY, "old", NOW, SHA, "ok", json.dumps(previous)))
        report = collect(self.conn, ReplayAdapter(), source_sha=SHA, run_id="gap", observed_utc=NOW)
        self.assertTrue(report["coverage_gap"])
        self.assertNotIn("hold_reason", report)
        self.assertEqual(report["new"], 2)
        self.assertGreater(report["requests"], 2)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM official_document_collection_runs").fetchone()[0], 2)

    def test_backdated_order_and_budget_cap_never_hold_discovery(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup((FIX / "listing.html").read_text(), "html.parser")
        rows = [r for r in soup.select("table.search-result tr") if r.select_one(".code")]
        rows[0].insert_before(rows[-1].extract())  # Oldest entry now listed first.
        self.assertEqual(len(listing(str(soup))), len(rows))
        adapter = ReplayAdapter()
        with patch("core.collection.vietnam_government_documents.MAX_DOCUMENTS", 1):
            found = adapter.discover(None)
        self.assertTrue(found.ok)
        self.assertEqual(len(found.references), 1)
        self.assertGreater(adapter.candidates_skipped, 0)

    def test_migration_replay_keeps_other_families_constraints(self):
        migration.up(self.conn)
        self.assertTrue(migration.is_already_applied(self.conn))
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (FAMILY, "vpcp-vi:1", "vietnam", INDEX+"?pageid=27160&docid=1", "2026-10-22",
                 "vn_mps", "vn_mps", None, SHA, "b"*64, "test", "official_link_only", "c"*64, NOW))


if __name__ == "__main__":
    unittest.main()
