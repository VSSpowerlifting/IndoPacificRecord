"""Korea records reach the reader only through the publication gate.

Two layers:

  * the gate itself (core.korea_corpus_bridge.publication_gate) on a migrated
    scratch database: admitted and finished rows publish, every other Korea
    row is hidden, a row that bypassed the bridge is hidden;
  * the production renderer (site/preview/generate_preview.build) on a
    disposable copy of pla_watch.db with the STAGED activation manifest synced
    in and the four public KOGL releases bridged: one reader record per
    finished release, labelled machine translation, cross-linked to its
    licensed original exhibit; held and pending releases absent; China and
    Singapore output unchanged; half-applied activation refused.

The English lines below are synthetic fixtures, never claims about the
releases. Nothing touches pla_watch.db, which is only read through a backup.
"""
import dataclasses
import difflib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import korea_corpus_bridge as bridge
from core.korea_published_originals import INDEX, ORIGINAL_DIR
from core.manifests import load_manifest
from core.registry import sync_desk_config
from migrations.runner import apply_all, connect
from tests.test_korea_corpus_bridge import (
    LIVE, BridgeCase, activate, admit_metadata,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site" / "preview"))
import generate_preview as gp  # noqa: E402

NUMBER = re.compile(r"\d+")
STAGED_MANIFEST = ROOT / "config" / "korea_daily_activation" / "manifest.json"


def synthetic_english(text_original):
    """Line-aligned synthetic English: blank where the original is blank."""
    return "\n".join("Synthetic machine translation line %d." % n if line.strip() else ""
                     for n, line in enumerate(text_original.split("\n"), 1))


def finish(conn, identity, state, *, english=True):
    """Put a bridged row into a processing state as the lane would."""
    aid, text = conn.execute(
        "SELECT a.id, a.text_original FROM korea_corpus_admissions k "
        "JOIN articles a ON a.id = k.article_id WHERE k.source_identity = ?",
        (identity,)).fetchone()
    if state == "processed":
        conn.execute(
            "UPDATE articles SET passed_relevance = 1, relevance_score = 0.9, "
            "title_english = ?, text_english = ?, summary_english = ?, "
            "is_significant = 0, analyzed_at = '2026-10-01T00:00:00Z', "
            "model_id = 'fixture-model', prompt_version = 'korea-v2-fixture' "
            "WHERE id = ?",
            ("Synthetic English title %d" % aid,
             synthetic_english(text) if english else None,
             "Synthetic summary %d." % aid, aid))
    conn.execute("UPDATE korea_corpus_admissions SET processing_state = ? "
                 "WHERE source_identity = ?", (state, identity))
    conn.commit()
    return aid


class TestPublicationGate(BridgeCase):
    def setUp(self):
        super().setUp()
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        self.run_bridge()
        self.ids = dict(self.conn.execute(
            "SELECT source_identity, article_id FROM korea_corpus_admissions"))

    def test_admitted_but_unprocessed_rows_are_hidden(self):          # scenario 1
        publishable, hidden = bridge.publication_gate(self.conn)
        self.assertEqual(publishable, {})
        self.assertEqual(hidden, set(self.ids.values()))

    def test_only_processed_and_not_relevant_publish(self):           # scenario 3, 4
        a, b, c, d = sorted(self.ids)
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='processed' WHERE source_identity=?", (a,))
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='not_relevant' WHERE source_identity=?", (b,))
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='qa_held' WHERE source_identity=?", (c,))
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='retryable' WHERE source_identity=?", (d,))
        publishable, hidden = bridge.publication_gate(self.conn)
        self.assertEqual(publishable, {self.ids[a]: a, self.ids[b]: b})
        self.assertEqual(hidden, {self.ids[c], self.ids[d]})

    def test_withdrawn_or_held_ledger_row_is_hidden_even_if_processed(self):  # scenario 5
        a, b = sorted(self.ids)[:2]
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='processed'")
        self.conn.execute("UPDATE korea_corpus_admissions SET state='withdrawn' WHERE source_identity=?", (a,))
        self.conn.execute("UPDATE korea_corpus_admissions SET state='held', "
                          "hold_reason='pin_text_mismatch' WHERE source_identity=?", (b,))
        publishable, hidden = bridge.publication_gate(self.conn)
        self.assertNotIn(self.ids[a], publishable)
        self.assertNotIn(self.ids[b], publishable)
        self.assertEqual(hidden, {self.ids[a], self.ids[b]})

    def test_a_korea_row_that_bypassed_the_bridge_is_hidden(self):    # scenario 13
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='processed'")
        src = bridge.source_row(self.conn)[0]
        cur = self.conn.execute(
            "INSERT INTO articles (source_id, url, title_original, text_original, "
            "content_hash, published_date) VALUES (?, 'https://www.korea.kr/x', "
            "'t', 'b', 'h', '2026-10-20')", (src,))
        publishable, hidden = bridge.publication_gate(self.conn)
        self.assertEqual(hidden, {cur.lastrowid})
        self.assertEqual(set(publishable), set(self.ids.values()))

    def test_gate_reads_through_a_dict_row_factory(self):
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='processed'")
        self.conn.row_factory = lambda cur, row: {
            d[0]: v for d, v in zip(cur.description, row)}
        publishable, hidden = bridge.publication_gate(self.conn)
        self.assertEqual(set(publishable), set(self.ids.values()))
        self.assertEqual(hidden, set())

    def test_predicate_is_constant_without_hidden_rows(self):         # scenario 11
        self.assertEqual(bridge.hidden_predicate(set()), "1=1")
        self.assertEqual(bridge.hidden_predicate({3, 1}, "x"), "x.id NOT IN (1,3)")


def live_registry(manifest=gp.KOREA_MANIFEST, status="live", records=True):
    real = gp.load_registry()
    sources = load_manifest(STAGED_MANIFEST).sources if manifest else []
    korea = dataclasses.replace(real.get("korea"), status=status,
                                manifest_path=manifest,
                                has_production_records=records,
                                sources=list(sources))
    return dataclasses.replace(real, entries=[
        korea if e.slug == "korea" else e for e in real.entries])


class TestRenderedKoreaRecords(unittest.TestCase):
    """One full build before and one after activation on disposable copies."""

    @classmethod
    def setUpClass(cls):
        from scripts.reconcile_db import read_only
        cls.tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-render-")
        root = Path(cls.tmp.name)
        cls.pristine, cls.activated = root / "pristine.db", root / "activated.db"
        for path in (cls.pristine, cls.activated):
            with read_only(str(ROOT / "pla_watch.db")) as source:
                dest = sqlite3.connect(str(path))
                source.backup(dest)
                dest.close()

        # Owner activation, rehearsed on the copy: migrate, sync the staged
        # manifest beside the real ones, bridge the released KOGL texts.
        desks = root / "desks"
        for desk in ("china", "singapore"):
            shutil.copytree(ROOT / "desks" / desk, desks / desk)
        (desks / "korea").mkdir()
        shutil.copyfile(STAGED_MANIFEST, desks / "korea" / "manifest.json")
        conn = connect(cls.activated)
        apply_all(conn)
        sync_desk_config(conn, desks)
        conn.isolation_level = None
        receipt = bridge.apply(conn, index=INDEX, original_dir=ORIGINAL_DIR,
                               excluded={}, registry=LIVE)
        assert len(receipt["admitted"]) == 4, receipt
        idents = sorted(i for i, in conn.execute(
            "SELECT source_identity FROM korea_corpus_admissions"))
        cls.processed, cls.no_english, cls.held, cls.pending = idents
        cls.ids = {i: finish(conn, i, s, english=(i != cls.no_english))
                   for i, s in ((cls.processed, "processed"),
                                (cls.no_english, "processed"),
                                (cls.held, "qa_held"))}
        cls.ids[cls.pending] = conn.execute(
            "SELECT article_id FROM korea_corpus_admissions WHERE source_identity=?",
            (cls.pending,)).fetchone()[0]
        # A real admission moves the site-wide "records last collected" date;
        # pin it before the corpus's newest record so the comparison below
        # isolates everything except the record totals.
        conn.execute("UPDATE articles SET scraped_at = '2026-10-01 00:00:00' "
                     "WHERE id IN (%s)" % ",".join(map(str, cls.ids.values())))
        conn.close()

        cls.before = root / "before"
        gp.build(cls.before, gp.PUBLIC_TITLE, cls.pristine,
                 snapshot=gp.snapshot_from_corpus(cls.pristine), legacy_routes=True)
        cls.after = root / "after"
        with mock.patch.object(gp, "load_registry", return_value=live_registry()), \
                mock.patch("core.korea_corpus_bridge.excluded_identities", return_value={}):
            gp.build(cls.after, gp.PUBLIC_TITLE, cls.activated,
                     snapshot=gp.snapshot_from_corpus(cls.activated), legacy_routes=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, out, rel):
        return (out / rel).read_text(encoding="utf-8")

    def assertOnlyTotalsMoved(self, rel):
        """Two more published records legitimately raise site-wide totals
        (masthead, citation snapshot, desk ledger). Anything else differing
        between the builds is a regression."""
        published = 2
        before = self.page(self.before, rel).split("\n")
        after = self.page(self.after, rel).split("\n")
        if len(before) != len(after):
            self.fail("%s: lines added or removed\n%s" % (rel, "\n".join(
                difflib.unified_diff(before, after, lineterm="", n=1))))
        for old, new in zip(before, after):
            if old == new:
                continue
            self.assertEqual(NUMBER.sub("N", old), NUMBER.sub("N", new), rel)
            for a, b in zip(NUMBER.findall(old), NUMBER.findall(new)):
                self.assertIn(int(b) - int(a), (0, published), "%s: %s" % (rel, new.strip()))

    def news_id(self, identity):
        return identity.split(":", 1)[1]

    def test_only_finished_releases_get_a_record(self):              # scenario 1, 4
        for ident in (self.processed, self.no_english):
            self.assertTrue((self.after / "record" / ("%d.html" % self.ids[ident])).is_file())
        for ident in (self.held, self.pending):
            self.assertFalse((self.after / "record" / ("%d.html" % self.ids[ident])).exists())
        index = json.loads(self.page(self.after, "corpus-index.json"))
        listed = json.dumps(index)
        for ident in (self.held, self.pending):
            self.assertNotIn("record/%d.html" % self.ids[ident], listed)

    def test_record_labels_machine_translation_and_links_the_original(self):  # scenario 3, 16
        html = self.page(self.after, "record/%d.html" % self.ids[self.processed])
        self.assertIn("Full text in English", html)
        self.assertIn("Machine translation", html)
        self.assertIn("Not reviewed by a human", html)
        self.assertIn("official claims", html)
        self.assertIn("../korea-originals/%s.html" % self.news_id(self.processed), html)
        self.assertIn("https://www.korea.kr/guide/copyRight.do", html)
        self.assertIn("Synthetic machine translation line", html)
        self.assertNotIn("human-reviewed translation", html.lower())
        # The Korean body lives on the licensed exhibit page only.
        original = (ORIGINAL_DIR / (self.news_id(self.processed) + ".txt")).read_text(encoding="utf-8")
        longest = max(original.split("\n"), key=len).strip()
        self.assertGreater(len(longest), 20)
        self.assertNotIn(longest, html)

    def test_record_without_english_has_no_translation_section(self):
        html = self.page(self.after, "record/%d.html" % self.ids[self.no_english])
        self.assertNotIn("record-translation-section", html)
        self.assertIn("../korea-originals/%s.html" % self.news_id(self.no_english), html)

    def test_desk_links_records_and_keeps_every_released_original(self):  # scenario 12
        desk = self.page(self.after, "korea.html")
        links = set(re.findall(r'data-korea-record-link="([^"]+)"', desk))
        self.assertEqual(links, {self.processed, self.no_english})
        for ident in (self.processed, self.held, self.pending, self.no_english):
            self.assertIn("korea-originals/%s.html" % self.news_id(ident), desk)
        for ident in (self.held, self.pending):
            self.assertNotIn("record/%d.html" % self.ids[ident], desk)

    def test_released_original_exhibits_are_byte_identical(self):    # scenario 8, 12
        for ident in (self.processed, self.held, self.pending, self.no_english):
            rel = "korea-originals/%s.html" % self.news_id(ident)
            self.assertEqual((self.before / rel).read_bytes(), (self.after / rel).read_bytes(), rel)

    def test_other_desks_record_pages_unchanged(self):               # scenario 11
        korea = {"%d.html" % i for i in self.ids.values()}
        before = {p.name for p in (self.before / "record").glob("*.html")}
        self.assertTrue(before)
        self.assertFalse(before & korea)
        for name in sorted(before):
            self.assertOnlyTotalsMoved("record/" + name)

    def test_other_desks_pages_unchanged(self):                      # scenario 11
        for rel in ("china.html", "singapore.html"):
            if (self.before / rel).exists():
                self.assertOnlyTotalsMoved(rel)


class TestBuildRefusals(unittest.TestCase):
    """Half-applied activation and excluded identities fail closed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ipr-korea-refuse-")
        cls.out = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def refuse(self, registry, name):
        with mock.patch.object(gp, "load_registry", return_value=registry):
            with self.assertRaisesRegex(ValueError, "Korea production admission remains prohibited"):
                gp.build(self.out / name, gp.PUBLIC_TITLE, ROOT / "pla_watch.db")

    def test_live_without_manifest_is_refused(self):
        self.refuse(live_registry(manifest="desks/korea/other.json"), "a")

    def test_live_without_production_records_is_refused(self):
        self.refuse(live_registry(records=False), "b")

    def test_shadow_with_manifest_is_refused(self):
        self.refuse(live_registry(status="shadow", records=False), "c")


class TestExcludedIdentityRefusal(BridgeCase):
    """The frozen baseline / reviewed English / hold never become a record."""

    def test_excluded_identity_reaching_the_gate_refuses_the_build(self):  # scenario 6, 8
        activate(self.conn)
        for rec in self.records:
            admit_metadata(self.conn, rec)
        self.run_bridge()
        self.conn.execute("UPDATE korea_corpus_admissions SET processing_state='processed'")
        publishable, _ = bridge.publication_gate(self.conn)
        excluded = bridge.excluded_identities()
        # In the real repository every one of the four released texts is
        # frozen or editor-reviewed, so none can be machine-published.
        self.assertTrue(set(publishable.values()) <= set(excluded))
        self.assertEqual(len(publishable), 4)


class TestStagedManifest(unittest.TestCase):
    def test_staged_manifest_is_valid_manual_and_mnd_only(self):
        cfg = load_manifest(STAGED_MANIFEST)
        self.assertEqual(cfg.desk.desk_id, "korea")
        self.assertEqual([(s.slug, s.access_method, s.adapter) for s in cfg.sources],
                         [(bridge.SOURCE_SLUG, "manual", None)])
        self.assertEqual({i.institution_id for i in cfg.institutions},
                         {"kr_policy_briefing", "kr_mnd"})

    def test_staged_manifest_is_not_discoverable(self):
        from core.manifests import load_all_desks
        self.assertNotIn("korea", load_all_desks())
        self.assertFalse((ROOT / gp.KOREA_MANIFEST).exists())


if __name__ == "__main__":
    unittest.main()
