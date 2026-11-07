"""Synthetic no-network checks for the DAPA KOGL Type 0 page-mark replay.

The wrapper markup mirrors the structure of the Korea Policy Briefing article
licence block; every article value here is invented and no capture is used.
"""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from core.korea_dapa_archived_kogl_replay import (
    MarkHold, inspect_captured_type0_mark, inspect_page_binding,
    replay_capture_file)

URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=123456789"
TEXT_MARK = "텍스트에 한하여 공공누리 제0유형(자유이용)의 조건"
MEDIA = ("단, 텍스트를 제외한 사진·이미지·일러스트·동영상 등 자료의 대부분은 "
         "정책브리핑이 저작권을 보유하고 있지 않으므로, 이용 전 해당 저작권자의 "
         "허락을 반드시 받으셔야 합니다.")
BADGE = ('<a href="https://www.kogl.or.kr/info/license.do">'
         '<img alt="공공누리 공공저작물 자유이용허락 0유형 자유이용" '
         'src="/images/v5/common/open_type_00.png"/></a>')


DOC_URL = "https://www.korea.kr/common/download.do?fileId=123456&tblKey=GMN"
REMARK = "“이 자료는 방위사업청의 보도자료를 전재하여 제공함을 알려드립니다.”"
FRAME = ('<iframe id="content_press" src="/docViewer/iframe_skin/doc.html?fn='
         + "a" * 32 + '&rs=/docViewer/result/2026.10/28/a"></iframe>')


def entry(file_id="123456", name="가상 보도자료.hwpx"):
    return (f'<p><span><a href="/common/download.do?fileId={file_id}&amp;tblKey=GMN">'
            f'{name}</a></span><span><a href="#">바로보기</a></span></p>')


def body_block(inner=FRAME, remark=REMARK):
    remark_html = f'<p class="remark">{remark}</p>' if remark is not None else ""
    return (f'<div class="article_body"><div class="view_cont">{inner}'
            f'{remark_html}</div></div>')


def files_block(*entries):
    entries = entries or (entry(), entry("123457", "가상 보도자료.pdf"))
    return f'<div class="filedown"><dl><dd>{"".join(entries)}</dd></dl></div>'


def page(url=URL, mark=TEXT_MARK, badge=BADGE, media=MEDIA, wrappers=1,
         canonicals=1, extra_in_wrapper="", body=None, files=None):
    block = (
        '<div class="kogl_wrap"><div class="kogl"><div class="guide">'
        f'<div class="type">{badge}<span>이 자료는 <strong>{mark}</strong>에 따라 '
        '이용할 수 있습니다.</span></div>'
        f'<div class="info"><p>{media}</p>{extra_in_wrapper}'
        '<div class="btn"><a href="/guide/copyRight.do">저작권정책</a></div>'
        '</div></div></div></div>')
    link = f'<link rel="canonical" href="{url}"/>' * canonicals
    body = body_block() if body is None else body
    files = files_block() if files is None else files
    return (f"<html><head>{link}</head><body>{body}{files}"
            + block * wrappers + "</body></html>").encode()


class Type0MarkReplayTest(unittest.TestCase):
    def hold(self, html, reason, url=URL):
        with self.assertRaisesRegex(MarkHold, reason):
            inspect_captured_type0_mark(html, url)

    def test_type0_text_mark_is_proved_with_narrow_scope(self):
        result = inspect_captured_type0_mark(page(), URL)
        self.assertEqual(result["mark"], "KOGL_TYPE_0_TEXT")
        self.assertEqual(result["scope"], "article_text_only")
        for flag in ("attachments_licensed_by_mark", "media_licensed",
                     "issuer_identified_by_mark"):
            self.assertIs(result[flag], False)
        self.assertRegex(result["mark_sha256"], r"^[0-9a-f]{64}$")

    def test_identity_must_match_exactly_one_canonical_link(self):
        self.hold(page(url=URL[:-1] + "0"), "identity_mismatch")
        self.hold(page(canonicals=0), "identity_mismatch")
        self.hold(page(canonicals=2), "identity_mismatch")
        self.hold(page(), "expected_article_url_invalid",
                  url="https://example.org/briefing?newsId=123456789")

    def test_wrapper_must_be_single_and_article_local(self):
        self.hold(page(wrappers=0), "license_wrapper_missing")
        self.hold(page(wrappers=2), "license_wrapper_missing")

    def test_other_kogl_types_and_missing_text_only_marker_hold(self):
        type1 = page(mark="공공누리 제1유형(출처표시)의 조건",
                     badge=BADGE.replace("open_type_00", "open_type_01")
                     .replace("0유형", "1유형"))
        self.hold(type1, "not_marked_kogl_type0_text_only")
        self.hold(page(mark="공공누리 제0유형(자유이용)의 조건"),
                  "not_marked_kogl_type0_text_only")

    def test_badge_must_agree_with_text_and_be_unique(self):
        wrong_src = BADGE.replace("open_type_00", "open_type_01")
        self.hold(page(badge=wrong_src), "badge_conflicts_with_text")
        wrong_alt = BADGE.replace("0유형", "1유형")
        self.hold(page(badge=wrong_alt), "badge_conflicts_with_text")
        self.hold(page(badge=BADGE + BADGE), "badge_conflicts_with_text")
        self.hold(page(badge=""), "badge_conflicts_with_text")

    def test_nontext_exclusion_notice_is_required(self):
        self.hold(page(media="이 자료는 자유롭게 이용할 수 있습니다."),
                  "notice_missing")
        self.hold(page(media="사진·이미지·일러스트·동영상은 자유롭게 이용할 수 있습니다."),
                  "notice_missing")

    def test_conflicting_type_label_in_wrapper_holds(self):
        extra = "<p>이 자료의 일부는 공공누리 제2유형 조건입니다.</p>"
        self.hold(page(extra_in_wrapper=extra), "conflicting_article_license")

    def test_input_bounds_and_encoding(self):
        self.hold(b"", "missing_or_oversize")
        self.hold(b"\xff\xfe\xfa", "not_utf8")
        with self.assertRaisesRegex(MarkHold, "missing_or_oversize"):
            inspect_captured_type0_mark("text", URL)

    def test_errors_never_carry_source_text(self):
        try:
            inspect_captured_type0_mark(page(media="가상 기사 본문"), URL)
        except MarkHold as exc:
            self.assertNotIn("가상", str(exc))
            self.assertRegex(str(exc), r"^[a-z0-9_]+$")

    def test_capture_file_is_hash_bound_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = page()
            path = Path(tmp) / "capture.bin"
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            result = replay_capture_file(path, digest, URL)
            self.assertEqual(result["capture_sha256"], digest)
            self.assertEqual(result["mark"], "KOGL_TYPE_0_TEXT")
            with self.assertRaisesRegex(MarkHold, "capture_hash_mismatch"):
                replay_capture_file(path, "0" * 64, URL)
            with self.assertRaisesRegex(MarkHold, "hash_invalid"):
                replay_capture_file(path, "xyz", URL)
            with self.assertRaisesRegex(MarkHold, "missing_or_oversize"):
                replay_capture_file(Path(tmp) / "absent.bin", digest, URL)
            link = Path(tmp) / "link.bin"
            os.symlink(path, link)
            with self.assertRaisesRegex(MarkHold, "missing_or_oversize"):
                replay_capture_file(link, digest, URL)


class PageBindingTest(unittest.TestCase):
    def holds(self, html, url=DOC_URL):
        return inspect_page_binding(html, url)["holds"]

    def test_viewer_only_page_binds_listed_hwpx(self):
        result = inspect_page_binding(page(), DOC_URL)
        self.assertEqual(result["holds"], [])
        self.assertEqual(result["hwpx_file_id"], "123456")
        self.assertIs(result["hwpx_matches_collector_document_url"], True)
        self.assertEqual(result["other_attachment_count"], 1)
        self.assertEqual(result["article_body_form"], "document_viewer_frame_only")
        self.assertIs(result["dapa_reprint_remark_present"], True)
        for flag in ("inline_article_prose_present", "viewer_conversion_preserved",
                     "viewer_source_attachment_identified",
                     "page_text_hwpx_equivalence_verifiable_offline",
                     "remark_proves_sole_issuer"):
            self.assertIs(result[flag], False, flag)

    def test_collector_url_must_be_valid_and_listed(self):
        self.assertIn("document_url_invalid",
                      self.holds(page(), "https://example.org/a.hwpx"))
        self.assertIn("document_url_invalid", self.holds(page(), None))
        self.assertEqual(self.holds(page(), DOC_URL.replace("123456", "999999")),
                         ["document_url_not_listed_on_page"])

    def test_attachment_list_shape_holds(self):
        self.assertEqual(self.holds(page(files="")),
                         ["attachment_list_missing_or_ambiguous"])
        self.assertIn("attachment_list_missing_or_ambiguous",
                      self.holds(page(files=files_block() * 2)))
        self.assertEqual(self.holds(page(files=files_block(entry("123457", "a.pdf")))),
                         ["hwpx_attachment_missing_or_ambiguous"])
        self.assertEqual(self.holds(page(files=files_block(
            entry(), entry("123458", "b.hwpx")))),
            ["hwpx_attachment_missing_or_ambiguous"])
        odd = '<p><span><a href="https://example.org/x.hwpx">x.hwpx</a></span></p>'
        self.assertIn("attachment_entry_not_recognized",
                      self.holds(page(files=files_block(entry(), odd))))

    def test_article_body_form_and_inline_prose_hold(self):
        self.assertIn("article_body_form_changed",
                      self.holds(page(body=body_block(inner=""))))
        self.assertIn("article_body_form_changed", self.holds(page(
            body=body_block(inner=FRAME.replace("content_press", "other")))))
        self.assertIn("article_body_form_changed", self.holds(page(body="")))
        prose = self.holds(page(body=body_block(inner=FRAME + "<p>가상 본문</p>")))
        self.assertEqual(prose,
                         ["inline_article_prose_present_requires_equivalence_review"])

    def test_reprint_remark_must_be_exact_and_single(self):
        self.assertEqual(self.holds(page(body=body_block(remark=None))),
                         ["dapa_reprint_remark_missing_or_changed"])
        changed = REMARK.replace("방위사업청", "가상기관")
        self.assertIn("dapa_reprint_remark_missing_or_changed",
                      self.holds(page(body=body_block(remark=changed))))

    def test_undecodable_bytes_hold_without_raising(self):
        holds = self.holds(b"\xff\xfe")
        self.assertIn("attachment_list_missing_or_ambiguous", holds)
        self.assertIn("article_body_form_changed", holds)

    def test_binding_carries_no_source_text(self):
        import json
        text = json.dumps(inspect_page_binding(page(), DOC_URL), ensure_ascii=False)
        self.assertNotIn("가상", text)
        self.assertNotIn("방위사업청", text)


if __name__ == "__main__":
    unittest.main()
