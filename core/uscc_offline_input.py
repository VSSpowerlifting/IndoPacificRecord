"""USCC standing-family narrative qualifier. Returned prose MUST stay private.

Implements the six checks of the founder-approved standing-family assessment
(docs/engineering/USCC_OFFICIAL_METADATA_COLLECTION_2026-10-15.md, "Standing-
family assessment"): a *rebuttable* 17 U.S.C. § 105 presumption for unsigned,
Commission-issued institutional press-release narrative. It replaces the earlier
exact-two adapter; the two 11-03 versions remain regression cases in tests.

No network, model, acquisition, output writer or publication path exists here.
The caller supplies bytes already in private custody plus the capture-bound
access receipt recorded at retrieval. `qualify_admitted` binds qualification to
the existing `uscc_official_source_records` lifecycle row and records a
hash-only receipt; narrative text is returned in memory only and never stored.

Qualification attaches to one exact captured version. The 90-word figure is an
output size limit on a later note, not a legal basis or an authorization.
"""
import hashlib
import json
import re
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from scripts.collect_uscc_press_metadata import canonical

POLICY = 'uscc-standing-family/1'
DECISION = ('DECISION_LOG.md#2026-11-04--founder-uscc-standing-family-assessment-text-approved-pr-987; '
            'DECISION_LOG.md#2026-11-07--founder-uscc-standing-family-adoption-and-qualifier-prepared-for-review')
CHECKS = ('first_party_identity', 'official_narrative', 'verifiable_structure',
          'authorship_indicators', 'access_conditions', 'source_specific_exclusions')
# Check 6: identity-keyed holds. Each stays held individually; never auto-reopened.
HELD_IDENTITIES = {
    'uscc-press:press-release-plain-english-guide-ai-tech-stack':
        'DECISION_LOG.md#2026-11-03--owner-exact-two-uscc-narrative-source-use-assessment-accepted',
}
SOCIAL_HOSTS = frozenset({'x.com', 'twitter.com', 'www.twitter.com', 'instagram.com',
                          'www.instagram.com', 'linkedin.com', 'www.linkedin.com',
                          'youtube.com', 'www.youtube.com', 'facebook.com',
                          'www.facebook.com'})
INLINE_TAGS = frozenset({'em', 'strong', 'span', 'i', 'b', 'br'})
MEDIA = 'script,style,img,picture,svg,iframe,object,embed,video,audio,canvas,figure,form,table'
QUOTES = ('“', '”', '"')
# Check 4 indicators (same patterns as the preserved 11-03 qualification probe).
CONTRACTED = re.compile(r'contracted|commissioned|prepared by|authored by|written by', re.I)
RIGHTS_WORDS = re.compile(r'copyright|all rights reserved|licen[cs]e|©', re.I)
CREDIT_LINE = re.compile(r'(?:^|\n)\s*(?:source|credit|byline|author|photo)\s*:', re.I)
AUTHOR_FIELDS = '[rel=author],.field--name-uid,[property=author],[itemprop=author],meta[name=author]'
# Check 2: speech, testimony or op-ed templates are not institutional narrative.
NOT_NARRATIVE = re.compile(r'\b(?:testimony|testif\w*|opening statement|prepared remarks|'
                           r'remarks (?:by|of)|op-ed|speech)\b', re.I)
# Check 5: page-level notice that could contradict the assessment, and access gates.
PAGE_NOTICE = re.compile(r'copyright|all rights reserved|terms of use|terms and conditions', re.I)
ACCESS_GATE = 'input[type=password],[class*=paywall],[id*=paywall]'
ACCESS_KEYS = frozenset({'capture_sha256', 'payload_bytes', 'requested_url', 'final_url',
                         'http_status', 'content_type', 'retrieved_utc', 'user_agent',
                         'robots_sha256'})
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
HEX40 = re.compile(r'[0-9a-f]{40}\Z')


class USCCInputHold(ValueError):
    """Fixed diagnostics only: never echo private input."""


def _need(ok, code):
    if not ok:
        raise USCCInputHold(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canon_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _check_access(raw, url, access, robots_txt):
    """Check 5: capture-bound receipt. Missing or mismatched receipt holds."""
    _need(type(access) is dict and set(access) == ACCESS_KEYS
          and type(robots_txt) is bytes and robots_txt, 'access_receipt_missing')
    _need(type(raw) is bytes and access['capture_sha256'] == _sha(raw)
          and access['payload_bytes'] == len(raw), 'access_receipt_mismatch')
    _need(access['requested_url'] == access['final_url'] == url, 'access_redirect_or_url_mismatch')
    _need(access['http_status'] == 200 and type(access['content_type']) is str
          and access['content_type'].split(';')[0].strip().lower() == 'text/html',
          'access_not_public_html')
    _need(type(access['robots_sha256']) is str and access['robots_sha256'] == _sha(robots_txt),
          'robots_receipt_mismatch')
    parser = RobotFileParser()
    try:
        parser.parse(robots_txt.decode('utf-8').splitlines())
    except UnicodeDecodeError:
        raise USCCInputHold('robots_receipt_mismatch') from None
    agent = access['user_agent']
    _need(type(agent) is str and agent and parser.can_fetch(agent, url)
          and parser.can_fetch('*', url), 'robots_restricted')


def _select(body):
    """Check 2: narrative -> quotations -> boilerplate -> social-labels template.

    Anything outside the recognised template holds the whole release. Linked
    works anywhere outside the social-label paragraph hold the whole release.
    """
    _need(all(c.name in ('h2', 'p') for c in body.find_all(recursive=False))
          and not [s for s in body.find_all(string=True, recursive=False) if s.strip()],
          'unrecognized_release_structure')
    paragraphs = [p for p in body.select('p') if p.get_text(strip=True)]
    values = [p.get_text(' ', strip=True) for p in paragraphs]
    _need(len(paragraphs) >= 3, 'unrecognized_release_structure')
    social = paragraphs[-1].find_all('a')
    _need(social and all(urlparse(a.get('href', '')).scheme == 'https'
                         and urlparse(a.get('href', '')).netloc.lower() in SOCIAL_HOSTS
                         for a in social), 'unrecognized_release_structure')
    _need(not paragraphs[-2].find('a') and not any(q in values[-2] for q in QUOTES),
          'unrecognized_release_structure')
    _need(not any(p.find('a') for p in paragraphs[:-1]), 'linked_work_present')
    included, excluded, seen_quote = [], {}, False
    for i in range(len(paragraphs) - 2):
        if any(q in values[i] for q in QUOTES):
            excluded[i], seen_quote = 'quotation', True
        else:
            _need(not seen_quote, 'unrecognized_release_structure')
            included.append(i)
    for i in (len(paragraphs) - 2, len(paragraphs) - 1):
        excluded[i] = 'institutional_boilerplate_and_social_labels'
    _need(included, 'no_official_narrative')
    _need(all({t.name for t in paragraphs[i].find_all(True)} <= INLINE_TAGS for i in included),
          'unsupported_body_content')
    return paragraphs, values, included, excluded


def qualify(raw, *, source_identity, canonical_url, publication_date, access, robots_txt):
    """Run the six checks on one exact private capture; return input + manifest.

    Raises USCCInputHold with a fixed code on the first failed check.
    """
    # Check 6 (identity-keyed) first: a held release is never parsed into input.
    _need(type(source_identity) is str and source_identity not in HELD_IDENTITIES,
          'source_specific_hold')
    # Check 1: first-party identity and canonical URL.
    c = canonical(canonical_url) if type(canonical_url) is str else None
    _need(c is not None and c[0] == canonical_url and source_identity == 'uscc-press:' + c[1],
          'publication_identity_mismatch')
    # Check 5: access conditions, bound to these exact bytes.
    _check_access(raw, canonical_url, access, robots_txt)
    # Check 3: mechanically verifiable structure.
    _need(raw.rstrip().lower().endswith(b'</html>'), 'incomplete_html')
    soup = BeautifulSoup(raw, 'html.parser')
    articles = soup.select('article.press-release.full')
    links = soup.select('link[rel="canonical"]')
    _need(len(articles) == len(links) == 1 and links[0].get('href') == canonical_url,
          'ambiguous_identity')
    article = articles[0]
    _need(article.get('about') == urlparse(canonical_url).path, 'article_identity_mismatch')
    bodies = article.select('.field--name-body')
    dates = article.select('.field--name-field-date')
    times = article.select('time')
    _need(len(bodies) == len(dates) == len(times) == 1, 'ambiguous_body_or_date')
    try:
        visible = datetime.strptime(dates[0].get_text(' ', strip=True), '%m/%d/%Y').date().isoformat()
    except ValueError:
        raise USCCInputHold('invalid_visible_date') from None
    _need(visible == publication_date and times[0].get('datetime') == publication_date + 'T12:00:00Z',
          'source_date_mismatch')
    body = bodies[0]
    _need(not body.select(MEDIA), 'unsupported_body_content')
    titles = body.select('h2')
    _need(len(titles) == 1 and titles[0].get_text(strip=True), 'ambiguous_title')
    # Check 5 (notices and access gates on the page itself).
    _need(not soup.select(ACCESS_GATE), 'access_gate_present')
    _need(not PAGE_NOTICE.search(soup.get_text('\n')), 'source_notice_present')
    # Check 4: unsigned, Commission-only identification.
    body_text = '\n'.join(body.stripped_strings)
    _need(not soup.select(AUTHOR_FIELDS) and not CONTRACTED.search(body_text)
          and not RIGHTS_WORDS.search(body_text) and not CREDIT_LINE.search(body_text),
          'authorship_indicator_present')
    # Check 2: unquoted institutional narrative only.
    paragraphs, values, included, excluded = _select(body)
    title = titles[0].get_text(' ', strip=True)
    _need(not NOT_NARRATIVE.search(title) and
          not any(NOT_NARRATIVE.search(values[i]) for i in included), 'speech_or_testimony')
    hashes = [_sha(v.encode()) for v in values]
    potential = {'title': title, 'canonical_url': canonical_url,
                 'publication_date': publication_date,
                 'narrative': '\n\n'.join(values[i] for i in included)}
    manifest = {'schema': 'ipr-uscc-family-potential-input/2', 'policy': POLICY,
                'decision_reference': DECISION, 'checks_passed': list(CHECKS),
                'source_identity': source_identity, 'canonical_url': canonical_url,
                'publication_date': publication_date,
                'capture_sha256': access['capture_sha256'],
                'content_sha256': _sha((body_text + '\n').encode()),
                'access_receipt_sha256': _sha(_canon_json(access)),
                'robots_sha256': access['robots_sha256'],
                'paragraph_text_sha256': hashes,
                'included_paragraphs': [{'index': i, 'sha256': hashes[i]} for i in included],
                'excluded_paragraphs': [{'index': i, 'sha256': hashes[i], 'reason': excluded[i]}
                                        for i in sorted(excluded)],
                'potential_input_sha256': _sha(_canon_json(potential)),
                'complete_original_input': False, 'model_transmission_authorized': False,
                'publication_authorized': False, 'public_scope': 'official_link_only',
                'potential_note_max_words': 90}
    return {'potential_input': potential, 'manifest': manifest}


def derive_input(raw, *, source_identity, canonical_url, publication_date, access, robots_txt):
    """Compatibility name for the retired exact-two entry point; same six checks."""
    return qualify(raw, source_identity=source_identity, canonical_url=canonical_url,
                   publication_date=publication_date, access=access, robots_txt=robots_txt)


# --- Lifecycle binding: hash-only receipts beside the admitted metadata rows ---

def create_receipt_schema(con):
    con.execute("""CREATE TABLE IF NOT EXISTS uscc_narrative_eligibility_receipts (
        source_identity TEXT NOT NULL REFERENCES uscc_official_source_records(source_identity),
        capture_sha256 TEXT NOT NULL,
        disposition TEXT NOT NULL CHECK (disposition IN ('eligible','held')),
        hold_code TEXT,
        policy TEXT NOT NULL,
        decision_reference TEXT NOT NULL,
        custody_commit_sha TEXT NOT NULL,
        manifest_json TEXT,
        supersedes_capture_sha256 TEXT,
        change_summary_json TEXT,
        recorded_utc TEXT NOT NULL,
        public_scope TEXT NOT NULL CHECK (public_scope='official_link_only'),
        model_transmission_authorized INTEGER NOT NULL CHECK (model_transmission_authorized=0),
        PRIMARY KEY (source_identity, capture_sha256),
        CHECK ((disposition='eligible') = (hold_code IS NULL)),
        CHECK ((disposition='eligible') = (manifest_json IS NOT NULL))
    )""")


def qualify_admitted(con, raw, *, source_identity, access, robots_txt, custody_commit,
                     recorded_utc, supersedes=None):
    """Qualify a capture of an admitted USCC record and record a hash-only receipt.

    URL and date come from the existing lifecycle row, never from the caller.
    Returns (receipt, potential_input_or_None). Same capture is idempotent. A new
    capture of an identity with an eligible version must name the version it
    supersedes; one with any held version stays held for individual review.
    """
    _need(type(custody_commit) is str and HEX40.fullmatch(custody_commit), 'custody_commit_invalid')
    row = con.execute("""SELECT canonical_official_url, publisher_posted_date
        FROM uscc_official_source_records WHERE source_identity=?""",
        (source_identity,)).fetchone() if con.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='uscc_official_source_records'""").fetchone() else None
    _need(row is not None, 'not_admitted_metadata_record')
    _need(type(raw) is bytes, 'access_receipt_mismatch')
    create_receipt_schema(con)
    url, day = row
    capture = _sha(raw)
    prior = con.execute("""SELECT capture_sha256, disposition, manifest_json, hold_code
        FROM uscc_narrative_eligibility_receipts WHERE source_identity=?
        ORDER BY rowid""", (source_identity,)).fetchall()
    hold, result = None, None
    try:
        result = qualify(raw, source_identity=source_identity, canonical_url=url,
                         publication_date=day, access=access, robots_txt=robots_txt)
    except USCCInputHold as exc:
        hold = str(exc)
    manifest = None if hold else result['manifest']  # hashes, indices, reasons only
    same = [p for p in prior if p[0] == capture]
    if same:
        if same[0][1] == 'held':
            # A recorded hold is final for this capture, whatever it recomputes to.
            return _receipt(source_identity, capture, same[0][3], None, None, None), None
        _need(not hold and same[0][2] == json.dumps(manifest, sort_keys=True),
              'recorded_receipt_changed')
        return _receipt(source_identity, capture, None, manifest, None, None), (
            result['potential_input'])
    change = None
    if any(p[1] == 'held' for p in prior):
        hold, manifest = hold or 'prior_version_held', None
    elif prior:
        latest = prior[-1]
        _need(supersedes == latest[0], 'supersession_unexplained')
        if not hold:
            old = json.loads(latest[2])['paragraph_text_sha256']
            new = manifest['paragraph_text_sha256']
            change = {'paragraphs_before': len(old), 'paragraphs_after': len(new),
                      'removed_sha256': sorted(set(old) - set(new)),
                      'added_sha256': sorted(set(new) - set(old))}
    else:
        _need(supersedes is None, 'supersession_unexplained')
    con.execute("""INSERT INTO uscc_narrative_eligibility_receipts VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (source_identity, capture, 'held' if hold else 'eligible', hold, POLICY, DECISION,
         custody_commit, None if hold else json.dumps(manifest, sort_keys=True),
         supersedes if prior and not any(p[1] == 'held' for p in prior) else None,
         None if change is None else json.dumps(change, sort_keys=True),
         recorded_utc, 'official_link_only', 0))
    return _receipt(source_identity, capture, hold, manifest, supersedes, change), (
        None if hold else result['potential_input'])


def _receipt(identity, capture, hold, manifest, supersedes, change):
    return {'source_identity': identity, 'capture_sha256': capture,
            'disposition': 'held' if hold else 'eligible', 'hold_code': hold,
            'policy': POLICY, 'manifest': manifest, 'supersedes_capture_sha256': supersedes,
            'change_summary': change, 'public_scope': 'official_link_only',
            'model_transmission_authorized': False}
