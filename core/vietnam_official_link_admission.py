"""Vietnam adapter for the shared regional official-link store.

Replays exact Git originals using the existing ministry reviewer and authenticates
the source tip/Actions attempt using the existing read-only GitHub attestor.
Human review is a separately sealed, exact-version metadata-only decision using
the regional review HMAC convention. No signer, collector or model is invoked.
MOIT's two source-use holds remain independent and unconditional here.
"""
from __future__ import annotations

import hashlib
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from core.collection.vietnam_sources import SOURCES
from core.regional_reviewed_evidence import _canonical, verify_review_seal
from core.regional_official_link_release import store_verified_links
from scripts import review_vietnam_ministry_state as ministry
from scripts import review_vietnam_shadow_state as formal
from scripts.attest_vietnam_run_state import one_family, PREFIX, RUN_ID, require_persisted_attempt

SCHEMA = "ipr-vietnam-official-link-candidates/1"
DECISION = "ipr-vietnam-reviewed-official-link-release/1"
DOMAIN = b"IPR-VIETNAM-OFFICIAL-LINK-RELEASE-v1\n"
MPS = "vn_mps_foreign_affairs_vi"
HOLDS = {slug: "moit_written_consent_and_robots_review_required"
         for slug in SOURCES if slug != MPS}
ISSUERS = {slug: "vn_mps" if slug == MPS else "vn_moit" for slug in SOURCES}
LABELS = {slug: "Vietnam Ministry of Public Security official source" if slug == MPS
          else "Vietnam Ministry of Industry and Trade official source" for slug in SOURCES}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def exact_url(family, identity, url):
    need(family in SOURCES and type(url) is str and type(identity) is str
         and len(url) <= 2048 and SOURCES[family].identity(url) == identity,
         "vietnam_source_identity_or_url_invalid")


def prepare(state_repo, commit, family, *, private=False):
    """Local immutable Git replay; return metadata/hashes only, all held."""
    need(family in SOURCES, "unknown_vietnam_source_family")
    repo = formal.resolve_state_repo(state_repo)
    state_ref = SOURCES[family].state_branch
    if private:
        state_ref = state_ref.replace("shadow/", "archive/", 1)
    formal.verify_state_commit(repo, commit, state_ref)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-links-") as tmp:
        state = formal.export_state_tree(repo, commit, Path(tmp) / "state")
        evidence = ministry.review(state, family)
        runs = {r["run_id"]: r for r in evidence["runs"]}
        versions = {(v["source_identity"], v["content_sha256"]): v
                    for v in evidence["versions"]}
        observations = {(o["run_id"], o["source_identity"]): o
                        for o in evidence["observations"]}
        metadata = {(m["run_id"], m["source_identity"]): ministry.loads(m["metadata_json"])
                    for m in evidence["source_metadata"]}
        rows = []
        for record in evidence["records"]:
            identity = record["source_identity"]
            exact_url(family, identity, record["url"])
            version = versions[(identity, record["current_content_sha256"])]
            first = version["first_seen_run"]
            observation = observations[(first, identity)]
            need(runs[first]["health"] == "ok", "version_from_failed_collection")
            need(not ministry.loads(observation["anomalies_json"]),
                 "vietnam_original_has_unresolved_anomalies")
            # Re-extract preserved HTML, not merely the SQLite hash envelope.
            from core.collection.contract import CandidateReference, CaptureResult
            from scraper.sources.vn_ministries import VNMinistryAdapter
            from scripts.shadow_collect_vietnam_ministry import load_source
            raw = (state / "captures" / (observation["capture_sha256"] + ".bin")).read_bytes()
            capture = CaptureResult(CandidateReference(record["url"], family), "ok", record["url"],
                                    final_url=record["url"], body=raw.decode("utf-8"))
            extracted = VNMinistryAdapter(load_source(family)).extract(capture)
            need(extracted.status == "ok" and len(extracted.documents) == 1
                 and extracted.documents[0].extra["content_sha256"] == version["content_sha256"]
                 and extracted.documents[0].published_date == record["published_date"],
                 "vietnam_capture_and_extracted_version_differ")
            row = {
                "source_family": family, "source_identity": identity, "desk": "vietnam",
                "canonical_official_url": record["url"],
                "publisher_posted_date": record["published_date"],
                "official_issuer": ISSUERS[family], "official_publisher": ISSUERS[family],
                "official_republisher": None, "source_git_commit": commit,
                "first_seen_run": record["first_seen_run"],
                "content_sha256": version["content_sha256"],
                "capture_sha256": observation["capture_sha256"],
                "version_first_seen_run": first,
                "collector_commit": runs[first]["collector_commit"],
                "collection_target_source": runs[first]["target_date_source"],
                "rss_instant_utc": metadata[(first, identity)].get("rss_instant_utc"),
            }
            # A recollection's Git SHA/HTML framing may change without a new
            # original-text version. Stable content identity controls replay.
            row["metadata_version_sha256"] = digest({k: v for k, v in row.items()
                if k not in ("source_git_commit", "capture_sha256", "version_first_seen_run",
                             "collector_commit", "collection_target_source")})
            rows.append(row)
        latest = evidence["runs"][-1]
        return {
            "schema": SCHEMA, "source_family": family, "source_git_commit": commit,
            "source_db_sha256": evidence["inputs"]["shadow.db"],
            "latest_run": latest["run_id"], "logical_date": latest["target_date"],
            "records": rows, "source_hold": HOLDS.get(family, "individual_review_required"),
            "source_anomalies": sorted({a for r in evidence["runs"]
                                        for a in r.get("source_anomalies", [])}),
            "public_release_authorized": False,
        }


def authenticate(packet, api, as_of):
    """Fresh API tip/attempt readback, never a JSON success checkbox."""
    family = packet["source_family"]
    observed = one_family(api, {
        "source_slug": family, "state_branch": SOURCES[family].state_branch,
        "workflow": ".github/workflows/vietnam_ministry_shadow.yml", "cron": "17 18 * * *",
    }, as_of)
    need(observed["state_head_sha"] == packet["source_git_commit"]
         and observed["run_id"] == packet["latest_run"]
         and observed["logical_date"] == packet["logical_date"],
         "stale_vietnam_source_or_attempt")
    attempts = {}
    for row in packet["records"]:
        rid = row["version_first_seen_run"]
        match = RUN_ID.fullmatch(rid)
        need(match is not None, "vietnam_original_attempt_identity_invalid")
        if rid not in attempts:
            attempts[rid] = api.get(PREFIX + "/actions/runs/%s/attempts/%s" % match.groups())
        run = attempts[rid]
        need(type(run) is dict and type(run.get("path")) is str,
             "vietnam_original_collection_attempt_malformed")
        event = "schedule" if row["collection_target_source"] == "schedule-slot" else "workflow_dispatch"
        need(run.get("id") == int(match.group(1))
             and run.get("run_attempt") == int(match.group(2))
             and run.get("event") == event and run.get("head_sha") == row["collector_commit"]
             and run.get("path", "").split("@")[0] == ".github/workflows/vietnam_ministry_shadow.yml",
             "vietnam_original_collection_attempt_mismatch")
        require_persisted_attempt(api, run)
    return observed


def reviewed_rows(packet, sealed, *, secret, as_of_utc, candidate_sha256=None):
    """Verify exact source/rights decision before the shared SQLite savepoint.

    A seal proves possession of the separate reviewer key, not legal consent.
    The owner must actually authorize this exact decision. There are no live
    decisions or provisioned publication keys supplied by this module.
    """
    family = packet["source_family"]
    need(family not in HOLDS, HOLDS.get(family, "vietnam_source_held"))
    need(type(sealed) is dict and set(sealed) == {"review", "hmac_sha256"},
         "signed_vietnam_release_decision_missing")
    decision = sealed["review"]
    need(type(decision) is dict and set(decision) == {
        "schema", "candidate_sha256", "approved_source_identities", "reviewer",
        "reviewed_on", "rights_basis", "approval_reference", "permitted_fields",
        "original_language_and_source_version_checked", "production_release_authorized",
        "protected_custody_verified", "custody_reference",
    }, "vietnam_release_decision_scope_invalid")
    verify_review_seal(sealed, secret, domain=DOMAIN)
    now = datetime.strptime(as_of_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    need(type(decision["reviewed_on"]) is str, "vietnam_review_chronology_invalid")
    reviewed = date.fromisoformat(decision["reviewed_on"])
    need(reviewed.isoformat() == decision["reviewed_on"] and reviewed <= now.date()
         and date.fromisoformat(packet["logical_date"]) <= reviewed,
         "vietnam_review_chronology_invalid")
    need(decision["schema"] == DECISION and decision["candidate_sha256"] == (candidate_sha256 or digest(packet))
         and decision["permitted_fields"] == ["source_identity", "canonical_official_url",
                                              "publisher_posted_date", "official_issuer"]
         and decision["original_language_and_source_version_checked"] is True
         and decision["production_release_authorized"] is True
         and decision["protected_custody_verified"] is True
         and all(type(decision[k]) is str and 5 <= len(decision[k].strip()) <= 1000
                 for k in ("reviewer", "rights_basis", "approval_reference", "custody_reference")),
         "vietnam_exact_version_or_rights_decision_missing")
    identities = decision["approved_source_identities"]
    known = {r["source_identity"]: r for r in packet["records"]}
    need(type(identities) is list and bool(identities)
         and all(type(i) is str for i in identities)
         and identities == sorted(set(identities)) and set(identities) <= set(known),
         "vietnam_approved_identity_selection_invalid")
    need(not packet["source_anomalies"], "vietnam_source_anomalies_unresolved")
    return [known[i] for i in identities]


def admit(conn, state_repo, commit, family, sealed, *, api, secret, as_of_utc):
    packet = prepare(state_repo, commit, family)
    rows = reviewed_rows(packet, sealed, secret=secret, as_of_utc=as_of_utc)
    authenticate(packet, api, datetime.strptime(as_of_utc, "%Y-%m-%dT%H:%M:%SZ").date())
    result = store_verified_links(conn, rows, digest(sealed),
                                  as_of_utc, stable_versions=True)
    return {"source_family": family, **result, "original_content_exported": False}


# Same private-runner MAC boundary already used by AFP/Kemhan. The public
# receiver never clones the private archive or reads original-bearing ledgers.
PRIVATE_REPO = "VSSpowerlifting/ipr-source-evidence-private"
PRIVATE_PREFIX = "/repos/" + PRIVATE_REPO
PRIVATE_WORKFLOW = ".github/workflows/vietnam_private_first_collector.yml"
PRIVATE_REF = "archive/vietnam-mps-foreign-affairs"
PRIVATE_SCHEMA = "ipr-vietnam-private-reviewed-metadata/1"
PRIVATE_DOMAIN = b"IPR-VIETNAM-PRIVATE-METADATA-v1\n"
ATTEMPT_SCHEMA = "ipr-vietnam-private-attempt/1"
ROW_FIELDS = frozenset({
    "source_family", "source_identity", "desk", "canonical_official_url",
    "publisher_posted_date", "official_issuer", "official_publisher",
    "official_republisher", "source_git_commit", "first_seen_run", "content_sha256",
    "capture_sha256", "version_first_seen_run", "collector_commit",
    "collection_target_source", "rss_instant_utc", "metadata_version_sha256",
})


def authenticate_private(packet, state_repo, public_frozen_tip, *, api, public_api):
    """Replay legacy versions, then authenticate every real private ledger attempt.

    The private workflow SHA and public collector code SHA are different objects.
    A source-specific private_attempts receipt binds both, the ledger and GitHub's
    attempt record. No public fallback is permitted for a post-cutover version.
    """
    from scripts.attest_vietnam_run_state import encoded_content, pinned_head, utc
    from core.shadow_schedule import scheduled_slot_date
    need(packet["source_family"] == MPS, "private_projection_is_mps_only")
    formal.verify_state_commit(Path(state_repo), public_frozen_tip, PRIVATE_REF)
    need(pinned_head(public_api, SOURCES[MPS].state_branch) == public_frozen_tip,
         "public_vietnam_writer_changed_after_cutover")
    # This history remains the authentic public history, never re-labelled private.
    with tempfile.TemporaryDirectory(prefix="ipr-vn-legacy-") as tmp:
        legacy_state = formal.export_state_tree(Path(state_repo), public_frozen_tip, Path(tmp) / "state")
        legacy = ministry.review(legacy_state, MPS)
    legacy_runs = {r["run_id"]: r for r in legacy["runs"]}
    legacy_versions = {(v["source_identity"], v["content_sha256"], v["first_seen_run"])
                       for v in legacy["versions"]}
    # Authenticate original legacy attempts against the public repository.
    checked = set()
    for row in packet["records"]:
        rid = row["version_first_seen_run"]
        if (row["source_identity"], row["content_sha256"], rid) not in legacy_versions:
            continue
        if rid in checked:
            continue
        checked.add(rid)
        m = RUN_ID.fullmatch(rid)
        need(m is not None, "legacy_attempt_identity_invalid")
        run = public_api.get(PREFIX + "/actions/runs/%s/attempts/%s" % m.groups())
        need(run.get("id") == int(m[1]) and run.get("run_attempt") == int(m[2])
             and run.get("path", "").split("@")[0] == ".github/workflows/vietnam_ministry_shadow.yml"
             and run.get("head_sha") == legacy_runs[rid]["collector_commit"]
             and run.get("event") == ("schedule" if legacy_runs[rid]["target_date_source"] == "schedule-slot"
                                      else "workflow_dispatch"), "legacy_collection_attempt_mismatch")
        require_persisted_attempt(public_api, run)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-private-") as tmp:
        state = formal.export_state_tree(Path(state_repo), packet["source_git_commit"], Path(tmp) / "state")
        evidence = ministry.review(state, MPS)
    private_runs = [r for r in evidence["runs"] if r["run_id"] not in legacy_runs]
    need(private_runs and private_runs[-1]["run_id"] == packet["latest_run"]
         and private_runs[-1]["health"] == "ok", "private_collection_not_yet_proven")
    subject = formal._git_bytes(["log", "-1", "--format=%s", packet["source_git_commit"]],
                                Path(state_repo)).decode().strip()
    need(subject == "private-vietnam: preserve " + MPS + " attempt " + packet["latest_run"],
         "private_latest_attempt_has_no_healthy_ledger")
    for ledger in private_runs:
        rid = ledger["run_id"]
        m = RUN_ID.fullmatch(rid)
        need(m is not None, "private_attempt_identity_invalid")
        receipt = encoded_content(api, "private_attempts/" + rid + ".json",
                                  packet["source_git_commit"], prefix=PRIVATE_PREFIX)
        run = api.get(PRIVATE_PREFIX + "/actions/runs/%s/attempts/%s" % m.groups())
        expected_event = "schedule" if ledger["target_date_source"] == "schedule-slot" else "workflow_dispatch"
        need(receipt.get("schema") == ATTEMPT_SCHEMA and receipt.get("source_family") == MPS
             and receipt.get("run_attempt") == rid
             and receipt.get("collector_commit") == ledger["collector_commit"]
             and receipt.get("state_sha256") == ledger["state_sha256_after"]
             and receipt.get("public_frozen_tip") == public_frozen_tip
             and receipt.get("health") == ledger["health"]
             and receipt.get("event") == expected_event
             and receipt.get("public_release_authorized") is False,
             "private_ledger_receipt_mismatch")
        need(run.get("id") == int(m[1]) and run.get("run_attempt") == int(m[2])
             and (run.get("repository") or {}).get("full_name") == PRIVATE_REPO
             and run.get("head_branch") == "main" and run.get("path", "").split("@")[0] == PRIVATE_WORKFLOW
             and run.get("head_sha") == receipt.get("workflow_commit")
             and run.get("event") == expected_event and run.get("status") == "completed"
             and run.get("conclusion") in ("success", "failure"), "private_collection_attempt_mismatch")
        need(utc(run.get("run_started_at")) <= utc(ledger["started_utc"])
             <= utc(ledger["finished_utc"]) <= utc(run.get("updated_at")),
             "private_collection_outside_authenticated_attempt")
        if expected_event == "schedule":
            need(scheduled_slot_date(utc(run["run_started_at"]), "18:17").isoformat() == ledger["target_date"],
                 "private_schedule_slot_mismatch")
        jobs = api.get(PRIVATE_PREFIX + "/actions/runs/%s/attempts/%s/jobs?per_page=100" % m.groups())
        need(type(jobs) is dict and jobs.get("total_count", 101) <= 100, "private_attempt_jobs_unbounded")
        steps = [s for j in jobs.get("jobs", []) for s in j.get("steps", [])
                 if s.get("name") == "Persist and independently verify private state"]
        need(len(steps) == 1 and steps[0].get("conclusion") == "success",
             "private_attempt_not_durably_persisted")
    for row in packet["records"]:
        need((row["source_identity"], row["content_sha256"], row["version_first_seen_run"]) in legacy_versions
             or row["version_first_seen_run"] in {r["run_id"] for r in private_runs},
             "source_version_has_no_authenticated_custody_attempt")
    head = api.get(PRIVATE_PREFIX + "/git/ref/heads/" + PRIVATE_REF)
    need(head.get("ref") == "refs/heads/" + PRIVATE_REF
         and head.get("object", {}).get("sha") == packet["source_git_commit"],
         "private_source_changed_concurrently")
    return {"private_attempts_verified": len(private_runs),
            "latest_run": packet["latest_run"], "source_git_commit": packet["source_git_commit"]}


def sign_private_projection(state_repo, commit, public_frozen_tip, sealed, *, api,
                            public_api, bridge_key, review_key, as_of_utc, validator_commit):
    """Private-only source replay, actual human decision, then metadata-only MAC."""
    import hmac
    import re
    need(len(bridge_key) >= 32 and bridge_key != review_key, "independent_private_bridge_key_required")
    need(re.fullmatch(r"[0-9a-f]{40}", validator_commit) is not None, "validator_commit_required")
    packet = prepare(state_repo, commit, MPS, private=True)
    rows = reviewed_rows(packet, sealed, secret=review_key, as_of_utc=as_of_utc)
    proof = authenticate_private(packet, state_repo, public_frozen_tip, api=api, public_api=public_api)
    projected = {**packet, "records": rows}
    envelope = {"schema": PRIVATE_SCHEMA, "source_repository": PRIVATE_REPO,
                "source_ref": PRIVATE_REF, "public_frozen_tip": public_frozen_tip,
                "validator_commit": validator_commit, "candidate_sha256": digest(packet),
                "packet": projected, "proof": proof}
    # Field allowlist precedes signing; never MAC an arbitrary original-bearing object.
    _projection_shape(envelope)
    return {"projection": envelope, "hmac_sha256": hmac.new(
        bridge_key, PRIVATE_DOMAIN + _canonical(envelope), hashlib.sha256).hexdigest()}


def _projection_shape(envelope):
    import re
    need(type(envelope) is dict and set(envelope) == {
        "schema", "source_repository", "source_ref", "public_frozen_tip",
        "validator_commit", "candidate_sha256", "packet", "proof"}
         and envelope["schema"] == PRIVATE_SCHEMA and envelope["source_repository"] == PRIVATE_REPO
         and envelope["source_ref"] == PRIVATE_REF, "private_projection_scope_invalid")
    packet = envelope["packet"]
    need(type(packet) is dict and set(packet) == {
        "schema", "source_family", "source_git_commit", "source_db_sha256", "latest_run",
        "logical_date", "records", "source_hold", "source_anomalies", "public_release_authorized"}
         and packet["schema"] == SCHEMA and packet["source_family"] == MPS
         and packet["public_release_authorized"] is False
         and packet["source_hold"] == "individual_review_required"
         and packet["source_anomalies"] == [], "private_packet_scope_invalid")
    for value in (envelope["candidate_sha256"], packet["source_db_sha256"]):
        need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             "private_projection_digest_invalid")
    need(type(packet["latest_run"]) is str and RUN_ID.fullmatch(packet["latest_run"]) is not None,
         "private_attempt_identity_invalid")
    need(type(packet["records"]) is list and 0 < len(packet["records"]) <= 1000,
         "private_projection_records_invalid")
    need(len({row.get("source_identity") for row in packet["records"] if type(row) is dict})
         == len(packet["records"]), "private_projection_duplicate_identity")
    need(type(envelope["proof"]) is dict and set(envelope["proof"]) == {
        "private_attempts_verified", "latest_run", "source_git_commit"}
         and type(envelope["proof"]["private_attempts_verified"]) is int
         and envelope["proof"]["private_attempts_verified"] > 0
         and envelope["proof"]["latest_run"] == packet["latest_run"]
         and envelope["proof"]["source_git_commit"] == packet["source_git_commit"],
         "private_projection_proof_invalid")
    for value in (envelope["public_frozen_tip"], envelope["validator_commit"], packet["source_git_commit"]):
        need(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
             "private_projection_commit_invalid")
    for row in packet["records"]:
        need(type(row) is dict and set(row) == ROW_FIELDS
             and row["source_family"] == MPS and row["desk"] == "vietnam"
             and row["official_issuer"] == row["official_publisher"] == "vn_mps"
             and row["official_republisher"] is None
             and row["source_git_commit"] == packet["source_git_commit"], "private_metadata_fields_invalid")
        exact_url(MPS, row["source_identity"], row["canonical_official_url"])
        need(type(row["collector_commit"]) is str and re.fullmatch(r"[0-9a-f]{40}", row["collector_commit"])
             and all(type(row[k]) is str and RUN_ID.fullmatch(row[k])
                     for k in ("first_seen_run", "version_first_seen_run"))
             and row["collection_target_source"] in ("schedule-slot", "explicit"),
             "private_metadata_attempt_invalid")
        from scripts.attest_vietnam_run_state import utc
        utc(row["rss_instant_utc"])
        need(date.fromisoformat(row["publisher_posted_date"]).isoformat() == row["publisher_posted_date"],
             "private_metadata_date_invalid")
        for key in ("content_sha256", "capture_sha256", "metadata_version_sha256"):
            need(type(row[key]) is str and re.fullmatch(r"[0-9a-f]{64}", row[key]) is not None,
                 "private_metadata_digest_invalid")
        need(row["metadata_version_sha256"] == digest({k: v for k, v in row.items()
             if k not in ("source_git_commit", "capture_sha256", "version_first_seen_run",
                          "collector_commit", "collection_target_source", "metadata_version_sha256")}),
             "private_metadata_version_mismatch")


def admit_private_projection(conn, signed, sealed, *, bridge_key, secret, api,
                             as_of_utc, public_checkout, private_api):
    """Public-only receiver: two independent seals, no private Git/body access."""
    import hmac
    import subprocess
    from scripts.attest_vietnam_run_state import pinned_head
    need(type(signed) is dict and set(signed) == {"projection", "hmac_sha256"}
         and len(bridge_key) >= 32 and bridge_key != secret, "independent_private_bridge_key_required")
    envelope = signed["projection"]
    need(type(signed["hmac_sha256"]) is str and hmac.compare_digest(signed["hmac_sha256"],
         hmac.new(bridge_key, PRIVATE_DOMAIN + _canonical(envelope), hashlib.sha256).hexdigest()),
         "private_projection_mac_invalid")
    _projection_shape(envelope)
    rows = reviewed_rows(envelope["packet"], sealed, secret=secret, as_of_utc=as_of_utc,
                         candidate_sha256=envelope["candidate_sha256"])
    need({r["source_identity"] for r in rows} ==
         {r["source_identity"] for r in envelope["packet"]["records"]}, "unapproved_metadata_in_projection")
    need(subprocess.run(["git", "-C", str(public_checkout), "merge-base", "--is-ancestor",
                         envelope["validator_commit"], "HEAD"], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL).returncode == 0, "private_validator_not_on_public_main")
    verify_private_projection_head(signed, private_api, public_api=api)
    result = store_verified_links(conn, rows, digest(sealed), as_of_utc, stable_versions=True)
    return {"source_family": MPS, **result, "original_content_exported": False}


def verify_private_projection_head(signed, private_api, *, public_api=None):
    """Metadata-only fresh ref/attempt readback; never request a private body."""
    envelope = signed["projection"]
    packet = envelope["packet"]
    head = private_api.get(PRIVATE_PREFIX + "/git/ref/heads/" + PRIVATE_REF)
    need(head.get("ref") == "refs/heads/" + PRIVATE_REF
         and head.get("object", {}).get("sha") == packet["source_git_commit"],
         "private_source_changed_concurrently")
    match = RUN_ID.fullmatch(packet["latest_run"])
    need(match is not None, "private_attempt_identity_invalid")
    run = private_api.get(PRIVATE_PREFIX + "/actions/runs/%s/attempts/%s" % match.groups())
    need(run.get("id") == int(match[1]) and run.get("run_attempt") == int(match[2])
         and (run.get("repository") or {}).get("full_name") == PRIVATE_REPO
         and run.get("head_branch") == "main" and run.get("event") in ("schedule", "workflow_dispatch")
         and run.get("path", "").split("@")[0] == PRIVATE_WORKFLOW
         and run.get("status") == "completed" and run.get("conclusion") in ("success", "failure"),
         "private_latest_attempt_unavailable")
    need(private_api.get(PRIVATE_PREFIX + "/git/ref/heads/" + PRIVATE_REF) == head,
         "private_source_changed_concurrently")
    if public_api is not None:
        from scripts.attest_vietnam_run_state import pinned_head
        need(pinned_head(public_api, SOURCES[MPS].state_branch) == envelope["public_frozen_tip"],
             "public_vietnam_writer_changed_after_cutover")
