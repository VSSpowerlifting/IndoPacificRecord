"""Entirely invented fixture expression. No private source prose or capture bytes."""
import json
import unittest
from pathlib import Path
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
        m = a['manifest']
        # Output never authorizes transmission, publication or a complete original input;
        # the 90-word figure is a size cap on a note, not an authorization.
        self.assertFalse(m['model_transmission_authorized'])
        self.assertFalse(m['publication_authorized'])
        self.assertFalse(m['complete_original_input'])
        self.assertEqual(m['potential_note_max_words'], 90)

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

class AcceptedScopeTests(unittest.TestCase):
    """The shipped policy must stay the exact accepted two; no family or June 25 admission."""
    POLICY = json.loads((Path(__file__).resolve().parents[1]
                         / 'config/uscc_offline_accepted_versions.json').read_text())
    SLUGS = {'press-release-us-china-commission-departs-fact-finding-trip-china',
             'press-release-us-china-commission-returns-fact-finding-trip-china'}
    REASONS = {'quotation', 'institutional_boilerplate_and_social_labels'}

    def test_policy_is_exactly_the_two_accepted_captures(self):
        self.assertEqual(set(self.POLICY), {'uscc-press:' + s for s in self.SLUGS})

    def test_every_paragraph_is_included_or_excluded_with_allowed_reason(self):
        for key, s in self.POLICY.items():
            with self.subTest(key=key):
                inc, exc = s['included'], {int(i): r for i, r in s['excluded'].items()}
                self.assertTrue(inc and set(inc).isdisjoint(exc))
                self.assertEqual(set(inc) | set(exc), set(range(len(s['paragraph_text_sha256']))))
                self.assertLessEqual(set(exc.values()), self.REASONS)
                self.assertEqual(s['canonical_url'], 'https://www.uscc.gov/press-releases/' + key.split(':', 1)[1])

    def test_policy_keys_are_exact_versions_not_a_family_pattern(self):
        # A standing family would need a reviewed qualifier; the file must not smuggle one in.
        for key, s in self.POLICY.items():
            with self.subTest(key=key):
                self.assertRegex(key, r'^uscc-press:[a-z0-9-]+$')
                self.assertEqual(set(s), {'canonical_url', 'date', 'payload_bytes', 'capture_sha256',
                                          'content_sha256', 'paragraph_text_sha256',
                                          'included', 'excluded'})
                self.assertRegex(s['capture_sha256'], r'^[0-9a-f]{64}$')

    def test_changed_capture_of_each_accepted_release_holds_via_public_api(self):
        # Strict version integrity: any bytes other than the exact accepted capture hold,
        # even with the accepted identity, URL and date.
        for key, s in self.POLICY.items():
            for raw in (b'', b'x' * s['payload_bytes'], b'x' * (s['payload_bytes'] + 1)):
                with self.subTest(key=key, size=len(raw)), \
                        self.assertRaisesRegex(USCCInputHold, '^capture_version_mismatch$'):
                    derive_input(raw, source_identity=key, canonical_url=s['canonical_url'],
                                 publication_date=s['date'])

    def test_other_releases_hold_through_public_api(self):
        # June 25 (linked-work pattern) and an invented release are outside the decision.
        for slug in ('press-release-plain-english-guide-ai-tech-stack', 'press-release-not-in-decision'):
            with self.subTest(slug=slug), self.assertRaisesRegex(USCCInputHold, '^unsupported_publication$'):
                derive_input(b'', source_identity='uscc-press:' + slug,
                             canonical_url='https://www.uscc.gov/press-releases/' + slug,
                             publication_date='2026-06-25')

if __name__ == '__main__': unittest.main()
