"""Synthetic no-network checks for the DAPA original-to-record candidate.

All Korean text here is invented for the test; no genuine release is used.
"""
import contextlib
import hashlib
import io
import json
import os
import sqlite3
import stat
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from core.korea_dapa_record_candidate import (
    CandidateHold, build_candidate, write_private_input)
from scripts import build_dapa_record_candidate as cli
from tests.test_korea_dapa_archived_kogl_replay import (
    DOC_URL, body_block, files_block, entry, page as page_html)

NEWS_ID = "123456789"
IDENTITY = "korea-dapa-policy:" + NEWS_ID
LEAD = "방위사업청(청장 가상인)은 10월 28일(수) 가상 사업 회의를 열었다고 밝혔다."
TITLE = "가상 사업 회의 개최 결과 공개"


def para(text):
    return f"<p><run><t>{text}</t></run></p>"


def table(*cells):
    return "<tbl><tr>" + "".join(f"<tc>{c}</tc>" for c in cells) + "</tr></tbl>"


def contact(label=None):
    cells = [para("담당 부서"), para("가상정책과"), para("책임자"),
             para("과장 홍길동"), para("(02-000-0000)")]
    if label:
        cells += [para(label)]
    return table(*cells)


def release(headline=("가상 사업 회의", "개최 결과 공개"), lead=LEAD,
            body=("회의에서는 가상 계획을 점검했다.",
                  "가상 관계자는 “계획을 계속 점검하겠다”고 말했다."),
            embargo="배포 즉시", contacts=None, extra_after_body="",
            trailing="<pic/>"):
    pic = "<pic/>"
    xml = "<root>"
    xml += table(pic, para("보도자료"), pic)
    xml += table(para("보도시점"), para(embargo), para("배포"),
                 para("2026.10.28.(수) 08:00"))
    xml += table("".join(para(h) for h in headline), para("- 가상 부제"))
    xml += "".join(para(x) for x in (lead,) + tuple(body))
    xml += extra_after_body
    xml += contacts if contacts is not None else contact()
    if trailing is not None:
        xml += table(trailing)
    xml += "</root>"
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("Contents/section0.xml", xml)
    return b.getvalue()


def lines_of(raw):
    from scripts.audit_dapa_hwpx import located_items
    from xml.etree import ElementTree as ET
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        tree = ET.fromstring(z.read("Contents/section0.xml"))
    return "\n".join(x[1] for x in located_items(tree) if x[0] == "text")


class RecordCandidateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        os.chmod(self.root, 0o700)

    def fixture(self, raw=None, title=TITLE, db_text=None, doc_sha=None,
                identity=IDENTITY, capture_sha=None, document_url=DOC_URL):
        raw = raw if raw is not None else release()
        capture = self.root / "page.bin"
        if not capture.exists():
            capture.write_bytes(page_html(
                url="https://www.korea.kr/briefing/pressReleaseView.do?newsId="
                    + identity.split(":")[-1]))
        if capture_sha is None:
            capture_sha = hashlib.sha256(capture.read_bytes()).hexdigest()
        hwpx = self.root / "original.hwpx"
        hwpx.write_bytes(raw)
        text = db_text if db_text is not None else lines_of(raw)
        sha = hashlib.sha256(text.encode()).hexdigest()
        meta = {"source_identity": identity, "issuer": "방위사업청",
                "publisher_text_license_notice": "KOGL_type_0_text_notice_only",
                "document_url": document_url,
                "content_sha256": sha, "capture_sha256": capture_sha,
                "document_capture_sha256":
                    doc_sha or hashlib.sha256(raw).hexdigest()}
        db = self.root / "shadow.db"
        if db.exists():
            db.unlink()
        con = sqlite3.connect(db)
        con.executescript(
            "create table shadow_records (source_identity text primary key,"
            " url text, source_slug text, title_original text,"
            " text_original text, published_date text, language_tag text,"
            " metadata_json text, content_sha256 text, capture_sha256 text,"
            " first_seen_run text); create table shadow_meta (desk text);"
            " insert into shadow_meta values ('korea_dapa');")
        con.execute("insert into shadow_records values (?,?,?,?,?,?,?,?,?,?,?)", (
            identity,
            "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
            + identity.split(":")[1],
            "kr_policy_dapa_releases", title, text, "2026-10-28", "ko",
            json.dumps(meta, ensure_ascii=False), sha, capture_sha, "12345678-1"))
        con.commit()
        con.close()
        return db, hashlib.sha256(db.read_bytes()).hexdigest(), hwpx

    def build(self, *args, as_of=None, **kwargs):
        db, sha, hwpx = self.fixture(*args, **kwargs)
        return build_candidate(db, sha, IDENTITY, hwpx, as_of,
                               self.root / "page.bin")

    def test_sole_issuer_release_becomes_private_candidate_only(self):
        receipt, paragraphs = self.build()
        self.assertEqual(receipt["status"], "CANDIDATE", receipt["reason_codes"])
        self.assertTrue(receipt["issuer_resolution"]["sole_issuer_structurally_confirmed"])
        self.assertEqual([p["role"] for p in receipt["selection"]["paragraphs"]],
                         ["lead", "body", "quotation_attribution_requires_review"])
        self.assertTrue(receipt["selection"]["headline_matches_db_title_exactly"])
        for flag in ("model_input_authorized", "public_component_authorized",
                     "korean_semantic_review_approved", "publication_approved",
                     "original_or_text_exported"):
            self.assertIs(receipt[flag], False)
        public = json.dumps(receipt, ensure_ascii=False)
        for secret in ("가상", "홍길동", "02-000"):
            self.assertNotIn(secret, public)
        self.assertEqual([p["text"] for p in paragraphs][0], LEAD)
        dest = self.root / "candidate.json"
        write_private_input(dest, receipt, paragraphs)
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)
        stored = json.loads(dest.read_text())
        self.assertNotIn("홍길동", json.dumps(stored, ensure_ascii=False))
        self.assertIs(stored["model_input_authorized"], False)
        with self.assertRaisesRegex(CandidateHold, "new_file"):
            write_private_input(dest, receipt, paragraphs)

    def test_pinned_db_identity_and_original_integrity(self):
        db, sha, hwpx = self.fixture()
        with self.assertRaisesRegex(CandidateHold, "db_sha256_mismatch"):
            build_candidate(db, "f" * 64, IDENTITY, hwpx)
        with self.assertRaisesRegex(CandidateHold, "not_in_pinned_db"):
            build_candidate(db, sha, "korea-dapa-policy:123456780", hwpx)
        with self.assertRaisesRegex(CandidateHold, "refused_orphan"):
            build_candidate(db, sha, "korea-dapa-policy:156787071", hwpx)
        with self.assertRaisesRegex(CandidateHold, "sha256_mismatch"):
            self.build(doc_sha="e" * 64)
        with self.assertRaisesRegex(CandidateHold, "does_not_match_pinned_row"):
            self.build(db_text=lines_of(release()).replace("점검했다", "확인했다"))

    def test_joint_release_signals_hold(self):
        joint = "방위사업청(청장 가상인)과 가상기관(기관장 가상인)은 10월 28일(수) 회의를 열었다."
        two = contact()[:-len("</tr></tbl>")] + "<tc>" + para("담당 부서") + "</tc></tr></tbl>"
        receipt, paragraphs = self.build(release(lead=joint, contacts=two))
        self.assertEqual(receipt["status"], "HOLD")
        self.assertIsNone(paragraphs)
        self.assertEqual(receipt["issuer_resolution"]["reasons"],
                         ["multiple_responsible_department_blocks",
                          "joint_issuer_lead_sentence"])
        receipt, _ = self.build(release(contacts=contact("(가상기관)")))
        self.assertIn("issuer:agency_label_cell_in_contact_block", receipt["reason_codes"])
        with self.assertRaisesRegex(CandidateHold, "requires_candidate"):
            write_private_input(self.root / "held.json", receipt, None)

    def test_joint_hold_never_reports_accepted_prose_basis(self):
        joint = "방위사업청(청장 가상인)과 가상기관(기관장 가상인)은 10월 28일(수) 회의를 열었다."
        receipt, _ = self.build(release(lead=joint))
        self.assertEqual(receipt["status"], "HOLD")
        self.assertEqual(receipt["rights_basis"]["hwpx_attachment_prose"],
                         "held_pending_clean_candidate")

    def test_joint_release_masthead_is_not_a_dapa_template(self):
        raw = release()
        joint = zipfile.ZipFile(io.BytesIO(raw)).read("Contents/section0.xml") \
            .decode().replace("보도자료", "공동보도자료", 1)
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("Contents/section0.xml", joint)
        with self.assertRaisesRegex(CandidateHold, "joint_release_masthead"):
            self.build(b.getvalue())

    def test_collector_document_url_drift_holds(self):
        with self.assertRaisesRegex(CandidateHold, "db_row_identity_or_provenance_drift"):
            self.build(document_url="https://example.org/download?fileId=1")

    def test_page_binding_failures_hold_without_private_prose(self):
        url = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + NEWS_ID
        cases = (
            (page_html(url=url, files=files_block(entry("999999", "다른.hwpx"))),
             "page_binding:document_url_not_listed_on_page"),
            (page_html(url=url, body=body_block(inner="<p>가상 본문</p>")),
             "page_binding:article_body_form_changed"),
            (page_html(url=url, body=body_block(remark=None)),
             "page_binding:dapa_reprint_remark_missing_or_changed"))
        for raw, code in cases:
            with self.subTest(code=code):
                cap = self.root / "page.bin"
                cap.write_bytes(raw)
                db, sha, hwpx = self.fixture(
                    capture_sha=hashlib.sha256(raw).hexdigest())
                receipt, paragraphs = build_candidate(db, sha, IDENTITY, hwpx,
                                                      None, cap)
                self.assertEqual(receipt["status"], "HOLD")
                self.assertIn(code, receipt["reason_codes"])
                self.assertIsNone(paragraphs)
                self.assertIsNotNone(receipt["license_mark_replay"])
                self.assertEqual(receipt["rights_basis"]["hwpx_attachment_prose"],
                                 "held_pending_clean_candidate")
                self.assertNotIn("가상", json.dumps(receipt, ensure_ascii=False))

    def test_unrecognized_template_shapes_hold(self):
        for raw, reason in (
                (release(extra_after_body=table(para("가상 표"))), "unrecognized"),
                (release(trailing=para("연락처 뒤 문장")), "trailing_text"),
                (release(contacts=table(para("가상 연락"))), "contact_block")):
            with self.subTest(reason=reason), \
                    self.assertRaisesRegex(CandidateHold, reason):
                self.build(raw)
        raw = release(trailing=None)
        self.assertEqual(self.build(raw)[0]["status"], "CANDIDATE")

    def test_headline_dates_contacts_and_screen_hold(self):
        cases = (
            ({"raw": release(headline=("가상‧사업 회의", "개최 결과 공개")),
              "title": "가상·사업 회의 개최 결과 공개"}, "headline_punctuation_variant"),
            ({"title": "다른 제목"}, "headline_title_mismatch"),
            ({"raw": release(lead=LEAD.replace("28일(수)", "27일(화)"))},
             "lead_date_mismatch"),
            ({"raw": release(body=("문의는 (02-111-2222)로 하면 된다.",))},
             "contact_detail_in_selected_prose"),
            ({"raw": release(body=("회의에서는 가상 계획을 점검했다.",
                                     "ⓒ 가상 통신사 기사를 인용했다."))},
             "text_screen_indicator_present"),
        )
        for kwargs, reason in cases:
            with self.subTest(reason=reason):
                receipt, paragraphs = self.build(**kwargs)
                self.assertEqual(receipt["status"], "HOLD")
                self.assertIn(reason, receipt["reason_codes"])
                self.assertIsNone(paragraphs)
                self.assertEqual(receipt["rights_basis"]["hwpx_attachment_prose"],
                                 "held_pending_clean_candidate")

    def test_embargo_must_have_elapsed(self):
        raw = release(embargo="2026.10.28.(수) 16:00")
        before = datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)
        after = datetime(2026, 10, 28, 7, 0, tzinfo=timezone.utc)
        self.assertIn("embargo_not_elapsed",
                      self.build(raw, as_of=before)[0]["reason_codes"])
        self.assertEqual(self.build(raw, as_of=after)[0]["status"], "CANDIDATE")

    def test_page_capture_replays_type0_mark_into_receipt(self):
        raw = page_html(url="https://www.korea.kr/briefing/pressReleaseView.do"
                            "?newsId=" + NEWS_ID)
        cap = self.root / "page.bin"
        cap.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        db, sha, hwpx = self.fixture(capture_sha=digest)
        receipt, _ = build_candidate(db, sha, IDENTITY, hwpx, None, cap)
        self.assertEqual(receipt["status"], "CANDIDATE", receipt["reason_codes"])
        self.assertEqual(receipt["license_mark_replay"]["mark"], "KOGL_TYPE_0_TEXT")
        self.assertEqual(receipt["rights_basis"]["article_page_text"],
                         "kogl_type0_page_notice_replayed")
        self.assertEqual(receipt["rights_basis"]["hwpx_attachment_prose"],
                         "interpretation_accepted_by_owner_option_a")
        self.assertIs(receipt["model_input_authorized"], False)
        self.assertNotIn("가상", json.dumps(receipt, ensure_ascii=False))
        # No preserved page means no licensed prose candidate or private export.
        bare, private = build_candidate(db, sha, IDENTITY, hwpx)
        self.assertEqual(bare["status"], "HOLD")
        self.assertIsNone(private)
        self.assertIsNone(bare["license_mark_replay"])
        self.assertIn("license_mark:preserved_page_capture_required",
                      bare["reason_codes"])
        self.assertIn("not_replayed", bare["rights_basis"]["article_page_text"])
        self.assertEqual(bare["rights_basis"]["hwpx_attachment_prose"],
                         "held_pending_clean_candidate")
        with self.assertRaisesRegex(CandidateHold, "requires_candidate"):
            write_private_input(self.root / "unqualified.json", bare, private)

    def test_page_capture_hash_or_mark_failure_holds(self):
        raw = page_html(url="https://www.korea.kr/briefing/pressReleaseView.do"
                            "?newsId=" + NEWS_ID)
        cap = self.root / "page.bin"
        cap.write_bytes(raw)
        db, sha, hwpx = self.fixture(capture_sha="d" * 64)
        receipt, paragraphs = build_candidate(db, sha, IDENTITY, hwpx, None, cap)
        self.assertEqual(receipt["status"], "HOLD")
        self.assertIn("license_mark:publisher_html_capture_hash_mismatch",
                      receipt["reason_codes"])
        self.assertIsNone(paragraphs)
        bad = page_html(url="https://www.korea.kr/briefing/pressReleaseView.do"
                            "?newsId=" + NEWS_ID, media="자유 이용")
        cap.write_bytes(bad)
        db, sha, hwpx = self.fixture(capture_sha=hashlib.sha256(bad).hexdigest())
        receipt, _ = build_candidate(db, sha, IDENTITY, hwpx, None, cap)
        self.assertIn("license_mark:nontext_third_party_exception_notice_missing",
                      receipt["reason_codes"])

    def test_cli_accepts_relative_page_capture(self):
        raw = page_html(url="https://www.korea.kr/briefing/pressReleaseView.do"
                            "?newsId=" + NEWS_ID)
        (self.root / "page.bin").write_bytes(raw)
        db, sha, hwpx = self.fixture(capture_sha=hashlib.sha256(raw).hexdigest())
        argv = ["--db", str(db), "--db-sha256", sha, "--source-identity",
                IDENTITY, "--hwpx", str(hwpx), "--page-capture", "page.bin"]
        before = os.getcwd()
        os.chdir(self.root)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(argv)
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("kogl_type0_page_notice_replayed", out.getvalue())
            # A symlinked capture is still refused after the path is absolutised.
            (self.root / "link.bin").symlink_to(self.root / "page.bin")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(argv[:-1] + ["link.bin"])
            self.assertEqual(code, 3, out.getvalue())
            reasons = json.loads(out.getvalue())["reason_codes"]
            self.assertTrue(any(r.startswith("license_mark:") for r in reasons),
                            reasons)
            self.assertIsNone(json.loads(out.getvalue())["license_mark_replay"])
        finally:
            os.chdir(before)

    def test_cli_prints_no_prose_and_signals_status(self):
        db, sha, hwpx = self.fixture()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--db", str(db), "--db-sha256", sha,
                             "--source-identity", IDENTITY, "--hwpx", str(hwpx),
                             "--private-output", str(self.root / "p.json")])
        self.assertEqual(code, 3)
        self.assertNotIn("가상", out.getvalue())
        self.assertIn("license_mark:preserved_page_capture_required",
                      json.loads(out.getvalue())["reason_codes"])
        self.assertFalse((self.root / "p.json").exists())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--db", str(db), "--db-sha256", sha,
                             "--source-identity", IDENTITY, "--hwpx", str(hwpx),
                             "--page-capture", str(self.root / "page.bin"),
                             "--private-output", str(self.root / "p.json")])
        self.assertEqual(code, 0)
        self.assertNotIn("가상", out.getvalue())
        self.assertTrue((self.root / "p.json").exists())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--db", str(db), "--db-sha256", "0" * 64,
                             "--source-identity", IDENTITY, "--hwpx", str(hwpx)])
        self.assertEqual(code, 2)
        self.assertIn("db_sha256_mismatch", out.getvalue())


if __name__ == "__main__":
    unittest.main()
