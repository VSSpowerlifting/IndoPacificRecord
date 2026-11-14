"""USCC standing-family qualifier tests.

SYNTHETIC: every HTML fixture here is invented expression, not a USCC release.
Synthetic success shows the code path works; it is not evidence that any real
release qualifies. Authentic evidence is the optional private replay at the end
(skipped unless IPR_USCC_PRIVATE_EVIDENCE names the private custody directory),
which prints and asserts hashes and dispositions only.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core import uscc_offline_input as Q
from core.uscc_offline_input import USCCInputHold, qualify, qualify_admitted
from core.uscc_official_metadata import create_schema, load_public_links

SLUG = 'press-release-synthetic-example'
URL = 'https://www.uscc.gov/press-releases/' + SLUG
ID = 'uscc-press:' + SLUG
DAY = '2026-07-18'
NARRATIVE = 'Invented delegation visit facts.'
QUOTE = '“Invented quotation sentence.”'
BOILER = 'Invented institutional boilerplate sentence.'
SOCIAL = ('<p><a href="https://x.com/i">X</a><br><a href="https://www.linkedin.com/i">'
          'LinkedIn</a></p>')
ROBOTS = b'User-agent: *\nAllow: /\n'
AGENT = 'IndoPacificRecordResearchBot/1.0 (+https://indopacificrecord.org/about.html)'
COMMIT = 'a' * 40


def page(body=None, title='Invented example', head='', footer='', date='07/18/2026'):
    body = body if body is not None else (
        f'<p><em>Invented</em> subtitle.</p><p>{NARRATIVE}</p><p>{QUOTE}</p><p>{BOILER}</p>{SOCIAL}')
    return (f'<html><head><link rel="canonical" href="{URL}">{head}</head><body>'
            f'<article class="press-release full" about="/press-releases/{SLUG}">'
            f'<div class="field--name-field-date"><time datetime="{DAY}T12:00:00Z">{date}</time></div>'
            f'<div class="field--name-body"><h2>{title}</h2>{body}</div></article>'
            f'{footer}</body></html>').encode()


RAW = page()


def access(raw=RAW, robots=ROBOTS, **change):
    a = {'capture_sha256': hashlib.sha256(raw).hexdigest(), 'payload_bytes': len(raw),
         'requested_url': URL, 'final_url': URL, 'http_status': 200,
         'content_type': 'text/html; charset=utf-8', 'retrieved_utc': '2026-11-03T00:00:00Z',
         'user_agent': AGENT, 'robots_sha256': hashlib.sha256(robots).hexdigest()}
    a.update(change)
    return a


def run(raw=RAW, ident=ID, acc=None, robots=ROBOTS, day=DAY):
    return qualify(raw, source_identity=ident, canonical_url=URL, publication_date=day,
                   access=access(raw, robots) if acc is None else acc, robots_txt=robots)


class SyntheticEligibilityTests(unittest.TestCase):
    """SYNTHETIC positive path and complete paragraph accounting."""

    def test_synthetic_release_passes_all_six_checks(self):
        out = run()
        self.assertEqual(out, run())  # deterministic
        m = out['manifest']
        self.assertEqual(m['checks_passed'], list(Q.CHECKS))
        self.assertEqual([p['index'] for p in m['included_paragraphs']], [0, 1])
        self.assertEqual({p['index']: p['reason'] for p in m['excluded_paragraphs']},
                         {2: 'quotation', 3: 'institutional_boilerplate_and_social_labels',
                          4: 'institutional_boilerplate_and_social_labels'})
        self.assertEqual(out['potential_input']['narrative'],
                         'Invented subtitle.\n\n' + NARRATIVE)
        for flag in ('model_transmission_authorized', 'publication_authorized',
                     'complete_original_input'):
            self.assertIs(m[flag], False)
        # 90 words is an output size limit on a later note, never an authorization.
        self.assertEqual(m['potential_note_max_words'], 90)
        self.assertEqual(m['public_scope'], 'official_link_only')

    def test_excluded_content_never_reaches_input_or_manifest(self):
        out = run()
        text = out['potential_input']['narrative']
        for excluded in (QUOTE, BOILER, 'LinkedIn', 'x.com'):
            self.assertNotIn(excluded, text)
        blob = json.dumps(out['manifest'], ensure_ascii=False)
        for prose in (NARRATIVE, QUOTE, BOILER, 'Invented example', 'subtitle'):
            self.assertNotIn(prose, blob)


class IndividualHoldTests(unittest.TestCase):
    """SYNTHETIC negative cases: each failure holds the whole release with a fixed code."""

    def hold(self, code, **kw):
        with self.assertRaises(USCCInputHold) as cm:
            run(**kw)
        self.assertEqual(str(cm.exception), code)
        self.assertNotIn('Invented', str(cm.exception))

    def test_identity_and_source_specific_holds(self):
        self.hold('publication_identity_mismatch', ident=ID + '-other')
        june = 'uscc-press:press-release-plain-english-guide-ai-tech-stack'
        self.hold('source_specific_hold', ident=june)

    def test_changed_and_truncated_captures(self):
        a = access()
        self.hold('access_receipt_mismatch', raw=RAW + b' ', acc=a)
        self.hold('access_receipt_mismatch', raw=RAW[:-7], acc=a)
        cut = RAW[:-7]
        self.hold('incomplete_html', raw=cut, acc=access(cut))

    def test_access_conditions(self):
        self.hold('access_receipt_missing', acc={})
        self.hold('access_receipt_missing', acc={**access(), 'extra': 1})
        self.hold('access_redirect_or_url_mismatch', acc=access(final_url=URL + '?x'))
        self.hold('access_not_public_html', acc=access(http_status=403))
        self.hold('access_not_public_html', acc=access(content_type='application/pdf'))
        self.hold('robots_receipt_mismatch', acc=access(robots_sha256='0' * 64))
        blocked = b'User-agent: *\nDisallow: /press-releases/\n'
        self.hold('robots_restricted', robots=blocked, acc=access(robots=blocked))
        gated = page(footer='<form><input type="password"></form>')
        self.hold('access_gate_present', raw=gated, acc=access(gated))
        notice = page(footer='<footer>Copyright 2026 Example. All rights reserved.</footer>')
        self.hold('source_notice_present', raw=notice, acc=access(notice))

    def test_structure_and_date(self):
        for raw, code in [
            (page(date='07/19/2026'), 'source_date_mismatch'),
            (page(date='not a date'), 'invalid_visible_date'),
            (page(body=f'<p>{NARRATIVE}</p><img src="x"><p>{BOILER}</p>{SOCIAL}'),
             'unsupported_body_content'),
            (page(body=f'<p>{NARRATIVE}</p><div>x</div><p>{BOILER}</p>{SOCIAL}'),
             'unrecognized_release_structure'),
            (page(head='<link rel="canonical" href="https://example.test/">'),
             'ambiguous_identity'),
            (page(body=f'<p>{NARRATIVE} <time datetime="{DAY}">07/18/2026</time></p>'
                       f'<p>{BOILER}</p>{SOCIAL}'), 'ambiguous_body_or_date'),
            (page(title='Invented example</h2><h2>Second invented title'), 'ambiguous_title'),
        ]:
            with self.subTest(code=code):
                self.hold(code, raw=raw, acc=access(raw))
        self.hold('source_date_mismatch', day='2026-07-25')

    def test_contractor_or_third_party_authorship_holds(self):
        for raw in (page(body=f'<p>Prepared by Example Contractor LLC.</p><p>{BOILER}</p>{SOCIAL}'),
                    page(body=f'<p>{NARRATIVE}</p><p>Source: Example Institute</p><p>{BOILER}</p>{SOCIAL}'),
                    page(body=f'<p>{NARRATIVE} Commissioned from Example Group.</p><p>{BOILER}</p>{SOCIAL}'),
                    page(head='<meta name="author" content="Example Person">'),
                    page(footer='<span rel="author">Example</span>')):
            with self.subTest(raw=len(raw)):
                self.hold('authorship_indicator_present', raw=raw, acc=access(raw))

    def test_linked_works_attachments_and_media_hold(self):
        for raw in (page(body=f'<p>{NARRATIVE} <a href="https://www.uscc.gov/x.pdf">report</a></p>'
                              f'<p>{BOILER}</p>{SOCIAL}'),
                    page(body=f'<p>{NARRATIVE}</p><p><a href="https://example.test">x</a></p>'
                              f'<p>{BOILER}</p>{SOCIAL}')):
            with self.subTest(raw=len(raw)):
                self.hold('linked_work_present', raw=raw, acc=access(raw))
        video = page(body=f'<p>{NARRATIVE}</p><video></video><p>{BOILER}</p>{SOCIAL}')
        self.hold('unsupported_body_content', raw=video, acc=access(video))

    def test_ambiguous_or_non_narrative_releases_hold(self):
        for raw, code in [
            # narrative resumes after a quotation: selection is ambiguous
            (page(body=f'<p>{NARRATIVE}</p><p>{QUOTE}</p><p>More facts.</p><p>{BOILER}</p>{SOCIAL}'),
             'unrecognized_release_structure'),
            # no recognised social-labels paragraph
            (page(body=f'<p>{NARRATIVE}</p><p>{QUOTE}</p><p>{BOILER}</p>'),
             'unrecognized_release_structure'),
            # quotations only
            (page(body=f'<p>{QUOTE}</p><p>{BOILER}</p>{SOCIAL}'), 'no_official_narrative'),
            (page(title='Opening statement of a Commissioner'), 'speech_or_testimony'),
            (page(body=f'<p>Commissioner testimony before Congress.</p><p>{BOILER}</p>{SOCIAL}'),
             'speech_or_testimony'),
            (page(body=f'<p><table><tr><td>x</td></tr></table></p><p>{BOILER}</p>{SOCIAL}'),
             'unsupported_body_content'),
        ]:
            with self.subTest(code=code):
                self.hold(code, raw=raw, acc=access(raw))


class LifecycleReceiptTests(unittest.TestCase):
    """SYNTHETIC lifecycle binding: receipts beside the existing admitted record."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'pla_watch.db'
        self.con = sqlite3.connect(self.db)
        create_schema(self.con)
        self.con.execute("""INSERT INTO uscc_official_source_records VALUES
            (?,?,?,?,?,?,?,?,?)""", (ID, URL, DAY, 'us_china_economic_security_review_commission',
            'www.uscc.gov', 'https://www.uscc.gov/press-releases', DAY, 'b' * 40,
            'official_link_only'))
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def admit(self, raw=RAW, ident=ID, supersedes=None, recorded='2026-11-07T00:00:00Z'):
        return qualify_admitted(self.con, raw, source_identity=ident, access=access(raw),
                                robots_txt=ROBOTS, custody_commit=COMMIT,
                                recorded_utc=recorded, supersedes=supersedes)

    def rows(self):
        return self.con.execute("""SELECT capture_sha256, disposition, hold_code,
            supersedes_capture_sha256, change_summary_json
            FROM uscc_narrative_eligibility_receipts ORDER BY rowid""").fetchall()

    def test_unadmitted_identity_holds_without_receipt(self):
        with self.assertRaisesRegex(USCCInputHold, '^not_admitted_metadata_record$'):
            self.admit(ident=ID + '-unadmitted')
        with self.assertRaisesRegex(USCCInputHold, '^custody_commit_invalid$'):
            qualify_admitted(self.con, RAW, source_identity=ID, access=access(),
                             robots_txt=ROBOTS, custody_commit='x', recorded_utc='t')

    def test_eligible_receipt_is_idempotent_and_hash_only(self):
        receipt, potential = self.admit()
        self.assertEqual(receipt['disposition'], 'eligible')
        self.assertEqual(potential, run()['potential_input'])
        self.assertEqual(self.admit()[0]['disposition'], 'eligible')  # same capture
        self.assertEqual(len(self.rows()), 1)
        dump = '\n'.join(self.con.iterdump())
        for prose in (NARRATIVE, QUOTE, BOILER, 'Invented example', 'subtitle'):
            self.assertNotIn(prose, dump)

    def test_new_version_requires_explicit_supersession_and_records_change(self):
        first, _ = self.admit()
        changed = page(body=f'<p>{NARRATIVE}</p><p>Added invented fact.</p><p>{QUOTE}</p>'
                            f'<p>{BOILER}</p>{SOCIAL}')
        with self.assertRaisesRegex(USCCInputHold, '^supersession_unexplained$'):
            self.admit(changed)
        receipt, potential = self.admit(changed, supersedes=first['capture_sha256'],
                                        recorded='2026-11-08T00:00:00Z')
        self.assertEqual(receipt['disposition'], 'eligible')
        self.assertIn('Added invented fact.', potential['narrative'])
        self.assertEqual(receipt['change_summary']['paragraphs_before'], 5)
        self.assertEqual(len(receipt['change_summary']['added_sha256']), 1)
        self.assertEqual(self.rows()[-1][3], first['capture_sha256'])

    def test_held_version_never_auto_reopens(self):
        bad = page(body=f'<p>Prepared by Example Contractor.</p><p>{BOILER}</p>{SOCIAL}')
        receipt, potential = self.admit(bad)
        self.assertEqual((receipt['disposition'], receipt['hold_code'], potential),
                         ('held', 'authorship_indicator_present', None))
        receipt, potential = self.admit(RAW, supersedes=receipt['capture_sha256'])
        self.assertEqual((receipt['disposition'], receipt['hold_code'], potential),
                         ('held', 'prior_version_held', None))
        # Re-qualifying the recorded held capture stays held and adds no row.
        receipt, potential = self.admit(RAW, supersedes=receipt['capture_sha256'])
        self.assertEqual((receipt['disposition'], receipt['hold_code'], potential),
                         ('held', 'prior_version_held', None))
        self.assertEqual(len(self.rows()), 2)

    def test_url_and_date_come_from_lifecycle_record(self):
        self.con.execute("UPDATE uscc_official_source_records SET publisher_posted_date='2026-07-25'")
        receipt, potential = self.admit()
        self.assertEqual((receipt['hold_code'], potential), ('source_date_mismatch', None))

    def test_public_projection_is_unchanged_by_receipts(self):
        before = load_public_links(self.db)
        self.admit()
        self.con.commit()
        self.assertEqual(load_public_links(self.db), before)
        cols = {r[1] for r in self.con.execute(
            'PRAGMA table_info(uscc_narrative_eligibility_receipts)')}
        self.assertFalse(cols & {'title', 'narrative', 'body', 'text', 'summary'})
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("""UPDATE uscc_narrative_eligibility_receipts
                SET model_transmission_authorized=1""")


FIXTURE = json.loads((Path(__file__).resolve().parent / 'fixtures'
                      / 'uscc_accepted_regression_versions.json').read_text())
EVIDENCE = os.environ.get('IPR_USCC_PRIVATE_EVIDENCE')


class AcceptedRegressionFixtureTests(unittest.TestCase):
    """The two 11-03 accepted versions are regression cases, not an allow-list."""

    def test_fixture_is_exactly_the_two_accepted_versions(self):
        self.assertEqual(len(FIXTURE), 2)
        for key, s in FIXTURE.items():
            inc, exc = s['included'], {int(i): r for i, r in s['excluded'].items()}
            self.assertEqual(set(inc) | set(exc), set(range(len(s['paragraph_text_sha256']))))
            self.assertRegex(s['potential_input_sha256'], r'^[0-9a-f]{64}$')

    def test_runtime_has_no_exact_version_allow_list(self):
        src = Path(Q.__file__).read_text()
        self.assertNotIn('uscc_offline_accepted_versions', src)
        self.assertNotIn('uscc_accepted_regression_versions', src)


@unittest.skipUnless(EVIDENCE, 'AUTHENTIC replay needs IPR_USCC_PRIVATE_EVIDENCE (private custody)')
class AuthenticPrivateReplayTests(unittest.TestCase):
    """AUTHENTIC: preserved private captures; asserts hashes and dispositions only."""

    def test_accepted_versions_reproduce_and_june_25_holds(self):
        root = Path(EVIDENCE)
        ledger = json.loads((root / 'ledger.json').read_text())
        robots = (root / 'captures' / (ledger['robots_sha256'] + '.bin')).read_bytes()
        seen = {}
        for r in ledger['releases']:
            raw = (root / 'captures' / (r['capture_sha256'] + '.bin')).read_bytes()
            acc = {'capture_sha256': r['capture_sha256'], 'payload_bytes': r['payload_bytes'],
                   'requested_url': r['requested_url'], 'final_url': r['final_url'],
                   'http_status': r['http_status'], 'content_type': r['headers']['content-type'],
                   'retrieved_utc': r['retrieved_utc'], 'user_agent': ledger['agent'],
                   'robots_sha256': ledger['robots_sha256']}
            try:
                m = qualify(raw, source_identity=r['source_identity'],
                            canonical_url=r['requested_url'], publication_date=r['listing_date'],
                            access=acc, robots_txt=robots)['manifest']
                seen[r['source_identity']] = m
            except USCCInputHold as exc:
                seen[r['source_identity']] = str(exc)
        for key, s in FIXTURE.items():
            m = seen[key]
            self.assertEqual(m['potential_input_sha256'], s['potential_input_sha256'])
            self.assertEqual(m['capture_sha256'], s['capture_sha256'])
            self.assertEqual(m['content_sha256'], s['content_sha256'])
            self.assertEqual(m['paragraph_text_sha256'], s['paragraph_text_sha256'])
            self.assertEqual([p['index'] for p in m['included_paragraphs']], s['included'])
            self.assertEqual({str(p['index']): p['reason'] for p in m['excluded_paragraphs']},
                             s['excluded'])
        self.assertEqual(seen['uscc-press:press-release-plain-english-guide-ai-tech-stack'],
                         'source_specific_hold')


if __name__ == '__main__':
    unittest.main()
