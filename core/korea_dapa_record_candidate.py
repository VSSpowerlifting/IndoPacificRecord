"""Offline DAPA original-to-record candidate selection; never a publication.

Binds one preserved Policy Briefing HWPX original to its pinned private shadow
row, confirms DAPA is the sole structural issuer, and separates the release's
government-authored body prose from masthead, timing, headline, contact and
picture elements. Expected values come only from the SHA-pinned DB row.

Rights basis: the preserved Policy Briefing article page carries a published
KOGL Type 0 notice for its *text*. When a captured page is supplied, that mark
is replayed from the hash-bound bytes (core.korea_dapa_archived_kogl_replay).
Applying the page-text mark to the linked HWPX's DAPA-authored prose is a
documented interpretation, not an explicit attachment licence, and is not
decided here. This module prepares a local offline candidate only: it
authorizes no model input, no public original or explanation, no HWPX/media
reuse and no production admission.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from core.korea_dapa_archived_kogl_replay import MarkHold, replay_capture_file
from core.korea_dapa_private_to_production import (
    HASH, ISSUER, NEWS, PREFIX, REPUBLISHER, RUN, URL_PREFIX)
from core.korea_text_only_exception_replay import inspect_text_only
from scripts.audit_dapa_hwpx import AuditHold, audit_with_items

SCHEMA = "ipr-dapa-record-candidate/1"
PRIVATE_SCHEMA = "ipr-dapa-record-candidate-private-input/1"
SLUG = "kr_policy_dapa_releases"
ISSUER_KO = "방위사업청"
LICENSE_NOTICE = "KOGL_type_0_text_notice_only"
# Policy Briefing listing artifact with no row in the pinned archive.
REFUSED_IDENTITIES = frozenset({PREFIX + "156787071"})
KST = timezone(timedelta(hours=9))
STAMP = re.compile(
    r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.\s*\((.)\)\s*(\d{1,2}):(\d{2})\Z")
LEAD_DATE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일\s*\((.)\)")
WEEKDAYS = "월화수목금토일"
PHONE = re.compile(r"\(?0\d{1,2}-\d{3,4}-\d{4}\)?")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
AGENCY_LABEL = re.compile(r"\([^()0-9]{2,20}\)\Z")
JOINT_LEAD = re.compile(r"\A\S+\([^)]*\)\s*(?:과|와|및)\s*\S+\([^)]*\)")
QUOTE = re.compile(r"[“”\"]")
# Heading punctuation the template varies: middle dots and their look-alikes.
FOLD = str.maketrans({"·": "", "․": "", "‧": "", "ㆍ": "", "•": "", "∙": ""})


class CandidateHold(ValueError):
    """Integrity failure; no candidate is produced for this version."""


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stamp(value):
    m = STAMP.fullmatch(value)
    if not m:
        return None
    y, mo, d, wd, h, mi = m.groups()
    when = datetime(int(y), int(mo), int(d), int(h), int(mi), tzinfo=KST)
    return when if WEEKDAYS[when.weekday()] == wd else None


def read_pinned_row(db_path, db_sha256, source_identity):
    """Return the shadow row only from the exact SHA-pinned private DB."""
    if source_identity in REFUSED_IDENTITIES:
        raise CandidateHold("refused_orphan_listing_version")
    if not (isinstance(source_identity, str) and source_identity.startswith(PREFIX)
            and NEWS.fullmatch(source_identity[len(PREFIX):])):
        raise CandidateHold("source_identity_invalid")
    if not (isinstance(db_sha256, str) and HASH.fullmatch(db_sha256)):
        raise CandidateHold("db_sha256_invalid")
    db_path = Path(db_path).expanduser()
    if not db_path.is_absolute() or db_path.is_symlink() or not db_path.is_file():
        raise CandidateHold("ordinary_absolute_db_file_required")
    if hashlib.sha256(db_path.read_bytes()).hexdigest() != db_sha256:
        raise CandidateHold("db_sha256_mismatch")
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    try:
        con.row_factory = sqlite3.Row
        if [r[0] for r in con.execute("select desk from shadow_meta")] != ["korea_dapa"]:
            raise CandidateHold("db_desk_not_korea_dapa")
        row = con.execute("select * from shadow_records where source_identity=?",
                          (source_identity,)).fetchone()
    except sqlite3.Error as exc:
        raise CandidateHold("db_schema_invalid") from exc
    finally:
        con.close()
    if row is None:
        raise CandidateHold("source_identity_not_in_pinned_db")
    row = dict(row)
    try:
        meta = json.loads(row["metadata_json"])
    except ValueError as exc:
        raise CandidateHold("db_metadata_invalid") from exc
    news_id = source_identity[len(PREFIX):]
    if (row["url"] != URL_PREFIX + news_id or row["source_slug"] != SLUG
            or row["language_tag"] != "ko" or not RUN.fullmatch(row["first_seen_run"])
            or meta.get("source_identity") != source_identity
            or meta.get("issuer") != ISSUER_KO
            or meta.get("publisher_text_license_notice") != LICENSE_NOTICE
            or meta.get("content_sha256") != row["content_sha256"]
            or meta.get("capture_sha256") != row["capture_sha256"]
            or not HASH.fullmatch(str(meta.get("document_capture_sha256")))):
        raise CandidateHold("db_row_identity_or_provenance_drift")
    if _sha(row["text_original"]) != row["content_sha256"]:
        raise CandidateHold("db_text_content_sha256_mismatch")
    try:
        date.fromisoformat(row["published_date"])
    except ValueError as exc:
        raise CandidateHold("db_published_date_invalid") from exc
    return row, meta


def _segments(items):
    """Group located items into ordered top-level tables and body runs."""
    out = []
    for kind, line, table, cell in items:
        key = ("table", table) if table is not None else ("body", None)
        if not out or out[-1]["key"] != key:
            out.append({"key": key, "cells": {}, "lines": [], "pictures": 0})
        seg = out[-1]
        if kind == "picture":
            seg["pictures"] += 1
        else:
            seg["lines"].append(line)
            seg["cells"].setdefault(cell, []).append(line)
    return out


def classify(items):
    """Map the DAPA release template; any unrecognized shape is a hold."""
    segs = _segments(items)
    shape = [s["key"][0] for s in segs]
    base = ["table"] * 3 + ["body", "table"]
    if shape not in (base, base + ["table"]):
        raise CandidateHold("unrecognized_dapa_template")
    mast, timing, head, body, contact = segs[:5]
    pictures_tail = segs[5] if len(segs) == 6 else None
    if mast["lines"] != ["보도자료"]:
        raise CandidateHold("masthead_not_recognized")
    t = timing["lines"]
    if timing["pictures"] or len(t) != 4 or t[0] != "보도시점" or t[2] != "배포":
        raise CandidateHold("timing_block_not_recognized")
    distributed = _stamp(t[3])
    embargo = None if t[1] == "배포 즉시" else _stamp(t[1])
    if distributed is None or (t[1] != "배포 즉시" and embargo is None):
        raise CandidateHold("timing_values_not_recognized")
    cells = sorted(head["cells"], key=lambda c: (c is None, c))
    headline = head["cells"][cells[0]] if cells else []
    subheads = [x for c in cells[1:] for x in head["cells"][c]]
    if (head["pictures"] or not headline or any(x.startswith("-") for x in headline)
            or not all(x.startswith("-") for x in subheads)):
        raise CandidateHold("headline_block_not_recognized")
    if body["pictures"] or not body["lines"]:
        raise CandidateHold("body_not_recognized")
    if contact["lines"][:1] != ["담당 부서"]:
        raise CandidateHold("contact_block_not_recognized")
    if pictures_tail is not None and pictures_tail["lines"]:
        raise CandidateHold("trailing_text_after_contact_block")
    return {
        "masthead_pictures": mast["pictures"],
        "distributed": distributed, "embargo": embargo,
        "headline": headline, "subheads": subheads,
        "body": body["lines"], "contact": contact,
        "trailing_pictures": pictures_tail["pictures"] if pictures_tail else 0,
    }


def issuer_resolution(shape):
    """Structural sole-issuer evidence; reasons name every joint signal."""
    reasons = []
    contact = shape["contact"]
    if contact["lines"].count("담당 부서") != 1:
        reasons.append("multiple_responsible_department_blocks")
    if any(AGENCY_LABEL.fullmatch(x) and not PHONE.search(x) for x in contact["lines"]):
        reasons.append("agency_label_cell_in_contact_block")
    lead = shape["body"][0]
    if JOINT_LEAD.match(lead):
        reasons.append("joint_issuer_lead_sentence")
    if not lead.startswith(ISSUER_KO):
        reasons.append("lead_sentence_not_attributed_to_dapa")
    return {"sole_issuer_structurally_confirmed": not reasons,
            "official_issuer": ISSUER, "official_republisher": REPUBLISHER,
            "reasons": reasons}


def _role(index, text):
    if index == 0:
        return "lead"
    if text.startswith(("*", "※")):
        return "annotation"
    if QUOTE.search(text):
        return "quotation_attribution_requires_review"
    return "body"


def build_candidate(db_path, db_sha256, source_identity, hwpx_path, as_of=None,
                    page_capture_path=None):
    """Return (public-safe receipt, private paragraphs or None).

    ``page_capture_path`` optionally replays the article-page KOGL Type 0 text
    mark from the preserved capture named by the pinned row's digest.
    """
    row, meta = read_pinned_row(db_path, db_sha256, source_identity)
    try:
        report, items = audit_with_items(
            hwpx_path, meta["document_capture_sha256"],
            expected_characters=len(row["text_original"]))
    except AuditHold as exc:
        raise CandidateHold(f"original_{exc}") from exc
    if not (report["extracted_text_sha256"] == row["content_sha256"]):
        raise CandidateHold("hwpx_text_does_not_match_pinned_row")
    shape = classify(items)
    issuer = issuer_resolution(shape)
    holds = [f"issuer:{r}" for r in issuer["reasons"]]
    license_mark = None
    if page_capture_path is not None:
        try:
            license_mark = replay_capture_file(
                page_capture_path, row["capture_sha256"], row["url"])
        except MarkHold as exc:
            holds.append(f"license_mark:{exc}")

    joined = " ".join(shape["headline"])
    if joined != row["title_original"]:
        holds.append("headline_punctuation_variant"
                     if joined.translate(FOLD) == row["title_original"].translate(FOLD)
                     else "headline_title_mismatch")
    published = date.fromisoformat(row["published_date"])
    if shape["distributed"].date() != published:
        holds.append("distribution_date_mismatch")
    as_of = as_of or datetime.now(timezone.utc)
    if shape["embargo"] is not None and shape["embargo"] > as_of:
        holds.append("embargo_not_elapsed")
    lead_dates = LEAD_DATE.findall(shape["body"][0])
    for mo, d, wd in lead_dates:
        if ((int(mo), int(d)) != (published.month, published.day)
                or WEEKDAYS[published.weekday()] != wd):
            holds.append("lead_date_mismatch")
            break

    body = shape["body"]
    prose = "\n".join(body)
    if PHONE.search(prose) or EMAIL.search(prose):
        holds.append("contact_detail_in_selected_prose")
    try:
        screen = inspect_text_only(prose.encode("utf-8"))
    except ValueError as exc:
        screen = None
        holds.append(f"text_screen_{exc}")
    if screen and (screen["third_party_indicators_present"]
                   or screen["alternate_license_indicators_present"]
                   or screen["sensitive_personal_or_restricted_indicators_present"]):
        holds.append("text_screen_indicator_present")
    paragraphs = [{"index": i, "sha256": _sha(x), "characters": len(x),
                   "role": _role(i, x)} for i, x in enumerate(body)]
    receipt = {
        "schema": SCHEMA,
        "status": "HOLD" if holds else "CANDIDATE",
        "reason_codes": holds,
        "source_identity": source_identity,
        "official_url": row["url"],
        "publisher_posted_date": row["published_date"],
        "evidence": {
            "pinned_db_sha256": db_sha256,
            "first_seen_run": row["first_seen_run"],
            "publisher_html_sha256": row["capture_sha256"],
            "original_hwpx_sha256": report["original_sha256"],
            "original_hwpx_bytes": report["original_bytes"],
            "full_text_sha256": row["content_sha256"],
            "full_text_characters": report["text_characters"],
            "extraction_matches_pinned_row": True,
        },
        "issuer_resolution": issuer,
        "selection": {
            "selected_component": "government_authored_body_prose",
            "selected_prose_sha256": _sha(prose),
            "selected_prose_characters": len(prose),
            "paragraphs": paragraphs,
            "headline_sha256": _sha(joined),
            "headline_matches_db_title_exactly": joined == row["title_original"],
            "subhead_count": len(shape["subheads"]),
            "lead_dates_checked": len(lead_dates),
            "embargo_value_present": shape["embargo"] is not None,
            "excluded_elements": {
                "masthead_label_lines": 1,
                "masthead_pictures": shape["masthead_pictures"],
                "timing_lines": 4,
                "contact_block_lines": len(shape["contact"]["lines"]),
                "contact_block_pictures": shape["contact"]["pictures"],
                "trailing_pictures": shape["trailing_pictures"],
            },
            "text_screen": screen,
        },
        "license_mark_replay": license_mark,
        "rights_basis": {
            "article_page_text": ("kogl_type0_page_notice_replayed"
                                  if license_mark else
                                  "kogl_type0_page_notice_recorded_by_collector_not_replayed"),
            "hwpx_attachment_prose": "interpretation_pending_owner_decision",
            "scope": "offline_preparation_only",
        },
        "network_requests": 0,
        "model_input_authorized": False,
        "public_component_authorized": False,
        "korean_semantic_review_approved": False,
        "publication_approved": False,
        "original_or_text_exported": False,
    }
    private = None
    if not holds:
        private = [{"index": p["index"], "sha256": p["sha256"], "role": p["role"],
                    "text": text} for p, text in zip(paragraphs, body)]
    return receipt, private


def write_private_input(dest, receipt, paragraphs):
    """Write prose only as a new 0600 file inside an owner-only directory."""
    if receipt["status"] != "CANDIDATE" or paragraphs is None:
        raise CandidateHold("private_input_requires_candidate")
    dest = Path(dest).expanduser()
    if (not dest.is_absolute() or dest.is_symlink() or dest.exists()
            or not dest.parent.is_dir() or dest.parent.is_symlink()
            or dest.parent.stat().st_mode & 0o077):
        raise CandidateHold("private_output_requires_new_file_in_restricted_directory")
    payload = {"schema": PRIVATE_SCHEMA, "receipt": receipt,
               "source": {"source_identity": receipt["source_identity"],
                          "official_url": receipt["official_url"],
                          "selected_prose_sha256":
                              receipt["selection"]["selected_prose_sha256"],
                          "paragraphs": paragraphs},
               "model_input_authorized": False,
               "public_component_authorized": False}
    with open(dest, "x", encoding="utf-8",
                   opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
