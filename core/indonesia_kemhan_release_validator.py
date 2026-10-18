"""Trusted Kemhan Berita release validator: recompute every release gate.

``core.regional_official_link_release.admit`` refuses to write without a
trusted validator and never trusts a caller-supplied receipt. This module is
that validator for ``id_kemhan_news``. It derives the receipt itself from:

* the exact source Git history (frozen owner pin must be an ancestor, every
  ledger attempt must map to exactly one source-history commit);
* preserved capture bytes (each blob re-hashed against its content address,
  and every stored record's capture present);
* the owner-pinned frozen cohort, rebuilt from Git and compared against the
  pinned manifest digest, with the rolling cohort checked against it;
* GitHub's own Actions records for every ``schedule-slot`` ledger attempt,
  healthy or failed. Elapsed days are reported, never required (DECISION_LOG
  2026-10-18); at least one authenticated healthy scheduled run is.

It then hands ``admit()`` a closure that accepts only that exact receipt and
packet. Nothing here grants title, body, translation, media or model rights.

Review basis: the owner's 2026-10-15 declaration covers the pinned frozen
cohort, and the policy states no record-specific review receipts exist. The
owner's 2026-10-18 standing authorization (in the same pinned policy) admits
every verified, non-held record, existing and future, without per-record
review. The receipt says exactly that, and counts the records admitted
without any record-specific review. Without that authorization only the
frozen cohort is approved and later records are held.

A private-runner envelope (post-cutover originals exist only in the private
evidence repository) is an HMAC attestation by that runner. The public side
re-verifies everything it can independently: the frozen baseline is rebuilt
from the public frozen branch, and the private history must contain the final
public tip.
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from core.crossdesk_official_metadata_candidates import (
    KEMHAN_HELD, build as build_candidates, canonical,
)
from core.regional_official_link_release import (
    RegionalLinkHold, digest, load_owner_policy,
    standing_link_metadata_authorization, verify_cohort,
)

FAMILY = "id_kemhan_news"
FROZEN_PIN = "0595c6677be24f8f0f33aecb28eec0050e36e8f9"
PUBLIC_REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
PRIVATE_REPOSITORY = "VSSpowerlifting/ipr-source-evidence-private"
PUBLIC_FROZEN_REF = "shadow/indonesia-kemhan"
PRIVATE_REF = "archive/indonesia-kemhan"
SCHEDULED_WORKFLOWS = frozenset({
    (PUBLIC_REPOSITORY, ".github/workflows/indonesia_korea_shadow.yml"),
    (PRIVATE_REPOSITORY, ".github/workflows/indonesia_private_first_collector.yml"),
})
HEALTHY_RESULTS = frozenset({"ok", "ok_all_duplicates"})
HELD_IDENTITY = "kemhan:" + KEMHAN_HELD
RECEIPT_SCHEMA = "ipr-crossdesk-independent-release-proof/2"
ENVELOPE_SCHEMA = "ipr-indonesia-kemhan-signed-private-metadata/1"
REVIEW_BASIS = ("owner_2026-10-15_frozen_cohort_human_review_and_"
                "standing_verified_link_metadata_authorization")
STANDING_REVIEW_BASIS = ("owner_2026-10-18_standing_verified_link_metadata_"
                         "authorization_existing_and_future_records")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
RUN = re.compile(r"([1-9][0-9]{0,19})-([1-9][0-9]{0,5})\Z")
LOCAL_RUN = re.compile(r"local-native-[0-9]{8}-indonesia\Z")
CAPTURE = re.compile(r"state/captures/([a-f0-9]{64})\.bin\Z")
LEDGER = re.compile(r"state/ledger/[^/]+\.json\Z")
ATTEMPT = re.compile(r"state/private_attempts/([0-9]+-[0-9]+)\.json\Z")
SUBJECTS = (
    (re.compile(r"shadow\(indonesia\): initial native collection (\S+)\Z"), "shadow"),
    (re.compile(r"shadow\(indonesia\): run (\S+)\Z"), "shadow"),
    (re.compile(r"private-indonesia: preserve attempt (\S+)\Z"), "private"),
)
MAX_ENVELOPE_BYTES = 48 * 1024


class ValidatorHold(RegionalLinkHold):
    """Fixed reason codes only; no publisher text is ever interpolated."""


def need(ok, reason):
    if not ok:
        raise ValidatorHold(reason)


def _git(repo, *args, data=None):
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args], input=data, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=300,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        raise ValidatorHold("source_git_history_unavailable") from None


def _is_ancestor(repo, older, newer):
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", older, newer],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _blobs(repo, specs):
    """Read many exact blobs in one batch; returns {spec: bytes}."""
    if not specs:
        return {}
    out = _git(repo, "cat-file", "--batch",
               data=("\n".join(specs) + "\n").encode())
    result, pos = {}, 0
    for spec in specs:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        need(len(header) == 3 and header[1] == b"blob", "source_git_object_missing")
        size = int(header[2])
        result[spec] = out[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return result


def verify_history(repo, commit):
    """Authenticate the exact Git source state; returns attempt evidence."""
    need(type(commit) is str and SHA40.fullmatch(commit) is not None,
         "source_commit_not_immutable")
    need(_git(repo, "cat-file", "-t", commit).strip() == b"commit",
         "source_commit_object_missing")
    need(_is_ancestor(repo, FROZEN_PIN, commit),
         "frozen_owner_pin_not_in_source_history")
    names = [n for n in _git(repo, "ls-tree", "-r", "-z", "--name-only",
                             commit, "state").decode().split("\0") if n]
    need("state/shadow.db" in names and "state/clock.json" in names,
         "source_state_incomplete")
    captures = {}
    for name in names:
        m = CAPTURE.fullmatch(name)
        if m:
            captures[m.group(1)] = "%s:%s" % (commit, name)
    blobs = _blobs(repo, list(captures.values()))
    for address, spec in captures.items():
        need(hashlib.sha256(blobs[spec]).hexdigest() == address,
             "preserved_capture_digest_mismatch")

    ledgers = [n for n in names if LEDGER.fullmatch(n)]
    receipts = {ATTEMPT.fullmatch(n).group(1): n for n in names if ATTEMPT.fullmatch(n)}
    ledger_blobs = _blobs(repo, ["%s:%s" % (commit, n) for n in ledgers]
                          + ["%s:%s" % (commit, n) for n in receipts.values()]
                          + ["%s:state/clock.json" % commit])
    clock = json.loads(ledger_blobs["%s:state/clock.json" % commit])
    need(type(clock) is dict and clock.get("desk") == "indonesia"
         and clock.get("day_zero_run_id") == "local-native-20261006-indonesia",
         "source_day_zero_clock_mismatch")
    attempts = {}
    for name in ledgers:
        try:
            d = json.loads(ledger_blobs["%s:%s" % (commit, name)])
        except ValueError:
            raise ValidatorHold("source_ledger_unreadable") from None
        need(type(d) is dict and d.get("desk") == "indonesia"
             and type(d.get("run_id")) is str
             and (RUN.fullmatch(d["run_id"]) or LOCAL_RUN.fullmatch(d["run_id"]))
             and d["run_id"] not in attempts,
             "source_ledger_identity_invalid")
        report = d.get("listing_report") if type(d.get("listing_report")) is dict else {}
        attempts[d["run_id"]] = {
            "run_id": d["run_id"],
            "target_date": d.get("target_date"),
            "target_date_source": d.get("target_date_source"),
            "healthy": (d.get("result") in HEALTHY_RESULTS and d.get("health") == "ok"
                        and d.get("listing_status") == "ok"
                        and report.get("window_proven") is True
                        and d.get("fetch_failures") == 0
                        and d.get("extraction_failures") == 0),
        }
    exit_codes = {}
    for run_id, name in receipts.items():
        try:
            r = json.loads(ledger_blobs["%s:%s" % (commit, name)])
        except ValueError:
            raise ValidatorHold("private_attempt_receipt_unreadable") from None
        need(type(r) is dict and r.get("schema") == "ipr-indonesia-private-attempt/1"
             and r.get("run_attempt") == run_id
             and type(r.get("collector_exit_status")) is int
             and r.get("collection_success_claim") is False
             and r.get("source_or_publication_rights_granted") is False,
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
    # Every collector ledger maps to exactly one history commit. A private
    # commit always carries its attempt receipt, even when the collector died
    # before writing a ledger; that is a visible failure, not a hold.
    need(set(attempts) <= commits["shadow"] | commits["private"]
         and commits["shadow"] <= set(attempts)
         and commits["private"] == set(receipts),
         "attempt_ledger_and_source_history_disagree")

    db_bytes = _blobs(repo, ["%s:state/shadow.db" % commit])["%s:state/shadow.db" % commit]
    with tempfile.TemporaryDirectory(prefix="ipr-kemhan-validator-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(db_bytes)
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as cx:
            need(cx.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                 "source_sqlite_integrity_failed")
            rows = cx.execute("SELECT text_original, content_sha256, capture_sha256 "
                              "FROM shadow_records").fetchall()
    for text, content_sha, capture_sha in rows:
        need(type(text) is str and hashlib.sha256(text.encode("utf-8")).hexdigest() == content_sha
             and capture_sha in captures,
             "stored_original_not_bound_to_preserved_capture")
    return {
        "attempts": sorted(attempts.values(), key=lambda a: a["run_id"]),
        "ledger_attempts": len(attempts),
        "private_attempts_without_ledger": len(set(receipts) - set(attempts)),
        "private_attempts_nonzero_exit": sum(1 for v in exit_codes.values() if v != 0),
        "unhealthy_attempts": sum(1 for a in attempts.values() if not a["healthy"]),
        "captures_verified": len(captures),
        "stored_originals": len(rows),
    }


def authenticate_scheduled_history(attempts, fetch_run):
    """Check every ledger ``schedule-slot`` claim against GitHub's own record.

    Failed attempts are authenticated too, so a failure cannot be relabelled.
    ``fetch_run(run_number)`` returns the Actions run JSON, or None when that
    run is not visible to this caller (e.g. a private run read from public).
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
                              country="indonesia", max_results=300)
    except ReaderHold:
        raise ValidatorHold("private_reader_refused_source_snapshot") from None
    return build_candidates(report, FAMILY)


def release_subset(eligible, baseline, policy):
    """Return (approved, held_unreviewed, outside_frozen_cohort) identities.

    Semantic holds never reach ``eligible``. Under the standing authorization
    every eligible row is approved; the ones outside the frozen cohort are
    reported, because no human reviewed them record by record.
    """
    reviewed = {r["source_identity"] for r in baseline["records"]}
    outside = sorted(r["source_identity"] for r in eligible
                     if r["source_identity"] not in reviewed)
    if standing_link_metadata_authorization(policy, FAMILY):
        return list(eligible), [], outside
    return ([r for r in eligible if r["source_identity"] in reviewed],
            outside, [])


def _receipt(packet, subset, policy, validator_ref, evidence, history):
    approved, unreviewed, outside = subset
    standing = standing_link_metadata_authorization(policy, FAMILY)
    need(type(validator_ref) is str and SHA40.fullmatch(validator_ref) is not None,
         "trusted_validator_ref_not_immutable")
    need(policy.get("owner_authorizes_automated_verified_link_metadata") is True,
         "owner_link_metadata_authorization_missing")
    need(policy.get("machine_verified_record_specific_human_review_receipts_in_repository")
         is False, "owner_review_basis_changed")
    ids = sorted(r["source_identity"] for r in approved)
    need(bool(ids), "no_reviewed_source_to_release")
    need(HELD_IDENTITY not in ids, "semantic_hold_would_be_released")
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
        # Read from the repository-pinned owner policy, not inferred.
        "standing_link_metadata_authorization_verified": standing,
        "released_without_record_specific_review_sha256": digest(outside),
        "released_without_record_specific_review_count": len(outside),
        "scheduled_history_authenticated": True,
        "all_visible_actions_attempts_reconciled": True,
        "official_metadata_link_use_checked": True,
        "known_semantic_holds_enforced": True,
        # The owner's standing metadata-only authorization (checked above).
        "production_live_site_authorized": True,
        "source_capture_version_reverified": True,
        "trusted_validator_ref": validator_ref,
        "review_basis": STANDING_REVIEW_BASIS if standing else REVIEW_BASIS,
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
                and all(a["source_identity"] in allowed for a in approved)
                and HELD_IDENTITY not in {a["source_identity"] for a in approved})
    return trusted_validator


def validate_source_checkout(repo, commit, *, fetch_run, validator_ref):
    """Full validation of an exact source history this caller can read."""
    policy = load_owner_policy()
    evidence = verify_history(repo, commit)
    baseline = candidate_packet(repo, FROZEN_PIN)
    packet = baseline if commit == FROZEN_PIN else candidate_packet(repo, commit)
    eligible = verify_cohort(packet, policy,
                             baseline_packet=None if commit == FROZEN_PIN else baseline)
    subset = release_subset(eligible, baseline, policy)
    approved = subset[0]
    history = authenticate_scheduled_history(evidence["attempts"], fetch_run)
    receipt = _receipt(packet, subset, policy, validator_ref, evidence, history)
    return {"packet": packet, "policy": policy, "receipt": receipt,
            "baseline_packet": None if commit == FROZEN_PIN else baseline,
            "eligible": eligible, "approved": approved,
            "trusted_validator": _trust(receipt, packet, approved)}


# --- private runner -> public production envelope -------------------------

def _mac(key, body):
    need(type(key) is bytes and len(key) >= 32, "bridge_key_missing_or_short")
    return hmac.new(key, body, hashlib.sha256).hexdigest()


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
    # The private history must have inherited the exact final public tip.
    need(envelope["public_frozen_tip"] == public_frozen_tip,
         "private_history_not_bound_to_public_frozen_tip")
    packet, private = envelope["packet"], envelope["private_receipt"]
    need(type(private) is dict and type(packet) is dict
         and private.get("source_git_commit") == packet.get("source_git_commit")
         and private.get("metadata_manifest_sha256") == packet.get("metadata_manifest_sha256")
         and private.get("schema") == RECEIPT_SCHEMA
         and private.get("review_basis") in (REVIEW_BASIS, STANDING_REVIEW_BASIS)
         and private.get("record_specific_review_receipts_verified") is False
         and type(private.get("trusted_validator_ref")) is str
         and SHA40.fullmatch(private["trusted_validator_ref"]) is not None
         and all(private.get(k) is True for k in (
             "owner_review_declaration_bound_to_frozen_manifest",
             "scheduled_history_authenticated",
             "all_visible_actions_attempts_reconciled",
             "source_capture_version_reverified")),
         "private_runner_release_evidence_incomplete")
    # The private runner must have run reviewed public validator code.
    need(_is_ancestor(public_main, private["trusted_validator_ref"], "HEAD"),
         "private_validator_code_not_on_public_main")
    policy = load_owner_policy()
    # Independent: frozen baseline rebuilt from the public frozen branch.
    need(_is_ancestor(public_checkout, FROZEN_PIN, public_frozen_tip),
         "public_frozen_branch_lacks_owner_pin")
    baseline = candidate_packet(public_checkout, FROZEN_PIN)
    eligible = verify_cohort(packet, policy, baseline_packet=baseline)
    # Approval is recomputed here from the public baseline, never taken from
    # the private runner's list.
    subset = release_subset(eligible, baseline, policy)
    approved = subset[0]
    public_evidence = verify_history(public_checkout, public_frozen_tip)
    # Scheduled history is re-authenticated here from GitHub's public run
    # records, not taken from the private runner's attestation.
    history = authenticate_scheduled_history(public_evidence["attempts"], fetch_run)
    receipt = _receipt(packet, subset, policy, validator_ref,
                       {"public_frozen_history": {k: v for k, v in public_evidence.items()
                                                  if k != "attempts"},
                        "private_runner_evidence": private.get("evidence")},
                       history)
    return {"packet": packet, "policy": policy, "receipt": receipt,
            "baseline_packet": baseline, "eligible": eligible, "approved": approved,
            "trusted_validator": _trust(receipt, packet, approved),
            "source_run_attempt": envelope["source_run_attempt"]}
