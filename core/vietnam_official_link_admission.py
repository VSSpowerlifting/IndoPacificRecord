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


def prepare(state_repo, commit, family):
    """Local immutable Git replay; return metadata/hashes only, all held."""
    need(family in SOURCES, "unknown_vietnam_source_family")
    repo = formal.resolve_state_repo(state_repo)
    formal.verify_state_commit(repo, commit, SOURCES[family].state_branch)
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


def admit(conn, state_repo, commit, family, sealed, *, api, secret, as_of_utc):
    """Verify exact source/rights decision before the shared SQLite savepoint.

    A seal proves possession of the separate reviewer key, not legal consent.
    The owner must actually authorize this exact decision. There are no live
    decisions or provisioned publication keys supplied by this module.
    """
    packet = prepare(state_repo, commit, family)
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
    need(decision["schema"] == DECISION and decision["candidate_sha256"] == digest(packet)
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
    authenticate(packet, api, now.date())
    result = store_verified_links(conn, [known[i] for i in identities], digest(sealed),
                                  as_of_utc, stable_versions=True)
    return {"source_family": family, **result, "original_content_exported": False}
