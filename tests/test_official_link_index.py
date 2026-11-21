"""Bounded Indonesia/Korea desk lists and their full official-link indexes.

The desk pages list the newest DESK_LINK_LIMIT admitted rows; a hub and one
page per publisher-posted month carry every admitted row exactly once. These
tests build a real site from the production database with synthetic admitted
rows layered over the loaders (no DB writes), then prove the renderer, the
local/deployed/HTTPS readbacks, the pre-commit budget gate and the writer
workflow text all fail closed.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core import official_link_index as link_index
from core import korea_official_live_links as korea_live
from core import regional_official_link_render as regional_render
import scripts.verify_korea_official_link_index as korea_readback
import scripts.verify_regional_source_index_readback as readback
from scripts.verify_regional_source_index_readback import ReadbackHold

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "pla_watch.db"
WORKFLOWS = ROOT / ".github" / "workflows"
PYTHON = sys.executable

ID_MONTHS = (("2026-11", 30, 30), ("2026-10", 30, 31), ("2026-09", 15, 30))


def indonesia_rows():
    """75 synthetic Kemhan rows, newest first, over three months (30/30/15)."""
    rows = []
    for month, count, last_day in ID_MONTHS:
        year, mm = month.split("-")
        for i in range(count):
            day = "%s-%02d" % (month, last_day - i)
            slug = "/%s/%s/%02d/ipr-synthetic-%s-%02d.html" % (
                year, mm, last_day - i, month, i)
            rows.append({
                "source_identity": "kemhan:" + slug,
                "canonical_official_url": "https://www.kemhan.go.id" + slug,
                "publisher_posted_date": day,
                "label": "Kemhan Berita official source",
                "publisher_label": "Indonesian Ministry of Defense — Berita",
            })
    return rows


def philippines_rows():
    """65 synthetic AFP rows: the Philippines desk keeps its full list."""
    return [{
        "source_identity": "afp:%d" % (990000 + i),
        "canonical_official_url": "https://www.afp.mil.ph/news/ipr-synthetic-%d" % i,
        "publisher_posted_date": "2026-11-%02d" % (20 - i // 4),
        "label": "AFP official source",
        "publisher_label": "Armed Forces of the Philippines",
    } for i in range(65)]


def korea_synthetic_rows():
    """30 synthetic MND rows newer than every committed row (21 Nov 2026)."""
    return [{
        "source_identity": "korea-policy:%d" % (999999999 - i),
        "source_url": korea_live.PREFIX + str(999999999 - i),
        "published_date": "2026-11-21",
        "issuer_label": "Republic of Korea Ministry of National Defense",
        "issuer_original_label": "국방부",
        "republisher_label": "Republic of Korea Policy Briefing",
        "neutral_label": "MND official press release %d" % (999999999 - i),
    } for i in range(30)]


ID_ROWS = indonesia_rows()
PH_ROWS = philippines_rows()
KOREA_EXTRA = korea_synthetic_rows()
_ORIGINAL_REGIONAL = regional_render.load_admitted_links
_ORIGINAL_KOREA = korea_live.load_live_korea_official_links


def fake_regional(db_path, desk):
    if desk == "indonesia":
        return [dict(r) for r in ID_ROWS]
    if desk == "philippines":
        return [dict(r) for r in PH_ROWS]
    return _ORIGINAL_REGIONAL(db_path, desk)


def fake_korea(db_path, *, exclude=()):
    excluded = set(exclude)
    real = _ORIGINAL_KOREA(db_path, exclude=exclude)
    return [dict(r) for r in KOREA_EXTRA if r["source_identity"] not in excluded] + real


ROW = {"indonesia": r'<li data-regional-official-source-id="([^"]+)">.*?</li>',
       "korea": r'<li data-korea-auto-official-link="([^"]+)">.*?</li>'}


def rows_in(html, desk):
    return [(m.group(1), m.group(0)) for m in re.finditer(ROW[desk], html, re.S)]


class CoreIndexTests(unittest.TestCase):
    def test_latest_bounds_without_resorting(self):
        shown = link_index.latest("indonesia", ID_ROWS)
        self.assertEqual(shown, ID_ROWS[:60])
        self.assertEqual(link_index.latest("indonesia", ID_ROWS[:59]), ID_ROWS[:59])
        self.assertEqual(link_index.latest("indonesia", []), [])

    def test_partition_routes_and_labels(self):
        months = link_index.partition("indonesia", ID_ROWS)
        self.assertEqual([(m, len(items)) for m, items in months],
                         [("2026-11", 30), ("2026-10", 30), ("2026-09", 15)])
        self.assertEqual(sum((items for _, items in months), []), ID_ROWS)
        self.assertEqual(link_index.index_routes("indonesia", ID_ROWS), [
            "indonesia-official-links.html",
            "indonesia-official-links/2026-11.html",
            "indonesia-official-links/2026-10.html",
            "indonesia-official-links/2026-09.html"])
        self.assertEqual(link_index.index_routes("korea", []), [])
        self.assertEqual(link_index.month_label("2026-09"), "September 2026")
        self.assertEqual(link_index.hub_route("korea"), "korea-official-links.html")

    def test_holds_instead_of_guessing(self):
        swapped = [ID_ROWS[40]] + ID_ROWS[:40] + ID_ROWS[41:]
        cases = {
            "misordered": swapped,
            "duplicate": ID_ROWS[:3] + [ID_ROWS[1]],
            "missing identity": [dict(ID_ROWS[0], source_identity="")],
            "bad date": [dict(ID_ROWS[0], publisher_posted_date="20 Nov 2026")],
            "impossible date": [dict(ID_ROWS[0], publisher_posted_date="2026-02-30")],
            "no date": [{"source_identity": "kemhan:/x"}],
        }
        for label, rows in cases.items():
            with self.subTest(label), self.assertRaises(link_index.IndexHold):
                link_index.partition("indonesia", rows)
            with self.subTest(label + " latest"), self.assertRaises(link_index.IndexHold):
                link_index.latest("indonesia", rows)
        for month in ("2026-13", "2026-1", "26-11", "../x"):
            with self.subTest(month), self.assertRaises(link_index.IndexHold):
                link_index.month_route("indonesia", month)
        for desk in ("philippines", "vietnam", "japan"):
            with self.subTest(desk), self.assertRaises(link_index.IndexHold):
                link_index.hub_route(desk)

    def test_stale_month_and_empty_index_are_removed(self):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as preview
        desk = types.SimpleNamespace(slug="indonesia")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            folder = out / "indonesia-official-links"
            folder.mkdir()
            (folder / "2026-08.html").write_text("stale", encoding="utf-8")
            (folder / "2026-11.html").write_text("old", encoding="utf-8")
            pages = {"indonesia-official-links.html": "hub",
                     "indonesia-official-links/2026-11.html": "new"}
            with mock.patch.object(preview, "render_official_link_index",
                                   return_value=pages):
                written = preview.write_official_link_index(None, out, desk, ID_ROWS[:30])
            self.assertEqual(sorted(written), sorted(pages))
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["2026-11.html"])
            self.assertEqual((folder / "2026-11.html").read_text(encoding="utf-8"), "new")
            with mock.patch.object(preview, "render_official_link_index",
                                   return_value={}):
                self.assertEqual(preview.write_official_link_index(None, out, desk, []), [])
            self.assertFalse((out / "indonesia-official-links.html").exists())
            self.assertFalse(folder.exists())


@unittest.skipUnless(DB.is_file(), "production database required")
class RenderedIndexTests(unittest.TestCase):
    """One real build with synthetic admitted rows; every gate is exercised."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as preview
        cls.patches = [
            mock.patch.object(regional_render, "load_admitted_links", fake_regional),
            mock.patch.object(readback, "load_admitted_links", fake_regional),
            mock.patch.object(korea_live, "load_live_korea_official_links", fake_korea),
        ]
        for patch in cls.patches:
            patch.start()
        cls.tmp = tempfile.TemporaryDirectory(prefix="ipr-official-link-index-")
        cls.out = Path(cls.tmp.name) / "output"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                preview.build(cls.out, "Indo-Pacific Record", DB,
                              snapshot=preview.snapshot_from_corpus(DB),
                              site_origin="https://indopacificrecord.org")
        except Exception:
            cls.tearDownClass()
            raise
        cls.korea_rows = korea_readback.korea_index_rows(DB)

    @classmethod
    def tearDownClass(cls):
        for patch in cls.patches:
            patch.stop()
        cls.tmp.cleanup()

    # -- helpers ---------------------------------------------------------
    def read(self, route):
        return (self.out / route).read_text(encoding="utf-8")

    @contextlib.contextmanager
    def mutated(self, route, change):
        path = self.out / route
        original = path.read_bytes()
        changed = change(original.decode("utf-8"))
        self.assertNotEqual(changed.encode("utf-8"), original, route)
        path.write_text(changed, encoding="utf-8")
        try:
            yield
        finally:
            path.write_bytes(original)

    def indonesia_holds(self, reason=None, **kwargs):
        ctx = (self.assertRaisesRegex(ReadbackHold, "^%s$" % reason) if reason
               else self.assertRaises(ReadbackHold))
        with ctx:
            readback.verify(DB, self.out, required_desks=("indonesia",), **kwargs)

    def korea_holds(self, reason=None, **kwargs):
        ctx = (self.assertRaisesRegex(ReadbackHold, "^%s$" % reason) if reason
               else self.assertRaises(ReadbackHold))
        with ctx:
            korea_readback.verify(DB, self.out, rows=self.korea_rows, **kwargs)

    def make_pages_dir(self, desk_routes):
        pages = Path(self.tmp.name) / "pages"
        if pages.exists():
            shutil.rmtree(pages)
        pages.mkdir()
        for route in desk_routes:
            target = pages / route
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.out / route, target)
        return pages

    # -- renderer --------------------------------------------------------
    def test_indonesia_desk_is_bounded_and_index_carries_every_row(self):
        desk = self.read("indonesia.html")
        self.assertEqual([sid for sid, _ in rows_in(desk, "indonesia")],
                         [r["source_identity"] for r in ID_ROWS[:60]])
        self.assertEqual(desk.count('href="indonesia-official-links.html"'), 1)
        self.assertEqual(
            sorted(p.name for p in (self.out / "indonesia-official-links").iterdir()),
            ["2026-09.html", "2026-10.html", "2026-11.html"])
        union = []
        for month, items in link_index.partition("indonesia", ID_ROWS):
            page = self.read(link_index.month_route("indonesia", month))
            ids = [sid for sid, _ in rows_in(page, "indonesia")]
            self.assertEqual(ids, [r["source_identity"] for r in items])
            union += ids
        self.assertEqual(union, [r["source_identity"] for r in ID_ROWS])
        hub = self.read("indonesia-official-links.html")
        self.assertIn('data-official-link-total="75"', hub)
        self.assertNotIn("data-regional-official-source-id", hub)
        for month, count in (("2026-11", 30), ("2026-10", 30), ("2026-09", 15)):
            self.assertIn('data-official-link-month="%s" data-official-link-month-count="%d"'
                          % (month, count), hub)

    def test_korea_desk_is_bounded_and_index_carries_every_row(self):
        rows = self.korea_rows
        self.assertGreater(len(rows), link_index.DESK_LINK_LIMIT)
        desk = self.read("korea.html")
        self.assertEqual([sid for sid, _ in rows_in(desk, "korea")],
                         [r["source_identity"] for r in rows[:60]])
        self.assertEqual(desk.count('href="korea-official-links.html"'), 1)
        union = []
        for route in link_index.index_routes("korea", rows)[1:]:
            union += [sid for sid, _ in rows_in(self.read(route), "korea")]
        self.assertEqual(union, [r["source_identity"] for r in rows])
        # The archive search index keeps every auto row, including those
        # past the desk bound.
        archive = self.read("archive-research-index.json")
        self.assertTrue(json.loads(archive))
        for row in rows[60:]:
            self.assertNotIn('data-korea-auto-official-link="%s"' % row["source_identity"], desk)
            self.assertIn(row["source_url"], archive)

    def test_philippines_and_vietnam_keep_full_lists_and_no_index(self):
        ph = self.read("philippines.html")
        self.assertEqual(ph.count("data-regional-official-source-id="), len(PH_ROWS))
        for row in PH_ROWS:
            self.assertIn('data-regional-official-source-id="%s"' % row["source_identity"], ph)
        for slug in ("philippines", "vietnam", "japan"):
            self.assertFalse((self.out / ("%s-official-links.html" % slug)).exists())
            self.assertFalse((self.out / ("%s-official-links" % slug)).exists())
        readback.verify(DB, self.out, required_desks=("philippines",))

    def test_index_routes_fit_the_default_budget(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_frontend_delivery as budget
        routes = (link_index.index_routes("indonesia", ID_ROWS)
                  + link_index.index_routes("korea", self.korea_rows))
        for route in routes:
            self.assertEqual(budget.html_css_cap(route), 120000, route)
        result = budget.verify(self.out, only=routes + ["indonesia.html", "korea.html"])
        self.assertEqual(result["failures"], [])

    def test_sitemap_lists_index_routes(self):
        sitemap = self.read("sitemap.xml")
        for route in link_index.index_routes("indonesia", ID_ROWS):
            self.assertIn("/" + route + "<", sitemap)

    # -- Indonesia local readback ----------------------------------------
    def test_indonesia_readback_accepts_exact_build(self):
        receipt = readback.verify(DB, self.out, required_desks=("indonesia",))
        family = receipt["source_families"]["id_kemhan_news"]
        self.assertEqual(family["admitted_official_link_count"], 75)
        self.assertEqual(family["desk_official_link_count"], 60)
        self.assertEqual(family["full_index"]["months"],
                         {"2026-11": 30, "2026-10": 30, "2026-09": 15})
        self.assertEqual(readback.index_routes(DB, "indonesia"),
                         ["indonesia.html"] + link_index.index_routes("indonesia", ID_ROWS))

    def test_indonesia_desk_mutations_hold(self):
        desk = "indonesia.html"
        month_09 = self.read("indonesia-official-links/2026-09.html")
        row_60 = rows_in(month_09, "indonesia")[0][1]
        self.assertIn(ID_ROWS[60]["source_identity"], row_60)

        def lis(html):
            return rows_in(html, "indonesia")

        def add_61(html):
            last = lis(html)[-1][1]
            return html.replace(last, last + row_60, 1)

        def drop_last(html):
            return html.replace(lis(html)[-1][1], "", 1)

        def swap(html):
            a, b = lis(html)[0][1], lis(html)[1][1]
            return html.replace(a + b, b + a, 1) if a + b in html else \
                html.replace(a, "\0", 1).replace(b, a, 1).replace("\0", b, 1)

        def older_in(html):
            return html.replace(lis(html)[-1][1], row_60, 1)

        def no_hub(html):
            return html.replace('href="indonesia-official-links.html"', 'href="archive.html"')

        def two_hubs(html):
            return html.replace('href="indonesia-official-links.html"',
                                'href="indonesia-official-links.html"></a><a '
                                'href="indonesia-official-links.html"', 1)

        for label, change in (("61 rows", add_61), ("59 rows", drop_last),
                              ("wrong order", swap), ("older row swapped in", older_in)):
            with self.subTest(label), self.mutated(desk, change):
                self.indonesia_holds()
        for label, change in (("no hub link", no_hub), ("two hub links", two_hubs)):
            with self.subTest(label), self.mutated(desk, change):
                self.indonesia_holds("desk_page_full_index_link_missing_or_repeated")

    def test_indonesia_month_mutations_hold(self):
        nov, oct_ = ("indonesia-official-links/2026-11.html",
                     "indonesia-official-links/2026-10.html")
        nov_rows = rows_in(self.read(nov), "indonesia")

        def lis(html):
            return rows_in(html, "indonesia")

        def missing(html):
            return html.replace(lis(html)[3][1], "", 1)

        def unadmitted(html):
            sid, li = lis(html)[0]
            fake = li.replace(sid, "kemhan:/2026/10/31/ipr-unadmitted.html").replace(
                sid.split(":", 1)[1], "/2026/10/31/ipr-unadmitted.html")
            return html.replace(li, fake + li, 1)

        def duplicate_from_other_month(html):
            first = lis(html)[0][1]
            return html.replace(first, nov_rows[0][1] + first, 1)

        for label, change in (("month missing a row", missing),
                              ("unadmitted row", unadmitted),
                              ("same id in two months", duplicate_from_other_month)):
            with self.subTest(label), self.mutated(oct_, change):
                self.indonesia_holds()
        # A row moved to the wrong month: gone from November, present in October.
        moved = nov_rows[-1][1]
        with self.mutated(nov, lambda h: h.replace(moved, "", 1)), \
                self.mutated(oct_, lambda h: h.replace(lis(h)[0][1], moved + lis(h)[0][1], 1)):
            self.indonesia_holds()

    def test_indonesia_month_inventory_and_hub_mutations_hold(self):
        folder = self.out / "indonesia-official-links"
        orphan = folder / "2026-08.html"
        orphan.write_bytes((folder / "2026-09.html").read_bytes())
        try:
            self.indonesia_holds("official_link_index_month_pages_disagree_with_db")
        finally:
            orphan.unlink()
        missing = folder / "2026-09.html"
        saved = missing.read_bytes()
        missing.unlink()
        try:
            self.indonesia_holds("official_link_index_month_pages_disagree_with_db")
        finally:
            missing.write_bytes(saved)
        hub = "indonesia-official-links.html"
        saved_hub = (self.out / hub).read_bytes()
        (self.out / hub).unlink()
        try:
            self.indonesia_holds("official_link_index_hub_missing")
        finally:
            (self.out / hub).write_bytes(saved_hub)
        cases = (
            ("hub total", lambda h: h.replace('data-official-link-total="75"',
                                              'data-official-link-total="74"'),
             "official_link_index_hub_total_disagrees_with_db"),
            ("hub month count", lambda h: h.replace('data-official-link-month-count="15"',
                                                    'data-official-link-month-count="16"'),
             "official_link_index_hub_months_disagree_with_db"),
            ("hub missing a month link", lambda h: h.replace(
                'href="indonesia-official-links/2026-09.html"', 'href="archive.html"'),
             "official_link_index_hub_months_disagree_with_db"),
            ("hub carries source rows", lambda h: h.replace(
                "</ol>", '</ol><ul><li data-regional-official-source-id="kemhan:/x"></li></ul>', 1),
             "official_link_index_hub_contains_source_rows"),
            ("hub for another desk", lambda h: h.replace(
                'data-official-link-index="indonesia"', 'data-official-link-index="korea"'),
             "official_link_index_hub_identity_differs"),
        )
        for label, change, reason in cases:
            with self.subTest(label), self.mutated(hub, change):
                self.indonesia_holds(reason)

    def test_indonesia_db_drift_holds(self):
        newer = dict(ID_ROWS[0], source_identity="kemhan:/2026/11/30/ipr-new.html",
                     canonical_official_url="https://www.kemhan.go.id/2026/11/30/ipr-new.html")
        for label, rows in (("new admitted row", [newer] + ID_ROWS),
                            ("row withdrawn", ID_ROWS[1:]),
                            ("withdrawn older month", ID_ROWS[:60])):
            with self.subTest(label), mock.patch.object(
                    readback, "load_admitted_links",
                    lambda db, desk, rows=rows: ([dict(r) for r in rows]
                                                 if desk == "indonesia" else fake_regional(db, desk))):
                self.indonesia_holds()
        with mock.patch.object(readback, "load_admitted_links",
                               lambda db, desk: [] if desk == "indonesia" else fake_regional(db, desk)):
            self.indonesia_holds()

    # -- Indonesia deployed readback -------------------------------------
    def test_indonesia_deployed_readback_requires_identical_bytes(self):
        routes = (["philippines.html", "indonesia.html"]
                  + link_index.index_routes("indonesia", ID_ROWS))
        pages = self.make_pages_dir(routes)
        readback.verify(DB, self.out, required_desks=("indonesia",), pages_dir=pages)
        month = pages / "indonesia-official-links/2026-10.html"
        good = month.read_bytes()
        month.write_bytes(good.replace(b"</main>", b"<!-- drift --></main>", 1))
        self.indonesia_holds("deployed_pages_route_differs_from_committed_site", pages_dir=pages)
        month.unlink()
        self.indonesia_holds("official_link_index_month_pages_disagree_with_db", pages_dir=pages)
        month.write_bytes(good)
        (pages / "indonesia-official-links/2026-08.html").write_bytes(good)
        self.indonesia_holds("official_link_index_month_pages_disagree_with_db", pages_dir=pages)
        (pages / "indonesia-official-links/2026-08.html").unlink()
        (pages / "indonesia-official-links.html").unlink()
        self.indonesia_holds("deployed_pages_route_differs_from_committed_site", pages_dir=pages)

    # -- HTTPS readback ---------------------------------------------------
    def fetch_from(self, overrides=None):
        overrides = overrides or {}

        def fetch(url):
            self.assertTrue(url.startswith(readback.LIVE_ORIGIN + "/"))
            route = url[len(readback.LIVE_ORIGIN) + 1:]
            if route in overrides:
                return overrides[route]
            return (self.out / route).read_bytes()
        return fetch

    def test_indonesia_https_readback(self):
        receipt = readback.verify_https(DB, self.out, "indonesia", fetch=self.fetch_from())
        self.assertEqual(receipt["routes"], readback.index_routes(DB, "indonesia"))
        self.assertEqual(receipt["admitted_official_link_count"], 75)
        month = "indonesia-official-links/2026-09.html"
        for label, body, reason in (
                ("wrong bytes", b"<html>stale</html>",
                 "indonesia_https_bytes_differ_from_committed_output"),
                ("oversize", b"x" * 500001, "indonesia_https_page_oversized")):
            with self.subTest(label), self.assertRaisesRegex(ReadbackHold, "^%s$" % reason):
                readback.verify_https(DB, self.out, "indonesia",
                                      fetch=self.fetch_from({month: body}))

    def test_korea_https_readback(self):
        receipt = korea_readback.verify_https(DB, self.out, fetch=self.fetch_from())
        self.assertEqual(receipt["routes"],
                         ["korea.html"] + link_index.index_routes("korea", self.korea_rows))
        hub = "korea-official-links.html"
        with self.assertRaisesRegex(ReadbackHold, "^korea_https_bytes_differ_from_committed_output$"):
            korea_readback.verify_https(DB, self.out, fetch=self.fetch_from({hub: b"old"}))

    # -- Korea local and deployed readback ------------------------------
    def test_korea_readback_accepts_exact_build(self):
        receipt = korea_readback.verify(DB, self.out, rows=self.korea_rows)
        self.assertEqual(receipt["admitted_official_link_count"], len(self.korea_rows))
        self.assertEqual(receipt["desk_official_link_count"], 60)
        self.assertEqual(korea_readback.index_routes(DB),
                         ["korea.html"] + link_index.index_routes("korea", self.korea_rows))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(korea_readback.main(
                ["--db", str(DB), "--site-dir", str(self.out)]), 0)
        self.assertEqual(json.loads(out.getvalue())["admitted_official_link_count"],
                         len(self.korea_rows))

    def test_korea_mutations_hold(self):
        desk = "korea.html"
        index_routes = link_index.index_routes("korea", self.korea_rows)
        last_month = index_routes[-1]
        row_60 = None
        for route in index_routes[1:]:
            for sid, li in rows_in(self.read(route), "korea"):
                if sid == self.korea_rows[60]["source_identity"]:
                    row_60 = li
        self.assertIsNotNone(row_60)

        def add_61(html):
            last = rows_in(html, "korea")[-1][1]
            return html.replace(last, last + row_60, 1)

        def drop_last(html):
            return html.replace(rows_in(html, "korea")[-1][1], "", 1)

        def older_in(html):
            return html.replace(rows_in(html, "korea")[-1][1], row_60, 1)

        for label, change in (("61 rows", add_61), ("59 rows", drop_last),
                              ("older row swapped in", older_in)):
            with self.subTest(label), self.mutated(desk, change):
                self.korea_holds()
        with self.mutated(desk, lambda h: h.replace('href="korea-official-links.html"',
                                                    'href="archive.html"')):
            self.korea_holds("desk_page_full_index_link_missing_or_repeated")
        with self.mutated(last_month, drop_last):
            self.korea_holds()
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(korea_readback.main(
                    ["--db", str(DB), "--site-dir", str(self.out)]), 2)
            self.assertEqual(json.loads(out.getvalue())["status"], "HOLD")
        with self.mutated("korea-official-links.html", lambda h: h.replace(
                'data-official-link-total="%d"' % len(self.korea_rows),
                'data-official-link-total="%d"' % (len(self.korea_rows) - 1))):
            self.korea_holds("official_link_index_hub_total_disagrees_with_db")
        # A record published through the gate leaves the index: rows that
        # still list it hold.
        with self.assertRaises(ReadbackHold):
            korea_readback.verify(DB, self.out, rows=self.korea_rows[1:])

    def test_korea_deployed_readback_requires_identical_bytes(self):
        routes = ["korea.html"] + link_index.index_routes("korea", self.korea_rows)
        pages = self.make_pages_dir(routes)
        korea_readback.verify(DB, self.out, rows=self.korea_rows, pages_dir=pages)
        hub = pages / "korea-official-links.html"
        hub.write_bytes(hub.read_bytes() + b"\n")
        self.korea_holds("deployed_pages_route_differs_from_committed_site", pages_dir=pages)
        hub.unlink()
        self.korea_holds("deployed_pages_route_differs_from_committed_site", pages_dir=pages)


class HttpsFetcherTests(unittest.TestCase):
    """The fixed-origin fetcher refuses redirects, non-200 and oversize bodies."""

    def fetch_with(self, status, final_url, body):
        class Response:
            def __init__(self):
                self.status = status

            def geturl(self):
                return final_url

            def read(self, limit):
                return body[:limit]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        opener = types.SimpleNamespace(open=lambda req, timeout: Response())
        with mock.patch("urllib.request.build_opener", return_value=opener):
            return readback.https_fetcher("indonesia", limit=100)(
                readback.LIVE_ORIGIN + "/indonesia-official-links.html")

    def test_fetcher(self):
        url = readback.LIVE_ORIGIN + "/indonesia-official-links.html"
        self.assertEqual(self.fetch_with(200, url, b"ok"), b"ok")
        for label, args, reason in (
                ("redirect", (200, readback.LIVE_ORIGIN + "/moved.html", b"ok"),
                 "indonesia_https_status_or_origin_differs"),
                ("non-200", (404, url, b"ok"), "indonesia_https_status_or_origin_differs"),
                ("oversize", (200, url, b"x" * 101), "indonesia_https_page_oversized")):
            with self.subTest(label), self.assertRaisesRegex(ReadbackHold, "^%s$" % reason):
                self.fetch_with(*args)


class BudgetGateTests(unittest.TestCase):
    def run_gate(self, root, *routes):
        args = [PYTHON, str(ROOT / "scripts" / "verify_frontend_delivery.py"),
                "--root", str(root), "--receipt", str(Path(root).parent / "receipt.json")]
        for route in routes:
            args += ["--only", route]
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)

    def write(self, root, route, size):
        path = Path(root) / route
        path.parent.mkdir(parents=True, exist_ok=True)
        head = "<!doctype html><title>x</title><p>"
        path.write_text(head + "x" * (size - len(head)), encoding="utf-8")
        self.assertEqual(path.stat().st_size, size)

    def test_only_gates_index_routes_at_their_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "output"
            month = "indonesia-official-links/2026-11.html"
            self.write(root, "indonesia.html", 150000)
            self.write(root, "indonesia-official-links.html", 1000)
            self.write(root, month, 120000)
            # An unrelated oversized page is outside a writer's --only set.
            self.write(root, "record/1.html", 200000)
            ok = self.run_gate(root, "indonesia.html", "indonesia-official-links.html", month)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.write(root, month, 120001)
            over = self.run_gate(root, "indonesia.html", month)
            self.assertEqual(over.returncode, 1)
            self.assertIn("1 delivery budget failures", over.stdout)
            self.write(root, month, 1000)
            self.write(root, "indonesia.html", 160001)
            self.assertEqual(self.run_gate(root, "indonesia.html").returncode, 1)
            self.write(root, "korea-official-links.html", 120001)
            self.assertEqual(self.run_gate(root, "korea-official-links.html").returncode, 1)
            for bad in ("korea-official-links/2026-11.html", "../outside.html",
                        "indonesia-official-links"):
                with self.subTest(bad):
                    missing = self.run_gate(root, bad)
                    self.assertEqual(missing.returncode, 1)
                    self.assertIn("Missing or invalid gated route", missing.stdout)
            self.assertEqual(self.run_gate(root).returncode, 1)  # full-site run still caps


class WriterWorkflowTextTests(unittest.TestCase):
    WRITERS = {
        "indonesia_verified_official_link_production.yml":
            ("verify_regional_source_index_readback --db pla_watch.db \\\n"
             "            --print-routes indonesia",
             "git add -- pla_watch.db output/indonesia.html"),
        "korea_verified_official_link_production.yml":
            ('--print-routes > "$RUNNER_TEMP/korea-routes"',
             "git add -- pla_watch.db output/korea.html"),
        "korea_standing_original_text_production.yml":
            ('--print-routes > "$RUNNER_TEMP/korea-text-routes"',
             "git add -A -- research/korea_published_original_texts.json"),
    }

    def flow(self, name):
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_budget_gate_runs_before_anything_is_staged(self):
        for name, (routes, first_add) in self.WRITERS.items():
            with self.subTest(name):
                flow = self.flow(name)
                gate = flow.index("python scripts/verify_frontend_delivery.py --root output")
                self.assertLess(flow.index(routes), gate)
                self.assertIn('"${only[@]}"', flow[gate:gate + 200])
                self.assertLess(gate, flow.index(first_add))
                self.assertLess(gate, flow.index("git commit"))

    def test_staging_allowlists_reject_stray_files(self):
        for name, desk in (("indonesia_verified_official_link_production.yml", "indonesia"),
                           ("korea_verified_official_link_production.yml", "korea")):
            patterns = re.findall(r"grep -vE '(\^\(.*?\)\$)'", self.flow(name))
            self.assertEqual(len(patterns), 2, name)
            main, pages = (re.compile(p) for p in patterns)
            good_main = ["pla_watch.db", "output/%s.html" % desk,
                         "output/%s-official-links.html" % desk,
                         "output/%s-official-links/2026-11.html" % desk]
            bad_main = ["output/index.html", "output/philippines.html",
                        "output/%s-official-links/2026-11.json" % desk,
                        "output/%s-official-links/2026-11xhtml" % desk,
                        "output/%s-official-links/x/2026-11.html" % desk,
                        "pla_watchxdb", "output/%s-official-links.html.bak" % desk]
            for path in good_main:
                self.assertTrue(main.match(path), (name, path))
            for path in bad_main:
                self.assertFalse(main.match(path), (name, path))
            for path in ("%s.html" % desk, "%s-official-links.html" % desk,
                         "%s-official-links/2026-09.html" % desk):
                self.assertTrue(pages.match(path), (name, path))
            for path in ("index.html", "pla_watch.db", "%s-official-links/2026-9.html" % desk,
                         "output/%s.html" % desk, "%s-official-links/../index.html" % desk):
                self.assertFalse(pages.match(path), (name, path))

    def test_page_only_writers_fail_closed_without_the_hub_on_pages(self):
        for name, pages_hub in (
                ("korea_original_text_pages_release.yml",
                 "test -f korea-existing-original-pages/korea-official-links.html"),
                ("korea_reviewed_english_release.yml",
                 "test -f korea-english-existing-pages/korea-official-links.html"),
                ("korea_pages_file_only_release.yml", "test -f korea-official-links.html"),
                ("korea_standing_original_text_production.yml",
                 "test -f korea-standing-existing-pages/korea-official-links.html")):
            with self.subTest(name):
                flow = self.flow(name)
                guard = flow.index(pages_hub)
                self.assertIn("grep -qF 'href=\"korea-official-links.html\"'",
                              flow[guard - 200:guard])
                self.assertIn("exit 1", flow[guard:guard + 300])
        for name in ("korea_original_text_pages_release.yml",
                     "korea_reviewed_english_release.yml"):
            flow = self.flow(name)
            main_guard = flow.index("git cat-file -e HEAD:output/korea-official-links.html")
            self.assertLess(main_guard, flow.index("git add -A -- research/"))
        flow = self.flow("korea_pages_file_only_release.yml")
        self.assertLess(flow.index("test -f korea-official-links.html"),
                        flow.index("cp ../output/korea.html korea.html"))

    def test_writers_publish_and_read_back_the_full_index(self):
        for name, desk in (("indonesia_verified_official_link_production.yml", "indonesia"),
                           ("korea_verified_official_link_production.yml", "korea")):
            flow = self.flow(name)
            with self.subTest(name):
                self.assertIn("cp -R ../output/%s-official-links %s-official-links"
                              % (desk, desk), flow)
                self.assertIn("HTTPS readback", flow)
        indonesia = self.flow("indonesia_verified_official_link_production.yml")
        self.assertIn("--https-desk indonesia", indonesia)
        # Deployed readback: identical month inventory and per-route bytes on
        # main and gh-pages, for every route the DB requires.
        self.assertIn("git ls-tree --name-only origin/gh-pages indonesia-official-links/",
                      indonesia)
        self.assertIn('"$(git show "origin/gh-pages:$route" | sha256sum)"', indonesia)
        for name, pages in (("korea_verified_official_link_production.yml",
                             "korea-existing-pages"),
                            ("korea_standing_original_text_production.yml",
                             "korea-standing-existing-pages")):
            flow = self.flow(name)
            with self.subTest(name):
                self.assertIn("--site-dir output --deployed-dir " + pages, flow)
                self.assertIn("--site-dir output --https; then exit 0; fi", flow)

    def test_release_checks_count_the_bounded_desk(self):
        for name in ("korea_public_bibliography_release.yml",
                     "korea_pages_file_only_release.yml"):
            flow = self.flow(name)
            with self.subTest(name):
                self.assertIn('shown = link_index.latest("korea", auto)', flow)
                self.assertIn("== len(shown)", flow)
                self.assertNotIn("== len(auto)", flow)
        # The PR-triggered source-link contract must still check every admitted
        # auto row, now through the full index, not only the bounded desk.
        contract = self.flow("korea_public_bibliography_release.yml")
        self.assertIn('verify_link_index("pla_watch.db", "output", rows=auto)', contract)
        self.assertLess(contract.index('verify_link_index("pla_watch.db", "output", rows=auto)'),
                        contract.index("print(\"Korea routes:"))
        for name in ("indonesia_official_links_release.yml",
                     "indonesia_press_links_release.yml"):
            flow = self.flow(name)
            with self.subTest(name):
                self.assertIn('link_index.latest("indonesia", admitted)', flow)
                self.assertIn("assert indexed == [row[\"source_identity\"] for row in admitted]",
                              flow)
                self.assertIn("assert not hub.exists()", flow)

    def test_daily_archive_includes_the_indonesia_index(self):
        flow = self.flow("daily_update.yml")
        self.assertIn("deployed_routes=(philippines.html indonesia.html vietnam.html)", flow)
        self.assertIn("deployed_routes+=(indonesia-official-links.html indonesia-official-links)",
                      flow)
        self.assertIn('git archive origin/gh-pages "${deployed_routes[@]}"', flow)


if __name__ == "__main__":
    unittest.main()
