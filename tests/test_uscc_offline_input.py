"""Entirely invented fixture expression. No private source prose or capture bytes."""
import unittest
from bs4 import BeautifulSoup
from core.uscc_offline_input import derive_input, _derive, _sha, USCCInputHold

URL = 'https://www.uscc.gov/press-releases/synthetic-example'
ID = 'uscc-press:synthetic-example'
RAW = (f'<html><head><link rel="canonical" href="{URL}"></head><body>'
       '<article class="press-release full" about="/press-releases/synthetic-example">'
       '<div class="field--name-field-date"><time datetime="2026-07-18T12:00:00Z">07/18/2026</time></div>'
       '<div class="field--name-body"><h2>Invented example</h2><p>Invented visit facts.</p>'
       '<p>“Invented quotation.”</p><p>Invented institutional boilerplate.</p>'
       '</div></article></body></html>').encode()

def spec(raw=RAW):
    b = BeautifulSoup(raw, 'html.parser').select_one('.field--name-body')
    return {'canonical_url': URL, 'date': '2026-07-18', 'payload_bytes': len(raw),
            'capture_sha256': _sha(raw), 'content_sha256': _sha(('\n'.join(b.stripped_strings)+'\n').encode()),
            'paragraph_text_sha256': [_sha(p.get_text(' ',strip=True).encode()) for p in b.select('p')],
            'included': [0], 'excluded': {'1': 'quotation', '2': 'boilerplate'}}

class OfflineInputTests(unittest.TestCase):
    def test_exact_input_and_complete_accounting(self):
        a = _derive(RAW, ID, URL, '2026-07-18', spec())
        self.assertEqual(a, _derive(RAW, ID, URL, '2026-07-18', spec()))
        self.assertEqual(a['potential_input']['narrative'], 'Invented visit facts.')
        self.assertEqual(len(a['manifest']['excluded_paragraphs']), 2)
        self.assertFalse(a['manifest']['model_transmission_authorized'])

    def test_public_api_does_not_accept_synthetic_or_unknown_release(self):
        with self.assertRaisesRegex(USCCInputHold, '^unsupported_publication$'):
            derive_input(RAW, source_identity=ID, canonical_url=URL, publication_date='2026-07-18')

    def test_changed_truncated_and_mismatched_inputs(self):
        cases = [(RAW+b' ', ID, URL, '2026-07-18', spec()),
                 (RAW[:-7], ID, URL, '2026-07-18', spec()),
                 (RAW, ID+'-other', URL, '2026-07-18', spec()),
                 (RAW, ID, URL, '2026-07-25', spec())]
        for args in cases:
            with self.subTest(args=args[1:4]), self.assertRaises(USCCInputHold):
                _derive(*args)

    def test_ambiguous_and_forbidden_selection(self):
        for change in ({'included': [0,1], 'excluded': {'2':'boilerplate'}},
                       {'included': [0,0]}, {'excluded': {'1':'quotation'}},
                       {'paragraph_text_sha256': ['0'*64]*3}):
            s = spec(); s.update(change)
            with self.subTest(change=change), self.assertRaises(USCCInputHold):
                _derive(RAW, ID, URL, '2026-07-18', s)

    def test_structural_failures_even_with_matching_capture_hash(self):
        for old,new in [(b'</html>',b''), (b'07/18/2026',b'07/19/2026'),
                        (b'<p>Invented visit facts.</p>',b'<p><a href="https://example.test">Invented visit facts.</a></p>'),
                        (b'<h2>',b'<h2><img src="excluded">'),
                        (b'</body>',b'<article class="press-release full"></article></body>'),
                        (b'</head>',b'<link rel="canonical" href="https://example.test"></head>')]:
            raw=RAW.replace(old,new); s=spec(raw)
            with self.subTest(old=old), self.assertRaises(USCCInputHold):
                _derive(raw,ID,URL,'2026-07-18',s)

if __name__ == '__main__': unittest.main()
