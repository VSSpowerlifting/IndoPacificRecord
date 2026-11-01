"""Render the immutable, approved-for-send worksheet as a clean email for prose editing.

The long original TXT stays attached and its exact SHA review is unchanged.
This is strictly a presentation transform: no source selection, LLM, SMTP,
approval, citations reassignment, publishing, or external HTML dependencies.
"""
from __future__ import annotations

import html
import re
from datetime import date, timedelta

BEGIN = "=== EDITABLE MANUSCRIPT ==="
APPENDIX = "=== SOURCE APPENDIX — DO NOT EDIT ==="
HEADINGS = (
    "WORKING TITLE", "DEK", "CONCRETE DEVELOPMENT", "OPENING NOTE",
    "WHAT STOOD OUT", "WHY IT MATTERS", "WHAT WAS ROUTINE",
    "WHAT I'M WATCHING NEXT", "CROSS-DESK COMPARISON",
)
# Article-first layout: one continuous ARTICLE section whose subheads are
# ``**bold-only**`` paragraphs. Source accounting lives in the appendix.
ARTICLE_KEY = "ARTICLE"
ARTICLE_HEADINGS = ("WORKING TITLE", "DEK", ARTICLE_KEY)
INTERNAL = frozenset(("EDITORIAL FOCUS", "EDITORIAL QUESTIONS / SATURDAY FOLLOW-UP"))
SUBHEAD_RE = re.compile(r"\*\*([^*\n]+)\*\*")
ACCOUNTING_BEGIN = "ARTICLE SOURCE ACCOUNTING"
ACCOUNTING_END = "END OF ARTICLE SOURCE ACCOUNTING"
BLOCK_LINE = re.compile(
    r"^Block ([0-9]+) \| fp ([0-9a-f]{12}) \| records ([0-9]+(?:, [0-9]+)*|none)"
    r" \| external ([A-Za-z0-9_-]+(?:, [A-Za-z0-9_-]+)*|none)$", re.MULTILINE)
IDS = ("SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:")
SECTION_RE = re.compile(r"^## ([^\r\n]+)$", re.MULTILINE)
PROSE_TITLES = {
    "CONCRETE DEVELOPMENT": "The development",
    "OPENING NOTE": "Overview",
    "WHAT STOOD OUT": "What stood out",
    "WHY IT MATTERS": "Why it matters",
    "WHAT WAS ROUTINE": "What was routine",
    "WHAT I'M WATCHING NEXT": "What we're watching",
    "CROSS-DESK COMPARISON": "Across the region",
}
INTRO = (
    "Hi Dylan,\n\n"
    "Here's this week's IPR Brief manuscript for your edit. The standing IPR "
    "Editor Instructions are attached; the specifics for this one are below. "
    "Please focus on the language, flow, clarity and structure: rewrite, "
    "reorder, merge, split or cut paragraphs, and change or drop subheads. "
    "If a claim strikes you as questionable, flag it in a comment—I’ll handle "
    "the source verification, permissions and final publication review. "
    "This is still a provisional, unapproved draft."
)
REPLY = (
    "Please reply in this thread with the edited Word file, changes still "
    "tracked, and a short note on what you changed and anything to check. "
    "If the timing does not work, tell me as soon as you can."
)
READING_NOTE = (
    "A reading copy follows; please make your edits in the attached Word file."
)
ATTACHED = (
    "the Word manuscript (your editing file, Track Changes on); the .txt "
    "worksheet (source-audit reference, no edits needed); IPR Editor Instructions"
)
# Instructions §4; the assignment states the draft's length against it.
TARGET_WORDS = (700, 1200)
CLOSING = "\n\nThanks,\nBen\n"


class ReadableEditorError(ValueError):
    """Refuse malformed manuscript or non-manuscript source packet."""


def editable_sections(original):
    """Only prose within the already reviewed editable boundary; never sources.

    Omit the editorial-only focus/queries and source ID display from Dylan's
    reading copy. The ORIGINAL immutable TXT remains the citation reference.
    """
    if not isinstance(original, str) or original.count(BEGIN) != 1 or original.count(APPENDIX) != 1:
        raise ReadableEditorError("missing or duplicated exact manuscript boundaries")
    before, remainder = original.split(BEGIN, 1)
    draft, _ = remainder.split(APPENDIX, 1)
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in before:
        raise ReadableEditorError("source worksheet does not state unapproved status")
    if "## " not in draft:
        raise ReadableEditorError("no model manuscript in worksheet")
    headings = list(SECTION_RE.finditer(draft))
    if not headings:
        raise ReadableEditorError("no article headings found")
    sections = {}
    for i, match in enumerate(headings):
        key = match.group(1)
        end = headings[i + 1].start() if i + 1 < len(headings) else len(draft)
        if key not in HEADINGS and key not in INTERNAL and key not in ARTICLE_HEADINGS:
            raise ReadableEditorError("unknown source worksheet heading")
        if key in sections:
            raise ReadableEditorError("duplicate manuscript heading")
        raw = draft[match.end():end].strip()
        if any(line.startswith("===") for line in raw.splitlines()):
            raise ReadableEditorError("unexpected envelope marker in article")
        cleaned = "\n".join(
            line for line in raw.splitlines()
            if not line.startswith(IDS)
        ).strip()
        if not cleaned:
            raise ReadableEditorError("empty manuscript section")
        sections[key] = cleaned
    if ARTICLE_KEY in sections:
        legacy = (set(HEADINGS) - set(ARTICLE_HEADINGS)) & set(sections)
        if legacy:
            raise ReadableEditorError("mixed article-first and fixed-outline headings")
        if not all(key in sections for key in ARTICLE_HEADINGS):
            raise ReadableEditorError("incomplete or truncated manuscript")
        return [(key, sections[key]) for key in ARTICLE_HEADINGS]
    if not all(key in sections for key in HEADINGS):
        raise ReadableEditorError("incomplete or truncated manuscript")
    return [(key, sections[key]) for key in HEADINGS]


def is_article_layout(sections):
    return any(key == ARTICLE_KEY for key, _ in sections)


def split_article(text):
    """``[("subhead"|"para", text)]`` from an ARTICLE body; the lead has no subhead."""
    items = []
    for chunk in re.split(r"\n\s*\n", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = SUBHEAD_RE.fullmatch(chunk)
        items.append(("subhead", match.group(1).strip()) if match else ("para", chunk))
    return items


def accounting_citations(packet):
    """Cited (kind, id) pairs, in block order, from the hash-pinned appendix."""
    appendix = packet.split(APPENDIX, 1)[1]
    if ACCOUNTING_BEGIN not in appendix or ACCOUNTING_END not in appendix:
        raise ReadableEditorError("article source accounting missing from appendix")
    block = appendix.split(ACCOUNTING_BEGIN, 1)[1].split(ACCOUNTING_END, 1)[0]
    cited = []
    for match in BLOCK_LINE.finditer(block):
        for kind, raw in (("Record", match.group(3)), ("External", match.group(4))):
            if raw == "none":
                continue
            for identifier in raw.split(", "):
                if (kind, identifier) not in cited:
                    cited.append((kind, identifier))
    return cited


def _plain(text):
    return re.sub(r"\*\*([^\n*]+)\*\*", r"\1", text)


def _due(week_ending):
    """Instructions §9: the Sunday manuscript is due Monday, 8 p.m. ET."""
    try:
        monday = date.fromisoformat(str(week_ending)) + timedelta(days=2)
    except ValueError:
        monday = None
    if monday is None or monday.weekday() != 0:
        return "Monday, 8 p.m. ET"
    return "Monday {} {}, 8 p.m. ET".format(monday.day, monday.strftime("%B %Y"))


def assignment(original, week_ending=None):
    """``[(label, value)]`` for the story-specific assignment (template fields).

    Deterministic and drawn only from the editable prose and the hash-pinned
    accounting counts; the INTERNAL focus/questions sections never appear.
    """
    sections = dict(editable_sections(original))
    body = [text for key, text in sections.items() if key not in ("WORKING TITLE", "DEK")]
    words = sum(len(_plain(text).split()) for text in body)
    low, high = TARGET_WORDS
    length = "about {:,} words, against the usual {:,}–{:,}".format(words, low, high)
    if words < low:
        length += "; shorter than usual, so please do not pad it"
    elif words > high:
        length += "; longer than usual, so please cut what does not earn its place"
    rows = [
        ("Working title", _plain(sections["WORKING TITLE"])),
        ("The development", _plain(sections["DEK"])),
        ("This Brief is", "the week's regular Sunday Brief"),
    ]
    try:
        cited = accounting_citations(original)
    except ReadableEditorError:
        cited = None
    if cited:
        records = sum(1 for kind, _ in cited if kind == "Record")
        external = len(cited) - records
        parts = ["{} preserved official record{}".format(records, "" if records == 1 else "s")]
        if external:
            parts.append("{} official research source{}".format(external, "" if external == 1 else "s"))
        rows.append(("Sources", " and ".join(parts) + " (listed in the .txt worksheet)"))
    rows.extend((("Length", length), ("Due", _due(week_ending)), ("Attached", ATTACHED)))
    return rows


def prose_only_text(original, week_ending=None):
    """Readable plain-text editorial copy for the multipart email fallback."""
    sections = editable_sections(original)
    out = [INTRO, ""]
    out.extend("- {}: {}".format(label, value) for label, value in assignment(original, week_ending))
    out.extend(("", REPLY, "", READING_NOTE, "", ""))
    for key, text in sections:
        # Plain-text mail clients also deserve prose without Markdown stars.
        text = re.sub(r"\*\*([^\n*]+)\*\*", r"\1", text)
        if key == "WORKING TITLE":
            out.append(text)
        elif key == "DEK":
            out.append(text)
        elif key == ARTICLE_KEY:
            out.append(text)
        else:
            out.extend((PROSE_TITLES[key], text))
        out.append("")
    out.append(CLOSING.strip())
    return "\n".join(out) + "\n"


def _paragraph_html(text):
    """Render only escaped paragraphs and simple bold; no raw publisher HTML."""
    safe = html.escape(text, quote=True)
    safe = re.sub(r"\*\*([^\n*]+)\*\*", r"<strong>\1</strong>", safe)
    return "".join(
        '<p style="margin:0 0 14px;line-height:1.65;">' +
        para.replace("\n", " ") + "</p>"
        for para in safe.split("\n\n") if para.strip()
    )


def prose_only_html(original, week_ending=None):
    """Professional article-first HTML; all technical source data stays out."""
    sections = editable_sections(original)
    para = "<p>{}</p>".format
    out = [
        '<!doctype html><html><body style="margin:0;padding:0;background:#ffffff;">',
        '<div style="max-width:680px;margin:20px auto;padding:24px 20px;'
        'font-family:Georgia,Times New Roman,serif;color:#1b2b36;font-size:16px;">',
        '<div style="font:700 12px Arial,sans-serif;letter-spacing:1px;'
        'text-transform:uppercase;color:#607887;margin-bottom:20px;">'
        "Indo-Pacific Record / Working Brief</div>",
        '<div style="font:14px Arial,sans-serif;color:#435664;line-height:1.6;'
        'padding:0 0 18px;border-bottom:1px solid #d8e1e6;margin-bottom:20px;">'
        + "".join(para(html.escape(p, quote=True)) for p in INTRO.split("\n\n"))
        + '<ul style="margin:0 0 14px;padding-left:20px;">'
        + "".join("<li><strong>{}:</strong> {}</li>".format(
            html.escape(label, quote=True), html.escape(value, quote=True))
            for label, value in assignment(original, week_ending))
        + "</ul>" + para(html.escape(REPLY, quote=True))
        + para(html.escape(READING_NOTE, quote=True)) + "</div>",
    ]
    for key, text in sections:
        if key == "WORKING TITLE":
            out.append('<h1 style="font-size:28px;line-height:1.25;margin:0 0 14px;">'
                       + html.escape(text, quote=True) + "</h1>")
        elif key == "DEK":
            out.append('<div style="font-size:17px;color:#425663;line-height:1.55;'
                       'margin:0 0 26px;">' + _paragraph_html(text) + "</div>")
        elif key == ARTICLE_KEY:
            for kind, value in split_article(text):
                if kind == "subhead":
                    out.append('<h2 style="font:700 17px Arial,sans-serif;'
                               'margin:26px 0 12px;color:#233a49;">' +
                               html.escape(value, quote=True) + "</h2>")
                else:
                    out.append(_paragraph_html(value))
        else:
            out.append('<h2 style="font:700 17px Arial,sans-serif;'
                       'margin:26px 0 12px;color:#233a49;">' +
                       html.escape(PROSE_TITLES[key], quote=True) + "</h2>")
            out.append(_paragraph_html(text))
    out.append('<p style="font:14px Arial,sans-serif;margin:22px 0 0;">'
               "Thanks,<br>Ben</p></div></body></html>")
    return "".join(out)
