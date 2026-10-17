"""Synthetic no-network checks for Korean DAPA original audit."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.audit_dapa_hwpx import AuditHold, audit


def sample(include_table=False):
    b = io.BytesIO()
    xml = "<root><p><run><t>첫 문단</t></run></p>"
    if include_table:
        xml += "<tbl><tr><tc><p><run><t>표의 내용</t></run></p></tc></tr></tbl>"
    xml += "</root>"
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("Contents/section0.xml", xml)
        z.writestr("version.xml", "<version/>")
    return b.getvalue()


class TestDapaHWPXStructureAudit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "original.hwpx"
        self.path.write_bytes(sample(include_table=True))
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_pinned_original_detects_tables_but_cannot_approve_publication(self):
        result = audit(self.path, self.digest, len(self.path.read_bytes()))
        self.assertTrue(result["offline_only"])
        self.assertEqual(result["structure"]["tables"], 1)
        self.assertEqual(result["structure"]["table_cells"], 1)
        self.assertEqual(result["structure"]["paragraphs"], 2)
        self.assertEqual(result["text_characters"], len("첫 문단\n표의 내용"))
        self.assertTrue(result["requires_human_table_and_reading_order_review"])
        self.assertFalse(result["korean_semantic_review_approved"])
        self.assertFalse(result["source_use_or_publication_approved"])
        self.assertFalse(result["automated_production_admission_approved"])
        self.assertNotIn("첫 문단", json.dumps(result, ensure_ascii=False))

    def test_wrong_hash_size_count_and_symlink_are_held(self):
        with self.assertRaisesRegex(AuditHold, "sha256_mismatch"):
            audit(self.path, "f" * 64)
        with self.assertRaisesRegex(AuditHold, "byte_count_mismatch"):
            audit(self.path, self.digest, 1)
        with self.assertRaisesRegex(AuditHold, "character_count_mismatch"):
            audit(self.path, self.digest, expected_characters=99)
        other = Path(self.temp.name) / "symlink.hwpx"
        other.symlink_to(self.path)
        with self.assertRaisesRegex(AuditHold, "ordinary_absolute_local_file_required"):
            audit(other, self.digest)

    def test_fake_zip_cannot_claim_real_original(self):
        self.path.write_bytes(b"not-an-HWPX")
        with self.assertRaisesRegex(AuditHold, "invalid_hwpx"):
            audit(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_foreign_xml_entity_disallowed(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("Contents/section0.xml",
                       '<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///private">]>'
                       '<root><p><run><t>&xxe;</t></run></p></root>')
        self.path.write_bytes(b.getvalue())
        with self.assertRaisesRegex(AuditHold, "xml_external_entities_refused"):
            audit(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
