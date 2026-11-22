"""
Scraper for Global Times — Military section (环球时报·军事)
https://www.globaltimes.cn/china/military/

Global Times is a CCP-affiliated tabloid published under People's Daily.
Its military coverage is English-language, often more sensational than
official PLA Daily output but useful for tracking official narrative aimed
at international audiences and for triangulating PLA signaling.

URL structure (verified May 2026):
  Listing page:  https://www.globaltimes.cn/china/military/
  Article page:  https://www.globaltimes.cn/page/YYYYMM/{numeric_id}.shtml

Date filtering: the listing's <div class="source_time"> ("By Author  |
YYYY/M/D H:MM:SS") dates a tile; an undated (featured) tile is resolved from
the article's own pub_time. Candidates are filtered on [target-N, target]
(UTC+8 dates). The URL month is not a date gate.

Article structure (verified May 2026):
  Title:  <div class="article_title"> text content
  Date:   <span class="pub_time"> "Published: Nov 20, 2026 11:42 PM" (UTC+8);
          listing tiles use <div class="source_time">
  Body:   <div class="article_content"> → <p> tags (first occurrence only;
          subsequent div.article_content elements are related-article embeds)
"""

import hashlib
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper

_BASE = "https://www.globaltimes.cn"
_LISTING_URL = f"{_BASE}/china/military/"

# Article URL: /page/YYYYMM/ID.shtml. The month in the path is NOT a date gate:
# a manual-dispatch capture on Oct 31 lost two items whose URLs had rolled to
# the next month, and a month match says nothing about the day.
_ARTICLE_URL_RE = re.compile(
    r"https?://www\.globaltimes\.cn/page/(\d{4})(\d{2})/(\d+)\.shtml$"
)

#: Source-family identifiers for the custody row.
FAMILY = "global_times_mil"

#: Optional private raw-byte store. When set, the exact wire bytes of every
#: custodied article are written here (never to a git-tracked path). No
#: workflow sets it yet; see the PR body for the remaining private wiring.
RAW_CAPTURE_DIR_ENV = "IPR_GT_RAW_CAPTURE_DIR"

#: Bylines naming an agency or institution other than Global Times. Their
#: text is not Global Times' own reporting; public text is held.
_NON_GT_BYLINE_RE = re.compile(
    r"\b(xinhua|mnd|ministry of (national )?defen[cs]e|china military|"
    r"cmo|pla daily|people'?s daily|cctv|cgtn|cmg|reuters|afp|ap|"
    r"agency|agencies|associated press)\b", re.IGNORECASE)

_PUB_TIME_RE = re.compile(
    r"Published:\s*([A-Za-z]{3,9})\.?\s+(\d{1,2}),\s*(\d{4})")


class GlobalTimesMilScraper(BaseScraper):
    """Scrapes military articles from the Global Times."""

    #: Read by `adapters.legacy.LegacyScraperAdapter`; `production_window()`
    #: then hands this scraper [target-2, target] instead of one day.
    PRODUCTION_LOOKBACK_DAYS = 2
    ACCEPTS_LOOKBACK = True

    def __init__(self, target_date: Optional[date] = None,
                 lookback_days: int = 0) -> None:
        super().__init__("global_times_mil", target_date=target_date)
        self.lookback_days = max(0, int(lookback_days))
        # url -> (wire bytes, decoded html), live this run only.
        self._captured: dict[str, tuple[bytes, str]] = {}
        self._last_wire: dict[str, bytes] = {}

    # ── Raw capture ───────────────────────────────────────────────────────────

    def _on_response(self, url, resp) -> None:
        self._last_wire[url] = bytes(resp.content)

    def fetch(self, url: str, force_refresh: bool = False):
        """
        Live fetch that keeps the wire bytes. A disk-cache hit would return
        decoded text with no bytes to hash, so article pages always go live;
        a page already fetched this run (undated-tile resolution) is reused so
        discovery and extraction see the same bytes.
        """
        if not _ARTICLE_URL_RE.match(url):
            return super().fetch(url, force_refresh=force_refresh)
        if url in self._captured:
            return self._captured[url][1]
        self._last_wire.pop(url, None)
        html = super().fetch(url, force_refresh=True)
        if html is not None and url in self._last_wire:
            self._captured[url] = (self._last_wire[url], html)
        return html

    # ── Listing page ──────────────────────────────────────────────────────────

    def window(self) -> tuple[date, date]:
        """[target-N, target], inclusive, in the source's own (UTC+8) dates."""
        return (self.target_date - timedelta(days=self.lookback_days),
                self.target_date)

    def _in_window(self, d: Optional[date]) -> bool:
        if d is None:
            return False
        start, end = self.window()
        return start <= d <= end

    def get_article_urls(self) -> list[str]:
        html = self.fetch(_LISTING_URL)
        if not html:
            self.logger.warning("Could not fetch Global Times military listing")
            return []

        soup = self.parse(html)

        # url -> listing date (None for undated featured tiles), in listing
        # order. A dated occurrence always supersedes an undated one.
        candidates: dict[str, Optional[date]] = {}
        for a in soup.find_all("a", href=True):
            href = urljoin(_LISTING_URL, a["href"])
            if not _ARTICLE_URL_RE.match(href):
                continue
            listed = _listing_date(_nearest_source_time(a))
            if href not in candidates or (candidates[href] is None
                                          and listed is not None):
                candidates[href] = listed

        ordered_urls: list[str] = []
        for href, listed in candidates.items():
            if listed is None:
                # Undated tile: the article's own pub_time decides. Unresolved
                # means skipped, never accepted.
                page = self.fetch(href)
                listed = (_pub_time_date(self.parse(page))
                          if page else None)
            if self._in_window(listed):
                ordered_urls.append(href)

        self.logger.debug("Global Times military: %d in-window articles",
                          len(ordered_urls))
        # Preserve the listing's observed order, not process-specific hash order.
        return ordered_urls

    # ── Article parsing ───────────────────────────────────────────────────────

    def parse_article(self, url: str, html: str) -> Optional[dict]:
        soup = self.parse(html)

        title = self._extract_title(soup)
        if not title:
            self.logger.debug("No title found, skipping: %s", url)
            return None

        pub_date = self._extract_date(soup, url)
        if pub_date is None:
            # Fail closed: a page with no readable publication date is not
            # silently stamped with the run's target date.
            self.logger.warning("No publication date, skipping: %s", url)
            return None
        if not self._in_window(date.fromisoformat(pub_date)):
            self.logger.debug("Outside acquisition window, skipping: %s", url)
            return None

        text = self._extract_text(soup)
        byline = self._extract_byline(soup)
        verdict = self._content_verdict(soup, text)
        text_held = None
        if byline and _NON_GT_BYLINE_RE.search(byline):
            # Another agency's or ministry's text: keep title, URL and date,
            # hold the body. No content verdict is asserted: the document has
            # prose, it is simply not published here. A blank stored body is
            # already withheld from model dispatch (hold_blank_original_bodies).
            text, verdict, text_held = "", None, "non_gt_byline"

        article = {
            "url":             url,
            "source_slug":     self.source_slug,
            "title_original":  title,
            "text_original":   text,
            "published_date":  pub_date,
            "content_verdict": verdict,
        }
        if text_held:
            # Read by the collection adapter: a deliberate hold is not an
            # unreadable page, so it is not counted as text_unavailable.
            article["text_held"] = text_held
        wire = self._captured.get(url, (None, None))[0]
        if wire is not None:
            sha = hashlib.sha256(wire).hexdigest()
            self._store_raw(sha, wire)
            article["custody"] = {
                "capture_sha256": sha,
                "byline": byline,
                "pub_time": _pub_time_text(soup),
                "fetched_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "text_held": text_held,
            }
        return article

    @staticmethod
    def _store_raw(sha: str, wire: bytes) -> None:
        """Write the exact wire bytes to the private store when configured."""
        root = os.environ.get(RAW_CAPTURE_DIR_ENV)
        if not root:
            return
        path = Path(root) / FAMILY / (sha + ".html")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(wire)

    @staticmethod
    def _extract_byline(soup: BeautifulSoup) -> Optional[str]:
        span = soup.find("span", class_="byline")
        if span is None:
            return None
        text = " ".join(span.get_text(" ", strip=True).split())
        text = re.sub(r"^by\s+", "", text, flags=re.IGNORECASE)
        return text or None

    @staticmethod
    def _content_verdict(soup: BeautifulSoup, text: str):
        """
        A deterministic statement about the document, or None.

        `media_only` only when the body container was found (so the template is
        still understood), it carries media, and it carries no prose. A missing
        container is template drift and returns None — which is exactly the
        case that produced records 3432, 3946 and 3948, and the reason an empty
        body is never a permanent verdict on its own.
        """
        if text.strip():
            return None
        content_div = soup.find("div", class_="article_content")
        if content_div is None:
            return None                      # template drift — say nothing
        if content_div.find(["img", "video", "iframe"]) is not None:
            return "media_only"
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        div = soup.find("div", class_="article_title")
        if div:
            text = div.get_text(strip=True)
            if text:
                return text
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        The article's prose, or an empty string.

        Three routes, tried in order, because the site serves two templates and
        the older one still has to keep working.

        1. **Paragraph markup.** `div.article_content` with real `<p>` bodies.
           This is the original route and is unchanged, so every page that
           extracted correctly before still takes exactly this path.
        2. **Flow markup.** `div.article_content > div.article_right` carrying
           the body as bare text nodes separated by `<br><br>`, with the only
           `<p>` being `class="picture"` image captions. Measured 2026-09-16:
           this is why records 3432, 3946 and 3948 were stored with empty
           bodies while their pages served 359, 3,969 and 2,113 characters of
           prose. Route 1 looked for `<p>` inside `article_content`, found only
           captions, correctly refused to treat a caption as a body, and
           returned nothing — so an extraction defect was recorded as source
           silence. C5 in docs/DESK_STRENGTH_CRITERIA.md names that inversion.
        3. **Bare paragraphs** anywhere on the page. The original fallback,
           unchanged.

        An empty string remains a real answer. A page that is genuinely a photo
        set or a video shell has no prose, and this returns nothing rather than
        promoting a caption or a headline into a body.
        """
        # Route 1 — paragraph markup, byte-for-byte the original behaviour.
        content_div = soup.find("div", class_="article_content")
        if content_div:
            paras = [
                p.get_text(strip=True)
                for p in content_div.find_all("p")
                if len(p.get_text(strip=True)) > 30
                   and p.get("class") != ["picture"]
            ]
            if paras:
                return "\n".join(paras)

        # Route 2 — flow markup.
        if content_div:
            flow = _flow_text(content_div)
            if flow:
                return flow

        # Route 3 — bare paragraphs, excluding related-article embeds.
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if not p.get("class")
               and len(p.get_text(strip=True)) > 40
               and not _inside_embed(p)
        ]
        return "\n".join(paragraphs)

    def _extract_date(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        Publication date (UTC+8 calendar date, as the site prints it), or None.

        Article pages carry `<span class="pub_time">Published: Nov 20, 2026
        11:42 PM</span>`; listing tiles carry `div.source_time`. An explicit
        `div.source_time` is honoured if the page has one. There is no
        fallback to the run's target date: unreadable means None.
        """
        d = _pub_time_date(soup)
        if d is not None:
            return d.isoformat()
        if soup.find(class_="pub_time") is not None:
            # A pub_time that does not parse is not replaced by some other
            # date on the page (related-article tiles carry their own).
            return None
        for div in soup.find_all("div", class_=lambda c: c and "source_time" in c):
            d = _listing_date(div.get_text(strip=True))
            if d is not None:
                return d.isoformat()
        return None


#: Containers that hold other articles' text on an article page: the related
#: and recommended rails. The module docstring has always noted that repeated
#: `div.article_content` elements are related-article embeds; route 3 did not
#: act on it, and on a flow-markup page where route 1 finds nothing it swept
#: thirty teaser paragraphs into the body. Measured 2026-09-16 on the PLA Navy
#: missile-test page: 2,726 characters of other articles' first lines stored as
#: this article's body, against a real body of 797. That is worse than an empty
#: body — an empty body is a gap, and this was other reporting attributed to
#: the wrong document.
_EMBED_CLASSES = ("related_content", "related_article", "related_section",
                  "recommend", "latest_news")


def _inside_embed(tag) -> bool:
    """True when this node sits inside a related/recommended rail."""
    for parent in tag.parents:
        classes = parent.get("class") if hasattr(parent, "get") else None
        if classes and any(c in _EMBED_CLASSES for c in classes):
            return True
    return False


#: Body text shorter than this is page furniture rather than a paragraph.
#: Matches the threshold route 1 already applies to `<p>` bodies.
_MIN_FLOW_PARAGRAPH_CHARS = 30


def _flow_text(content_div) -> str:
    """
    Recover paragraphs from a body written as bare text nodes and `<br>`.

    The container is copied before it is stripped, because these helpers run
    against a soup the caller may still read — `_extract_date` walks the same
    tree — and mutating shared state to compute a return value is how a second
    defect gets introduced while fixing the first.

    Image captions (`p.picture`), the images themselves and their `<center>`
    wrappers are removed rather than flattened. A caption describes a
    photograph; it is not a sentence the paper published as its report, and
    letting one stand in for a body is the same invention this adapter refuses
    everywhere else.
    """
    import copy

    node = copy.copy(content_div)
    for junk in node.find_all(["script", "style", "img", "center", "iframe"]):
        junk.decompose()
    for caption in node.find_all("p", class_="picture"):
        caption.decompose()

    for br in node.find_all("br"):
        br.replace_with("\n")

    text = node.get_text()
    paragraphs = [
        line.strip()
        for line in text.split("\n")
        if len(line.strip()) >= _MIN_FLOW_PARAGRAPH_CHARS
    ]
    return "\n".join(paragraphs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nearest_source_time(tag) -> Optional[str]:
    """
    Walk up the DOM tree from <a> looking for a sibling or ancestor
    <div class="source_time"> that carries the article's publication date.
    Checks parent, grandparent, and great-grandparent elements.
    """
    node = tag
    for _ in range(4):
        node = node.parent
        if node is None:
            return None
        # Look at siblings of the current node
        for sibling in node.find_all("div", class_=lambda c: c and "source_time" in c):
            text = sibling.get_text(strip=True)
            if re.search(r"\d{4}/\d{1,2}/\d{1,2}", text):
                return text
    return None


def _listing_date(text: Optional[str]) -> Optional[date]:
    """Parse 'By Author  |  2026/5/7 18:37:07' to a date, or None."""
    if not text:
        return None
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _pub_time_text(soup: BeautifulSoup) -> Optional[str]:
    span = soup.find(class_="pub_time")
    if span is None:
        return None
    return " ".join(span.get_text(" ", strip=True).split()) or None


def _pub_time_date(soup: BeautifulSoup) -> Optional[date]:
    """Date part of 'Published: Nov 20, 2026 11:42 PM' (printed in UTC+8)."""
    text = _pub_time_text(soup)
    m = _PUB_TIME_RE.search(text or "")
    if not m:
        return None
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(
                "%s %s %s" % (m.group(1)[:9], m.group(2), m.group(3)),
                fmt).date()
        except ValueError:
            continue
    return None
