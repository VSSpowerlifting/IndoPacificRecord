"""Extract a frozen DOCX's exact text and inline links; never rewrite prose.

Paragraph indices are explicit editorial selections, zero-based. Output is an
intermediate JSON snapshot, not publication approval or a numbered Brief.

A Saturday provisional manuscript (keyword or header/footer label) is refused
unless a passed Sunday recheck receipt binds this exact DOCX's SHA-256.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PROVISIONAL_KEYWORD = "ipr-saturday-provisional"
PROVISIONAL_TEXT = "SATURDAY PROVISIONAL"


def is_saturday_provisional(archive):
    """Any surviving marker counts: core keyword, body, header or footer text."""
    for name in archive.namelist():
        if name == "docProps/core.xml":
            if PROVISIONAL_KEYWORD in archive.read(name).decode("utf-8", "replace"):
                return True
        elif name.startswith("word/") and name.endswith(".xml"):
            part = ET.fromstring(archive.read(name))
            if PROVISIONAL_TEXT in "".join(t.text or "" for t in part.iter(W + "t")):
                return True
    return False


def extract(path, *, expected_sha256, title_index, subtitle_index, body_start, body_stop,
            provisional_recheck=None):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("DOCX does not match frozen manuscript SHA-256")
    with ZipFile(path) as archive:
        if is_saturday_provisional(archive):
            if provisional_recheck is None:
                raise ValueError("Saturday provisional manuscript needs its Sunday recheck receipt")
            from scripts.weekly_briefs_saturday_audit import load_recheck_receipt
            load_recheck_receipt(provisional_recheck, manuscript_sha256=expected_sha256)
        doc = ET.fromstring(archive.read("word/document.xml"))
        rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
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
    return {"title": text(paragraphs[title_index]),
            "dek": text(paragraphs[subtitle_index]),
            "manuscript_sha256": expected_sha256,
            "body_paragraphs": body,
            "publisher_references": [{"id": ident, "url": url} for url, ident in sources.items()]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("docx", type=Path)
    p.add_argument("--expected-sha256", required=True)
    for field in ("title-index", "subtitle-index", "body-start", "body-stop"):
        p.add_argument("--" + field, required=True, type=int)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--provisional-recheck", type=Path,
                   help="passed Sunday recheck receipt for a Saturday provisional DOCX")
    args = p.parse_args()
    result = extract(args.docx, expected_sha256=args.expected_sha256,
                     title_index=args.title_index, subtitle_index=args.subtitle_index,
                     body_start=args.body_start, body_stop=args.body_stop,
                     provisional_recheck=args.provisional_recheck)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
