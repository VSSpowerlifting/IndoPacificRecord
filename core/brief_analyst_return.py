"""Bounded Word/memo intake; extracted assertions are untrusted, not facts.

This module never follows links or executes embedded content. Track changes,
fields, tables, text boxes and footnotes are explicitly unsupported: return an
accepted/rejected-changes copy or a concise memo instead of silently losing data.
"""
from __future__ import annotations

from io import BytesIO
import re
import zlib
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from core.brief_analyst_packet import (
    AnalystPacketRefused, MANUSCRIPT_BEGIN, MANUSCRIPT_END, MEMO_BEGIN, MEMO_END,
    digest, require, validate_manifest, web_url,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MAX_BYTES, MAX_EXPANDED, MAX_ENTRIES = 3_000_000, 30_000_000, 200
URL = re.compile(r"https?://[^\s<>\"\]\)]+")
MEMO_PLACEHOLDER = "Research memo: describe material findings, source links/locators, proposed changes and remaining uncertainty. You may leave Word comments instead. Optional maps/GIS only if useful."


def _xml(raw):
    require(b"<!DOCTYPE" not in raw.upper() and b"<!ENTITY" not in raw.upper(), "DTD/entities are forbidden in Word returns")
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AnalystPacketRefused("malformed Word XML") from exc


def _paragraph_text(p):
    return "".join((n.text or "") if n.tag == W + "t" else ("\n" if n.tag == W + "br" else "\t")
                   for n in p.iter() if n.tag in {W + "t", W + "br", W + "tab"})


def _references(text, manifest, extra_urls=()):
    known = {s["url"]: s for s in manifest["sources"]}
    refs = []
    for url in dict.fromkeys([*URL.findall(text), *extra_urls]):
        require(web_url(url), "unsafe returned source reference")
        source = known.get(url)
        refs.append({"url": url, "source_id": source["id"] if source else None,
                     "version_sha256": source["version_sha256"] if source else None,
                     "requires_independent_source_review": True})
    return refs


def _finding(identifier, text, origin, manifest, anchor="", extra_urls=()):
    return {"finding_id": identifier, "assertion": text, "origin": origin,
            "anchor": anchor, "references": _references(text, manifest, extra_urls),
            "factual_verification": False}


def extract_docx(manifest, word_bytes):
    """Extract comments, memo and edited prose against the TRUSTED manifest.

    An unchanged document is a valid no-change response. A changed body is a
    proposal only; protected instructions/source references must remain exact.
    """
    validate_manifest(manifest)
    require(isinstance(word_bytes, bytes) and 0 < len(word_bytes) <= MAX_BYTES,
            "Word return must be nonempty and at most 3 MB")
    hyperlinks = []
    relationship_targets = {}
    try:
        with ZipFile(BytesIO(word_bytes)) as archive:
            entries = archive.infolist()
            names = [e.filename for e in entries]
            require(len(entries) <= MAX_ENTRIES and len(set(names)) == len(names)
                    and sum(e.file_size for e in entries) <= MAX_EXPANDED,
                    "Word archive exceeds extraction bounds or has duplicate entries")
            require(all(not e.flag_bits & 1 and not e.filename.startswith(("/", "\\"))
                        and ".." not in e.filename.split("/") for e in entries), "unsafe Word archive entry")
            require("word/document.xml" in names, "Word main document missing")
            require(not any(n.lower().endswith((".bin", ".vba", ".exe"))
                            or "/embeddings/" in n.lower() or "vbaproject" in n.lower() for n in names),
                    "macros and embedded objects are forbidden")
            trees = {}
            for name in names:
                if name.endswith((".xml", ".rels")):
                    raw = archive.read(name)
                    require(b"macroEnabled" not in raw, "macro-enabled Word content is forbidden")
                    trees[name] = _xml(raw)
            for name, tree in trees.items():
                if name.endswith(".rels"):
                    part = name.replace("/_rels/", "/").removesuffix(".rels")
                    targets = relationship_targets.setdefault(part, {})
                    for rel in tree:
                        require(rel.get("Id") not in targets, "duplicate Word relationship identity")
                        targets[rel.get("Id")] = None
                        if rel.get("TargetMode") == "External":
                            target = rel.get("Target", "")
                            require(rel.get("Type", "").endswith("/hyperlink") and web_url(target),
                                    "external includes/relationships are forbidden")
                            hyperlinks.append(target)
                            targets[rel.get("Id")] = target
            body = trees["word/document.xml"]
            for tree in trees.values():
                tags = {node.tag for node in tree.iter()}
                require(not tags.intersection({W + t for t in ("ins", "del", "moveFrom", "moveTo")}),
                        "tracked changes unsupported; accept/reject changes or return a research memo")
                require(not tags.intersection({W + t for t in (
                    "tbl", "txbxContent", "altChunk", "object", "fldSimple", "instrText", "footnote", "endnote")}),
                    "unsupported Word tables, fields, text boxes, footnotes or embedded content; return a plain research memo")
            def links(node, part):
                found = []
                for link in node.iter(W + "hyperlink"):
                    ident = link.get(R + "id")
                    if ident is not None:
                        require(ident in relationship_targets.get(part, {}), "unresolved Word hyperlink relation")
                        target = relationship_targets[part][ident]
                        if target is not None:
                            found.append(target)
                return found
            paragraph_nodes = list(body.iter(W + "p"))
            paragraphs = [_paragraph_text(p) for p in paragraph_nodes]
            for marker in (MANUSCRIPT_BEGIN, MANUSCRIPT_END, MEMO_BEGIN, MEMO_END):
                require(paragraphs.count(marker) == 1, "missing or duplicated protected Word boundaries")
            a, b, c, d = [paragraphs.index(m) for m in (MANUSCRIPT_BEGIN, MANUSCRIPT_END, MEMO_BEGIN, MEMO_END)]
            require(a < b < c < d and b + 1 == c, "reordered or altered Word boundaries")
            require(paragraphs[:a] == manifest["protected_prefix"]
                    and paragraphs[d + 1:] == manifest["protected_suffix"], "assignment identity, instructions or source appendix was altered")
            editable = paragraphs[a + 1:b]
            old_sections = manifest["sections"]
            keys = [key for key, _ in old_sections]
            require(all(editable.count(key) == 1 for key in keys), "manuscript sections missing or duplicated")
            positions = [editable.index(key) for key in keys]
            require(positions == sorted(positions) and positions[0] == 0, "manuscript sections reordered")
            new_sections = []
            for i, key in enumerate(keys):
                end = positions[i + 1] if i + 1 < len(keys) else len(editable)
                text = "\n\n".join(editable[positions[i] + 1:end]).strip()
                require(bool(text), "empty returned manuscript section")
                new_sections.append((key, text))
            findings = []
            memo = "\n\n".join(t for t in paragraphs[c + 1:d] if t != MEMO_PLACEHOLDER).strip()
            if memo:
                findings.append(_finding("memo", memo, "analyst-memo", manifest, extra_urls=[
                    url for p in paragraph_nodes[c + 1:d] for url in links(p, "word/document.xml")]))
            comments_tree = trees.get("word/comments.xml")
            starts = {n.get(W + "id") for n in body.iter(W + "commentRangeStart")}
            ends = {n.get(W + "id") for n in body.iter(W + "commentRangeEnd")}
            comments = list(comments_tree) if comments_tree is not None else []
            ids = [node.get(W + "id") for node in comments]
            require(len(ids) == len(set(ids)) and set(ids) == starts == ends,
                    "orphaned, duplicated or unsupported Word comment anchors")
            for node in comments:
                ident = node.get(W + "id")
                require(ident is not None and ident.isdigit(), "invalid Word comment identifier")
                text = "\n".join(_paragraph_text(p) for p in node.iter(W + "p")).strip()
                require(bool(text), "empty Word comment")
                anchor, active = [], False
                for elem in body.iter():
                    if elem.tag == W + "commentRangeStart" and elem.get(W + "id") == ident:
                        active = True
                    elif elem.tag == W + "commentRangeEnd" and elem.get(W + "id") == ident:
                        active = False
                    elif active and elem.tag == W + "t":
                        anchor.append(elem.text or "")
                findings.append(_finding("comment:" + ident, text, "word-comment", manifest, "".join(anchor),
                                         extra_urls=links(node, "word/comments.xml")))
            for (key, old), (_, new) in zip(old_sections, new_sections):
                if old != new:
                    findings.append(_finding("edit:" + key, new, "proposed-manuscript-edit", manifest, old,
                        extra_urls=[url for p in paragraph_nodes[a + 1:b] for url in links(p, "word/document.xml")]))
    except (BadZipFile, KeyError, RuntimeError, OSError, zlib.error) as exc:
        raise AnalystPacketRefused("invalid or unreadable Word archive") from exc
    payload = {"schema": "ipr-research-analyst-return/1", "assignment_id": manifest["assignment_id"],
        "manifest_sha256": manifest["manifest_sha256"], "worksheet_sha256": manifest["worksheet_sha256"],
        "returned_file_sha256": digest(word_bytes), "sections": new_sections,
        "findings": findings, "external_hyperlinks": [dict(url=u, requires_independent_source_review=True) for u in dict.fromkeys(hyperlinks)],
        "no_change": not findings, "factual_review_complete": False, "publication_authorized": False}
    payload["return_receipt_sha256"] = digest(payload)
    return payload


def extract_memo(manifest, memo):
    """A nontechnical analyst may return plain text instead of Word comments."""
    validate_manifest(manifest)
    require(isinstance(memo, dict) and set(memo) == {"assignment_id", "worksheet_sha256", "text"}
            and memo["assignment_id"] == manifest["assignment_id"]
            and memo["worksheet_sha256"] == manifest["worksheet_sha256"], "memo belongs to another assignment/manuscript")
    require(isinstance(memo["text"], str) and 0 < len(memo["text"].strip()) <= 20_000, "memo must be nonempty and bounded")
    out = {"schema": "ipr-research-analyst-return/1", "assignment_id": manifest["assignment_id"],
           "manifest_sha256": manifest["manifest_sha256"], "worksheet_sha256": manifest["worksheet_sha256"],
           "returned_file_sha256": digest(memo), "sections": manifest["sections"],
           "findings": [_finding("memo", memo["text"], "analyst-memo", manifest)],
           "external_hyperlinks": [], "no_change": False,
           "factual_review_complete": False, "publication_authorized": False}
    out["return_receipt_sha256"] = digest(out)
    return out
