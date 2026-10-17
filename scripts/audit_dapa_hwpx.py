#!/usr/bin/env python3
"""Read-only SHA-pinned HWPX structure audit; never endorses source reuse.

No source HTTP, originals upload, public data, editorial approval, or model.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import stat
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SHA = re.compile(r"[0-9a-f]{64}\Z")
SECTION = re.compile(r"Contents/section([0-9]+)\.xml\Z")

class AuditHold(ValueError):
    """Explicit non-publication hold."""

def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""

def audit(path, expected_sha256, expected_bytes=None, expected_characters=None):
    path = Path(path).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise AuditHold("ordinary_absolute_local_file_required")
    if not isinstance(expected_sha256, str) or not SHA.fullmatch(expected_sha256):
        raise AuditHold("expected_sha256_invalid")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 2_000_000:
        raise AuditHold("original_size_invalid")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise AuditHold("original_sha256_mismatch")
    if expected_bytes is not None and len(raw) != expected_bytes:
        raise AuditHold("original_byte_count_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            names = [x.filename for x in members]
            if (len(names) > 200 or len(names) != len(set(names))
                    or sum(x.file_size for x in members) > 10_000_000):
                raise AuditHold("unsafe_hwpx_archive_shape")
            if any(x.filename.startswith("/") or ".." in Path(x.filename).parts
                   or stat.S_IFMT(x.external_attr >> 16) == stat.S_IFLNK
                   for x in members):
                raise AuditHold("unsafe_hwpx_member_path")
            sections = sorted(
                (x for x in members if SECTION.fullmatch(x.filename)),
                key=lambda x: int(SECTION.fullmatch(x.filename)[1]))
            if not sections:
                raise AuditHold("hwpx_sections_missing")
            count = dict(paragraphs=0, empty_paragraphs=0, tables=0,
                         table_rows=0, table_cells=0, pictures=0,
                         equations=0, other_shapes=0)
            lines = []
            for section in sections:
                xml = z.read(section).decode("utf-8", "strict")
                if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                    raise AuditHold("xml_external_entities_refused")
                for node in ET.fromstring(xml).iter():
                    kind = local(node.tag)
                    if kind == "tbl": count["tables"] += 1
                    elif kind == "tr": count["table_rows"] += 1
                    elif kind == "tc": count["table_cells"] += 1
                    elif kind in ("pic", "img"): count["pictures"] += 1
                    elif kind == "equation": count["equations"] += 1
                    elif kind in ("line", "rect", "ellipse", "arc", "polygon"):
                        count["other_shapes"] += 1
                    elif kind == "p":
                        count["paragraphs"] += 1
                        chunks = ["".join(t.itertext()) for run in node
                                  if local(run.tag) == "run" for t in run
                                  if local(t.tag) == "t"]
                        line = "".join(chunks).strip()
                        if line: lines.append(line)
                        else: count["empty_paragraphs"] += 1
            if not lines:
                raise AuditHold("hwpx_no_extractable_original_text")
            extracted = "\n".join(lines)
            if expected_characters is not None and len(extracted) != expected_characters:
                raise AuditHold("hwpx_text_character_count_mismatch")
            binary_members = sum(name.startswith(("BinData/", "Pictures/"))
                                 for name in names)
    except (zipfile.BadZipFile, ET.ParseError, UnicodeError,
            RuntimeError, KeyError, OSError) as exc:
        raise AuditHold("invalid_hwpx_original_or_xml") from exc
    return {
        "schema": "ipr-dapa-local-original-structure-audit/1",
        "offline_only": True,
        "original_sha256_verified": True,
        "original_sha256": digest,
        "original_bytes": len(raw),
        "sections": len(sections),
        "text_characters": len(extracted),
        "extracted_text_sha256": hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
        "nontext_zip_member_count": binary_members,
        "structure": count,
        "requires_human_table_and_reading_order_review": True,
        "korean_semantic_review_approved": False,
        "source_use_or_publication_approved": False,
        "automated_production_admission_approved": False,
        "original_or_text_exported": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--local-hwpx", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--expected-bytes", type=int)
    p.add_argument("--expected-characters", type=int)
    p.add_argument("--private-receipt", type=Path)
    args = p.parse_args(argv)
    try:
        report = audit(args.local_hwpx, args.expected_sha256,
                       args.expected_bytes, args.expected_characters)
        if args.private_receipt:
            dest = args.private_receipt.expanduser()
            if (not dest.is_absolute() or dest.is_symlink() or dest.exists()
                    or not dest.parent.is_dir() or dest.parent.is_symlink()
                    or dest.parent.stat().st_mode & 0o077):
                raise AuditHold("private_receipt_requires_new_file_in_restricted_directory")
            with dest.open("x", encoding="utf-8",
                           opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except AuditHold as exc:
        print(json.dumps({"status": "HOLD", "reason_code": str(exc),
                          "network_requests": 0,
                          "publication_approved": False}, sort_keys=True))
        return 2

if __name__ == "__main__":
    sys.exit(main())
