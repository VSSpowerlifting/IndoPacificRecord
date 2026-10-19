"""Philippine NSC Official Statements: replay, hold and governed link admission.

NSC rows join the Philippines desk in the shared `regional_official_source_links`
index (migration 0014) beside AFP. Nothing here touches AFP's owner policy or
`admit()` in `core.regional_official_link_release`; only the shared atomic
`store_verified_links` is reused, after NSC-specific checks.

Order of decisions, each fail-closed:
  1. Replay: every candidate is re-derived from the preserved capture bytes in
     a Git commit of the private archive. Capture hash, permalink, post
     identity, posted date, content hash and the first-seen run's health must
     all agree. Nothing is read from a listing, a fixture or a model.
  2. Zero eligible records is a clean no-op: no write, no hold. The NSC
     category is often silent for weeks; silence is not a failure.
  3. Custody: rows come only from the private archive ref. The retired public
     shadow branch is public storage and is never a row source.
  4. Source-use: the observed category anomaly holds until the owner records
     it resolved in the policy file.
  5. Authorization: either a standing owner policy for neutral NSC link
     metadata, or an owner-sealed decision on this exact candidate version.
     Neither exists in this repository; both are owner acts.

What can be published, if authorized: source identity, canonical official URL,
publisher-posted date and the publisher code. Never the title, body, excerpt,
image, translation or a model summary. The packet never carries them either.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from core.collection import status as st
from core.collection.contract import CandidateReference, CaptureResult
from core.regional_official_link_release import (
    RegionalLinkHold, canonical, digest, need, store_verified_links)
from core.regional_reviewed_evidence import verify_review_seal
from scraper.sources.ph_nsc import PHNscAdapter, canonical_url, PERMALINK_RE

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "config" / "ph_nsc_official_link_policy.json"
MANIFEST = REPO_ROOT / "shadow" / "ph_nsc" / "manifest.json"

FAMILY = "ph_nsc_official_statements"
DESK = "philippines"
PUBLISHER = "ph_nsc"
PUBLIC_REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
PRIVATE_REPOSITORY = "VSSpowerlifting/ipr-source-evidence-private"
PUBLIC_REF = "shadow/ph-nsc"
PRIVATE_REF = "archive/ph-nsc"
PACKET = "ipr-ph-nsc-official-link-candidate/1"
POLICY = "ipr-ph-nsc-official-link-policy/1"
DECISION = "ipr-ph-nsc-official-link-decision/1"
DOMAIN = b"ipr-ph-nsc-official-link-decision/1\n"
PERMITTED_FIELDS = ["source_identity", "canonical_official_url",
                    "publisher_posted_date", "official_publisher"]

IDENTITY = re.compile(r"^nsc:[1-9][0-9]{0,9}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
LEDGER_NAME = re.compile(r"^ledger/\d{8}T\d{6}\+0000-[A-Za-z0-9_.-]{1,128}\.json$")
CAPTURE_NAME = re.compile(r"^captures/[0-9a-f]{64}\.bin$")
STATE_FILES = ("clock.json", "shadow.db")
SHADOW_COLUMNS = (
    "url", "source_identity", "source_slug", "title_original", "text_original",
    "published_date", "published_at_original", "published_at_utc", "language_tag",
    "site_byline", "site_byline_url", "publication_kind", "content_sha256",
    "capture_sha256", "requested_url", "final_url", "http_status", "retrieved_at",
    "first_seen_run")
POLICY_KEYS = {
    "schema", "source_family", "standing_metadata_publication_authorized",
    "owner_decision_reference", "category_anomaly_resolved",
    "category_anomaly_reference", "permitted_fields", "notes"}


class NscHold(RegionalLinkHold):
    """Fixed diagnostic; never echoes publisher-controlled text."""


def _hold(ok, reason):
    if not ok:
        raise NscHold(reason)


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True).stdout


def load_policy(path=POLICY_PATH):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    _hold(type(policy) is dict and set(policy) == POLICY_KEYS
          and policy["schema"] == POLICY and policy["source_family"] == FAMILY
          and type(policy["standing_metadata_publication_authorized"]) is bool
          and type(policy["category_anomaly_resolved"]) is bool
          and policy["permitted_fields"] == PERMITTED_FIELDS,
          "nsc_policy_invalid")
    for flag, ref in (("standing_metadata_publication_authorized", "owner_decision_reference"),
                      ("category_anomaly_resolved", "category_anomaly_reference")):
        # A true flag without a named owner act is not an owner decision.
        _hold(not policy[flag] or (type(policy[ref]) is str and len(policy[ref].strip()) >= 10),
              "nsc_policy_invalid")
    return policy


def load_source():
    from types import SimpleNamespace
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    source = manifest["sources"][0]
    _hold(source["slug"] == FAMILY, "nsc_manifest_invalid")
    return SimpleNamespace(**source)


def export_state(state_repo, commit, dest):
    """`state/` of one commit, from Git objects only; regular files only."""
    _hold(bool(SHA40.match(commit or "")), "nsc_state_commit_invalid")
    listing = _git(["ls-tree", "-r", "-z", "--full-tree", "--long",
                    "%s:state" % commit], state_repo)
    names = []
    for raw in listing.split(b"\0"):
        if not raw:
            continue
        meta, _, name = raw.partition(b"\t")
        mode, kind, oid, _size = meta.decode("ascii").split(None, 3)
        name = name.decode("utf-8")
        _hold(kind == "blob" and mode == "100644", "nsc_state_tree_not_regular")
        _hold(name in STATE_FILES or bool(LEDGER_NAME.match(name))
              or bool(CAPTURE_NAME.match(name)), "nsc_state_tree_unexpected_file")
        out = Path(dest) / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_git(["cat-file", "blob", oid], state_repo))
        names.append(name)
    _hold(all(f in names for f in STATE_FILES)
          and any(LEDGER_NAME.match(n) for n in names), "nsc_state_tree_incomplete")
    return Path(dest)


def _ledgers(state_dir):
    runs = {}
    for path in sorted((state_dir / "ledger").glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        _hold(type(entry) is dict and type(entry.get("run_id")) is str
              and path.name.endswith("-" + entry["run_id"] + ".json")
              and entry["run_id"] not in runs, "nsc_ledger_invalid")
        runs[entry["run_id"]] = entry
    return runs


def _version(row, content_sha256):
    # Excludes the Git commit, run and retrieval time, so the same official
    # statement replayed from a later private commit is `unchanged`. A changed
    # body, URL, date or identity changes the version and is refused upstream.
    return digest({k: row[k] for k in (
        "source_family", "source_identity", "desk", "canonical_official_url",
        "publisher_posted_date", "official_issuer", "official_publisher",
        "official_republisher")} | {"content_sha256": content_sha256})


def replay_state(state_dir, source_commit, source_ref):
    """Metadata-only candidate packet, re-derived from preserved capture bytes."""
    state_dir = Path(state_dir)
    runs = _ledgers(state_dir)
    db = sqlite3.connect("file://%s?mode=ro&immutable=1" % (state_dir / "shadow.db").resolve(),
                         uri=True)
    try:
        cols = tuple(r[1] for r in db.execute("PRAGMA table_info(shadow_records)"))
        _hold(cols == SHADOW_COLUMNS, "nsc_shadow_schema_unexpected")
        rows = db.execute("SELECT %s FROM shadow_records ORDER BY source_identity"
                          % ",".join(SHADOW_COLUMNS)).fetchall()
    finally:
        db.close()
    adapter = PHNscAdapter(load_source())
    records, links = [], []
    for values in rows:
        r = dict(zip(SHADOW_COLUMNS, values))
        url = r["url"]
        _hold(canonical_url(url) == url == r["requested_url"] == r["final_url"]
              and r["http_status"] == 200 and r["source_slug"] == FAMILY,
              "nsc_capture_provenance_mismatch")
        _hold(bool(IDENTITY.match(r["source_identity"])), "nsc_identity_invalid")
        _hold(bool(SHA256.match(r["capture_sha256"])), "nsc_capture_missing")
        path = state_dir / "captures" / (r["capture_sha256"] + ".bin")
        _hold(path.is_file(), "nsc_capture_missing")
        payload = path.read_bytes()
        _hold(hashlib.sha256(payload).hexdigest() == r["capture_sha256"],
              "nsc_capture_hash_mismatch")
        try:
            body = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise NscHold("nsc_capture_not_utf8")
        ref = CandidateReference(url, FAMILY)
        result = adapter.extract(CaptureResult(
            ref, st.OK, url, final_url=url, http_status=200,
            payload_bytes=len(payload), payload_sha256=r["capture_sha256"],
            retrieved_at=r["retrieved_at"], body=body))
        _hold(result.status == st.OK and len(result.documents) == 1,
              "nsc_capture_replay_refused")
        doc = result.documents[0]
        x = doc.extra
        _hold(x["source_identity"] == r["source_identity"], "nsc_identity_changed")
        _hold(x["content_sha256"] == r["content_sha256"], "nsc_content_changed")
        permalink = "-".join(PERMALINK_RE.match(url[len("https://nsc.gov.ph"):]).groups()[:3])
        _hold(doc.published_date == r["published_date"] == permalink
              and x["published_at_utc"] == r["published_at_utc"],
              "nsc_date_discrepancy")
        run = runs.get(r["first_seen_run"])
        _hold(run is not None and run.get("health") == "ok"
              and st.is_success(run.get("result") or ""), "nsc_first_seen_run_unhealthy")
        link = {
            "source_family": FAMILY, "source_identity": r["source_identity"],
            "desk": DESK, "canonical_official_url": url,
            "publisher_posted_date": r["published_date"], "official_issuer": None,
            "official_publisher": PUBLISHER, "official_republisher": None,
            "source_git_commit": source_commit, "first_seen_run": r["first_seen_run"],
        }
        link["metadata_version_sha256"] = _version(link, r["content_sha256"])
        links.append(link)
        records.append({
            "source_identity": r["source_identity"], "canonical_official_url": url,
            "publisher_posted_date": r["published_date"],
            "capture_sha256": r["capture_sha256"], "content_sha256": r["content_sha256"],
            "first_seen_run": r["first_seen_run"],
        })
    return {
        "schema": PACKET, "source_family": FAMILY, "desk": DESK,
        "source_ref": source_ref, "source_git_commit": source_commit,
        "records": records, "links": links,
        "public_release_authorized": False, "original_content_exported": False,
    }


def prepare(state_repo, commit, source_ref):
    """Export `state/` at `commit` and replay it. Writes nothing it keeps."""
    tmp = Path(tempfile.mkdtemp(prefix="nsc-replay-"))
    try:
        return replay_state(export_state(state_repo, commit, tmp / "state"), commit, source_ref)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _sealed_selection(packet, sealed, secret, as_of_utc):
    _hold(type(sealed) is dict and set(sealed) == {"review", "hmac_sha256"},
          "nsc_metadata_publication_not_authorized")
    decision = sealed["review"]
    _hold(type(decision) is dict and set(decision) == {
        "schema", "candidate_sha256", "approved_source_identities", "reviewer",
        "reviewed_on", "rights_basis", "approval_reference", "permitted_fields",
        "production_release_authorized", "protected_custody_verified", "custody_reference",
    }, "nsc_release_decision_scope_invalid")
    verify_review_seal(sealed, secret, domain=DOMAIN)
    now = datetime.strptime(as_of_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    _hold(type(decision["reviewed_on"]) is str, "nsc_review_chronology_invalid")
    reviewed = date.fromisoformat(decision["reviewed_on"])
    _hold(reviewed.isoformat() == decision["reviewed_on"] and reviewed <= now.date(),
          "nsc_review_chronology_invalid")
    _hold(decision["schema"] == DECISION
          and decision["candidate_sha256"] == candidate_digest(packet)
          and decision["permitted_fields"] == PERMITTED_FIELDS
          and decision["production_release_authorized"] is True
          and decision["protected_custody_verified"] is True
          and all(type(decision[k]) is str and 5 <= len(decision[k].strip()) <= 1000
                  for k in ("reviewer", "rights_basis", "approval_reference",
                            "custody_reference")),
          "nsc_exact_version_or_rights_decision_missing")
    ids = decision["approved_source_identities"]
    _hold(type(ids) is list and bool(ids) and all(type(i) is str for i in ids)
          and ids == sorted(set(ids))
          and set(ids) <= {r["source_identity"] for r in packet["records"]},
          "nsc_approved_identity_selection_invalid")
    return set(ids), digest(sealed)


def candidate_digest(packet):
    return digest({k: packet[k] for k in (
        "schema", "source_family", "source_ref", "source_git_commit", "records")})


def admit(conn, packet, *, policy, as_of_utc, sealed=None, secret=None):
    """Store authorized NSC link rows, or hold with a fixed reason.

    Returns a dict on success or a clean no-op. Raises NscHold (a ValueError)
    for every refusal; nothing has been written when it does.
    """
    _hold(packet.get("schema") == PACKET and packet.get("source_family") == FAMILY,
          "nsc_packet_invalid")
    if not packet["links"]:
        return {"source_family": FAMILY, "status": "no_eligible_records",
                "new_official_links": 0, "unchanged_official_links": 0,
                "original_content_exported": False}
    _hold(packet["source_ref"] == PRIVATE_REF, "nsc_rows_not_from_private_custody")
    _hold(policy["category_anomaly_resolved"] is True, "nsc_category_anomaly_unresolved")
    if policy["standing_metadata_publication_authorized"] is True:
        approved = {l["source_identity"] for l in packet["links"]}
        proof = digest({"policy": policy, "candidate": candidate_digest(packet)})
    else:
        _hold(sealed is not None, "nsc_metadata_publication_not_authorized")
        approved, proof = _sealed_selection(packet, sealed, secret, as_of_utc)
    rows = [l for l in packet["links"] if l["source_identity"] in approved]
    result = store_verified_links(conn, rows, proof, as_of_utc, stable_versions=True)
    return {"source_family": FAMILY, "status": "admitted", **result,
            "original_content_exported": False}


def unrelated_digest(conn):
    """Every index row EXCEPT NSC's: AFP, Kemhan, Vietnam must not move."""
    rows = conn.execute(
        "SELECT * FROM regional_official_source_links WHERE source_family != ? "
        "ORDER BY source_family, source_identity", (FAMILY,)).fetchall()
    return hashlib.sha256(canonical([list(r) for r in rows])).hexdigest()
