"""USCC standing-family narrative qualifier. Returned prose MUST stay private.

Implements the six checks of the founder-approved standing-family assessment
(docs/engineering/USCC_OFFICIAL_METADATA_COLLECTION_2026-10-15.md, "Standing-
family assessment"): a *rebuttable* 17 U.S.C. § 105 presumption for unsigned,
Commission-issued institutional press-release narrative. It replaces the earlier
exact-two adapter; the two 11-03 versions remain regression cases in tests.

No network, model, acquisition, output writer or publication path exists here.
The caller supplies bytes already in private custody plus the capture-bound
access receipt recorded at retrieval. The runtime caller is the shared Daily
links adapter (``core.uscc_press_links.links_from_custody``): it qualifies every
custody row at the pinned commit, passes eligible narrative only under a private
``_``-prefixed key that the lifecycle strips before anything is persisted, and
returns held rows with their fixed code so they never reach a model. Version,
attempt and hold state live in the shared queue and the link-only parent
(m0024), not here; this module keeps no state of its own.

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
# The June 25 glossary announcement is outside the 11-03 decision. The standing-
# family assessment names the 2026-08-26 and 2026-09-22 announcements as releases
# that credit an external author or organization ("Components that stay held
# individually", item 1); they are held by identity here, not only by pattern.
_ASSESSMENT = ('docs/engineering/USCC_OFFICIAL_METADATA_COLLECTION_2026-10-15.md'
               '#components-that-stay-held-individually')
HELD_IDENTITIES = {
    'uscc-press:press-release-plain-english-guide-ai-tech-stack':
        'DECISION_LOG.md#2026-11-03--owner-exact-two-uscc-narrative-source-use-assessment-accepted',
    'uscc-press:press-release-dalai-lamas-succession-geopolitical-implications-and-policy':
        _ASSESSMENT,
    'uscc-press:press-release-new-report-chinas-gray-zone-threats-trans-pacific-undersea-cables':
        _ASSESSMENT,
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


class USCCInputHold(ValueError):
    """Fixed diagnostics only: never echo private input."""


def _need(ok, code):
    if not ok:
        raise USCCInputHold(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canon_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def release_text(raw):
    """(title, text) of the one release body in a capture, or None.

    The single derivation shared by custody writing and qualification: the body
    ``h2`` as ``get_text(' ', strip=True)`` and every body string joined with LF
    plus a terminal LF, which is the text whose SHA-256 ``qualify`` reports as
    ``content_sha256`` (the 11-03 archived ``originals/<sha>.txt`` rule). None
    when the page does not hold exactly one release article, body and title; the
    qualifier then holds the capture with its own fixed code.
    """
    if type(raw) is not bytes:
        return None
    articles = BeautifulSoup(raw, 'html.parser').select('article.press-release.full')
    bodies = articles[0].select('.field--name-body') if len(articles) == 1 else []
    titles = bodies[0].select('h2') if len(bodies) == 1 else []
    if len(titles) != 1:
        return None
    return titles[0].get_text(' ', strip=True), '\n'.join(bodies[0].stripped_strings) + '\n'


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
    manifest = {'schema': 'ipr-uscc-family-potential-input/3', 'policy': POLICY,
                'decision_reference': DECISION, 'checks_passed': list(CHECKS),
                'source_identity': source_identity, 'canonical_url': canonical_url,
                'publication_date': publication_date,
                'capture_sha256': access['capture_sha256'],
                'content_sha256': _sha((body_text + '\n').encode()),
                'title_sha256': _sha(title.encode()),
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
