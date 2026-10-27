"""Guard the pilot's assets, source geometry and complete delivery accounting."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from PIL import Image
from core.frontend_budget import measure_page
from scripts.verify_frontend_delivery import verify

ROOT = Path(__file__).resolve().parents[1]


class MaterialIntegrity(unittest.TestCase):
    def test_material_receipt_and_seamless_edges(self):
        directory = ROOT / 'site/assets/material'
        receipt = json.loads((directory / 'ASSET_RECEIPT.json').read_text())
        for name, values in receipt['assets'].items():
            content = (directory / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), values['sha256'])
            self.assertEqual(len(content), values['bytes'])
        with Image.open(directory / 'chart-paper.png') as image:
            self.assertEqual(list(image.size), receipt['paper']['dimensions'])
            self.assertEqual(list(image.crop((0, 0, 1, image.height)).getdata()), list(image.crop((image.width - 1, 0, image.width, image.height)).getdata()))
            self.assertEqual(list(image.crop((0, 0, image.width, 1)).getdata()), list(image.crop((0, image.height - 1, image.width, image.height)).getdata()))
            # Detail survives optimization; neutral paper stays in a small range.
            self.assertGreater(len(set(image.getdata())), 2)
            extrema = image.convert('RGB').getextrema()
            self.assertTrue(all(high - low <= 7 for low, high in extrema))
        self.assertLess((directory / 'chart-paper.png').stat().st_size, 60000)

    def test_curves_are_original_and_no_operational_marks_are_added(self):
        from urllib.parse import unquote
        original = unquote((ROOT / 'site/preview/topography.css').read_text())
        for name in ('hero', 'paper'):
            svg = ET.parse(ROOT / ('site/assets/material/contours-%s.svg' % name))
            paths = list(svg.getroot().iter('{http://www.w3.org/2000/svg}path'))
            self.assertEqual(len(paths), 36)
            self.assertEqual(len(set(path.attrib['d'] for path in paths)), 12)
            for path in paths:
                self.assertIn(path.attrib['d'], original)
            self.assertEqual(set(e.tag.split('}')[-1] for e in svg.getroot().iter()), {'svg', 'g', 'path'})


class CompleteDelivery(unittest.TestCase):
    def test_every_committed_generated_route_meets_complete_budgets(self):
        root = ROOT / 'output'
        result = verify(root)
        # The pre-retirement site had >7,000 HTML routes; October's cull
        # deliberately reduced that number. Assert every CURRENT committed
        # HTML route was checked rather than demanding deleted pages return.
        html_routes = {p.relative_to(root).as_posix()
                       for p in root.rglob('*.html') if p.is_file()}
        self.assertTrue(html_routes, "published site has no HTML routes")
        self.assertEqual(result['routes_checked'], len(html_routes))
        index = json.loads((root / 'corpus-index.json').read_text('utf-8'))
        living = {str(r[0]) + '.html' for r in index['records']}
        from core.daily_machine_records import load as load_machine_records
        machine = {Path(r['record_path']).name for r in load_machine_records(ROOT / 'pla_watch.db')}
        self.assertEqual({p.name for p in (root / 'record').glob('*.html')},
                         living | machine,
                         "retired, missing or extra record pages would go unchecked")
        self.assertEqual(result['failures'], [])

    def test_fonts_css_graphics_srcset_icons_and_inline_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'css').mkdir()
            (root / 'index.html').write_text('<link rel="stylesheet" href="css/main.css"><link rel="icon" href="icon.png"><img src="small.png" srcset="small.png 320w, large.png 640w"><style>i{background:url(small.png)}</style>')
            (root / 'css/main.css').write_text('@import url(nested.css);i{background:url(../small.png)}')
            (root / 'css/nested.css').write_text('@font-face{src:url(../face.woff2)}')
            for name, size in [('small.png', 5), ('large.png', 9), ('face.woff2', 11), ('icon.png', 3)]:
                (root / name).write_bytes(b'x' * size)
            values = measure_page(root / 'index.html', root)
            self.assertEqual(values['asset_bytes'], 28)
            self.assertEqual(values['assets'], ['face.woff2', 'icon.png', 'large.png', 'small.png'])
            self.assertEqual(len(values['css']), 2)

    def test_missing_graphic_or_font_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text('<style>i{background:url(absent.png)}</style>')
            with self.assertRaises(ValueError): measure_page(root / 'index.html', root)

    def test_all_route_gate_catches_large_record_and_combined_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'record').mkdir()
            (root / 'index.html').write_text('x' * 130000)
            (root / 'record/large.html').write_text('x' * 120001)
            (root / 'record/scripts.html').write_text('<script src="../a.js"></script><script src="../b.js"></script>')
            (root / 'a.js').write_text('x' * 6000); (root / 'b.js').write_text('x' * 6000)
            values = verify(root)
            self.assertEqual(values['routes_checked'], 3)
            self.assertEqual([v['route'] for v in values['failures']], ['record/large.html', 'record/scripts.html'])

    def test_dossier_allowance_covers_only_individual_dossier_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('dossier/nested', 'record', 'briefs', 'the-pla-watch/posts'):
                (root / folder).mkdir(parents=True)
            # Linked CSS counts toward the dossier's combined allowance.
            (root / 'dossiers.css').write_text('x' * 50000)
            link = '<link rel="stylesheet" href="../dossiers.css">'
            (root / 'dossier/within.html').write_text(link + 'x' * (200000 - 50000 - len(link)))
            (root / 'dossier/over.html').write_text(link + 'x' * (200001 - 50000 - len(link)))
            (root / 'dossier/plain.html').write_text('x' * 199999)
            (root / 'dossier/large.html').write_text('x' * 200001)
            for route in ('dossiers.html', 'dossier/index.html', 'dossier/nested/page.html', 'record/1.html',
                          'briefs/brief.html', 'the-pla-watch/posts/week.html'):
                (root / route).write_text('x' * 120001)
            (root / 'dossier/scripts.html').write_text('<script src="../a.js"></script>')
            (root / 'a.js').write_text('x' * 10001)
            values = verify(root)
            failed = {v['route']: v['html_css_limit'] for v in values['failures']}
            self.assertEqual(failed, {'briefs/brief.html': 120000, 'dossier/index.html': 120000,
                                      'dossier/large.html': 200000, 'dossier/nested/page.html': 120000,
                                      'dossier/over.html': 200000, 'dossier/scripts.html': 200000,
                                      'dossiers.html': 120000, 'record/1.html': 120000,
                                      'the-pla-watch/posts/week.html': 120000})
            limits = {v['route']: (v['html_css_limit'], v['js_limit']) for v in values['routes']}
            self.assertEqual(limits['dossier/within.html'], (200000, 10000))
            self.assertEqual(limits['dossier/plain.html'], (200000, 10000))
