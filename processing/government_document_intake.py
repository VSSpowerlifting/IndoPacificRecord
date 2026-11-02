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
SELECTION = Path(__file__).resolve().parents[1] / "config/vietnam_vpcp_editorial_selection.json"
SELECTION_ENTRY = {"source_identity", "metadata_sha256", "selected_by", "reason"}


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


def selection(path=None):
    """Editorial routing pins for exact captured versions; grants no new use.

    It only overrides the subject-index false negatives within the existing
    bibliographic-metadata decision. It never adds a body, attachment,
    translation or model input, and never changes text-processing routing.
    """
    try:
        value = json.loads(Path(path or SELECTION).read_text())
    except (OSError, ValueError):
        value = None
    need(type(value) is dict and value.get("source_family") == FAMILY
         and value.get("decision_reference") == "docs/engineering/VIETNAM_GOVERNMENT_DOCUMENTS_2026-10-23.md"
         and value.get("policy") == "config/vietnam_vpcp_metadata_policy.json"
         and value.get("scope") == "public_bibliographic_metadata_only"
         and set(value) == {"source_family", "decision_reference", "policy", "scope", "selections"}
         and type(value["selections"]) is list, "vpcp_selection_invalid")
    seen = set()
    for entry in value["selections"]:
        need(type(entry) is dict and set(entry) == SELECTION_ENTRY
             and all(type(entry[k]) is str and entry[k].strip() for k in SELECTION_ENTRY)
             and re.fullmatch(r"vpcp-vi:[1-9][0-9]{0,8}", entry["source_identity"])
             and re.fullmatch(r"[a-f0-9]{64}", entry["metadata_sha256"])
             and entry["source_identity"] not in seen, "vpcp_selection_invalid")
        seen.add(entry["source_identity"])
    return value


def validate(metadata):
    need(type(metadata) is dict and set(metadata) == METADATA_FIELDS, "vpcp_metadata_fields")
    need(metadata["issuer"] == ISSUER and metadata["publisher"] == PUBLISHER
         and metadata["document_type"] in TYPES, "vpcp_institution_or_type")
    need(canonical_url(metadata["official_url"]) == metadata["official_url"]
         and metadata["official_url"].endswith("docid=" + metadata["document_id"]), "vpcp_identity")
    need(date.fromisoformat(metadata["issue_date"]).isoformat() == metadata["issue_date"], "vpcp_issue_date")


def admit(conn, captures, *, source_sha, run_id, observed_utc, selection_path=None):
    """Caller holds the DB transaction; every exception rolls back that run."""
    rules = policy()
    # An invalid selection file holds the selections only: topical captures
    # in the same run still admit and existing selection links stay as they are.
    try:
        chosen = selection(selection_path)
    except ValueError:
        chosen = None
    pinned = {e["source_identity"] for e in chosen["selections"]} if chosen else _selection_links(conn)
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
            # A selected identity is decided by its exact pin below.
            if old and ident not in pinned:
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
    selected = "vpcp_selection_invalid"
    if chosen:
        selected = {e["source_identity"]: _reconcile(conn, rules, chosen, e, observed_utc)
                    for e in chosen["selections"]}
        # A removed entry withdraws its link; the version history stays intact.
        for ident in sorted(_selection_links(conn) - pinned):
            conn.execute("DELETE FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
                         (FAMILY, ident))
            selected[ident] = "selection_withdrawn"
    return {"new": added, "unchanged": unchanged, "revised": revised, "filtered": filtered,
            "selection": selected, "scope": "bibliographic_metadata_only", "model_calls": 0}


def _selection_links(conn):
    """Identities whose public link pins a non-topical, editorially selected version."""
    return {ident for ident, m in conn.execute("SELECT l.source_identity,v.metadata_json "
        "FROM regional_official_source_links l JOIN official_document_versions v "
        "ON v.source_family=l.source_family AND v.source_identity=l.source_identity "
        "AND v.metadata_sha256=l.metadata_version_sha256 WHERE l.source_family=?", (FAMILY,))
        if not topics(json.loads(m))}


def _reconcile(conn, rules, chosen, entry, observed_utc):
    """One pin's explicit disposition; a held pin never blocks the run.

    The newest captured version decides. A pin publishes only while it is
    still that version; a later revision is never followed automatically.
    """
    ident, pin = entry["source_identity"], entry["metadata_sha256"]
    rows = conn.execute("SELECT metadata_sha256,metadata_json,capture_sha256,source_run,collector_commit "
        "FROM official_document_versions WHERE source_family=? AND source_identity=? "
        "ORDER BY first_observed_utc,rowid", (FAMILY, ident)).fetchall()
    exact = [r for r in rows if r[0] == pin]
    if not exact:
        return "selection_version_missing"
    try:
        m = json.loads(exact[0][1])
        validate(m)
        need(identity(m) == ident and digest(m) == pin, "vpcp_selection_digest_mismatch")
    except (ValueError, TypeError, KeyError):
        return "selection_digest_mismatch"
    newest = json.loads(rows[-1][1])
    link = conn.execute("SELECT metadata_version_sha256 FROM regional_official_source_links "
        "WHERE source_family=? AND source_identity=?", (FAMILY, ident)).fetchone()
    if rows[-1][0] != pin:
        if topics(newest):
            return "selection_superseded"
        if link:
            conn.execute("DELETE FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
                         (FAMILY, ident))
        return "selection_revision_held"
    if topics(m):
        return "selection_topical"
    if link and link[0] == pin:
        return "selection_unchanged"
    if link:
        # An older topical projection is not silently replaced by a pin.
        conn.execute("DELETE FROM regional_official_source_links WHERE source_family=? AND source_identity=?",
                     (FAMILY, ident))
        return "selection_conflict"
    _, _, capture, run, commit = exact[0]
    proof = digest({"policy": rules, "selection_sha256": digest(chosen), "capture_sha256": capture,
                    "metadata_sha256": pin, "collector_commit": commit, "run_id": run,
                    "routing": "editorial_selection"})
    try:
        store_verified_links(conn, [{"source_family": FAMILY, "source_identity": ident, "desk": "vietnam",
            "canonical_official_url": m["official_url"], "publisher_posted_date": m["issue_date"],
            "official_issuer": "vn_vpcp", "official_publisher": "vn_government_portal",
            "official_republisher": None, "source_git_commit": commit, "metadata_version_sha256": pin,
            "first_seen_run": run}], proof, observed_utc, stable_versions=True)
    except ValueError as error:
        return "selection_held:" + str(error)
    return "selection_admitted"


def processing_metadata(conn,ident):
    """Bind text processing to metadata, independently of title-only routing.

    A public link pins a current topical version. Without one, only a single
    verified, subject-filtered version is unambiguous; revised or withdrawn
    topical identities remain held rather than guessing the current version.
    An editorial-selection link to a non-topical version changes publication
    only, never this routing: it falls through to the unlinked rule.
    """
    row=conn.execute("SELECT v.metadata_sha256,v.metadata_json FROM regional_official_source_links l "
        "JOIN official_document_versions v ON v.source_family=l.source_family AND v.source_identity=l.source_identity "
        "AND v.metadata_sha256=l.metadata_version_sha256 WHERE l.source_family=? AND l.source_identity=?",
        (FAMILY,ident)).fetchone()
    if row is not None and not topics(json.loads(row[1])):row=None
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
