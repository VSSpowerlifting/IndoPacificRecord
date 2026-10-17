"""No-network DAPA vault-to-public metadata bridge and fail-closed negatives."""
import copy
import hashlib
import json
import sqlite3
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
            b.verify_signed_packet(self.packet, self.mac, KEY)["official_issuer"],
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


if __name__ == "__main__":
    unittest.main()
