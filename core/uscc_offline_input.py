"""Offline-only exact-two USCC input derivation. Returned prose MUST stay private.

No network, models, acquisition, runtime registration or output writer. The
11-03 owner decision defines the accepted exact scope (DECISION below); it does
not itself authorize implementation. The offline implementation was authorized by
the follow-up task brief, and neither authorizes sending returned input anywhere.
"""
import hashlib
import json
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from scripts.collect_uscc_press_metadata import canonical

EVIDENCE_COMMIT = '9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab'
# Scope anchor (accepted exact-two source-use assessment), not an implementation grant.
DECISION = 'DECISION_LOG.md#2026-11-03--owner-exact-two-uscc-narrative-source-use-assessment-accepted'
_POLICY = Path(__file__).resolve().parents[1] / 'config/uscc_offline_accepted_versions.json'

class USCCInputHold(ValueError):
    """Fixed diagnostics only: never echo private input."""

def _need(ok, code):
    if not ok:
        raise USCCInputHold(code)

def _sha(raw):
    return hashlib.sha256(raw).hexdigest()

def _derive(raw, identity, url, date, spec):
    """Internal extraction seam for synthetic tests; not an authority override API."""
    _need(type(raw) is bytes and len(raw) == spec['payload_bytes']
          and _sha(raw) == spec['capture_sha256'], 'capture_version_mismatch')
    _need(url == spec['canonical_url'] and date == spec['date'], 'identity_or_date_mismatch')
    c = canonical(url)
    _need(c is not None and identity == 'uscc-press:' + c[1], 'publication_identity_mismatch')
    _need(raw.rstrip().lower().endswith(b'</html>'), 'incomplete_html')
    soup = BeautifulSoup(raw, 'html.parser')
    articles = soup.select('article.press-release.full')
    links = soup.select('link[rel="canonical"]')
    _need(len(articles) == len(links) == 1 and links[0].get('href') == url, 'ambiguous_identity')
    article = articles[0]
    _need(article.get('about') == url.removeprefix('https://www.uscc.gov'), 'article_identity_mismatch')
    bodies = article.select('.field--name-body')
    dates = article.select('.field--name-field-date')
    times = article.select('time')
    _need(len(bodies) == len(dates) == len(times) == 1, 'ambiguous_body_or_date')
    try:
        visible = datetime.strptime(dates[0].get_text(' ', strip=True), '%m/%d/%Y').date().isoformat()
    except ValueError:
        raise USCCInputHold('invalid_visible_date') from None
    _need(visible == date and times[0].get('datetime') == date + 'T12:00:00Z', 'source_date_mismatch')
    body = bodies[0]
    _need(not body.select('script,style,img,iframe,object,embed,video,audio,canvas'), 'unsupported_body_content')
    text = '\n'.join(body.stripped_strings) + '\n'  # exact preserved qualification algorithm
    _need(_sha(text.encode()) == spec['content_sha256'], 'text_version_mismatch')
    paragraphs = [p for p in body.select('p') if p.get_text(strip=True)]
    values = [p.get_text(' ', strip=True) for p in paragraphs]
    hashes = [_sha(t.encode()) for t in values]
    _need(hashes == spec['paragraph_text_sha256'], 'paragraph_boundaries_mismatch')
    included = spec['included']
    excluded = spec['excluded']
    _need(included == sorted(set(included)) and set(included).isdisjoint(map(int, excluded))
          and set(included) | set(map(int, excluded)) == set(range(len(values))), 'ambiguous_selection')
    _need(all(not paragraphs[i].find('a') and not any(q in values[i] for q in ('“', '”', '"'))
              for i in included), 'excluded_expression_in_input')
    titles = body.select('h2')
    _need(len(titles) == 1, 'ambiguous_title')
    potential = {'title': titles[0].get_text(' ', strip=True), 'canonical_url': url,
                 'publication_date': date, 'narrative': '\n\n'.join(values[i] for i in included)}
    manifest = {'schema': 'ipr-uscc-offline-potential-input/1', 'source_identity': identity,
                'evidence_commit': EVIDENCE_COMMIT, 'decision_reference': DECISION,
                'capture_sha256': spec['capture_sha256'], 'content_sha256': spec['content_sha256'],
                'canonical_url': url, 'publication_date': date,
                'included_paragraphs': [{'index': i, 'sha256': hashes[i]} for i in included],
                'excluded_paragraphs': [{'index': i, 'sha256': hashes[i], 'reason': excluded[str(i)]}
                                        for i in range(len(values)) if str(i) in excluded],
                'potential_input_sha256': _sha(json.dumps(potential, sort_keys=True, ensure_ascii=False,
                                                         separators=(',', ':')).encode()),
                'complete_original_input': False, 'model_transmission_authorized': False,
                'publication_authorized': False, 'potential_note_max_words': 90}
    return {'potential_input': potential, 'manifest': manifest}

def derive_input(raw, *, source_identity, canonical_url, publication_date):
    """Derive in memory from bytes already held privately; exact accepted versions only.

    Caller keeps input and return value private. No caller-supplied policy allowed.
    Full originals are neither changed nor rewritten. Unknown/changed versions hold.
    """
    policy = json.loads(_POLICY.read_text())
    _need(type(source_identity) is str and source_identity in policy, 'unsupported_publication')
    return _derive(raw, source_identity, canonical_url, publication_date, policy[source_identity])
