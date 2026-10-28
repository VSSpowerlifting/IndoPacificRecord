"""Disposable Git/SQLite tests. Test seals are fictional, never human approvals."""
import copy
import hashlib
import hmac
import json
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core import vietnam_official_link_admission as vn
from core.regional_official_link_render import read_live_links
from migrations.versions import m0010_regional_official_source_links as old
from migrations.versions import m0013_vietnam_regional_official_links as migration
from scripts.verify_regional_source_index_readback import validate_page
from tests import test_vietnam_ministry_remote_review as fixtures

# The regional fragment of desk.html calls the shared record macros, which the
# full template imports at its top; a fragment render imports them the same way.
MACROS = '{% from "_records.html" import explanation_part, explanation_details %}'


def desk_fragment_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "site/preview/templates")),
                       autoescape=select_autoescape(default_for_string=True))

MPS, ENERGY, INDUSTRY = fixtures.MPS, fixtures.ENERGY, fixtures.INDUSTRY

KEY = b"fictional-test-only-owner-key-0000000000"
NOW = "2026-10-18T23:00:00Z"


def sealed(packet):
    review = {
        "schema": vn.DECISION, "candidate_sha256": vn.digest(packet),
        "approved_source_identities": sorted(r["source_identity"] for r in packet["records"]),
        "reviewer": "Fictional test reviewer", "reviewed_on": "2026-10-18",
        "rights_basis": "Fictional metadata-only test authorization",
        "approval_reference": "Fictional offline test; never a real approval",
        "permitted_fields": ["source_identity", "canonical_official_url",
                             "publisher_posted_date", "official_issuer"],
        "original_language_and_source_version_checked": True,
        "production_release_authorized": True,
        "protected_custody_verified": True, "custody_reference": "Fictional custody test only",
    }
    return seal_review(review)


def seal_review(review):
    return {"review": review, "hmac_sha256": hmac.new(
        KEY, vn.DOMAIN + vn._canonical(review), hashlib.sha256).hexdigest()}


def db():
    conn = sqlite3.connect(":memory:")
    old.up(conn)
    migration.up(conn)
    return conn


class VietnamAdmission(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.RemoteReview()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.batch()
        self.fixture = fixture
        self.shas = {s: fixture.commit_state(s) for s in (MPS, ENERGY, INDUSTRY)}
        self.repo = fixture.repos / MPS
        self.packet = vn.prepare(self.repo, self.shas[MPS], MPS)
        self.cx = db()
        self.addCleanup(self.cx.close)
        # Fake transport attestation for a synthetic fixture, not live evidence.
        self.observed = {"state_head_sha": self.shas[MPS], "run_id": self.packet["latest_run"],
                         "logical_date": self.packet["logical_date"]}
        # Fixture run IDs intentionally are not real Actions identities. Keep
        # the separate real API verifier covered by authenticated run tests.
        self.auth = patch.object(vn, "authenticate", side_effect=self.authenticated_fixture)
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def authenticated_fixture(self, packet, api, day):
        vn.need(all(self.observed[k] == packet[v] for k, v in (
            ("state_head_sha", "source_git_commit"), ("run_id", "latest_run"),
            ("logical_date", "logical_date"))), "stale_vietnam_source_or_attempt")
        return self.observed

    def admit(self, decision=None, **kwargs):
        return vn.admit(self.cx, self.repo, self.shas[MPS], MPS,
                        sealed(self.packet) if decision is None else decision,
                        api=object(), secret=KEY, as_of_utc=NOW, **kwargs)

    def count(self):
        return self.cx.execute("SELECT count(*) FROM " + old.TABLE).fetchone()[0]

    def test_real_fixture_capture_replay_yields_held_metadata_without_source_text(self):
        self.assertEqual(len(self.packet["records"]), 2)
        self.assertFalse(self.packet["public_release_authorized"])
        serialized = json.dumps(self.packet)
        for key in ("title_original", "text_original", "translation", "summary"):
            self.assertNotIn('"' + key + '"', serialized)
        self.assertTrue(all(len(r["capture_sha256"]) == 64 for r in self.packet["records"]))
        self.assertTrue(all(r["rss_instant_utc"] for r in self.packet["records"]))

    def test_signed_synthetic_admission_replay_and_independent_query(self):
        self.assertEqual(self.admit()["new_official_links"], 2)
        self.assertEqual(self.admit()["unchanged_official_links"], 2)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.cx.execute("SELECT DISTINCT desk,official_issuer,release_scope FROM "
                                        + old.TABLE).fetchall(), [("vietnam", "vn_mps", "official_link_only")])
        public = read_live_links(self.cx, "vietnam")
        self.assertEqual(len(public), 2)
        # Exercise the shared independent HTML readback with this desk's rows.
        from types import SimpleNamespace
        env = desk_fragment_env()
        source = Path("site/preview/templates/desk.html").read_text()
        start = source.index("{% if desk.slug in ('philippines', 'indonesia', 'vietnam')", source.index("{# Regional official-link index:"))
        end = source.index("{# US: first-party publisher URLs", start)
        rendered = env.from_string(MACROS + source[start:end]).render(
            desk=SimpleNamespace(slug="vietnam"), explained={}, regional_official_links=public)
        self.assertEqual(validate_page(rendered, public), 2)
        self.assertNotIn("Indonesian Ministry", rendered)
        self.assertNotIn("text_original", rendered)

    def test_unsigned_tampered_or_wrong_scope_never_writes(self):
        original = sealed(self.packet)
        cases = [None, {"review": original["review"]}, copy.deepcopy(original)]
        cases[-1]["hmac_sha256"] = "0" * 64
        for field, value in (("candidate_sha256", "0" * 64),
                             ("production_release_authorized", False),
                             ("protected_custody_verified", False),
                             ("permitted_fields", ["text_original"]),
                             ("approved_source_identities", ["mps-vi:9999999999"])):
            decision = copy.deepcopy(original["review"])
            decision[field] = value
            cases.append(seal_review(decision))
        for candidate in cases:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                # None must remain a missing receipt, unlike the test helper default.
                vn.admit(self.cx, self.repo, self.shas[MPS], MPS, candidate,
                         api=object(), secret=KEY, as_of_utc=NOW)
            self.assertEqual(self.count(), 0)

    def test_unapproved_field_in_signed_decision_is_rejected(self):
        review = sealed(self.packet)["review"]
        review["title_original"] = "Unapproved field"
        with self.assertRaisesRegex(ValueError, "scope_invalid"):
            self.admit(seal_review(review))

    def test_stale_source_or_wrong_attempt_fails_before_database_write(self):
        for field in self.observed:
            original = self.observed[field]
            self.observed[field] = "stale"
            with self.assertRaisesRegex(ValueError, "stale_vietnam"):
                self.admit()
            self.assertEqual(self.count(), 0)
            self.observed[field] = original

    def test_each_moit_family_remains_held_even_with_synthetic_signature(self):
        for slug in (ENERGY, INDUSTRY):
            repo = self.fixture.repos / slug
            packet = vn.prepare(repo, self.shas[slug], slug)
            self.assertIn("moit_", packet["source_hold"])
            with self.assertRaisesRegex(ValueError, "written_consent"):
                vn.admit(self.cx, repo, self.shas[slug], slug, sealed(packet),
                         api=object(), secret=KEY, as_of_utc=NOW)
            self.assertEqual(self.count(), 0)

    def test_interrupted_batch_rolls_back_and_retry_is_safe(self):
        self.cx.execute("CREATE TRIGGER interrupted BEFORE INSERT ON " + old.TABLE
                        + " WHEN (SELECT count(*) FROM " + old.TABLE
                        + ")=1 BEGIN SELECT RAISE(ABORT,'interrupted'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.admit()
        self.assertEqual(self.count(), 0)
        self.cx.execute("DROP TRIGGER interrupted")
        self.assertEqual(self.admit()["new_official_links"], 2)

    def test_changed_version_is_not_silently_overwritten(self):
        self.admit()
        self.cx.execute("UPDATE " + old.TABLE + " SET metadata_version_sha256=?", ("f" * 64,))
        with self.assertRaisesRegex(ValueError, "previously_released_source_version_changed"):
            self.admit()
        self.assertEqual(self.count(), 2)

    def test_migration_is_idempotent_and_preserves_other_desks(self):
        from tests.test_regional_official_link_render import insert
        insert(self.cx)
        before = self.cx.execute("SELECT * FROM " + old.TABLE).fetchall()
        migration.up(self.cx)
        self.assertEqual(before, self.cx.execute("SELECT * FROM " + old.TABLE).fetchall())
        self.assertTrue(migration.is_already_applied(self.cx))
        with self.assertRaises(sqlite3.IntegrityError):
            self.cx.execute("UPDATE " + old.TABLE + " SET desk='vietnam'")

    def test_forced_moit_database_row_is_refused_at_render_boundary(self):
        self.admit()
        self.cx.execute("UPDATE " + old.TABLE + " SET source_family=?,source_identity=?,"
                        "canonical_official_url=?,official_issuer='vn_moit',official_publisher='vn_moit' "
                        "WHERE source_identity=?", (ENERGY, "moit-energy-vi:/tin-tuc/test.html",
                        "https://moit.gov.vn/tin-tuc/test.html", self.packet["records"][0]["source_identity"]))
        with self.assertRaisesRegex(ValueError, "rights_hold"):
            read_live_links(self.cx, "vietnam")


class AuthenticatedVietnamAttempts(unittest.TestCase):
    def test_original_attempt_and_collector_are_authenticated_independently(self):
        from tests.test_vietnam_run_state_attestation import FakeGitHub, OTHER_HEAD, RUN, PREFIX
        api = FakeGitHub(moit_anomaly=False)
        packet = {
            "source_family": MPS, "source_git_commit": format(1, "040x"),
            "latest_run": RUN, "logical_date": "2026-10-10",
            "records": [{"version_first_seen_run": RUN, "collector_commit": OTHER_HEAD,
                         "collection_target_source": "schedule-slot"}],
        }
        self.assertEqual(vn.authenticate(packet, api, date(2026, 10, 10))["run_id"], RUN)
        packet["records"][0]["collector_commit"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "attempt_mismatch"):
            vn.authenticate(packet, api, date(2026, 10, 10))
        packet["records"][0]["collector_commit"] = OTHER_HEAD
        packet["records"][0]["version_first_seen_run"] = "38088742605-2"
        api.routes[PREFIX + "/actions/runs/38088742605/attempts/2"] = copy.deepcopy(
            api.routes[PREFIX + "/actions/runs/38088742605/attempts/1"])
        with self.assertRaisesRegex(ValueError, "attempt_mismatch"):
            vn.authenticate(packet, api, date(2026, 10, 10))


if __name__ == "__main__":
    unittest.main()
