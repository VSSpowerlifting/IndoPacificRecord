"""Korea live production status cannot be hidden by frozen bibliography overlap.

All source/rights and reviewed-editorial publication registries remain
independently governed. This test only observes existing production metadata.
"""
from __future__ import annotations

import tempfile
import unittest
import io
import os
import re
import textwrap
from contextlib import redirect_stdout
from pathlib import Path
import sys

from core.korea_official_live_links import load_live_korea_official_links
from core.korea_public_bibliography import load_public_korea_links
from core.korea_additional_public_links import load_additional_korea_official_links
from core.korea_published_originals import read_release_index
from core.korea_english_publication import public_registry
from core import official_link_index as link_index
# The writer gates import these after chdir into a scratch runner directory,
# where the repository root is no longer importable through sys.path[0].
import scripts.verify_korea_official_link_index  # noqa: F401
import scripts.verify_regional_source_index_readback  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


class KoreaLiveMetadataCountTests(unittest.TestCase):
    def test_real_production_counts_beyond_previously_curated_links(self):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as preview
        db = ROOT / "pla_watch.db"
        all_admitted = load_live_korea_official_links(db)
        self.assertGreater(len(all_admitted), 0,
                           "verified Korea production metadata cannot silently disappear")
        mnd_count = sum(row["source_identity"].startswith("korea-policy:")
                        for row in all_admitted)
        dapa_count = sum(row["source_identity"].startswith("korea-dapa-policy:")
                         for row in all_admitted)
        self.assertEqual(mnd_count + dapa_count, len(all_admitted))
        bibliography = load_public_korea_links() + load_additional_korea_official_links()
        frozen = {r["source_identity"] for r in bibliography}
        article_routes = preview.load_corpus(db)["korea_publishable"]
        article_identities = set(article_routes.values())
        newly_listed = [r for r in all_admitted
                        if r["source_identity"] not in frozen | article_identities]
        # The desk rail shows only the newest DESK_LINK_LIMIT of these; the
        # official-link hub and month pages list every one exactly once.
        shown = link_index.latest("korea", newly_listed)
        shown_ids = {r["source_identity"] for r in shown}
        originals = read_release_index()
        reviewed = public_registry()

        with tempfile.TemporaryDirectory(prefix="ipr-korea-status-") as tmp:
            # The gates refuse a symlinked site directory, so the renderer
            # writes the runner's real output/ tree directly.
            work = Path(tmp) / "runner"
            out = work / "output"
            preview.build(out, "Indo-Pacific Record", db,
                          snapshot=preview.snapshot_from_corpus(db),
                          site_origin="https://indopacificrecord.org")
            html = (out / "korea.html").read_text(encoding="utf-8")
            # Execute the publishers' actual post-render gates. A completed
            # shared record replaces its bare link in the renderer; comparing
            # the rail against every DB admission used to fail both writers.
            for name in ("korea_verified_official_link_production.yml",
                         "korea_standing_original_text_production.yml"):
                flow = (ROOT / ".github/workflows" / name).read_text()
                blocks = re.findall(r"          python - <<'PY'\n(.*?)          PY", flow, re.S)
                check = next(block for block in blocks
                             if "data-korea-auto-official-link=" in block)
                if not (work / "pla_watch.db").exists():
                    (work / "pla_watch.db").symlink_to(db)
                previous = Path.cwd()
                try:
                    os.chdir(work)
                    with redirect_stdout(io.StringIO()):
                        exec(compile(textwrap.dedent(check), name, "exec"), {})
                    # Missing or duplicated metadata still fails the real gate.
                    for changed in (html.replace('data-korea-auto-official-link=',
                                                  'data-missing-link=', 1),
                                    html + '<li data-korea-auto-official-link="duplicate">'):
                        (out / "korea.html").write_text(changed, encoding="utf-8")
                        with self.assertRaises(AssertionError), redirect_stdout(io.StringIO()):
                            exec(compile(textwrap.dedent(check), name, "exec"), {})
                    (out / "korea.html").write_text(html, encoding="utf-8")
                    # A month page that drops or duplicates a row, or a hub
                    # whose total disagrees with SQLite, fails the gate too.
                    if newly_listed:
                        month = out / link_index.month_route(
                            "korea", link_index.partition("korea", newly_listed)[0][0])
                        hub = out / link_index.hub_route("korea")
                        for target, original in ((month, month.read_text(encoding="utf-8")),
                                                 (hub, hub.read_text(encoding="utf-8"))):
                            if target == month:
                                variants = (
                                    original.replace('data-korea-auto-official-link=',
                                                     'data-missing-link=', 1),
                                    original.replace('</ol>', '<li data-korea-auto-official-link="'
                                                     + newly_listed[0]["source_identity"]
                                                     + '"></li></ol>', 1))
                            else:
                                variants = (original.replace(
                                    'data-official-link-total="%d"' % len(newly_listed),
                                    'data-official-link-total="%d"' % (len(newly_listed) + 1)),)
                            try:
                                for changed in variants:
                                    self.assertNotEqual(changed, original)
                                    target.write_text(changed, encoding="utf-8")
                                    with self.assertRaises(AssertionError), \
                                            redirect_stdout(io.StringIO()):
                                        exec(compile(textwrap.dedent(check), name, "exec"), {})
                            finally:
                                target.write_text(original, encoding="utf-8")
                finally:
                    os.chdir(previous)
                    (out / "korea.html").write_text(html, encoding="utf-8")
            directory = (out / "desks.html").read_text(encoding="utf-8")
            self.assertIn(
                'data-korea-directory-mnd-metadata="%d"' % mnd_count,
                directory)
            self.assertIn(
                'data-korea-directory-scope-count="%d"' % mnd_count,
                directory)
            self.assertIn("MND official pages linked", directory)
            self.assertIn("This is not full coverage of the country", directory)
            korea_card = directory.split('id="desk-korea"', 1)[1].split(
                '</section>', 1)[0]
            self.assertIn("desk--live", directory.split(
                'id="desk-korea"', 1)[0][-350:])
            self.assertIn("Live — collecting", korea_card)
            self.assertNotIn("Not admitted", korea_card)
            self.assertIn(
                'data-korea-production-admitted-count="%d"' % len(all_admitted),
                html)
            self.assertIn(
                "MND and DAPA official-source archive" if dapa_count
                else "MND official-source production live", html)
            self.assertIn('data-korea-mnd-count="%d"' % mnd_count, html)
            self.assertIn('data-korea-dapa-count="%d"' % dapa_count, html)
            self.assertNotIn("Research-only source family; no DAPA records admitted", html)
            self.assertIn(
                "contains %d separately admitted official-link metadata records"
                % len(all_admitted), html)
            self.assertIn(
                "links to %d licensed Korean original-text releases" % len(originals),
                html)
            self.assertIn(
                "%d editor-approved English translation" % len(reviewed),
                html)
            self.assertEqual(
                html.count('data-korea-auto-official-link='), len(shown))
            self.assertEqual(len(shown), min(len(newly_listed), link_index.DESK_LINK_LIMIT))
            index_pages = [out / route for route in link_index.index_routes("korea", newly_listed)]
            self.assertTrue(all(page.is_file() for page in index_pages))
            indexed = "".join(page.read_text(encoding="utf-8") for page in index_pages)
            self.assertEqual(indexed.count('data-korea-auto-official-link='), len(newly_listed))
            for source in newly_listed:
                self.assertEqual(indexed.count(
                    'data-korea-auto-official-link="%s"' % source["source_identity"]), 1)
            for article_id, identity in article_routes.items():
                self.assertNotIn('data-korea-auto-official-link="%s"' % identity, indexed)
            self.assertEqual(
                html.count('href="%s"' % link_index.hub_route("korea")),
                1 if newly_listed else 0)
            self.assertIn('data-korea-production-lanes', html)
            self.assertIn('Live MND official-link metadata</dt><dd>%d</dd>'
                          % mnd_count, html)
            self.assertIn('Published Korean originals</dt><dd>%d</dd>'
                          % len(originals), html)
            self.assertIn('Reviewed English translations and analyses</dt><dd>%d</dd>'
                          % len(reviewed), html)
            self.assertNotIn('Article-corpus records</dt><dd>Not admitted', html)
            self.assertIn("labeled as\nunreviewed machine output", html)
            self.assertIn(
                'DAPA production source</dt><dd>Link metadata admitted'
                if dapa_count else
                'DAPA production source</dt><dd>Not qualified', html)
            if dapa_count:
                self.assertIn(
                    'Live DAPA official-link metadata</dt><dd>%d</dd>' % dapa_count,
                    html)
            self.assertNotIn(
                'This desk has no admitted records in the public IPR corpus.', html)
            self.assertEqual(html.count('data-korea-public-link='), 5)
            self.assertEqual(html.count('data-korea-additional-link='), 9)
            for source in shown:
                self.assertIn(
                    'data-korea-auto-official-link="%s"' % source["source_identity"],
                    html)
            for source in all_admitted:
                expected = int(source["source_identity"] in shown_ids)
                self.assertEqual(html.count(
                    'data-korea-auto-official-link="%s"' % source["source_identity"]
                ), expected)
            for article_id in article_routes:
                self.assertIn('href="record/%d.html"' % article_id, html)
            self.assertIn("DAPA original documents and English assessments require separate review", html)
            self.assertNotIn("original-source archive remains restricted", html)
            self.assertNotIn("text_original", html)
            self.assertNotIn("summary_english", html)
            self.assertFalse((ROOT / "pla_watch.db-wal").exists())
            self.assertFalse((ROOT / "pla_watch.db-shm").exists())

    def test_actual_writer_runs_on_status_template_changes_but_stays_scoped(self):
        path = ROOT / ".github/workflows/korea_verified_official_link_production.yml"
        flow = path.read_text(encoding="utf-8")
        self.assertIn("- site/preview/generate_preview.py", flow)
        self.assertIn("- site/preview/templates/desk.html", flow)
        self.assertIn("git add -- pla_watch.db output/korea.html", flow)
        self.assertIn("cp ../output/korea.html korea.html", flow)
        self.assertIn("cmp ../output/korea.html korea.html", flow)


if __name__ == "__main__":
    unittest.main()
