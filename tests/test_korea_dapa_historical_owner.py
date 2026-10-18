"""Synthetic negative controls for the exact Oct 15 historical DAPA exception."""
import copy
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import korea_dapa_historical_owner as hist
from core import korea_dapa_private_to_production as b
from migrations.versions import m0008_korea_official_source_metadata as old
from migrations.versions import m0011_korea_dapa_metadata_source_separation as newer

KEY = "fictional-unit-test-key-" + "Y" * 40


def packet():
    row = {
        "source_identity": hist.IDENTITY, "canonical_official_url": hist.URL,
        "publisher_posted_date": hist.DATE, "official_issuer": b.ISSUER,
        "official_republisher": b.REPUBLISHER,
        "original_title_sha256": hist.TITLE_SHA,
        "original_text_sha256": hist.TEXT_SHA,
        "publisher_html_sha256": hist.HTML_SHA,
        "original_hwpx_sha256": hist.HWPX_SHA,
    }
    row["candidate_version_sha256"] = b.version_hash(row)
    return {
        "schema": hist.SCHEMA, "source_repository": b.REPO,
        "source_ref": b.REF, "source_git_commit": hist.OWNER_COMMIT,
        "source_db_sha256": "a" * 64,
        "source_run_attempt": hist.ATTEMPT, "records": [row],
        "historical_owner_import_commit": hist.OWNER_COMMIT,
        "historical_manifest_sha256": "b" * 64,
        "historical_failed_ledger_sha256": hist.LEDGER_SHA,
        "historical_review_sha256": "c" * 64,
    }


class HistoricalContract(unittest.TestCase):
    def test_exact_bounded_historical_packet_signs_and_admits_only_metadata(self):
        p = packet()
        mac = b.sign(p, KEY)
        self.assertEqual(b.verify_signed_packet(p, mac, KEY)[0]["source_identity"],
                         hist.IDENTITY)
        with sqlite3.connect(":memory:") as db:
            old.up(db)
            newer.up(db)
            first = b.admit(db, p, mac, KEY, as_of_utc="2026-10-18T15:00:00Z")
            second = b.admit(db, p, mac, KEY, as_of_utc="2026-10-18T15:01:00Z")
            self.assertEqual(first["new_official_links_admitted"], 1)
            self.assertEqual(second["new_official_links_admitted"], 0)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            self.assertEqual(db.execute(
                "SELECT source_identity, official_issuer, public_scope "
                "FROM korea_official_source_records").fetchall(),
                [(hist.IDENTITY, "kr_dapa", "official_link_only")])

    def test_routine_live_credential_does_not_inherit_historical_exception(self):
        p = packet()
        p["schema"] = b.SCHEMA
        for field in hist.HIST_FIELDS:
            del p[field]
        with self.assertRaises(b.DAPABridgeHold):
            b.sign(p, KEY)

    def test_historical_packet_cannot_be_retargeted_to_another_source(self):
        for field, value in (
            ("historical_owner_import_commit", "1" * 40),
            ("historical_manifest_sha256", "invalid"),
            ("historical_failed_ledger_sha256", "f" * 64),
            ("historical_review_sha256", ""),
            ("source_run_attempt", "39076047211-1"),
            ("source_repository", "VSSpowerlifting/IndoPacificRecord"),
            ("source_ref", "main"),
            ("source_db_sha256", "invalid"),
        ):
            with self.subTest(field=field):
                p = packet()
                p[field] = value
                with self.assertRaises(b.DAPABridgeHold):
                    b.sign(p, KEY)

        for field, value in (
            ("source_identity", "korea-dapa-policy:156785255"),
            ("publisher_posted_date", "2026-10-16"),
            ("original_text_sha256", "2" * 64),
            ("original_title_sha256", "2" * 64),
            ("original_hwpx_sha256", "2" * 64),
            ("publisher_html_sha256", "2" * 64),
            ("canonical_official_url", hist.URL + "&other=1"),
        ):
            with self.subTest(row_field=field):
                p = packet()
                p["records"][0][field] = value
                p["records"][0]["candidate_version_sha256"] = b.version_hash(p["records"][0])
                with self.assertRaises(b.DAPABridgeHold):
                    b.sign(p, KEY)

    def test_signed_metadata_cannot_carry_original_or_analysis(self):
        p = packet()
        for forbidden in ("title_original", "text_original", "hwpx", "media",
                          "summary_english", "translation_english"):
            altered = copy.deepcopy(p)
            altered["records"][0][forbidden] = "DO NOT EXPORT"
            with self.assertRaises(b.DAPABridgeHold):
                b.sign(altered, KEY)
        blob = b.canonical(p).decode("utf-8")
        for forbidden in ("title_original", "text_original", "download.do",
                          "summary_english", "translation_english"):
            self.assertNotIn(forbidden, blob)

    def test_modified_packet_or_wrong_key_fails_verification(self):
        p = packet()
        mac = b.sign(p, KEY)
        p["historical_manifest_sha256"] = "d" * 64
        with self.assertRaises(b.DAPABridgeHold):
            b.verify_signed_packet(p, mac, KEY)
        with self.assertRaises(b.DAPABridgeHold):
            b.verify_signed_packet(packet(), mac, "other-test-key-" + "X" * 40)

    def test_unreviewed_directory_cannot_export(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(b.DAPABridgeHold):
                hist.export_from_private_checkout(root)

    def test_accidental_original_title_publication_policy_hold(self):
        with patch("core.korea_dapa_private_to_production.read_policy") as policy:
            policy.return_value = {
                "source_family": "kr_policy_dapa_releases",
                "automatic_admission_of_verified_link_metadata": True,
                "public_fields": ["canonical_official_url", "publisher_posted_date",
                                  "official_issuer", "official_republisher", "source_identity"],
                "publish_original_korean_titles": True,
                "publish_original_text": False, "publish_document_media": False,
                "publish_translations_or_analysis": False, "publish_to_model_or_email": False}
            with self.assertRaises(b.DAPABridgeHold):
                b.sign(packet(), KEY)


if __name__ == "__main__":
    unittest.main()
