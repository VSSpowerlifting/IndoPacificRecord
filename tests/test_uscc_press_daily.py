"""USCC press releases in the shared Daily lane: contracts and an opt-in authentic replay.

SYNTHETIC by default: every release page here is invented expression in the
Commission's page structure, custody is a throw-away git repository with the
private repository's origin URL, and the model is a TEST DOUBLE (a Mock
analyzer, model id ``synthetic-offline-rehearsal``) whose sentences are fixed
content-free attributions and whose evidence spans are selected mechanically
from the passages the lane actually sent it. Nothing spends money, contacts the
publisher or GitHub, or touches the tracked database.

AUTHENTIC (``AuthenticReplay``, skipped unless ``IPR_USCC_PRIVATE_EVIDENCE``
names a private custody directory): replays the preserved 2026-11-03 captures
through the same lifecycle and the production renderer, with the same labelled
test double for processing. It asserts and prints hashes, codes and counts
only; no original text leaves the temporary directories it deletes.
"""
import hashlib
import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import uscc_press_links as links
from core import uscc_offline_input as Q
from core.daily_sources import SOURCES, _uscc_known_hold, _uscc_output_check
from migrations.versions import m0024_uscc_press_source_records as m24
from processing import daily_intake as d
from tests.test_migrations import build_legacy_db
from tests.test_reconcile import migrate

ROOT = Path(__file__).resolve().parents[1]
FAMILY = "us_uscc_press_en"
REMOTE = "https://github.com/" + d.PRIVATE_REPO
BRANCH = "archive/uscc-press"
AGENT = "IndoPacificRecordResearchBot/1.0 (+https://indopacificrecord.org/about.html)"
ROBOTS = b"User-agent: *\nAllow: /\n"
KEY = "synthetic-uscc-press-key-" * 2
MODEL_ID = "synthetic-offline-rehearsal"

SLUG_A = "press-release-synthetic-commission-visit"
SLUG_B = "press-release-synthetic-commission-appointment"
DAY_A, DAY_B = "2026-07-20", "2026-07-10"
TITLE = "Invented commission announcement"
N1 = "The invented commission announced a delegation visit to an example city this week."
N2 = "Invented commissioners planned meetings with example officials during the visit."
N3 = "The invented commission named an example member to a synthetic advisory post."
N4 = "That example member will begin the synthetic advisory post next month."
QUOTE = "“Invented quotation sentence attributed to an example chair.”"
BOILER = "Invented institutional boilerplate sentence about the invented commission."
SOCIAL = ('<p><a href="https://x.com/i">X</a><br><a href="https://www.linkedin.com/i">'
          'LinkedIn</a></p>')
SENTENCES = ("The USCC release describes an institutional activity in its own narrative account.",
             "According to the USCC, the release adds detail about that same institutional activity.")


def ident(slug):
    return "uscc-press:" + slug


def release_page(slug, day, *, title=TITLE, narrative=(N1, N2), body_html=None, footer=""):
    """A synthetic USCC release page in the publisher's structure (no USCC text)."""
    url = links.canonical_url(ident(slug))
    body = body_html if body_html is not None else (
        "".join("<p>" + html.escape(p, quote=False) + "</p>" for p in narrative)
        + "<p>" + QUOTE + "</p><p>" + BOILER + "</p>" + SOCIAL)
    mdy = day[5:7] + "/" + day[8:10] + "/" + day[:4]
    return ('<html><head><link rel="canonical" href="' + url + '"></head><body>'
            '<article class="press-release full" about="/press-releases/' + slug + '">'
            '<div class="field--name-field-date"><time datetime="' + day + 'T12:00:00Z">'
            + mdy + '</time></div><div class="field--name-body"><h2>' + html.escape(title)
            + '</h2>' + body + '</div></article>' + footer + '</body></html>').encode()


def receipt(raw, url, robots=ROBOTS, when="2026-11-14T00:00:00Z", agent=AGENT):
    return {"capture_sha256": hashlib.sha256(raw).hexdigest(), "payload_bytes": len(raw),
            "requested_url": url, "final_url": url, "http_status": 200,
            "content_type": "text/html; charset=utf-8", "retrieved_utc": when,
            "user_agent": agent, "robots_sha256": hashlib.sha256(robots).hexdigest()}


def init_custody(root, *, remote=REMOTE, branch=BRANCH):
    repo = Path(root) / "custody"
    (repo / "state").mkdir(parents=True)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["checkout", "-q", "-b", branch], check=True)
    subprocess.run(git + ["remote", "add", "origin", remote], check=True)
    return repo


def commit_custody(repo, releases, *, run_id="uscc-1", robots=ROBOTS, provenance=None):
    """Write (slug or identity, day, raw[, access]) captures into custody; return the pin."""
    rows, captures = [], {}
    for item in releases:
        key, day, raw = item[:3]
        identity = key if key.startswith("uscc-press:") else ident(key)
        access = item[3] if len(item) > 3 else receipt(raw, links.canonical_url(identity), robots)
        row, caps = links.custody_row(raw, source_identity=identity, publication_date=day,
                                      access=access, robots_txt=robots, run_id=run_id,
                                      provenance=provenance)
        rows.append(row)
        captures.update(caps)
    links.write_custody(repo / "state", rows, captures)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(git + ["add", "state"], check=True)
    subprocess.run(git + ["commit", "-qm", "custody " + run_id], check=True)
    return subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()


def list_metadata(conn, identity, day):
    """The existing USCC listing-metadata row a parent must match (shape only)."""
    from core.uscc_official_metadata import create_schema, ISSUER, HOST, INDEX
    create_schema(conn)
    conn.execute("INSERT OR IGNORE INTO uscc_official_source_records VALUES (?,?,?,?,?,?,?,?,?)",
                 (identity, links.canonical_url(identity), day, ISSUER, HOST, INDEX,
                  "2026-11-14", "c" * 40, "official_link_only"))


def policy(enabled=True):
    p = d.load_policy()
    p["sources"][FAMILY].update(private_model_processing=enabled,
                                public_machine_explanation=enabled, unattended_release=enabled)
    if enabled:
        p["sources"][FAMILY]["owner_decision"] = "synthetic test policy only"
    return p


def mechanical_reading(title, body, profile):
    """TEST DOUBLE for the model: fixed attributions, evidence selected by position.

    The evidence spans are the first two passages the lane itself built from
    the body it sent; nothing is written from the source by hand.
    """
    from analysis.philippines_prompts import evidence_passages
    spans = [text for _id, text in evidence_passages(body) if 20 <= len(text) <= 500][:2]
    if len(spans) < 2:  # a thin narrative: cite the same passage twice
        spans = (spans * 2)[:2]
    return dict(passed_relevance=True, requires_translation=False,
                summary_english=" ".join(SENTENCES),
                facts=[dict(sentence=s, evidence=e) for s, e in zip(SENTENCES, spans)],
                categories=["commission_activity"], is_significant=False,
                significance_reasoning=None, model_id=MODEL_ID,
                prompt_version=SOURCES[FAMILY].prompt_versions[0])


def analyzer():
    a = Mock()
    a.analyze_record.side_effect = mechanical_reading
    a.usage.rows.return_value = []
    return a


class Lane:
    """The production callers, in order, on a scratch public DB and private handoff.

    Private side: ``scripts/uscc_press_links.py sign`` beside custody, then
    ``processing.daily_runner.private_run``. Public side:
    ``scripts/fetch_daily_machine_outputs.py`` (its private-branch read served
    from the handoff directory), ``scripts/uscc_press_links.py admit``, then
    ``pipeline._daily_admission``, the governed admission the Daily pipeline
    runs for a registered family. Policy and switch values are synthetic.
    """

    def __init__(self, case, db, tmp, p=None):
        self.case, self.db, self.tmp = case, Path(db), Path(tmp)
        self.p = p or policy()
        self.handoff = self.tmp / "handoff"
        self.queue = self.handoff / "queues" / (FAMILY + ".json")
        self.envelopes = self.handoff / "envelopes"
        self.public_in = self.tmp / "public-machine-outputs"
        self.handoff.mkdir(exist_ok=True)
        self.model = analyzer()
        self.factory = Mock(return_value=self.model)
        self.env = {"DAILY_OUTPUT_KEY": KEY, links.KEY_ENV: KEY, "US_USCC_LINKS_ENABLED": "true",
                    "IPR_PRIVATE_DAILY_ENABLED": "true", "IPR_DAILY_INTAKE_DIR": str(self.public_in)}

    def sign_links(self, repo, head):
        from scripts import uscc_press_links as bridge
        with patch.dict(os.environ, self.env), patch("sys.stdout"):
            code = bridge.main(["sign", "--source-checkout", str(repo), "--source-commit", head,
                                "--output", str(self.handoff / links.LINKS_NAME)])
        self.case.assertEqual(code, 0)
        return json.loads((self.handoff / links.LINKS_NAME).read_text())

    def shared_processing(self, repo, head):
        from processing import daily_runner
        with patch.dict(os.environ, self.env), \
                patch.object(daily_runner, "load_policy", return_value=self.p), \
                patch("analysis.analyzer.Analyzer", self.factory), \
                patch.object(d, "bound_private_calls", return_value=None), \
                patch("analysis.usage.build_run_record", return_value=[]):
            daily_runner.private_run(FAMILY + "," + str(repo) + "," + head, public_db=self.db,
                                     state_path=self.queue, out_dir=self.envelopes)
        return (json.loads(self.queue.read_text()),
                json.loads((self.envelopes / (FAMILY + ".json")).read_text()))

    def fetch(self):
        from scripts import fetch_daily_machine_outputs as fetch

        def private_branch(remote_path, path, ref="state/shared-daily"):
            source = self.handoff / remote_path
            if not source.exists():
                return "fetch_failed"
            shutil.copyfile(source, path)
            return "fetched"

        with patch.dict(os.environ, self.env), \
                patch.object(fetch, "load_policy", return_value=self.p), \
                patch.object(fetch, "_fetch", side_effect=private_branch), patch("sys.stdout"):
            return fetch.main()

    def admit_links(self):
        from scripts import uscc_press_links as bridge
        out = []
        with patch.dict(os.environ, self.env), patch("sys.stdout.write", side_effect=out.append):
            code = bridge.main(["admit", "--database", str(self.db), "--envelope",
                                str(self.public_in / links.LINKS_NAME)])
        return code, json.loads("".join(out))

    def public_admission(self):
        import pipeline
        from processing import daily_runner
        with patch.dict(os.environ, self.env), \
                patch.object(d, "load_policy", return_value=self.p), \
                patch.object(daily_runner, "load_policy", return_value=self.p), \
                patch.object(pipeline, "DB_PATH", self.db):
            admission = pipeline._daily_admission(FAMILY)
            self.case.assertIsNone(admission.inactive_reason())
            return admission.admit(1)

    def daily(self, repo, head):
        """Production order: the collector's link-bridge step signs parents, the
        public Daily admits them, the next shared processing run binds to them,
        and the following public Daily admits its signed outputs."""
        self.sign_links(repo, head)
        self.fetch()
        code, receipt = self.admit_links()
        self.case.assertEqual(code, 0, receipt)
        state, envelope = self.shared_processing(repo, head)
        fetched = self.fetch()
        self.case.assertEqual((fetched[FAMILY], fetched[links.LINKS_NAME]), ("fetched", "fetched"))
        return state, envelope, self.public_admission()

    def reader(self):
        from core import daily_machine_records as reader
        with patch.object(reader, "load_policy", return_value=self.p):
            return reader.load(self.db)

    def rows(self):
        with sqlite3.connect(str(self.db)) as conn:
            return [r[0] for r in conn.execute(
                "SELECT source_identity FROM daily_machine_records WHERE source_family=? "
                "ORDER BY source_identity", (FAMILY,))]

    def parent_scope(self, identity):
        with sqlite3.connect(str(self.db)) as conn:
            row = conn.execute("SELECT public_scope FROM " + links.TABLE
                               + " WHERE source_identity=?", (identity,)).fetchone()
        return row and row[0]


def render(db, p, out, title):
    """The production preview generator on a scratch DB (reader policy patched)."""
    sys.path.insert(0, str(ROOT / "site" / "preview"))
    import generate_preview as gp
    from core import daily_machine_records as reader
    briefs = out.parent / (out.name + "-briefs")
    briefs.mkdir()
    with patch.object(reader, "load_policy", return_value=p):
        gp.build(out, title, db, snapshot=gp.snapshot_from_corpus(db), briefs_dir=briefs,
                 dossiers_dir=out.parent / (out.name + "-no-dossiers"))


def public_files(out):
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".json", ".js", ".xml", ".txt", ".csv"}:
            yield path, path.read_text(encoding="utf-8", errors="ignore")


def leaks(needles, blobs):
    return sorted({name for name, text in blobs for n in needles if n and n in text})


class Definition(unittest.TestCase):
    def test_family_is_activated_registered_and_switch_gated(self):
        s = SOURCES[FAMILY]
        self.assertEqual((s.desk_id, s.label, s.custody_ref, s.language, s.identity_max_length),
                         ("us-indopacific", "USCC", BRANCH, "en", links.IDENTITY_MAX))
        self.assertEqual(s.publisher, "U.S.-China Economic and Security Review Commission")
        self.assertEqual((s.key_env, s.public_switch), (links.KEY_ENV, "US_USCC_LINKS_ENABLED"))
        self.assertTrue(s.desk_registered)
        # No declared cadence until the private collector writes the shared
        # ledger schema: the family signs /1 and gets no freshness verdict.
        self.assertIsNone(s.collection_expectation()[0])
        self.assertFalse(s.signs_collection())
        committed = d.load_policy()["sources"][FAMILY]
        # 2026-11-22 founder first activation, within unchanged ceilings.
        for switch in ("private_model_processing", "public_machine_explanation",
                       "unattended_release"):
            self.assertIs(committed[switch], True)
        self.assertIn("2026-11-22 founder", committed["owner_decision"])
        self.assertIn("US_USCC_LINKS_ENABLED rolls back both public halves",
                      committed["owner_decision"])
        self.assertEqual((committed["max_records_per_run"],
                          committed["max_estimated_cost_usd_per_run"],
                          committed["max_input_characters"],
                          committed["excluded_source_identities"]), (1, 0.35, 16000, []))
        import pipeline
        self.assertIn(FAMILY, pipeline._governed_admissions())
        # The committed policy is open; the owner switch alone withholds it.
        with patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true"}):
            os.environ.pop("US_USCC_LINKS_ENABLED", None)
            self.assertEqual(pipeline._daily_admission(FAMILY).inactive_reason(),
                             "owner public switch is off")
            os.environ["US_USCC_LINKS_ENABLED"] = "true"
            self.assertIsNone(pipeline._daily_admission(FAMILY).inactive_reason())
        # A policy with any flag withheld still stops it.
        with patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                     "US_USCC_LINKS_ENABLED": "true"}), \
                patch.object(d, "load_policy", return_value=policy(enabled=False)):
            self.assertEqual(pipeline._daily_admission(FAMILY).inactive_reason(),
                             "source-use policy withholds unattended release")

    def test_profile_is_source_level_and_evidence_bound(self):
        from analysis.analyzer import _evidence_bound, _fact_only
        from processing.screening import US_USCC_DAILY_PROFILE, profile_for_source
        profile = profile_for_source(FAMILY)
        self.assertIs(profile, US_USCC_DAILY_PROFILE)
        self.assertEqual((profile.desk_id, profile.daily_queue, profile.source_language),
                         ("us-indopacific", False, "en"))
        self.assertTrue(_evidence_bound(profile))
        self.assertFalse(_fact_only(profile))
        self.assertEqual((profile.prompt_version + "+" + profile.analysis_prompt_version,),
                         SOURCES[FAMILY].prompt_versions)

    def test_prompts_attribute_the_commission_and_disclaim_policy(self):
        from analysis import uscc_daily_prompts as prompts
        system = prompts.system_prompt()
        self.assertIn("congressional advisory commission", system)
        self.assertIn("never U.S. law or policy", system)
        self.assertIn("quotations, boilerplate, linked reports and attachments were removed", system)
        text = json.dumps(prompts.analysis_messages(TITLE, N1 + "\n\n" + N2))
        self.assertIn("exact abbreviation USCC", text)
        self.assertNotIn("Japan Coast Guard", system + text)
        self.assertNotIn("military_diplomacy", prompts.CATEGORIES)

    def test_output_check_requires_attribution_and_no_flag(self):
        ok = {"model_flagged": False, "summary": "The USCC said a trip took place."}
        self.assertIsNone(_uscc_output_check(ok))
        for bad in ({**ok, "model_flagged": True}, {**ok, "summary": "A trip took place."},
                    {**ok, "summary": "The Commission said a trip took place."}):
            self.assertEqual(_uscc_output_check(bad), "daily_us_uscc_flag_or_attribution_held")

    def test_individually_held_identities_are_mirrored_in_the_schema(self):
        self.assertEqual(set(m24.HELD_IDENTITIES), set(Q.HELD_IDENTITIES))
        for held in Q.HELD_IDENTITIES:
            self.assertTrue(_uscc_known_hold({"source_identity": held, "uscc_hold": None}))

    def test_workflow_and_fetcher_are_off_until_the_owner_switch(self):
        workflow = (ROOT / ".github/workflows/daily_update.yml").read_text()
        self.assertIn("vars.US_USCC_LINKS_ENABLED == 'true'", workflow)
        self.assertEqual(workflow.count("secrets.DAILY_US_USCC_PRESS_EN_KEY"), 2)
        self.assertIn("python scripts/uscc_press_links.py admit", workflow)
        from scripts import fetch_daily_machine_outputs as fetch
        with tempfile.TemporaryDirectory() as tmp, patch.object(fetch, "_fetch") as call, \
                patch.dict(os.environ, {"IPR_PRIVATE_DAILY_ENABLED": "true",
                                        "IPR_DAILY_INTAKE_DIR": tmp}):
            os.environ.pop("US_USCC_LINKS_ENABLED", None)
            call.return_value = "fetched"
            result = fetch.main()
            self.assertEqual(result[FAMILY], "public_switch_off")
            self.assertNotIn(links.LINKS_NAME, result)
            os.environ["US_USCC_LINKS_ENABLED"] = "true"
            result = fetch.main()
            # The committed policy is open: the owner switch releases both halves.
            self.assertEqual(result[FAMILY], "fetched")
            self.assertEqual(result[links.LINKS_NAME], "fetched")
            self.assertEqual(call.call_args.args[2], links.LINKS_REF)
            self.assertIn("envelopes/" + FAMILY + ".json",
                          [c.args[0] for c in call.call_args_list])


class Migration(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "scratch.db"
        build_legacy_db(self.db)
        migrate(self.db)
        self.conn = sqlite3.connect(str(self.db))
        self.addCleanup(self.conn.close)

    def parent(self, identity=ident(SLUG_A), **change):
        row = dict(source_identity=identity, canonical_official_url=links.canonical_url(identity),
                   publisher_posted_date=DAY_A, source_git_commit="e" * 40,
                   metadata_version_sha256="a" * 64, content_sha256="b" * 64,
                   capture_sha256="c" * 64, title_sha256="d" * 64,
                   potential_input_sha256="f" * 64, first_seen_run="r",
                   official_issuer=links.ISSUER, public_scope="official_link_only",
                   admitted_at_utc="2026-11-14T00:00:00Z")
        row.update(change)
        self.conn.execute("INSERT INTO " + m24.TABLE + " (" + ",".join(row) + ") VALUES ("
                          + ",".join("?" * len(row)) + ")", list(row.values()))

    def test_applied_idempotent_and_runner_reports_the_family(self):
        self.assertTrue(m24.is_already_applied(self.conn))
        m24.up(self.conn)
        self.assertTrue(m24.is_already_applied(self.conn))
        from migrations import runner
        self.assertIn("0024", runner.applied_versions(self.conn))

    def test_table_admits_only_canonical_eligible_identities(self):
        self.parent()
        for change in ({"source_identity": ident(SLUG_B)},  # URL is not this identity's
                       {"publisher_posted_date": "2024-12-31"},
                       {"official_issuer": "us_department_of_the_treasury"},
                       {"public_scope": "public_text"}):
            with self.subTest(change=change), self.assertRaises(sqlite3.IntegrityError):
                self.parent(identity=ident("press-release-other"), **{
                    "canonical_official_url": links.canonical_url(ident("press-release-other")),
                    **change})
        for held in m24.HELD_IDENTITIES:
            with self.subTest(held=held), self.assertRaises(sqlite3.IntegrityError):
                self.parent(identity=held)

    def test_machine_row_requires_an_official_link_parent(self):
        row = dict(zip(d.PUBLIC_FIELDS, [FAMILY, ident(SLUG_A)] + ["a" * 64] * 3
                       + ["e" * 40, "1-1", "USCC s.", "[]", 0, None, "m", "v", "q" * 64, "p" * 64]))
        cols = ["categories_json" if k == "categories" else k for k in row]
        insert = ("INSERT INTO daily_machine_records (" + ",".join(cols) + ") VALUES ("
                  + ",".join("?" * len(cols)) + ")")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.conn.execute(insert, list(row.values()))
        self.parent(public_scope="held")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "daily_machine_record_parent_missing"):
            self.conn.execute(insert, list(row.values()))
        self.conn.execute("UPDATE " + m24.TABLE + " SET public_scope='official_link_only'")
        self.conn.execute(insert, list(row.values()))


class Custody(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = init_custody(self.tmp)

    def test_eligible_release_sends_only_the_unquoted_narrative(self):
        head = commit_custody(self.repo, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A))])
        (record,) = d.verified_source(self.repo, head, FAMILY)
        self.assertIsNone(record["uscc_hold"])
        self.assertFalse(_uscc_known_hold(record))
        self.assertEqual(record["body"], N1 + "\n\n" + N2)
        for excluded in (QUOTE, BOILER, "LinkedIn"):
            self.assertNotIn(excluded, record["body"])
        self.assertNotIn("_narrative", record)
        self.assertEqual(record["title"], TITLE)
        self.assertRegex(record["potential_input_sha256"], r"^[0-9a-f]{64}$")

    def test_held_releases_carry_a_code_and_no_prose(self):
        linked = ("<p>" + N1 + ' See the <a href="https://www.uscc.gov/research/x">report</a>.</p>'
                  "<p>" + BOILER + "</p>" + SOCIAL)
        quote_only = "<p>" + QUOTE + "</p><p>" + BOILER + "</p>" + SOCIAL
        dalai = "press-release-dalai-lamas-succession-geopolitical-implications-and-policy"
        cases = [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A)),
                 ("press-release-synthetic-linked", DAY_A,
                  release_page("press-release-synthetic-linked", DAY_A, body_html=linked)),
                 ("press-release-synthetic-contracted", DAY_A,
                  release_page("press-release-synthetic-contracted", DAY_A,
                               narrative=(N1, "This study was prepared by an example contractor."))),
                 ("press-release-synthetic-quotes", DAY_A,
                  release_page("press-release-synthetic-quotes", DAY_A, body_html=quote_only)),
                 (dalai, "2026-08-26", release_page(dalai, "2026-08-26"))]
        head = commit_custody(self.repo, cases)
        records = links.with_title_hash(d.verified_source(self.repo, head, FAMILY))
        holds = {r["source_identity"]: r["uscc_hold"] for r in records}
        self.assertEqual(holds, {ident(SLUG_A): None,
                                 ident("press-release-synthetic-linked"): "uscc_linked_work_present",
                                 ident("press-release-synthetic-contracted"):
                                     "uscc_authorship_indicator_present",
                                 ident("press-release-synthetic-quotes"): "uscc_no_official_narrative",
                                 ident(dalai): "uscc_source_specific_hold"})
        for r in records:
            if r["uscc_hold"]:
                self.assertTrue(_uscc_known_hold(r))
                self.assertEqual(r["body"], "")
        envelope = links.sign_links(records, key=KEY)
        self.assertEqual([l["source_identity"] for l in envelope["packet"]["links"]], [ident(SLUG_A)])
        self.assertEqual(set(envelope["packet"]["links"][0]), set(links.LINK_FIELDS))
        blob = json.dumps(envelope)
        for prose in (TITLE, N1, N2, QUOTE, BOILER):
            self.assertNotIn(prose, blob)

    def test_changed_or_unreproduced_evidence_holds_at_the_pin(self):
        raw = release_page(SLUG_A, DAY_A)
        head = commit_custody(self.repo, [(SLUG_A, DAY_A, raw)])
        capture = self.repo / "state/captures" / (hashlib.sha256(raw).hexdigest() + ".bin")
        capture.write_bytes(raw.replace(b"delegation", b"delegatiom"))
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(git + ["commit", "-qam", "tamper"], check=True)
        tampered = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                                  text=True).stdout.strip()
        (good,) = d.verified_source(self.repo, head, FAMILY)
        (bad,) = d.verified_source(self.repo, tampered, FAMILY)
        self.assertIsNone(good["uscc_hold"])
        self.assertEqual(bad["uscc_hold"], "uscc_capture_hash_mismatch")
        self.assertEqual(bad["body"], "")
        # A stored text the capture does not reproduce never qualifies.
        with sqlite3.connect(str(self.repo / "state/shadow.db")) as conn:
            text = N1 + "\n"
            conn.execute("UPDATE shadow_records SET text_original=?, content_sha256=?",
                         (text, hashlib.sha256(text.encode()).hexdigest()))
        conn.close()
        capture.write_bytes(raw)
        subprocess.run(git + ["commit", "-qam", "restored capture, altered text"], check=True)
        altered = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True,
                                 text=True).stdout.strip()
        (row,) = d.verified_source(self.repo, altered, FAMILY)
        self.assertEqual(row["uscc_hold"], "uscc_custody_text_not_reproduced")

    def test_custody_is_append_only(self):
        commit_custody(self.repo, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A))])
        changed = release_page(SLUG_A, DAY_A, narrative=(N1, N3))
        with self.assertRaises(links.LinkRefused) as cm:
            commit_custody(self.repo, [(SLUG_A, DAY_A, changed)], run_id="uscc-2")
        self.assertEqual(str(cm.exception), "uscc_custody_row_conflict")

    def test_wrong_remote_or_branch_is_refused(self):
        other = init_custody(self.tmp / "o", remote="https://github.com/example/other")
        head = commit_custody(other, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A))])
        with self.assertRaises(d.IntakeHold):
            d.verified_source(other, head, FAMILY)
        wrong = init_custody(self.tmp / "w", branch="archive/another-family")
        head = commit_custody(wrong, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A))])
        with self.assertRaises(subprocess.CalledProcessError):
            d.verified_source(wrong, head, FAMILY)

    def test_disabled_policy_and_held_rows_never_reach_a_model(self):
        dalai = "press-release-dalai-lamas-succession-geopolitical-implications-and-policy"
        head = commit_custody(self.repo, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A)),
                                          (dalai, "2026-08-26", release_page(dalai, "2026-08-26"))])
        records = d.verified_source(self.repo, head, FAMILY)
        factory = Mock()
        state, _ = d.process(records, {}, family=FAMILY, policy=policy(enabled=False),
                             analyzer_factory=factory)
        factory.assert_not_called()
        self.assertEqual(state[FAMILY + ":" + ident(SLUG_A)]["reason"], "model_rights_held")
        held = [r for r in records if r["source_identity"] == ident(dalai)]
        state, _ = d.process(held, {}, family=FAMILY, policy=policy(), analyzer_factory=factory)
        factory.assert_not_called()
        self.assertNotEqual(state.get(FAMILY + ":" + ident(dalai), {}).get("status"), "complete")


class Lifecycle(unittest.TestCase):
    """Custody -> signed links -> private processing -> signed outputs -> SQLite -> reader."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db = self.tmp / "public.db"
        build_legacy_db(self.db)
        migrate(self.db)
        with sqlite3.connect(str(self.db)) as conn:
            list_metadata(conn, ident(SLUG_A), DAY_A)
            list_metadata(conn, ident(SLUG_B), DAY_B)
        conn.close()
        self.repo = init_custody(self.tmp)
        self.head = commit_custody(self.repo, [
            (SLUG_A, DAY_A, release_page(SLUG_A, DAY_A)),
            (SLUG_B, DAY_B, release_page(SLUG_B, DAY_B, narrative=(N3, N4)))])
        self.lane = Lane(self, self.db, self.tmp)

    def deliver(self, head=None):
        """One Daily cycle; returns (state, envelope, governed outcome)."""
        return self.lane.daily(self.repo, head or self.head)

    def test_links_need_the_existing_listing_metadata_row(self):
        with sqlite3.connect(str(self.db)) as conn:
            conn.execute("DELETE FROM uscc_official_source_records WHERE source_identity=?",
                         (ident(SLUG_B),))
        conn.close()
        self.lane.sign_links(self.repo, self.head)
        self.lane.fetch()
        code, receipt = self.lane.admit_links()
        self.assertEqual(receipt["admitted"], 1)
        self.assertEqual(receipt["refused"], {ident(SLUG_B): "uscc_link_metadata_identity_missing"})
        self.assertIsNone(self.lane.parent_scope(ident(SLUG_B)))

    def test_one_release_per_run_reaches_the_reader_and_replays_without_duplication(self):
        from core.collection import status
        a, b = FAMILY + ":" + ident(SLUG_A), FAMILY + ":" + ident(SLUG_B)
        state, envelope, outcome = self.deliver()
        self.assertEqual(outcome.status, status.OK)
        self.assertEqual(state[a]["status"], "complete")  # newest first, one per run
        self.assertEqual(self.lane.model.analyze_record.call_count, 1)
        title, body, profile = self.lane.model.analyze_record.call_args.args
        self.assertEqual((title, body, profile.source_family), (TITLE, N1 + "\n\n" + N2, FAMILY))
        self.assertEqual([r["source_identity"] for r in self.lane.reader()], [ident(SLUG_A)])
        state, envelope, outcome = self.deliver()
        self.assertEqual(state[b]["status"], "complete")
        self.assertEqual(self.lane.model.analyze_record.call_count, 2)
        rows = self.lane.reader()
        self.assertEqual([r["source_identity"] for r in rows], [ident(SLUG_A), ident(SLUG_B)])
        for r in rows:
            self.assertEqual((r["desk_id"], r["source_label"], r["model_id"]),
                             ("us-indopacific", "USCC", MODEL_ID))
            self.assertEqual(r["summary"], " ".join(SENTENCES))
        # The same versions again: no model call, no new row, no re-admitted parent.
        state, envelope, outcome = self.deliver()
        self.assertEqual(self.lane.model.analyze_record.call_count, 2)
        self.assertEqual(outcome.status, status.OK_ALL_DUPLICATES)
        self.assertEqual(self.lane.rows(), sorted([ident(SLUG_A), ident(SLUG_B)]))
        code, receipt = self.lane.admit_links()
        self.assertEqual((receipt["admitted"], receipt["unchanged"]), (0, 2))

    def test_a_changed_version_holds_its_parent_and_withdraws_the_record(self):
        self.deliver()
        self.assertEqual([r["source_identity"] for r in self.lane.reader()], [ident(SLUG_A)])
        # The publisher's page changes; a fresh custody capture of the same identity.
        changed = init_custody(self.tmp / "recaptured")
        head = commit_custody(changed, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A,
                                                                     narrative=(N1, N3)))],
                              run_id="uscc-2")
        self.lane.sign_links(changed, head)
        self.lane.fetch()
        code, receipt = self.lane.admit_links()
        self.assertEqual(receipt["held"], [ident(SLUG_A)])
        self.assertEqual(self.lane.parent_scope(ident(SLUG_A)), "held")
        self.assertEqual(self.lane.reader(), [])
        self.assertEqual(self.lane.rows(), [ident(SLUG_A)])  # kept, withdrawn, not deleted

    def test_a_bad_mac_is_refused_and_accepted_state_is_intact(self):
        self.deliver()
        before = self.lane.reader()
        path = self.lane.public_in / (FAMILY + ".json")
        envelope = json.loads(path.read_text())
        envelope["mac"] = "0" * len(envelope["mac"])
        path.write_text(json.dumps(envelope))
        with self.assertRaises(d.IntakeHold):
            self.lane.public_admission()
        links_path = self.lane.public_in / links.LINKS_NAME
        signed = json.loads(links_path.read_text())
        signed["packet"]["links"][0]["publisher_posted_date"] = "2026-07-21"
        links_path.write_text(json.dumps(signed))
        code, receipt = self.lane.admit_links()
        self.assertEqual((code, receipt["reason"]), (1, "uscc_link_envelope_mac_invalid"))
        self.assertEqual(self.lane.reader(), before)

    def test_a_failed_attempt_recovers_without_resetting_attempts_or_public_state(self):
        a, b = FAMILY + ":" + ident(SLUG_A), FAMILY + ":" + ident(SLUG_B)
        self.deliver()
        public = self.lane.reader()
        good = self.lane.model.analyze_record.side_effect
        thin = dict(mechanical_reading(TITLE, N3 + "\n\n" + N4, None), summary_english="Too short.")
        self.lane.model.analyze_record.side_effect = [thin, good(TITLE, N3 + "\n\n" + N4, None)]
        state, envelope, _ = self.deliver()
        self.assertEqual((state[b]["status"], state[b]["attempts"]), ("retriable", 1))
        self.assertEqual(state[a]["status"], "complete")
        self.assertEqual(self.lane.reader(), public)
        state, envelope, _ = self.deliver()
        self.assertEqual(state[b]["status"], "complete")
        # One failed attempt was recorded and kept; the successful retry neither
        # resets nor double-counts it (the JCG retriable semantics).
        self.assertEqual(state[b]["attempts"], 1)
        self.assertEqual(self.lane.model.analyze_record.call_count, 3)
        self.assertEqual([r["source_identity"] for r in self.lane.reader()],
                         [ident(SLUG_A), ident(SLUG_B)])
        self.assertEqual(self.lane.reader()[0], public[0])

    def test_no_title_narrative_or_excluded_text_in_public_or_handoff_state(self):
        self.deliver()
        self.deliver()
        blobs = [("db", "\n".join(sqlite3.connect(str(self.db)).iterdump()))]
        for folder in (self.lane.public_in, self.lane.envelopes):
            blobs += [(str(p), p.read_text()) for p in folder.glob("*.json")]
        blobs += [("queue", self.lane.queue.read_text()),
                  ("links", (self.lane.handoff / links.LINKS_NAME).read_text())]
        self.assertEqual(leaks((TITLE, N1, N2, N3, N4, QUOTE, BOILER), blobs), [])


class RenderedDelivery(unittest.TestCase):
    """SYNTHETIC: one release through the lane into a render of a tracked-DB copy."""

    @classmethod
    def setUpClass(cls):
        tracked = ROOT / "pla_watch.db"
        if not tracked.exists():
            raise unittest.SkipTest("tracked database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="uscc-delivery-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.tracked, cls.before = tracked, hashlib.sha256(tracked.read_bytes()).hexdigest()
        cls.db = cls.tmp / "scratch.db"
        shutil.copy(tracked, cls.db)
        migrate(cls.db)
        with sqlite3.connect(str(cls.db)) as conn:
            list_metadata(conn, ident(SLUG_A), DAY_A)
        conn.close()
        repo = init_custody(cls.tmp)
        head = commit_custody(repo, [(SLUG_A, DAY_A, release_page(SLUG_A, DAY_A))])
        lane = Lane(unittest.TestCase(), cls.db, cls.tmp)
        lane.daily(repo, head)
        cls.rows = [r for r in lane.reader() if r["source_family"] == FAMILY]
        cls.out = cls.tmp / "build"
        render(cls.db, lane.p, cls.out, "USCC delivery test")
        cls.path = cls.rows[0]["record_path"]

    def page(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_one_record_admitted_and_tracked_database_untouched(self):
        self.assertEqual(len(self.rows), 1)
        self.assertEqual(hashlib.sha256(self.tracked.read_bytes()).hexdigest(), self.before)

    def test_record_page_labels_the_machine_reading_and_the_exclusions(self):
        page = self.page(self.path)
        self.assertIn("US Indo-Pacific Reference Desk", page)
        self.assertIn("../us-indopacific.html", page)
        self.assertNotIn("Philippines Desk", page)
        self.assertIn("data-uscc-source-note", page)
        self.assertIn("not USCC text", page)
        self.assertIn(MODEL_ID, page)
        for s in SENTENCES:
            self.assertIn(s, page)
        self.assertIn(self.rows[0]["content_sha256"], page)

    def test_us_desk_lists_and_annotates_the_record(self):
        desk = self.page("us-indopacific.html")
        self.assertIn("data-us-uscc-machine-explanations", desk)
        self.assertIn(self.path, desk)
        self.assertIn('data-uscc-official-link="' + ident(SLUG_A) + '"', desk)
        self.assertIn("Machine explanation published above", desk)

    def test_other_record_pages_do_not_gain_the_uscc_note(self):
        for path in (self.out / "record").glob("source-*.html"):
            if path.name != Path(self.path).name:
                self.assertNotIn("data-uscc-source-note", path.read_text(encoding="utf-8"))

    def test_archive_and_search_projection_carry_the_record(self):
        self.assertIn('value="machine_explanation"', self.page("archive.html"))
        self.assertIn(self.path, self.page("archive-research-index.json"))

    def test_no_synthetic_original_text_reaches_any_public_file(self):
        self.assertEqual(leaks((TITLE, N1, N2, QUOTE, BOILER), public_files(self.out)), [])


EVIDENCE = os.environ.get("IPR_USCC_PRIVATE_EVIDENCE")
ACCEPTED = ("uscc-press:press-release-us-china-commission-departs-fact-finding-trip-china",
            "uscc-press:press-release-us-china-commission-returns-fact-finding-trip-china")
JUNE_25 = "uscc-press:press-release-plain-english-guide-ai-tech-stack"


@unittest.skipUnless(EVIDENCE, "AUTHENTIC replay needs IPR_USCC_PRIVATE_EVIDENCE (private custody)")
class AuthenticReplay(unittest.TestCase):
    """AUTHENTIC captures, TEST-DOUBLE processing, production lane and renderer.

    The preserved 2026-11-03 captures (private evidence 9036f2fc) enter the
    shared custody layout through ``custody_row``/``write_custody`` in a scratch
    repository; their metadata parents are the tracked database's real USCC
    listing rows (copied DB). Assertions and output are hashes, codes, counts.
    """

    @classmethod
    def setUpClass(cls):
        from tests.test_uscc_offline_input import FIXTURE, load_ledger
        tracked = ROOT / "pla_watch.db"
        cls.fixture = FIXTURE
        root = Path(EVIDENCE)
        ledger = load_ledger(root)
        robots = (root / "captures" / (ledger["robots_sha256"] + ".bin")).read_bytes()
        cls.tmp = Path(tempfile.mkdtemp(prefix="uscc-authentic-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.tracked, cls.before = tracked, hashlib.sha256(tracked.read_bytes()).hexdigest()
        cls.db = cls.tmp / "scratch.db"
        shutil.copy(tracked, cls.db)
        migrate(cls.db)
        repo = init_custody(cls.tmp)
        releases, cls.raw = [], {}
        for r in ledger["releases"]:
            raw = (root / "captures" / (r["capture_sha256"] + ".bin")).read_bytes()
            cls.raw[r["source_identity"]] = raw
            access = {"capture_sha256": r["capture_sha256"], "payload_bytes": r["payload_bytes"],
                      "requested_url": r["requested_url"], "final_url": r["final_url"],
                      "http_status": r["http_status"], "content_type": r["headers"]["content-type"],
                      "retrieved_utc": r["retrieved_utc"], "user_agent": ledger["agent"],
                      "robots_sha256": ledger["robots_sha256"]}
            releases.append((r["source_identity"], r["listing_date"], raw, access))
        head = commit_custody(repo, releases, run_id=ledger["run_id"], robots=robots,
                              provenance={"imported_from": "ipr-source-evidence-private@9036f2fc",
                                          "ledger_run": ledger["run_id"]})
        with sqlite3.connect(str(repo / "state/shadow.db")) as conn:
            cls.private = {row[0]: (row[1], row[2]) for row in conn.execute(
                "SELECT source_identity,title_original,text_original FROM shadow_records")}
        conn.close()
        cls.lane = lane = Lane(unittest.TestCase(), cls.db, cls.tmp)
        cls.signed = lane.sign_links(repo, head)
        cls.records = d.verified_source(repo, head, FAMILY)
        cls.states = []
        for _ in range(3):  # two eligible versions at one per run, then a replay
            state, _env, outcome = lane.daily(repo, head)
            cls.states.append((state, outcome))
        cls.inputs = [c.args[1] for c in lane.model.analyze_record.call_args_list]
        cls.rows = [r for r in lane.reader() if r["source_family"] == FAMILY]
        cls.out = cls.tmp / "build"
        render(cls.db, lane.p, cls.out, "USCC authentic replay")
        # A changed capture of an accepted version: the publisher-change case.
        changed = init_custody(cls.tmp / "recaptured")
        july25 = cls.raw[ACCEPTED[1]].replace(b"</html>", b"<!-- recaptured --></html>")
        chead = commit_custody(changed, [(ACCEPTED[1], "2026-07-25", july25,
                                          dict(receipt(july25, links.canonical_url(ACCEPTED[1]),
                                                       robots), user_agent=ledger["agent"]))],
                               run_id="uscc-recapture", robots=robots)
        lane.sign_links(changed, chead)
        lane.fetch()
        cls.change_receipt = lane.admit_links()[1]
        cls.after_change = [r["source_identity"] for r in lane.reader() if r["source_family"] == FAMILY]
        summary = {"dispositions": {r["source_identity"]: r["uscc_hold"] or "eligible"
                                    for r in cls.records},
                   "potential_input_sha256": {r["source_identity"]: r["potential_input_sha256"]
                                              for r in cls.records if r["potential_input_sha256"]},
                   "model_calls": len(cls.inputs), "public_rows": len(cls.rows),
                   "replay_outcome": cls.states[-1][1].status,
                   "change_receipt": {k: cls.change_receipt[k] for k in ("held", "admitted")},
                   "rows_after_change": cls.after_change}
        print("\nAUTHENTIC USCC replay (hashes/codes only): " + json.dumps(summary, sort_keys=True),
              file=sys.stderr)

    def test_accepted_versions_qualify_with_their_recorded_input_and_june_25_holds(self):
        holds = {r["source_identity"]: r["uscc_hold"] for r in self.records}
        self.assertEqual(holds, {ACCEPTED[0]: None, ACCEPTED[1]: None,
                                 JUNE_25: "uscc_source_specific_hold"})
        for r in self.records:
            if r["source_identity"] in self.fixture:
                s = self.fixture[r["source_identity"]]
                self.assertEqual((r["potential_input_sha256"], r["capture_sha256"],
                                  r["content_sha256"]),
                                 (s["potential_input_sha256"], s["capture_sha256"],
                                  s["content_sha256"]))
        self.assertEqual(sorted(l["source_identity"] for l in self.signed["packet"]["links"]),
                         sorted(ACCEPTED))

    def test_only_the_qualified_narrative_reached_the_test_double(self):
        self.assertEqual(len(self.inputs), 2)
        by_hash = {hashlib.sha256(i.encode()).hexdigest(): i for i in self.inputs}
        for r in self.records:
            if r["source_identity"] in ACCEPTED:
                self.assertIn(hashlib.sha256(r["body"].encode()).hexdigest(), by_hash)
        for identity, (title, text) in self.private.items():
            narrative = next((r["body"] for r in self.records
                              if r["source_identity"] == identity), "")
            excluded = [line for line in text.splitlines()
                        if len(line) >= 25 and line not in narrative]
            for sent in self.inputs:
                self.assertFalse([x for x in excluded if x in sent], identity)

    def test_both_versions_reach_every_reader_surface(self):
        self.assertEqual(sorted(r["source_identity"] for r in self.rows), sorted(ACCEPTED))
        desk = (self.out / "us-indopacific.html").read_text(encoding="utf-8")
        index = (self.out / "archive-research-index.json").read_text(encoding="utf-8")
        self.assertIn("data-us-uscc-machine-explanations", desk)
        self.assertEqual(desk.count("Machine explanation published above"), 2)
        for r in self.rows:
            page = (self.out / r["record_path"]).read_text(encoding="utf-8")
            self.assertIn("data-uscc-source-note", page)
            self.assertIn(MODEL_ID, page)
            self.assertIn(r["record_path"], desk)
            self.assertIn(r["record_path"], index)

    def test_replay_admits_nothing_new(self):
        from core.collection import status
        self.assertEqual([o.status for _s, o in self.states],
                         [status.OK, status.OK, status.OK_ALL_DUPLICATES])
        self.assertEqual(len(self.rows), 2)

    def test_a_changed_capture_holds_the_parent_and_withdraws_only_that_record(self):
        self.assertEqual(self.change_receipt["held"], [ACCEPTED[1]])
        self.assertEqual(self.after_change, [ACCEPTED[0]])

    def test_no_private_text_in_public_files_database_or_handoff(self):
        needles = set()
        for title, text in self.private.values():
            needles.add(title)
            needles.update(line for line in text.splitlines() if len(line) >= 25)
        blobs = list(public_files(self.out))
        blobs.append(("db", "\n".join(sqlite3.connect(str(self.db)).iterdump())))
        blobs += [(str(p), p.read_text()) for p in self.lane.public_in.glob("*.json")]
        blobs.append(("queue", self.lane.queue.read_text()))
        self.assertEqual(leaks(needles, blobs), [])
        self.assertEqual(hashlib.sha256(self.tracked.read_bytes()).hexdigest(), self.before)


if __name__ == "__main__":
    unittest.main()
