"""Global Times private-first custody and its signed public replay.

DECISION_LOG 2026-11-22 (action D). Fixtures are fictional pages and
synthetic keys; no test reaches the network. HTTP is a stub session on a real
``GlobalTimesMilScraper``; ``git`` runs only against temporary repositories.
"""
import ast
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from requests.models import Response
from requests.structures import CaseInsensitiveDict

from adapters.global_times_handoff import GlobalTimesHandoffAdapter
from core.collection import attempts
from core.collection import global_times_handoff as handoff
from core.collection import status as st
from core.collection.contract import CollectionWindow
from core.shadow_schedule import SOURCE_EXPLICIT
from processing.metadata import (compute_content_hash, compute_held_content_hash,
                                 normalize_article)
from scraper.sources.global_times_mil import GlobalTimesMilScraper

ROOT = Path(__file__).resolve().parents[1]
KEY = "synthetic-global-times-key-for-tests-only-0000"
COLLECTOR = "c" * 40
TARGET = date(2026, 11, 20)
LISTING = "https://www.globaltimes.cn/china/military/"
A1 = "https://www.globaltimes.cn/page/202611/900001.shtml"
A2 = "https://www.globaltimes.cn/page/202611/900002.shtml"
A3 = "https://www.globaltimes.cn/page/202611/900003.shtml"
BODY = "A fictional fixture paragraph about a harbour drill, written for tests."


def page(title, body=BODY, byline="By Fixture Writer",
         pub="Published: Nov 20, 2026 11:42 PM") -> bytes:
    return ("<html><head><meta charset='utf-8'></head><body>"
            "<div class='article_title'>%s</div><span class='byline'>%s</span>"
            "<span class='pub_time'>%s</span>"
            "<div class='article_content'><p>%s</p></div></body></html>"
            % (title, byline, pub, body)).encode("utf-8")


def listing(*hrefs) -> bytes:
    tiles = "".join("<div class='tile'><a href='%s'>tile</a>"
                    "<div class='source_time'>By Desk | 2026/11/20 10:00:00</div></div>"
                    % h for h in hrefs)
    return ("<html><body>%s</body></html>" % tiles).encode("utf-8")


def pages(**over):
    base = {LISTING: listing("/page/202611/900001.shtml", "/page/202611/900002.shtml"),
            A1: page("Fixture headline one"),
            A2: page("Fixture headline two", byline="By Xinhua")}
    base.update(over)
    return base


class FakeSession:
    """Serves fixture bytes; anything else is a connection failure."""

    def __init__(self, served):
        self.served, self.calls, self.headers = dict(served), [], {}

    def get(self, url, timeout=None):
        self.calls.append(url)
        if url not in self.served:
            raise requests.ConnectionError("offline fixture")
        resp = Response()
        resp.status_code, resp.url = 200, url
        resp._content = self.served[url]
        resp.headers = CaseInsensitiveDict({"Content-Type": "text/html; charset=utf-8"})
        resp.encoding = "utf-8"
        return resp


def factory(session):
    def make(target_date, lookback_days):
        scraper = GlobalTimesMilScraper(target_date=target_date, lookback_days=lookback_days)
        scraper._session = session
        scraper._rate_limit = lambda: None
        return scraper
    return make


def legacy_parse(url, wire):
    """What the old public scraper's parse_article handed the pipeline."""
    return GlobalTimesMilScraper(target_date=TARGET, lookback_days=2).parse_article(
        url, wire.decode("utf-8"))


GIT = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
       "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]


def git(repo, *args) -> str:
    return subprocess.run(GIT + ["-C", str(repo)] + list(args), check=True,
                          capture_output=True).stdout.decode().strip()


def commit(repo) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", "fixture custody")
    return git(repo, "rev-parse", "HEAD")


def clone(repo, dest) -> Path:
    subprocess.run(GIT + ["clone", "-q", str(repo), str(dest)], check=True,
                   capture_output=True)
    return Path(dest)


def facts(commit_sha="d" * 40, target="2026-11-20", result="ok", health="ok"):
    healthy = result in st.SUCCESS_STATUSES and health in ("ok", "partial")
    return {"schema": attempts.SCHEMA, "family": handoff.FAMILY,
            "custody_commit": commit_sha, "attested": True, "reason": None,
            "latest": {"run_id": "1001-1", "target_date": target,
                       "target_date_source": SOURCE_EXPLICIT,
                       "finished_utc": "2026-11-21T01:30:00Z", "result": result,
                       "health": health, "healthy": healthy},
            "latest_healthy_target_date": target if healthy else None,
            "unledgered_exit": None}


def record(url, title, text=BODY, held=None):
    raw = {"url": url, "source_slug": handoff.SOURCE_SLUG, "title_original": title,
           "text_original": "" if held else text, "published_date": "2026-11-20",
           "content_verdict": None}
    if held:
        raw["text_held"] = held
    wire = page(title)
    return dict(raw, text_held=held, source_identity=handoff.source_identity(url),
                capture_sha256=hashlib.sha256(wire).hexdigest(),
                content_sha256=handoff.content_sha256(raw),
                fetched_at="2026-11-21T01:20:00Z", source_run="1001-1",
                collector_commit=COLLECTOR, raw_retained=not held)


def envelope(records, collection="default", commit_sha="d" * 40, key=KEY, **over):
    env = {"schema": handoff.SCHEMA, "family": handoff.FAMILY,
           "custody_ref": handoff.CUSTODY_REF, "custody_commit": commit_sha,
           "generated_utc": "2026-11-21T01:40:00Z",
           "collection": facts(commit_sha) if collection == "default" else collection,
           "records": records}
    env.update(over)
    env["mac"] = handoff.mac(key, env)
    return env


FRESH = datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc)
# Slot 2026-11-21 01:17 UTC plus the 14 h grace has passed: 2026-11-20 is stale.
STALE = datetime(2026, 11, 21, 16, 0, tzinfo=timezone.utc)


class Isolated(unittest.TestCase):
    """Temp dirs, no hold, no retries, no disk cache outside the test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for p in (patch("scraper.base.CACHE_DIR", self.tmp / "cache"),
                  patch("scraper.base.MAX_RETRIES", 1),
                  patch.dict(os.environ, {})):
            p.start()
            self.addCleanup(p.stop)
        for name in ("IPR_CHINA_SOURCE_USE_HOLD", handoff.KEY_ENV, handoff.INTAKE_DIR_ENV):
            os.environ.pop(name, None)

    def write(self, env, name=handoff.ENVELOPE_NAME) -> Path:
        path = self.tmp / name
        path.write_bytes(handoff.canonical(env))
        return path


# ── envelope: authenticated, exact, fail closed ──────────────────────────────

class EnvelopeRejection(Isolated):

    def good(self):
        return envelope([record(A1, "Fixture headline one")])

    def test_good_envelope_verifies(self):
        env = handoff.verify_envelope(handoff.canonical(self.good()), KEY)
        self.assertEqual(len(env["records"]), 1)

    def assertRejected(self, raw, code, key=KEY):
        with self.assertRaises(handoff.HandoffError) as ctx:
            handoff.verify_envelope(raw, key)
        self.assertEqual(str(ctx.exception), code)

    def test_bad_mac(self):
        env = self.good()
        env["records"][0]["title_original"] = "Altered after signing"
        self.assertRejected(handoff.canonical(env), "gt_handoff_mac_invalid")
        self.assertRejected(handoff.canonical(self.good()), "gt_handoff_mac_invalid",
                            key="another-synthetic-key-of-sufficient-length")

    def test_wrong_schema_even_when_signed(self):
        self.assertRejected(handoff.canonical(envelope([], schema="ipr-other/1")),
                            "gt_handoff_schema_invalid")

    def test_unknown_key_even_when_signed(self):
        self.assertRejected(handoff.canonical(envelope([], extra="x")),
                            "gt_handoff_envelope_shape")
        rec = dict(record(A1, "Fixture headline one"), extra="x")
        self.assertRejected(handoff.canonical(envelope([rec])), "gt_handoff_record_shape")

    def test_non_canonical_url_is_rejected_not_normalised(self):
        for url in ("http://www.globaltimes.cn/page/202611/900001.shtml",
                    "https://globaltimes.cn/page/202611/900001.shtml",
                    A1 + "?utm=x", A1 + "/", "https://www.globaltimes.cn/page/2026/900001.shtml"):
            with self.subTest(url=url):
                rec = record(A1, "Fixture headline one")
                rec["url"] = url
                self.assertRejected(handoff.canonical(envelope([rec])),
                                    "gt_handoff_record_invalid")

    def test_oversize(self):
        raw = handoff.canonical(self.good())
        self.assertRejected(raw + b" " * (handoff.MAX_ENVELOPE_BYTES - len(raw) + 1),
                            "gt_handoff_envelope_too_large")
        path = self.tmp / "big.json"
        path.write_bytes(b"{" + b" " * handoff.MAX_ENVELOPE_BYTES + b"}")
        self.assertEqual(handoff.load_envelope(path, KEY, now=FRESH),
                         ([], st.ADAPTER_ERROR, "gt_handoff_envelope_too_large"))

    def test_missing_or_short_key(self):
        self.assertRejected(handoff.canonical(self.good()), "gt_handoff_key_unavailable", key="")
        self.assertRejected(handoff.canonical(self.good()), "gt_handoff_key_unavailable",
                            key="short")

    def test_content_hash_must_match_public_text(self):
        rec = record(A1, "Fixture headline one")
        rec["content_sha256"] = "0" * 64
        self.assertRejected(handoff.canonical(envelope([rec])),
                            "gt_handoff_content_hash_mismatch")

    def test_held_record_with_text_or_bytes_is_rejected(self):
        rec = record(A2, "Fixture headline two", held="non_gt_byline")
        bad = dict(rec, text_original=BODY)
        self.assertRejected(handoff.canonical(envelope([bad])),
                            "gt_handoff_held_record_invalid")
        bad = dict(rec, raw_retained=True)
        self.assertRejected(handoff.canonical(envelope([bad])),
                            "gt_handoff_held_record_invalid")

    def test_duplicate_identity_rejected(self):
        rec = record(A1, "Fixture headline one")
        self.assertRejected(handoff.canonical(envelope([rec, dict(rec)])),
                            "gt_handoff_duplicate_record")

    def test_load_never_raises(self):
        path = self.tmp / "garbage.json"
        for body in (b"", b"\xff\xfe", b"[]", b'{"mac": 1}'):
            with self.subTest(body=body):
                path.write_bytes(body)
                records, status, detail = handoff.load_envelope(path, KEY, now=FRESH)
                self.assertEqual((records, status), ([], st.ADAPTER_ERROR))
                self.assertTrue(detail.startswith("gt_handoff_"))


# ── public replay adapter statuses ───────────────────────────────────────────

class AdapterStatuses(Isolated):

    class Source:
        slug, enabled, desk_id, language_tag = "global_times_mil", True, "china", "en"

    def collect(self, path, now):
        adapter = GlobalTimesHandoffAdapter(self.Source(), envelope_path=path, key=KEY, now=now)
        return adapter.collect(CollectionWindow(TARGET, TARGET))

    def test_absent_is_listing_failure(self):
        result, docs = self.collect(self.tmp / "missing.json", FRESH)
        self.assertEqual((result.status, result.error_detail, docs),
                         (st.LISTING_FAILURE, "gt_handoff_not_delivered", []))
        self.assertTrue(result.is_failure)
        # No intake directory configured at all: the same named failure.
        adapter = GlobalTimesHandoffAdapter(self.Source(), key=KEY, now=FRESH)
        result, docs = adapter.collect(CollectionWindow(TARGET, TARGET))
        self.assertEqual(result.status, st.LISTING_FAILURE)

    def test_bad_mac_is_adapter_error(self):
        env = envelope([record(A1, "Fixture headline one")])
        env["mac"] = "0" * 64
        result, docs = self.collect(self.write(env), FRESH)
        self.assertEqual((result.status, result.error_detail, docs),
                         (st.ADAPTER_ERROR, "gt_handoff_mac_invalid", []))

    def test_missing_collection_is_fetch_failure(self):
        result, docs = self.collect(self.write(envelope([], collection=None)), FRESH)
        self.assertEqual((result.status, result.error_detail, docs),
                         (st.FETCH_FAILURE, "collection_not_attested", []))

    def test_stale_collection_is_staleness_verdict(self):
        path = self.write(envelope([record(A1, "Fixture headline one")]))
        result, docs = self.collect(path, STALE)
        self.assertEqual((result.status, docs), (st.FETCH_FAILURE, []))
        self.assertTrue(result.error_detail.startswith("collection stale"))
        self.assertEqual(self.collect(path, FRESH)[0].status, st.OK)

    def test_failed_private_attempt_is_named(self):
        path = self.write(envelope([record(A1, "Fixture headline one")], collection=facts(
            result=st.LISTING_FAILURE, health="fail")))
        result, docs = self.collect(path, FRESH)
        self.assertEqual((result.status, docs), (st.LISTING_FAILURE, []))
        self.assertIn("run 1001-1", result.error_detail)

    def test_empty_attested_envelope_is_no_publications(self):
        result, docs = self.collect(self.write(envelope([])), FRESH)
        self.assertEqual((result.status, docs), (st.OK_NO_PUBLICATIONS, []))

    def test_key_read_from_environment(self):
        path = self.write(envelope([record(A1, "Fixture headline one")]))
        adapter = GlobalTimesHandoffAdapter(self.Source(), envelope_path=path, now=FRESH)
        self.assertEqual(adapter.collect(CollectionWindow(TARGET, TARGET))[0].error_detail,
                         "gt_handoff_key_unavailable")
        os.environ[handoff.KEY_ENV] = KEY
        os.environ[handoff.INTAKE_DIR_ENV] = str(self.tmp)
        adapter = GlobalTimesHandoffAdapter(self.Source(), now=FRESH)
        self.assertEqual(adapter.collect(CollectionWindow(TARGET, TARGET))[0].status, st.OK)

    def test_healthy_raw_equals_legacy_parse_article(self):
        wire1, wire2 = page("Fixture headline one"), page("Fixture headline two", byline="By Xinhua")
        legacy = [legacy_parse(A1, wire1), legacy_parse(A2, wire2)]
        self.assertNotIn("custody", legacy[0])
        recs = [record(A1, "Fixture headline one"),
                record(A2, "Fixture headline two", held="non_gt_byline")]
        result, docs = self.collect(self.write(envelope(recs)), FRESH)
        self.assertEqual(result.status, st.OK)
        self.assertEqual([d.raw for d in docs], legacy)
        self.assertEqual([d.as_article_dict() for d in docs], legacy)
        # PUB-3: the held (blank-body) page is counted exactly as the
        # pipeline's text-gap receipts count it, so they never disagree.
        self.assertEqual(result.text_unavailable, 1)
        self.assertIn("held by the parser (non_gt_byline)", result.error_detail)

    def test_held_documents_agree_with_text_gap_receipts(self):
        import logging
        from core.collection.text_gap_receipts import log_unreadable_source_receipts
        recs = [record(A1, "Fixture headline one"),
                record(A2, "Fixture headline two", held="non_gt_byline"),
                record(A3, "Fixture headline three", text="   ")]
        result, docs = self.collect(self.write(envelope(recs)), FRESH)
        receipts = log_unreadable_source_receipts(
            "global_times_mil", docs, logging.getLogger("gt-test-receipts"))
        self.assertEqual((result.status, result.text_unavailable, receipts), (st.OK, 2, 2))
        self.assertIn("held by the parser (non_gt_byline)", result.error_detail)
        self.assertIn("1 of 3 parsed page(s) carried no usable text", result.error_detail)
        # Held pages alone stay a healthy read, never an extraction failure.
        result, docs = self.collect(self.write(envelope(
            [record(A2, "Fixture headline two", held="non_gt_byline")])), FRESH)
        self.assertEqual((result.status, result.text_unavailable), (st.OK, 1))


# ── the real public dedup / insert path ──────────────────────────────────────

class PublicStorage(Isolated):

    def setUp(self):
        super().setUp()
        from storage import db
        self.db = db
        p = patch.object(db, "DB_PATH", self.tmp / "public.db")
        p.start()
        self.addCleanup(p.stop)
        db.init_db()
        if db.get_source_id(handoff.FAMILY) is None:
            with db.get_conn() as c:
                c.execute("INSERT INTO sources(slug,display_name,base_url,language,desk_id)"
                          " VALUES(?,?,?,?,?)", (handoff.FAMILY, "Global Times",
                                                 "https://www.globaltimes.cn/", "en", "china"))

    def replay(self, records):
        """Stages 3-8 exactly as pipeline.py runs them for one source."""
        from processing.dedup import dedup_articles
        from processing.deduplicator import deduplicate
        from processing.relevance import keyword_filter
        result, docs = GlobalTimesHandoffAdapter(
            AdapterStatuses.Source(), envelope_path=self.write(envelope(records)),
            key=KEY, now=FRESH).collect(CollectionWindow(TARGET, TARGET))
        self.assertEqual(result.status, st.OK)
        run_id = self.db.start_scrape_run()
        normalized = [normalize_article(d.as_article_dict()) for d in docs]
        passed, rejected = keyword_filter(deduplicate(dedup_articles(normalized)))
        return [aid for aid in (self.db.insert_article(a, run_id) for a in passed + rejected)
                if aid is not None]

    def rows(self):
        with self.db.get_conn() as c:
            return [tuple(r) for r in c.execute(
                "SELECT id, url, content_hash, text_original FROM articles ORDER BY id")]

    def recs(self):
        return [record(A1, "Fixture headline one"),
                record(A2, "Fixture headline two", held="non_gt_byline"),
                record(A3, "Fixture headline three", held="non_gt_byline")]

    def test_redelivered_envelope_inserts_nothing_and_keeps_ids(self):
        first = self.replay(self.recs())
        self.assertEqual(len(first), 3)
        before = self.rows()
        self.assertEqual(self.replay(self.recs()), [])
        self.assertEqual(self.rows(), before)
        # A later envelope that still carries the same articles changes nothing.
        self.assertEqual(self.replay(self.recs()[:1]), [])
        self.assertEqual({r[1]: r[0] for r in self.rows()}, {r[1]: r[0] for r in before})

    def test_held_rows_insert_blank_and_never_reach_model_dispatch(self):
        from pipeline import hold_blank_original_bodies
        self.replay(self.recs())
        rows = {r[1]: r for r in self.rows()}
        self.assertEqual(rows[A2][3], "")
        self.assertEqual(rows[A3][3], "")
        self.assertEqual(rows[A1][3], BODY)
        candidates = [(r[0], "title", r[3], r[1]) for r in rows.values()]
        ready, withheld = hold_blank_original_bodies(candidates)
        self.assertEqual(([c[3] for c in ready], withheld), ([A1], 2))

    def test_held_rows_with_one_headline_are_not_reposts_of_each_other(self):
        # Title dedup within one batch is unchanged; across runs the content
        # hash alone would have dropped the second held page as a repost.
        self.assertEqual(len(self.replay([record(A2, "Shared headline", held="non_gt_byline")])), 1)
        self.assertEqual(len(self.replay([record(A3, "Shared headline", held="non_gt_byline")])), 1)
        self.assertEqual(self.replay([record(A3, "Shared headline", held="non_gt_byline")]), [])

    def fold_status(self, records):
        """Replay, then the per-source status refinement pipeline.py applies."""
        from processing.dedup import dedup_articles
        from processing.deduplicator import deduplicate
        result, docs = GlobalTimesHandoffAdapter(
            AdapterStatuses.Source(), envelope_path=self.write(envelope(records)),
            key=KEY, now=FRESH).collect(CollectionWindow(TARGET, TARGET))
        new = deduplicate(dedup_articles(
            [normalize_article(d.as_article_dict()) for d in docs]))
        duplicates = len(docs) - len(new)
        if result.status == st.OK and not new and duplicates > 0:
            return st.OK_ALL_DUPLICATES, len(docs)
        return result.status, len(docs)

    def test_stored_redelivery_never_title_suppresses_a_new_article(self):
        b2 = "A different fictional fixture paragraph for a second article."
        self.assertEqual(len(self.replay([record(A3, "Shared headline")])), 1)
        day2 = [record(A3, "Shared headline"), record(A2, "Shared headline", text=b2)]
        self.assertEqual(len(self.replay(day2)), 1)
        self.assertIn(A2, {r[1] for r in self.rows()})
        # Input order does not matter.
        self.assertEqual(len(self.replay([record(A1, "Other headline", text=b2 + " x"),
                                          record(A3, "Other headline")])), 1)

    def test_stored_held_redelivery_never_title_suppresses_a_new_held_article(self):
        self.assertEqual(len(self.replay([record(A3, "Shared headline",
                                                 held="non_gt_byline")])), 1)
        self.assertEqual(len(self.replay([record(A3, "Shared headline", held="non_gt_byline"),
                                          record(A2, "Shared headline",
                                                 held="non_gt_byline")])), 1)
        self.assertEqual({r[1] for r in self.rows()}, {A2, A3})

    def test_all_known_day_still_folds_to_all_duplicates(self):
        recs = [record(A3, "Shared headline"), record(A1, "Fixture headline one")]
        self.assertEqual(len(self.replay(recs)), 2)
        # Every delivered record is stored: all of them still reach dedup, so
        # the fold reports ok_all_duplicates exactly as before, never
        # ok_no_publications.
        self.assertEqual(self.fold_status(recs), (st.OK_ALL_DUPLICATES, 2))
        # A same-title pair that is entirely stored is also left untouched.
        b2 = "A different fictional fixture paragraph for a second article."
        pair = [record(A3, "Shared headline"), record(A2, "Shared headline", text=b2)]
        self.replay(pair)
        self.assertEqual(self.fold_status(pair), (st.OK_ALL_DUPLICATES, 2))

    def test_china_hold_still_refuses_insert(self):
        from core.china_source_use_hold import SourceUseHold
        os.environ["IPR_CHINA_SOURCE_USE_HOLD"] = "true"
        with self.assertRaises(SourceUseHold):
            self.db.insert_article(normalize_article(handoff.public_raw(
                record(A1, "Fixture headline one"))), self.db.start_scrape_run())


class HeldHashFold(unittest.TestCase):

    def test_held_rows_fold_the_url(self):
        a = normalize_article(handoff.public_raw(record(A2, "Same title", held="non_gt_byline")))
        b = normalize_article(handoff.public_raw(record(A3, "Same title", held="non_gt_byline")))
        self.assertNotEqual(a["content_hash"], b["content_hash"])
        self.assertEqual(a["content_hash"], compute_held_content_hash("Same title", A2))
        # Without the fold the two would collide as reposts of each other.
        self.assertEqual(compute_content_hash("Same title", ""),
                         compute_content_hash("Same title", ""))

    def test_unheld_rows_keep_their_hash(self):
        raw = handoff.public_raw(record(A1, "Same title"))
        self.assertEqual(normalize_article(raw)["content_hash"],
                         compute_content_hash("Same title", BODY))
        for falsy in (None, ""):
            self.assertEqual(normalize_article(dict(raw, text_held=falsy))["content_hash"],
                             compute_content_hash("Same title", BODY))

    def test_fold_never_equals_an_unheld_hash(self):
        self.assertNotEqual(compute_held_content_hash("T", ""), compute_content_hash("T", ""))
        self.assertNotEqual(compute_held_content_hash("T", "U"), compute_content_hash("T", "\nU"))


# ── private collect ──────────────────────────────────────────────────────────

class CollectBase(Isolated):

    def run_once(self, session, run_id="1001-1", target=TARGET):
        state = self.tmp / "custody" / "state"
        code = handoff.run_collect(state, target, SOURCE_EXPLICIT, run_id, COLLECTOR,
                                   scraper_factory=factory(session))
        ledgers = sorted((state / "ledger").glob("*-%s.json" % run_id))
        return state, code, json.loads(ledgers[-1].read_text())

    def versions(self, state):
        conn = sqlite3.connect(str(state / "shadow.db"))
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM capture_versions ORDER BY source_identity, fetched_at")]
        finally:
            conn.close()


class Collect(CollectBase):

    def test_writes_versions_bins_ledger_and_receipt(self):
        session = FakeSession(pages())
        state, code, entry = self.run_once(session)
        self.assertEqual(code, 0)
        rows = self.versions(state)
        self.assertEqual([r["source_identity"] for r in rows], ["gt:900001", "gt:900002"])
        self.assertEqual([r["url"] for r in rows], [A1, A2])   # byte-identical, as listed
        normal, held = rows
        self.assertEqual(normal["capture_sha256"], hashlib.sha256(pages()[A1]).hexdigest())
        self.assertEqual(normal["content_sha256"],
                         normalize_article(legacy_parse(A1, pages()[A1]))["content_hash"])
        self.assertEqual((held["text_held"], held["text_original"]), ("non_gt_byline", ""))
        self.assertEqual(sorted(p.name for p in (state / "captures").iterdir()),
                         [normal["capture_sha256"] + ".bin"])
        self.assertEqual((state / "captures" / (normal["capture_sha256"] + ".bin")).read_bytes(),
                         pages()[A1])
        ledgers = list((state / "ledger").iterdir())
        self.assertEqual(len(ledgers), 1)
        self.assertRegex(ledgers[0].name, r"^[0-9]{8}T[0-9]{6}Z-1001-1\.json$")
        self.assertEqual((entry["schema"], entry["family"], entry["result"], entry["health"]),
                         (attempts.SCHEMA, "global_times_mil", st.OK, "ok"))
        self.assertEqual(entry["window"], ["2026-11-18", "2026-11-20"])
        self.assertEqual((entry["new_versions"], entry["held"], entry["observed"]), (2, 1, 2))
        self.assertEqual(json.loads((state / "private_attempts" / "1001-1.json").read_text()),
                         {"run_id": "1001-1", "collector_exit_status": 0})
        self.assertTrue((state / "clock.json").is_file())
        # The scraper's own window: [target-2, target].
        self.assertEqual(session.calls[0], LISTING)

    def test_reobservation_is_a_new_version_never_a_skip(self):
        state, _, _ = self.run_once(FakeSession(pages()))
        clock = (state / "clock.json").read_text()
        changed = pages(**{A1: page("Fixture headline one", body=BODY + " Corrected.")})
        state, code, entry = self.run_once(FakeSession(changed), run_id="1002-1")
        self.assertEqual(code, 0)
        self.assertEqual((entry["result"], entry["new_versions"], entry["known_versions"]),
                         (st.OK, 1, 1))
        rows = [r for r in self.versions(state) if r["source_identity"] == "gt:900001"]
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["url"] for r in rows}, {A1})
        self.assertEqual(len(list((state / "captures").glob("*.bin"))), 2)
        self.assertEqual((state / "clock.json").read_text(), clock)   # written once
        state, code, entry = self.run_once(FakeSession(changed), run_id="1003-1")
        self.assertEqual((entry["result"], entry["known_versions"]), (st.OK_ALL_DUPLICATES, 2))

    def test_capture_versions_are_append_only(self):
        state, _, _ = self.run_once(FakeSession(pages()))
        conn = sqlite3.connect(str(state / "shadow.db"))
        try:
            for sql in ("UPDATE capture_versions SET title_original = 'x'",
                        "DELETE FROM capture_versions"):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql)
        finally:
            conn.close()

    def test_old_schema_custody_db_is_named_outdated(self):
        state = self.tmp / "custody" / "state"
        state.mkdir(parents=True)
        conn = sqlite3.connect(str(state / "shadow.db"))
        conn.execute("CREATE TABLE capture_versions (source_identity TEXT NOT NULL,"
                     " capture_sha256 TEXT NOT NULL,"
                     " PRIMARY KEY (source_identity, capture_sha256))")
        conn.commit()
        conn.close()
        session = FakeSession(pages())
        _, code, entry = self.run_once(session)
        self.assertEqual((code, entry["result"], entry["error_detail"]),
                         (1, st.STORAGE_FAILURE, "capture_schema_outdated"))
        self.assertEqual(session.calls, [])

    def test_non_canonical_listing_url_is_counted_never_fetched(self):
        http = "http://www.globaltimes.cn/page/202611/900003.shtml"
        session = FakeSession(pages(**{LISTING: listing("/page/202611/900001.shtml", http)}))
        state, code, entry = self.run_once(session)
        self.assertEqual((code, entry["non_canonical"], entry["health"]), (0, 1, "partial"))
        self.assertEqual(entry["error_detail"], "incomplete_window")
        self.assertNotIn(http, session.calls)
        self.assertEqual([r["source_identity"] for r in self.versions(state)], ["gt:900001"])

    def test_listing_failure_writes_failed_ledger_and_receipt(self):
        state, code, entry = self.run_once(FakeSession({}))
        self.assertEqual((code, entry["result"], entry["error_detail"]),
                         (1, st.LISTING_FAILURE, "listing_unreachable"))
        self.assertEqual(json.loads((state / "private_attempts" / "1001-1.json").read_text()),
                         {"run_id": "1001-1", "collector_exit_status": 1})
        self.assertFalse((state / "clock.json").exists())

    def test_article_fetch_failure(self):
        served = pages()
        del served[A1], served[A2]
        state, code, entry = self.run_once(FakeSession(served))
        self.assertEqual((code, entry["result"], entry["error_detail"], entry["fetch_failures"]),
                         (1, st.FETCH_FAILURE, "no_article_retrieved", 2))

    def test_ledger_is_initialised_as_a_failure(self):
        state = self.tmp / "custody" / "state"
        seen = {}

        def explode(target_date, lookback_days):
            [skeleton] = list((state / "ledger").iterdir())
            seen.update(json.loads(skeleton.read_text()))
            raise RuntimeError("fixture crash")

        code = handoff.run_collect(state, TARGET, SOURCE_EXPLICIT, "1001-1", COLLECTOR,
                                   scraper_factory=explode)
        self.assertEqual((seen["result"], seen["health"], seen["error_detail"]),
                         (st.ADAPTER_ERROR, "fail", "collector_incomplete"))
        self.assertEqual(attempts._reduce_ledger(seen)["healthy"], False)
        [final] = list((state / "ledger").iterdir())
        entry = json.loads(final.read_text())
        self.assertEqual((code, entry["result"], entry["error_detail"]),
                         (1, st.ADAPTER_ERROR, "collector_raised"))
        # A run that dies before listing still leaves a valid custody DB.
        self.assertTrue((state / "shadow.db").is_file())

    def test_mid_loop_exception_leaves_no_orphan_capture(self):
        state = self.tmp / "custody" / "state"
        real = GlobalTimesMilScraper.parse_article

        def second_page_raises(scraper, url, html):
            if url == A2:
                raise RuntimeError("fixture parser crash")
            return real(scraper, url, html)

        with patch.object(GlobalTimesMilScraper, "parse_article", second_page_raises):
            state, code, entry = self.run_once(FakeSession(pages()))
        self.assertEqual((code, entry["result"]), (1, st.ADAPTER_ERROR))
        rows = self.versions(state)
        # The page completed before the crash is committed with its bytes;
        # nothing on disk lacks a committed row.
        self.assertEqual([r["source_identity"] for r in rows], ["gt:900001"])
        self.assertEqual(sorted(p.name for p in (state / "captures").iterdir()),
                         [rows[0]["capture_sha256"] + ".bin"])

    def test_failed_page_write_rolls_back_its_row_and_file(self):
        real = handoff._write_capture

        def write_then_fail(captures, sha, wire):
            real(captures, sha, wire)
            raise handoff.HandoffError("capture_write_unverified")

        with patch.object(handoff, "_write_capture", write_then_fail):
            state, code, entry = self.run_once(FakeSession(pages()))
        self.assertEqual((code, entry["result"], entry["error_detail"]),
                         (1, st.STORAGE_FAILURE, "capture_write_unverified"))
        self.assertEqual(self.versions(state), [])
        self.assertEqual(list((state / "captures").iterdir()), [])

    def test_china_hold_skips_with_zero_requests(self):
        os.environ["IPR_CHINA_SOURCE_USE_HOLD"] = "true"
        session = FakeSession(pages())
        state, code, entry = self.run_once(session)
        self.assertEqual((code, entry["result"], entry["health"], entry["error_detail"]),
                         (0, st.SKIPPED_DISABLED, "skipped", "source_use_hold"))
        self.assertEqual(session.calls, [])
        # The schema-only custody DB exists, so the attempt can be persisted.
        self.assertTrue((state / "shadow.db").is_file())
        self.assertEqual(self.versions(state), [])

    def test_cli_refuses_rerun_without_explicit_date_and_writes_nothing(self):
        state = self.tmp / "cli" / "state"
        base = ["collect", "--state-dir", str(state), "--event-name", "schedule",
                "--commit", COLLECTOR]
        self.assertEqual(handoff.main(base + ["--run-id", "5-2", "--run-attempt", "2",
                                              "--cron-utc", "01:17"]), 2)
        self.assertEqual(handoff.main(base + ["--run-id", "5-1", "--run-attempt", "2",
                                              "--target-date", "2026-11-20"]), 2)
        self.assertEqual(handoff.main(["collect", "--state-dir", str(state), "--event-name",
                                       "schedule", "--commit", "not-hex", "--run-id", "5-1",
                                       "--run-attempt", "1", "--target-date", "2026-11-20"]), 2)
        self.assertFalse(state.exists())

    def test_cli_hold_prints_counts_only(self):
        from contextlib import redirect_stdout
        from io import StringIO
        os.environ["IPR_CHINA_SOURCE_USE_HOLD"] = "true"
        out = StringIO()
        with redirect_stdout(out):
            code = handoff.main(["collect", "--state-dir", str(self.tmp / "s"),
                                 "--run-id", "7-1", "--run-attempt", "1",
                                 "--event-name", "workflow_dispatch", "--commit", COLLECTOR,
                                 "--target-date", "2026-11-20"])
        self.assertEqual(code, 0)
        printed = json.loads(out.getvalue())
        self.assertEqual(printed["result"], st.SKIPPED_DISABLED)
        self.assertNotIn("url", printed)


# ── verify and sign, from a committed fresh clone ────────────────────────────

class Custody(CollectBase):
    """A committed custody repository with one healthy attempt."""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "custody"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        self.state, code, _ = self.run_once(FakeSession(pages()))
        self.assertEqual(code, 0)
        self.head = commit(self.repo)
        self.n = 0

    def fresh(self):
        self.n += 1
        return clone(self.repo, self.tmp / ("clone%d" % self.n))

    def now(self):
        return datetime.now(timezone.utc) + timedelta(minutes=1)

    def normal_sha(self):
        return hashlib.sha256(pages()[A1]).hexdigest()

    # verify

    def test_verify_accepts_sound_custody(self):
        self.assertIsNone(handoff.verify_clone(self.fresh(), self.head, COLLECTOR))
        self.assertEqual(handoff.verify_clone(self.fresh(), "e" * 40, COLLECTOR), "head_mismatch")

    def test_verify_detects_tampered_bin(self):
        (self.state / "captures" / (self.normal_sha() + ".bin")).write_bytes(b"tampered")
        head = commit(self.repo)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "capture_digest_mismatch")

    def test_verify_detects_missing_bin(self):
        (self.state / "captures" / (self.normal_sha() + ".bin")).unlink()
        head = commit(self.repo)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR), "capture_missing")

    def test_verify_detects_held_row_with_bytes(self):
        held = pages()[A2]
        (self.state / "captures" / (hashlib.sha256(held).hexdigest() + ".bin")).write_bytes(held)
        head = commit(self.repo)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR), "held_row_retained")

    def test_verify_detects_parse_mismatch(self):
        # Rows an older collector committed in an earlier custody commit are
        # not re-parsed by this one (rows this commit appends always are).
        second = self.healthy_next_run("1002-1")
        self.assertIsNone(handoff.verify_clone(self.fresh(), second, "f" * 40))
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        conn.executescript("DROP TRIGGER capture_versions_no_update;"
                           "UPDATE capture_versions SET text_original = 'not what was served'"
                           " WHERE source_identity = 'gt:900001';")
        conn.commit()
        conn.close()
        head = commit(self.repo)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR), "reparse_mismatch")
        # A committed row rewritten since the parent custody commit is caught
        # even when this collector would not re-parse it.
        self.assertEqual(handoff.verify_clone(self.fresh(), head, "f" * 40),
                         "custody_row_changed")

    def test_held_first_run_persists_verifies_and_signs(self):
        os.environ["IPR_CHINA_SOURCE_USE_HOLD"] = "true"
        repo = self.tmp / "fresh-orphan"
        repo.mkdir()
        git(repo, "init", "-q")
        code = handoff.run_collect(repo / "state", TARGET, SOURCE_EXPLICIT, "2001-1",
                                   COLLECTOR, scraper_factory=factory(FakeSession({})))
        self.assertEqual(code, 0)
        # The private persist step's read-only integrity check.
        conn = sqlite3.connect("file:%s?mode=ro" % (repo / "state" / "shadow.db"), uri=True)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            conn.close()
        head = commit(repo)
        fresh = clone(repo, self.tmp / "fresh-orphan-clone")
        self.assertIsNone(handoff.verify_clone(fresh, head, COLLECTOR))
        env = handoff.build_envelope(fresh, head, KEY, self.now())
        self.assertEqual((env["records"], env["collection"]["latest"]["result"]),
                         ([], st.SKIPPED_DISABLED))

    def test_mid_loop_exception_then_healthy_run_still_verifies(self):
        real = GlobalTimesMilScraper.parse_article

        def second_page_raises(scraper, url, html):
            if url == A2:
                raise RuntimeError("fixture parser crash")
            return real(scraper, url, html)

        changed = pages(**{A1: page("Fixture headline one", body=BODY + " Edited.")})
        with patch.object(GlobalTimesMilScraper, "parse_article", second_page_raises):
            _, code, _ = self.run_once(FakeSession(changed), run_id="1002-1")
        self.assertEqual(code, 1)
        head = commit(self.repo)
        self.assertIsNone(handoff.verify_clone(self.fresh(), head, COLLECTOR))
        again = pages(**{A1: page("Fixture headline one", body=BODY + " Edited twice.")})
        _, code, _ = self.run_once(FakeSession(again), run_id="1003-1")
        self.assertEqual(code, 0)
        head = commit(self.repo)
        self.assertIsNone(handoff.verify_clone(self.fresh(), head, COLLECTOR))

    def run_with(self, run_id, collector, held_by_byline=True):
        import scraper.sources.global_times_mil as gt
        never = __import__("re").compile(r"(?!x)x")
        with patch.object(gt, "_NON_GT_BYLINE_RE",
                          gt._NON_GT_BYLINE_RE if held_by_byline else never):
            return handoff.run_collect(self.state, TARGET, SOURCE_EXPLICIT, run_id,
                                       collector, scraper_factory=factory(FakeSession(pages())))

    def verify_with(self, head, collector, held_by_byline=True):
        import scraper.sources.global_times_mil as gt
        never = __import__("re").compile(r"(?!x)x")
        with patch.object(gt, "_NON_GT_BYLINE_RE",
                          gt._NON_GT_BYLINE_RE if held_by_byline else never):
            return handoff.verify_clone(self.fresh(), head, collector)

    def test_held_then_unheld_same_bytes_records_the_unheld_version(self):
        # A later collector stops holding the same byte-identical page.
        self.assertEqual(self.run_with("1002-1", "e" * 40, held_by_byline=False), 0)
        entry = json.loads(sorted((self.state / "ledger").glob("*-1002-1.json"))[-1].read_text())
        self.assertEqual((entry["result"], entry["new_versions"]), (st.OK, 1))
        rows = [r for r in self.versions(self.state) if r["source_identity"] == "gt:900002"]
        self.assertEqual([r["text_held"] for r in rows], ["non_gt_byline", None])
        self.assertEqual(rows[0]["capture_sha256"], rows[1]["capture_sha256"])
        self.assertTrue((self.state / "captures" / (rows[1]["capture_sha256"] + ".bin")).is_file())
        head = commit(self.repo)
        self.assertIsNone(self.verify_with(head, "e" * 40, held_by_byline=False))
        env = handoff.build_envelope(self.fresh(), head, KEY, self.now())
        rec = {r["source_identity"]: r for r in env["records"]}["gt:900002"]
        self.assertEqual((rec["text_held"], rec["raw_retained"], rec["text_original"]),
                         (None, True, BODY))
        # And back: a still later collector holds it again; nothing breaks.
        self.assertEqual(self.run_with("1003-1", "b" * 40), 0)
        head = commit(self.repo)
        self.assertIsNone(self.verify_with(head, "b" * 40))
        env = handoff.build_envelope(self.fresh(), head, KEY, self.now())
        rec = {r["source_identity"]: r for r in env["records"]}["gt:900002"]
        self.assertEqual((rec["text_held"], rec["raw_retained"]), ("non_gt_byline", False))

    def tamper(self, sql):
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        conn.executescript("DROP TRIGGER capture_versions_no_update;"
                           "DROP TRIGGER capture_versions_no_delete;" + sql)
        conn.commit()
        conn.close()
        return commit(self.repo)

    def test_verify_detects_a_deleted_held_row(self):
        head = self.tamper("DELETE FROM capture_versions WHERE text_held IS NOT NULL;")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_changed")

    def test_verify_detects_insert_or_replace_rewrite(self):
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM capture_versions"
                                " WHERE source_identity = 'gt:900002'").fetchone())
        row["title_original"] = "Rewritten fixture headline"
        conn.execute("INSERT OR REPLACE INTO capture_versions (%s) VALUES (%s)" % (
            ", ".join(row), ", ".join("?" * len(row))), list(row.values()))
        conn.commit()
        conn.close()
        head = commit(self.repo)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, "f" * 40),
                         "custody_row_changed")

    def test_verify_accepts_appended_versions(self):
        changed = pages(**{A1: page("Fixture headline one", body=BODY + " Corrected.")})
        self.run_once(FakeSession(changed), run_id="1002-1")
        head = commit(self.repo)
        self.assertIsNone(handoff.verify_clone(self.fresh(), head, COLLECTOR))

    def test_verify_refuses_a_shallow_clone_that_hides_the_parent(self):
        changed = pages(**{A1: page("Fixture headline one", body=BODY + " Corrected.")})
        self.run_once(FakeSession(changed), run_id="1002-1")
        head = commit(self.repo)
        shallow = self.tmp / "shallow"
        subprocess.run(GIT + ["clone", "-q", "--depth", "1", "file://" + str(self.repo),
                              str(shallow)], check=True, capture_output=True)
        self.assertEqual(handoff.verify_clone(shallow, head, COLLECTOR),
                         "parent_custody_unverifiable")
        # A full clone of the same commit is sound.
        self.assertIsNone(handoff.verify_clone(self.fresh(), head, COLLECTOR))

    def healthy_next_run(self, run_id):
        """The next routine attempt on top of whatever HEAD now holds."""
        _, code, entry = self.run_once(FakeSession(pages()), run_id=run_id)
        self.assertEqual(code, 0)
        return commit(self.repo)

    def append_row(self, **over):
        conn = sqlite3.connect(str(self.state / "shadow.db"))
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM capture_versions"
                                " WHERE source_identity = 'gt:900001'").fetchone())
        row.pop("version_seq")
        row.update(over)
        conn.execute("INSERT INTO capture_versions (%s) VALUES (%s)" % (
            ", ".join(row), ", ".join("?" * len(row))), list(row.values()))
        conn.commit()
        conn.close()
        return commit(self.repo)

    def test_rewritten_held_row_stays_caught_after_a_healthy_run(self):
        # A consistent rewrite: a new title and a recomputed content hash.
        raw = {"url": A2, "source_slug": handoff.SOURCE_SLUG,
               "title_original": "Forged fixture headline", "text_original": "",
               "published_date": "2026-11-20", "content_verdict": None,
               "text_held": "non_gt_byline"}
        head = self.tamper(
            "UPDATE capture_versions SET title_original = 'Forged fixture headline',"
            " content_sha256 = '%s' WHERE source_identity = 'gt:900002';"
            % handoff.content_sha256(raw))
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_changed")
        head = self.healthy_next_run("1002-1")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_changed")

    def test_deleted_held_row_stays_caught_after_a_healthy_run(self):
        head = self.tamper("DELETE FROM capture_versions WHERE text_held IS NOT NULL;")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_changed")
        head = self.healthy_next_run("1002-1")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_changed")

    def test_appended_row_of_a_foreign_collector_is_refused_and_stays_refused(self):
        # The genuine bytes, an invented body, a self-consistent hash: only a
        # re-parse would catch it, and a foreign collector id would skip one.
        raw = {"url": A1, "source_slug": handoff.SOURCE_SLUG,
               "title_original": "Fixture headline one",
               "text_original": "Invented body that the bytes never said.",
               "published_date": "2026-11-20", "content_verdict": None}
        head = self.append_row(text_original=raw["text_original"],
                               content_sha256=handoff.content_sha256(raw),
                               fetched_at=handoff._stamp(datetime.now(timezone.utc)),
                               collector_commit="a" * 40)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_unattributed")
        head = self.healthy_next_run("1002-1")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_unattributed")

    def test_appended_row_with_a_low_version_seq_is_refused(self):
        # Other bytes that parse to the same record, ordered ahead of the
        # genuine version so recover() would pick them first.
        other = page("Fixture headline one").replace(b"<body>", b"<body><!-- x -->")
        sha = hashlib.sha256(other).hexdigest()
        (self.state / "captures" / (sha + ".bin")).write_bytes(other)
        head = self.append_row(version_seq=-5, capture_sha256=sha)
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_out_of_order")
        head = self.healthy_next_run("1002-1")
        self.assertEqual(handoff.verify_clone(self.fresh(), head, COLLECTOR),
                         "custody_row_out_of_order")

    def test_verify_refuses_a_depth_two_shallow_clone(self):
        for n, run_id in enumerate(("1002-1", "1003-1")):
            changed = pages(**{A1: page("Fixture headline one",
                                        body=BODY + " Corrected %d." % n)})
            self.run_once(FakeSession(changed), run_id=run_id)
            head = commit(self.repo)
        shallow = self.tmp / "shallow2"
        subprocess.run(GIT + ["clone", "-q", "--depth", "2", "file://" + str(self.repo),
                              str(shallow)], check=True, capture_output=True)
        self.assertEqual(handoff.verify_clone(shallow, head, COLLECTOR),
                         "parent_custody_unverifiable")
        self.assertIsNone(handoff.verify_clone(self.fresh(), head, COLLECTOR))

    def test_verify_refuses_a_working_tree_db_that_is_not_head(self):
        fresh = self.fresh()
        conn = sqlite3.connect(str(fresh / "state" / "shadow.db"))
        conn.execute("CREATE TABLE extra (x)")
        conn.commit()
        conn.close()
        self.assertEqual(handoff.verify_clone(fresh, self.head, COLLECTOR),
                         "custody_db_uncommitted")

    def test_recover_accepts_a_sqlite_row(self):
        db_path, captures = self.state / "shadow.db", self.state / "captures"
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        public = self.public_a1()
        row = conn.execute("SELECT ? AS url, ? AS content_hash, ? AS published_date",
                           (public["url"], public["content_hash"],
                            public["published_date"])).fetchone()
        conn.close()
        self.assertEqual(handoff.recover(row, db_path, captures),
                         {"status": "recovered", "capture_sha256": self.normal_sha()})

    def test_cli_verify(self):
        clone_dir = self.fresh()
        self.assertEqual(handoff.main(["verify", "--clone", str(clone_dir), "--expect-head",
                                       self.head, "--collector-commit", COLLECTOR]), 0)

    # sign

    def test_sign_builds_a_verifiable_envelope(self):
        env = handoff.build_envelope(self.fresh(), self.head, KEY, self.now())
        self.assertEqual(env["custody_commit"], self.head)
        self.assertIs(env["collection"]["attested"], True)
        self.assertEqual(env["collection"]["latest_healthy_target_date"], "2026-11-20")
        recs = {r["source_identity"]: r for r in env["records"]}
        self.assertEqual(set(recs), {"gt:900001", "gt:900002"})
        self.assertIs(recs["gt:900001"]["raw_retained"], True)
        self.assertEqual((recs["gt:900002"]["raw_retained"], recs["gt:900002"]["text_original"]),
                         (False, ""))
        self.assertEqual(handoff.verify_envelope(handoff.canonical(env), KEY), env)

    def test_sign_refuses_without_key(self):
        with self.assertRaises(handoff.HandoffError) as ctx:
            handoff.build_envelope(self.fresh(), self.head, "", self.now())
        self.assertEqual(str(ctx.exception), "gt_handoff_key_unavailable")
        out = self.tmp / "out.json"
        self.assertEqual(handoff.main(["sign", "--clone", str(self.fresh()), "--commit",
                                       self.head, "--out", str(out)]), 1)
        self.assertFalse(out.exists())
        os.environ[handoff.KEY_ENV] = KEY
        self.assertEqual(handoff.main(["sign", "--clone", str(self.fresh()), "--commit",
                                       self.head, "--out", str(out)]), 0)
        self.assertEqual(handoff.load_envelope(out, KEY, now=FRESH)[1], None)

    def test_sign_uses_the_committed_clone_only(self):
        clone_dir = self.fresh()
        # Work in the collector checkout after the commit is invisible to sign.
        self.run_once(FakeSession(pages(**{
            LISTING: listing("/page/202611/900001.shtml", "/page/202611/900003.shtml"),
            A3: page("Fixture headline three")})), run_id="1002-1")
        env = handoff.build_envelope(clone_dir, self.head, KEY, self.now())
        self.assertEqual({r["source_identity"] for r in env["records"]},
                         {"gt:900001", "gt:900002"})
        with self.assertRaises(handoff.HandoffError) as ctx:
            handoff.build_envelope(clone_dir, "e" * 40, KEY, self.now())
        self.assertEqual(str(ctx.exception), "clone_head_mismatch")
        (clone_dir / "stray.txt").write_text("x")
        with self.assertRaises(handoff.HandoffError) as ctx:
            handoff.build_envelope(clone_dir, self.head, KEY, self.now())
        self.assertEqual(str(ctx.exception), "clone_not_clean")

    def test_sign_carries_latest_version_within_three_days(self):
        changed = pages(**{A1: page("Fixture headline one", body=BODY + " Corrected.")})
        self.run_once(FakeSession(changed), run_id="1002-1")
        head = commit(self.repo)
        clone_dir = self.fresh()
        env = handoff.build_envelope(clone_dir, head, KEY, self.now())
        rec = {r["source_identity"]: r for r in env["records"]}["gt:900001"]
        self.assertEqual(rec["source_run"], "1002-1")
        self.assertEqual(rec["text_original"], BODY + " Corrected.")
        later = handoff.build_envelope(clone_dir, head, KEY, self.now() + timedelta(days=4))
        self.assertEqual(later["records"], [])

    def test_sign_refuses_oversize(self):
        size = len(handoff.canonical(
            handoff.build_envelope(self.fresh(), self.head, KEY, self.now())))
        with patch.object(handoff, "MAX_ENVELOPE_BYTES", size - 1):
            with self.assertRaises(handoff.HandoffError) as ctx:
                handoff.build_envelope(self.fresh(), self.head, KEY, self.now())
        self.assertEqual(str(ctx.exception), "gt_handoff_envelope_too_large")

    def test_uncommitted_ledger_gives_no_envelope_and_last_one_goes_stale(self):
        good = handoff.build_envelope(self.fresh(), self.head, KEY, self.now())
        path = self.write(good)
        # A new empty custody repo: the attempt ran but its commit never landed.
        other = self.tmp / "unpushed"
        other.mkdir()
        git(other, "init", "-q")
        empty_head = commit(other)
        handoff.run_collect(other / "state", TARGET, SOURCE_EXPLICIT, "1002-1", COLLECTOR,
                            scraper_factory=factory(FakeSession(pages())))
        with self.assertRaises(handoff.HandoffError) as ctx:
            handoff.build_envelope(clone(other, self.tmp / "unpushed-clone"), empty_head,
                                   KEY, self.now())
        self.assertEqual(str(ctx.exception), "collection_not_attested")
        # The public side keeps the last envelope until the slot plus grace.
        self.assertIsNone(handoff.load_envelope(path, KEY, now=FRESH)[1])
        records, status, detail = handoff.load_envelope(path, KEY, now=STALE)
        self.assertEqual((records, status), ([], st.FETCH_FAILURE))
        self.assertTrue(detail.startswith("collection stale"))

    def test_committed_failed_attempt_fails_the_public_source(self):
        shutil.rmtree(self.tmp / "cache")   # the listing is disk-cached per target date
        self.run_once(FakeSession({}), run_id="1002-1")
        head = commit(self.repo)
        env = handoff.build_envelope(self.fresh(), head, KEY, self.now())
        self.assertEqual(env["collection"]["latest"]["result"], st.LISTING_FAILURE)
        records, status, detail = handoff.load_envelope(self.write(env), KEY, now=FRESH)
        self.assertEqual((records, status), ([], st.LISTING_FAILURE))
        self.assertIn("run 1002-1", detail)

    # recovery

    def public_a1(self):
        public = normalize_article(legacy_parse(A1, pages()[A1]))
        return {"url": A1, "content_hash": public["content_hash"],
                "published_date": public["published_date"]}

    def test_recover_ties_a_public_row_to_its_capture(self):
        db_path, captures = self.state / "shadow.db", self.state / "captures"
        self.assertEqual(handoff.recover(self.public_a1(), db_path, captures),
                         {"status": "recovered", "capture_sha256": self.normal_sha()})
        self.assertEqual(handoff.recover({"url": A2, "content_hash": "0" * 64},
                                         db_path, captures)["status"], "held_no_bytes")
        self.assertEqual(handoff.recover({"url": A3, "content_hash": "0" * 64},
                                         db_path, captures)["status"], "no_version")
        self.assertEqual(handoff.recover({"url": A1, "content_hash": "0" * 64,
                                          "published_date": "2026-11-20"},
                                         db_path, captures)["status"], "no_match")

    def test_recover_requires_the_public_date_and_the_recorded_hash(self):
        db_path, captures = self.state / "shadow.db", self.state / "captures"
        # An earlier, self-consistent version with the same title and body
        # but another publication date is not the public row's version.
        forged = page("Fixture headline one", pub="Published: Nov 19, 2026 09:00 AM")
        sha = hashlib.sha256(forged).hexdigest()
        (captures / (sha + ".bin")).write_bytes(forged)
        parsed = legacy_parse(A1, forged)
        self.assertEqual(parsed["published_date"], "2026-11-19")
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO capture_versions (source_identity, url, title_original,"
            " text_original, published_date, content_verdict, text_held, byline,"
            " pub_time, content_type, capture_sha256, content_sha256, fetched_at,"
            " source_run, collector_commit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("gt:900001", A1, parsed["title_original"], parsed["text_original"],
             parsed["published_date"], None, None, None, None,
             "text/html; charset=utf-8", sha, handoff.content_sha256(
                 handoff.public_raw(parsed)), "2000-01-01T00:00:00Z", "999-1", COLLECTOR))
        conn.commit()
        conn.close()
        self.assertEqual(handoff.recover(self.public_a1(), db_path, captures),
                         {"status": "recovered", "capture_sha256": self.normal_sha()})
        # Without the public date nothing can be tied to an exact version.
        public = dict(self.public_a1())
        del public["published_date"]
        self.assertEqual(handoff.recover(public, db_path, captures)["status"], "no_match")

    def test_recover_reports_parser_drift_separately(self):
        db_path, captures = self.state / "shadow.db", self.state / "captures"
        public = self.public_a1()   # what the public archive stored
        real = GlobalTimesMilScraper.parse_article

        def drifted(scraper, url, html):
            article = real(scraper, url, html)
            return dict(article, text_original=article["text_original"] + " drift")

        with patch.object(GlobalTimesMilScraper, "parse_article", drifted):
            self.assertEqual(handoff.recover(public, db_path, captures),
                             {"status": "parser_drift", "capture_sha256": self.normal_sha()})

        def raises(scraper, url, html):
            raise RuntimeError("fixture parser crash")

        with patch.object(GlobalTimesMilScraper, "parse_article", raises):
            self.assertEqual(handoff.recover(public, db_path, captures),
                             {"status": "reparse_failed", "capture_sha256": self.normal_sha()})


# ── wiring: manifest, imports, fetch step, workflow ──────────────────────────

class Wiring(Isolated):

    def test_manifest_names_the_replay_adapter_only(self):
        manifest = json.loads((ROOT / "desks/china/manifest.json").read_text())
        [gt] = [s for s in manifest["sources"] if s["slug"] == "global_times_mil"]
        self.assertEqual(gt["adapter"], "adapters.global_times_handoff:GlobalTimesHandoffAdapter")
        self.assertEqual(gt["access_method"], "html")
        for path in ROOT.glob("desks/*/manifest.json"):
            self.assertNotIn("GlobalTimesMilScraper", path.read_text(), path)
        from core.registry import get_registry
        self.assertIsInstance(get_registry(refresh=True).get_adapter("global_times_mil"),
                              GlobalTimesHandoffAdapter)

    def test_adapter_imports_no_network_library(self):
        banned = ("requests", "httpx", "urllib.request", "playwright", "aiohttp", "socket")
        probe = ("import sys; import adapters.global_times_handoff; "
                 "print([m for m in %r if m in sys.modules])" % (banned,))
        out = subprocess.run([sys.executable, "-c", probe], cwd=str(ROOT), check=True,
                             capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=str(ROOT))).stdout.strip()
        self.assertEqual(out, "[]")
        for module in ("adapters/global_times_handoff.py",):
            tree = ast.parse((ROOT / module).read_text())
            names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            names |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            self.assertFalse({n for n in names if n.split(".")[0] in
                              ("requests", "httpx", "playwright", "aiohttp", "socket")}
                             | ({"urllib.request"} & names), module)

    def test_fetch_block_requires_exact_true_and_unlinks_stale_file(self):
        from scripts import fetch_daily_machine_outputs as fetch
        for value in (None, "", "false", "True", "TRUE", "true ", "1", "true"):
            with self.subTest(value=value):
                stale = self.tmp / handoff.ENVELOPE_NAME
                stale.write_text("old envelope")
                env = {"IPR_PRIVATE_DAILY_ENABLED": "true",
                       "IPR_DAILY_INTAKE_DIR": str(self.tmp)}
                if value is not None:
                    env["CN_GLOBAL_TIMES_HANDOFF_ENABLED"] = value
                calls = []
                with patch.dict(os.environ, env), \
                        patch.object(fetch, "_fetch",
                                     side_effect=lambda *a: calls.append(a) or "fetch_failed"):
                    if value is None:
                        os.environ.pop("CN_GLOBAL_TIMES_HANDOFF_ENABLED", None)
                    results = fetch.main()
                gt_calls = [c for c in calls if c[0] == handoff.ENVELOPE_NAME]
                self.assertFalse(stale.exists())
                if value == "true":
                    self.assertEqual(gt_calls, [(handoff.ENVELOPE_NAME, stale,
                                                 "state/global-times-captures")])
                    self.assertEqual(results[handoff.ENVELOPE_NAME], "fetch_failed")
                else:
                    self.assertEqual(gt_calls, [])
                    self.assertNotIn(handoff.ENVELOPE_NAME, results)

    def test_secret_only_in_pipeline_step_and_switch_only_in_fetch_step(self):
        workflow = (ROOT / ".github/workflows/daily_update.yml").read_text()
        steps = workflow.split("\n      - name: ")
        secret = [s for s in steps if "DAILY_GLOBAL_TIMES_MIL_KEY" in s]
        self.assertEqual(len(secret), 1)
        self.assertIn("id: pipeline", secret[0])
        self.assertEqual(workflow.count("secrets.DAILY_GLOBAL_TIMES_MIL_KEY"), 1)
        switch = [s for s in steps if "CN_GLOBAL_TIMES_HANDOFF_ENABLED" in s]
        self.assertEqual(len(switch), 1)
        self.assertIn("id: shared_daily_fetch", switch[0])
        self.assertIn("CN_GLOBAL_TIMES_HANDOFF_ENABLED: ${{ vars.CN_GLOBAL_TIMES_HANDOFF_ENABLED }}",
                      switch[0])
        # The private collector's own switches never appear in the public workflow.
        self.assertNotIn("CN_GLOBAL_TIMES_PRIVATE_COLLECTION_ENABLED", workflow)

    def test_fetch_is_not_a_shared_daily_source(self):
        from scripts import fetch_daily_machine_outputs as fetch
        self.assertNotIn("global_times_mil", fetch.SOURCES)


if __name__ == "__main__":
    unittest.main()
