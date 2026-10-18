"""No-network DAPA vault-to-public metadata bridge and fail-closed negatives."""
import copy
import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from core import korea_dapa_private_to_production as b
from migrations.versions import (
    m0008_korea_official_source_metadata as old,
    m0011_korea_dapa_metadata_source_separation as newer,
)

KEY = "fictional-test-key-only-" + "x" * 40


def sample():
    row = {
        "source_identity": "korea-dapa-policy:156785999",
        "canonical_official_url": b.URL_PREFIX + "156785999",
        "publisher_posted_date": "2026-10-18",
        "official_issuer": "kr_dapa",
        "official_republisher": "kr_policy_briefing",
        "original_title_sha256": "a" * 64,
        "original_text_sha256": "b" * 64,
        "publisher_html_sha256": "c" * 64,
        "original_hwpx_sha256": "d" * 64,
    }
    row["candidate_version_sha256"] = b.version_hash(row)
    return {
        "schema": b.SCHEMA,
        "source_repository": b.REPO,
        "source_ref": b.REF,
        "source_git_commit": "e" * 40,
        "source_db_sha256": "f" * 64,
        "source_run_attempt": "39076047212-1",
        "records": [row],
    }


class DAPABridgeContracts(unittest.TestCase):
    def setUp(self):
        self.packet = sample()
        self.mac = b.sign(self.packet, KEY)

    def test_exact_signed_packet_is_verified(self):
        self.assertEqual(
            b.verify_signed_packet(self.packet, self.mac, KEY)[0]["official_issuer"],
            "kr_dapa")
        self.assertEqual(self.mac, b.sign(self.packet, KEY))

    def test_unsigned_wrong_key_malformed_hmac_refused(self):
        for key, mac in ((KEY, "0" * 64), ("y" * 40, self.mac),
                         ("short", self.mac), (KEY, "not-a-mac")):
            with self.subTest(mac=mac[:8], key=key[:8]), self.assertRaises(
                    b.DAPABridgeHold):
                b.verify_signed_packet(self.packet, mac, key)

    def test_wrong_issuer_url_source_ref_date_and_hash_refused(self):
        mutations = [
            ("row", "official_issuer", "kr_mnd"),
            ("row", "canonical_official_url", "http://example.com"),
            ("row", "canonical_official_url", b.URL_PREFIX + "156785998"),
            ("row", "source_identity", "korea-policy:156785999"),
            ("row", "publisher_posted_date", "2026-02-30"),
            ("row", "publisher_posted_date", "2026-10-15"),
            ("row", "publisher_html_sha256", "0" * 64),
            ("packet", "source_ref", "main"),
            ("packet", "source_repository", "VSSpowerlifting/IndoPacificRecord"),
            ("packet", "source_run_attempt", "local-run"),
        ]
        for where, key, val in mutations:
            packet = copy.deepcopy(self.packet)
            (packet["records"][0] if where == "row" else packet)[key] = val
            with self.subTest(key=key, value=val), self.assertRaises(
                    b.DAPABridgeHold):
                b.verify_structure(packet)

    def test_extra_text_fields_or_multiple_rows_refused(self):
        for key, value in (("title_original", "NEVER EXPORT"),
                           ("text_original", "NEVER EXPORT"),
                           ("document_bytes", "HWPX CONTENT"),
                           ("original_url", "sensitive")):
            pkt = copy.deepcopy(self.packet)
            pkt["records"][0][key] = value
            with self.subTest(extra=key), self.assertRaises(b.DAPABridgeHold):
                b.verify_structure(pkt)
        pkt = copy.deepcopy(self.packet)
        pkt["records"].append(pkt["records"][0])
        with self.assertRaises(b.DAPABridgeHold):
            b.verify_structure(pkt)

    @staticmethod
    def batch(n):
        pkt = sample()
        row = pkt["records"][0]
        pkt["records"] = []
        for i in range(n):
            item = copy.deepcopy(row)
            suffix = str(156785990 + i)
            item["source_identity"] = b.PREFIX + suffix
            item["canonical_official_url"] = b.URL_PREFIX + suffix
            item["original_text_sha256"] = format(i + 1, "064x")
            item["candidate_version_sha256"] = b.version_hash(item)
            pkt["records"].append(item)
        return pkt

    def test_bounded_sorted_one_day_batch_and_invalid_sizes(self):
        for n in (1, 2, 5):
            pkt = self.batch(n)
            self.assertEqual(len(b.verify_signed_packet(pkt, b.sign(pkt, KEY), KEY)), n)
        for n in (0, 6):
            with self.assertRaisesRegex(b.DAPABridgeHold, "bounded"):
                b.sign(self.batch(n), KEY)
        for broken in ("reverse", "date", "duplicate", "foreign"):
            pkt = self.batch(2)
            if broken == "reverse":
                pkt["records"].reverse()
            elif broken == "date":
                pkt["records"][1]["publisher_posted_date"] = "2026-10-19"
                pkt["records"][1]["candidate_version_sha256"] = b.version_hash(pkt["records"][1])
            elif broken == "duplicate":
                pkt["records"][1] = copy.deepcopy(pkt["records"][0])
            else:
                pkt["records"][1]["text_original"] = "NO PRIVATE TEXT"
            with self.subTest(broken=broken), self.assertRaises(b.DAPABridgeHold):
                b.sign(pkt, KEY)

    def test_batch_transaction_rollback_on_middle_collision(self):
        pkt = self.batch(3)
        mac = b.sign(pkt, KEY)
        with sqlite3.connect(":memory:") as conn:
            old.up(conn)
            newer.up(conn)
            inserted = b.admit(conn, pkt, mac, KEY, as_of_utc="2026-10-18T12:00:00Z")
            self.assertEqual(inserted["new_official_links_admitted"], 3)
            self.assertEqual(inserted["batch_records"], 3)
            self.assertEqual(b.admit(
                conn, pkt, mac, KEY, as_of_utc="2026-10-18T12:01:00Z")[
                    "unchanged_official_links"], 3)
            count_before = conn.execute("SELECT COUNT(*) FROM korea_official_source_records").fetchone()[0]
            followup = self.batch(5)
            followup["records"][1]["original_text_sha256"] = "9" * 64
            followup["records"][1]["candidate_version_sha256"] = b.version_hash(followup["records"][1])
            with self.assertRaisesRegex(b.DAPABridgeHold, "drifted"):
                b.admit(conn, followup, b.sign(followup, KEY),
                        KEY, as_of_utc="2026-10-18T12:02:00Z")
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM korea_official_source_records").fetchone()[0],
                count_before)
            self.assertNotIn(b.PREFIX + "156785993", {
                row[0] for row in conn.execute(
                    "SELECT source_identity FROM korea_official_source_records")})

    def test_bad_version_even_with_attacker_signature_refused(self):
        pkt = copy.deepcopy(self.packet)
        pkt["records"][0]["candidate_version_sha256"] = "1" * 64
        with self.assertRaisesRegex(b.DAPABridgeHold, "candidate_version"):
            b.sign(pkt, KEY)

    def test_mnd_and_dapa_are_separate_and_idempotent(self):
        with sqlite3.connect(":memory:") as conn:
            old.up(conn)
            mnd = (
                "korea-policy:156785286", b.URL_PREFIX + "156785286",
                "2026-10-15", "a" * 40, "b" * 64, "c" * 64,
                "d" * 64, "e" * 64, "f" * 64, "0" * 64,
                "kr_mnd", "kr_policy_briefing", "ko", "B", "syndicated",
                "official_link_only", "2026-10-17T20:00:00Z",
                "2026-10-17T20:00:00Z",
            )
            conn.execute("INSERT INTO korea_official_source_records VALUES (" +
                         ",".join("?" for _ in mnd) + ")", mnd)
            newer.up(conn)
            first = b.admit(conn, self.packet, self.mac, KEY,
                            as_of_utc="2026-10-18T12:00:00Z")
            second = b.admit(conn, self.packet, self.mac, KEY,
                             as_of_utc="2026-10-18T12:01:00Z")
            self.assertEqual(first["new_official_links_admitted"], 1)
            self.assertEqual(second["new_official_links_admitted"], 0)
            self.assertEqual(
                conn.execute("SELECT * FROM korea_official_source_records "
                             "WHERE official_issuer='kr_mnd'").fetchone(), mnd)
            row = conn.execute(
                "SELECT source_identity,official_issuer,public_scope "
                "FROM korea_official_source_records WHERE official_issuer='kr_dapa'"
            ).fetchone()
            self.assertEqual(row, ("korea-dapa-policy:156785999",
                                   "kr_dapa", "official_link_only"))
            self.assertEqual(conn.execute("PRAGMA quick_check").fetchone(), ("ok",))

    def test_changed_original_conflict_rolls_back(self):
        with sqlite3.connect(":memory:") as conn:
            old.up(conn)
            newer.up(conn)
            b.admit(conn, self.packet, self.mac, KEY,
                    as_of_utc="2026-10-18T12:00:00Z")
            before = conn.execute("SELECT * FROM korea_official_source_records").fetchall()
            bad = copy.deepcopy(self.packet)
            bad["records"][0]["original_text_sha256"] = "3" * 64
            bad["records"][0]["candidate_version_sha256"] = b.version_hash(bad["records"][0])
            mac = b.sign(bad, KEY)
            with self.assertRaisesRegex(b.DAPABridgeHold, "drifted"):
                b.admit(conn, bad, mac, KEY,
                        as_of_utc="2026-10-18T12:01:00Z")
            self.assertEqual(
                before, conn.execute("SELECT * FROM korea_official_source_records").fetchall())

    def test_unauthorized_mnd_url_collision_refused(self):
        with sqlite3.connect(":memory:") as conn:
            old.up(conn)
            newer.up(conn)
            row = list((
                "korea-policy:156785999", b.URL_PREFIX + "156785999",
                "2026-10-18", "a" * 40, "b" * 64, "c" * 64,
                "d" * 64, "e" * 64, "f" * 64, "0" * 64,
                "kr_mnd", "kr_policy_briefing", "ko", "B", "syndicated",
                "official_link_only", "2026-10-17T20:00:00Z",
                "2026-10-17T20:00:00Z",
            ))
            conn.execute("INSERT INTO korea_official_source_records VALUES (" +
                         ",".join("?" for _ in row) + ")", row)
            with self.assertRaises(b.DAPABridgeHold):
                b.admit(conn, self.packet, self.mac, KEY,
                        as_of_utc="2026-10-18T12:01:00Z")
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM korea_official_source_records").fetchone()[0], 1)

    def test_no_original_export_in_packet(self):
        blob = b.canonical(self.packet)
        for forbidden in (b"title_original", b"text_original", b".hwpx",
                          b"document_url", b"publisher_text_license_notice",
                          b"summary_english"):
            self.assertNotIn(forbidden, blob)

    def test_live_private_evidence_cannot_be_forged_with_synthetic_packet(self):
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertRaises(b.DAPABridgeHold):
                b.export_from_private_checkout(Path(dirname), "39076047212-1")


class DAPASyntheticVaultRoundTrip(unittest.TestCase):
    """Actual disposable private Git, ledger, original hashes and SQLite."""

    def test_actual_korea_page_renders_admitted_dapa_without_originals(self):
        # Actual preview renderer + actual production schema, but only a
        # disposable database copy and temporary output. No public writes.
        import sys
        from scripts.reconcile_db import read_only
        from core.korea_official_live_links import load_live_korea_official_links
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site" / "preview"))
        import generate_preview as preview

        packet = sample()
        second = copy.deepcopy(packet["records"][0])
        second["source_identity"] = "korea-dapa-policy:156785998"
        second["canonical_official_url"] = b.URL_PREFIX + "156785998"
        second["original_text_sha256"] = "9" * 64
        second["candidate_version_sha256"] = b.version_hash(second)
        packet["records"].insert(0, second)
        mac = b.sign(packet, KEY)
        with tempfile.TemporaryDirectory(prefix="ipr-dapa-render-") as folder:
            sandbox = Path(folder)
            temp_db = sandbox / "safe-production-copy.sqlite"
            with read_only(root / "pla_watch.db") as source, sqlite3.connect(temp_db) as dest:
                source.backup(dest)
            with sqlite3.connect(temp_db) as conn:
                newer.up(conn)
                conn.commit()
            baseline = sandbox / "baseline"
            preview.build(baseline, "DAPA synthetic bridge check", temp_db,
                          snapshot=preview.snapshot_from_corpus(temp_db),
                          site_origin="https://indopacificrecord.org")
            first = (baseline / "korea.html").read_text(encoding="utf-8")
            with sqlite3.connect(temp_db) as conn:
                result = b.admit(conn, packet, mac, KEY,
                                 as_of_utc="2026-10-18T12:00:00Z")
                conn.commit()
            self.assertEqual(result["new_official_links_admitted"], 2)
            published = sandbox / "after"
            preview.build(published, "DAPA synthetic bridge check", temp_db,
                          snapshot=preview.snapshot_from_corpus(temp_db),
                          site_origin="https://indopacificrecord.org")
            second = (published / "korea.html").read_text(encoding="utf-8")
            self.assertEqual(second.count("data-korea-auto-official-link="),
                             first.count("data-korea-auto-official-link=") + 2)
            self.assertIn('data-korea-auto-official-link="korea-dapa-policy:156785998"', second)
            self.assertIn('data-korea-auto-official-link="korea-dapa-policy:156785999"', second)
            self.assertIn(b.URL_PREFIX + "156785999", second)
            self.assertIn("DAPA official press release 156785999", second)
            listed = load_live_korea_official_links(temp_db)
            self.assertEqual(sum(row["source_identity"] ==
                                 "korea-dapa-policy:156785999" for row in listed), 1)
            for forbidden in ("original_title_sha256", "original_text_sha256",
                              "original_hwpx_sha256", "source_git_commit",
                              "DAPA_BRIDGE_KEY", "title_original", "text_original",
                              "summary_english", "FAKE HWPX",
                              "FICTIONAL SYNTHETIC BODY"):
                self.assertNotIn(forbidden, second)
            self.assertFalse((root / "pla_watch.db-wal").exists())
            self.assertFalse((root / "pla_watch.db-shm").exists())

    def test_private_original_replay_to_signed_public_metadata(self):
        import subprocess

        import io
        import zipfile

        run = "39076047219-1"
        body, title = "FICTIONAL SYNTHETIC BODY", "FICTIONAL SYNTHETIC TITLE"
        url = b.URL_PREFIX + "156785999"
        document_url = ("https://www.korea.kr/common/download.do"
                        "?fileId=456789&tblKey=GMN")
        html = ("""<html><head><link rel="canonical" href="{url}"></head>
        <body><div class="view_title"><h1>{title}</h1></div>
        <div class="variety"><div class="info">
        <span>2026.10.18</span>
        <a class="gotosite" href="/news/ministryNewsList.do?repCode=B00008">
        방위사업청</a></div></div>
        <a href="/common/download.do?fileId=456789&tblKey=GMN">
        fictional-original.hwpx</a>
        </body></html>""".format(url=url, title=title)).encode("utf-8")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("Contents/section0.xml",
                             "<root><p><run><t>" + body +
                             "</t></run></p></root>")
        doc = buf.getvalue()
        robots = b"User-agent: *\\nAllow: /\\n"
        listing = b"<html><body>fictional listing</body></html>"
        htmlsha, docsha = b.digest(html), b.digest(doc)
        robotsha, listingsha = b.digest(robots), b.digest(listing)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "private-vault"
            root.mkdir()
            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(root), *args],
                    check=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True).stdout.strip()
            git("init", "-q")
            git("checkout", "-b", b.REF)
            git("config", "user.name", "Synthetic Test")
            git("config", "user.email", "test@example.invalid")
            state = root / "state"
            for sub in ("captures", "ledger", "private_attempts"):
                (state / sub).mkdir(parents=True)
            for sha, payload in ((htmlsha, html), (docsha, doc),
                                (robotsha, robots), (listingsha, listing)):
                (state / "captures" / (sha + ".bin")).write_bytes(payload)
            metadata = {
                "issuer": "방위사업청",
                "publisher": "대한민국 정책브리핑",
                "body_scope": "captured_hwpx_text_not_editorially_approved",
                "attachments_collected": True,
                "document_url": document_url,
                "document_capture_sha256": docsha,
                "public_metadata_admission_approved": False,
                "public_full_text_approved": False,
                "document_reuse_approved": False,
            }
            db = state / "shadow.db"
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "CREATE TABLE shadow_records("
                    "source_identity TEXT, url TEXT, source_slug TEXT,"
                    "title_original TEXT, text_original TEXT,"
                    "published_date TEXT, language_tag TEXT, metadata_json TEXT,"
                    "content_sha256 TEXT, capture_sha256 TEXT,"
                    "first_seen_run TEXT)")
                conn.execute(
                    "INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("korea-dapa-policy:156785999", url,
                     "kr_policy_dapa_releases", title, body,
                     "2026-10-18", "ko", json.dumps(metadata),
                     b.digest(body.encode("utf-8")), htmlsha, run))
                conn.commit()
            (state / "private_attempts" / (run + ".json")).write_text(
                json.dumps({
                    "run_attempt": run, "collector_commit": "a" * 40,
                    "collector_exit_status": 0,
                    "public_admission_approved": False,
                    "original_reuse_approved": False,
                }))
            ledger = {
                "desk": "korea_dapa", "run_id": run,
                "collector_commit": "a" * 40,
                "result": "ok", "health": "ok",
                "inserted": 1, "selected": 1, "retrieved": 1,
                "extracted": 1, "fetch_failures": 0,
                "extraction_failures": 0, "access_failures": 0,
                "failures": [], "target_date_source": "explicit",
                "target_date": "2026-10-18", "cap": 1, "lookback_days": 0,
                "requests": [
                    {"requested_url": "https://www.korea.kr/robots.txt",
                     "capture_sha256": robotsha, "http_status": 200},
                    {"requested_url": "https://www.korea.kr/briefing/pressReleaseList.do",
                     "capture_sha256": listingsha, "http_status": 200,
                     "form": {"repCode": "B00008", "startDate": "2026-10-18",
                              "endDate": "2026-10-18"}},
                    {"requested_url": url, "capture_sha256": htmlsha,
                     "http_status": 200},
                    {"requested_url": document_url, "capture_sha256": docsha,
                     "http_status": 200},
                ],
            }
            (state / "ledger" / ("20261018T000000.000000+0000-" + run +
                                 ".json")).write_text(json.dumps(ledger))
            # Add a second separately captured article and HWPX in the same
            # private attempt. Both must survive one atomic signature/receipt.
            second_url = b.URL_PREFIX + "156785998"
            second_title = "SECOND FICTIONAL DAPA TITLE"
            second_body = "SECOND FICTIONAL HWPX CONTENT"
            second_document_url = document_url.replace("456789", "456790")
            second_html = (
                html.replace(b"156785999", b"156785998")
                    .replace(b"456789", b"456790")
                    .replace(title.encode("utf-8"), second_title.encode("utf-8")))
            second_buffer = io.BytesIO()
            with zipfile.ZipFile(second_buffer, "w") as archive:
                archive.writestr(
                    "Contents/section0.xml",
                    "<root><p><run><t>" + second_body +
                    "</t></run></p></root>")
            second_document = second_buffer.getvalue()
            second_html_sha = b.digest(second_html)
            second_doc_sha = b.digest(second_document)
            (state / "captures" / (second_html_sha + ".bin")).write_bytes(second_html)
            (state / "captures" / (second_doc_sha + ".bin")).write_bytes(second_document)
            second_meta = dict(metadata, document_url=second_document_url,
                               document_capture_sha256=second_doc_sha)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("korea-dapa-policy:156785998", second_url,
                     "kr_policy_dapa_releases", second_title, second_body,
                     "2026-10-18", "ko", json.dumps(second_meta),
                     b.digest(second_body.encode("utf-8")), second_html_sha, run))
                conn.commit()
            ledger.update(inserted=2, selected=2, retrieved=2, extracted=2,
                          duplicates=0, cap=5)
            ledger["requests"].extend((
                {"requested_url": second_url, "capture_sha256": second_html_sha,
                 "http_status": 200},
                {"requested_url": second_document_url, "capture_sha256": second_doc_sha,
                 "http_status": 200},
            ))
            (state / "ledger" / ("20261018T000000.000000+0000-" + run +
                                 ".json")).write_text(json.dumps(ledger))
            git("add", "state")
            git("commit", "-qm", "private-dapa: preserve source attempt " + run)

            packet = b.export_from_private_checkout(root, run)
            self.assertEqual(packet["source_git_commit"], git("rev-parse", "HEAD"))
            self.assertEqual(packet["source_db_sha256"], b.digest(db.read_bytes()))
            self.assertEqual(len(packet["records"]), 2)
            self.assertEqual(
                [row["source_identity"] for row in packet["records"]],
                ["korea-dapa-policy:156785998", "korea-dapa-policy:156785999"])
            for value in (title, body, document_url,
                          second_title, second_body, second_document_url):
                self.assertNotIn(value, b.canonical(packet).decode("utf-8"))
            signed = b.sign(packet, KEY)
            with sqlite3.connect(":memory:") as prod:
                old.up(prod)
                newer.up(prod)
                self.assertEqual(
                    b.admit(prod, packet, signed, KEY,
                            as_of_utc="2026-10-18T12:00:00Z")[
                                "new_official_links_admitted"], 2)
            (state / "captures" / (second_doc_sha + ".bin")).write_bytes(b"CORRUPTED")
            with self.assertRaises(b.DAPABridgeHold):
                b.export_from_private_checkout(root, run)


if __name__ == "__main__":
    unittest.main()
