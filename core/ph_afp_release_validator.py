"""Trusted AFP release validator: recompute every release gate for ph_afp_articles.

``core.regional_official_link_release.admit`` refuses to write without a
trusted validator and never trusts a caller-supplied receipt. This module is
that validator for the Armed Forces of the Philippines articles family. It
derives the receipt itself from:

* the exact AFP source Git history (``shadow/ph-afp`` before custody cutover,
  ``archive/ph-afp`` in private custody after it): the owner's frozen pin must
  be an ancestor and every ledger attempt must map to exactly one commit;
* the AFP layout's own evidence: request-evidence files re-hashed against
  their ledger digests, every retained payload re-hashed against its content
  address, every SQLite capture re-hashed, and every stored original bound to
  its capture;
* the owner-pinned frozen 23-record cohort, rebuilt from Git and compared with
  the pinned manifest digest, with the rolling cohort checked against it;
* GitHub's own Actions records for every ``schedule-slot`` ledger attempt.
  Elapsed days are reported, never required (DECISION_LOG 2026-10-18).

Review basis: the owner's 2026-10-15 declaration covers the frozen cohort and
the policy states no record-specific review receipts exist; the receipt says
exactly that. Records first collected after the pin are held, not admitted.
Nothing here grants AFP title, body, photograph, translation or model rights.

AFP is not Kemhan: there is no listing-window proof field, no semantic hold
identity, the clock carries no desk field, and private attempt receipts live
at the archive root (``private_attempts/``), not under ``state/``.
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import re
import sqlite3
import tempfile
from pathlib import Path

from core.crossdesk_official_metadata_candidates import (
    build as build_candidates, canonical,
)
# Generic, family-neutral Git/MAC helpers; the Kemhan constants are not used.
from core.indonesia_kemhan_release_validator import (
    ValidatorHold, _blobs, _git, _is_ancestor, _mac, need, reviewed_subset,
)
from core.regional_official_link_release import (
    digest, load_owner_policy, verify_cohort,
)

FAMILY = "ph_afp_articles"
DESK = "philippines"
FROZEN_PIN = "8a63ba423818e30d147096fd1a32949cf6905ee5"
PUBLIC_REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
PRIVATE_REPOSITORY = "VSSpowerlifting/ipr-source-evidence-private"
PUBLIC_FROZEN_REF = "shadow/ph-afp"
PRIVATE_REF = "archive/ph-afp"
SCHEDULED_WORKFLOWS = frozenset({
    (PUBLIC_REPOSITORY, ".github/workflows/ph_afp_shadow.yml"),
    (PRIVATE_REPOSITORY, ".github/workflows/afp_private_first_collector.yml"),
})
HEALTHY_RESULTS = frozenset({"ok", "ok_all_duplicates"})
DAY_ZERO_RUN = "37631681338-1"
DAY_ZERO_UTC = "2026-10-07T13:51:44+00:00"
RECEIPT_SCHEMA = "ipr-crossdesk-independent-release-proof/2"
ENVELOPE_SCHEMA = "ipr-ph-afp-signed-private-metadata/1"
ATTEMPT_SCHEMA = "ipr-ph-afp-private-attempt/1"
REVIEW_BASIS = ("owner_2026-10-15_frozen_cohort_human_review_and_"
                "standing_verified_link_metadata_authorization")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
RUN = re.compile(r"([1-9][0-9]{0,19})-([1-9][0-9]{0,5})\Z")
PAYLOAD = re.compile(r"state/evidence/payloads/([a-f0-9]{64})\.bin\Z")
EVIDENCE = re.compile(r"state/evidence/([1-9][0-9]{0,19}-[1-9][0-9]{0,5})\.json\Z")
LEDGER = re.compile(r"state/ledger/[^/]+\.json\Z")
ATTEMPT = re.compile(r"private_attempts/([1-9][0-9]{0,19}-[1-9][0-9]{0,5})\.json\Z")
SUBJECTS = (
    (re.compile(r"shadow\(ph-afp\): run (\S+)\Z"), "shadow"),
    (re.compile(r"private-ph-afp: preserve attempt (\S+)\Z"), "private"),
)
MAX_ENVELOPE_BYTES = 48 * 1024


def _ledger_healthy(d):
    """Every AFP failure counter the collector records must be clean."""
    return (d.get("result") in HEALTHY_RESULTS and d.get("health") == "ok"
            and d.get("listing_status") == "ok"
            and d.get("robots_status") == "allowed"
            and d.get("aborted") is None and d.get("rehearsal") is False
            and all(d.get(k) == 0 for k in (
                "fetch_failures", "extraction_failures", "access_failures",
                "redirect_refusals", "identity_collisions")))


def verify_history(repo, commit):
    """Authenticate the exact AFP Git source state; returns attempt evidence."""
    need(type(commit) is str and SHA40.fullmatch(commit) is not None,
         "source_commit_not_immutable")
    need(_git(repo, "cat-file", "-t", commit).strip() == b"commit",
         "source_commit_object_missing")
    need(_is_ancestor(repo, FROZEN_PIN, commit),
         "frozen_owner_pin_not_in_source_history")
    names = [n for n in _git(repo, "ls-tree", "-r", "-z", "--name-only", commit,
                             "state", "private_attempts").decode().split("\0") if n]
    need("state/shadow.db" in names and "state/clock.json" in names,
         "source_state_incomplete")
    payloads = {}
    for name in names:
        m = PAYLOAD.fullmatch(name)
        if m:
            payloads[m.group(1)] = "%s:%s" % (commit, name)
    payload_blobs = _blobs(repo, list(payloads.values()))
    for address, spec in payloads.items():
        need(hashlib.sha256(payload_blobs[spec]).hexdigest() == address,
             "preserved_capture_digest_mismatch")

    ledgers = [n for n in names if LEDGER.fullmatch(n)]
    evidence_files = {EVIDENCE.fullmatch(n).group(1): n
                      for n in names if EVIDENCE.fullmatch(n)}
    receipts = {ATTEMPT.fullmatch(n).group(1): n for n in names if ATTEMPT.fullmatch(n)}
    specs = (["%s:%s" % (commit, n) for n in ledgers]
             + ["%s:%s" % (commit, n) for n in evidence_files.values()]
             + ["%s:%s" % (commit, n) for n in receipts.values()]
             + ["%s:state/clock.json" % commit])
    blobs = _blobs(repo, specs)
    try:
        clock = json.loads(blobs["%s:state/clock.json" % commit])
    except ValueError:
        raise ValidatorHold("source_day_zero_clock_mismatch") from None
    need(type(clock) is dict and clock.get("day_zero_run_id") == DAY_ZERO_RUN
         and clock.get("day_zero_utc") == DAY_ZERO_UTC,
         "source_day_zero_clock_mismatch")

    attempts = {}
    for name in ledgers:
        try:
            d = json.loads(blobs["%s:%s" % (commit, name)])
        except ValueError:
            raise ValidatorHold("source_ledger_unreadable") from None
        need(type(d) is dict and d.get("desk") == "ph-afp"
             and type(d.get("run_id")) is str and RUN.fullmatch(d["run_id"])
             and d["run_id"] not in attempts,
             "source_ledger_identity_invalid")
        # A ledger's request evidence must be the exact preserved file, and
        # every retained payload it lists must be present and content-addressed.
        ev = d.get("request_evidence")
        need(type(ev) is dict and ev.get("path") == "evidence/%s.json" % d["run_id"]
             and d["run_id"] in evidence_files, "request_evidence_missing")
        raw = blobs["%s:%s" % (commit, evidence_files[d["run_id"]])]
        need(hashlib.sha256(raw).hexdigest() == ev.get("sha256"),
             "request_evidence_digest_mismatch")
        try:
            requests = json.loads(raw)
        except ValueError:
            raise ValidatorHold("request_evidence_unreadable") from None
        need(type(requests) is list and len(requests) == ev.get("requests"),
             "request_evidence_count_mismatch")
        for req in requests:
            need(type(req) is dict and (req.get("payload_retained") is not True
                                        or req.get("payload_sha256") in payloads),
                 "retained_payload_missing")
        attempts[d["run_id"]] = {
            "run_id": d["run_id"],
            "target_date": d.get("target_date"),
            "target_date_source": d.get("target_date_source"),
            "healthy": _ledger_healthy(d),
        }
    exit_codes = {}
    for run_id, name in receipts.items():
        try:
            r = json.loads(blobs["%s:%s" % (commit, name)])
        except ValueError:
            raise ValidatorHold("private_attempt_receipt_unreadable") from None
        need(type(r) is dict and r.get("schema") == ATTEMPT_SCHEMA
             and r.get("run_attempt") == run_id
             and type(r.get("collector_exit_status")) is int
             and r.get("public_release_approved") is False
             and r.get("original_body_reuse_approved") is False,
             "private_attempt_receipt_invalid")
        exit_codes[run_id] = r["collector_exit_status"]

    commits = {"shadow": set(), "private": set()}
    for line in _git(repo, "log", "--format=%s", commit).decode().split("\n"):
        if not line:
            continue
        for pattern, kind in SUBJECTS:
            m = pattern.fullmatch(line)
            if m:
                need(m.group(1) not in commits["shadow"] | commits["private"],
                     "duplicate_source_attempt_commit")
                commits[kind].add(m.group(1))
                break
        else:
            raise ValidatorHold("unrecognized_source_history_commit")
    # A private commit always carries its attempt receipt, even when the
    # collector died before writing a ledger: a visible failure, not a hold.
    need(set(attempts) <= commits["shadow"] | commits["private"]
         and commits["shadow"] <= set(attempts)
         and commits["private"] == set(receipts),
         "attempt_ledger_and_source_history_disagree")

    db_bytes = _blobs(repo, ["%s:state/shadow.db" % commit])["%s:state/shadow.db" % commit]
    with tempfile.TemporaryDirectory(prefix="ipr-afp-validator-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(db_bytes)
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as cx:
            need(cx.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                 "source_sqlite_integrity_failed")
            captures = set()
            for payload, address in cx.execute(
                    "SELECT payload, payload_sha256 FROM captures"):
                need(type(payload) is bytes
                     and hashlib.sha256(payload).hexdigest() == address,
                     "preserved_capture_digest_mismatch")
                captures.add(address)
            rows = cx.execute("SELECT text_original, content_sha256, capture_sha256 "
                              "FROM shadow_records").fetchall()
    # An image-only AFP article stores '' with the empty-string digest; that
    # is still a hash-bound original, and still needs its preserved capture.
    for text, content_sha, capture_sha in rows:
        need(type(text) is str
             and hashlib.sha256(text.encode("utf-8")).hexdigest() == content_sha
             and capture_sha in captures,
             "stored_original_not_bound_to_preserved_capture")
    return {
        "attempts": sorted(attempts.values(), key=lambda a: a["run_id"]),
        "ledger_attempts": len(attempts),
        "private_attempts_without_ledger": len(set(receipts) - set(attempts)),
        "private_attempts_nonzero_exit": sum(1 for v in exit_codes.values() if v != 0),
        "unhealthy_attempts": sum(1 for a in attempts.values() if not a["healthy"]),
        "payloads_verified": len(payloads),
        "captures_verified": len(captures),
        "stored_originals": len(rows),
    }


def authenticate_scheduled_history(attempts, fetch_run):
    """Check every ledger ``schedule-slot`` claim against GitHub's own record.

    Failed attempts are authenticated too, so a failure cannot be relabelled.
    ``fetch_run(run_number)`` returns the Actions run JSON, or None when that
    run is not visible to this caller (a private run read from public).
    """
    days, failed, hidden = set(), 0, 0
    for a in attempts:
        m = RUN.fullmatch(a["run_id"])
        if not (m and a["target_date_source"] == "schedule-slot"):
            continue
        run = fetch_run(m.group(1))
        if run is None:
            hidden += 1
            continue
        need(type(run) is dict and str(run.get("id")) == m.group(1)
             and str(run.get("run_attempt")) == m.group(2),
             "scheduled_run_identity_mismatch")
        repo = (run.get("repository") or {}).get("full_name")
        need(run.get("event") == "schedule" and run.get("head_branch") == "main"
             and (repo, run.get("path")) in SCHEDULED_WORKFLOWS,
             "ledger_claims_schedule_github_does_not")
        if a["healthy"]:
            days.add(a["target_date"])
        else:
            failed += 1
    need(bool(days), "scheduled_history_not_authenticated")
    return {"healthy_days": sorted(days), "failed_attempts": failed,
            "claims_not_visible": hidden}


def candidate_packet(repo, commit):
    from scripts.private_country_desk_reader import ReaderHold, build as read_private
    try:
        report = read_private([",".join((FAMILY, str(repo), commit))],
                              country=DESK, max_results=300)
    except ReaderHold:
        raise ValidatorHold("private_reader_refused_source_snapshot") from None
    return build_candidates(report, FAMILY)


def _receipt(packet, approved, unreviewed, policy, validator_ref, evidence, history):
    need(type(validator_ref) is str and SHA40.fullmatch(validator_ref) is not None,
         "trusted_validator_ref_not_immutable")
    need(policy.get("owner_authorizes_automated_verified_link_metadata") is True,
         "owner_link_metadata_authorization_missing")
    need(policy.get("machine_verified_record_specific_human_review_receipts_in_repository")
         is False, "owner_review_basis_changed")
    ids = sorted(r["source_identity"] for r in approved)
    need(bool(ids), "no_reviewed_source_to_release")
    return {
        "schema": RECEIPT_SCHEMA,
        "source_family": FAMILY,
        "source_git_commit": packet["source_git_commit"],
        "metadata_manifest_sha256": packet["metadata_manifest_sha256"],
        "approved_source_identities": ids,
        "eligible_source_identities_sha256": digest(ids),
        # verify_cohort rebuilt the pinned frozen cohort from Git and matched
        # the owner's manifest; that cohort is what the owner declared reviewed.
        "owner_review_declaration_bound_to_frozen_manifest": True,
        # Copied from the owner policy, which states none exist.
        "record_specific_review_receipts_verified": False,
        "held_unreviewed_source_identities_sha256": digest(unreviewed),
        "held_unreviewed_count": len(unreviewed),
        "scheduled_history_authenticated": True,
        "all_visible_actions_attempts_reconciled": True,
        "official_metadata_link_use_checked": True,
        # AFP has no owner semantic-hold identity; verify_cohort still enforces
        # the policy's (empty) known_excluded_source_identities list.
        "known_semantic_holds_enforced": True,
        # The owner's standing metadata-only authorization (checked above).
        "production_live_site_authorized": True,
        "source_capture_version_reverified": True,
        "trusted_validator_ref": validator_ref,
        "review_basis": REVIEW_BASIS,
        "frozen_review_cohort_commit": FROZEN_PIN,
        "authenticated_scheduled_days": history["healthy_days"],
        "authenticated_failed_scheduled_attempts": history["failed_attempts"],
        "scheduled_claims_not_visible": history["claims_not_visible"],
        "evidence": {k: v for k, v in evidence.items() if k != "attempts"},
    }


def _trust(receipt, packet, approved):
    allowed = {r["source_identity"] for r in approved}

    def trusted_validator(r, p, approved):
        return (r is receipt and p is packet
                and all(a["source_identity"] in allowed for a in approved))
    return trusted_validator


def validate_source_checkout(repo, commit, *, fetch_run, validator_ref):
    """Full validation of an exact AFP source history this caller can read."""
    policy = load_owner_policy()
    evidence = verify_history(repo, commit)
    baseline = candidate_packet(repo, FROZEN_PIN)
    packet = baseline if commit == FROZEN_PIN else candidate_packet(repo, commit)
    eligible = verify_cohort(packet, policy,
                             baseline_packet=None if commit == FROZEN_PIN else baseline)
    approved, unreviewed = reviewed_subset(eligible, baseline)
    history = authenticate_scheduled_history(evidence["attempts"], fetch_run)
    receipt = _receipt(packet, approved, unreviewed, policy, validator_ref,
                       evidence, history)
    return {"packet": packet, "policy": policy, "receipt": receipt,
            "baseline_packet": None if commit == FROZEN_PIN else baseline,
            "eligible": eligible, "approved": approved,
            "trusted_validator": _trust(receipt, packet, approved)}


# --- private runner -> public production envelope -------------------------
# After custody cutover new AFP originals exist only in the private archive.
# The private runner signs a metadata-only envelope; the public side
# re-verifies everything it can: the frozen baseline from public Git, the
# public history's scheduled runs from GitHub, and that the validator code the
# runner used is on public main. Approval is never taken from the envelope.

def sign_envelope(validated, *, key, source_run_attempt, public_frozen_tip):
    """Private runner only: compress and MAC metadata-only release evidence."""
    need(RUN.fullmatch(source_run_attempt or "") is not None, "source_run_attempt_invalid")
    need(SHA40.fullmatch(public_frozen_tip or "") is not None, "public_frozen_tip_invalid")
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "source_repository": PRIVATE_REPOSITORY,
        "source_ref": PRIVATE_REF,
        "source_run_attempt": source_run_attempt,
        "public_frozen_tip": public_frozen_tip,
        "packet": validated["packet"],
        "private_receipt": validated["receipt"],
    }
    body = gzip.compress(canonical(envelope), mtime=0)
    need(len(body) <= MAX_ENVELOPE_BYTES, "signed_envelope_too_large")
    return body, _mac(key, body)


def validate_signed_envelope(body, mac_hex, *, key, public_checkout,
                             public_frozen_tip, validator_ref, public_main,
                             fetch_run):
    """Public production: authenticate a private envelope, then re-verify."""
    need(type(body) is bytes and 0 < len(body) <= MAX_ENVELOPE_BYTES,
         "signed_envelope_size_invalid")
    need(type(mac_hex) is str and SHA256.fullmatch(mac_hex) is not None
         and hmac.compare_digest(_mac(key, body), mac_hex),
         "signed_envelope_mac_invalid")
    try:
        envelope = json.loads(gzip.decompress(body).decode("utf-8"))
    except (OSError, ValueError, UnicodeError, EOFError):
        raise ValidatorHold("signed_envelope_unreadable") from None
    need(type(envelope) is dict and set(envelope) == {
        "schema", "source_repository", "source_ref", "source_run_attempt",
        "public_frozen_tip", "packet", "private_receipt"}
         and envelope["schema"] == ENVELOPE_SCHEMA
         and envelope["source_repository"] == PRIVATE_REPOSITORY
         and envelope["source_ref"] == PRIVATE_REF
         and RUN.fullmatch(envelope["source_run_attempt"] or "") is not None,
         "signed_envelope_schema_invalid")
    need(envelope["public_frozen_tip"] == public_frozen_tip,
         "private_history_not_bound_to_public_frozen_tip")
    packet, private = envelope["packet"], envelope["private_receipt"]
    need(type(private) is dict and type(packet) is dict
         and private.get("source_family") == FAMILY
         and private.get("source_git_commit") == packet.get("source_git_commit")
         and private.get("metadata_manifest_sha256") == packet.get("metadata_manifest_sha256")
         and private.get("schema") == RECEIPT_SCHEMA
         and private.get("review_basis") == REVIEW_BASIS
         and private.get("record_specific_review_receipts_verified") is False
         and type(private.get("trusted_validator_ref")) is str
         and SHA40.fullmatch(private["trusted_validator_ref"]) is not None
         and all(private.get(k) is True for k in (
             "owner_review_declaration_bound_to_frozen_manifest",
             "scheduled_history_authenticated",
             "all_visible_actions_attempts_reconciled",
             "source_capture_version_reverified")),
         "private_runner_release_evidence_incomplete")
    need(_is_ancestor(public_main, private["trusted_validator_ref"], "HEAD"),
         "private_validator_code_not_on_public_main")
    policy = load_owner_policy()
    need(_is_ancestor(public_checkout, FROZEN_PIN, public_frozen_tip),
         "public_frozen_branch_lacks_owner_pin")
    baseline = candidate_packet(public_checkout, FROZEN_PIN)
    eligible = verify_cohort(packet, policy, baseline_packet=baseline)
    approved, unreviewed = reviewed_subset(eligible, baseline)
    public_evidence = verify_history(public_checkout, public_frozen_tip)
    history = authenticate_scheduled_history(public_evidence["attempts"], fetch_run)
    receipt = _receipt(packet, approved, unreviewed, policy, validator_ref,
                       {"public_frozen_history": {k: v for k, v in public_evidence.items()
                                                  if k != "attempts"},
                        "private_runner_evidence": private.get("evidence")},
                       history)
    return {"packet": packet, "policy": policy, "receipt": receipt,
            "baseline_packet": baseline, "eligible": eligible, "approved": approved,
            "trusted_validator": _trust(receipt, packet, approved),
            "source_run_attempt": envelope["source_run_attempt"]}
