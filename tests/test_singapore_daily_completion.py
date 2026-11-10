"""Singapore MINDEF in the shared Daily lane: synthetic offline contracts only.

No MINDEF text, media or capture is used or committed. Bodies are synthetic
English placeholders, custody is a throw-away git repository, and the model is
a fake returning a fixed reading. Nothing here spends money or touches a
production database.
"""
import hashlib
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import mindef_public_boundary as boundary
from core import singapore_mindef_links as links
from core.daily_sources import SOURCES, _sg_known_hold, _sg_output_check
from migrations.versions import m0021_dapa_daily_machine_parent as m21
from migrations.versions import m0022_singapore_mindef_source_records as m22
from processing import daily_intake as d
from processing.screening import SINGAPORE_MINDEF_DAILY_PROFILE, profile_for_desk, profile_for_source
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "sg_mindef_releases"
IDENT = "synthetic-release-one"
URL = links.URL_PREFIX + IDENT + "/"
TITLE = "Synthetic MINDEF fixture title"
FIRST = "MINDEF announced a routine bilateral meeting between two defence officials."
SECOND = "The release describes the agenda for a planned working-level discussion."
BODY = FIRST + "\n\n" + SECOND
DAY = "2026-10-28"
RUN = "77-1"
REMOTE = "https://github.com/" + d.PRIVATE_REPO


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def policy(enabled=True):
    p = d.load_policy()
    if enabled:
        p["sources"][FAMILY].update(private_model_processing=True, public_machine_explanation=True,
                                    unattended_release=True, owner_decision="synthetic test policy only")
    return p


def reading(**extra):
    one = "MINDEF says it held a routine bilateral meeting between two defence officials."
    two = "MINDEF describes the agenda for a planned working-level discussion."
    r = dict(passed_relevance=True, requires_translation=False, summary_english=one + " " + two,
             facts=[dict(sentence=one, evidence=FIRST), dict(sentence=two, evidence=SECOND)],
             categories=["military_diplomacy"], is_significant=False, significance_reasoning=None,
             model_id="synthetic-offline-rehearsal",
             prompt_version="sg-relevance-v2+sg-analysis-v2")
    r.update(extra)
    return r


def analyzer(reply=None):
    a = Mock()
    a.analyze_record.return_value = reading() if reply is None else reply
    a.usage.rows.return_value = []
    return a


def build_custody(root, rows=None, *, schema_current=True, remote=REMOTE):
    """A synthetic private custody checkout; returns (repo path, pinned commit)."""
    rows = rows if rows is not None else [(IDENT, TITLE, BODY, DAY)]
    repo = Path(root) / "custody"
    (repo / "state").mkdir(parents=True)
    extra = ", source_identity TEXT, metadata_json TEXT" if schema_current else ""
    with sqlite3.connect(str(repo / "state/shadow.db")) as conn:
        conn.execute("CREATE TABLE shadow_records (url TEXT PRIMARY KEY, source_slug TEXT,"
                     " title_original TEXT, text_original TEXT, published_date TEXT,"
                     " language_tag TEXT, publication_kind TEXT, content_sha256 TEXT,"
                     " capture_sha256 TEXT, retrieved_at TEXT, first_seen_run TEXT" + extra + ")")
        for ident, title, body, day in rows:
            cols = [links.canonical_url(ident), FAMILY, title, body, day, "en", "release",
                    sha(body), sha("capture:" + ident), "2026-11-01T00:00:00Z", RUN]
            names = ("url,source_slug,title_original,text_original,published_date,language_tag,"
                     "publication_kind,content_sha256,capture_sha256,retrieved_at,first_seen_run")
            if schema_current:
                names += ",source_identity,metadata_json"
                cols += [ident, "{}"]
            conn.execute("INSERT INTO shadow_records (%s) VALUES (%s)"
                         % (names, ",".join("?" * len(cols))), cols)
    conn.close()
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["checkout", "-q", "-b", "archive/singapore-mindef-daily"], check=True)
    subprocess.run(git + ["add", "state/shadow.db"], check=True)
    subprocess.run(git + ["commit", "-qm", "synthetic"], check=True)
    subprocess.run(git + ["remote", "add", "origin", remote], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    return repo, head


class SingaporeDefinition(unittest.TestCase):
    def test_family_is_in_the_shared_lane_but_not_activated(self):
        s = SOURCES[FAMILY]
        self.assertEqual((s.desk_id, s.label, s.custody_ref, s.language),
                         ("singapore", "MINDEF", "archive/singapore-mindef-daily", "en"))
        self.assertFalse(s.desk_registered)
        self.assertEqual(s.prompt_versions, ("sg-relevance-v2+sg-analysis-v2",))
        p = d.load_policy()["sources"][FAMILY]
        for key in ("private_model_processing", "public_machine_explanation", "unattended_release"):
            self.assertFalse(p[key], key)
        self.assertEqual(sorted(p["excluded_source_identities"]), sorted(links.HELD_IDENTITIES))

    def test_held_identities_have_one_value_everywhere(self):
        from scraper.sources.sg_mindef import HELD_RELEASE_SLUGS
        expected = tuple(sorted(HELD_RELEASE_SLUGS))
        for held in (links.HELD_IDENTITIES, boundary.HELD_IDENTITIES, m22.HELD_IDENTITIES):
            self.assertEqual(tuple(sorted(held)), expected)

    def test_daily_profile_is_its_own_and_legacy_desk_profile_is_untouched(self):
        self.assertIs(profile_for_source(FAMILY), SINGAPORE_MINDEF_DAILY_PROFILE)
        self.assertIsNot(SINGAPORE_MINDEF_DAILY_PROFILE, profile_for_desk("singapore"))
        self.assertFalse(SINGAPORE_MINDEF_DAILY_PROFILE.translates)
        self.assertFalse(SINGAPORE_MINDEF_DAILY_PROFILE.daily_queue)
        self.assertFalse(SINGAPORE_MINDEF_DAILY_PROFILE.keyword_prefilter)
        self.assertEqual(d.allowed_prompt_versions(FAMILY), ("sg-relevance-v2+sg-analysis-v2",))

    def test_output_check_requires_mindef_attribution_and_no_flag(self):
        self.assertIsNone(_sg_output_check({"model_flagged": False, "summary": "MINDEF says x."}))
        for out in ({"model_flagged": True, "summary": "MINDEF says x."},
                    {"model_flagged": False, "summary": "It says x."},
                    {"model_flagged": False, "summary": "MINDEFS says x."}):
            self.assertEqual(_sg_output_check(out), "daily_singapore_flag_or_attribution_held")

    def test_known_hold_covers_the_two_excluded_speeches_only(self):
        for ident in links.HELD_IDENTITIES:
            self.assertTrue(_sg_known_hold({"source_identity": ident}))
        self.assertFalse(_sg_known_hold({"source_identity": IDENT}))


class SingaporeCustody(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def test_verified_source_binds_identity_hashes_and_never_persists_prose(self):
        repo, head = build_custody(self.tmp)
        (rec,) = d.verified_source(repo, head, FAMILY)
        self.assertEqual((rec["source_identity"], rec["canonical_official_url"],
                          rec["publisher_posted_date"], rec["source_git_commit"]),
                         (IDENT, URL, DAY, head))
        self.assertEqual((rec["content_sha256"], rec["capture_sha256"]),
                         (sha(BODY), sha("capture:" + IDENT)))
        self.assertEqual((rec["title"], rec["body"]), (TITLE, BODY))
        self.assertEqual(links.version_hash({**rec, "title_sha256": sha(TITLE)}),
                         rec["metadata_version_sha256"])

    def test_wrong_remote_or_family_branch_is_refused(self):
        repo, head = build_custody(self.tmp, remote="https://github.com/example/other")
        with self.assertRaisesRegex(d.IntakeHold, "daily_custody_mismatch"):
            d.verified_source(repo, head, FAMILY)

    def test_original_text_that_disagrees_with_its_hash_is_refused(self):
        repo, head = build_custody(self.tmp)
        db = repo / "state/shadow.db"
        with sqlite3.connect(str(db)) as conn:
            conn.execute("UPDATE shadow_records SET text_original=text_original||' tampered'")
        conn.close()
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(git + ["commit", "-qam", "tamper"], check=True)
        head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                              text=True).stdout.strip()
        with self.assertRaisesRegex(d.IntakeHold, "daily_source_version_mismatch"):
            d.verified_source(repo, head, FAMILY)

    def test_legacy_custody_is_refused_by_name_at_link_admission_and_processing(self):
        repo, head = build_custody(self.tmp, schema_current=False)
        with self.assertRaisesRegex(links.LinkRefused, "singapore_link_custody_schema_legacy"):
            links.links_from_custody(repo, head)
        with self.assertRaises(Exception):
            d.verified_source(repo, head, FAMILY)

    def test_registered_custody_ref_is_the_new_current_schema_ref(self):
        from core.daily_sources import source_for
        self.assertEqual(source_for(FAMILY).custody_ref, "archive/singapore-mindef-daily")
        self.assertEqual(source_for(FAMILY).key_env, "DAILY_SG_MINDEF_RELEASES_KEY")

    def test_legacy_custody_schema_is_refused_by_the_collector_guard(self):
        from scripts import shadow_collect
        legacy, _ = build_custody(self.tmp, schema_current=False)
        with self.assertRaises(SystemExit) as ctx:
            shadow_collect.assert_current_schema(legacy / "state/shadow.db")
        self.assertIn("legacy Singapore custody", str(ctx.exception))
        self.assertIn("archive/singapore-mindef-daily", str(ctx.exception))
        current = Path(self.tmp) / "current"
        current.mkdir()
        modern, _ = build_custody(current)
        shadow_collect.assert_current_schema(modern / "state/shadow.db")  # accepted
        shadow_collect.assert_current_schema(Path(self.tmp) / "absent.db")  # first run


class SingaporeAdmission(unittest.TestCase):
    """Source → analysis → authenticated admission → reader, on a scratch DB."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.db = Path(self.tmp) / "scratch.db"
        build_legacy_db(self.db)
        migrate(self.db)
        self.repo, self.head = build_custody(self.tmp)
        self.p = policy()
        self.key = "synthetic-singapore-key-" * 2
        conn = self.connect()
        self.records = links.with_title_hash(d.verified_source(self.repo, self.head, FAMILY))
        with conn:
            self.parent = links.admit_links(conn, self.records, now="2026-11-07T00:00:00Z")
        self.assertEqual(self.parent["admitted"], [IDENT])
        bound = d.bind_admitted_metadata(self.records, conn, source_repo=self.repo)
        self.assertEqual([r["source_identity"] for r in bound], [IDENT])
        self.state, _ = d.process(bound, {}, family=FAMILY, policy=self.p, analyzer_factory=analyzer)
        self.assertEqual(self.state[FAMILY + ":" + IDENT]["status"], "complete")
        self.envelope = d.sign_outputs(self.state, family=FAMILY, policy=self.p, key=self.key)
        for k in ("title", "body"):
            self.assertNotIn(k, self.envelope["packet"]["records"][0])

    def connect(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        self.addCleanup(conn.close)
        return conn

    def admit(self, conn):
        return d.admit(conn, self.envelope, family=FAMILY, policy=self.p, key=self.key)

    def reader(self, policy_=None):
        from core import daily_machine_records as reader
        with patch.object(reader, "load_policy", return_value=policy_ or self.p):
            return reader.load(self.db)

    def raw_insert(self, conn, identity=IDENT):
        row = dict(zip(d.PUBLIC_FIELDS, [FAMILY, identity] + ["a" * 64] * 3
                       + ["e" * 40, "1-1", "MINDEF s.", "[]", 0, None, "m", "v", "q" * 64, "p" * 64]))
        cols = ["categories_json" if k == "categories" else k for k in row]
        conn.execute("INSERT INTO daily_machine_records (" + ",".join(cols) + ") VALUES ("
                     + ",".join("?" * len(cols)) + ")", list(row.values()))

    def test_m0022_applied_and_trigger_requires_the_singapore_parent(self):
        conn = self.connect()
        self.assertTrue(m21.is_already_applied(conn))
        self.assertTrue(m22.is_already_applied(conn))
        with conn:
            conn.execute("DELETE FROM singapore_mindef_source_records")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.raw_insert(conn)
        self.assertEqual(self.admit(conn), {"admitted": 0, "holds": ["daily_admitted_source_version_mismatch"]})

    FROZEN = ("CREATE TRIGGER {name} BEFORE {event} ON daily_machine_records WHEN "
              "NEW.source_family='sg_mindef_releases' AND NEW.publication_state='released' "
              "AND NOT (0) BEGIN SELECT RAISE(ABORT,'MINDEF machine publication held'); END")

    def test_m0022_reissues_boundary_triggers_frozen_before_the_parent_existed(self):
        # stage_mindef_public_projection froze the permitted-row predicate as 0 on staged
        # databases; without re-issuing, that blanket hold would silently defeat admission.
        conn = self.connect()
        for name, event in m22.BOUNDARY_TRIGGERS:
            conn.execute("DROP TRIGGER IF EXISTS " + name)
            conn.execute(self.FROZEN.format(name=name, event=event))
        conn.commit()
        self.assertFalse(m22.is_already_applied(conn))
        # The migration gate refuses admission rather than letting the frozen hold fire.
        with self.assertRaises(d.IntakeHold) as held:
            self.admit(conn)
        self.assertEqual(str(held.exception), "daily_migration_required")
        with conn:
            m22.up(conn)
        self.assertTrue(m22.is_already_applied(conn))
        self.assertEqual(self.admit(conn), {"admitted": 1, "holds": []})
        # The reissued trigger is still a real gate: a flagged or unattributed row is refused.
        with self.assertRaisesRegex(sqlite3.IntegrityError, "MINDEF machine publication held"):
            with conn:
                conn.execute("UPDATE daily_machine_records SET model_flagged=1 "
                             "WHERE source_identity=?", (IDENT,))

    def test_migration_predicate_equals_the_boundary_predicate(self):
        conn = self.connect()
        self.assertEqual(m22.permitted_machine_predicate("NEW"), boundary.permitted_machine_sql(conn))
        self.assertEqual(m22.permitted_machine_predicate("r"), boundary.permitted_machine_sql(conn, "r"))

    def test_m0022_leaves_a_database_without_boundary_triggers_untouched(self):
        conn = self.connect()
        for name, _ in m22.BOUNDARY_TRIGGERS:
            conn.execute("DROP TRIGGER IF EXISTS " + name)
        self.assertTrue(m22.is_already_applied(conn))
        m22.up(conn)
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        self.assertFalse(names & {n for n, _ in m22.BOUNDARY_TRIGGERS})

    def test_m0022_is_idempotent_and_preserves_existing_rows(self):
        conn = self.connect()
        def snapshot():
            return (sorted(conn.execute("SELECT name, sql FROM sqlite_master "
                                        "WHERE name LIKE '%mindef%' OR name LIKE 'daily_machine%'")),
                    sorted(conn.execute("SELECT * FROM singapore_mindef_source_records")),
                    sorted(conn.execute("SELECT * FROM daily_machine_records")))
        before = snapshot()
        for _ in range(2):
            with conn:
                m22.up(conn)
        self.assertEqual(before, snapshot())

    def test_admission_reaches_the_reader_with_only_permitted_components(self):
        conn = self.connect()
        self.assertEqual(self.admit(conn)["admitted"], 1)
        (row,) = self.reader()
        self.assertEqual((row["url"], row["source_label"], row["publisher"], row["desk_id"],
                          row["published_date"], row["machine_only"]),
                         (URL, "MINDEF", "Ministry of Defence, Singapore", "singapore", DAY, True))
        self.assertIn("MINDEF", row["summary"])
        # Original publisher text and title never reach a public column.
        stored = " ".join(str(v) for v in conn.execute(
            "SELECT * FROM daily_machine_records").fetchone() if v is not None)
        self.assertNotIn(TITLE, stored)
        self.assertNotIn(FIRST, stored)
        self.assertNotIn(SECOND, stored)
        # The boundary predicate accepts exactly this row.
        self.assertEqual(conn.execute(
            "SELECT count(*) FROM daily_machine_records NEW WHERE "
            + boundary.permitted_machine_sql(conn, "NEW")).fetchone()[0], 1)

    def test_admission_is_idempotent(self):
        conn = self.connect()
        self.assertEqual(self.admit(conn)["admitted"], 1)
        again = self.admit(conn)
        self.assertEqual(again["admitted"], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM daily_machine_records").fetchone()[0], 1)
        with conn:
            summary = links.admit_links(conn, self.records)
        self.assertEqual((summary["admitted"], summary["unchanged"], summary["held"]), ([], [IDENT], []))

    def test_policy_off_means_nothing_is_public(self):
        conn = self.connect()
        self.admit(conn)
        self.assertEqual(self.reader(policy(False)), [])

    def test_excluded_identities_are_never_public(self):
        conn = self.connect()
        self.admit(conn)
        held = policy()
        held["sources"][FAMILY]["excluded_source_identities"] = [IDENT]
        self.assertEqual(self.reader(held), [])

    def test_drifted_original_withdraws_the_record_from_readers(self):
        conn = self.connect()
        self.admit(conn)
        self.assertEqual(len(self.reader()), 1)
        drift = [{**r, "content_sha256": sha("a changed original"),
                  "metadata_version_sha256": links.version_hash(
                      {**r, "content_sha256": sha("a changed original")})} for r in self.records]
        with conn:
            summary = links.admit_links(conn, drift)
        self.assertEqual(summary["held"], [IDENT])
        self.assertEqual(self.reader(), [])
        self.assertEqual(conn.execute(
            "SELECT public_scope FROM singapore_mindef_source_records").fetchone()[0], "held")

    def test_held_speech_identities_cannot_enter_the_parent_table(self):
        conn = self.connect()
        for ident in links.HELD_IDENTITIES:
            bad = links.with_title_hash([dict(self.records[0], source_identity=ident,
                                              canonical_official_url=links.canonical_url(ident))])
            bad[0]["metadata_version_sha256"] = links.version_hash(bad[0])
            with conn:
                summary = links.admit_links(conn, bad)
            self.assertEqual(summary["refused"], {ident: "singapore_link_identity_held"})
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        "INSERT INTO singapore_mindef_source_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (ident, links.canonical_url(ident), DAY, "e" * 40, "a" * 64, "b" * 64,
                         "c" * 64, "d" * 64, RUN, "sg_mindef", "official_link_only", "x"))

    def test_link_refusals_write_nothing(self):
        conn = self.connect()
        base = self.records[0]
        cases = {
            "singapore_link_url_not_canonical": dict(canonical_official_url="https://example.com/x/"),
            "singapore_link_identity_invalid": dict(source_identity="Bad Identity"),
            "singapore_link_date_invalid": dict(publisher_posted_date="28-10-2026"),
            "singapore_link_content_sha256_invalid": dict(content_sha256="nothex"),
            "singapore_link_commit_invalid": dict(source_git_commit="short"),
            "singapore_link_version_mismatch": dict(metadata_version_sha256="0" * 64),
        }
        for reason, change in cases.items():
            rec = {**base, **change}
            with conn:
                summary = links.admit_links(conn, [rec])
            self.assertEqual(list(summary["refused"].values()), [reason], reason)
        self.assertEqual(conn.execute(
            "SELECT count(*) FROM singapore_mindef_source_records WHERE source_identity!=?",
            (IDENT,)).fetchone()[0], 0)

    def test_missing_migration_fails_closed(self):
        bare = sqlite3.connect(":memory:")
        self.addCleanup(bare.close)
        with self.assertRaisesRegex(links.LinkRefused, "singapore_link_migration_required"):
            links.admit_links(bare, self.records)
        self.assertEqual(boundary.permitted_machine_sql(bare, "NEW"), "0")
        conn = self.connect()
        with patch.object(m22, "is_already_applied", return_value=False):
            with self.assertRaisesRegex(d.IntakeHold, "daily_migration_required"):
                self.admit(conn)

    def test_original_text_in_a_reading_is_refused_before_signing(self):
        long_copy = FIRST + " " + SECOND
        leaked = reading(summary_english=long_copy, facts=[
            dict(sentence=FIRST, evidence=FIRST), dict(sentence=SECOND, evidence=SECOND)])
        bound = d.bind_admitted_metadata(self.records, self.connect(), source_repo=self.repo)
        state, _ = d.process(bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(leaked))
        entry = state[FAMILY + ":" + IDENT]
        self.assertNotEqual(entry["status"], "complete")

    def test_unattributed_or_flagged_output_is_held(self):
        bound = d.bind_admitted_metadata(self.records, self.connect(), source_repo=self.repo)
        unattributed = "It held a routine bilateral meeting between two defence officials."
        bad = reading(summary_english=unattributed + " " + reading()["facts"][1]["sentence"],
                      facts=[dict(sentence=unattributed, evidence=FIRST), reading()["facts"][1]])
        state, _ = d.process(bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(bad))
        self.assertEqual(state[FAMILY + ":" + IDENT]["quality_hold"], "daily_attribution_missing")
        flagged = reading(is_significant=True, significance_reasoning="MINDEF note.",
                          flag_evidence=SECOND)
        state, _ = d.process(bound, {}, family=FAMILY, policy=self.p,
                             analyzer_factory=lambda: analyzer(flagged))
        # A model flag is an editorial matter: it may complete privately but is
        # never admitted as an unattended machine record.
        envelope = d.sign_outputs(state, family=FAMILY, policy=self.p, key=self.key)
        conn = self.connect()
        result = d.admit(conn, envelope, family=FAMILY, policy=self.p, key=self.key)
        self.assertEqual(result, {"admitted": 0, "holds": ["daily_singapore_flag_or_attribution_held"]})
        self.assertEqual(conn.execute("SELECT count(*) FROM daily_machine_records").fetchone()[0], 0)

    def test_committed_policy_holds_before_any_analyzer(self):
        factory = Mock()
        bound = d.bind_admitted_metadata(self.records, self.connect(), source_repo=self.repo)
        state, _ = d.process(bound, {}, family=FAMILY, policy=policy(False), analyzer_factory=factory)
        self.assertEqual(state[FAMILY + ":" + IDENT]["reason"], "model_rights_held")
        factory.assert_not_called()

    def test_committed_singapore_policy_is_one_record_and_capped_at_035(self):
        import json
        committed = json.loads(Path("config/philippines_daily_policy.json").read_text())
        sg = committed["sources"][FAMILY]
        self.assertEqual((sg["max_records_per_run"], sg["max_estimated_cost_usd_per_run"]), (1, 0.35))
        self.assertEqual(sorted(sg["excluded_source_identities"]), sorted(links.HELD_IDENTITIES))
        self.assertFalse(any(sg[k] for k in ("private_model_processing",
                                              "public_machine_explanation", "unattended_release")))
        over = json.loads(json.dumps(committed))
        over["sources"][FAMILY]["max_estimated_cost_usd_per_run"] = 0.36
        tmp = Path(tempfile.mkdtemp()); self.addCleanup(lambda: __import__("shutil").rmtree(tmp, True))
        (tmp / "p.json").write_text(json.dumps(over))
        with self.assertRaises(d.IntakeHold) as held:
            d.load_policy(tmp / "p.json")
        self.assertEqual(str(held.exception), "daily_spend_bound_invalid")

    def test_held_speech_never_reaches_the_model(self):
        factory = Mock()
        rec = dict(self.records[0], source_identity=links.HELD_IDENTITIES[0])
        state, _ = d.process([rec], {}, family=FAMILY, policy=self.p, analyzer_factory=factory)
        self.assertNotEqual(state[FAMILY + ":" + rec["source_identity"]]["status"], "complete")
        factory.assert_not_called()

    def test_historical_rows_survive_the_migration(self):
        """m0022 adds a table and swaps two triggers; it rewrites no existing row."""
        conn = self.connect()
        before = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        m22.up(conn)  # idempotent re-apply
        self.assertEqual(conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], before)


class SingaporeRenderedDelivery(unittest.TestCase):
    """Real build: source -> analysis -> admission -> Record page, Singapore Desk, Archive/search.

    Runs the actual chain on a scratch copy of the tracked database (which carries the staged
    boundary triggers) and renders with the production preview generator. The tracked database
    and all production output are untouched; the release and its model reading are synthetic.
    """

    @classmethod
    def setUpClass(cls):
        import json, shutil, sys
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as gp
        from core import daily_machine_records as reader
        if not Path(gp.TRACKED_DB).exists():
            raise unittest.SkipTest("tracked database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="sg-delivery-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.tracked_before = hashlib.sha256(Path(gp.TRACKED_DB).read_bytes()).hexdigest()
        cls.tracked = Path(gp.TRACKED_DB)
        db = cls.tmp / "scratch.db"
        shutil.copy(gp.TRACKED_DB, db)
        migrate(db)
        repo, _head = build_custody(str(cls.tmp))
        p = policy()
        key = "synthetic-singapore-key-" * 2
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys=ON")
        records = links.with_title_hash(d.verified_source(repo, _head, FAMILY))
        with conn:
            links.admit_links(conn, records, now="2026-11-09T00:00:00Z")
        bound = d.bind_admitted_metadata(records, conn, source_repo=repo)
        state, _ = d.process(bound, {}, family=FAMILY, policy=p, analyzer_factory=analyzer)
        env = d.sign_outputs(state, family=FAMILY, policy=p, key=key)
        cls.admitted = d.admit(conn, env, family=FAMILY, policy=p, key=key)
        conn.close()
        briefs = cls.tmp / "briefs"
        briefs.mkdir()
        with patch.object(reader, "load_policy", return_value=p):
            cls.rows = [r for r in reader.load(db) if r["desk_id"] == "singapore"]
            cls.out = cls.tmp / "build"
            gp.build(cls.out, "Singapore delivery test", db, snapshot=gp.snapshot_from_corpus(db),
                     briefs_dir=briefs, dossiers_dir=cls.tmp / "no-dossiers")
        cls.json = json
        cls.record_path = cls.rows[0]["record_path"] if cls.rows else None

    def page(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_admitted_one_record_and_tracked_database_untouched(self):
        self.assertEqual(self.admitted, {"admitted": 1, "holds": []})
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(hashlib.sha256(self.tracked.read_bytes()).hexdigest(), self.tracked_before)

    def test_record_page_shows_permitted_components_and_the_right_desk(self):
        page = self.page(self.record_path)
        self.assertIn("Singapore Desk", page)
        self.assertNotIn("Philippines Desk", page)
        self.assertIn("../singapore.html", page)
        self.assertIn(URL, page)
        for sentence in (r["sentence"] for r in reading()["facts"]):
            self.assertIn(sentence, page)
        self.assertIn(self.rows[0]["content_sha256"], page)
        self.assertIn(self.rows[0]["capture_sha256"], page)
        self.assertIn("Machine-generated from the English source", page)

    def test_singapore_desk_lists_the_record_with_current_copy(self):
        desk = self.page("singapore.html")
        self.assertIn("data-singapore-machine-explanations", desk)
        self.assertIn(self.record_path, desk)
        self.assertIn("independently written, source-grounded English readings", desk)
        self.assertNotIn("none has been admitted yet", desk)
        self.assertIn("MINDEF titles, article text and media are not republished", desk)

    def test_archive_and_search_index_carry_the_record(self):
        self.assertIn('value="machine_explanation"', self.page("archive.html"))
        index = self.json.loads(self.page("archive-research-index.json"))
        hits = [r for r in self.json.dumps(index).split("},") if self.record_path in r]
        self.assertTrue(hits)
        self.assertIn("singapore", self.json.dumps(index))

    def test_no_original_title_or_body_text_reaches_any_public_file(self):
        needles = (TITLE, FIRST, SECOND)
        leaks = []
        for path in self.out.rglob("*"):
            if path.is_file() and path.suffix in {".html", ".json", ".js", ".xml", ".txt", ".csv"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                if any(n in text for n in needles):
                    leaks.append(str(path.relative_to(self.out)))
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
