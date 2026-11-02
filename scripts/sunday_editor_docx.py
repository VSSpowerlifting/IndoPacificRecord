"""Editor-first DOCX projection of a validated Sunday worksheet.

This is a presentation layer only. The unchanged original TXT is the
provenance/approval artifact; this document is a provisional editing copy,
not a publication-ready IPR Brief or a substitute for original-source checks.
"""
from __future__ import annotations

import io
import re
import zipfile
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.shared import Inches, Pt

from core.brief_editorial_cycle import (
    DOCX_CYCLE_PROPERTY, DOCX_CYCLE_VARIABLE, SATURDAY_PROVISIONAL_KEYWORD,
    SATURDAY_PROVISIONAL_LABEL, packet_identity,
)
from scripts.sunday_editorial_handoff import is_saturday_provisional
from scripts.sunday_editor_readable import (
    APPENDIX, ARTICLE_KEY, BEGIN, PROSE_TITLES, accounting_citations,
    editable_sections, is_article_layout, split_article,
)

RECORD_PREFIX = "SOURCE RECORD IDS:"
EXTERNAL_PREFIX = "EXTERNAL SOURCE IDS:"
RECORD_LINE = re.compile(r"^Record ([0-9]+) \|")
EXTERNAL_LINE = re.compile(r"^External source ([A-Za-z0-9_-]+) \|")
BOLD = re.compile(r"\*\*([^\n*]+)\*\*")
CUSTOM_PROPERTIES = ("http://schemas.openxmlformats.org/officeDocument/2006/"
                     "relationships/custom-properties")
CUSTOM_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.custom-properties+xml"


def _cycle_parts(files, identity):
    """Add the hidden custom property carrying the cycle Brief identity.

    Visible labels are for Dylan; this property (and the document variable)
    is what scripts.import_brief_manuscript reads as cycle provenance.
    """
    value = escape(identity)
    files["docProps/custom.xml"] = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="'
        + escape(DOCX_CYCLE_PROPERTY) + '"><vt:lpwstr>' + value + "</vt:lpwstr></property>"
        "</Properties>").encode()
    files["_rels/.rels"] = files["_rels/.rels"].replace(
        b"</Relationships>",
        b'<Relationship Id="rIdIprCycle" Type="' + CUSTOM_PROPERTIES.encode()
        + b'" Target="docProps/custom.xml"/></Relationships>')
    files["[Content_Types].xml"] = files["[Content_Types].xml"].replace(
        b"</Types>",
        b'<Override PartName="/docProps/custom.xml" ContentType="'
        + CUSTOM_CONTENT_TYPE.encode() + b'"/></Types>')


def _references(packet):
    """Return ONLY cited publisher URLs, never raw bodies/synopses/hashes."""
    manuscript = packet.split(BEGIN, 1)[1].split(APPENDIX, 1)[0]
    appendix = packet.split(APPENDIX, 1)[1]
    cited = []
    if re.search(r"^## " + ARTICLE_KEY + r"$", manuscript, re.MULTILINE):
        # Article-first worksheets keep the citation map in the appendix.
        cited = accounting_citations(packet)
    for line in ([] if cited else manuscript.splitlines()):
        kind = None
        if line.startswith(RECORD_PREFIX):
            kind = "Record"
            values = line[len(RECORD_PREFIX):]
        elif line.startswith(EXTERNAL_PREFIX):
            kind = "External"
            values = line[len(EXTERNAL_PREFIX):]
        if kind:
            for raw in values.split(","):
                identifier = raw.strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
                    raise ValueError("invalid cited source identifier in worksheet")
                key = (kind, identifier)
                if key not in cited:
                    cited.append(key)

    catalog = {}
    current = None
    for line in appendix.splitlines():
        record = RECORD_LINE.match(line)
        external = EXTERNAL_LINE.match(line)
        if record:
            current = ("Record", record.group(1))
        elif external:
            current = ("External", external.group(1))
        elif line.startswith("URL: ") and current is not None:
            url = line[5:].strip()
            parts = urlsplit(url)
            # The immutable production corpus includes original publisher URLs
            # using HTTP (e.g. Chinese MOD/China Military Online). Preserve the
            # source's actual URL rather than silently rewriting it to HTTPS;
            # never accept non-web schemes or embedded credentials.
            if (parts.scheme in ("http", "https") and parts.hostname
                    and not parts.username and not parts.password):
                if current in catalog and catalog[current] != url:
                    raise ValueError("duplicate source identity with conflicting URL")
                catalog[current] = url
            current = None
    missing = [name for name in cited if name not in catalog]
    if missing:
        raise ValueError("cited source URL absent from immutable worksheet")
    return [(kind, identifier, catalog[(kind, identifier)])
            for kind, identifier in cited]


def _rich_paragraph(paragraph, value):
    """Preserve authored text and optional **bold** without interpreting HTML."""
    clean = " ".join(value.splitlines()).strip()
    offset = 0
    for match in BOLD.finditer(clean):
        if match.start() > offset:
            paragraph.add_run(clean[offset:match.start()])
        paragraph.add_run(match.group(1)).bold = True
        offset = match.end()
    if offset < len(clean):
        paragraph.add_run(clean[offset:])


def _hyperlink(paragraph, label, target):
    relation = paragraph.part.relate_to(
        target, RELATIONSHIP_TYPE.HYPERLINK, is_external=True,
    )
    element = OxmlElement("w:hyperlink")
    element.set(qn("r:id"), relation)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    props.append(style)
    run.append(props)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    element.append(run)
    paragraph._p.append(element)


def render_editor_docx(worksheet):
    """Return .docx bytes only after the source-text boundary validator passes."""
    sections = editable_sections(worksheet)
    sources = _references(worksheet)
    saturday_provisional = is_saturday_provisional(worksheet)
    identity = packet_identity(worksheet) if saturday_provisional else None
    if saturday_provisional and identity is None:
        raise ValueError("Saturday provisional worksheet lacks one Packet: identity")
    doc = Document()
    doc.core_properties.title = "Indo-Pacific Record — Working Brief"
    doc.core_properties.author = "Indo-Pacific Record"
    if saturday_provisional:
        doc.core_properties.keywords = SATURDAY_PROVISIONAL_KEYWORD
        variables = OxmlElement("w:docVars")
        variable = OxmlElement("w:docVar")
        variable.set(qn("w:name"), DOCX_CYCLE_VARIABLE)
        variable.set(qn("w:val"), identity)
        variables.append(variable)
        # CT_Settings order: w:docVars comes directly before w:rsids.
        doc.settings.element.find(qn("w:rsids")).addprevious(variables)

    section = doc.sections[0]
    section.top_margin = Inches(.82)
    section.bottom_margin = Inches(.78)
    section.left_margin = Inches(.85)
    section.right_margin = Inches(.85)

    normal = doc.styles["Normal"]
    normal.font.name = "Georgia"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(8)
    normal.paragraph_format.line_spacing = 1.24
    for name in ("Title", "Heading 1", "Heading 2"):
        style = doc.styles[name]
        style.font.name = "Aptos"
        style.font.color.rgb = None

    label = doc.add_paragraph()
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label.add_run("INDO-PACIFIC RECORD / BRIEFS").bold = True
    if saturday_provisional:
        mark = doc.add_paragraph()
        mark.alignment = WD_ALIGN_PARAGRAPH.CENTER
        mark.add_run(SATURDAY_PROVISIONAL_LABEL).bold = True
        doc.add_paragraph(
            "Drafted from sources collected through Saturday's daily run. "
            "Later Saturday publications may be missing; Ben rechecks the "
            "full week on Sunday before this draft can be used."
        )

    doc.add_paragraph(
        "Provisional editorial manuscript · For Dylan's language and structure edits only"
    )
    doc.add_paragraph(
        "Ben will independently check the underlying sources and approve any publication."
    )
    for key, value in sections:
        if key == "WORKING TITLE":
            p = doc.add_paragraph(style="Title")
            _rich_paragraph(p, value)
        elif key == "DEK":
            p = doc.add_paragraph(style="Subtitle")
            _rich_paragraph(p, value)
        elif key == ARTICLE_KEY:
            for kind, text in split_article(value):
                if kind == "subhead":
                    doc.add_heading(text, level=2)
                else:
                    p = doc.add_paragraph()
                    _rich_paragraph(p, text)
        else:
            doc.add_heading(PROSE_TITLES[key], level=2)
            for block in re.split(r"\n\s*\n", value):
                if block.strip():
                    p = doc.add_paragraph()
                    _rich_paragraph(p, block)

    if sources:
        doc.add_page_break()
        doc.add_heading("Source links for context", level=2)
        doc.add_paragraph(
            "These are links cited by the draft, not independently verified "
            "publication approvals. Please flag any factual questions; Ben "
            "will check original wording, dates and final citations."
        )
        for kind, identifier, url in sources:
            p = doc.add_paragraph()
            _hyperlink(p, kind + " " + identifier, url)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run(
        (SATURDAY_PROVISIONAL_LABEL + " · " if saturday_provisional else "") +
        "UNNUMBERED DRAFT · NOT APPROVED FOR PUBLICATION")

    output = io.BytesIO()
    doc.save(output)
    # ZIP wall-clock timestamps otherwise change the Word attachment between
    # owner preview and exact-TXT release, even though its contents are identical.
    stable = io.BytesIO()
    with zipfile.ZipFile(output) as source:
        entries = source.infolist()
        files = {entry.filename: source.read(entry.filename) for entry in entries}
    if identity is not None:
        _cycle_parts(files, identity)
        custom = zipfile.ZipInfo("docProps/custom.xml")
        custom.compress_type = zipfile.ZIP_DEFLATED
        entries.append(custom)
    with zipfile.ZipFile(stable, "w") as target:
        for entry in entries:
            entry.date_time = (1980, 1, 1, 0, 0, 0)
            target.writestr(entry, files[entry.filename])
    return stable.getvalue()
