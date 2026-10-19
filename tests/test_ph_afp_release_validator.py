"""Real Git/SQLite synthetic tests for the AFP trusted release validator.

No network: GitHub run records come from a fake fetcher. Every case builds an
actual AFP-layout source history like ``scripts/shadow_collect_ph.py`` and the
private first collector write: the collector's own SQLite schema with captures
in the database, content-addressed payloads under ``state/evidence/payloads``,
per-run request evidence bound to its ledger digest, root ``private_attempts``
receipts and the exact commit subjects.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core import ph_afp_release_validator as v
from core import regional_official_link_release as release
from scripts import admit_ph_afp_official_links as cli
from scripts.shadow_collect_ph import SCHEMA

SECRET = "PRIVATE AFP BODY must never leave the source history"
TITLE = "Original AFP headline text"
KEY = b"k" * 32
FIRST = 37631681338
PINNED_POLICY_LOADER = release.load_owner_policy  # the real, unpatched loader


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


def healthy_ledger(run_id, day, source, healthy, evidence):
    return {"desk": "ph-afp", "run_id": run_id, "target_date": day,
            "target_date_source": source,
            "result": "ok" if healthy else "partial",
            "health": "ok" if healthy else "degraded",
            "listing_status": "ok", "robots_status": "allowed",
            "aborted": None if healthy else "consecutive_failures",
            "rehearsal": False, "fetch_failures": 0 if healthy else 5,
            "extraction_failures": 0, "access_failures": 0,
            "redirect_refusals": 0, "identity_collisions": 0,
            "request_evidence": evidence}


class History:
    """Append-only synthetic AFP source history in the collector's layout."""

    def __init__(self, folder):
        self.folder = folder
        folder.mkdir()
        git(folder, "init", "-q")
        git(folder, "config", "user.name", "Offline QA")
        git(folder, "config", "user.email", "offline@example.invalid")
        self.records, self.captures, self.pending = [], [], []
        (folder / "state" / "evidence" / "payloads").mkdir(parents=True)
        (folder / "state" / "ledger").mkdir()
        (folder / "state" / "clock.json").write_text(json.dumps({
            "day_zero_utc": v.DAY_ZERO_UTC, "day_zero_run_id": v.DAY_ZERO_RUN}))

    def add_record(self, number, slug, day, first_seen, text=SECRET):
        sid = "afp:%d" % number
        payload = json.dumps({"id": number, "slug": slug, "date": day}).encode()
        sha = hashlib.sha256(payload).hexdigest()
        (self.folder / "state" / "evidence" / "payloads" / (sha + ".bin")).write_bytes(payload)
        self.captures.append([sid, first_seen, "https://www.afp.mil.ph/api/x", None, 200,
                              "application/json", day + "T06:40:00+00:00", "f" * 64, sha,
                              payload])
        self.pending.append(sha)
        self.records.append({
            "url": "https://www.afp.mil.ph/news/" + slug, "source_identity": sid,
            "source_slug": "ph_afp_articles", "title_original": TITLE, "text_original": text,
            "text_status": "ok" if text else "no_text", "text_composition": "intro_body",
            "published_date": day, "published_at_utc": day + "T02:00:00+00:00",
            "published_at_original": day + "T10:00:00+08:00", "byline": None,
            "category_slug": "news-blog", "api_created_at": None, "api_updated_at": None,
            "featured_image_path": None, "language_tag": "en",
            "publication_kind": "institutional_news",
            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "source_fingerprint": "f" * 64, "capture_sha256": sha,
            "retrieved_at": day + "T06:40:00+00:00", "first_seen_run": first_seen})

    def _write_db(self):
        db = self.folder / "state" / "shadow.db"
        if db.exists():
            db.unlink()
        with sqlite3.connect(db) as cx:
            cx.executescript(SCHEMA)
            for r in self.records:
                cx.execute("INSERT INTO shadow_records (%s) VALUES (%s)" % (
                    ",".join(r), ",".join("?" * len(r))), list(r.values()))
            cx.executemany(
                "INSERT INTO captures (source_identity, run_id, requested_url, final_url,"
                " http_status, content_type, retrieved_at, source_fingerprint,"
                " payload_sha256, payload) VALUES (?,?,?,?,?,?,?,?,?,?)", self.captures)
        cx.close()

    def attempt(self, run_id, day, *, source="schedule-slot", kind="shadow",
                ledger=True, healthy=True, subject=None, new=(), evidence_sha=None):
        for number, slug, pday in new:
            self.add_record(number, slug, pday, run_id)
        self._write_db()
        if ledger:
            requests = [{"requested_url": "https://www.afp.mil.ph/api/x", "http_status": 200,
                         "payload_retained": True, "payload_sha256": sha}
                        for sha in self.pending] or [
                {"requested_url": "https://www.afp.mil.ph/robots.txt", "http_status": 200,
                 "payload_retained": False, "payload_sha256": None}]
            raw = json.dumps(requests).encode()
            (self.folder / "state" / "evidence" / (run_id + ".json")).write_bytes(raw)
            evidence = {"path": "evidence/%s.json" % run_id, "requests": len(requests),
                        "sha256": evidence_sha or hashlib.sha256(raw).hexdigest()}
            (self.folder / "state" / "ledger" / ("%sT064000+0000-%s.json" % (
                day.replace("-", ""), run_id))).write_text(
                json.dumps(healthy_ledger(run_id, day, source, healthy, evidence)))
        self.pending = []
        if kind == "private":
            receipts = self.folder / "private_attempts"
            receipts.mkdir(exist_ok=True)
            (receipts / (run_id + ".json")).write_text(json.dumps({
                "schema": v.ATTEMPT_SCHEMA, "run_attempt": run_id,
                "collector_exit_status": 0 if healthy else 1,
                "public_release_approved": False, "original_body_reuse_approved": False}))
        if subject is None:
            subject = ("private-ph-afp: preserve attempt %s" % run_id if kind == "private"
                       else "shadow(ph-afp): run %s" % run_id)
        git(self.folder, "add", "-A", ".")
        git(self.folder, "commit", "-qm", subject)
        return git(self.folder, "rev-parse", "HEAD")


def scheduled_runs(*numbers, event="schedule", repo=v.PUBLIC_REPOSITORY,
                   path=".github/workflows/ph_afp_shadow.yml", private=()):
    runs = {str(n): {"id": n, "run_attempt": 1, "event": event, "head_branch": "main",
                     "path": path, "repository": {"full_name": repo}} for n in numbers}
    for n in private:
        runs[str(n)] = {"id": n, "run_attempt": 1, "event": "schedule", "head_branch": "main",
                        "path": ".github/workflows/afp_private_first_collector.yml",
                        "repository": {"full_name": v.PRIVATE_REPOSITORY}}
    return lambda number: runs.get(number)


def policy_for(packet):
    policy = copy.deepcopy(release.load_owner_policy())
    # Most synthetic tests exercise the pre-authorization fallback explicitly.
    # Keep that fixture narrow even after the real AFP standing ruling lands.
    policy["standing_link_metadata_authorizations"] = [
        a for a in policy["standing_link_metadata_authorizations"]
        if a["source_family"] != v.FAMILY]
    spec = next(s for s in policy["source_families"] if s["source_family"] == v.FAMILY)
    spec.update(frozen_review_cohort_commit=packet["source_git_commit"],
                frozen_review_cohort_candidate_count=packet["candidate_count"],
                frozen_review_cohort_metadata_manifest_sha256=packet["metadata_manifest_sha256"])
    return policy


def production_db(path):
    with sqlite3.connect(path) as cx:
        cx.execute(release.SCHEMA_SQL)
        cx.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT)")
        cx.execute("INSERT INTO articles (url) VALUES ('https://example.invalid/unrelated')")
        cx.execute("INSERT INTO regional_official_source_links VALUES "
                   "('id_kemhan_news','kemhan:/2026/10/01/x.html','indonesia',"
                   "'https://www.kemhan.go.id/2026/10/01/x.html','2026-10-01',NULL,"
                   "'Kementerian Pertahanan Republik Indonesia',NULL,?,?,'1-1',"
                   "'official_link_only',?,'2026-10-15T00:00:00Z')",
                   ("b" * 40, "c" * 64, "d" * 64))
    cx.close()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class AfpReleaseValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-afp-validator-test-")
        root = Path(self.tmp.name)
        self.h = History(root / "source")
        self.runs = []
        for i in range(5):
            n = FIRST + i
            day = "2026-10-%02d" % (7 + i)
            self.runs.append(n)
            new = [(1380 + 2 * i, "afp-news-day-%d" % i, day)]
            if i == 2:  # an image-only article: empty text, still hash-bound
                new.append((1381 + 2 * i, "afp-photo-release-%d" % i, day))
            self.pin = self.h.attempt("%d-1" % n, day, new=[x[:3] for x in new])
            if i == 2:
                self.h.records[-1]["text_original"] = ""
                self.h.records[-1]["text_status"] = "no_text"
                self.h.records[-1]["content_sha256"] = hashlib.sha256(b"").hexdigest()
                self.pin = self.h.attempt("%d-2" % n, day, source="manual-utc-date")
        self.baseline = v.candidate_packet(self.h.folder, self.pin)
        self.policy = policy_for(self.baseline)
        self.patches = [patch.object(v, "FROZEN_PIN", self.pin),
                        patch.object(v, "load_owner_policy", lambda: self.policy),
                        patch.object(release, "load_owner_policy", lambda: self.policy)]
        for p in self.patches:
            p.start()
        self.fetch = scheduled_runs(*self.runs, 39124069601)
        self.ref = "e" * 40
        self.db = root / "pla_watch.db"
        production_db(self.db)
        self.root = root

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def validate(self, commit, fetch=None):
        return v.validate_source_checkout(self.h.folder, commit,
                                          fetch_run=fetch or self.fetch, validator_ref=self.ref)

    def rows(self):
        with sqlite3.connect(self.db.as_uri() + "?mode=ro", uri=True) as cx:
            return {r[0]: r[1:] for r in cx.execute(
                "SELECT source_identity, canonical_official_url, publisher_posted_date, "
                "source_git_commit FROM regional_official_source_links WHERE desk='philippines'")}

    def assertHold(self, reason, fn, *a, **kw):
        with self.assertRaises(release.RegionalLinkHold) as caught:
            fn(*a, **kw)
        self.assertEqual(str(caught.exception), reason)

    # --- happy path, rolling cohort, replay --------------------------------

    def test_reviewed_frozen_cohort_admits_once_and_new_record_stays_held(self):
        self.assertEqual(self.baseline["candidate_count"], 6)
        tip = self.h.attempt("39124069601-1", "2026-10-18", new=[
            (1409, "afp-chief-visits-command", "2026-10-14")])
        out = self.validate(tip)
        self.assertEqual(out["receipt"]["authenticated_scheduled_days"],
                         ["2026-10-%02d" % d for d in range(7, 12)] + ["2026-10-18"])
        self.assertEqual((len(out["eligible"]), len(out["approved"])), (7, 6))
        self.assertEqual(out["receipt"]["held_unreviewed_count"], 1)
        self.assertEqual(out["receipt"]["evidence"]["stored_originals"], 7)
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T21:13:00Z")
        self.assertEqual((receipts[0]["new_official_links"], total), (6, 6))
        self.assertEqual(receipts[0]["held_pending_individual_approval"], 1)
        self.assertNotIn("afp:1409", self.rows())
        self.assertIn("afp:1385", self.rows(), "image-only record is an official link too")
        self.assertEqual(self.rows()["afp:1380"][:2],
                         ("https://www.afp.mil.ph/news/afp-news-day-0", "2026-10-07"))
        before = sha(self.db)
        receipts, _ = cli.admit_validated(self.db, [self.validate(tip)],
                                          as_of_utc="2026-10-19T21:13:00Z")
        self.assertEqual((receipts[0]["new_official_links"],
                          receipts[0]["unchanged_official_links"]), (0, 6))
        self.assertEqual(sha(self.db), before, "replay must not rewrite the database")
        with sqlite3.connect(self.db) as cx:
            self.assertEqual(cx.execute("SELECT count(*) FROM regional_official_source_links "
                                        "WHERE desk='indonesia'").fetchone(), (1,))

    def test_later_collection_keeps_original_admitted_version(self):
        first = self.h.attempt("39124069601-1", "2026-10-18")
        cli.admit_validated(self.db, [self.validate(first)], as_of_utc="2026-10-18T21:13:00Z")
        later = self.h.attempt("39200000000-1", "2026-10-19", kind="private",
                               source="manual-utc-date")
        receipts, _ = cli.admit_validated(self.db, [self.validate(later)],
                                          as_of_utc="2026-10-19T21:13:00Z")
        self.assertEqual(receipts[0]["new_official_links"], 0)
        self.assertEqual({r[2] for r in self.rows().values()}, {first})

    # --- authentication failures -----------------------------------------

    def test_ledger_schedule_claim_must_match_github_record(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        lying = scheduled_runs(*self.runs, 39124069601, event="workflow_dispatch")
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, lying)
        foreign = scheduled_runs(*self.runs, 39124069601, path=".github/workflows/other.yml")
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, foreign)

    def test_elapsed_days_are_measured_not_required(self):
        out = self.validate(self.pin, scheduled_runs(self.runs[0]))
        self.assertEqual(out["receipt"]["authenticated_scheduled_days"], ["2026-10-07"])
        self.assertEqual(out["receipt"]["scheduled_claims_not_visible"], 4)
        receipts, _ = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T21:13:00Z")
        self.assertEqual(receipts[0]["new_official_links"], 6)

    def test_no_authenticated_healthy_scheduled_run_holds(self):
        self.assertHold("scheduled_history_not_authenticated", self.validate, self.pin,
                        scheduled_runs())

    def test_tampered_payload_or_capture_holds(self):
        payload = next((self.h.folder / "state" / "evidence" / "payloads").glob("*.bin"))
        payload.write_bytes(b"altered after capture")
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("preserved_capture_digest_mismatch", self.validate, tip)

    def test_tampered_capture_blob_in_database_holds(self):
        self.h.captures[0][9] = b"altered capture blob"
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("preserved_capture_digest_mismatch", self.validate, tip)

    def test_stored_original_without_preserved_capture_holds(self):
        self.h.add_record(1410, "afp-without-capture", "2026-10-18", "39124069601-1")
        self.h.captures.pop()
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("stored_original_not_bound_to_preserved_capture", self.validate, tip)

    def test_altered_stored_original_text_holds(self):
        self.h.records[0]["text_original"] = SECRET + " (edited later)"
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("stored_original_not_bound_to_preserved_capture", self.validate, tip)

    def test_request_evidence_must_match_its_ledger_digest(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", evidence_sha="0" * 64)
        self.assertHold("request_evidence_digest_mismatch", self.validate, tip)

    def test_unexplained_history_commit_holds(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", subject="manual edit of state")
        self.assertHold("unrecognized_source_history_commit", self.validate, tip)

    def test_shadow_commit_without_ledger_holds(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", ledger=False, new=[
            (1410, "afp-without-ledger", "2026-10-18")])
        self.assertHold("attempt_ledger_and_source_history_disagree", self.validate, tip)

    def test_private_attempt_without_ledger_is_visible_failure_not_success(self):
        tip = self.h.attempt("39200000000-1", "2026-10-19", kind="private",
                             ledger=False, healthy=False)
        evidence = self.validate(tip)["receipt"]["evidence"]
        self.assertEqual((evidence["private_attempts_without_ledger"],
                          evidence["private_attempts_nonzero_exit"]), (1, 1))

    def test_unhealthy_scheduled_attempt_does_not_count_as_a_day(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", healthy=False)
        out = self.validate(tip)
        self.assertNotIn("2026-10-18", out["receipt"]["authenticated_scheduled_days"])
        self.assertEqual(out["receipt"]["evidence"]["unhealthy_attempts"], 1)
        self.assertEqual(out["receipt"]["authenticated_failed_scheduled_attempts"], 1)

    def test_failed_attempt_cannot_be_relabelled_as_scheduled(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", healthy=False)
        runs = scheduled_runs(*self.runs)
        lying = lambda n: (dict(id=39124069601, run_attempt=1, event="workflow_dispatch",
                                head_branch="main", repository={"full_name": v.PUBLIC_REPOSITORY},
                                path=".github/workflows/ph_afp_shadow.yml")
                           if n == "39124069601" else runs(n))
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, lying)

    def test_wrong_day_zero_clock_holds(self):
        (self.h.folder / "state" / "clock.json").write_text(json.dumps({
            "day_zero_utc": "2026-10-01T00:00:00+00:00", "day_zero_run_id": v.DAY_ZERO_RUN}))
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("source_day_zero_clock_mismatch", self.validate, tip)

    # --- review basis -----------------------------------------------------

    def test_receipt_states_the_actual_review_basis(self):
        receipt = self.validate(self.h.attempt("39124069601-1", "2026-10-18"))["receipt"]
        self.assertIs(receipt["owner_review_declaration_bound_to_frozen_manifest"], True)
        self.assertIs(receipt["record_specific_review_receipts_verified"], False)
        self.assertEqual(receipt["review_basis"], v.REVIEW_BASIS)
        self.assertIs(receipt["standing_link_metadata_authorization_verified"], False)
        self.assertEqual(receipt["released_without_record_specific_review_count"], 0)
        claiming = dict(receipt, record_specific_review_receipts_verified=True)
        out = self.validate(self.h.attempt("39124069602-1", "2026-10-19"))
        self.assertHold("independent_release_evidence_missing", release.verify_release_evidence,
                        claiming, out["packet"], out["eligible"])

    # --- AFP future metadata authorized; old non-standing fallback retained --

    def test_pinned_owner_policy_grants_afp_standing_authorization(self):
        pinned = PINNED_POLICY_LOADER()
        self.assertIs(release.standing_link_metadata_authorization(pinned, v.FAMILY), True)
        self.assertIs(release.standing_link_metadata_authorization(pinned, "id_kemhan_news"),
                      True)
        self.assertEqual({a["source_family"] for a in
                          pinned["standing_link_metadata_authorizations"]},
                         {v.FAMILY, "id_kemhan_news"})

    def test_pinned_owner_authorization_is_accepted_by_real_loader(self):
        # The owner-authorized AFP entry is now in the pinned policy.
        # Changing the precise permission shape still fails closed.
        policy = json.loads(release.POLICY_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with patch.object(release, "POLICY_PATH", path):
                loaded = PINNED_POLICY_LOADER(path=path)
                self.assertIs(release.standing_link_metadata_authorization(
                    loaded, v.FAMILY), True)
                loaded["standing_link_metadata_authorizations"][-1][
                    "per_record_human_review_required"] = True
                path.write_text(json.dumps(loaded), encoding="utf-8")
                with self.assertRaises(release.RegionalLinkHold):
                    PINNED_POLICY_LOADER(path=path)

    def _afp_standing(self):
        # Restore the owner's real pinned AFP entry that policy_for() strips.
        self.policy["standing_link_metadata_authorizations"] = [
            a for a in PINNED_POLICY_LOADER()["standing_link_metadata_authorizations"]
            if a["source_family"] == v.FAMILY]
        self.assertEqual(len(self.policy["standing_link_metadata_authorizations"]), 1)

    def test_pinned_afp_standing_entry_admits_future_records_without_claiming_review(self):
        self._afp_standing()
        tip = self.h.attempt("39124069601-1", "2026-10-18", new=[
            (1409, "afp-chief-visits-command", "2026-10-14")])
        out = self.validate(tip)
        r = out["receipt"]
        self.assertEqual((len(out["eligible"]), len(out["approved"])), (7, 7))
        self.assertIs(r["standing_link_metadata_authorization_verified"], True)
        self.assertIs(r["record_specific_review_receipts_verified"], False)
        self.assertEqual((r["held_unreviewed_count"],
                          r["released_without_record_specific_review_count"]), (0, 1))
        self.assertEqual(r["review_basis"], v.STANDING_REVIEW_BASIS)
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T21:13:00Z")
        self.assertEqual((receipts[0]["new_official_links"], total), (7, 7))
        self.assertIn("afp:1409", self.rows())
        # A released post-pin record that later changes is an anomaly: hold all.
        self.h.records[-1]["published_date"] = "2026-10-13"
        changed = self.validate(self.h.attempt("39124069602-1", "2026-10-19"))
        before = sha(self.db)
        self.assertHold("previously_released_source_missing_or_changed",
                        cli.admit_validated, self.db, [changed],
                        as_of_utc="2026-10-19T21:13:00Z")
        self.assertEqual(sha(self.db), before)

    def test_standing_flag_without_policy_entry_cannot_widen_release(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", new=[
            (1410, "afp-not-yet-reviewed", "2026-10-18")])
        out = self.validate(tip)
        ids = sorted(r["source_identity"] for r in out["eligible"])
        forged = dict(out["receipt"], approved_source_identities=ids,
                      eligible_source_identities_sha256=release.digest(ids),
                      standing_link_metadata_authorization_verified=True)
        with sqlite3.connect(self.db) as cx:
            self.assertHold("unreviewed_source_selected_for_release", release.admit, cx,
                            out["packet"], out["policy"], forged,
                            as_of_utc="2026-10-18T21:13:00Z",
                            trusted_validator=lambda *a: True,
                            baseline_packet=out["baseline_packet"])
        self.assertEqual(self.rows(), {})

    def test_write_boundary_refuses_unreviewed_identity_even_if_validator_accepts(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", new=[
            (1410, "afp-not-yet-reviewed", "2026-10-18")])
        out = self.validate(tip)
        ids = sorted(r["source_identity"] for r in out["eligible"])
        widened = dict(out["receipt"], approved_source_identities=ids,
                       eligible_source_identities_sha256=release.digest(ids))
        with sqlite3.connect(self.db) as cx:
            self.assertHold("unreviewed_source_selected_for_release", release.admit, cx,
                            out["packet"], out["policy"], widened,
                            as_of_utc="2026-10-18T21:13:00Z",
                            trusted_validator=lambda *a: True,
                            baseline_packet=out["baseline_packet"])
        self.assertEqual(self.rows(), {})

    def test_readback_refuses_a_stored_unreviewed_identity(self):
        tip = self.h.attempt("39124069601-1", "2026-10-18", new=[
            (1410, "afp-not-yet-reviewed", "2026-10-18")])
        out = self.validate(tip)

        def smuggle():
            raise AssertionError("not reached")
        real_admit = cli.admit

        def admit_and_smuggle(conn, *a, **kw):
            result = real_admit(conn, *a, **kw)
            conn.execute("INSERT INTO regional_official_source_links SELECT source_family,"
                         " 'afp:1410', desk, 'https://www.afp.mil.ph/news/afp-not-yet-reviewed',"
                         " publisher_posted_date, official_issuer, official_publisher,"
                         " official_republisher, source_git_commit, metadata_version_sha256,"
                         " first_seen_run, release_scope, release_proof_sha256, released_at_utc"
                         " FROM regional_official_source_links WHERE source_identity='afp:1380'")
            return result
        before = sha(self.db)
        with patch.object(cli, "admit", admit_and_smuggle):
            self.assertHold("unreviewed_record_admitted", cli.admit_validated, self.db, [out],
                            as_of_utc="2026-10-18T21:13:00Z")
        self.assertEqual(sha(self.db), before)

    def test_frozen_record_revision_holds(self):
        self.h.records[0]["published_date"] = "2026-10-06"
        tip = self.h.attempt("39124069601-1", "2026-10-18")
        self.assertHold("rolling_source_frozen_identity_or_metadata_changed", self.validate, tip)

    def test_history_not_descending_from_owner_pin_holds(self):
        with patch.object(v, "FROZEN_PIN", "f" * 40):
            self.assertHold("frozen_owner_pin_not_in_source_history", self.validate, self.pin)

    def test_non_numeric_identity_is_refused_before_admission(self):
        self.h.records[-1]["source_identity"] = "afp:photo-1385"
        self.h.captures[-1][0] = "afp:photo-1385"
        with patch.object(v, "FROZEN_PIN", self.h.attempt("39124069601-1", "2026-10-18")):
            with self.assertRaises(ValueError):
                v.candidate_packet(self.h.folder, v.FROZEN_PIN)

    # --- database safety --------------------------------------------------

    def test_interruption_before_commit_rolls_back_and_leaves_no_residue(self):
        before = sha(self.db)

        def crash():
            raise sqlite3.OperationalError("simulated interruption")
        with self.assertRaises(sqlite3.OperationalError):
            cli.admit_validated(self.db, [self.validate(self.pin)],
                                as_of_utc="2026-10-18T21:13:00Z", fail_after_insert=crash)
        self.assertEqual(sha(self.db), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ["pla_watch.db", "source"])

    def test_concurrent_production_writer_is_never_overwritten(self):
        def other_desk_writes():
            with sqlite3.connect(self.db) as cx:
                cx.execute("INSERT INTO articles (url) VALUES ('https://example.invalid/new')")
            cx.close()
        self.assertHold("production_database_changed_concurrently", cli.admit_validated,
                        self.db, [self.validate(self.pin)], as_of_utc="2026-10-18T21:13:00Z",
                        fail_after_insert=other_desk_writes)
        with sqlite3.connect(self.db) as cx:
            self.assertEqual(cx.execute("SELECT count(*) FROM articles").fetchone(), (2,))
            self.assertEqual(cx.execute("SELECT count(*) FROM regional_official_source_links "
                                        "WHERE desk='philippines'").fetchone(), (0,))

    def test_legacy_article_url_collision_holds_whole_admission(self):
        with sqlite3.connect(self.db) as cx:
            cx.execute("INSERT INTO articles (url) VALUES "
                       "('https://www.afp.mil.ph/news/afp-news-day-3')")
        cx.close()
        before = sha(self.db)
        self.assertHold("legacy_article_url_collision", cli.admit_validated, self.db,
                        [self.validate(self.pin)], as_of_utc="2026-10-18T21:13:00Z")
        self.assertEqual(sha(self.db), before)

    def test_caller_supplied_receipt_or_validator_is_refused(self):
        out = self.validate(self.pin)
        forged = dict(out["receipt"])
        with sqlite3.connect(self.db) as cx:
            self.assertHold("trusted_release_evidence_not_authenticated", release.admit, cx,
                            out["packet"], out["policy"], forged,
                            as_of_utc="2026-10-18T21:13:00Z",
                            trusted_validator=out["trusted_validator"])
            self.assertHold("trusted_release_evidence_validator_missing", release.admit, cx,
                            out["packet"], out["policy"], out["receipt"],
                            as_of_utc="2026-10-18T21:13:00Z")

    # --- private envelope -------------------------------------------------

    def _ipr_main(self):
        main = self.root / "ipr-main"
        main.mkdir()
        git(main, "init", "-q")
        git(main, "config", "user.name", "Offline QA")
        git(main, "config", "user.email", "offline@example.invalid")
        git(main, "commit", "-q", "--allow-empty", "-m", "reviewed validator")
        return main, git(main, "rev-parse", "HEAD")

    def _signed(self):
        public_tip = self.h.attempt("39124069601-1", "2026-10-18")
        private_tip = self.h.attempt("39200000000-1", "2026-10-19", kind="private", new=[
            (1412, "afp-private-custody-item", "2026-10-19")])
        main, ref = self._ipr_main()
        validated = v.validate_source_checkout(
            self.h.folder, private_tip, fetch_run=scheduled_runs(
                *self.runs, 39124069601, private=[39200000000]),
            validator_ref=ref)
        body, mac = v.sign_envelope(validated, key=KEY, source_run_attempt="39200000000-1",
                                    public_frozen_tip=public_tip)
        return body, mac, public_tip, main

    def _open(self, body, mac, public_tip, main, **kw):
        args = dict(key=KEY, public_checkout=self.h.folder, public_frozen_tip=public_tip,
                    validator_ref=self.ref, public_main=main, fetch_run=self.fetch)
        args.update(kw)
        return v.validate_signed_envelope(body, mac, **args)

    def test_signed_private_envelope_admits_reviewed_cohort_and_holds_new_record(self):
        body, mac, public_tip, main = self._signed()
        plain = gzip.decompress(body).decode()
        self.assertNotIn(SECRET, plain)
        self.assertNotIn(TITLE, plain)
        out = self._open(body, mac, public_tip, main)
        self.assertEqual((len(out["eligible"]), len(out["approved"])), (7, 6))
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-19T21:13:00Z")
        self.assertEqual(total, 6)
        self.assertEqual(receipts[0]["held_pending_individual_approval"], 1)
        self.assertNotIn("afp:1412", self.rows())

    def test_signed_envelope_forgery_and_binding_failures_hold(self):
        body, mac, public_tip, main = self._signed()
        self.assertHold("signed_envelope_mac_invalid", self._open, body, "0" * 64, public_tip, main)
        self.assertHold("signed_envelope_mac_invalid", self._open, body, mac, public_tip, main,
                        key=b"x" * 32)
        envelope = json.loads(gzip.decompress(body))
        envelope["packet"]["records"][0]["canonical_official_url"] += "?x"
        forged = gzip.compress(json.dumps(envelope).encode(), mtime=0)
        self.assertHold("signed_envelope_mac_invalid", self._open, forged, mac, public_tip, main)
        self.assertHold("private_history_not_bound_to_public_frozen_tip", self._open,
                        body, mac, self.pin, main)
        unrelated = self.root / "unrelated-main"
        unrelated.mkdir()
        git(unrelated, "init", "-q")
        git(unrelated, "config", "user.name", "Offline QA")
        git(unrelated, "config", "user.email", "offline@example.invalid")
        git(unrelated, "commit", "-q", "--allow-empty", "-m", "unreviewed")
        self.assertHold("private_validator_code_not_on_public_main", self._open,
                        body, mac, public_tip, unrelated)

    # --- CLI boundaries ---------------------------------------------------

    def test_cli_refuses_wrong_database_targets_and_prints_no_source_text(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["admit", "--source-checkout", str(self.h.folder),
                           "--source-commit", self.pin, "--production-db", str(self.db)])
        self.assertEqual(rc, 2)
        self.assertIn("only_canonical_production_database_allowed", buf.getvalue())
        buf = io.StringIO()
        with redirect_stdout(buf), patch.object(cli, "github_fetcher", lambda *a, **k: self.fetch):
            rc = cli.main(["admit", "--rehearsal", "--validator-ref", self.ref,
                           "--source-checkout", str(self.h.folder),
                           "--source-commit", self.pin, "--production-db", str(self.db)])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertEqual(json.loads(buf.getvalue())["philippines_rows_after"], 6)
        for leaked in (SECRET, TITLE, "https://www.afp.mil.ph"):
            self.assertNotIn(leaked, buf.getvalue())

    def test_cli_envelope_without_key_holds(self):
        buf = io.StringIO()
        body = self.root / "e.gz"
        body.write_bytes(b"x")
        with redirect_stdout(buf), patch.object(cli, "github_fetcher", lambda *a, **k: self.fetch), \
                patch.dict("os.environ", {cli.BRIDGE_KEY_ENV: ""}):
            rc = cli.main(["admit", "--rehearsal", "--validator-ref", self.ref,
                           "--source-checkout", str(self.h.folder), "--source-commit", self.pin,
                           "--production-db", str(self.db), "--signed-envelope", str(body),
                           "--signed-mac", str(body)])
        self.assertEqual(rc, 2)
        self.assertIn("afp_bridge_key_not_configured", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
