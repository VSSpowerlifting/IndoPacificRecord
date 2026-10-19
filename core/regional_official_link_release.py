"""Regional AFP/Kemhan official-link release contract: no implicit approval.

The owner approved metadata-only scope and reports completing human review.
That declaration is evidence of the owner's decision, not machine-verified
per-original release receipts or an authenticated scheduled Actions census.
This module supplies the final strict SQLite writing boundary; the scheduled
publisher MUST independently verify those prerequisites before calling it.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from core.crossdesk_official_metadata_candidates import (
    FAMILIES, KEMHAN_HELD, SCHEMA as CANDIDATE_SCHEMA,
    canonical, exact_source_url,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/afp_kemhan_owner_link_activation.json"
TABLE = "regional_official_source_links"
RELEASE_FIELDS = frozenset({
    "desk", "source_family", "source_identity", "canonical_official_url",
    "publisher_posted_date", "official_issuer", "official_publisher",
    "official_republisher", "source_git_commit", "first_seen_run",
    "metadata_version_sha256", "review_state", "semantic_exception_hold",
    "production_admission_authorized", "automatic_public_link_authorized",
    "publisher_body_reuse_authorized",
})
SCOPE = (
    "source_family", "source_identity", "canonical_official_url",
    "publisher_posted_date", "official_issuer", "official_publisher",
    "official_republisher", "source_git_commit", "metadata_version_sha256",
)
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
RECEIPT_V1 = "ipr-crossdesk-independent-release-proof/1"
# Version 2 states the review basis truthfully: the owner's declaration is
# bound to the pinned frozen cohort, and no record-specific review receipts
# exist. Admission is limited to identities in that reviewed cohort. Elapsed
# scheduled days are not a gate; every visible scheduled claim is.
RECEIPT_V2 = "ipr-crossdesk-independent-release-proof/2"
V1_GATES = ("review_receipts_version_matched",
            "seven_actual_scheduled_days_authenticated")
V2_GATES = ("owner_review_declaration_bound_to_frozen_manifest",
            "scheduled_history_authenticated")
# Owner ruling 2026-10-18 (DECISION_LOG): for a family listed here, every
# verified, non-held record is admissible without per-record review. The same
# metadata-only scope, semantic holds and validation gates still apply.
STANDING_AUTHORIZATION = {
    "covers_existing_and_future_records": True,
    "per_record_human_review_required": False,
    "asserts_human_review_outside_frozen_cohort": False,
    "elapsed_time_gate": False,
}
COMMON_GATES = ("all_visible_actions_attempts_reconciled",
                "official_metadata_link_use_checked",
                "known_semantic_holds_enforced",
                "production_live_site_authorized",
                "source_capture_version_reverified")

# This DDL is used in disposable test databases ONLY until a unique, approved
# versioned migration lands (concurrent China and Korea PRs both claim 0008).
# No standalone CREATE TABLE is permitted against production pla_watch.db.
SCHEMA_SQL = """
CREATE TABLE regional_official_source_links (
    source_family TEXT NOT NULL
      CHECK(source_family IN ('ph_afp_articles','id_kemhan_news')),
    source_identity TEXT NOT NULL,
    desk TEXT NOT NULL CHECK(desk IN ('philippines','indonesia')),
    canonical_official_url TEXT NOT NULL UNIQUE,
    publisher_posted_date TEXT NOT NULL,
    official_issuer TEXT,
    official_publisher TEXT NOT NULL,
    official_republisher TEXT,
    source_git_commit TEXT NOT NULL,
    metadata_version_sha256 TEXT NOT NULL,
    first_seen_run TEXT NOT NULL,
    release_scope TEXT NOT NULL CHECK(release_scope='official_link_only'),
    release_proof_sha256 TEXT NOT NULL,
    released_at_utc TEXT NOT NULL,
    PRIMARY KEY (source_family, source_identity)
)
"""
EXPECTED_TABLE_COLUMNS = frozenset({
    "source_family", "source_identity", "desk", "canonical_official_url",
    "publisher_posted_date", "official_issuer", "official_publisher",
    "official_republisher", "source_git_commit", "metadata_version_sha256",
    "first_seen_run", "release_scope", "release_proof_sha256",
    "released_at_utc",
})


class RegionalLinkHold(ValueError):
    """Fixed diagnostic; no publisher-controlled text is echoed."""


def need(ok, reason):
    if not ok:
        raise RegionalLinkHold(reason)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load_owner_policy(path=POLICY_PATH):
    path = Path(path)
    need(path == POLICY_PATH and not path.is_symlink(),
         "owner_policy_must_be_repository_pinned")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RegionalLinkHold("owner_policy_unavailable") from None
    need(type(policy) is dict
         and policy.get("schema") == "ipr-afp-kemhan-owner-metadata-activation/1"
         and policy.get("decision_recorded_on") == "2026-10-15"
         and policy.get("owner_confirms_human_review_occurred") is True
         and policy.get("owner_authorizes_automated_verified_link_metadata") is True
         and policy.get("machine_verified_record_specific_human_review_receipts_in_repository") is False
         and policy.get("all_actions_attempts_and_release_gates_approved_by_this_declaration") is False
         and policy.get("production_database_or_site_changed_by_this_declaration") is False
         and policy.get("metadata_only_fields") == list(SCOPE)
         and type(policy.get("source_families")) is list
         and len(policy["source_families"]) == 2,
         "owner_activation_policy_scope_changed")
    fields = {"source_family", "desk", "frozen_review_cohort_commit",
              "frozen_review_cohort_candidate_count",
              "frozen_review_cohort_metadata_manifest_sha256",
              "known_excluded_source_identities"}
    seen = set()
    for spec in policy["source_families"]:
        need(type(spec) is dict and set(spec) == fields,
             "owner_source_family_policy_drift")
        family = spec["source_family"]
        need(family in FAMILIES and family not in seen
             and spec["desk"] == FAMILIES[family]["desk"]
             and type(spec["frozen_review_cohort_commit"]) is str
             and SHA40.fullmatch(spec["frozen_review_cohort_commit"])
             and type(spec["frozen_review_cohort_candidate_count"]) is int
             and 1 <= spec["frozen_review_cohort_candidate_count"] <= 300
             and type(spec["frozen_review_cohort_metadata_manifest_sha256"]) is str
             and SHA256.fullmatch(spec["frozen_review_cohort_metadata_manifest_sha256"]),
             "unrecognized_or_unpinned_source_family")
        excluded = spec["known_excluded_source_identities"]
        expected_hold = (["kemhan:" + KEMHAN_HELD]
                         if family == "id_kemhan_news" else [])
        need(excluded == expected_hold, "known_semantic_exclusions_changed")
        seen.add(family)
    need(seen == set(FAMILIES), "incomplete_owner_family_scope")
    standing = policy.get("standing_link_metadata_authorizations", [])
    need(type(standing) is list
         and all(type(s) is dict and set(s) == set(STANDING_AUTHORIZATION)
                 | {"source_family", "decision_recorded_on", "decision_source"}
                 and s["source_family"] in FAMILIES
                 and all(s[k] is val for k, val in STANDING_AUTHORIZATION.items())
                 and type(s["decision_source"]) is str
                 and type(s["decision_recorded_on"]) is str
                 and re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]",
                                  s["decision_recorded_on"])
                 for s in standing)
         and len({s["source_family"] for s in standing}) == len(standing),
         "owner_standing_authorization_scope_changed")
    return policy


def standing_link_metadata_authorization(policy, family):
    """True when the owner authorized verified link metadata for existing and
    future records of ``family`` without per-record human review. It never
    asserts that such review happened, and never widens the metadata scope."""
    return any(s.get("source_family") == family
               for s in policy.get("standing_link_metadata_authorizations", []))


def verify_cohort(packet, policy, *, baseline_packet=None):
    """Validate one entire frozen source cohort; return metadata-only rows.

    Never reinterpret a candidate's private-review flags as a publication grant.
    The owner confirmation is separately scoped and does not authorize admission
    until an independently verified release receipt is supplied to admit().
    """
    need(type(packet) is dict and type(policy) is dict,
         "invalid_cohort_or_owner_policy")
    family = packet.get("source_family")
    specs = [x for x in policy["source_families"]
             if x.get("source_family") == family]
    need(len(specs) == 1, "unapproved_source_family")
    spec = specs[0]
    records = packet.get("records")
    future_commit = packet.get("source_git_commit") != spec["frozen_review_cohort_commit"]
    original_eligible = None
    if future_commit:
        # The owner's source-family approval is standing, but the baseline
        # cannot be substituted or forgotten as new immutable captures arrive.
        # This structural gate does NOT verify Git ancestry, review or rights;
        # a separate authenticated validator MUST do that before writes.
        need(type(packet.get("source_git_commit")) is str
             and SHA40.fullmatch(packet["source_git_commit"]) is not None
             and baseline_packet is not None,
             "rolling_source_requires_independently_pinned_baseline")
        original_eligible = verify_cohort(baseline_packet, policy)
        need(type(packet.get("candidate_count")) is int
             and packet["candidate_count"] >=
             spec["frozen_review_cohort_candidate_count"],
             "rolling_source_lost_frozen_candidates")
    need(packet.get("schema") == CANDIDATE_SCHEMA
         and packet.get("desk") == FAMILIES[family]["desk"]
         and (future_commit or
              packet.get("source_git_commit") == spec["frozen_review_cohort_commit"])
         and (future_commit or packet.get("candidate_count") ==
              spec["frozen_review_cohort_candidate_count"])
         and type(records) is list
         and len(records) == packet["candidate_count"]
         and packet.get("all_candidates_held") is True
         and packet.get("production_import_enabled") is False
         and packet.get("public_release_enabled") is False
         and packet.get("source_capture_bytes_authenticated_by_this_projection") is False
         and packet.get("seven_scheduled_days_authenticated_by_this_projection") is False
         and packet.get("source_specific_reuse_authorized_by_this_projection") is False
         and packet.get("original_title_or_body_exported") is False
         and type(packet.get("metadata_manifest_sha256")) is str
         and SHA256.fullmatch(packet["metadata_manifest_sha256"])
         and (future_commit or packet["metadata_manifest_sha256"] ==
              spec["frozen_review_cohort_metadata_manifest_sha256"])
         and digest(records) == packet["metadata_manifest_sha256"],
         "source_candidate_cohort_not_owner_pinned")
    seen_id, seen_url, eligible, held = set(), set(), [], set()
    for r in records:
        need(type(r) is dict and set(r) == RELEASE_FIELDS,
             "unexpected_candidate_public_content")
        family_spec = FAMILIES[family]
        sid, url, day = r["source_identity"], r["canonical_official_url"], r["publisher_posted_date"]
        need(type(day) is str, "invalid_publisher_day")
        try:
            need(date.fromisoformat(day).isoformat() == day, "invalid_publisher_day")
        except ValueError:
            raise RegionalLinkHold("invalid_publisher_day") from None
        path = exact_source_url(sid, url, day, family)
        need(sid not in seen_id and url not in seen_url
             and r["desk"] == family_spec["desk"] and r["source_family"] == family
             and r["source_git_commit"] == packet["source_git_commit"]
             and r["official_issuer"] == family_spec["issuer"]
             and r["official_publisher"] == family_spec["publisher"]
             and r["official_republisher"] == family_spec["republisher"]
             and r["review_state"] == "held"
             and r["production_admission_authorized"] is False
             and r["automatic_public_link_authorized"] is False
             and r["publisher_body_reuse_authorized"] is False
             and type(r["metadata_version_sha256"]) is str
             and SHA256.fullmatch(r["metadata_version_sha256"]),
             "invalid_source_identity_attribution_or_rights")
        source_fields = {k: r[k] for k in (
            "desk", "source_family", "source_identity",
            "canonical_official_url", "publisher_posted_date",
            "official_issuer", "official_publisher", "official_republisher",
            "source_git_commit", "first_seen_run")}
        need(digest(source_fields) == r["metadata_version_sha256"],
             "source_metadata_digest_drift")
        seen_id.add(sid); seen_url.add(url)
        should_hold = sid in spec["known_excluded_source_identities"]
        need((r["semantic_exception_hold"] ==
              ("publisher_geography_discrepancy" if should_hold else None))
             and (not should_hold or path == KEMHAN_HELD),
             "semantic_exception_hold_drift")
        if should_hold:
            held.add(sid)
        else:
            eligible.append(r)
    need(held == set(spec["known_excluded_source_identities"])
         and packet["semantic_exception_count"] == len(held),
         "incomplete_semantic_exception_set")
    if future_commit:
        # Every initially reviewable identity must remain the same exact
        # official source. Commit-bound digests may change across collections;
        # the independent validator MUST recheck original version/capture bytes.
        current_by_id = {row["source_identity"]: row for row in eligible}
        for original in original_eligible:
            current = current_by_id.get(original["source_identity"])
            need(current is not None and all(
                current[k] == original[k] for k in (
                    "source_identity", "canonical_official_url",
                    "publisher_posted_date", "official_issuer",
                    "official_publisher", "official_republisher",
                    "first_seen_run")),
                "rolling_source_frozen_identity_or_metadata_changed")
    return eligible


def selected_official_links(receipt, eligible):
    """Choose only individually authenticated approvals, not all stored originals.

    A self-authored list is NOT authority. The separately trusted validator
    must authenticate every selected identity and exact captured source version.
    All other candidates remain unpublished, even when collected successfully.
    """
    if type(receipt) is not dict:
        raise RegionalLinkHold("release_selection_untrusted")
    rows = {r["source_identity"]: r for r in eligible}
    if "approved_source_identities" not in receipt:
        # Compatibility with existing whole-cohort proof; never bypasses
        # the independent trusted validator in admit().
        return list(eligible)
    identities = receipt["approved_source_identities"]
    need(type(identities) is list and bool(identities)
         and all(type(v) is str for v in identities)
         and identities == sorted(set(identities))
         and set(identities) <= set(rows),
         "release_selection_untrusted_or_contains_held_source")
    return [rows[sid] for sid in identities]


def verify_release_evidence(receipt, packet, eligible):
    """Shape and digest preflight; caller must also authenticate provenance.

    A self-authored JSON receipt is NEVER sufficient: gate 'authenticated'
    must be established by the independent Actions+original review validator,
    not inferred here. Until that validator is wired the importer is HOLD-only.
    """
    selected = selected_official_links(receipt, eligible)
    schema = receipt.get("schema") if type(receipt) is dict else None
    gates = {RECEIPT_V1: V1_GATES, RECEIPT_V2: V2_GATES}.get(schema)
    need(gates is not None
         and (schema == RECEIPT_V1 or (
             "approved_source_identities" in receipt
             and receipt.get("record_specific_review_receipts_verified") is False))
         and receipt.get("source_family") == packet.get("source_family")
         and receipt.get("source_git_commit") == packet.get("source_git_commit")
         and receipt.get("metadata_manifest_sha256") ==
             packet.get("metadata_manifest_sha256")
         and receipt.get("eligible_source_identities_sha256") ==
             digest(sorted(r["source_identity"] for r in selected))
         and all(receipt.get(k) is True for k in gates + COMMON_GATES)
         and type(receipt.get("trusted_validator_ref")) is str
         and SHA40.fullmatch(receipt["trusted_validator_ref"]),
         "independent_release_evidence_missing")
    return digest(receipt)


def admit(conn, packet, policy, receipt, *, as_of_utc,
          trusted_validator=None, baseline_packet=None):
    """Insert source-scoped link rows transactionally after trusted validation.

    Default HOLD: no deployment caller currently has a trusted independent
    validator. Do not pass a self-declared JSON flag or an unverified receipt.
    """
    need(policy == load_owner_policy(), "owner_policy_is_not_repository_pinned")
    need(callable(trusted_validator), "trusted_release_evidence_validator_missing")
    eligible = verify_cohort(packet, policy, baseline_packet=baseline_packet)
    approved = selected_official_links(receipt, eligible)
    proof_digest = verify_release_evidence(receipt, packet, eligible)
    standing = (receipt["schema"] == RECEIPT_V2
                and standing_link_metadata_authorization(policy, packet["source_family"])
                and receipt.get("standing_link_metadata_authorization_verified") is True)
    if receipt["schema"] == RECEIPT_V2 and not standing:
        # Without a standing authorization the owner's review covers the
        # pinned frozen cohort only; later records stay held.
        reviewed = (verify_cohort(baseline_packet, policy)
                    if baseline_packet is not None else eligible)
        need({r["source_identity"] for r in approved}
             <= {r["source_identity"] for r in reviewed},
             "unreviewed_source_selected_for_release")
    need(trusted_validator(receipt, packet, approved) is True,
         "trusted_release_evidence_not_authenticated")
    need(type(as_of_utc) is str and
         re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z", as_of_utc),
         "invalid_release_timestamp")
    result = store_verified_links(conn, approved, proof_digest, as_of_utc)
    return {"source_family":packet["source_family"], **result,
            "held_semantic_exceptions":packet["semantic_exception_count"],
            "held_pending_individual_approval":len(eligible) - len(approved),
            "published_original_titles_or_bodies":False}


def store_verified_links(conn, approved, proof_digest, as_of_utc, *, stable_versions=False):
    """Shared atomic store. Call ONLY after source-specific authentication.

    Rights, source bytes and authorization are verified by the admission gate,
    never by this persistence helper. Vietnam uses the same regional index.
    """
    columns = {r[1] for r in conn.execute(
        "PRAGMA table_info(%s)" % TABLE)}
    need(columns == EXPECTED_TABLE_COLUMNS, "regional_official_index_not_migrated")
    if standing:
        # Without per-record review, a released link whose identity, date or
        # attribution later changes or disappears is an anomaly: hold it all.
        current = {r["source_identity"]: r for r in eligible}
        for old in conn.execute(
                "SELECT source_identity,canonical_official_url,publisher_posted_date,"
                "official_issuer,official_publisher,official_republisher,first_seen_run "
                "FROM %s WHERE source_family=?" % TABLE, (packet["source_family"],)):
            row = current.get(old[0])
            need(row is not None and tuple(old[1:]) == (
                row["canonical_official_url"], row["publisher_posted_date"],
                row["official_issuer"], row["official_publisher"],
                row["official_republisher"], row["first_seen_run"]),
                 "previously_released_source_missing_or_changed")
    conn.execute("SAVEPOINT regional_link_admission")
    added = unchanged = 0
    try:
        for row in approved:
            key = (row["source_family"], row["source_identity"])
            stable = (row["canonical_official_url"],
                      row["publisher_posted_date"], row["official_issuer"],
                      row["official_publisher"], row["official_republisher"],
                      row["first_seen_run"])
            old = conn.execute(
                "SELECT canonical_official_url,publisher_posted_date,"
                "official_issuer,official_publisher,official_republisher,"
                "first_seen_run,source_git_commit,metadata_version_sha256 "
                "FROM regional_official_source_links "
                "WHERE source_family=? AND source_identity=?", key).fetchone()
            if old is not None:
                need(tuple(old[:6]) == stable and
                     (not stable_versions or old[7] == row["metadata_version_sha256"]) and
                     (old[6] != row["source_git_commit"] or
                      old[7] == row["metadata_version_sha256"]),
                     "previously_released_source_version_changed")
                # An unchanged official identity retains its ORIGINAL
                # admitted Git SHA/proof. A later collection commit changes
                # the candidate digest without creating a second public row.
                # The trusted validator still re-verifies the new snapshot.
                unchanged += 1
                continue
            # Reject a collided legacy source URL rather than asserting its
            # original article copyright is automatically reusable.
            legacy = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles'"
            ).fetchone()
            if legacy:
                need(conn.execute("SELECT 1 FROM articles WHERE url=? LIMIT 1",
                                  (row["canonical_official_url"],)).fetchone() is None,
                     "legacy_article_url_collision")
            conn.execute(
                "INSERT INTO regional_official_source_links "
                "(source_family,source_identity,desk,canonical_official_url,"
                "publisher_posted_date,official_issuer,official_publisher,"
                "official_republisher,source_git_commit,metadata_version_sha256,"
                "first_seen_run,release_scope,release_proof_sha256,released_at_utc)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key[0],key[1],row["desk"],row["canonical_official_url"],
                 row["publisher_posted_date"],row["official_issuer"],
                 row["official_publisher"],row["official_republisher"],
                 row["source_git_commit"],row["metadata_version_sha256"],
                 row["first_seen_run"],"official_link_only",
                 proof_digest,as_of_utc))
            added += 1
        need(conn.execute("PRAGMA foreign_key_check").fetchall() == [],
             "regional_official_index_foreign_key_violation")
        conn.execute("RELEASE SAVEPOINT regional_link_admission")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT regional_link_admission")
        conn.execute("RELEASE SAVEPOINT regional_link_admission")
        raise
    return {"new_official_links": added, "unchanged_official_links": unchanged}
