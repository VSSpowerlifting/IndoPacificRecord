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


def replay_capture_file(path, expected_sha256, expected_url):
    """Hash-bind one preserved page capture to its pinned digest, then replay."""
    _need(type(expected_sha256) is str and HEX.fullmatch(expected_sha256) is not None,
          "publisher_html_hash_invalid")
    path = Path(path)
    _need(path.is_absolute() and path.is_file() and not path.is_symlink()
          and 0 < path.stat().st_size <= MAX_HTML,
          "publisher_html_capture_missing_or_oversize")
    content = path.read_bytes()
    _need(hashlib.sha256(content).hexdigest() == expected_sha256,
          "publisher_html_capture_hash_mismatch")
    result = inspect_captured_type0_mark(content, expected_url)
    result["schema"] = SCHEMA
    result["capture_sha256"] = expected_sha256
    return result
