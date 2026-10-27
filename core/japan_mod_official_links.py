"""Japan MOD news metadata gate, reusing the shared regional official-link store.

Reads immutable Git objects from the existing collector, never a working DB.
Original text is used only to rehash its preserved collection identity; no
publisher prose crosses the metadata boundary. Unretrieved rows never qualify.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from core.regional_official_link_release import digest, need, store_verified_links

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/japan_mod_official_link_policy.json"
FAMILY = "jp_mod_news_ja"
DATE_TYPE = "RSS pubDate (not independently verified document issue date)"
PERMITTED = ["source_identity", "canonical_official_url", "rss_date", "date_type",
             "official_issuer", "official_publisher"]
SOURCE_REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
SOURCE_REF = "shadow/jp-mod"
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
URL = re.compile(r"https://www\.mod\.go\.jp/j/press/news/(20[0-9]{2})/([01][0-9])/([0-3][0-9])[a-z]*\.pdf\Z")
RUN = re.compile(r"([1-9][0-9]*)(?:-([1-9][0-9]*))?\Z")
FEED = "https://www.mod.go.jp/j/rss/news.xml"


def load_policy():
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    need(policy.get("schema") == "ipr-japan-mod-official-link-policy/1"
         and policy.get("source_family") == FAMILY
         and policy.get("permitted_fields") == PERMITTED
         and policy.get("date_type") == DATE_TYPE
         and type(policy.get("standing_metadata_publication_authorized")) is bool,
         "japan_metadata_policy_invalid")
    return policy


def require_authorization():
    policy = load_policy()
    need(policy["standing_metadata_publication_authorized"] is True
         and type(policy.get("owner_decision_reference")) is str
         and policy["owner_decision_reference"].startswith("DECISION_LOG.md#")
         and len(policy["owner_decision_reference"]) > 25,
         "japan_standing_metadata_authorization_missing")
    return policy


def source_identity(url):
    m = URL.fullmatch(url) if type(url) is str else None
    need(m is not None, "japan_noncanonical_official_url")
    try:
        date(*map(int, m.groups()))
    except ValueError:
        need(False, "japan_invalid_url_date")
    return FAMILY + ":" + url.removeprefix("https://www.mod.go.jp")


def _git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)


def _blob(repo, commit, name):
    mode = _git(repo, "ls-tree", commit, "--", name).decode().split()
    need(len(mode) >= 3 and mode[:2] == ["100644", "blob"], "japan_source_object_not_regular")
    return _git(repo, "show", commit + ":" + name)


def _authenticate(entry, fetch_run, *, scheduled=False):
    m = RUN.fullmatch(entry.get("run_id", ""))
    need(m is not None, "japan_run_identity_invalid")
    run = fetch_run(m[1])
    need(type(run) is dict and str(run.get("id")) == m[1]
         and str(run.get("run_attempt")) == (m[2] or "1")
         and run.get("status") == "completed" and run.get("conclusion") == "success"
         and run.get("head_branch") == "main"
         and (run.get("repository") or {}).get("full_name") == SOURCE_REPOSITORY
         and run.get("path") == ".github/workflows/japan_shadow.yml"
         and run.get("event") in (("schedule",) if scheduled else ("schedule", "workflow_dispatch"))
         and run.get("head_sha") == entry.get("collector_commit"),
         "japan_collection_actions_not_authenticated")


def candidates(repo, commit, *, fetch_run):
    """Reconcile the pinned latest scheduled ledger, state hash and first runs.

    Dates retain the collector's exact RSS date; URL dates are never substituted.
    No pre-bootstrap or unretrieved rows are exported. Source snapshots may grow
    but cannot change an admitted identity or its date/attribution.
    """
    need(type(commit) is str and SHA.fullmatch(commit), "japan_source_commit_invalid")
    db_bytes = _blob(repo, commit, "state/shadow.db")
    paths = _git(repo, "ls-tree", "-r", "--name-only", commit, "--", "state/ledger").decode().splitlines()
    need(1 <= len(paths) <= 10000, "japan_ledger_history_missing")
    ledgers = {}
    for path in paths:
        need(re.fullmatch(r"state/ledger/[0-9]{8}T[0-9]{6}\+0000-[0-9]+(?:-[0-9]+)?\.json", path),
             "japan_ledger_path_invalid")
        entry = json.loads(_blob(repo, commit, path))
        need(entry.get("run_id") not in ledgers, "japan_duplicate_ledger_run")
        ledgers[entry["run_id"]] = entry
    latest = max(ledgers.values(), key=lambda e: e["finished_utc"])
    need(latest.get("state_sha256_after") == hashlib.sha256(db_bytes).hexdigest()
         and latest.get("target_date_source") == "schedule-slot"
         and latest.get("result") in ("ok", "ok_all_duplicates", "ok_no_publications")
         and latest.get("policy_failures") == [], "japan_latest_snapshot_unverified")
    _authenticate(latest, fetch_run, scheduled=True)
    news = [s for s in latest["sources"] if s["source_slug"] == FAMILY]
    need(len(news) == 1 and news[0].get("listing_status") == "ok"
         and news[0].get("failed_endpoints") == []
         and news[0].get("robots_status") == "allowed", "japan_news_listing_unverified")
    robots = news[0].get("robots_observation") or {}
    text = robots.get("text", "")
    need(robots.get("http_status") == 200
         and robots.get("url") == "https://www.mod.go.jp/robots.txt"
         and hashlib.sha256(text.encode()).hexdigest() == robots.get("payload_sha256"),
         "japan_policy_observation_unverified")
    import urllib.robotparser
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    need(parser.can_fetch("*", FEED), "japan_feed_policy_refused")
    with tempfile.TemporaryDirectory(prefix="ipr-japan-replay-") as tmp:
        path = Path(tmp) / "shadow.db"
        path.write_bytes(db_bytes)
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as con:
            need(con.execute("PRAGMA quick_check").fetchone() == ("ok",), "japan_source_sqlite_invalid")
            records = con.execute("SELECT url,source_slug,published_date,first_seen_run,"
                "content_sha256,capture_sha256,text_original FROM shadow_records "
                "WHERE source_slug=? ORDER BY url", (FAMILY,)).fetchall()
            held = {r[0] for r in con.execute("SELECT url FROM shadow_unretrieved WHERE reason='access_challenged'")}
    rows, seen = [], set()
    for url, slug, day, first, content_hash, capture_hash, original in records:
        if url in held:
            continue
        ident = source_identity(url)
        need(ident not in seen, "japan_duplicate_source_identity")
        seen.add(ident)
        need(type(day) is str and date.fromisoformat(day).isoformat() == day
             and day <= latest["finished_utc"][:10], "japan_rss_date_unverified")
        need(parser.can_fetch("*", url), "japan_original_policy_refused")
        need(type(capture_hash) is str and HASH.fullmatch(capture_hash)
             and hashlib.sha256(original.encode()).hexdigest() == content_hash,
             "japan_stored_content_identity_unverified")
        first_entry = ledgers.get(first)
        need(first_entry is not None and content_hash in first_entry.get("content_hashes", [])
             and first_entry.get("inserted", 0) > 0,
             "japan_first_seen_evidence_missing")
        _authenticate(first_entry, fetch_run)
        stable = dict(source_family=FAMILY, source_identity=ident, desk="japan",
            canonical_official_url=url, publisher_posted_date=day,
            official_issuer="jp_mod", official_publisher="jp_mod",
            official_republisher=None, first_seen_run=first)
        rows.append(dict(stable, source_git_commit=commit,
                         metadata_version_sha256=digest(stable)))
    return rows, {"source_commit": commit, "latest_run": latest["run_id"],
                  "state_sha256": latest["state_sha256_after"],
                  "eligible_links": len(rows), "date_type": DATE_TYPE}


def admit(conn, rows, evidence):
    policy = require_authorization()
    need(evidence.get("eligible_links") == len(rows)
         and SHA.fullmatch(evidence.get("source_commit", ""))
         and HASH.fullmatch(evidence.get("state_sha256", ""))
         and RUN.fullmatch(evidence.get("latest_run", ""))
         and evidence.get("date_type") == DATE_TYPE, "japan_candidate_evidence_invalid")
    seen = set()
    for row in rows:
        stable = {k: row[k] for k in ("source_family", "source_identity", "desk",
            "canonical_official_url", "publisher_posted_date", "official_issuer",
            "official_publisher", "official_republisher", "first_seen_run")}
        need(set(row) == set(stable) | {"source_git_commit", "metadata_version_sha256"}
             and row["source_family"] == FAMILY and row["desk"] == "japan"
             and row["source_identity"] == source_identity(row["canonical_official_url"])
             and row["official_issuer"] == row["official_publisher"] == "jp_mod"
             and row["official_republisher"] is None
             and row["source_git_commit"] == evidence["source_commit"]
             and row["metadata_version_sha256"] == digest(stable)
             and date.fromisoformat(row["publisher_posted_date"]).isoformat() == row["publisher_posted_date"]
             and RUN.fullmatch(row["first_seen_run"]), "japan_candidate_metadata_invalid")
        need(row["source_identity"] not in seen, "japan_duplicate_source_identity")
        seen.add(row["source_identity"])
    return store_verified_links(conn, rows, digest(dict(evidence, policy=policy)),
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), stable_versions=True)


def read_public_links(conn):
    records = conn.execute("SELECT source_identity,canonical_official_url,publisher_posted_date,"
        "official_issuer,official_publisher,official_republisher,source_git_commit,"
        "metadata_version_sha256,release_proof_sha256,release_scope "
        "FROM regional_official_source_links WHERE source_family=? AND desk='japan' "
        "ORDER BY publisher_posted_date DESC,source_identity", (FAMILY,)).fetchall()
    if records:
        require_authorization()
    result = []
    for ident, url, day, issuer, publisher, republisher, commit, version, proof, scope in records:
        need(ident == source_identity(url) and issuer == publisher == "jp_mod"
             and republisher is None and scope == "official_link_only"
             and SHA.fullmatch(commit) and HASH.fullmatch(version) and HASH.fullmatch(proof)
             and date.fromisoformat(day).isoformat() == day, "japan_public_metadata_invalid")
        result.append(dict(source_identity=ident, canonical_official_url=url,
            publisher_posted_date=day, date_kind=DATE_TYPE,
            label="Japan MOD official PDF · " + url.split("/news/", 1)[1],
            publisher_label="Japan Ministry of Defense"))
    return result
