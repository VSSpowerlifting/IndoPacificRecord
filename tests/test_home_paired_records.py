"""Current home evidence contracts; old C1 six-record layout is superseded.

Retain fixture horizon, original-title rejection and fallback macro checks.
The parallel-text home page (2026-11-14) carries no opening photograph;
the governed counts, newest records and machine labels are checked below.
"""
from __future__ import annotations

import datetime as dt

import html as html_mod

import json

import re

import shutil

import sqlite3

import sys

import tempfile

import unittest

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "site" / "preview"))

import generate_preview as gp                                    # noqa: E402

from core.viewmodel import PublicView                            # noqa: E402

from scripts.reconcile_db import read_only                       # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"

TEMPLATES = REPO_ROOT / "site" / "preview" / "templates"

CSS = REPO_ROOT / "site" / "preview" / "styles.css"

HOME_RECORDS = 6

_FIXTURE_HORIZON = None

def _corpus_freshness():
    """
    The tracked corpus's newest `published_date`, or None.

    Read through `reconcile_db.read_only`, which copies the database and its
    sidecars to a scratch directory and reads the copy. Never
    `sqlite3.connect()` on the tracked file, even to read: it is WAL-mode, so an
    open can leave a -wal/-shm beside it. That is the run-475 defect, and
    `test_workflow_failure_paths` enforces the rule against this whole suite.
    """
    if not TRACKED_DB.exists():
        return None
    with read_only(str(TRACKED_DB)) as con:
        return con.execute(
            "SELECT MAX(published_date) FROM articles "
            " WHERE published_date GLOB "
            "'[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*'").fetchone()[0]

def fixture_date(offset: int = 0) -> str:
    """`offset` days before the fixture horizon, as `YYYY-MM-DD`."""
    global _FIXTURE_HORIZON
    if _FIXTURE_HORIZON is None:
        newest = _corpus_freshness()
        base = (dt.date.fromisoformat(newest[:10]) if newest
                else dt.date(2026, 9, 14))
        _FIXTURE_HORIZON = base + dt.timedelta(days=HOME_RECORDS)
    return (_FIXTURE_HORIZON - dt.timedelta(days=offset)).isoformat()

ZH = "zh-Hans"

EN = "en"

RECORD_PARTIAL = TEMPLATES / "_records.html"

def require_partial(case):
    if not RECORD_PARTIAL.is_file():
        case.skipTest("_records.html is not present: this tree does not carry "
                      "the paired-record partial")

def strip_tags(fragment: str) -> str:
    """Visible text. Entities are resolved: an institution whose name holds an
    apostrophe reaches the page as `&#39;` and must still compare equal to the
    name the corpus stores."""
    return html_mod.unescape(
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()

def _newest_analyzed_ids(db: Path, count: int) -> list:
    con = sqlite3.connect(str(db))
    try:
        return [r[0] for r in con.execute(
            "SELECT id FROM articles WHERE analyzed_at IS NOT NULL "
            " ORDER BY published_date DESC, id DESC LIMIT ?", (count,))]
    finally:
        con.close()

def _source_ids_by_tag(db: Path) -> dict:
    """slug -> (source_id, language_tag, institution display name)."""
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT s.id, s.slug, s.display_name, s.language_tag, "
            "       i.display_name AS institution "
            "  FROM sources s "
            "  LEFT JOIN institutions i ON i.institution_id = s.institution_id"
        ).fetchall()
    finally:
        con.close()
    return {r["slug"]: dict(r) for r in rows}

def fixture_corpus(tmp: Path, rows: list, name="fixture"):
    """Return a corpus copy whose newest analyzed records match `rows`."""
    db = tmp / ("%s.db" % name)
    shutil.copy2(TRACKED_DB, db)
    ids = _newest_analyzed_ids(db, len(rows))
    if len(ids) < len(rows):
        raise unittest.SkipTest("corpus holds too few analyzed records")
    sources = _source_ids_by_tag(db)

    con = sqlite3.connect(str(db))
    for position, (record_id, row) in enumerate(zip(ids, rows)):
        slug = row.get("source_slug", "pla_daily")
        con.execute(
            "UPDATE articles SET title_english = ?, title_original = ?, "
            "       published_date = ?, source_id = ? WHERE id = ?",
            (row["title_english"], row.get("title_original"),
             row.get("published_date") or fixture_date(),
             sources[slug]["id"], record_id))
    con.commit()
    con.close()

    # The fixture verifies its own premise: the records it rewrote are the ones
    # the page actually selected. Without this a mis-ordered fixture would make
    # every assertion below vacuously true.
    selected = gp.load_corpus(db)["recent"][:len(rows)]
    if [r["id"] for r in selected] != ids:
        raise AssertionError("fixture did not become the newest records")
    return db, selected

def build_fixture(tmp: Path, rows: list, name="fixture"):
    """
    Render a home page whose six newest analyzed records are exactly `rows`.

    `rows` is newest-first. Each entry may set `title_english`,
    `title_original` (None or "" for a record that has none) and `source_slug`;
    dates are assigned descending from `fixture_date()`, a horizon derived
    from the corpus rather than hard-coded, so
    `dates=True` produces a mixed-date register and the default produces one
    date shared by all six.
    """
    db, selected = fixture_corpus(tmp, rows, name)
    out = tmp / ("%s-build" % name)
    gp.build(out, gp.PUBLIC_TITLE, db, snapshot=gp.snapshot_from_corpus(db))
    home = (out / "index.html").read_text(encoding="utf-8")
    return home, selected, out

def homogeneous_rows(count=HOME_RECORDS):
    return [{"title_english": "Record %d in English" % n,
             "title_original": "第%d号原文标题" % n,
             "source_slug": "pla_daily",
             "published_date": fixture_date()} for n in range(count)]

class TestTheFixtureHorizonOutranksTheCorpus(unittest.TestCase):
    """
    The premise every controlled fixture in this file rests on.

    `build_fixture` rewrites the six newest analyzed records and then verifies
    that they really are the six the page selected. That verification can only
    succeed while the dates the fixture stamps outrank every real publication
    date in the corpus — including the OLDEST row of a descending series.

    This was a literal (`2026-09-20`) until the corpus advanced to within six
    days of it and three provenance cases failed with "fixture did not become
    the newest records". The literal is gone; this case is what stops a derived
    horizon from quietly drifting back into range.
    """

    def test_the_oldest_fixture_row_is_still_newer_than_the_whole_corpus(self):
        if not TRACKED_DB.exists():
            self.skipTest("tracked corpus not present")
        newest = _corpus_freshness()
        self.assertIsNotNone(newest, "corpus carries no usable published_date")
        oldest_fixture_row = fixture_date(HOME_RECORDS - 1)
        self.assertGreater(
            oldest_fixture_row, newest[:10],
            "the fixture horizon has drifted into the corpus: the oldest row "
            "of a %d-day descending series (%s) no longer outranks the "
            "corpus's newest record (%s), so build_fixture's own premise "
            "check will fail" % (HOME_RECORDS, oldest_fixture_row, newest[:10]))

    def test_the_horizon_is_derived_rather_than_written_down(self):
        """A date literal here is the defect, not the fix."""
        source = Path(__file__).read_text(encoding="utf-8")
        body = source.split("class TestTheFixtureHorizon", 1)[0]
        self.assertNotIn(
            "published_date = '2026-", body,
            "a corpus rewrite is stamping a hard-coded date again")

class HomeCase(unittest.TestCase):
    """One build of the tracked corpus, shared by the structural assertions."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-home-"))
        cls.out = cls.tmp / "build"
        # These historical-issue contracts deliberately exercise the state
        # before a native Brief leads. Real publication must not change that
        # fixture; native-first behavior is covered by the publication suite.
        cls.briefs = cls.tmp / "briefs"
        cls.briefs.mkdir()
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                 briefs_dir=cls.briefs, dossiers_dir=cls.tmp / "no-dossiers")
        cls.home = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.data = gp.load_corpus(TRACKED_DB)
        cls.view = PublicView(TRACKED_DB)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def dateline(self) -> str:
        """
        The home page's dateline is the opening's LEDGER.

        It moved there with the CMW revival on 2026-09-15 and nothing else
        about it changed: same view model, same five rows, same labels, same
        run link as its footer. It is the opening's right-hand column now
        instead of a strip above the content, so `base.html` skips the strip
        on index.html and `home.html` renders the same context in its place.
        Every interior page still gets the strip.

        The contract below is unchanged, and that is the point of naming this
        helper rather than the markup: consolidation is a layout change, not
        permission to drop a disclosure.
        """
        self.assertIn('class="ledger"', self.home,
                      "the home page has no dateline ledger")
        after = self.home.split('class="ledger"', 1)[1]
        return after.split("</section>", 1)[0]

class TestARecordWithNoOriginalTitle(unittest.TestCase):
    """
    Two separate contracts, because the absence is handled in two places.

    The **builder** already refuses it. `record_citation()` requires the
    original title and substitutes nothing, so a stored record without one
    stops the build with a named refusal rather than publishing a record page
    that quietly cites its machine translation as the source text. That is the
    governed behaviour and this file does not relax it.

    The **home page** must still degrade cleanly, because the guard is what
    keeps an absent original from becoming an empty line or an orphaned rule.
    That half is rendered directly from the partial with a controlled record,
    which is the only way to exercise a state the builder refuses to reach.
    """

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        cls.tmp = Path(tempfile.mkdtemp(prefix="c1-missing-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def render_records(records, shared=None):
        if not RECORD_PARTIAL.is_file():
            raise unittest.SkipTest(
                "_records.html is not present: this tree does not carry the "
                "paired-record partial")
        """
        The home page's record partial, rendered on its own.

        Lifted as a real template rather than by string surgery: the partial is
        the unit that decides whether an original is shown, so testing it
        directly tests the decision rather than a copy of it.
        """
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                          autoescape=True, trim_blocks=True,
                          lstrip_blocks=True)
        return env.from_string(
            '{% from "_records.html" import lead_record, record_register %}'
            "{{ lead_record(records[0]) }}"
            "{{ record_register(records[1:], shared) }}"
        ).render(records=list(records), shared=shared)

    def record(self, **overrides):
        base = {"id": 1, "title_english": "An English title",
                "title_original": "原文标题", "language_tag": ZH,
                "institution": "CMC Political Work Department",
                "source_name": "PLA Daily (解放军报)",
                "source_slug": "pla_daily", "published_date": "2026-09-20"}
        base.update(overrides)
        return base

    def test_the_builder_refuses_a_record_with_no_original_title(self):
        db = self.tmp / "no-original.db"
        shutil.copy2(TRACKED_DB, db)
        # MINDEF's original title is withheld on purpose and replaced by a
        # neutral label, so the specimen must be a source that still owes one.
        con = sqlite3.connect(str(db))
        target = con.execute(
            "SELECT a.id FROM articles a JOIN sources s ON s.id = a.source_id "
            " WHERE a.analyzed_at IS NOT NULL AND s.slug != 'sg_mindef_releases' "
            " ORDER BY a.published_date DESC, a.id DESC LIMIT 1").fetchone()[0]
        con.execute("UPDATE articles SET title_original = NULL WHERE id = ?",
                    (target,))
        con.commit()
        con.close()
        with self.assertRaises(gp.CitationDataMissing) as caught:
            gp.build(self.tmp / "no-original-build", gp.PUBLIC_TITLE, db,
                     snapshot=gp.snapshot_from_corpus(db))
        self.assertIn("original title is absent", str(caught.exception))

    def test_the_withheld_mindef_title_is_a_label_never_a_stored_title(self):
        # The exemption is exact: MINDEF rows carry no stored title at all, the
        # build succeeds, and the page shows IPR's label rather than a headline.
        with read_only(str(TRACKED_DB)) as con:
            rows = con.execute(
                "SELECT a.id, a.title_original, a.title_english FROM articles a "
                "JOIN sources s ON s.id = a.source_id "
                "WHERE s.slug = 'sg_mindef_releases'").fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(r[1] is None and r[2] is None for r in rows))
        corpus = gp.load_corpus(TRACKED_DB)["corpus"]
        labels = {r["id"]: r["title_original"] for r in corpus
                  if r["source_slug"] == "sg_mindef_releases"}
        self.assertEqual(set(labels), {r[0] for r in rows})
        for rid, label in labels.items():
            self.assertEqual(label, "Source metadata — Singapore MINDEF record %d" % rid)

    def test_an_absent_original_renders_no_line_at_all(self):
        rendered = self.render_records([
            self.record(id=10),
            self.record(id=11, title_original=None),
            self.record(id=12, title_original="   "),
            self.record(id=13),
        ])
        originals = re.findall(r'<p class="original"[^>]*>(.*?)</p>',
                               rendered, re.S)
        self.assertEqual(len(originals), 2,
                         "an original was rendered for a record without one")
        for text in originals:
            with self.subTest(text=text):
                self.assertEqual(text.strip(), "原文标题")
        self.assertNotRegex(rendered, r'<p class="original"[^>]*>\s*</p>')
        self.assertNotRegex(rendered, r'<p class="original"[^>]*>\s*[·—-]\s*</p>')

    def test_no_record_borrows_a_neighbours_original(self):
        rendered = self.render_records([
            self.record(id=20, title_original="第一条原文"),
            self.record(id=21, title_original=None),
            self.record(id=22, title_original="第三条原文"),
        ])
        row = re.search(r'href="record/21\.html".*?(?=href="record/22)',
                        rendered, re.S)
        self.assertIsNotNone(row)
        self.assertNotIn("第一条原文", row.group(0))
        self.assertNotIn("第三条原文", row.group(0))

    def test_an_absent_english_title_falls_back_to_the_original(self):
        """
        The existing fallback convention, kept: a record with no machine
        translation shows its original as the heading rather than an empty
        link, and does not then repeat it beneath itself.
        """
        rendered = self.render_records([
            self.record(id=30, title_english=None,
                        title_original="只有原文标题"),
            self.record(id=31),
        ])
        self.assertIn("只有原文标题", rendered)
        self.assertEqual(rendered.count("只有原文标题"), 1)

if __name__ == "__main__":                                  # pragma: no cover
    unittest.main()


class TestReviewedHome(HomeCase):
    def test_fresh_tree_contains_pinned_natural_jpeg_fallback(self):
        # The build still ships this file although no page shows it any more
        # (the renderer owner retires unused assets separately). While it is
        # shipped it must be the pinned original, byte for byte.
        import hashlib
        source = REPO_ROOT / "site/assets/editorial/reagan-jmsdf-2015.jpg"
        emitted = self.out / "assets/editorial/reagan-jmsdf-2015.jpg"
        if not emitted.exists():
            self.skipTest("the retired opening photograph is no longer shipped")
        self.assertEqual(hashlib.sha256(emitted.read_bytes()).hexdigest(),
                         hashlib.sha256(source.read_bytes()).hexdigest())

    def test_the_home_page_carries_no_scenery_photograph(self):
        """The opening photograph was retired on 2026-11-14. The only pictures
        the page may carry are the identity mark and an admitted Brief cover."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        self.assertFalse(soup.select('picture, .pacific-photo, .photo-credit'))
        for img in soup.find_all('img'):
            self.assertTrue(
                'brand-mark' in img.get('class', [])
                or img.find_parent(class_='home-feature-photo') is not None,
                img.get('src'))
        self.assertNotIn('assets/editorial/', self.home)
        self.assertNotIn('assets/frontend/', self.home)

    def test_one_reading_h1_and_selected_identity(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        self.assertEqual(len(soup.find_all('h1')), 1)
        self.assertEqual(soup.h1.get_text(' ', strip=True), 'The region, in its own words.')
        self.assertIn('selected-ipr/ipr-ivory-', str(soup.header))

    def test_current_snapshot_and_search_scope(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        snapshot = gp.snapshot_from_corpus(TRACKED_DB)
        total = '{:,}'.format(snapshot['expected_records'])
        flat = lambda node: ' '.join(node.get_text(' ').split())
        # The total, tied to the date it was true on, in the dateline ...
        self.assertIn('%s records, as of %s' % (total, gp.reader_date(snapshot['date'])),
                      flat(soup.select_one('.masthead .publication-status')))
        # ... and again beside the search, with what the search reads.
        self.assertIn('%s records. Search reads titles only.' % total,
                      flat(soup.select_one('.home-open-note')))
        form = soup.select_one('form.home-search')
        self.assertEqual(form['action'], 'archive.html')
        self.assertEqual(form.select_one('input[name=scope]')['value'], 'all')
        self.assertEqual(flat(form.select_one('label[for=home-q]')),
                         'Search record titles, in English or the original language')
        self.assertIn('a link to the original', flat(soup.select_one('dl.home-legend')))
        self.assertIn('Coverage is selective', flat(soup.select_one('.footer-standing')))
        # Desks with no public records are named once, each with its
        # registry state verbatim, never drawn as an empty row.
        empty = soup.select_one('.home-desks-empty')
        from core.desk_registry import load_registry
        for entry in load_registry().public_entries:
            held = any(r.get('desk_id') == entry.slug for r in self.data['corpus'])
            with self.subTest(desk=entry.slug):
                if held:
                    self.assertNotIn(entry.name, flat(empty))
                else:
                    self.assertIn('%s (%s)' % (entry.name, entry.status_label), flat(empty))
                    self.assertIsNotNone(empty.select_one('a[href="%s"]' % entry.route))

    def test_latest_rows_keep_governed_titles_languages_and_links(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        # One row per desk that holds public records, in registry order:
        # the first row of that desk's own page (desk_front_rows).
        rows = soup.select('.home-newest .record-row')
        held = [d for d in self.view.desk_directory() if d.record_count]
        self.assertEqual(len(rows), len(held))
        self.assertEqual([c.a.get_text(strip=True) for c in soup.select('.home-newest .desk-cell')],
                         [d.name for d in held])
        by_id = {r['id']: r for r in self.data['corpus']}
        for row in rows:
            link = row.select_one('h3 a')
            governed = by_id[int(Path(link['href']).stem)]
            record = BeautifulSoup((self.out / link['href']).read_text(), 'html.parser')
            self.assertEqual(link.get_text(' ', strip=True), record.h1.get_text(' ', strip=True))
            self.assertEqual(link.get_text(' ', strip=True),
                             governed['title_english'] or governed['title_original'])
            original = row.select_one('.original')
            # Vietnam records publish no original title (public_title_display
            # is false), so a missing original is never paired.
            paired = bool(governed['title_english'] and governed['title_original']
                          and governed['title_original'].strip()
                          != governed['title_english'].strip())
            self.assertEqual(original is not None, paired)
            if paired:
                self.assertEqual(original.get_text(' ', strip=True), governed['title_original'])
                self.assertEqual(original.get('lang'), governed['language_tag'] or None)
            else:
                self.assertEqual(row.h3.get('lang'),
                                 (governed['language_tag'] or None)
                                 if not governed['title_english'] else None)
            # The date in the row's meta line is the source-stated one.
            self.assertEqual(row.select_one('.row-side time')['datetime'],
                             governed['published_date'])
        # The record the page opens on exercises the translated title pair
        # even when every newest arrival has only an original title.
        selected = soup.select_one('.home-open .specimen')
        link = selected.select_one('h2 a')
        governed = by_id[int(Path(link['href']).stem)]
        self.assertEqual(link.get_text(' ', strip=True),
                         governed['title_english'] or governed['title_original'])
        head = selected.select_one('.specimen-head')
        self.assertIn('evidence--record', head.span['class'])
        self.assertIn(governed['institution'] or governed['source_name'],
                      head.get_text(' ', strip=True))
        self.assertEqual(head.select_one('time')['datetime'], governed['published_date'])
        original = selected.select_one('p.specimen-original')
        # The selected live record may have no machine title. The template
        # must show an original-title pair only when the two titles differ,
        # and must not claim translation for a source-language-only record.
        paired = bool(governed['title_english'] and governed['title_original'].strip()
                      and governed['title_original'].strip()
                      != governed['title_english'].strip())
        self.assertEqual(original is not None, paired)
        if paired:
            self.assertEqual(original.get_text(' ', strip=True), governed['title_original'])
            self.assertEqual(original.get('lang'), governed['language_tag'] or None)
            label = selected.select_one('.specimen-head--english')
            self.assertEqual(label.select_one('.evidence--model').get_text(strip=True),
                             'Machine translation')
            self.assertIn(
                'Human review not recorded'
                if governed['desk_id'] == 'china' and governed['language_tag'] != 'en'
                else 'Not reviewed by a person', label.get_text(' ', strip=True))
        else:
            self.assertNotIn('Machine translation', str(selected))
            self.assertEqual(selected.select_one('h2').get('lang'),
                             (governed['language_tag'] or None)
                             if not governed['title_english'] else None)

    def test_human_brief_and_machine_record_labels_are_explicit(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(self.home, 'html.parser')
        self.assertIn('Machine translation', self.home)
        briefs = soup.select_one('section#analysis.home-briefs')
        self.assertEqual(
            briefs.select_one('.home-head .evidence--analysis').get_text(strip=True),
            'Human-controlled analysis')
        self.assertEqual(briefs.h2.get_text(strip=True), 'Briefs')
        # This build has no native Brief, so the feature is an earlier issue
        # and says so; it never borrows the "Latest" label.
        feature = briefs.select_one('.home-feature')
        self.assertRegex(feature.select_one('.home-label').get_text(strip=True),
                         r'^Earlier Brief, No\. \d+$')
        self.assertEqual(feature.select_one('a.text-link').get_text(strip=True),
                         'Read this Brief')
        self.assertEqual(feature.select_one('a.text-link')['href'],
                         feature.h3.a['href'])
        # No machine mark inside the human-analysis section.
        self.assertFalse(briefs.select('.evidence--model'))

    def test_self_hosted_faces_and_native_mobile_menu(self):
        self.assertIn('href="fonts.css"', self.home)
        self.assertNotIn('fonts.googleapis.com', self.home)
        self.assertIn('class="shell-menu nav-mobile"', self.home)


@unittest.skipUnless(TRACKED_DB.exists(), "production database not present")
class TestTheHomeBriefCoverIsCredited(unittest.TestCase):
    """
    The only photograph the home page may show is the latest Brief's admitted
    cover (core/catalogue_media.py). When it shows one it must carry the whole
    credit the Briefs page carries: creator, licence, source, change note and
    the reminder that the picture is context rather than evidence. When the
    lead has no admission there is no picture at all.

    The lead below is a non-synthetic copy of the fixture Brief; the resolver
    is patched to admit it with No. 8's real admitted record, as
    `tests/test_catalogue_media.py` does for the Briefs page.
    """

    @classmethod
    def setUpClass(cls):
        import copy
        import functools
        from core import catalogue_media as cm
        from tests import brief_fixtures
        cls.root = Path(tempfile.mkdtemp(prefix="home-cover-"))
        slug = brief_fixtures.FIXTURE_SLUG
        side = copy.deepcopy(json.loads(
            (brief_fixtures.FIXTURE_DIR / (slug + ".json")).read_text(encoding="utf-8")))
        side.pop("synthetic", None)
        side.pop("fixture_note", None)
        briefs = cls.root / "briefs-src"
        shutil.copytree(brief_fixtures.FIXTURE_DIR, briefs)
        (briefs / (slug + ".json")).write_text(json.dumps(side), encoding="utf-8")
        brief_fixtures.write_synthetic_veil(briefs / "media" / (slug + "-veil.jpg"))
        real = cm.resolve_catalogue_media(
            {"entry": {"issue": 8, "date": "2026-06-27", "slug": "s-8"}, "kind": "issue"},
            cm.load_admissions(repo_root=REPO_ROOT), repo_root=REPO_ROOT)
        assert real.is_photograph, real.reason
        cls.photo = real.photo
        original_resolve = gp.resolve_catalogue_media
        original_collection = gp.load_collection

        def admit_the_lead(row, admissions, **kw):
            if row["entry"].get("slug") == slug:
                return cm.CatalogueMedia(cm.KIND_PHOTOGRAPH, "admitted", 8, (), real.photo)
            return original_resolve(row, admissions, **kw)

        snap = gp.snapshot_from_corpus(TRACKED_DB)
        gp.load_collection = functools.partial(original_collection, unreconciled=frozenset())
        try:
            for name, resolver in (("default", original_resolve), ("admitted", admit_the_lead)):
                gp.resolve_catalogue_media = resolver
                gp.build(cls.root / name, gp.PUBLIC_TITLE, TRACKED_DB, snapshot=snap,
                         briefs_dir=briefs, dossiers_dir=cls.root / "no-dossiers",
                         site_origin="https://briefs-review.test", allow_test_origin=True)
        finally:
            gp.resolve_catalogue_media = original_resolve
            gp.load_collection = original_collection

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def briefs(self, name):
        from bs4 import BeautifulSoup
        html = (self.root / name / "index.html").read_text(encoding="utf-8")
        return BeautifulSoup(html, "html.parser").select_one("section#analysis.home-briefs")

    def test_a_lead_without_an_admission_shows_no_picture(self):
        section = self.briefs("default")
        self.assertIsNotNone(section.select_one(".home-feature"))
        self.assertEqual(section.select("img, picture, figure, svg"), [])
        self.assertEqual(
            section.select_one(".home-feature .home-label").get_text(strip=True)[:12],
            "Latest Brief")

    def test_an_admitted_cover_carries_the_full_credit(self):
        section = self.briefs("admitted")
        figures = section.select("figure.home-feature-photo")
        self.assertEqual(len(figures), 1)
        figure, p = figures[0], self.photo
        img = figure.select_one("img")
        self.assertEqual(img["src"], p["served"])
        self.assertEqual(img["alt"], p["alt"])
        self.assertTrue(img["alt"].strip())
        self.assertEqual((img["width"], img["height"]), (str(p["width"]), str(p["height"])))
        # The picture links where the heading links, and nowhere else.
        self.assertEqual(img.find_parent("a")["href"],
                         section.select_one(".home-feature h3 a")["href"])
        caption = figure.select_one("figcaption")
        flat = " ".join(caption.get_text(" ").split())
        self.assertIn(p["caption"], flat)
        if p.get("date_note"):
            self.assertIn(p["date_note"], flat)
        self.assertIn("Photo: " + p["creator"], flat)
        if p.get("creator_native"):
            native = caption.select_one("span[lang]")
            self.assertEqual(native["lang"], p["creator_native_lang"])
            self.assertEqual(native.get_text(strip=True), p["creator_native"])
        links = {a["href"]: a.get_text(strip=True) for a in caption.select("a")}
        self.assertEqual(links.get(p["source_page"]), p["source_label"])
        if p.get("license_url"):
            self.assertEqual(links.get(p["license_url"]), p["license"])
        else:
            self.assertIn(p["license"], flat)
        self.assertIn(p["change_note"], flat)
        self.assertIn("Visual context, not evidence.", flat)
        if p.get("notice"):
            self.assertIn(p["notice"], flat)
        # The section stays under the human-analysis mark with the picture in.
        self.assertEqual(
            section.select_one(".home-head .evidence--analysis").get_text(strip=True),
            "Human-controlled analysis")

