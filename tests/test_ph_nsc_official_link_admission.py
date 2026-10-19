"""NSC link admission over disposable Git state and in-memory SQLite.

The state is produced by the real NSC shadow runner against the unit-test
fixture pages (tests.test_ph_nsc_adapter), with the network blocked. It is a
synthetic rehearsal, never a live observation. Test seals use a fictional key
and are never human approvals.
"""
import copy
import hashlib
import hmac
import json
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from core import ph_nsc_official_link_admission as nsc
from core.regional_reviewed_evidence import _canonical
from migrations.versions import m0010_regional_official_source_links as base
from migrations.versions import m0013_vietnam_regional_official_links as m13
from migrations.versions import m0014_ph_nsc_regional_official_links as m14
from scripts import shadow_collect_ph_nsc as runner
from tests.test_ph_nsc_adapter import Rig, TARGET

KEY = b"fictional-test-only-owner-key-0000000000"
NOW = "2026-10-19T12:00:00Z"
CLOSED = {"schema": nsc.POLICY, "source_family": nsc.FAMILY,
          "standing_metadata_publication_authorized": False,
          "owner_decision_reference": None, "category_anomaly_resolved": False,
          "category_anomaly_reference": None, "permitted_fields": nsc.PERMITTED_FIELDS,
          "notes": "fictional test policy"}


def policy(**changes):
    p = dict(CLOSED, **changes)
    return p


RESOLVED = policy(category_anomaly_resolved=True,
                  category_anomaly_reference="Fictional test resolution only")
STANDING = dict(RESOLVED, standing_metadata_publication_authorized=True,
                owner_decision_reference="Fictional standing test policy only")


def seal(review):
    return {"review": review, "hmac_sha256": hmac.new(
        KEY, nsc.DOMAIN + _canonical(review), hashlib.sha256).hexdigest()}


def decision(packet, **changes):
    review = {
        "schema": nsc.DECISION, "candidate_sha256": nsc.candidate_digest(packet),
        "approved_source_identities": sorted(r["source_identity"] for r in packet["records"]),
        "reviewer": "Fictional test reviewer", "reviewed_on": "2026-10-19",
        "rights_basis": "Fictional metadata-only test authorization",
        "approval_reference": "Fictional offline test; never a real approval",
        "permitted_fields": nsc.PERMITTED_FIELDS,
        "production_release_authorized": True, "protected_custody_verified": True,
        "custody_reference": "Fictional custody test only",
    }
    review.update(changes)
    return seal(review)


def index_db():
    conn = sqlite3.connect(":memory:")
    base.up(conn)
    m13.up(conn)
    m14.up(conn)
    return conn


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), check=True,
                          capture_output=True, text=True).stdout.strip()


class NscCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "archive"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Fixture")
        guard = mock.patch.object(socket.socket, "connect",
                                  side_effect=AssertionError("real network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)
        self.cx = index_db()
        self.addCleanup(self.cx.close)

    def collect(self, run_id="r1", lookback=22, target=TARGET):
        entry = runner.run(self.repo / "state", target, lookback, 40, run_id,
                           "collector-sha", adapter=Rig().adapter)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", run_id)
        return entry, git(self.repo, "rev-parse", "HEAD")

    def packet(self, commit, ref=nsc.PRIVATE_REF):
        return nsc.prepare(self.repo, commit, ref)

    def count(self, family=nsc.FAMILY):
        return self.cx.execute("SELECT count(*) FROM " + base.TABLE
                               + " WHERE source_family=?", (family,)).fetchone()[0]


class Replay(NscCase):
    def test_replay_is_metadata_only_and_held_by_default(self):
        _, sha = self.collect()
        packet = self.packet(sha)
        self.assertEqual([r["source_identity"] for r in packet["records"]],
                         ["nsc:2269", "nsc:3108"])
        text = json.dumps(packet)
        for key in ("title_original", "text_original", "site_byline", "summary"):
            self.assertNotIn('"%s"' % key, text)
        self.assertFalse(packet["public_release_authorized"])
        self.assertTrue(all(l["official_issuer"] is None and l["official_publisher"] == "ph_nsc"
                            for l in packet["links"]))
        with self.assertRaisesRegex(ValueError, "category_anomaly_unresolved"):
            nsc.admit(self.cx, packet, policy=nsc.load_policy(), as_of_utc=NOW)
        with self.assertRaisesRegex(ValueError, "metadata_publication_not_authorized"):
            nsc.admit(self.cx, packet, policy=RESOLVED, as_of_utc=NOW)
        self.assertEqual(self.count(), 0)

    def test_committed_policy_is_fail_closed(self):
        p = nsc.load_policy()
        self.assertFalse(p["standing_metadata_publication_authorized"])
        self.assertFalse(p["category_anomaly_resolved"])
        for bad in (dict(p, standing_metadata_publication_authorized=True),
                    dict(p, permitted_fields=nsc.PERMITTED_FIELDS + ["title_original"]),
                    dict(p, extra=1)):
            path = self.root / "p.json"
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, "policy_invalid"):
                nsc.load_policy(path)

    def test_empty_window_is_a_clean_no_op_not_a_hold(self):
        # The prospective window after activation: the category is silent.
        entry, sha = self.collect(target=date(2026, 10, 2), lookback=6)
        self.assertEqual((entry["result"], entry["health"]), ("ok_no_publications", "ok"))
        packet = self.packet(sha)
        self.assertEqual(packet["records"], [])
        # Holds that would apply to a real record are not raised for silence.
        for ref in (nsc.PRIVATE_REF, nsc.PUBLIC_REF):
            result = nsc.admit(self.cx, dict(packet, source_ref=ref),
                               policy=nsc.load_policy(), as_of_utc=NOW)
            self.assertEqual(result["status"], "no_eligible_records")
        self.assertEqual(self.count(), 0)

    def test_public_branch_state_is_never_a_row_source(self):
        _, sha = self.collect()
        packet = self.packet(sha, nsc.PUBLIC_REF)
        with self.assertRaisesRegex(ValueError, "not_from_private_custody"):
            nsc.admit(self.cx, packet, policy=STANDING, as_of_utc=NOW)
        self.assertEqual(self.count(), 0)


class Tampering(NscCase):
    def tamper(self, fn):
        _, sha = self.collect()
        fn(self.repo / "state")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "tamper")
        return git(self.repo, "rev-parse", "HEAD")

    def rewrite(self, sql, *args):
        def fn(state):
            with sqlite3.connect(str(state / "shadow.db")) as db:
                db.execute(sql, args)
            db.close()
        return fn

    def test_changed_capture_bytes_hold(self):
        def fn(state):
            path = next((state / "captures").glob("*.bin"))
            path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "capture_hash_mismatch"):
            self.packet(self.tamper(fn))

    def test_date_discrepancy_holds(self):
        sha = self.tamper(self.rewrite(
            "UPDATE shadow_records SET published_date='2026-01-01' WHERE source_identity='nsc:3108'"))
        with self.assertRaisesRegex(ValueError, "date_discrepancy"):
            self.packet(sha)

    def test_changed_identity_holds(self):
        sha = self.tamper(self.rewrite(
            "UPDATE shadow_records SET source_identity='nsc:9999' WHERE source_identity='nsc:3108'"))
        with self.assertRaisesRegex(ValueError, "identity_changed"):
            self.packet(sha)

    def test_redirected_or_failed_capture_holds(self):
        for sql in ("UPDATE shadow_records SET final_url='https://nsc.gov.ph/elsewhere/'",
                    "UPDATE shadow_records SET http_status=203"):
            with self.subTest(sql=sql):
                self.setUp()
                with self.assertRaisesRegex(ValueError, "provenance_mismatch"):
                    self.packet(self.tamper(self.rewrite(sql)))

    def test_record_from_an_unhealthy_run_holds(self):
        def fn(state):
            path = next((state / "ledger").glob("*.json"))
            entry = json.loads(path.read_text())
            entry["health"] = "fail"
            path.write_text(json.dumps(entry))
        with self.assertRaisesRegex(ValueError, "first_seen_run_unhealthy"):
            self.packet(self.tamper(fn))

    def test_unexpected_file_in_state_tree_holds(self):
        with self.assertRaisesRegex(ValueError, "unexpected_file"):
            self.packet(self.tamper(lambda s: (s / "notes.txt").write_text("x")))


class Admission(NscCase):
    def setUp(self):
        super().setUp()
        from tests.test_regional_official_link_render import insert
        insert(self.cx)  # AFP / Kemhan rows that must never move
        self.other = nsc.unrelated_digest(self.cx)
        _, self.sha = self.collect()
        self.p = self.packet(self.sha)

    def tearDown(self):
        self.assertEqual(self.other, nsc.unrelated_digest(self.cx))

    def admit(self, packet=None, sealed=None, pol=RESOLVED):
        packet = packet or self.p
        return nsc.admit(self.cx, packet, policy=pol, as_of_utc=NOW,
                         sealed=decision(packet) if sealed is None else sealed, secret=KEY)

    def test_sealed_exact_version_admits_then_replays_unchanged(self):
        self.assertEqual(self.admit()["new_official_links"], 2)
        self.assertEqual(self.admit()["unchanged_official_links"], 2)
        rows = self.cx.execute("SELECT desk, official_issuer, official_publisher, release_scope FROM "
                               + base.TABLE + " WHERE source_family=?", (nsc.FAMILY,)).fetchall()
        self.assertEqual(set(rows), {("philippines", None, "ph_nsc", "official_link_only")})

    def test_later_private_commit_of_same_statements_is_unchanged(self):
        self.admit()
        entry, later = self.collect(run_id="r2")
        self.assertEqual(entry["result"], "ok_all_duplicates")
        self.assertNotEqual(later, self.sha)
        packet = self.packet(later)
        self.assertEqual(self.admit(packet)["unchanged_official_links"], 2)
        commits = {r[0] for r in self.cx.execute(
            "SELECT source_git_commit FROM " + base.TABLE + " WHERE source_family=?", (nsc.FAMILY,))}
        self.assertEqual(commits, {self.sha})

    def test_standing_policy_admits_without_a_seal(self):
        result = nsc.admit(self.cx, self.p, policy=STANDING, as_of_utc=NOW)
        self.assertEqual(result["new_official_links"], 2)
        self.assertFalse(result["original_content_exported"])

    def test_unsigned_tampered_or_out_of_scope_decisions_never_write(self):
        good = decision(self.p)
        bad = [{"review": good["review"]}, dict(copy.deepcopy(good), hmac_sha256="0" * 64)]
        for field, value in (("candidate_sha256", "0" * 64),
                             ("production_release_authorized", False),
                             ("protected_custody_verified", False),
                             ("permitted_fields", ["title_original"]),
                             ("approved_source_identities", ["nsc:1"]),
                             ("reviewed_on", "2026-10-20")):
            bad.append(decision(self.p, **{field: value}))
        extra = copy.deepcopy(good["review"])
        extra["title_original"] = "unapproved"
        bad.append(seal(extra))
        for sealed in bad:
            with self.subTest(sealed=sealed), self.assertRaises(ValueError):
                self.admit(sealed=sealed)
            self.assertEqual(self.count(), 0)

    def test_partial_selection_admits_only_approved_identities(self):
        self.admit(sealed=decision(self.p, approved_source_identities=["nsc:3108"]))
        self.assertEqual([r[0] for r in self.cx.execute(
            "SELECT source_identity FROM " + base.TABLE + " WHERE source_family=?", (nsc.FAMILY,))],
            ["nsc:3108"])

    def test_interrupted_write_rolls_back_and_retry_is_safe(self):
        self.cx.execute("CREATE TRIGGER interrupted BEFORE INSERT ON " + base.TABLE
                        + " WHEN NEW.source_family='%s' AND (SELECT count(*) FROM %s WHERE "
                        "source_family='%s')=1 BEGIN SELECT RAISE(ABORT,'interrupted'); END"
                        % (nsc.FAMILY, base.TABLE, nsc.FAMILY))
        with self.assertRaises(sqlite3.IntegrityError):
            self.admit()
        self.assertEqual(self.count(), 0)
        self.cx.execute("DROP TRIGGER interrupted")
        self.assertEqual(self.admit()["new_official_links"], 2)

    def test_changed_source_version_is_not_overwritten(self):
        self.admit()
        packet = copy.deepcopy(self.p)
        packet["links"][0]["metadata_version_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "previously_released_source_version_changed"):
            self.admit(packet)
        self.assertEqual(self.count(), 2)


class Migration(unittest.TestCase):
    def test_constraints_admit_only_nsc_permalinks_on_the_philippines_desk(self):
        cx = index_db()
        row = dict(source_family=nsc.FAMILY, source_identity="nsc:1", desk="philippines",
                   canonical_official_url="https://nsc.gov.ph/2026/07/08/a-b/",
                   publisher_posted_date="2026-07-08", official_issuer=None,
                   official_publisher="ph_nsc", official_republisher=None,
                   source_git_commit="a" * 40, metadata_version_sha256="b" * 64,
                   first_seen_run="r1", release_scope="official_link_only",
                   release_proof_sha256="c" * 64, released_at_utc=NOW)
        cols = [c for c in row if c in base.COLUMNS]

        def put(**ch):
            r = dict(row, **ch)
            cx.execute("INSERT INTO %s (%s) VALUES (%s)" % (
                base.TABLE, ",".join(cols), ",".join("?" * len(cols))), [r[c] for c in cols])
        for bad in ({"desk": "vietnam"}, {"official_issuer": "ph_nsc"},
                    {"canonical_official_url": "https://evil.example/2026/07/08/a-b/"},
                    {"official_publisher": "ph_afp"}):
            with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                put(**bad)
        put()
        self.assertEqual(cx.execute("SELECT count(*) FROM " + base.TABLE).fetchone()[0], 1)

    def test_requires_0013_and_is_idempotent(self):
        cx = sqlite3.connect(":memory:")
        base.up(cx)
        with self.assertRaisesRegex(ValueError, "0013 must precede"):
            m14.up(cx)
        m13.up(cx)
        from tests.test_regional_official_link_render import insert
        insert(cx)
        before = cx.execute("SELECT * FROM " + base.TABLE + " ORDER BY 1,2").fetchall()
        m14.up(cx)
        m14.up(cx)
        self.assertEqual(before, cx.execute("SELECT * FROM " + base.TABLE + " ORDER BY 1,2").fetchall())
        self.assertTrue(m14.is_already_applied(cx))


class Render(NscCase):
    """The Philippines desk rail reads AFP and NSC under separate checks."""

    def setUp(self):
        super().setUp()
        from tests.test_regional_official_link_render import insert
        insert(self.cx)
        _, sha = self.collect()
        nsc.admit(self.cx, self.packet(sha), policy=STANDING, as_of_utc=NOW)

    def read(self, pol=RESOLVED, desk="philippines"):
        from core.regional_official_link_render import read_live_links
        with mock.patch.object(nsc, "load_policy", return_value=pol):
            return read_live_links(self.cx, desk)

    def test_afp_and_nsc_rows_render_with_their_own_attribution(self):
        rows = self.read()
        self.assertEqual([r["source_identity"] for r in rows],
                         ["afp:1499", "nsc:3108", "nsc:2269"])
        days = [r["publisher_posted_date"] for r in rows]
        self.assertEqual(days, sorted(days, reverse=True))
        afp, *statements = rows
        self.assertEqual((afp["label"], afp["publisher_label"]),
                         ("AFP official source", "Armed Forces of the Philippines"))
        for r in statements:
            self.assertEqual((r["label"], r["publisher_label"]),
                             ("NSC official statement", "National Security Council"))
            self.assertTrue(r["canonical_official_url"].startswith("https://nsc.gov.ph/"))
            self.assertEqual(set(r), {"source_identity", "canonical_official_url",
                                      "publisher_posted_date", "label", "publisher_label"})

    def test_rows_admitted_under_a_hold_never_render(self):
        with self.assertRaisesRegex(ValueError, "nsc_source_use_hold"):
            self.read(pol=CLOSED)

    def test_without_nsc_rows_the_afp_rail_needs_no_nsc_policy(self):
        self.cx.execute("DELETE FROM " + base.TABLE + " WHERE source_family=?", (nsc.FAMILY,))
        with mock.patch.object(nsc, "load_policy", side_effect=AssertionError("read")):
            from core.regional_official_link_render import read_live_links
            rows = read_live_links(self.cx, "philippines")
        self.assertEqual([r["source_identity"] for r in rows], ["afp:1499"])

    def test_permalink_date_drift_holds_the_page(self):
        self.cx.execute("UPDATE " + base.TABLE + " SET publisher_posted_date='2026-07-01' "
                        "WHERE source_identity='nsc:3108'")
        with self.assertRaisesRegex(ValueError, "nsc_reference_not_canonical"):
            self.read()

    def test_attribution_drift_holds_the_page(self):
        # Bypass the CHECK on this in-memory index only to prove the renderer
        # independently refuses a row the schema should never have held.
        self.cx.execute("PRAGMA ignore_check_constraints=1")
        self.cx.execute("UPDATE " + base.TABLE + " SET official_issuer='ph_afp' "
                        "WHERE source_identity='nsc:3108'")
        self.cx.execute("PRAGMA ignore_check_constraints=0")
        with self.assertRaisesRegex(ValueError, "published_reference_missing_authenticity"):
            self.read()

    def test_other_desks_never_see_nsc_rows(self):
        self.assertEqual(self.read(desk="indonesia"), [])

    def test_readback_validates_the_combined_rail(self):
        from scripts.verify_regional_source_index_readback import validate_page
        rows = self.read()
        items = "".join(
            '<li data-regional-official-source-id="%s"><h3><a href="%s" '
            'rel="noopener noreferrer">%s</a></h3><time datetime="%s">%s</time></li>'
            % (r["source_identity"], r["canonical_official_url"], r["label"],
               r["publisher_posted_date"], r["publisher_posted_date"]) for r in rows)
        page = ('<section class="regional-official-live-links" '
                'data-source-scope="official-link-only"><ol>%s</ol></section>' % items)
        self.assertEqual(validate_page(page, rows), 3)
        with self.assertRaisesRegex(ValueError, "count_disagrees"):
            validate_page(page, rows[:1])


if __name__ == "__main__":
    unittest.main()
