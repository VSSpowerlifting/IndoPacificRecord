"""Strict, signed DAPA private-evidence to public metadata-only bridge.

Only a separately authenticated private Git checkout may produce envelopes.
The public consumer verifies their MAC and schema; it NEVER receives an
original Korean title, body, picture, HWPX or unpublished publisher response.
A MAC is an attestation by the private runner, not independent public access
to its source originals. No writer or scheduled publisher is activated here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import subprocess
from datetime import date
from pathlib import Path

from core.korea_dapa_official_metadata_policy import read_policy

SCHEMA = "ipr-korea-dapa-signed-private-source-metadata/1"
REPO = "VSSpowerlifting/ipr-source-evidence-private"
REF = "archive/korea-dapa-policy-briefing"
ISSUER = "kr_dapa"
REPUBLISHER = "kr_policy_briefing"
PREFIX = "korea-dapa-policy:"
URL_PREFIX = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
HASH = re.compile(r"[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
RUN = re.compile(r"[0-9]{8,20}-[1-9][0-9]{0,5}\Z")
NEWS = re.compile(r"1[0-9]{8}\Z")
KEY_MIN = 32
ROW_FIELDS = frozenset((
    "source_identity", "canonical_official_url", "publisher_posted_date",
    "official_issuer", "official_republisher", "candidate_version_sha256",
    "original_title_sha256", "original_text_sha256", "publisher_html_sha256",
    "original_hwpx_sha256",
))
PACKET_FIELDS = frozenset((
    "schema", "source_repository", "source_ref", "source_git_commit",
    "source_db_sha256", "source_run_attempt", "records",
))


class DAPABridgeHold(ValueError):
    """Fixed error codes; never interpolate untrusted article content."""


def need(ok, code):
    if not ok:
        raise DAPABridgeHold(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def valid_hash(x):
    return type(x) is str and bool(HASH.fullmatch(x))


def valid_commit(x):
    return type(x) is str and bool(COMMIT.fullmatch(x))


def valid_run(x):
    return type(x) is str and bool(RUN.fullmatch(x))


def valid_date(day):
    if type(day) is not str:
        return False
    try:
        return date.fromisoformat(day).isoformat() == day
    except ValueError:
        return False


def version_hash(row):
    return digest(canonical({
        "source_identity": row["source_identity"],
        "source_url": row["canonical_official_url"],
        "published_date": row["publisher_posted_date"],
        "original_text_sha256": row["original_text_sha256"],
        "publisher_html_sha256": row["publisher_html_sha256"],
        "original_hwpx_sha256": row["original_hwpx_sha256"],
    }))


def verify_structure(packet):
    need(type(packet) is dict and set(packet) == PACKET_FIELDS,
         "dapa_signed_packet_schema_invalid")
    need(packet["schema"] == SCHEMA
         and packet["source_repository"] == REPO
         and packet["source_ref"] == REF
         and valid_commit(packet["source_git_commit"])
         and valid_hash(packet["source_db_sha256"])
         and valid_run(packet["source_run_attempt"]),
         "dapa_source_attestation_invalid")
    rows = packet["records"]
    need(type(rows) is list and len(rows) == 1,
         "dapa_one_new_original_required")
    row = rows[0]
    need(type(row) is dict and set(row) == ROW_FIELDS,
         "dapa_public_field_scope_invalid")
    ident = row["source_identity"]
    suffix = ident[len(PREFIX):] if type(ident) is str and ident.startswith(PREFIX) else ""
    need(bool(NEWS.fullmatch(suffix))
         and row["canonical_official_url"] == URL_PREFIX + suffix
         and row["official_issuer"] == ISSUER
         and row["official_republisher"] == REPUBLISHER
         and valid_date(row["publisher_posted_date"])
         and row["publisher_posted_date"] >= "2026-10-16",
         "dapa_issuer_identity_or_date_invalid")
    need(all(valid_hash(row[k]) for k in (
        "candidate_version_sha256", "original_title_sha256",
        "original_text_sha256", "publisher_html_sha256",
        "original_hwpx_sha256")), "dapa_private_capture_hash_missing")
    need(row["candidate_version_sha256"] == version_hash(row),
         "dapa_candidate_version_inconsistent")
    policy = read_policy()
    need(policy["issuer"] == ISSUER
         and policy["source_family"] == "kr_policy_dapa_releases"
         and policy["automatic_admission_of_verified_link_metadata"] is True
         and policy["public_fields"] == [
             "canonical_official_url", "publisher_posted_date",
             "official_issuer", "official_republisher", "source_identity"
         ] and all(policy[k] is False for k in (
             "publish_original_korean_titles", "publish_original_text",
             "publish_document_media", "publish_translations_or_analysis",
             "publish_to_model_or_email")),
         "dapa_owner_metadata_policy_hold")
    return row


def sign(packet, key):
    need(type(key) is str and len(key) >= KEY_MIN,
         "dapa_private_signing_key_not_configured")
    verify_structure(packet)
    return hmac.new(key.encode("utf-8"), canonical(packet),
                    hashlib.sha256).hexdigest()


def verify_signed_packet(packet, mac, key):
    need(type(key) is str and len(key) >= KEY_MIN,
         "dapa_public_signature_key_not_configured")
    need(type(mac) is str and valid_hash(mac),
         "dapa_private_attestation_signature_invalid")
    need(type(packet) is dict and len(canonical(packet)) <= 12000,
         "dapa_packet_size_or_schema_invalid")
    expected = hmac.new(key.encode("utf-8"), canonical(packet),
                        hashlib.sha256).hexdigest()
    need(hmac.compare_digest(mac, expected),
         "dapa_private_attestation_signature_mismatch")
    return verify_structure(packet)


def _json(path, max_bytes=128000):
    need(path.is_file() and not path.is_symlink()
         and 0 < path.stat().st_size <= max_bytes,
         "dapa_private_evidence_missing")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise DAPABridgeHold("dapa_private_evidence_unreadable") from None


def _git(path, *args):
    p = subprocess.run(["git", "-C", str(path), *args],
                       capture_output=True, text=True, timeout=20)
    need(p.returncode == 0, "dapa_private_source_git_unverified")
    return p.stdout.strip()


def export_from_private_checkout(checkout, run_attempt):
    """Execute ONLY inside the authenticated private repository workflow.

    Relies on the private workflow's independent fsck/clone readback, then
    rechecks the exact immutable record/receipt/ledger/capture bytes.
    A zero-publication day is not exportable.
    """
    root = Path(checkout).resolve(strict=True)
    need(root.is_dir() and not root.is_symlink()
         and valid_run(run_attempt), "dapa_private_checkout_or_run_invalid")
    need(_git(root, "rev-parse", "--show-toplevel") == str(root)
         and _git(root, "branch", "--show-current") == REF
         and _git(root, "status", "--porcelain") == "",
         "dapa_private_checkout_dirty_or_wrong_ref")
    source_sha = _git(root, "rev-parse", "HEAD")
    need(valid_commit(source_sha), "dapa_private_git_commit_invalid")
    state = root / "state"
    receipt = _json(state / "private_attempts" / (run_attempt + ".json"))
    need(receipt.get("run_attempt") == run_attempt
         and receipt.get("collector_exit_status") == 0
         and receipt.get("public_admission_approved") is False
         and receipt.get("original_reuse_approved") is False,
         "dapa_private_run_attempt_not_eligible")
    ledgers = list((state / "ledger").glob("*-" + run_attempt + ".json"))
    need(len(ledgers) == 1, "dapa_private_ledger_missing_or_duplicated")
    ledger = _json(ledgers[0])
    need(ledger.get("desk") == "korea_dapa"
         and ledger.get("run_id") == run_attempt
         and ledger.get("result") == "ok"
         and ledger.get("health") == "ok"
         and ledger.get("inserted") == 1
         and ledger.get("selected") == 1
         and ledger.get("retrieved") == 1
         and ledger.get("extracted") == 1
         and ledger.get("fetch_failures") == 0
         and ledger.get("extraction_failures") == 0
         and ledger.get("access_failures") == 0
         and ledger.get("failures") == []
         and ledger.get("target_date_source") == "explicit"
         and valid_date(ledger.get("target_date"))
         and ledger.get("target_date") >= "2026-10-16"
         and ledger.get("cap") == 1
         and ledger.get("lookback_days") == 0
         and ledger.get("collector_commit") == receipt.get("collector_commit"),
         "dapa_private_live_collection_not_proven")
    import sqlite3
    db = state / "shadow.db"
    need(db.is_file() and not db.is_symlink(),
         "dapa_private_database_missing")
    dbsha = digest(db.read_bytes())
    need(valid_hash(dbsha), "dapa_private_database_digest_invalid")
    try:
        with sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True) as c:
            need(c.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                 "dapa_private_database_integrity_failure")
            rows = c.execute(
                "SELECT source_identity,url,source_slug,title_original,"
                "text_original,published_date,language_tag,metadata_json,"
                "content_sha256,capture_sha256,first_seen_run FROM shadow_records "
                "WHERE first_seen_run=?", (run_attempt,)).fetchall()
    except sqlite3.Error:
        raise DAPABridgeHold("dapa_private_database_schema_invalid") from None
    need(len(rows) == 1, "dapa_private_inserted_record_not_unique")
    (ident, url, family, title, body, day, lang,
     extra_json, bodysha, htmlsha, first_seen) = rows[0]
    try:
        extra = json.loads(extra_json)
    except (TypeError, ValueError):
        raise DAPABridgeHold("dapa_private_record_metadata_invalid") from None
    need(type(title) is str and 0 < len(title) <= 3000
         and type(body) is str and 0 < len(body) <= 200000
         and digest(body.encode("utf-8")) == bodysha
         and family == "kr_policy_dapa_releases"
         and lang == "ko"
         and extra.get("issuer") == "방위사업청"
         and extra.get("publisher") == "대한민국 정책브리핑"
         and extra.get("body_scope") ==
             "captured_hwpx_text_not_editorially_approved"
         and extra.get("attachments_collected") is True
         and extra.get("public_metadata_admission_approved") is False
         and extra.get("public_full_text_approved") is False
         and extra.get("document_reuse_approved") is False
         and day == ledger["target_date"]
         and first_seen == run_attempt,
         "dapa_private_record_source_or_rights_scope_invalid")
    document_sha = extra.get("document_capture_sha256")
    need(valid_hash(htmlsha) and valid_hash(document_sha)
         and any(q.get("requested_url") == url
                 and q.get("capture_sha256") == htmlsha
                 and q.get("http_status") == 200
                 for q in ledger.get("requests", []))
         and any(q.get("requested_url") == extra.get("document_url")
                 and q.get("capture_sha256") == document_sha
                 and q.get("http_status") == 200
                 for q in ledger.get("requests", []))
         and any(q.get("form", {}).get("repCode") == "B00008"
                 for q in ledger.get("requests", []) if type(q.get("form")) is dict),
         "dapa_original_request_chain_incomplete")
    for sha in (htmlsha, document_sha):
        path = state / "captures" / (sha + ".bin")
        need(path.is_file() and not path.is_symlink()
             and digest(path.read_bytes()) == sha,
             "dapa_private_original_capture_mismatch")
    row = {
        "source_identity": ident,
        "canonical_official_url": url,
        "publisher_posted_date": day,
        "official_issuer": ISSUER,
        "official_republisher": REPUBLISHER,
        "original_title_sha256": digest(title.encode("utf-8")),
        "original_text_sha256": bodysha,
        "publisher_html_sha256": htmlsha,
        "original_hwpx_sha256": document_sha,
    }
    row["candidate_version_sha256"] = version_hash(row)
    packet = {
        "schema": SCHEMA,
        "source_repository": REPO,
        "source_ref": REF,
        "source_git_commit": source_sha,
        "source_db_sha256": dbsha,
        "source_run_attempt": run_attempt,
        "records": [row],
    }
    verify_structure(packet)
    return packet


def admit(conn: sqlite3.Connection, packet, mac, key, *, as_of_utc):
    """Only signed metadata becomes an official-link-only row; never a body."""
    row = verify_signed_packet(packet, mac, key)
    need(type(as_of_utc) is str and
         re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                      as_of_utc), "dapa_admission_clock_invalid")
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(korea_official_source_records)")}
    need(ROW_FIELDS.issubset(set(row))
         and "original_hwpx_sha256" in cols
         and "public_scope" in cols,
         "dapa_production_schema_not_ready")
    proposed = (
        row["source_identity"], row["canonical_official_url"],
        row["publisher_posted_date"], packet["source_git_commit"],
        packet["source_db_sha256"], row["candidate_version_sha256"],
        row["original_title_sha256"], row["original_text_sha256"],
        row["publisher_html_sha256"], row["original_hwpx_sha256"],
        ISSUER, REPUBLISHER, "ko", "B", "syndicated",
        "official_link_only", as_of_utc, as_of_utc,
    )
    conn.execute("SAVEPOINT dapa_signed_admission")
    try:
        old = conn.execute(
            "SELECT * FROM korea_official_source_records "
            "WHERE source_identity=? OR canonical_official_url=?",
            (row["source_identity"], row["canonical_official_url"])).fetchall()
        if old:
            need(len(old) == 1 and tuple(old[0][:16]) == proposed[:16],
                 "dapa_conflicting_or_drifted_source_version")
            changed = False
        else:
            conn.execute(
                "INSERT INTO korea_official_source_records VALUES "
                "(" + ",".join("?" for _ in proposed) + ")", proposed)
            changed = True
        need(conn.execute("PRAGMA foreign_key_check").fetchall() == [],
             "dapa_metadata_foreign_key_violation")
        conn.execute("RELEASE SAVEPOINT dapa_signed_admission")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT dapa_signed_admission")
        conn.execute("RELEASE SAVEPOINT dapa_signed_admission")
        raise
    return {
        "schema": "ipr-korea-dapa-signed-metadata-admission/1",
        "source_git_commit": packet["source_git_commit"],
        "new_official_links_admitted": int(changed),
        "unchanged_official_links": int(not changed),
        "original_titles_text_media_exported": False,
        "english_analysis_automatically_published": False,
    }
