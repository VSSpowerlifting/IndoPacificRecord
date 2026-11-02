"""Extract a frozen DOCX's exact text and inline links; never rewrite prose.

Paragraph indices are explicit editorial selections, zero-based. Output is an
intermediate JSON snapshot, not publication approval or a numbered Brief.

Import does not decide whether a manuscript is releasable, but it carries
weekend editorial cycle provenance forward. A DOCX written for a Saturday
provisional draft holds the cycle Brief identity in a hidden custom property
and document variable; the snapshot then carries ``editorial_cycle``, and
readiness and approval require that Brief's own Sunday reconciliation
receipt (``core.brief_editorial_cycle``), which binds this DOCX's SHA-256.
Removing the visible labels or changing the stated author does not remove
it. Import fails closed: a DOCX without that provenance needs exactly one
declaration, ``--saturday-packet`` (the cycle packet it came from) or
``--independent``, and ``--independent`` is refused while any cycle signal
remains.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from core.brief_editorial_cycle import (
    DOCX_CYCLE_PROPERTY, DOCX_CYCLE_VARIABLE, PROVENANCE_KEY,
    SATURDAY_PROVISIONAL_KEYWORD, cycle_provenance, packet_identity,
)

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CUSTOM = "{http://schemas.openxmlformats.org/officeDocument/2006/custom-properties}"
# Any of these left in the DOCX means it came from a weekend cycle draft.
VISIBLE_SIGNALS = ("SATURDAY PROVISIONAL", "Saturday's daily run",
                   SATURDAY_PROVISIONAL_KEYWORD)


def cycle_signals(archive):
    """Return (hidden cycle identities, whether any visible cycle signal remains)."""
    names = set(archive.namelist())
    identities = []
    if "docProps/custom.xml" in names:
        for prop in ET.fromstring(archive.read("docProps/custom.xml")).iter(CUSTOM + "property"):
            if prop.get("name") == DOCX_CYCLE_PROPERTY:
                identities.append("".join(prop.itertext()).strip())
    if "word/settings.xml" in names:
        for var in ET.fromstring(archive.read("word/settings.xml")).iter(W + "docVar"):
            if var.get(W + "name") == DOCX_CYCLE_VARIABLE:
                identities.append((var.get(W + "val") or "").strip())
    parts = [n for n in names if n == "docProps/core.xml"
             or (n.startswith("word/") and n.endswith(".xml"))]
    visible = any(signal in archive.read(n).decode("utf-8", "replace")
                  for n in parts for signal in VISIBLE_SIGNALS)
    return identities, visible


def cycle_identity(identities, visible, *, saturday_packet=None, independent=False):
    """Decide the manuscript's provenance; None only for a declared independent Brief."""
    if independent and saturday_packet is not None:
        raise ValueError("declare either a Saturday packet or an independent Brief, not both")
    if len(set(identities)) > 1:
        raise ValueError("DOCX cycle provenance carriers disagree")
    found = identities[0] if identities else None
    if found is not None:
        cycle_provenance(found)  # raises on a malformed identity
    if independent:
        if found is not None or visible:
            raise ValueError("DOCX carries weekend editorial cycle signals; "
                             "it cannot be imported as an independent Brief")
        return None
    if saturday_packet is not None:
        declared = packet_identity(saturday_packet)
        if declared is None:
            raise ValueError("declared Saturday packet has no single Packet: identity")
        if found is not None and found != declared:
            raise ValueError("DOCX cycle provenance is for a different Brief than the packet")
        return declared
    if found is None:
        raise ValueError("DOCX has no weekend editorial cycle provenance; declare "
                         "--saturday-packet or --independent")
    return found


def extract(path, *, expected_sha256, title_index, subtitle_index, body_start, body_stop,
            saturday_packet=None, independent=False):
    """``saturday_packet`` is the cycle packet's text, when the DOCX came from one."""
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("DOCX does not match frozen manuscript SHA-256")
    with ZipFile(path) as archive:
        doc = ET.fromstring(archive.read("word/document.xml"))
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
        identity = cycle_identity(*cycle_signals(archive), saturday_packet=saturday_packet,
                                  independent=independent)
    if any(doc.iter(W + "ins")) or any(doc.iter(W + "del")):
        raise ValueError("resolve tracked changes before freezing the manuscript")
    links = {r.attrib["Id"]: r.attrib["Target"] for r in rels
             if r.attrib.get("Type", "").endswith("/hyperlink")}
    paragraphs = doc.find(W + "body").findall(W + "p")
    def text(element):
        return "".join(t.text or "" for t in element.iter(W + "t"))
    sources, body = {}, []
    for paragraph in paragraphs[body_start:body_stop]:
        runs = []
        for element in paragraph:
            if element.tag == W + "pPr":
                continue
            value = text(element)
            if not value:
                continue
            run = {"text": value}
            if element.tag == W + "hyperlink":
                url = links[element.attrib[R + "id"]]
                if url not in sources:
                    sources[url] = "s%d" % (len(sources) + 1)
                run["source"] = sources[url]
            if runs and runs[-1].get("source") == run.get("source"):
                runs[-1]["text"] += value
            else:
                runs.append(run)
        body.append(runs)
    result = {"title": text(paragraphs[title_index]),
              "dek": text(paragraphs[subtitle_index]),
              "manuscript_sha256": expected_sha256,
              "body_paragraphs": body,
              "publisher_references": [{"id": ident, "url": url} for url, ident in sources.items()]}
    if identity is not None:
        result[PROVENANCE_KEY] = cycle_provenance(identity)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("docx", type=Path)
    p.add_argument("--expected-sha256", required=True)
    for field in ("title-index", "subtitle-index", "body-start", "body-stop"):
        p.add_argument("--" + field, required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    origin = p.add_mutually_exclusive_group()
    origin.add_argument("--saturday-packet", type=Path,
                        help="private cycle packet .txt this DOCX was drafted from")
    origin.add_argument("--independent", action="store_true",
                        help="the manuscript was authored outside the weekend cycle")
    args = p.parse_args(argv)
    packet = (args.saturday_packet.read_text(encoding="utf-8-sig")
              if args.saturday_packet else None)
    try:
        result = extract(args.docx, expected_sha256=args.expected_sha256,
                         title_index=args.title_index, subtitle_index=args.subtitle_index,
                         body_start=args.body_start, body_stop=args.body_stop,
                         saturday_packet=packet, independent=args.independent)
    except ValueError as exc:
        p.error(str(exc))
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
