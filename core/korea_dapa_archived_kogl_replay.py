"""Read-only replay of the KOGL Type 0 text mark on a preserved DAPA page.

Korea Policy Briefing republishes Defense Acquisition Program Administration
(DAPA) press releases and marks each article's *text* as KOGL Type 0 (free
use). The MND path replays the Type 1 mark in
``core/korea_archived_kogl_replay.py``; that module stays MND/Type 1-bound.
This sibling proves the Type 0 article mark from the exact preserved page
bytes, so the mark applying to a captured version is evidenced rather than
inferred from a collector-recorded label.

It proves only what the page states: article text carries the Type 0 mark and
non-text material is excluded. It does not extend that mark to the linked
HWPX/PDF files, authenticate today's portal policy, identify the issuer, call
a model, or publish anything. Errors are fixed codes, never source text.

``inspect_page_binding`` reads the same hash-bound bytes for what ties the
preserved HWPX to that marked page version: the page must list exactly one
HWPX attachment, equal to the collector's recorded download, and carry the
single DAPA reprint remark. It also records the article-body form. On every
preserved DAPA page the marked article body is only a document-viewer frame
(a conversion of an attachment that is not preserved) plus the remark, so
page-text/HWPX equivalence cannot be verified offline; any change to that
form is held until reviewed. The remark corroborates DAPA as the reprinted
source; joint releases carry the same remark, so it never proves sole issuance.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

MAX_HTML = 10_000_000
HEX = re.compile(r"[0-9a-f]{64}\Z")
URL = re.compile(r"https://www\.korea\.kr/briefing/pressReleaseView\.do\?newsId=[0-9]{9}\Z")
MARK = "텍스트에 한하여 공공누리 제0유형(자유이용)"
BADGE_SRC = "/images/v5/common/open_type_00.png"
MEDIA = "사진·이미지·일러스트·동영상"
SCHEMA = "ipr-dapa-archived-kogl-type0-mark-replay/1"
OTHER_TYPES = ("제1유형", "제2유형", "제3유형", "제4유형")
BINDING_SCHEMA = "ipr-dapa-archived-page-original-binding/1"
DOCUMENT_URL = re.compile(
    r"https://www\.korea\.kr/common/download\.do\?fileId=([0-9]{6,12})&tblKey=GMN\Z")
DOWNLOAD_HREF = re.compile(r"/common/download\.do\?fileId=([0-9]{6,12})&tblKey=GMN\Z")
VIEWER_SRC = re.compile(r"/docViewer/iframe_skin/doc\.html\?fn=[0-9a-f]{32}&rs=/docViewer/result/")
REMARK = "“이 자료는 방위사업청의 보도자료를 전재하여 제공함을 알려드립니다.”"


class MarkHold(ValueError):
    """Fixed codes: never include source text or HTML in exceptions."""


def _need(value, reason):
    if not value:
        raise MarkHold(reason)


def inspect_captured_type0_mark(html_bytes, expected_url):
    """Prove the article-local KOGL Type 0 *text* mark, never file rights."""
    _need(type(expected_url) is str and URL.fullmatch(expected_url) is not None,
          "expected_article_url_invalid")
    _need(type(html_bytes) is bytes and 0 < len(html_bytes) <= MAX_HTML,
          "publisher_html_capture_missing_or_oversize")
    try:
        html_text = html_bytes.decode("utf-8", "strict")
    except UnicodeError:
        raise MarkHold("publisher_html_not_utf8") from None
    soup = BeautifulSoup(html_text, "html.parser")
    canonical = soup.select('link[rel="canonical"]')
    _need(len(canonical) == 1 and canonical[0].get("href") == expected_url,
          "captured_publisher_article_identity_mismatch")
    wrappers = soup.select("div.kogl_wrap")
    _need(len(wrappers) == 1, "article_specific_license_wrapper_missing")
    types = wrappers[0].select(".type")
    _need(len(types) == 1, "article_license_type_ambiguous")
    strong = types[0].select("span strong")
    _need(len(strong) == 1, "article_license_text_marker_missing")
    marked = " ".join(strong[0].get_text(" ", strip=True).split())
    _need(MARK in marked, "article_not_marked_kogl_type0_text_only")
    images = types[0].select("img")
    _need(len(images) == 1 and images[0].get("src") == BADGE_SRC
          and "0유형" in images[0].get("alt", ""),
          "article_license_badge_conflicts_with_text")
    notices = wrappers[0].select(".info p")
    _need(any(MEDIA in n.get_text(" ", strip=True)
              and "허락" in n.get_text(" ", strip=True) for n in notices),
          "nontext_third_party_exception_notice_missing")
    _need(not any(label in wrappers[0].get_text(" ", strip=True)
                  for label in OTHER_TYPES), "conflicting_article_license_markers")
    return {"mark": "KOGL_TYPE_0_TEXT",
            "mark_sha256": hashlib.sha256(marked.encode("utf-8")).hexdigest(),
            "scope": "article_text_only",
            "attachments_licensed_by_mark": False,
            "media_licensed": False,
            "issuer_identified_by_mark": False}


def _flat(node):
    return " ".join(node.get_text(" ", strip=True).split())


def inspect_page_binding(html_bytes, document_url):
    """Bind the collector's HWPX to the marked page; codes and ids only.

    Returns {"holds": [...], ...facts}. Holds name every failed check, so a
    receipt can still be written; the facts carry no source text.
    """
    holds = []
    wanted = DOCUMENT_URL.fullmatch(document_url) if type(document_url) is str else None
    if wanted is None:
        holds.append("document_url_invalid")
    try:
        soup = BeautifulSoup(html_bytes.decode("utf-8", "strict"), "html.parser")
    except (AttributeError, UnicodeError):
        soup = BeautifulSoup("", "html.parser")
    hwpx_ids, other_ids = [], []
    lists = soup.select("div.filedown")
    for entry in (lists[0].select("dd > p") if len(lists) == 1 else []):
        spans = entry.find_all("span", recursive=False)
        links = spans[0].find_all("a") if spans else []
        found = (DOWNLOAD_HREF.fullmatch(links[0].get("href", ""))
                 if len(links) == 1 else None)
        if found is None:
            holds.append("attachment_entry_not_recognized")
        elif _flat(links[0]).lower().endswith(".hwpx"):
            hwpx_ids.append(found[1])
        else:
            other_ids.append(found[1])
    if len(lists) != 1:
        holds.append("attachment_list_missing_or_ambiguous")
    elif len(hwpx_ids) != 1:
        holds.append("hwpx_attachment_missing_or_ambiguous")
    elif wanted is not None and hwpx_ids[0] != wanted[1]:
        holds.append("document_url_not_listed_on_page")
    bodies = soup.select("div.article_body div.view_cont")
    frames = bodies[0].select("iframe") if len(bodies) == 1 else []
    remarks = bodies[0].select("p.remark") if len(bodies) == 1 else []
    inline = ""
    if len(bodies) == 1:
        inline = _flat(bodies[0])
        for remark in remarks:
            inline = inline.replace(_flat(remark), "", 1)
        inline = inline.strip()
    viewer_only = (len(bodies) == 1 and len(frames) == 1
                   and frames[0].get("id") == "content_press"
                   and VIEWER_SRC.match(frames[0].get("src", "")) is not None)
    if not viewer_only:
        holds.append("article_body_form_changed")
    if inline:
        holds.append("inline_article_prose_present_requires_equivalence_review")
    if len(remarks) != 1 or _flat(remarks[0]) != REMARK:
        holds.append("dapa_reprint_remark_missing_or_changed")
    return {
        "schema": BINDING_SCHEMA,
        "holds": holds,
        "hwpx_attachment_listed": len(hwpx_ids) == 1,
        "hwpx_file_id": hwpx_ids[0] if len(hwpx_ids) == 1 else None,
        "hwpx_matches_collector_document_url": (
            len(hwpx_ids) == 1 and wanted is not None and hwpx_ids[0] == wanted[1]),
        "other_attachment_count": len(other_ids),
        "article_body_form": ("document_viewer_frame_only" if viewer_only
                              else "unrecognized"),
        "inline_article_prose_present": bool(inline),
        "viewer_conversion_preserved": False,
        "viewer_source_attachment_identified": False,
        "page_text_hwpx_equivalence_verifiable_offline": False,
        "dapa_reprint_remark_present": len(remarks) == 1
                                       and _flat(remarks[0]) == REMARK,
        "remark_proves_sole_issuer": False,
    }


def read_capture(path, expected_sha256):
    """Return the exact preserved page bytes only if they match the pin."""
    _need(type(expected_sha256) is str and HEX.fullmatch(expected_sha256) is not None,
          "publisher_html_hash_invalid")
    path = Path(path)
    _need(path.is_absolute() and path.is_file() and not path.is_symlink()
          and 0 < path.stat().st_size <= MAX_HTML,
          "publisher_html_capture_missing_or_oversize")
    content = path.read_bytes()
    _need(hashlib.sha256(content).hexdigest() == expected_sha256,
          "publisher_html_capture_hash_mismatch")
    return content


def replay_capture_bytes(content, expected_sha256, expected_url):
    """Replay the mark from bytes already returned by ``read_capture``."""
    result = inspect_captured_type0_mark(content, expected_url)
    result["schema"] = SCHEMA
    result["capture_sha256"] = expected_sha256
    return result


def replay_capture_file(path, expected_sha256, expected_url):
    """Hash-bind one preserved page capture to its pinned digest, then replay."""
    content = read_capture(path, expected_sha256)
    result = inspect_captured_type0_mark(content, expected_url)
    result["schema"] = SCHEMA
    result["capture_sha256"] = expected_sha256
    return result
