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
from datetime import date, datetime
from pathlib import Path

from core.korea_dapa_official_metadata_policy import read_policy

SCHEMA = "ipr-korea-dapa-signed-private-source-metadata/1"
MAX_DAPA_BATCH = 5  # Single authorized publisher day; never a silent truncation.
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
    # One owner-verified historical release has a separately typed envelope.
    # Routine new-source packets retain their >=2026-10-16 date and genuine
    # successful private-collection receipt checks, unchanged.
    if type(packet) is dict and packet.get("schema") == (
            "ipr-korea-dapa-signed-owner-historical-metadata/1"):
        from core.korea_dapa_historical_owner import verify_structure as historical
        return historical(packet)
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
    need(type(rows) is list and 1 <= len(rows) <= MAX_DAPA_BATCH,
         "dapa_bounded_nonempty_batch_required")
    identities = []
    dates = set()
    for row in rows:
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
        identities.append(ident)
        dates.add(row["publisher_posted_date"])
    need(identities == sorted(set(identities)) and len(dates) == 1,
         "dapa_batch_not_unique_sorted_single_day")
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
    return rows


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


def collection_date_proven(ledger, run_attempt):
    """Accept explicit recovery or the collector's first, nominal 22:17 slot.

    The private receipt authenticates this ledger. Recompute the slot from its
    preserved start, never today's clock or the metadata retry's start time.
    """
    from core.shadow_schedule import SOURCE_EXPLICIT, SOURCE_SCHEDULE, scheduled_slot_date

    source = ledger.get("target_date_source")
    if source == SOURCE_EXPLICIT:
        return valid_date(ledger.get("target_date"))
    if source != SOURCE_SCHEDULE or not run_attempt.endswith("-1"):
        return False
    try:
        started = datetime.fromisoformat(ledger["started_utc"].replace("Z", "+00:00"))
        return scheduled_slot_date(started, "22:17").isoformat() == ledger.get("target_date")
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def export_from_private_checkout(checkout, run_attempt):
    """Execute ONLY inside the authenticated private repository workflow.

    Relies on the private workflow's independent fsck/clone readback, then
    rechecks the exact immutable record/receipt/ledger/capture bytes.
    A zero-publication day is not exportable.
    """
    source_path = Path(checkout)
    need(not source_path.is_symlink() and valid_run(run_attempt),
         "dapa_private_checkout_or_run_invalid")
    try:
        root = source_path.resolve(strict=True)
    except OSError:
        raise DAPABridgeHold("dapa_private_checkout_or_run_invalid") from None
    need(root.is_dir(), "dapa_private_checkout_or_run_invalid")
    need(_git(root, "rev-parse", "--show-toplevel") == str(root)
         and _git(root, "branch", "--show-current") == REF
         and _git(root, "status", "--porcelain") == "",
         "dapa_private_checkout_dirty_or_wrong_ref")
    source_sha = _git(root, "rev-parse", "HEAD")
    need(valid_commit(source_sha), "dapa_private_git_commit_invalid")
    # Sign only the exact source-attempt commit, never a later branch tip:
    # a reproducible retry must preserve the originally admitted hash pins.
    need(_git(root, "log", "-1", "--format=%s") ==
         "private-dapa: preserve source attempt " + run_attempt,
         "dapa_private_source_commit_not_exact_attempt")
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
         and type(ledger.get("inserted")) is int
         and 1 <= ledger["inserted"] <= MAX_DAPA_BATCH
         and type(ledger.get("duplicates")) is int
         and 0 <= ledger["duplicates"] <= MAX_DAPA_BATCH
         and type(ledger.get("selected")) is int
         and ledger["selected"] == ledger.get("retrieved")
         and ledger["selected"] == ledger.get("extracted")
         and ledger["selected"] == ledger["inserted"] + ledger["duplicates"]
         and ledger["selected"] <= MAX_DAPA_BATCH
         and ledger.get("fetch_failures") == 0
         and ledger.get("extraction_failures") == 0
         and ledger.get("access_failures") == 0
         and ledger.get("failures") == []
         and collection_date_proven(ledger, run_attempt)
         and valid_date(ledger.get("target_date"))
         and ledger.get("target_date") >= "2026-10-16"
         and type(ledger.get("cap")) is int
         and 1 <= ledger["cap"] <= MAX_DAPA_BATCH
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
    need(len(rows) == ledger["inserted"], "dapa_private_inserted_record_count_mismatch")
    requests = ledger.get("requests")
    need(type(requests) is list and 3 <= len(requests) <= 5 + MAX_DAPA_BATCH * 3
         and all(type(q) is dict for q in requests),
         "dapa_original_request_chain_incomplete")
    listing_url = "https://www.korea.kr/briefing/pressReleaseList.do"
    robots_url = "https://www.korea.kr/robots.txt"
    need(any(q.get("requested_url") == robots_url
                 and q.get("http_status") == 200
                 and valid_hash(q.get("capture_sha256"))
                 for q in requests)
         and any(q.get("requested_url") == listing_url
                 and q.get("http_status") == 200
                 and valid_hash(q.get("capture_sha256"))
                 and type(q.get("form")) is dict
                 and q["form"].get("repCode") == "B00008"
                 and q["form"].get("startDate") == ledger["target_date"]
                 and q["form"].get("endDate") == ledger["target_date"]
                 for q in requests), "dapa_original_request_chain_incomplete")
    for q in requests:
        sha = q.get("capture_sha256")
        need(valid_hash(sha), "dapa_original_request_chain_incomplete")
        file = state / "captures" / (sha + ".bin")
        need(file.is_file() and not file.is_symlink()
             and digest(file.read_bytes()) == sha,
             "dapa_private_original_capture_mismatch")
    from scraper.sources.kr_dapa_policy_briefing import KoreaDapaPolicyAdapter
    from scraper.sources.kr_policy_briefing import hwpx_text
    signed_rows = []
    for (ident, url, family, title, body, day, lang,
         extra_json, bodysha, htmlsha, first_seen) in rows:
        try:
            extra = json.loads(extra_json)
        except (TypeError, ValueError):
            raise DAPABridgeHold("dapa_private_record_metadata_invalid") from None
        need(type(extra) is dict
             and type(title) is str and 0 < len(title) <= 3000
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
                     and q.get("http_status") == 200 for q in requests)
             and any(q.get("requested_url") == extra.get("document_url")
                     and q.get("capture_sha256") == document_sha
                     and q.get("http_status") == 200 for q in requests),
             "dapa_original_request_chain_incomplete")
        try:
            article_bytes = (state / "captures" / (htmlsha + ".bin")).read_bytes()
            document_bytes = (state / "captures" / (document_sha + ".bin")).read_bytes()
            captured_title, captured_date, captured_document_url = (
                KoreaDapaPolicyAdapter.metadata(None, article_bytes.decode("utf-8"), url))
            recovered_text = hwpx_text(document_bytes)
        except (ValueError, UnicodeError, OSError, KeyError, TypeError, ImportError):
            raise DAPABridgeHold("dapa_original_replay_failed") from None
        need(captured_title == title and captured_date == day
             and captured_document_url == extra.get("document_url")
             and recovered_text == body
             and digest(recovered_text.encode("utf-8")) == bodysha,
             "dapa_original_semantic_or_text_fidelity_mismatch")
        signed_row = {
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
        signed_row["candidate_version_sha256"] = version_hash(signed_row)
        signed_rows.append(signed_row)
    signed_rows.sort(key=lambda r: r["source_identity"])
    packet = {
        "schema": SCHEMA,
        "source_repository": REPO,
        "source_ref": REF,
        "source_git_commit": source_sha,
        "source_db_sha256": dbsha,
        "source_run_attempt": run_attempt,
        "records": signed_rows,
    }
    verify_structure(packet)
    return packet


def admit(conn: sqlite3.Connection, packet, mac, key, *, as_of_utc):
    """Atomic metadata-only admission: any collision blocks the entire batch."""
    rows = verify_signed_packet(packet, mac, key)
    need(type(as_of_utc) is str and
         re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                      as_of_utc), "dapa_admission_clock_invalid")
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(korea_official_source_records)")}
    need("original_hwpx_sha256" in cols and "public_scope" in cols,
         "dapa_production_schema_not_ready")
    inserted = 0
    unchanged = 0
    conn.execute("SAVEPOINT dapa_signed_admission")
    try:
        for row in rows:
            proposed = (
                row["source_identity"], row["canonical_official_url"],
                row["publisher_posted_date"], packet["source_git_commit"],
                packet["source_db_sha256"], row["candidate_version_sha256"],
                row["original_title_sha256"], row["original_text_sha256"],
                row["publisher_html_sha256"], row["original_hwpx_sha256"],
                ISSUER, REPUBLISHER, "ko", "B", "syndicated",
                "official_link_only", as_of_utc, as_of_utc,
            )
            old = conn.execute(
                "SELECT * FROM korea_official_source_records "
                "WHERE source_identity=? OR canonical_official_url=?",
                (row["source_identity"], row["canonical_official_url"])).fetchall()
            if old:
                need(len(old) == 1 and tuple(old[0][:16]) == proposed[:16],
                     "dapa_conflicting_or_drifted_source_version")
                unchanged += 1
            else:
                conn.execute(
                    "INSERT INTO korea_official_source_records VALUES "
                    "(" + ",".join("?" for _ in proposed) + ")", proposed)
                inserted += 1
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
        "batch_records": len(rows),
        "new_official_links_admitted": inserted,
        "unchanged_official_links": unchanged,
        "original_titles_text_media_exported": False,
        "english_analysis_automatically_published": False,
    }
