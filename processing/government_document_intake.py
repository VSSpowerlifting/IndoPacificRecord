"""Bibliographic-only intake into the common Daily official-link store.

No article, second corpus, private original or model call is created. All
public data is a projection of the portal's verified bibliographic table.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from core.collection.vietnam_government_documents import (FAMILY, ISSUER, PUBLISHER,
    METADATA_FIELDS, TYPES, canonical_url, digest, identity, need)
from core.regional_official_link_release import store_verified_links

POLICY = Path(__file__).resolve().parents[1] / "config/vietnam_vpcp_metadata_policy.json"


def policy():
    value = json.loads(POLICY.read_text())
    need(value == {"source_family": FAMILY,
        "decision_reference": "docs/engineering/VIETNAM_GOVERNMENT_DOCUMENTS_2026-10-23.md",
        "public_bibliographic_metadata": True, "external_model_transmission": False,
        "attachment_download": False, "public_document_body": False,
        "public_translation": False, "public_machine_explanation": False}, "vpcp_source_use_held")
    return value


def topics(metadata):
    """Conservative subject-index routing, not a full-document relevance claim."""
    subject = metadata["subject"].casefold()
    groups = {
        "Energy security": ("bảo đảm cung ứng điện", "an ninh năng lượng", "phát triển năng lượng", "kinh doanh xăng dầu"),
        "Aviation security": ("an ninh hàng không",),
        "Defense and maritime security": ("quốc phòng", "an ninh quốc gia", "biển đông", "an ninh biển"),
        "Strategic infrastructure": ("cảng biển", "đường sắt", "công trình trọng điểm quốc gia"),
        "Strategic industry": ("khoáng sản", "bán dẫn", "đất hiếm"),
    }
    return [name for name, phrases in groups.items() if any(p in subject for p in phrases)]


def validate(metadata):
    need(type(metadata) is dict and set(metadata) == METADATA_FIELDS, "vpcp_metadata_fields")
    need(metadata["issuer"] == ISSUER and metadata["publisher"] == PUBLISHER
         and metadata["document_type"] in TYPES, "vpcp_institution_or_type")
    need(canonical_url(metadata["official_url"]) == metadata["official_url"]
         and metadata["official_url"].endswith("docid=" + metadata["document_id"]), "vpcp_identity")
    need(date.fromisoformat(metadata["issue_date"]).isoformat() == metadata["issue_date"], "vpcp_issue_date")


def admit(conn, captures, *, source_sha, run_id, observed_utc):
    """Caller holds the DB transaction; every exception rolls back that run."""
    rules = policy()
    need(re.fullmatch(r"[a-f0-9]{40}", source_sha) and re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", run_id),
         "vpcp_provenance_invalid")
    added = unchanged = revised = filtered = 0
    for metadata, capture_sha in captures:
        validate(metadata)
        need(re.fullmatch(r"[a-f0-9]{64}", capture_sha), "vpcp_capture_hash_invalid")
        ident, version = identity(metadata), digest(metadata)
        need(metadata["issue_date"] <= observed_utc[:10], "vpcp_future_document")
        old = conn.execute("SELECT metadata_version_sha256,first_seen_run FROM regional_official_source_links "
            "WHERE source_family=? AND source_identity=?", (FAMILY, ident)).fetchone()
        conn.execute("INSERT OR IGNORE INTO official_document_versions VALUES (?,?,?,?,?,?,?,?)",
            (FAMILY, ident, version, json.dumps(metadata, ensure_ascii=False, sort_keys=True),
             capture_sha, observed_utc, run_id, source_sha))
        if not topics(metadata):
            filtered += 1
            # A revised subject outside the bounded topical scope withdraws
            # the old public reference; the version history stays intact.
            if old:
                conn.execute("DELETE FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
                             (FAMILY, ident))
            continue
        proof = digest({"policy": rules, "capture_sha256": capture_sha, "metadata_sha256": version,
                        "collector_commit": source_sha, "run_id": run_id})
        if old and old[0] != version:
            # A newly observed, revalidated bibliographic revision replaces only
            # this family's projection. Every prior version remains preserved.
            conn.execute("UPDATE regional_official_source_links SET publisher_posted_date=?,"
                "metadata_version_sha256=?,source_git_commit=?,release_proof_sha256=?,released_at_utc=? "
                "WHERE source_family=? AND source_identity=?", (metadata["issue_date"], version,
                source_sha, proof, observed_utc, FAMILY, ident))
            revised += 1
        else:
            result = store_verified_links(conn, [{"source_family": FAMILY, "source_identity": ident,
                "desk": "vietnam", "canonical_official_url": metadata["official_url"],
                # The shared column is explicitly presented as ISSUE date for documents.
                "publisher_posted_date": metadata["issue_date"], "official_issuer": "vn_vpcp",
                "official_publisher": "vn_government_portal", "official_republisher": None,
                "source_git_commit": source_sha, "metadata_version_sha256": version,
                "first_seen_run": old[1] if old else run_id}], proof, observed_utc, stable_versions=True)
            added += result["new_official_links"]
            unchanged += result["unchanged_official_links"]
    return {"new": added, "unchanged": unchanged, "revised": revised, "filtered": filtered,
            "scope": "bibliographic_metadata_only", "model_calls": 0}


def processing_metadata(conn,ident):
    """Bind text processing to metadata, independently of title-only routing.

    A public link pins a current topical version. Without one, only a single
    verified, subject-filtered version is unambiguous; revised or withdrawn
    topical identities remain held rather than guessing the current version.
    """
    row=conn.execute("SELECT v.metadata_sha256,v.metadata_json FROM regional_official_source_links l "
        "JOIN official_document_versions v ON v.source_family=l.source_family AND v.source_identity=l.source_identity "
        "AND v.metadata_sha256=l.metadata_version_sha256 WHERE l.source_family=? AND l.source_identity=?",
        (FAMILY,ident)).fetchone()
    if row is None:
        rows=conn.execute("SELECT metadata_sha256,metadata_json FROM official_document_versions "
            "WHERE source_family=? AND source_identity=? LIMIT 2",(FAMILY,ident)).fetchall()
        if len(rows)!=1:return None
        row=rows[0]
        if topics(json.loads(row[1])):return None
    metadata=json.loads(row[1]);validate(metadata)
    need(identity(metadata)==ident and digest(metadata)==row[0],'vpcp_processing_metadata_mismatch')
    return row[0],metadata


def read_links(conn):
    """Current versions only; no raw captures, body or model output exists here."""
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='official_document_versions'").fetchone()
    if not table:
        return []
    rows = conn.execute("SELECT r.source_identity,r.canonical_official_url,r.publisher_posted_date,"
        "r.metadata_version_sha256,v.metadata_json,v.first_observed_utc,v.source_run "
        "FROM regional_official_source_links r JOIN official_document_versions v "
        "ON v.source_family=r.source_family AND v.source_identity=r.source_identity "
        "AND v.metadata_sha256=r.metadata_version_sha256 WHERE r.source_family=? "
        "ORDER BY r.publisher_posted_date DESC,r.source_identity", (FAMILY,)).fetchall()
    policy()
    result = []
    for ident, url, day, version, raw, seen, run in rows:
        m = json.loads(raw)
        validate(m)
        need(identity(m) == ident and m["official_url"] == url and m["issue_date"] == day
             and digest(m) == version, "vpcp_public_version_mismatch")
        result.append({"source_identity": ident, "canonical_official_url": url,
            "publisher_posted_date": day, "label": m["document_number"],
            "publisher_label": PUBLISHER, "issuer_label": "Government Office of Vietnam",
            "document": m, "document_type_label": TYPES[m["document_type"]],
            "topics": topics(m), "first_observed_utc": seen, "source_run": run})
    return result
