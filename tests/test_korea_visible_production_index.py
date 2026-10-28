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
        originals = read_release_index()
        reviewed = public_registry()

        with tempfile.TemporaryDirectory(prefix="ipr-korea-status-") as tmp:
            out = Path(tmp) / "site"
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
                work = Path(tmp) / "runner"
                work.mkdir(exist_ok=True)
                if not (work / "output").exists():
                    (work / "output").symlink_to(out, target_is_directory=True)
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
            self.assertIn("Live MND link metadata", directory)
            self.assertIn("not a full-country article corpus", directory)
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
                html.count('data-korea-auto-official-link='), len(newly_listed))
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
            for source in newly_listed:
                self.assertIn(
                    'data-korea-auto-official-link="%s"' % source["source_identity"],
                    html)
            for source in all_admitted:
                expected = int(source["source_identity"] not in frozen | article_identities)
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
