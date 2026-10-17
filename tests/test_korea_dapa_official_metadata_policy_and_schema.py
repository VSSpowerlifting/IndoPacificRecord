"""Synthetic Korea DAPA publication-scope and safe existing-MND-schema expansion."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.korea_dapa_official_metadata_policy import (
    DAPAPolicyHold, EXPECTED, read_policy,
)
from migrations.versions import (
    m0008_korea_official_source_metadata as old,
    m0011_korea_dapa_metadata_source_separation as new,
)

CANONICAL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
MND_ID = "korea-policy:156785286"
DAPA_ID = "korea-dapa-policy:156785254"


def sample(ident, issuer, *, scope="official_link_only"):
    suffix = ident.split(":")[1]
    return (ident, CANONICAL + suffix, "2026-10-15",
            "a" * 40, "b" * 64, "c" * 64, "d" * 64,
            "e" * 64, "f" * 64, "0" * 64,
            issuer, "kr_policy_briefing", "ko", "B", "syndicated",
            scope, "2026-10-17T20:00:00Z", "2026-10-17T20:00:00Z")


class DapaSourceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        old.up(self.conn)
        self.conn.execute("INSERT INTO korea_official_source_records VALUES "
                          "(" + ",".join("?" for _ in range(18)) + ")",
                          sample(MND_ID, "kr_mnd"))
        self.mnd_before = self.conn.execute(
            "SELECT * FROM korea_official_source_records"
        ).fetchall()

    def test_existing_mnd_rows_and_index_survive_upgrade(self):
        new.up(self.conn)
        self.assertEqual(self.mnd_before, self.conn.execute(
            "SELECT * FROM korea_official_source_records"
        ).fetchall())
        self.assertTrue(new.is_already_applied(self.conn))
        new.up(self.conn)
        self.assertEqual(self.mnd_before, self.conn.execute(
            "SELECT * FROM korea_official_source_records"
        ).fetchall())
        self.assertIsNotNone(self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            ("idx_korea_official_source_date",)
        ).fetchone())
        self.assertEqual(self.conn.execute("PRAGMA quick_check").fetchone(), ("ok",))

    def test_dapa_distinct_issuer_and_source_identity_can_be_held(self):
        new.up(self.conn)
        row = sample(DAPA_ID, "kr_dapa", scope="held")
        self.conn.execute("INSERT INTO korea_official_source_records VALUES "
                          "(" + ",".join("?" for _ in range(18)) + ")", row)
        self.assertEqual(self.conn.execute(
            "SELECT official_issuer, public_scope FROM korea_official_source_records "
            "WHERE source_identity=?", (DAPA_ID,)
        ).fetchone(), ("kr_dapa", "held"))
        self.assertEqual(self.conn.execute(
            "SELECT official_issuer FROM korea_official_source_records "
            "WHERE source_identity=?", (MND_ID,)
        ).fetchone()[0], "kr_mnd")
        self.assertNotIn("text_original", old.EXPECTED_COLUMNS)
        self.assertNotIn("title_original", old.EXPECTED_COLUMNS)
        self.assertNotIn("document_bytes", old.EXPECTED_COLUMNS)

    def test_wrong_dapa_as_mnd_and_invalid_cross_source_urls_refused(self):
        new.up(self.conn)
        good = sample(DAPA_ID, "kr_dapa", scope="held")
        variants = [
            tuple(list(good[:10]) + ["kr_mnd"] + list(good[11:])),
            tuple([MND_ID] + list(good[1:])),
            tuple([DAPA_ID, CANONICAL + "156785255"] + list(good[2:])),
            tuple([DAPA_ID, "http://www.korea.kr/briefing/pressReleaseView.do?newsId=156785254"] + list(good[2:])),
            tuple([DAPA_ID, CANONICAL + "156785254#fragment"] + list(good[2:])),
        ]
        for row in variants:
            with self.subTest(row=row[:2]), self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute("INSERT INTO korea_official_source_records VALUES "
                                  "(" + ",".join("?" for _ in range(18)) + ")", row)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 1)

    def test_same_news_id_cannot_be_both_mnd_and_dapa(self):
        new.up(self.conn)
        collision = sample("korea-dapa-policy:156785286", "kr_dapa")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO korea_official_source_records VALUES "
                              "(" + ",".join("?" for _ in range(18)) + ")", collision)

    def test_upgrading_empty_or_wrong_schema_fails_closed(self):
        with sqlite3.connect(":memory:") as conn:
            with self.assertRaisesRegex(ValueError, "must exist"):
                new.up(conn)
        with sqlite3.connect(":memory:") as conn:
            conn.execute("CREATE TABLE korea_official_source_records (id INTEGER)")
            with self.assertRaisesRegex(ValueError, "schema drift"):
                new.up(conn)


class DapaPolicyTests(unittest.TestCase):
    def test_exact_owner_scope_and_mnd_separate(self):
        policy = read_policy()
        self.assertEqual(policy, EXPECTED)
        self.assertEqual(policy["issuer"], "kr_dapa")
        self.assertEqual(policy["government_portal_issuer_code"], "B00008")
        self.assertTrue(policy["automatic_admission_of_verified_link_metadata"])
        self.assertTrue(policy["private_original_custody_required"])
        for key in ("publish_original_korean_titles", "publish_original_text",
                    "publish_document_media", "publish_translations_or_analysis",
                    "publish_to_model_or_email", "rights_to_rehost_original_implied",
                    "retrospective_approval_of_unverified_articles",
                    "desk_launch_or_collector_schedule_authorized_by_policy"):
            self.assertIs(policy[key], False, key)
        self.assertEqual(len(policy["public_fields"]), 5)

    def test_untrusted_or_scope_expanding_policy_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            altered = Path(folder) / "policy.json"
            altered.write_text('{"source_family":"anything"}')
            with self.assertRaises(DAPAPolicyHold):
                read_policy(altered)
        with patch("core.korea_dapa_official_metadata_policy.POLICY_PATH", Path("/invalid/path")):
            with self.assertRaises(DAPAPolicyHold):
                read_policy()


if __name__ == "__main__":
    unittest.main()
