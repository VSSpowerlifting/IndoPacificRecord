"""Offline, source-scoped research assignments for the existing Brief manuscript.

The caller supplies an explicit exact-version owner distribution decision. It is
an attestation of an already reviewed source-use decision, never a rights grant.
No originals, translations, research synopses, SMTP, or model calls are emitted.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
from io import BytesIO
import json
import re
from urllib.parse import urlsplit
from zipfile import ZipFile

from docx import Document
from scripts.sunday_editor_docx import _references
from scripts.sunday_editor_readable import editable_sections
from scripts.validate_editorial_return import _split

SCHEMA = "ipr-research-analyst-assignment/1"
MANUSCRIPT_BEGIN = "BEGIN EDITABLE MANUSCRIPT"
MANUSCRIPT_END = "END EDITABLE MANUSCRIPT"
MEMO_BEGIN = "BEGIN ANALYST MEMO"
MEMO_END = "END ANALYST MEMO"
HEX = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_FIELDS = {"id", "url", "version_sha256", "evidence_basis", "access_note",
                 "original_review_reference", "distribution_reference"}
BASES = {"preserved_original", "reviewed_original", "metadata_only", "inaccessible"}


class AnalystPacketRefused(ValueError):
    """Unsafe, incomplete or non-substantive assignment input."""


def digest(value):
    raw = value if isinstance(value, bytes) else (value.encode("utf-8") if isinstance(value, str)
          else json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise AnalystPacketRefused(message)


def line(value, minimum=1, maximum=1500):
    return (isinstance(value, str) and minimum <= len(value.strip()) <= maximum
            and value == value.strip() and not any(ord(c) < 32 for c in value))


def web_url(value):
    if not line(value):
        return False
    p = urlsplit(value)
    return p.scheme in ("https", "http") and bool(p.hostname) and not p.username and not p.password


def validate_sources(sources):
    require(isinstance(sources, list) and 1 <= len(sources) <= 12, "one to twelve scoped source references required")
    seen = set()
    for s in sources:
        require(isinstance(s, dict) and set(s) == SOURCE_FIELDS, "source references contain missing or forbidden fields; no source bodies")
        require(line(s["id"], maximum=100) and s["id"] not in seen, "invalid or duplicate source identity")
        seen.add(s["id"])
        require(web_url(s["url"]), "source reference must be a canonical web URL")
        require(s["evidence_basis"] in BASES, "unknown source access basis")
        require(line(s["access_note"], 8) and line(s["distribution_reference"], 12), "source-specific access and distribution decision references required")
        if s["evidence_basis"] in ("preserved_original", "reviewed_original"):
            require(isinstance(s["version_sha256"], str) and HEX.fullmatch(s["version_sha256"])
                    and line(s["original_review_reference"], 12), "inspected originals require version pins and actual original-review references")
        else:
            require(s["version_sha256"] is None and s["original_review_reference"] is None,
                    "metadata/inaccessible references must not claim an inspected version")
    return sources


def build_packet(worksheet, *, thesis, questions, sources, distribution, deadline):
    """Return manifest, deterministic DOCX, and a source-scoped research brief.

    ``distribution`` is trusted operator input, not analyst-return data. Its
    reference must point to the real owner source-use decision; this module does
    not establish the truth or legality of that decision. Production adapters
    must resolve current per-family policy before calling this offline builder.
    """
    sections = editable_sections(worksheet)
    cited = _references(worksheet)
    header, _, appendix = _split(worksheet)
    match = re.search(r"^Packet: (IPR-\d{4}-\d{2}-\d{2}(?:-[a-z][a-z0-9-]{0,79})?)$", worksheet, re.M)
    require(match is not None, "existing Brief packet identity required")
    week = match.group(1)[4:14]
    require(date.fromisoformat(week).weekday() == 5, "packet must name a reporting Saturday")
    validate_sources(sources)
    by_id = {s["id"]: s for s in sources}
    program_checked = {}
    for kind, ident, url in cited:
        key = ("record:" if kind == "Record" else "external:") + ident
        require(key in by_id and by_id[key]["url"] == url, "every cited source requires the same scoped identity and URL")
        require(by_id[key]["evidence_basis"] in ("preserved_original", "reviewed_original"),
                "HELD: every source cited by the manuscript needs an inspected, version-pinned original")
        program_checked[key] = "worksheet_identity_and_url_matched; original version/access owner-attested"
    # External research packets sometimes already pin captured original text.
    # Enforce any available exact version instead of replacing it with a claim.
    current = None
    for row in worksheet.splitlines():
        record = re.match(r"^Record ([0-9]+) \|", row)
        external = re.match(r"^External source ([A-Za-z0-9_-]+) \|", row)
        if record or external:
            current = ("record:" if record else "external:") + (record or external).group(1)
        elif current in by_id and row.startswith("Version/content SHA-256: "):
            pinned = row.split(": ", 1)[1]
            if HEX.fullmatch(pinned):
                require(by_id[current]["version_sha256"] == pinned, "offered original version differs from existing worksheet provenance")
                program_checked[current] = "worksheet_identity_url_and_version_matched; access owner-attested"
    require(any(s["evidence_basis"] in ("preserved_original", "reviewed_original") for s in sources),
            "HELD: metadata or inaccessible links alone cannot support an analyst manuscript")
    require(line(thesis, 30, 1200), "specific current analytical thesis required")
    require(isinstance(questions, list) and 1 <= len(questions) <= 2, "one or two interpretation-changing questions required")
    for q in questions:
        require(isinstance(q, dict) and set(q) == {"question", "why_it_matters", "source_ids"}, "invalid research question")
        require(line(q["question"], 35, 1000) and "?" in q["question"]
                and line(q["why_it_matters"], 35, 1200), "question needs a specific uncertainty and consequence for the thesis")
        require(not re.search(r"^(?:please )?(?:verify|check|review) (?:all|every|the records|the sources)\b", q["question"], re.I),
                "generic record verification is not analytical review")
        require(isinstance(q["source_ids"], list) and q["source_ids"] and len(set(q["source_ids"])) == len(q["source_ids"])
                and set(q["source_ids"]) <= set(by_id), "research questions must name offered source identities")
    when = datetime.fromisoformat(deadline)
    require(when.tzinfo is not None and when.utcoffset() is not None, "deadline must include a timezone offset")
    require(isinstance(distribution, dict) and set(distribution) == {
        "owner_confirmed", "reviewed_by", "reference", "worksheet_sha256", "source_pins_sha256", "scope"},
        "exact owner distribution decision required")
    require(distribution["owner_confirmed"] is True and line(distribution["reviewed_by"], 3)
            and line(distribution["reference"], 12), "owner-reviewed source distribution decision required")
    require(distribution["worksheet_sha256"] == digest(worksheet)
            and distribution["source_pins_sha256"] == digest(sources)
            and distribution["scope"] == "analyst-review-manuscript-and-links-only",
            "distribution decision does not bind exact manuscript, sources and analyst scope")
    manifest = {"schema": SCHEMA, "packet": match.group(1), "week_ending": week,
        "worksheet_sha256": digest(worksheet), "source_pins_sha256": digest(sources),
        "worksheet_header_sha256": digest(header), "worksheet_appendix_sha256": digest(appendix),
        "thesis": thesis, "questions": deepcopy(questions), "sources": deepcopy(sources),
        "distribution": deepcopy(distribution), "deadline": deadline,
        "sections": sections, "source_validation": program_checked, "status": "SATURDAY_PROVISIONAL",
        "factual_review_complete": False, "publication_authorized": False,
        "credit_proposal": None}
    manifest["assignment_id"] = match.group(1) + "-research-" + digest(manifest)[:16]
    prefix = ["INDO-PACIFIC RECORD — RESEARCH ANALYST ASSIGNMENT",
              "PROVISIONAL · NOT APPROVED FOR PUBLICATION", "Assignment: " + manifest["assignment_id"],
              "Worksheet SHA-256: " + manifest["worksheet_sha256"], "Return target: " + deadline,
              "Current thesis: " + thesis,
              "Please challenge the interpretation using the scoped original sources below. Disagreement, abstention and evidence gaps are useful outcomes.",
              "Source links are not proof of access. No publisher originals or private synopses are included. Ben retains source-to-claim and credit decisions."]
    for q in questions:
        prefix.extend(["Research question: " + q["question"], "Why this could change the argument: " + q["why_it_matters"],
                       "Relevant sources: " + ", ".join(q["source_ids"])])
    source_lines = ["SCOPED SOURCE REFERENCES — DO NOT EDIT"]
    for s in sources:
        source_lines.extend([s["id"] + " | " + s["evidence_basis"], s["url"],
            "Version: " + (s["version_sha256"] or "UNINSPECTED — NO ORIGINAL VERSION CLAIM"),
            "Access/limits: " + s["access_note"]])
    suffix = ["END OF SOURCE REFERENCES", "Nothing in this packet assigns authorship or approves factual claims."]
    manifest["protected_prefix"] = prefix
    manifest["protected_suffix"] = source_lines + suffix
    manifest["manifest_sha256"] = digest(manifest)
    doc = Document()
    doc.core_properties.title = "IPR provisional research assignment"
    doc.core_properties.author = "Indo-Pacific Record"
    for text in prefix:
        doc.add_paragraph(text)
    doc.add_paragraph(MANUSCRIPT_BEGIN)
    for key, value in sections:
        doc.add_paragraph(key, style="Heading 2")
        for p in value.split("\n\n"):
            doc.add_paragraph(p)
    doc.add_paragraph(MANUSCRIPT_END)
    doc.add_paragraph(MEMO_BEGIN)
    doc.add_paragraph("Research memo: describe material findings, source links/locators, proposed changes and remaining uncertainty. You may leave Word comments instead. Optional maps/GIS only if useful.")
    doc.add_paragraph(MEMO_END)
    for text in source_lines + suffix:
        doc.add_paragraph(text)
    raw = BytesIO()
    doc.save(raw)
    stable = BytesIO()
    with ZipFile(raw) as src, ZipFile(stable, "w") as out:
        for item in src.infolist():
            item.date_time = (1980, 1, 1, 0, 0, 0)
            out.writestr(item, src.read(item.filename))
    brief = "\n\n".join(prefix + source_lines + suffix) + "\n"
    return manifest, stable.getvalue(), brief


def validate_manifest(manifest):
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA, "not an analyst assignment")
    expected = manifest.get("manifest_sha256")
    require(isinstance(expected, str) and HEX.fullmatch(expected)
            and expected == digest({k: v for k, v in manifest.items() if k != "manifest_sha256"}),
            "assignment manifest changed")
    validate_sources(manifest["sources"])
    return manifest
