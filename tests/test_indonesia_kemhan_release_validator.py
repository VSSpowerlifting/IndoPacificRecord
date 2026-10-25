"""Real Git/SQLite synthetic tests for the Kemhan trusted release validator.

No network: GitHub run records come from a fake fetcher. Every case builds an
actual source history (shadow DB, preserved captures, ledgers, private attempt
receipts and exact commit subjects) like the collector and private runner do.
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

from core import indonesia_kemhan_release_validator as v
from core import regional_official_link_release as release
from core.crossdesk_official_metadata_candidates import KEMHAN_HELD
from scripts import admit_indonesia_kemhan_official_links as cli

SECRET = "PRIVATE KEMHAN BODY must never leave the source history"
TITLE = "Judul Asli Berita Kemhan"
KEY = b"k" * 32
SQL = """CREATE TABLE shadow_records (
source_identity TEXT, url TEXT, source_slug TEXT, title_original TEXT,
text_original TEXT, published_date TEXT, language_tag TEXT, metadata_json TEXT,
content_sha256 TEXT, capture_sha256 TEXT, first_seen_run TEXT)"""
META = json.dumps({"publisher": "Kementerian Pertahanan Republik Indonesia",
                   "issuer": None, "publication_kind": "institutional_news",
                   "body_scope": "published_html_text", "attachments_collected": False})


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()


class History:
    """Append-only synthetic Kemhan source history."""

    def __init__(self, folder):
        self.folder = folder
        folder.mkdir()
        git(folder, "init", "-q")
        git(folder, "config", "user.name", "Offline QA")
        git(folder, "config", "user.email", "offline@example.invalid")
        self.records = []
        (folder / "state" / "captures").mkdir(parents=True)
        (folder / "state" / "ledger").mkdir()
        (folder / "state" / "clock.json").write_text(json.dumps({
            "desk": "indonesia", "day_zero_utc": "2026-10-06T16:52:15+00:00",
            "day_zero_run_id": "local-native-20261006-indonesia"}))

    def add_record(self, path, day, first_seen):
        capture = ("<html>%s</html>" % path).encode()
        sha = hashlib.sha256(capture).hexdigest()
        (self.folder / "state" / "captures" / (sha + ".bin")).write_bytes(capture)
        self.records.append(["kemhan:" + path, "https://www.kemhan.go.id" + path,
                             "id_kemhan_news", TITLE, SECRET, day, "id", META,
                             hashlib.sha256(SECRET.encode()).hexdigest(), sha, first_seen])

    def _write_db(self):
        db = self.folder / "state" / "shadow.db"
        if db.exists():
            db.unlink()
        with sqlite3.connect(db) as cx:
            cx.execute(SQL)
            cx.execute("CREATE TABLE shadow_meta (desk TEXT PRIMARY KEY)")
            cx.execute("INSERT INTO shadow_meta VALUES ('indonesia')")
            cx.executemany("INSERT INTO shadow_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           self.records)
        cx.close()

    def attempt(self, run_id, day, *, source="schedule-slot", kind="shadow",
                ledger=True, healthy=True, subject=None, new=()):
        for path, pday in new:
            self.add_record(path, pday, run_id)
        self._write_db()
        if ledger:
            (self.folder / "state" / "ledger" / ("%sT20-%s.json" % (day, run_id))).write_text(
                json.dumps({"desk": "indonesia", "run_id": run_id, "target_date": day,
                            "target_date_source": source,
                            "result": "ok" if healthy else "partial",
                            "health": "ok" if healthy else "degraded",
                            "listing_status": "ok",
                            "listing_report": {"window_proven": True},
                            "fetch_failures": 0, "extraction_failures": 0}))
        if kind == "private":
            receipts = self.folder / "state" / "private_attempts"
            receipts.mkdir(exist_ok=True)
            (receipts / (run_id + ".json")).write_text(json.dumps({
                "schema": "ipr-indonesia-private-attempt/1", "run_attempt": run_id,
                "collector_commit": "a" * 40, "collector_exit_status": 0 if healthy else 1,
                "persisted_at_utc": day + "T20:00:00+00:00",
                "collection_success_claim": False,
                "source_or_publication_rights_granted": False}))
        if subject is None:
            subject = ("private-indonesia: preserve attempt %s" % run_id if kind == "private"
                       else "shadow(indonesia): initial native collection %s" % run_id
                       if run_id.startswith("local-native") else
                       "shadow(indonesia): run %s" % run_id)
        git(self.folder, "add", "-A", "state")
        git(self.folder, "commit", "-qm", subject)
        return git(self.folder, "rev-parse", "HEAD")


def scheduled_runs(*numbers, event="schedule", repo=v.PUBLIC_REPOSITORY,
                   path=".github/workflows/indonesia_korea_shadow.yml", private=()):
    runs = {str(n): {"id": n, "run_attempt": 1, "event": event, "head_branch": "main",
                     "path": path, "repository": {"full_name": repo},
                     "conclusion": "success"} for n in numbers}
    for n in private:
        runs[str(n)] = {"id": n, "run_attempt": 1, "event": "schedule", "head_branch": "main",
                        "path": ".github/workflows/indonesia_private_first_collector.yml",
                        "repository": {"full_name": v.PRIVATE_REPOSITORY},
                        "conclusion": "failure"}
    return lambda number: runs.get(number)


def policy_for(packet):
    policy = copy.deepcopy(release.load_owner_policy())
    spec = next(s for s in policy["source_families"] if s["source_family"] == "id_kemhan_news")
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
                   "('ph_afp_articles','afp:1','philippines','https://www.afp.mil.ph/x',"
                   "'2026-10-01',NULL,'Armed Forces of the Philippines',NULL,?,?,'1-1',"
                   "'official_link_only',?,'2026-10-15T00:00:00Z')",
                   ("b" * 40, "c" * 64, "d" * 64))
    cx.close()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class KemhanReleaseValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-kemhan-validator-test-")
        root = Path(self.tmp.name)
        self.h = History(root / "source")
        self.h.attempt("local-native-20261006-indonesia", "2026-10-06", source="manual-utc-date",
                       new=[("/2026/10/02/" + KEMHAN_HELD.rsplit("/", 1)[1], "2026-10-02"),
                            ("/2026/10/05/menhan-terima-kunjungan.html", "2026-10-05")])
        self.runs = []
        for i in range(7):
            n = 37693074726 + i
            day = "2026-10-%02d" % (7 + i)
            self.runs.append(n)
            self.pin = self.h.attempt("%d-1" % n, day, new=[
                ("/2026/10/%02d/kemhan-berita-hari-%d.html" % (7 + i, i), day)])
        self.baseline = v.candidate_packet(self.h.folder, self.pin)
        self.policy = policy_for(self.baseline)
        self.patches = [patch.object(v, "FROZEN_PIN", self.pin),
                        patch.object(v, "load_owner_policy", lambda: self.policy),
                        patch.object(release, "load_owner_policy", lambda: self.policy)]
        for p in self.patches:
            p.start()
        self.fetch = scheduled_runs(*self.runs, 38958633428)
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
                "source_git_commit FROM regional_official_source_links WHERE desk='indonesia'")}

    # --- happy path, rolling cohort, replay --------------------------------

    NEW_ID = "kemhan:/2026/10/16/" + "-".join(["menhan-sjafrie-tinjau"] * 9) + ".html"

    def _new_record_tip(self):
        return self.h.attempt("38958633428-1", "2026-10-16", new=[
            (self.NEW_ID[len("kemhan:"):], "2026-10-16")])

    def without_standing_authorization(self):
        self.policy.pop("standing_link_metadata_authorizations")

    def test_standing_authorization_admits_new_record_once_without_review_claim(self):
        tip = self._new_record_tip()
        out = self.validate(tip)
        receipt = out["receipt"]
        self.assertEqual(receipt["authenticated_scheduled_days"], [
            "2026-10-%02d" % d for d in range(7, 14)] + ["2026-10-16"])
        self.assertEqual(len(out["eligible"]), 9)  # 10 stored, Yonif 880 held
        self.assertEqual(len(out["approved"]), 9)  # frozen cohort + post-pin record
        self.assertIs(receipt["standing_link_metadata_authorization_verified"], True)
        self.assertIs(receipt["record_specific_review_receipts_verified"], False)
        self.assertEqual(receipt["review_basis"], v.STANDING_REVIEW_BASIS)
        self.assertEqual(receipt["released_without_record_specific_review_count"], 1)
        self.assertEqual(receipt["released_without_record_specific_review_sha256"],
                         release.digest([self.NEW_ID]))
        self.assertEqual(receipt["held_unreviewed_count"], 0)
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual((receipts[0]["new_official_links"], total), (9, 9))
        self.assertEqual(receipts[0]["held_pending_individual_approval"], 0)
        self.assertNotIn(v.HELD_IDENTITY, self.rows())
        self.assertEqual(self.rows()[self.NEW_ID][:2],
                         ("https://www.kemhan.go.id" + self.NEW_ID[len("kemhan:"):],
                          "2026-10-16"))
        before = sha(self.db)
        receipts, _ = cli.admit_validated(self.db, [self.validate(tip)],
                                          as_of_utc="2026-10-19T19:43:00Z")
        self.assertEqual((receipts[0]["new_official_links"],
                          receipts[0]["unchanged_official_links"]), (0, 9))
        self.assertEqual(sha(self.db), before, "replay must not rewrite the database")
        with sqlite3.connect(self.db) as cx:
            self.assertEqual(cx.execute("SELECT count(*) FROM regional_official_source_links "
                                        "WHERE desk='philippines'").fetchone(), (1,))

    def test_without_standing_authorization_new_record_stays_held(self):
        self.without_standing_authorization()
        out = self.validate(self._new_record_tip())
        self.assertEqual(len(out["approved"]), 8)  # the owner-reviewed frozen cohort
        self.assertEqual(out["receipt"]["held_unreviewed_count"], 1)
        self.assertEqual(out["receipt"]["review_basis"], v.REVIEW_BASIS)
        self.assertIs(out["receipt"]["standing_link_metadata_authorization_verified"], False)
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual((receipts[0]["new_official_links"], total), (8, 8))
        self.assertEqual(receipts[0]["held_pending_individual_approval"], 1)
        self.assertNotIn(self.NEW_ID, self.rows())

    def test_released_post_pin_record_revised_or_missing_later_holds(self):
        cli.admit_validated(self.db, [self.validate(self._new_record_tip())],
                            as_of_utc="2026-10-18T19:43:00Z")
        before = sha(self.db)
        revised = self.h.records[-1]
        path = "/2026/10/15/" + self.NEW_ID.rsplit("/", 1)[1]
        revised[0], revised[1], revised[5] = ("kemhan:" + path,
                                              "https://www.kemhan.go.id" + path, "2026-10-15")
        out = self.validate(self.h.attempt("39065613730-1", "2026-10-17",
                                           kind="private", source="manual-utc-date"))
        self.assertNotIn(self.NEW_ID, {r["source_identity"] for r in out["eligible"]})
        self.assertHold("previously_released_source_missing_or_changed",
                        cli.admit_validated, self.db, [out], as_of_utc="2026-10-18T20:00:00Z")
        self.assertEqual(sha(self.db), before)

    def test_later_collection_keeps_original_admitted_version(self):
        first = self.h.attempt("38958633428-1", "2026-10-16")
        cli.admit_validated(self.db, [self.validate(first)], as_of_utc="2026-10-18T19:43:00Z")
        later = self.h.attempt("39065613730-1", "2026-10-17", kind="private", source="manual-utc-date")
        receipts, _ = cli.admit_validated(self.db, [self.validate(later)],
                                          as_of_utc="2026-10-18T20:00:00Z")
        self.assertEqual(receipts[0]["new_official_links"], 0)
        self.assertEqual({r[2] for r in self.rows().values()}, {first})

    # --- authentication failures -----------------------------------------

    def assertHold(self, reason, fn, *a, **kw):
        with self.assertRaises(release.RegionalLinkHold) as caught:
            fn(*a, **kw)
        self.assertEqual(str(caught.exception), reason)

    def test_ledger_schedule_claim_must_match_github_record(self):
        tip = self.h.attempt("38958633428-1", "2026-10-16")
        lying = scheduled_runs(*self.runs, 38958633428, event="workflow_dispatch")
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, lying)
        foreign = scheduled_runs(*self.runs, 38958633428, path=".github/workflows/other.yml")
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, foreign)

    def test_elapsed_days_are_measured_not_required(self):
        out = self.validate(self.pin, scheduled_runs(self.runs[0]))
        self.assertEqual(out["receipt"]["authenticated_scheduled_days"], ["2026-10-07"])
        self.assertEqual(out["receipt"]["scheduled_claims_not_visible"], 6)
        receipts, _ = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual(receipts[0]["new_official_links"], 8)

    def test_no_authenticated_healthy_scheduled_run_holds(self):
        self.assertHold("scheduled_history_not_authenticated", self.validate, self.pin,
                        scheduled_runs())

    def test_tampered_or_missing_capture_holds(self):
        cap = next((self.h.folder / "state" / "captures").glob("*.bin"))
        cap.write_bytes(b"altered after capture")
        tip = self.h.attempt("38958633428-1", "2026-10-16")
        self.assertHold("preserved_capture_digest_mismatch", self.validate, tip)

    def test_stored_original_without_preserved_capture_holds(self):
        self.h.add_record("/2026/10/16/tanpa-tangkapan.html", "2026-10-16", "38958633428-1")
        cap = self.h.folder / "state" / "captures" / (self.h.records[-1][9] + ".bin")
        cap.unlink()
        tip = self.h.attempt("38958633428-1", "2026-10-16")
        self.assertHold("stored_original_not_bound_to_preserved_capture", self.validate, tip)

    def test_unexplained_or_unledgered_history_commits_hold(self):
        tip = self.h.attempt("38958633428-1", "2026-10-16", subject="manual edit of state")
        self.assertHold("unrecognized_source_history_commit", self.validate, tip)

    def test_shadow_commit_without_ledger_holds(self):
        tip = self.h.attempt("38958633428-1", "2026-10-16", ledger=False, new=[
            ("/2026/10/16/tanpa-ledger.html", "2026-10-16")])
        self.assertHold("attempt_ledger_and_source_history_disagree", self.validate, tip)

    def test_private_attempt_without_ledger_is_visible_failure_not_success(self):
        tip = self.h.attempt("39065613730-1", "2026-10-17", kind="private",
                             ledger=False, healthy=False)
        evidence = self.validate(tip)["receipt"]["evidence"]
        self.assertEqual((evidence["private_attempts_without_ledger"],
                          evidence["private_attempts_nonzero_exit"]), (1, 1))

    def test_unhealthy_scheduled_attempt_does_not_count_as_a_day(self):
        tip = self.h.attempt("38958633428-1", "2026-10-16", healthy=False)
        out = self.validate(tip)
        self.assertNotIn("2026-10-16", out["receipt"]["authenticated_scheduled_days"])
        self.assertEqual(out["receipt"]["evidence"]["unhealthy_attempts"], 1)
        self.assertEqual(out["receipt"]["authenticated_failed_scheduled_attempts"], 1)

    def test_failed_attempt_cannot_be_relabelled_as_scheduled(self):
        tip = self.h.attempt("38958633428-1", "2026-10-16", healthy=False)
        runs = scheduled_runs(*self.runs)
        lying = lambda n: (dict(id=38958633428, run_attempt=1, event="workflow_dispatch",
                                head_branch="main", repository={"full_name": v.PUBLIC_REPOSITORY},
                                path=".github/workflows/indonesia_korea_shadow.yml")
                           if n == "38958633428" else runs(n))
        self.assertHold("ledger_claims_schedule_github_does_not", self.validate, tip, lying)

    # --- review basis -----------------------------------------------------

    def test_receipt_states_the_actual_review_basis(self):
        receipt = self.validate(self.h.attempt("38958633428-1", "2026-10-16"))["receipt"]
        self.assertIs(receipt["owner_review_declaration_bound_to_frozen_manifest"], True)
        self.assertIs(receipt["record_specific_review_receipts_verified"], False)
        self.assertIs(self.policy[
            "machine_verified_record_specific_human_review_receipts_in_repository"], False)
        for untrue in ("review_receipts_version_matched",
                       "seven_actual_scheduled_days_authenticated"):
            self.assertNotIn(untrue, receipt)
        claiming = dict(receipt, record_specific_review_receipts_verified=True)
        out = self.validate(self.h.attempt("38958633429-1", "2026-10-17"))
        self.assertHold("independent_release_evidence_missing", release.verify_release_evidence,
                        claiming, out["packet"], out["eligible"])

    def test_write_boundary_refuses_unreviewed_identity_even_if_validator_accepts(self):
        self.without_standing_authorization()
        tip = self.h.attempt("38958633428-1", "2026-10-16", new=[
            ("/2026/10/16/belum-ditinjau.html", "2026-10-16")])
        out = self.validate(tip)
        ids = sorted(r["source_identity"] for r in out["eligible"])
        widened = dict(out["receipt"], approved_source_identities=ids,
                       eligible_source_identities_sha256=release.digest(ids))
        claiming = dict(widened, standing_link_metadata_authorization_verified=True)
        with sqlite3.connect(self.db) as cx:
            for receipt in (widened, claiming):
                self.assertHold("unreviewed_source_selected_for_release", release.admit, cx,
                                out["packet"], out["policy"], receipt,
                                as_of_utc="2026-10-18T19:43:00Z",
                                trusted_validator=lambda *a: True,
                                baseline_packet=out["baseline_packet"])
        self.assertEqual(self.rows(), {})

    def test_write_boundary_refuses_semantic_hold_under_standing_authorization(self):
        out = self.validate(self._new_record_tip())
        ids = sorted([v.HELD_IDENTITY] + [r["source_identity"] for r in out["eligible"]])
        widened = dict(out["receipt"], approved_source_identities=ids)
        with sqlite3.connect(self.db) as cx:
            self.assertHold("release_selection_untrusted_or_contains_held_source", release.admit,
                            cx, out["packet"], out["policy"], widened,
                            as_of_utc="2026-10-18T19:43:00Z",
                            trusted_validator=lambda *a: True,
                            baseline_packet=out["baseline_packet"])
        self.assertEqual(self.rows(), {})

    def test_standing_authorization_scope_is_pinned(self):
        self.patches[2].stop()
        try:
            real = release.load_owner_policy()
            self.assertTrue(release.standing_link_metadata_authorization(real, "id_kemhan_news"))
            # AFP has its own separate owner ruling (DECISION_LOG 2026-10-18);
            # an unlisted sibling family is still never authorized.
            self.assertTrue(release.standing_link_metadata_authorization(real, "ph_afp_articles"))
            self.assertFalse(release.standing_link_metadata_authorization(real,
                                                                          "id_kemhan_press"))
            standing = real["standing_link_metadata_authorizations"][0]
            for key, bad in (("per_record_human_review_required", True),
                             ("asserts_human_review_outside_frozen_cohort", True),
                             ("elapsed_time_gate", True),
                             ("source_family", "id_kemhan_press"),
                             ("titles_authorized", True)):
                broken = copy.deepcopy(real)
                broken["standing_link_metadata_authorizations"][0] = dict(standing, **{key: bad})
                with patch.object(release.json, "loads", lambda *_a, **_k: broken):
                    self.assertHold("owner_standing_authorization_scope_changed",
                                    release.load_owner_policy)
        finally:
            self.patches[2].start()

    def test_frozen_record_date_revision_holds(self):
        self.h.records[1][5] = "2026-10-04"
        self.h.records[1][0] = "kemhan:/2026/10/04/menhan-terima-kunjungan.html"
        self.h.records[1][1] = "https://www.kemhan.go.id/2026/10/04/menhan-terima-kunjungan.html"
        tip = self.h.attempt("38958633428-1", "2026-10-16")
        self.assertHold("rolling_source_frozen_identity_or_metadata_changed", self.validate, tip)

    def test_history_not_descending_from_owner_pin_holds(self):
        with patch.object(v, "FROZEN_PIN", "f" * 40):
            self.assertHold("frozen_owner_pin_not_in_source_history", self.validate, self.pin)

    # --- database safety --------------------------------------------------

    def test_interruption_before_commit_rolls_back_and_leaves_no_residue(self):
        before = sha(self.db)

        def crash():
            raise sqlite3.OperationalError("simulated interruption")
        with self.assertRaises(sqlite3.OperationalError):
            cli.admit_validated(self.db, [self.validate(self.pin)],
                                as_of_utc="2026-10-18T19:43:00Z", fail_after_insert=crash)
        self.assertEqual(sha(self.db), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ["pla_watch.db", "source"])

    def test_concurrent_production_writer_is_never_overwritten(self):
        def other_desk_writes():
            with sqlite3.connect(self.db) as cx:
                cx.execute("INSERT INTO articles (url) VALUES ('https://example.invalid/new')")
            cx.close()
        self.assertHold("production_database_changed_concurrently", cli.admit_validated,
                        self.db, [self.validate(self.pin)], as_of_utc="2026-10-18T19:43:00Z",
                        fail_after_insert=other_desk_writes)
        with sqlite3.connect(self.db) as cx:
            self.assertEqual(cx.execute("SELECT count(*) FROM articles").fetchone(), (2,))
            self.assertEqual(cx.execute("SELECT count(*) FROM regional_official_source_links "
                                        "WHERE desk='indonesia'").fetchone(), (0,))

    def test_caller_supplied_receipt_or_validator_is_refused(self):
        out = self.validate(self.pin)
        forged = dict(out["receipt"])
        with sqlite3.connect(self.db) as cx:
            self.assertHold("trusted_release_evidence_not_authenticated", release.admit, cx,
                            out["packet"], out["policy"], forged,
                            as_of_utc="2026-10-18T19:43:00Z",
                            trusted_validator=out["trusted_validator"])
            self.assertHold("trusted_release_evidence_validator_missing", release.admit, cx,
                            out["packet"], out["policy"], out["receipt"],
                            as_of_utc="2026-10-18T19:43:00Z")

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
        public_tip = self.h.attempt("38958633428-1", "2026-10-16")
        private_tip = self.h.attempt("39145984711-1", "2026-10-18", kind="private", new=[
            ("/2026/10/18/wamenhan-terima-audiensi.html", "2026-10-18")])
        main, ref = self._ipr_main()
        validated = v.validate_source_checkout(
            self.h.folder, private_tip, fetch_run=scheduled_runs(
                *self.runs, 38958633428, private=[39145984711]),
            validator_ref=ref)
        body, mac = v.sign_envelope(validated, key=KEY, source_run_attempt="39145984711-1",
                                    public_frozen_tip=public_tip)
        return body, mac, public_tip, main

    def _open(self, body, mac, public_tip, main, **kw):
        args = dict(key=KEY, public_checkout=self.h.folder, public_frozen_tip=public_tip,
                    validator_ref=self.ref, public_main=main, fetch_run=self.fetch)
        args.update(kw)
        return v.validate_signed_envelope(body, mac, **args)

    def test_signed_private_envelope_admits_new_private_record(self):
        body, mac, public_tip, main = self._signed()
        plain = gzip.decompress(body).decode()
        self.assertNotIn(SECRET, plain)
        self.assertNotIn(TITLE, plain)
        out = self._open(body, mac, public_tip, main)
        self.assertEqual((len(out["eligible"]), len(out["approved"])), (9, 9))
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual(total, 9)  # Yonif 880 held; new private item admitted
        self.assertEqual(receipts[0]["held_pending_individual_approval"], 0)
        self.assertIn("kemhan:/2026/10/18/wamenhan-terima-audiensi.html", self.rows())
        self.assertNotIn(v.HELD_IDENTITY, self.rows())

    def test_daily_cycles_after_private_release_neither_hold_nor_rewrite(self):
        """The scheduled retry (frozen only) and later envelope dispatches must
        keep working once a private record is released, and still fail closed."""
        body, mac, public_tip, main = self._signed()
        frozen = self.validate(public_tip)
        out = self._open(body, mac, public_tip, main)
        receipts, total = cli.admit_validated(self.db, [frozen, out], frozen_first=True,
                                              as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual(([r["new_official_links"] for r in receipts], total), ([8, 1], 9))
        released = sha(self.db)
        # Without the baseline exemption the frozen packet alone would refuse
        # the nine stored rows: this is the failure the exemption removes.
        self.assertHold("previously_released_source_missing_or_changed",
                        cli.admit_validated, self.db, [self.validate(public_tip)],
                        as_of_utc="2026-10-19T19:43:00Z")
        # 19:43 scheduled reconciliation: frozen history only, no envelope.
        receipts, total = cli.admit_validated(self.db, [self.validate(public_tip)],
                                              frozen_first=True, as_of_utc="2026-10-19T19:43:00Z")
        self.assertEqual((receipts, total), ([], 9))
        # Next day's dispatch: frozen baseline plus the same envelope again.
        receipts, total = cli.admit_validated(
            self.db, [self.validate(public_tip), self._open(body, mac, public_tip, main)],
            frozen_first=True, as_of_utc="2026-10-20T19:43:00Z")
        self.assertEqual(([(r["new_official_links"], r["unchanged_official_links"])
                           for r in receipts], total), ([(0, 9)], 9))
        self.assertEqual(sha(self.db), released, "replays must not rewrite the database")
        # A frozen row altered in SQLite is never waved through.
        with sqlite3.connect(self.db) as cx:
            cx.execute("UPDATE regional_official_source_links SET publisher_posted_date="
                       "'2026-10-01' WHERE source_identity=?", ("kemhan:/2026/10/05/menhan-terima-kunjungan.html",))
        tampered = sha(self.db)
        self.assertHold("previously_released_source_missing_or_changed",
                        cli.admit_validated, self.db, [self.validate(public_tip)],
                        frozen_first=True, as_of_utc="2026-10-21T19:43:00Z")
        self.assertEqual(sha(self.db), tampered)

    def test_envelope_that_drops_a_released_private_record_still_holds(self):
        body, mac, public_tip, main = self._signed()
        cli.admit_validated(self.db, [self.validate(public_tip),
                                      self._open(body, mac, public_tip, main)],
                            frozen_first=True, as_of_utc="2026-10-18T19:43:00Z")
        before = sha(self.db)
        revised = self.h.records[-1]
        path = "/2026/10/17/" + revised[0].rsplit("/", 1)[1]
        revised[0], revised[1], revised[5] = ("kemhan:" + path,
                                              "https://www.kemhan.go.id" + path, "2026-10-17")
        later = self.validate(self.h.attempt("39145984712-1", "2026-10-19",
                                             kind="private", source="manual-utc-date"))
        self.assertHold("previously_released_source_missing_or_changed",
                        cli.admit_validated, self.db, [self.validate(public_tip), later],
                        frozen_first=True, as_of_utc="2026-10-19T20:00:00Z")
        self.assertEqual(sha(self.db), before)

    def test_signed_private_envelope_without_standing_authorization_holds_new_record(self):
        self.without_standing_authorization()
        out = self._open(*self._signed())
        self.assertEqual((len(out["eligible"]), len(out["approved"])), (9, 8))
        receipts, total = cli.admit_validated(self.db, [out], as_of_utc="2026-10-18T19:43:00Z")
        self.assertEqual((total, receipts[0]["held_pending_individual_approval"]), (8, 1))
        self.assertNotIn("kemhan:/2026/10/18/wamenhan-terima-audiensi.html", self.rows())

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
        self.assertHold("bridge_key_missing_or_short", self._open, body, mac, public_tip, main,
                        key=b"")

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
        for leaked in (SECRET, TITLE, "https://www.kemhan.go.id"):
            self.assertNotIn(leaked, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
