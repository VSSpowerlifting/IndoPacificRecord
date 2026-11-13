"""Japan Coast Guard English press-release HTML family; shadow candidate only.

Institution: Japan Coast Guard (maritime law enforcement), NOT Japan MOD.
Uses the existing isolated ListingShadowAdapter transport: named client,
robots checks, no redirect/challenge bypass, bounded fetches, capture hashes.
No production manifest or authorization to publish is present in this module.

Document scope: publisher's HTML release text, not embedded PDF attachments,
photos or any broader JCG publications. Every listed article stays distinguishable
by its published canonical URL, never its title.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString

from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import ListingShadowAdapter, Page

HOST = "www.kaiho.mlit.go.jp"
LISTING = "https://" + HOST + "/e/topics_archive/index.html"
# The publisher's site-use rules (PDL 1.0 and its exclusions). Captured into
# custody in every run, before the listing, so the standing-rights replay
# (core.japan_jcg_rights) verifies the terms in force when the releases were
# collected. Policy evidence only: no release scope is added, and a failed
# capture refuses the run.
POLICY_URL = "https://" + HOST + "/questions/post-1.html"
RELEASE = re.compile(r"^/e/topics_archive/article([0-9]+)\.html$")
# Directory of the declared release family. An index row that links a
# first-party page *outside* this directory (observed 2026-10-26: an
# "Update" row for /info/topics/rescueforeignvessels.html) is disclosed as
# an uncollected non-release row, never admitted or fetched. Anything
# inside the directory must still be an exact release identity.
ARCHIVE_DIR = "/e/topics_archive/"
# Initial bounded pilot scope; older publisher rows are counted as discovery
# history but are not admitted until their URL/document families are reviewed.
PILOT_BEGIN = "2026-09-01"
DATE_DMY = re.compile(r"^(\d{1,2})\s+(\d{1,2})\s+(\d{4})$")
DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
DATE_DOTTED = re.compile(r"^(\d{4})[./](\d{1,2})[./](\d{1,2})$")
DATE_ENGLISH = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
                "%d %B, %Y", "%d %b, %Y")

# Version of the article-text extraction. Custody rows written by an earlier
# profile (attachment link labels in the text, <p>-only bodies) are held by
# ``core.japan_jcg_links.scope_hold`` rather than passed to processing.
EXTRACTION_PROFILE = "jcg-html-article-text/2"
ATTACHMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                       ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")
MEDIA_TAGS = ("img", "picture", "figure", "video", "audio", "object", "embed")
MEDIA_HOLDERS = ("p", "li", "td", "th", "dd", "dt", "figure", "blockquote", "caption")
BLOCKS = frozenset(("p", "li", "blockquote", "div", "td", "th", "tr", "table",
                    "tbody", "thead", "ul", "ol", "dl", "dd", "dt", "section",
                    "article", "figure", "figcaption", "caption", "pre",
                    "h1", "h2", "h3", "h4", "h5", "h6"))
HEADINGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
# ASCII whitespace only: a full-width space is publisher text, not layout.
SPACE = re.compile(r"[ \t\r\n\f\v]+")
LABEL_WORDS = 12


def article_blocks(body):
    """Article prose as publisher blocks, in document order.

    Text is split at block elements and at ``<br>``, so releases published as
    ``<br>``-separated text without paragraphs and releases whose lead or
    numbered section labels are headings both keep all of their prose. A
    short heading left with no prose under it (for example "Photo Gallery" or
    "Links" once media and attachment labels are excluded) is not prose.
    """
    blocks, buf = [], []

    def flush(kind="text"):
        text = SPACE.sub(" ", "".join(buf)).strip()
        buf.clear()
        if text:
            blocks.append((kind, text))

    def walk(node):
        for child in node.children:
            name = getattr(child, "name", None)
            if name is None:
                if type(child) is NavigableString:  # not a comment or doctype
                    buf.append(str(child))
            elif name == "br":
                # html.parser nests the text after an unclosed <br> inside it.
                flush()
                walk(child)
            elif name in HEADINGS:
                flush()
                walk(child)
                flush("heading")
            elif name in BLOCKS:
                flush()
                walk(child)
                flush()
            else:
                walk(child)

    walk(body)
    flush()
    kept = []
    for i, (kind, text) in enumerate(blocks):
        following = blocks[i + 1][0] if i + 1 < len(blocks) else None
        if (kind == "heading" and len(text.split()) <= LABEL_WORDS
                and following in (None, "heading")):
            continue
        kept.append(text)
    return kept


def one(nodes, purpose):
    nodes = list(nodes)
    if len(nodes) != 1:
        raise ValueError("expected one " + purpose + ", observed " + str(len(nodes)))
    return nodes[0]


def canon(url):
    """Accept only an explicitly linked first-party release on this hostname."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != HOST or parts.query
            or parts.fragment or not RELEASE.fullmatch(parts.path)):
        raise ValueError("URL is not a JCG English release identity")
    return "https://" + HOST + parts.path


def source_date(value):
    text = " ".join(value.replace("\u3000", " ").strip().split())
    m = DATE_DMY.fullmatch(text)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    m = DATE_ISO.fullmatch(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    m = DATE_DOTTED.fullmatch(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    for fmt in DATE_ENGLISH:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("unrecognized JCG publisher date (no inferred fallback): " + repr(text[:64]))


class JCGEnglishAdapter(ListingShadowAdapter):
    host, listing = HOST, LISTING

    def first_request(self, window):
        self._request(POLICY_URL)
        return self.listing, None

    def discover(self, window):
        outcome = super().discover(window)
        if outcome.ok and hasattr(self, "listing_observation"):
            self.listing_report.update(self.listing_observation)
        return outcome

    def parse_listing(self, text, request, number):
        if request != (LISTING, None) or number != 1:
            raise ValueError("only the publisher's complete English index is scoped")
        soup = BeautifulSoup(text, "html.parser")
        section = one(soup.select("main article.main-article section.topics.has-pd"),
                      "JCG press-release listing section")
        date_nodes = section.select("dl.topics-list p.topics-date")
        links = section.select("dl.topics-list a.arrow-link[href]")
        if not date_nodes or len(date_nodes) != len(links):
            raise ValueError("publisher listing date/article pairs incomplete")
        items = []
        seen = set()
        all_dates = []
        excluded_earlier = 0
        other_family = []
        for dnode, link in zip(date_nodes, links):
            if dnode.find_parent("dl") is not link.find_parent("dl"):
                raise ValueError("date paired across different publisher year groups")
            stated = source_date(dnode.get_text(" ", strip=True))
            all_dates.append(stated)
            if stated < PILOT_BEGIN:
                excluded_earlier += 1
                continue
            linked = urljoin(LISTING, link["href"])
            parts = urlsplit(linked)
            if (parts.scheme == "https" and parts.netloc == HOST
                    and not parts.path.startswith(ARCHIVE_DIR)):
                other_family.append({"url": linked, "date": stated})
                continue
            url = canon(linked)
            title = link.get_text(" ", strip=True)
            if not title or url in seen:
                raise ValueError("missing title or repeated publisher article identity")
            seen.add(url)
            items.append({"url": url, "date": stated, "title": title})
        if all_dates != sorted(all_dates, reverse=True):
            raise ValueError("JCG source listing chronology changed")
        self.listing_observation = {
            "publisher_index_rows_total": len(all_dates),
            "outside_declared_pilot_scope": excluded_earlier,
            "pilot_source_begin": PILOT_BEGIN,
            "outside_declared_url_family": len(other_family),
            "outside_declared_url_family_rows": other_family,
        }
        return Page(items, None)

    def parse_article(self, text, url):
        url = canon(url)
        soup = BeautifulSoup(text, "html.parser")
        section = one(soup.select("main article.main-article section.topics.topics-article"),
                      "JCG original release section")
        title = one(section.select("h1.entry-title"), "release title").get_text(" ", strip=True)
        time = one(section.select("time"), "publisher release date")
        raw_date = time.get_text(" ", strip=True)
        published_date = source_date(raw_date)
        machine_value = (time.get("datetime") or "").strip()
        machine_state = "absent"
        if machine_value:
            if machine_value == "2021-3-1":
                # Observed publisher-wide stale HTML template value on
                # October 6 page; make the disagreement inspectable, not
                # a silently trusted machine date. Listing still supplies
                # an independent *element* for runtime cross-check.
                machine_state = "observed_stale_template_2021-3-1"
            elif source_date(machine_value) == published_date:
                machine_state = "matches_visible"
            else:
                raise ValueError("publisher visible and datetime attribute dates disagree")
        body = one(section.select("div.topics-article__main.tich-text"),
                   "official release body")
        for node in body.select("script, style, noscript, nav, form, iframe, svg"):
            node.decompose()
        # Linked attachments (PDFs, documents, images) are outside the standing
        # HTML-text family. Their URLs are disclosed as metadata, never fetched,
        # and their link labels ("... (PDF:390KB)") are not article prose.
        pdf_links, attachment_labels = [], 0
        for link in body.select("a[href]"):
            href = urljoin(url, link["href"])
            p = urlsplit(href)
            if p.path.lower().endswith(ATTACHMENT_SUFFIXES):
                if p.scheme != "https" or p.netloc != HOST:
                    raise ValueError("release references off-host attachment; requires separate review")
                pdf_links.append(href)
                attachment_labels += 1
                link.decompose()
        # Photographs and their captions are media, not article prose: the
        # smallest block holding an image (a captioned paragraph or table cell)
        # is excluded whole, so a caption is never model input.
        media_blocks = 0
        for media in list(body.select(", ".join(MEDIA_TAGS))):
            if media.decomposed:
                continue
            holder = media.find_parent(MEDIA_HOLDERS)
            if holder is not None and body in holder.parents:
                holder.decompose()
            else:
                media.decompose()
            media_blocks += 1
        paragraphs = article_blocks(body)
        if not title or len(" ".join(paragraphs)) < 180:
            raise ValueError("body too short for a substantive original HTML release")
        if not any(len(p) > 70 for p in paragraphs):
            raise ValueError("no substantive paragraph (possibly links-only page)")
        prose = "\n\n".join(paragraphs)
        return ExtractedDocument(
            url=url, source_slug=self.slug, title_original=title,
            text_original=prose, published_date=published_date,
            language_tag="en", extra={
                "source_identity": "jcg-en:" + RELEASE.fullmatch(urlsplit(url).path)[1],
                "publisher": "Japan Coast Guard",
                "issuer": "Japan Coast Guard",
                "publication_kind": "english_official_press_release",
                "published_date_original": raw_date,
                "date_basis": "visible_publisher_time_and_archive_listing",
                "html_datetime_original": machine_value or None,
                "html_datetime_verdict": machine_state,
                "body_scope": "published_html_text_only",
                "attachments_collected": False,
                "attachment_urls": sorted(set(pdf_links)),
                "extraction_profile": EXTRACTION_PROFILE,
                "attachment_link_labels_excluded": attachment_labels,
                "media_blocks_excluded": media_blocks,
                "derivation": "first_party_english_original_not_translated",
            })
