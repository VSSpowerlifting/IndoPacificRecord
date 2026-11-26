"""Bounded Indonesia/Korea/Philippines desk lists and full official-link indexes.

The desk pages list the newest DESK_LINK_LIMIT admitted rows; a hub and one
page per publisher-posted month carry every admitted row exactly once. These
tests build a real site from the production database with synthetic admitted
rows layered over the loaders (no DB writes), then prove the renderer, the
local/deployed/HTTPS readbacks, the pre-commit budget gate and the writer
workflow text all fail closed.
"""
from __future__ import annotations

import contextlib
import hashlib
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

from core import daily_machine_records as machine_records
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


PH_AFP = "Armed Forces of the Philippines"
PH_NSC = "National Security Council"
# Ten times the 74 rows that pushed philippines.html over its 120 KB cap
# (25 Nov 2026), at about 35 rows a month over 22 months.
PH_GROWTH_ROWS = 740
PH_ROWS_PER_MONTH = 35


def philippines_rows(count=PH_GROWTH_ROWS):
    """Synthetic AFP and NSC rows in load_admitted_links order.

    Newest official date first, then source identity, as read_live_links
    orders them; every 74th row is NSC, so NSC rows fall both inside and
    outside the latest DESK_LINK_LIMIT and the desk's AFP-then-NSC grouping
    differs from DB order. URLs are longer than the real AFP average.
    """
    rows = []
    for i in range(count):
        year, month0 = divmod(2026 * 12 + 10 - i // PH_ROWS_PER_MONTH, 12)
        day = "%04d-%02d-%02d" % (year, month0 + 1, 28 - (i % PH_ROWS_PER_MONTH) // 2)
        if i % 74 == 37:
            rows.append({
                "source_identity": "nsc:%d" % (80000 + i),
                "canonical_official_url": "https://nsc.gov.ph/%s/statement-of-the-"
                                          "national-security-adviser-ipr-synthetic-%d/"
                                          % (day.replace("-", "/"), i),
                "publisher_posted_date": day,
                "label": "NSC official source",
                "publisher_label": PH_NSC,
            })
            continue
        rows.append({
            "source_identity": "afp:%d" % (990000 + i),
            "canonical_official_url": "https://www.afp.mil.ph/news/ipr-synthetic-growth-"
                                      "row-%04d-statement-on-a-long-official-headline-slug"
                                      "-for-budget-headroom" % i,
            "publisher_posted_date": day,
            "label": "AFP official source",
            "publisher_label": PH_AFP,
        })
    rows.sort(key=lambda r: r["source_identity"])
    rows.sort(key=lambda r: r["publisher_posted_date"], reverse=True)
    return rows


def korea_synthetic_rows():
    """61 synthetic MND rows, placed ahead of every committed row.

    One more than DESK_LINK_LIMIT on their own, so the desk bound is exercised
    however many real auto rows remain (released originals with a Record
    leave the auto-link list). Their date is set in fake_korea from the newest
    committed row, so a scheduled Korea admission never misorders them."""
    return [{
        "source_identity": "korea-policy:%d" % (999999999 - i),
        "source_url": korea_live.PREFIX + str(999999999 - i),
        "published_date": "2026-11-21",
        "issuer_label": "Republic of Korea Ministry of National Defense",
        "issuer_original_label": "국방부",
        "republisher_label": "Republic of Korea Policy Briefing",
        "neutral_label": "MND official press release %d" % (999999999 - i),
    } for i in range(link_index.DESK_LINK_LIMIT + 1)]


ID_ROWS = indonesia_rows()
PH_ROWS = philippines_rows()
KOREA_EXTRA = korea_synthetic_rows()
KOREA_FLOOR_DAY = "2026-11-21"
_ORIGINAL_REGIONAL = regional_render.load_admitted_links
_ORIGINAL_KOREA = korea_live.load_live_korea_official_links
_ORIGINAL_MACHINE = machine_records.load

# Sixty released Philippines machine explanations bound to the newest synthetic
# admitted links (AFP and NSC). They REPLACE the committed Philippines records,
# as fake_regional replaces the committed Philippines links, so Daily releases
# (any date, with or without original text) cannot change which five records
# the desk lists. At about 900 bytes each, listing all sixty would exceed
# philippines.html's cap.
PH_MACHINE_GROWTH = 60
PH_FAMILIES = {PH_AFP: "ph_afp_articles", PH_NSC: "ph_nsc_official_statements"}
# The oldest synthetic link (an AFP row) carries original text, so the
# original-text count, Record page and archive title are exercised outside the
# newest five.
PH_ORIGINAL_INDEX = PH_MACHINE_GROWTH - 1
PH_ORIGINAL_TITLE = "IPR synthetic official title for the growth test"
PH_ORIGINAL_TEXT = ("IPR synthetic original paragraph one.\n\n"
                    "IPR synthetic original paragraph two.")
_PH_MACHINE_CACHE = []


def philippines_machine_rows(real):
    """Synthetic released records cloned from committed ones, load() fields.

    Any committed record of the family serves as the template: identity, URL,
    date, summary and original fields are all overwritten here."""
    templates = {}
    for r in real:
        if r["desk_id"] == "philippines":
            templates.setdefault(r["source_family"], r)
    rows = []
    for i, link in enumerate(PH_ROWS[:PH_MACHINE_GROWTH]):
        family = PH_FAMILIES[link["publisher_label"]]
        sid = link["source_identity"]
        original = i == PH_ORIGINAL_INDEX
        rows.append(dict(
            templates[family], source_identity=sid,
            record_path="record/source-" + hashlib.sha256(
                (family + ":" + sid).encode()).hexdigest()[:24] + ".html",
            url=link["canonical_official_url"],
            published_date=link["publisher_posted_date"],
            summary="IPR synthetic machine explanation of %s for budget growth." % sid,
            original_title=PH_ORIGINAL_TITLE if original else None,
            original_text=PH_ORIGINAL_TEXT if original else None))
    return rows


def fake_machine(db_path):
    real = _ORIGINAL_MACHINE(db_path)
    if not _PH_MACHINE_CACHE:
        _PH_MACHINE_CACHE.extend(philippines_machine_rows(real))
    others = [r for r in real if r["desk_id"] != "philippines"]
    return sorted(others + [dict(r) for r in _PH_MACHINE_CACHE],
                  key=lambda r: (r["published_date"], r["source_identity"]),
                  reverse=True)


def fake_regional(db_path, desk):
    if desk == "indonesia":
        return [dict(r) for r in ID_ROWS]
    if desk == "philippines":
        return [dict(r) for r in PH_ROWS]
    return _ORIGINAL_REGIONAL(db_path, desk)


def fake_korea(db_path, *, exclude=()):
    excluded = set(exclude)
    real = _ORIGINAL_KOREA(db_path, exclude=exclude)
    # Newest-first is checked strictly (day > previous holds), so sharing the
    # newest committed day keeps canonical order whatever Daily admits next.
    newest = max([KOREA_FLOOR_DAY] + [r["published_date"] for r in real])
    return [dict(r, published_date=newest) for r in KOREA_EXTRA
            if r["source_identity"] not in excluded] + real


ROW = {"indonesia": r'<li data-regional-official-source-id="([^"]+)">.*?</li>',
       "philippines": r'<li data-regional-official-source-id="([^"]+)">.*?</li>',
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
        for desk in ("vietnam", "japan", "singapore"):
            with self.subTest(desk), self.assertRaises(link_index.IndexHold):
                link_index.hub_route(desk)
            with self.subTest(desk + " listing"), self.assertRaises(link_index.IndexHold):
                link_index.desk_listing(desk, [])

    def test_philippines_listing_is_latest_rows_grouped_afp_then_nsc(self):
        shown = link_index.desk_listing("philippines", PH_ROWS)
        latest = PH_ROWS[:link_index.DESK_LINK_LIMIT]
        self.assertEqual(sorted(r["source_identity"] for r in shown),
                         sorted(r["source_identity"] for r in latest))
        self.assertEqual(shown, [r for r in latest if r["publisher_label"] == PH_AFP]
                         + [r for r in latest if r["publisher_label"] == PH_NSC])
        # The corpus makes the grouping matter: an NSC row sits among the
        # latest AFP rows, so display order is not DB order.
        self.assertNotEqual(shown, latest)
        self.assertEqual(sum(r["publisher_label"] == PH_NSC for r in shown), 1)
        self.assertEqual(link_index.desk_listing("philippines", PH_ROWS[:5]),
                         [r for r in PH_ROWS[:5] if r["publisher_label"] == PH_AFP]
                         + [r for r in PH_ROWS[:5] if r["publisher_label"] == PH_NSC])
        self.assertEqual(link_index.hub_route("philippines"), "philippines-official-links.html")
        self.assertEqual(link_index.month_route("philippines", "2026-07"),
                         "philippines-official-links/2026-07.html")

    def test_philippines_growth_partition_is_exact_and_monthly(self):
        months = link_index.partition("philippines", PH_ROWS)
        self.assertEqual(len(PH_ROWS), PH_GROWTH_ROWS)
        self.assertEqual(len(months), -(-PH_GROWTH_ROWS // PH_ROWS_PER_MONTH))
        self.assertEqual(months[0][0], "2026-11")
        self.assertTrue(all(len(items) <= PH_ROWS_PER_MONTH for _, items in months))
        flat = [r["source_identity"] for _, items in months for r in items]
        self.assertEqual(flat, [r["source_identity"] for r in PH_ROWS])
        self.assertEqual(len(set(flat)), len(flat))

    def test_philippines_holds_instead_of_guessing(self):
        rows = PH_ROWS[:70]
        cases = {
            "misordered": [rows[65]] + rows[:65] + rows[66:],
            "duplicate": rows[:10] + [rows[3]],
            "missing identity": [dict(rows[0], source_identity="")] + rows[1:],
            "bad date": [dict(rows[0], publisher_posted_date="25 Nov 2026")] + rows[1:],
            "impossible date": [dict(rows[0], publisher_posted_date="2026-11-31")] + rows[1:],
        }
        for label, bad in cases.items():
            for fn in (link_index.partition, link_index.latest, link_index.desk_listing):
                with self.subTest(label, fn=fn.__name__), self.assertRaises(link_index.IndexHold):
                    fn("philippines", bad)
        # A row from no declared publisher group is never dropped or appended.
        stray = [dict(rows[0], publisher_label="Department of National Defense")] + rows[1:]
        with self.assertRaises(link_index.IndexHold):
            link_index.desk_listing("philippines", stray)
        # Desks without groups are unaffected by publisher labels.
        self.assertEqual(link_index.desk_listing("indonesia", ID_ROWS), ID_ROWS[:60])

    def test_philippines_groups_point_older_rows_to_their_month(self):
        afp = [r for r in PH_ROWS if r["publisher_label"] == PH_AFP][:70]
        nsc_old = dict(PH_ROWS[-1], source_identity="nsc:3108",
                       publisher_posted_date="2026-07-08", publisher_label=PH_NSC)
        rows = afp + [nsc_old]
        groups = link_index.desk_groups(
            "philippines", rows, link_index.desk_listing("philippines", rows))
        self.assertEqual([g["id"] for g in groups], ["ph-afp-links", "ph-nsc-links"])
        afp_group, nsc_group = groups
        self.assertEqual((afp_group["total"], len(afp_group["rows"])), (70, 60))
        self.assertEqual(afp_group["older"]["route"], link_index.month_route(
            "philippines", afp[60]["publisher_posted_date"][:7]))
        # The real 25 Nov shape: the only NSC row is older than the latest 60,
        # so its group lists nothing and points to the month that holds it.
        self.assertEqual((nsc_group["total"], nsc_group["rows"]), (1, []))
        self.assertEqual(nsc_group["older"], {
            "label": "July 2026", "route": "philippines-official-links/2026-07.html"})
        few = link_index.desk_groups("philippines", afp[:5], afp[:5])
        self.assertEqual([g["older"] for g in few], [None, None])
        self.assertEqual(few[1]["total"], 0)

    def test_desk_context_is_pure_and_groups_only_philippines(self):
        self.assertIsNone(link_index.desk_context("philippines", []))
        ph = link_index.desk_context("philippines", PH_ROWS)
        self.assertEqual((ph["total"], ph["shown"], ph["hub"]),
                         (len(PH_ROWS), link_index.DESK_LINK_LIMIT,
                          "philippines-official-links.html"))
        self.assertEqual([r for g in ph["groups"] for r in g["rows"]],
                         link_index.desk_listing("philippines", PH_ROWS))
        self.assertNotIn("groups", link_index.desk_context("indonesia", ID_ROWS))

    def test_source_free_wiring_module_loads_without_generate_preview(self):
        # The regional live-site wiring job installs only jinja2; config.py
        # (imported by generate_preview) needs dotenv. The module must load
        # and build desk contexts without it.
        probe = ("import sys; sys.modules['dotenv'] = None; "
                 "import tests.test_regional_live_site_wiring as w; "
                 "assert 'generate_preview' not in sys.modules; "
                 "assert 'config' not in sys.modules")
        result = subprocess.run([sys.executable, "-c", probe], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

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
            mock.patch.object(machine_records, "load", fake_machine),
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

    def test_philippines_desk_is_bounded_and_index_carries_every_row_once(self):
        desk = self.read("philippines.html")
        shown = link_index.desk_listing("philippines", PH_ROWS)
        self.assertEqual([sid for sid, _ in rows_in(desk, "philippines")],
                         [r["source_identity"] for r in shown])
        self.assertEqual(desk.count('href="philippines-official-links.html"'), 1)
        # Counts and in-page navigation stay totals, not the bounded list.
        afp_total = sum(r["publisher_label"] == PH_AFP for r in PH_ROWS)
        nsc_total = len(PH_ROWS) - afp_total
        self.assertIn('<h3 id="ph-afp-links">%s · %d links</h3>' % (PH_AFP, afp_total), desk)
        self.assertIn('<h3 id="ph-nsc-links">%s · %d links</h3>' % (PH_NSC, nsc_total), desk)
        self.assertIn('href="#ph-afp-links">AFP links (%d)</a>' % afp_total, desk)
        self.assertIn('href="#ph-nsc-links">NSC links (%d)</a>' % nsc_total, desk)
        self.assertIn('data-official-link-index-note="60/%d"' % len(PH_ROWS), desk)
        for group in ("ph-afp-links", "ph-nsc-links"):
            self.assertIn('data-official-link-older="%s"' % group, desk)
        # Every listed row keeps its reader semantics.
        for sid, li in rows_in(desk, "philippines"):
            self.assertIn('target="_blank"', li)
            self.assertIn('rel="noopener noreferrer"', li)
            self.assertIn("Official date <time datetime=", li)
            self.assertIn("Official-link metadata only", li)
        months = link_index.partition("philippines", PH_ROWS)
        self.assertEqual(
            sorted(p.name for p in (self.out / "philippines-official-links").iterdir()),
            sorted(month + ".html" for month, _ in months))
        union = []
        for month, items in months:
            page = self.read(link_index.month_route("philippines", month))
            got = rows_in(page, "philippines")
            self.assertEqual([sid for sid, _ in got], [r["source_identity"] for r in items])
            for (sid, li), row in zip(got, items):
                self.assertIn('href="%s"' % row["canonical_official_url"], li)
                self.assertIn('rel="noopener noreferrer"', li)
                self.assertIn('<time datetime="%s">' % row["publisher_posted_date"], li)
                self.assertIn("Publisher: %s" % row["publisher_label"], li)
            union += [sid for sid, _ in got]
        # Every admitted row is on exactly one month page, in DB order.
        self.assertEqual(union, [r["source_identity"] for r in PH_ROWS])
        hub = self.read("philippines-official-links.html")
        self.assertIn('data-official-link-total="%d"' % len(PH_ROWS), hub)
        self.assertNotIn("data-regional-official-source-id", hub)
        self.assertEqual(hub.count("data-official-link-month="), len(months))

    def test_philippines_growth_corpus_fits_the_default_budget(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_frontend_delivery as budget
        routes = readback.index_routes(DB, "philippines")
        self.assertEqual(routes, ["philippines.html"]
                         + link_index.index_routes("philippines", PH_ROWS))
        self.assertEqual(len(routes), 2 + len(link_index.partition("philippines", PH_ROWS)))
        for route in routes:
            self.assertEqual(budget.html_css_cap(route), 120000, route)
        result = budget.verify(self.out, only=routes)
        self.assertEqual(result["failures"], [])

    def test_philippines_machine_explanations_are_bounded_and_counts_stay_totals(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_frontend_delivery as budget
        machine = [r for r in fake_machine(DB) if r["desk_id"] == "philippines"]
        # Only synthetic Philippines records: a Daily release cannot reorder them.
        self.assertEqual(len(machine), PH_MACHINE_GROWTH)
        desk = self.read("philippines.html")
        # Only the newest five, in load() order, are listed on the desk.
        self.assertEqual(re.findall(r'data-machine-explanation-id="([^"]+)"', desk),
                         [r["source_identity"] for r in machine[:5]])
        for rec in machine[5:]:
            self.assertNotIn(rec["summary"], desk)
        afp = sum(r["source_label"] == "AFP" for r in machine)
        nsc = sum(r["source_label"] == "NSC" for r in machine)
        self.assertTrue(afp and nsc)
        self.assertEqual(afp + nsc, len(machine))
        originals = sum(bool(r["original_text"]) for r in machine)
        self.assertEqual(originals, 1)
        with_original = [i for i, r in enumerate(machine) if r["original_text"]]
        self.assertTrue(with_original and min(with_original) >= 5, with_original)
        self.assertFalse(any(r["original_text"] for r in machine[:5]))
        # The count covers a record the desk does not list; its Record and
        # archive row still carry the original title and text.
        self.assertNotIn(PH_ORIGINAL_TITLE, desk)
        original_rec = machine[with_original[0]]
        page = self.read(original_rec["record_path"])
        self.assertIn(">%s</h1>" % PH_ORIGINAL_TITLE, page)
        for paragraph in PH_ORIGINAL_TEXT.split("\n\n"):
            self.assertIn(paragraph, page)
        self.assertIn('<dt>Machine explanations</dt><dd>%d <span class="meta">(AFP %d · NSC %d)'
                      % (len(machine), afp, nsc), desk)
        self.assertIn("<dt>Records with original text</dt><dd>%d</dd>" % originals, desk)
        self.assertIn('href="#daily-machine-heading">Machine explanations (%d)</a>'
                      % len(machine), desk)
        self.assertIn("The latest 5 of %d, newest official date first." % len(machine), desk)
        self.assertEqual(desk.count(
            '<a href="archive.html?desk=philippines&amp;scope=published">'
            'Browse all %d Philippines machine explanations</a>' % len(machine)), 1)
        # Listed links say where their explanation is: above, or in the archive.
        listed = {sid for sid, _ in rows_in(desk, "philippines")}
        above = {r["source_identity"] for r in machine[:5]}
        explained = {r["source_identity"] for r in machine} & listed
        self.assertTrue(explained - above)
        self.assertEqual(desk.count("Machine explanation published above"),
                         len(explained & above))
        self.assertEqual(desk.count("Machine explanation in the published archive"),
                         len(explained - above))
        # Every record, listed or not, is in the published archive search.
        rows = {r["id"]: r for r in json.loads(
            self.read("archive-research-index.json"))["records"]}
        for rec in machine:
            row = rows["machine:" + rec["source_identity"]]
            self.assertEqual(row["desks"], ["philippines"])
            self.assertEqual(row["record_type"], "machine_explanation")
            self.assertTrue((self.out / rec["record_path"]).is_file(), rec["record_path"])
        self.assertEqual(rows["machine:" + original_rec["source_identity"]]["title"],
                         PH_ORIGINAL_TITLE)
        self.assertEqual(budget.html_css_cap("philippines.html"), 120000)
        self.assertEqual(budget.verify(self.out, only=["philippines.html"])["failures"], [])

    def test_vietnam_and_japan_keep_full_lists_and_no_index(self):
        for slug in ("vietnam", "japan", "singapore"):
            self.assertFalse((self.out / ("%s-official-links.html" % slug)).exists())
            self.assertFalse((self.out / ("%s-official-links" % slug)).exists())
        vietnam = _ORIGINAL_REGIONAL(DB, "vietnam")
        self.assertEqual(self.read("vietnam.html").count("data-regional-official-source-id="),
                         len(vietnam))

    # -- Philippines local, deployed and HTTPS readback -------------------
    def philippines_holds(self, reason=None, **kwargs):
        ctx = (self.assertRaisesRegex(ReadbackHold, "^%s$" % reason) if reason
               else self.assertRaises(ReadbackHold))
        with ctx:
            readback.verify(DB, self.out, required_desks=("philippines",), **kwargs)

    def test_philippines_readback_accepts_exact_build(self):
        receipt = readback.verify(DB, self.out, required_desks=("philippines",))
        family = receipt["source_families"]["ph_afp_articles"]
        self.assertEqual(family["admitted_official_link_count"], len(PH_ROWS))
        self.assertEqual(family["desk_official_link_count"], 60)
        self.assertEqual(family["full_index"]["months"],
                         {m: len(items) for m, items in
                          link_index.partition("philippines", PH_ROWS)})

    def test_philippines_desk_mutations_hold(self):
        desk = "philippines.html"
        first_hidden = PH_ROWS[link_index.DESK_LINK_LIMIT]
        self.assertEqual(first_hidden["publisher_label"], PH_AFP)

        def lis(html):
            return rows_in(html, "philippines")

        # The first hidden row, in exactly the desk's own row markup.
        template = lis(self.read(desk))[0][1]
        row_60 = re.sub(r'source-id="[^"]+"',
                        'source-id="%s"' % first_hidden["source_identity"], template)
        row_60 = re.sub(r'href="[^"]+"', 'href="%s"' % first_hidden["canonical_official_url"],
                        row_60)
        row_60 = re.sub(r'datetime="[^"]+">[^<]+<',
                        'datetime="%s">%s<' % ((first_hidden["publisher_posted_date"],) * 2),
                        row_60)

        def add_61(html):
            last = lis(html)[-1][1]
            return html.replace(last, last + row_60, 1)

        def drop_last(html):
            return html.replace(lis(html)[-1][1], "", 1)

        def duplicate(html):
            first = lis(html)[0][1]
            return html.replace(first, first + first, 1)

        def swap(html):
            a, b = lis(html)[0][1], lis(html)[1][1]
            return html.replace(a, "\0", 1).replace(b, a, 1).replace("\0", b, 1)

        def db_order(html):
            # NSC listed where DB order puts it (among AFP rows) holds: the
            # desk must list AFP, then NSC.
            nsc = [li for sid, li in lis(html) if sid.startswith("nsc:")][0]
            first = lis(html)[0][1]
            return html.replace(nsc, "", 1).replace(first, nsc + first, 1)

        def older_in(html):
            return html.replace(lis(html)[-2][1], row_60, 1)

        def altered(field_old, field_new):
            def change(html):
                li = lis(html)[2][1]
                return html.replace(li, li.replace(field_old(li), field_new(li), 1), 1)
            return change

        url = altered(lambda li: re.search(r'href="([^"]+)"', li).group(1),
                      lambda li: re.search(r'href="([^"]+)"', li).group(1) + "?x=1")
        date = altered(lambda li: re.search(r'datetime="([^"]+)"', li).group(0),
                       lambda li: 'datetime="2026-01-01"')
        label = altered(lambda li: "AFP official source", lambda li: "AFP official sources")
        identity = altered(lambda li: re.search(r'source-id="([^"]+)"', li).group(0),
                           lambda li: 'source-id="afp:1"')
        for label_, change in (("61 rows", add_61), ("59 rows", drop_last),
                               ("duplicated row", duplicate), ("wrong order", swap),
                               ("DB order instead of groups", db_order),
                               ("older row swapped in", older_in),
                               ("altered URL", url), ("altered date", date),
                               ("altered label", label), ("altered identity", identity)):
            with self.subTest(label_), self.mutated(desk, change):
                self.philippines_holds()
        with self.mutated(desk, lambda h: h.replace('href="philippines-official-links.html"',
                                                    'href="archive.html"')):
            self.philippines_holds("desk_page_full_index_link_missing_or_repeated")

    def test_philippines_month_mutations_hold(self):
        months = link_index.partition("philippines", PH_ROWS)
        first, second = (link_index.month_route("philippines", m) for m, _ in months[:2])
        first_rows = rows_in(self.read(first), "philippines")

        def lis(html):
            return rows_in(html, "philippines")

        def missing(html):
            return html.replace(lis(html)[3][1], "", 1)

        def duplicate(html):
            li = lis(html)[3][1]
            return html.replace(li, li + li, 1)

        def from_other_month(html):
            li = lis(html)[0][1]
            return html.replace(li, first_rows[0][1] + li, 1)

        def altered_url(html):
            li = lis(html)[1][1]
            href = re.search(r'href="([^"]+)"', li).group(1)
            return html.replace(li, li.replace(href, href + "-changed", 1), 1)

        def altered_date(html):
            li = lis(html)[1][1]
            day = re.search(r'datetime="([^"]+)"', li).group(1)
            return html.replace(li, li.replace('datetime="%s"' % day,
                                               'datetime="2026-10-02"', 1), 1)

        for label, change in (("month missing a row", missing),
                              ("duplicated row", duplicate),
                              ("same id in two months", from_other_month),
                              ("altered URL", altered_url),
                              ("altered date", altered_date)):
            with self.subTest(label), self.mutated(second, change):
                self.philippines_holds()
        folder = self.out / "philippines-official-links"
        orphan = folder / "2020-01.html"
        orphan.write_bytes((self.out / second).read_bytes())
        try:
            self.philippines_holds("official_link_index_month_pages_disagree_with_db")
        finally:
            orphan.unlink()
        with self.mutated("philippines-official-links.html", lambda h: h.replace(
                'data-official-link-total="%d"' % len(PH_ROWS),
                'data-official-link-total="%d"' % (len(PH_ROWS) - 1))):
            self.philippines_holds("official_link_index_hub_total_disagrees_with_db")

    def test_philippines_db_drift_holds(self):
        newer = dict(PH_ROWS[0], source_identity="afp:999999",
                     canonical_official_url="https://www.afp.mil.ph/news/ipr-new")
        for label, rows in (("new admitted row", [newer] + PH_ROWS),
                            ("row withdrawn", PH_ROWS[1:]),
                            ("older row withdrawn", PH_ROWS[:-1]),
                            ("URL changed", [dict(PH_ROWS[0], canonical_official_url=
                                                  PH_ROWS[0]["canonical_official_url"] + "/")]
                             + PH_ROWS[1:])):
            with self.subTest(label), mock.patch.object(
                    readback, "load_admitted_links",
                    lambda db, desk, rows=rows: ([dict(r) for r in rows]
                                                 if desk == "philippines" else fake_regional(db, desk))):
                self.philippines_holds()

    def test_philippines_deployed_and_https_readback(self):
        routes = (["philippines.html", "indonesia.html"]
                  + link_index.index_routes("philippines", PH_ROWS)
                  + link_index.index_routes("indonesia", ID_ROWS))
        pages = self.make_pages_dir(routes)
        readback.verify(DB, self.out, required_desks=("philippines",), pages_dir=pages)
        month = pages / link_index.index_routes("philippines", PH_ROWS)[-1]
        good = month.read_bytes()
        month.write_bytes(good.replace(b"</main>", b"<!-- drift --></main>", 1))
        self.philippines_holds("deployed_pages_route_differs_from_committed_site",
                               pages_dir=pages)
        month.write_bytes(good)
        (pages / "philippines-official-links.html").unlink()
        self.philippines_holds("deployed_pages_route_differs_from_committed_site",
                               pages_dir=pages)
        receipt = readback.verify_https(DB, self.out, "philippines", fetch=self.fetch_from())
        self.assertEqual(receipt["routes"], readback.index_routes(DB, "philippines"))
        self.assertEqual(receipt["admitted_official_link_count"], len(PH_ROWS))
        hub = "philippines-official-links.html"
        with self.assertRaisesRegex(ReadbackHold,
                                    "^philippines_https_bytes_differ_from_committed_output$"):
            readback.verify_https(DB, self.out, "philippines",
                                  fetch=self.fetch_from({hub: b"<html>stale</html>"}))

    def test_index_routes_fit_the_default_budget(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_frontend_delivery as budget
        routes = (link_index.index_routes("indonesia", ID_ROWS)
                  + link_index.index_routes("korea", self.korea_rows)
                  + link_index.index_routes("philippines", PH_ROWS))
        for route in routes + ["philippines.html"]:
            self.assertEqual(budget.html_css_cap(route), 120000, route)
        result = budget.verify(self.out, only=routes + ["indonesia.html", "korea.html",
                                                        "philippines.html"])
        self.assertEqual(result["failures"], [])

    def test_sitemap_lists_index_routes(self):
        sitemap = self.read("sitemap.xml")
        for route in (link_index.index_routes("indonesia", ID_ROWS)
                      + link_index.index_routes("philippines", PH_ROWS)):
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
        # The default Philippines desk is now indexed too, so its full index
        # must also be byte-identical in the deployed checkout.
        routes = (["philippines.html", "indonesia.html"]
                  + link_index.index_routes("philippines", PH_ROWS)
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

    # -- page closure: no unmarked link rides along on index pages ------
    @staticmethod
    def in_list(html, marker, extra, after=False):
        """Insert `extra` just inside (or just after) the list carrying `marker`."""
        close = html.index("</ol>", html.index(marker))
        if after:
            close += len("</ol>")
        return html[:close] + extra + html[close:]

    def test_unmarked_publisher_links_on_index_pages_hold(self):
        reason = "official_link_index_page_has_unadmitted_off_site_link"
        id_month = "indonesia-official-links/2026-10.html"
        korea_month = link_index.index_routes("korea", self.korea_rows)[1]
        id_row, ko_row = "data-regional-official-source-id", "data-korea-auto-official-link"
        hub_list = "data-official-link-index"
        extra_korea_li = ('<li><a href="%s111111111" rel="noopener noreferrer">MND official '
                          'press release 111111111</a> <time datetime="2026-11-01">x</time></li>'
                          % korea_live.PREFIX)
        cases = (
            ("korea", korea_month, "unmarked Korea li",
             lambda h: self.in_list(h, ko_row, extra_korea_li)),
            ("indonesia", id_month, "p/a after the list",
             lambda h: self.in_list(h, id_row, '<p><a href="https://example.com/x" '
                                    'rel="noopener noreferrer">Kemhan Berita official '
                                    'source</a></p>', after=True)),
            ("indonesia", id_month, "area element",
             lambda h: self.in_list(h, id_row, '<map><area href="https://example.com/x"></map>',
                                    after=True)),
            ("indonesia", id_month, "protocol-relative link",
             lambda h: self.in_list(h, id_row, '<a href="//example.com/x">x</a>', after=True)),
            ("korea", korea_month, "javascript link with a tab",
             lambda h: self.in_list(h, ko_row, '<a href="java\tscript:alert(1)">x</a>',
                                    after=True)),
            ("korea", korea_month, "mailto inside main",
             lambda h: self.in_list(h, ko_row, '<a href="mailto:x@example.com">x</a>',
                                    after=True)),
            ("indonesia", "indonesia-official-links.html", "off-site link on the hub",
             lambda h: self.in_list(h, hub_list, '<p><a href="https://www.kemhan.go.id/x">x</a></p>',
                                    after=True)),
            ("korea", "korea-official-links.html", "off-site link on the Korea hub",
             lambda h: self.in_list(h, hub_list, '<p><a href="%s1">x</a></p>' % korea_live.PREFIX,
                                    after=True)),
        )
        for desk, route, label, change in cases:
            holds = self.indonesia_holds if desk == "indonesia" else self.korea_holds
            with self.subTest(label), self.mutated(route, change):
                holds(reason)
        # Shared chrome outside <main> comes from base.html, not admitted rows.
        with self.mutated(id_month, lambda h: h.replace(
                "</main>", '</main><a href="https://example.com/x">x</a>', 1)):
            readback.verify(DB, self.out, required_desks=("indonesia",))
        for desk, route in (("indonesia", id_month), ("korea", korea_month)):
            holds = self.indonesia_holds if desk == "indonesia" else self.korea_holds
            with self.subTest(desk + " second main"), self.mutated(
                    route, lambda h: h.replace("</main>", "</main><main></main>", 1)):
                holds("official_link_index_page_main_missing_or_repeated")

    def test_hub_month_list_admits_only_marked_month_entries(self):
        reason = "official_link_index_hub_unmarked_month_entry"
        for desk, holds in (("indonesia", self.indonesia_holds), ("korea", self.korea_holds)):
            hub = link_index.hub_route(desk)
            orphan = link_index.month_route(desk, "2026-08")
            for label, extra in (
                    ("plain li", '<li><a href="%s">August 2026 (5)</a></li>' % orphan),
                    ("bare a", '<a href="%s">August</a>' % orphan)):
                with self.subTest(desk + " " + label), self.mutated(
                        hub, lambda h, e=extra: self.in_list(h, "data-official-link-index", e)):
                    holds(reason)

    def test_desk_hub_link_must_be_a_real_anchor(self):
        reason = "desk_page_full_index_link_missing_or_repeated"
        for desk, holds in (("indonesia", self.indonesia_holds), ("korea", self.korea_holds)):
            route, hub = desk + ".html", link_index.hub_route(desk)
            html = self.read(route)
            anchor = re.search(r'<a href="%s">[^<]*</a>' % re.escape(hub), html).group(0)
            for label, change in (
                    ("comment", lambda h: h.replace(anchor, '<!-- href="%s" -->' % hub, 1)),
                    ("non-anchor", lambda h: h.replace(
                        anchor, '<span data-x=\'href="%s"\'>Full index</span>' % hub, 1))):
                with self.subTest(desk + " " + label), self.mutated(route, change):
                    holds(reason)

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
            # Philippines desk and index routes keep the default 120 KB cap.
            ph_month = "philippines-official-links/2026-11.html"
            self.write(root, "philippines.html", 120000)
            self.write(root, "philippines-official-links.html", 1000)
            self.write(root, ph_month, 120000)
            ph_routes = ("philippines.html", "philippines-official-links.html", ph_month)
            ok = self.run_gate(root, *ph_routes)
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            for route in ph_routes:
                with self.subTest(over=route):
                    self.write(root, route, 120001)
                    over = self.run_gate(root, *ph_routes)
                    self.assertEqual(over.returncode, 1)
                    self.assertIn("1 delivery budget failures", over.stdout)
                    self.write(root, route, 1000)
            for bad in ("korea-official-links/2026-11.html", "../outside.html",
                        "indonesia-official-links", "philippines-official-links/2026-10.html",
                        "philippines-official-links"):
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
        "ph_afp_verified_official_link_production.yml":
            ('--print-routes philippines > "$RUNNER_TEMP/ph-routes"',
             "git add -- pla_watch.db output/philippines.html"),
        "ph_nsc_verified_official_link_production.yml":
            ('--print-routes philippines > "$RUNNER_TEMP/nsc-routes"',
             "git add -- pla_watch.db output/philippines.html"),
    }
    PH_WRITERS = ("ph_afp_verified_official_link_production.yml",
                  "ph_nsc_verified_official_link_production.yml")

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

    def test_route_listing_commands_run_as_written(self):
        """Run each writer's exact --print-routes lines under `set -euo pipefail`."""
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            (bin_dir / "python").symlink_to(PYTHON)
            writers = ((("indonesia_verified_official_link_production.yml", "indonesia"),
                        ("korea_verified_official_link_production.yml", "korea"),
                        ("korea_standing_original_text_production.yml", "korea"))
                       + tuple((name, "philippines") for name in self.PH_WRITERS))
            for name, desk in writers:
                with self.subTest(name):
                    m = re.search(r"\n( *)(python -m scripts\.verify_\w+ --db pla_watch\.db"
                                  r" \\\n *--print-routes[^\n]*\n\1test [^\n]*)\n",
                                  self.flow(name))
                    self.assertIsNotNone(m, name)
                    env = {"PATH": "%s:/usr/bin:/bin" % bin_dir, "RUNNER_TEMP": tmp,
                           "HOME": tmp}
                    run = subprocess.run(["bash", "-c", "set -euo pipefail\n" + m.group(2)],
                                         cwd=ROOT, env=env, capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                    target = re.search(r'> "\$RUNNER_TEMP/([\w-]+)"', m.group(2)).group(1)
                    routes = (Path(tmp) / target).read_text().split()
                    self.assertEqual(routes[0], desk + ".html")
                    self.assertEqual(routes[1:2], [link_index.hub_route(desk)])

    def test_staging_allowlists_reject_stray_files(self):
        for name, desk in (("indonesia_verified_official_link_production.yml", "indonesia"),
                           ("korea_verified_official_link_production.yml", "korea")) \
                + tuple((name, "philippines") for name in self.PH_WRITERS):
            patterns = re.findall(r"grep -vE '(\^\(.*?\)\$)'", self.flow(name))
            self.assertEqual(len(patterns), 2, name)
            main, pages = (re.compile(p) for p in patterns)
            good_main = ["pla_watch.db", "output/%s.html" % desk,
                         "output/%s-official-links.html" % desk,
                         "output/%s-official-links/2026-11.html" % desk]
            other = "output/indonesia.html" if desk == "philippines" else "output/philippines.html"
            bad_main = ["output/index.html", other, "output/sitemap.xml",
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
                           ("korea_verified_official_link_production.yml", "korea")) \
                + tuple((name, "philippines") for name in self.PH_WRITERS):
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
        for name in self.PH_WRITERS:
            flow = self.flow(name)
            with self.subTest(name):
                self.assertIn("--require-desk philippines --https-desk philippines", flow)
                self.assertIn("git ls-tree --name-only origin/gh-pages "
                              "philippines-official-links/", flow)
                self.assertIn('"$(git show "origin/gh-pages:$route" | sha256sum)"', flow)
                # The desk check is the bounded listing; every admitted row is
                # checked exactly once across the month pages.
                self.assertIn('link_index.desk_listing("philippines", admitted)', flow)
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
        self.assertIn("deployed_routes+=(philippines-official-links.html "
                      "philippines-official-links)", flow)
        self.assertIn('git archive origin/gh-pages "${deployed_routes[@]}"', flow)


if __name__ == "__main__":
    unittest.main()
