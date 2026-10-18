"""Strict one-record historical DAPA evidence bridge; never rewrites failed collection.

This exception applies ONLY to the owner-verified 2026-10-15 DAPA release.
Originals and reviewer receipts remain in the restricted source repository.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA = "ipr-korea-dapa-signed-owner-historical-metadata/1"
OWNER_COMMIT = "5791fc9594d5f44184bd07c5b2353ee941a4b937"
RELATIVE = "state/historical_owner_imports/dapa-2026-10-15-156785254"
ATTEMPT = "owner-once-20261017T191435Z"
IDENTITY = "korea-dapa-policy:156785254"
URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785254"
DATE = "2026-10-15"
HWPX_SHA = "dc832374f7709dfc14a08baf4fad526bf8b519114f0cebdca9793a49a64dd8a8"
HTML_SHA = "18d6f645ac345f8a76958be45c6445672e39792e905b6a1edb9472b4a315b992"
LISTING_SHA = "df5a7c671d03c4c2ed28704fb3b023afa4baeb647154379325d842f0f733e066"
ROBOTS_SHA = "98d411637ae27a333b95d03c7b691eae06992f5d0d061ff6e3a77ffaace7ebf8"
LEDGER_SHA = "4a7b3ad9b814a50b6b5ac1d378a717adf830420b5c876fdabf6830e136b70c99"
TITLE_SHA = "6313a4d35cea21fa9ff2410eb3a7b4ddde6ea4cd28e10bbd2698638226a82410"
TEXT_SHA = "23c014be6ed75bef835553d6d4a674871c6f10f7abb4aa41bee432650fff3abb"
HIST_FIELDS = frozenset((
    "historical_owner_import_commit", "historical_manifest_sha256",
    "historical_failed_ledger_sha256", "historical_review_sha256",
))
REVIEW_SCHEMA = "ipr-dapa-historical-official-link-review/1"


def _hash(blob):
    return hashlib.sha256(blob).hexdigest()


def _read(root: Path, rel: str, limit=2_000_000):
    from core import korea_dapa_private_to_production as b
    path = root / rel
    b.need(path.is_file() and not path.is_symlink()
           and 0 < path.stat().st_size <= limit,
           "dapa_historical_private_file_missing_or_unsafe")
    return path.read_bytes()


def verify_structure(packet):
    """Unlike routine DAPA, this does not claim a successful Actions run."""
    from core import korea_dapa_private_to_production as b
    b.need(type(packet) is dict
           and set(packet) == b.PACKET_FIELDS | HIST_FIELDS
           and packet.get("schema") == SCHEMA,
           "dapa_historical_packet_schema_invalid")
    b.need(packet["source_repository"] == b.REPO
           and packet["source_ref"] == b.REF
           and b.valid_commit(packet["source_git_commit"])
           and packet["historical_owner_import_commit"] == OWNER_COMMIT
           and packet["source_run_attempt"] == ATTEMPT
           and all(b.valid_hash(packet[k]) for k in (
               "source_db_sha256", "historical_manifest_sha256",
               "historical_failed_ledger_sha256", "historical_review_sha256")),
           "dapa_historical_attestation_invalid")
    records = packet["records"]
    b.need(type(records) is list and len(records) == 1
           and type(records[0]) is dict
           and set(records[0]) == b.ROW_FIELDS,
           "dapa_historical_one_metadata_record_required")
    row = records[0]
    b.need(row.get("source_identity") == IDENTITY
           and row.get("canonical_official_url") == URL
           and row.get("publisher_posted_date") == DATE
           and row.get("official_issuer") == b.ISSUER
           and row.get("official_republisher") == b.REPUBLISHER
           and row.get("original_title_sha256") == TITLE_SHA
           and row.get("original_text_sha256") == TEXT_SHA
           and row.get("publisher_html_sha256") == HTML_SHA
           and row.get("original_hwpx_sha256") == HWPX_SHA
           and row.get("candidate_version_sha256") == b.version_hash(row),
           "dapa_historical_source_identity_or_fingerprint_mismatch")
    b.need(packet["historical_failed_ledger_sha256"] == LEDGER_SHA,
           "dapa_historical_failed_attempt_not_preserved")
    policy = b.read_policy()
    b.need(policy["source_family"] == "kr_policy_dapa_releases"
           and policy["automatic_admission_of_verified_link_metadata"] is True
           and policy["public_fields"] == [
               "canonical_official_url", "publisher_posted_date",
               "official_issuer", "official_republisher", "source_identity"]
           and all(policy[k] is False for k in (
               "publish_original_korean_titles", "publish_original_text",
               "publish_document_media", "publish_translations_or_analysis",
               "publish_to_model_or_email")),
           "dapa_historical_public_rights_scope_invalid")
    return records


def export_from_private_checkout(checkout):
    """Private-only exporter. Requires separately committed review and source DB.

    A legitimate private workflow must independently clone/verify the vault,
    establish the trusted repository and sign before any public dispatch.
    """
    from core import korea_dapa_private_to_production as b
    root = Path(checkout).resolve(strict=True)
    b.need(root.is_dir() and not root.is_symlink(),
           "dapa_historical_private_checkout_invalid")
    b.need(b._git(root, "rev-parse", "--show-toplevel") == str(root)
           and b._git(root, "branch", "--show-current") == b.REF
           and b._git(root, "status", "--porcelain") == "",
           "dapa_historical_private_checkout_dirty")
    b._git(root, "merge-base", "--is-ancestor", OWNER_COMMIT, "HEAD")
    source_sha = b._git(root, "rev-parse", "HEAD")
    base = root / RELATIVE
    manifest_raw = _read(base, "historical_manifest.json", 15000)
    ledger_raw = _read(base, "failed_original_ledger.json", 200000)
    b.need(_hash(ledger_raw) == LEDGER_SHA, "dapa_historical_failed_ledger_drift")
    try:
        manifest = json.loads(manifest_raw)
        ledger = json.loads(ledger_raw)
    except (ValueError, UnicodeError):
        raise b.DAPABridgeHold("dapa_historical_manifest_or_ledger_invalid") from None
    b.need(manifest.get("schema") == "ipr-dapa-historical-owner-source-custody/1"
           and manifest.get("source_identity") == IDENTITY
           and manifest.get("source_url") == URL
           and manifest.get("source_day") == DATE
           and manifest.get("issuer") == b.ISSUER
           and manifest.get("republisher") == b.REPUBLISHER
           and manifest.get("original_ledger_result") == "extraction_failure"
           and manifest.get("original_ledger_health") == "fail"
           and manifest.get("original_attempt_reclassified") is False
           and manifest.get("offline_adapter_replay_passed") is True
           and manifest.get("original_hwpx_sha256") == HWPX_SHA
           and manifest.get("original_text_sha256") == TEXT_SHA
           and manifest.get("original_title_sha256") == TITLE_SHA
           and ledger.get("result") == "extraction_failure"
           and ledger.get("health") == "fail"
           and all(manifest.get(flag) is False for flag in (
               "public_metadata_admission_approved",
               "korean_semantic_review_approved",
               "specific_source_rights_review_approved",
               "signing_packet_issued", "live_publisher_or_pages_touched")),
           "dapa_historical_failed_source_status_changed")
    b.need(manifest.get("original_request_captures_sha256") == {
               "robots": ROBOTS_SHA, "listing": LISTING_SHA, "article": HTML_SHA},
           "dapa_historical_original_request_inventory_mismatch")
    for sha in (ROBOTS_SHA, LISTING_SHA, HTML_SHA):
        b.need(_hash(_read(base, "captures/" + sha + ".bin", 12_000_000)) == sha,
               "dapa_historical_capture_hash_changed")
    doc = _read(base, HWPX_SHA + ".hwpx", 2_000_000)
    b.need(len(doc) == 230559 and _hash(doc) == HWPX_SHA,
           "dapa_historical_hwpx_hash_changed")
    from scraper.sources.kr_dapa_policy_briefing import KoreaDapaPolicyAdapter
    from scraper.sources.kr_policy_briefing import hwpx_text
    try:
        title, date, document_url = KoreaDapaPolicyAdapter.metadata(
            None, _read(base, "captures/" + HTML_SHA + ".bin", 2_000_000).decode("utf-8"), URL)
        body = hwpx_text(doc)
    except (ValueError, UnicodeError, OSError, KeyError, TypeError) as exc:
        raise b.DAPABridgeHold("dapa_historical_original_parser_mismatch") from exc
    b.need(date == DATE and "fileId=198570147" in document_url
           and _hash(title.encode("utf-8")) == TITLE_SHA
           and _hash(body.encode("utf-8")) == TEXT_SHA,
           "dapa_historical_original_replay_mismatch")
    review_raw = _read(base, "review_official_link.json", 10000)
    try:
        review = json.loads(review_raw)
    except (ValueError, UnicodeError):
        raise b.DAPABridgeHold("dapa_historical_review_invalid") from None
    b.need(type(review) is dict and set(review) == {
               "schema", "source_identity", "source_commit", "reviewer",
               "issuer_and_date_verified", "official_link_metadata_rights_approved",
               "metadata_only_release_approved", "original_text_media_reuse_approved",
               "translation_analysis_reuse_approved"}
           and review["schema"] == REVIEW_SCHEMA
           and review["source_identity"] == IDENTITY
           and review["source_commit"] == OWNER_COMMIT
           and isinstance(review["reviewer"], str)
           and 3 <= len(review["reviewer"].strip()) <= 120
           and all(review[k] is True for k in (
               "issuer_and_date_verified", "official_link_metadata_rights_approved",
               "metadata_only_release_approved"))
           and review["original_text_media_reuse_approved"] is False
           and review["translation_analysis_reuse_approved"] is False,
           "dapa_historical_specific_review_not_approved")
    # source_db_sha256 means a real separately committed private SQLite file,
    # NEVER a manifest digest mislabeled as a source database.
    dbfile = base / "historical_source.db"
    dbraw = _read(base, "historical_source.db", 2_000_000)
    try:
        with sqlite3.connect(dbfile.as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            b.need(db.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                   "dapa_historical_source_db_corrupt")
            entries = db.execute(
                "SELECT source_identity,original_article_sha256,original_hwpx_sha256,"
                "original_failed_ledger_sha256 FROM historical_dapa_sources").fetchall()
    except sqlite3.Error:
        raise b.DAPABridgeHold("dapa_historical_source_db_schema_invalid") from None
    b.need(entries == [(IDENTITY, HTML_SHA, HWPX_SHA, LEDGER_SHA)],
           "dapa_historical_source_db_not_bound_to_original")
    row = {"source_identity": IDENTITY, "canonical_official_url": URL,
           "publisher_posted_date": DATE, "official_issuer": b.ISSUER,
           "official_republisher": b.REPUBLISHER,
           "original_title_sha256": TITLE_SHA, "original_text_sha256": TEXT_SHA,
           "publisher_html_sha256": HTML_SHA, "original_hwpx_sha256": HWPX_SHA}
    row["candidate_version_sha256"] = b.version_hash(row)
    packet = {
        "schema": SCHEMA, "source_repository": b.REPO, "source_ref": b.REF,
        "source_git_commit": source_sha, "source_db_sha256": _hash(dbraw),
        "source_run_attempt": ATTEMPT, "records": [row],
        "historical_owner_import_commit": OWNER_COMMIT,
        "historical_manifest_sha256": _hash(manifest_raw),
        "historical_failed_ledger_sha256": LEDGER_SHA,
        "historical_review_sha256": _hash(review_raw),
    }
    verify_structure(packet)
    return packet
