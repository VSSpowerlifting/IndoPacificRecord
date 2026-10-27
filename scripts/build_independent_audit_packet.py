#!/usr/bin/env python3
"""Build or verify a private, unsigned audit packet from committed evidence only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.reconcile_db import read_only

SEED = 'ipr-independent-audit-2026-10-27-v1'
ORIGIN = 'https://indopacificrecord.org'
METHOD = 'docs/INDEPENDENT_QUALITY_AUDIT.md'
NOTES = 'research/china/original-source-review-2026-10-15.json'
CHECKS = {
    'extraction': 'Completeness, contamination, paragraph ordering; compare raw publisher capture if available.',
    'attribution_dates': 'Distinguish issuer, publisher/republication, posting, issue, event and collection dates.',
    'translation': 'Check machine labeling, omissions and limitations using appropriate language expertise.',
    'explanation_support': 'Trace every substantive explanation to cited evidence; distinguish official claims from facts.',
    'citation_identity': 'Compare source identity, citation, publisher URL and canonical IPR link.',
}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def blob(revision, path):
    return git('show', revision + ':' + path)


def rank(seed, row):
    return sha((seed + '\0' + row['identity'] + '\0' + row['version_sha256']).encode())


def select(rows, count, seed):
    """One per family/quarter, then highest N/(allocated+1); exact rational ties."""
    groups = defaultdict(list)
    for row in rows:
        groups[row['stratum']].append(row)
    if not groups or len(groups) > count or len(rows) < count:
        raise ValueError('frame cannot supply requested sample with every stratum represented')
    allocation = {key: 1 for key in groups}
    while sum(allocation.values()) < count:
        candidates = [k for k in sorted(groups) if allocation[k] < len(groups[k])]
        key = max(candidates, key=lambda k: Fraction(len(groups[k]), allocation[k] + 1))
        allocation[key] += 1
    return [r for k in sorted(groups) for r in sorted(groups[k], key=lambda r: (rank(seed, r), r['identity']))[:allocation[k]]]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonicals, self.links = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'link' and 'canonical' in a.get('rel', '').split():
            self.canonicals.append(a.get('href'))
        if tag == 'a':
            self.links.append(a.get('href'))


def page_facts(raw):
    parser = Links()
    parser.feed(raw.decode('utf-8'))
    return parser


def pending_reviews(items):
    return {r['identity']: {k: {'outcome': 'pending', 'reviewer': None,
            'review_date': None, 'evidence_note': None} for k in CHECKS} for r in items}


def validate_reviews(reviews, identities):
    if set(reviews) != set(identities):
        raise ValueError('review identity set changed')
    for checks in reviews.values():
        if set(checks) != set(CHECKS):
            raise ValueError('review check set changed')
        for verdict in checks.values():
            if set(verdict) != {'outcome', 'reviewer', 'review_date', 'evidence_note'}:
                raise ValueError('invalid verdict fields')
            if verdict['outcome'] == 'pending':
                if any(verdict[k] is not None for k in ('reviewer', 'review_date', 'evidence_note')):
                    raise ValueError('pending verdict must remain unsigned')
            elif verdict['outcome'] in ('pass', 'issue', 'not-assessable'):
                if not all(isinstance(verdict[k], str) and verdict[k].strip() for k in ('reviewer', 'review_date', 'evidence_note')):
                    raise ValueError('human verdict requires reviewer, actual date and evidence note')
                day = date.fromisoformat(verdict['review_date'])
                if day.isoformat() != verdict['review_date'] or day > date.today():
                    raise ValueError('invalid actual review date')
            else:
                raise ValueError('unknown review outcome')


def load_frame(db, paths):
    db.row_factory = sqlite3.Row
    rows, excluded = [], []
    for row in db.execute('SELECT a.*,s.slug,s.display_name,s.desk_id,s.language_tag,s.institution_id,i.display_name AS institution_name FROM articles a JOIN sources s ON s.id=a.source_id LEFT JOIN institutions i ON i.institution_id=s.institution_id ORDER BY a.id'):
        r = dict(row)
        reason = None
        try:
            day = date.fromisoformat(r['published_date'])
        except (TypeError, ValueError):
            reason = 'missing_or_invalid_publication_date'
        if not (r['text_original'] or '').strip():
            reason = 'no_preserved_body'
        elif 'output/record/%s.html' % r['id'] not in paths:
            reason = 'no_committed_record_page'
        if reason:
            excluded.append({'identity': 'article:%s' % r['id'], 'reason': reason})
            continue
        if not r['url']:
            raise ValueError('preserved record missing publisher identity')
        rows.append({'identity': 'article:%s' % r['id'], 'source_family': r['slug'],
                     'stratum': r['slug'] + '/' + '%s-Q%s' % (day.year, (day.month - 1) // 3 + 1),
                     'version_sha256': sha(encoded(r)), 'row': r})
    return rows, excluded


def provenance(db, url, identity, article_id=None):
    """Retain stored receipts, without fetching private companion repositories."""
    result = {}
    identities = {identity}
    tables = ('regional_official_source_links', 'daily_machine_records',
              'korea_corpus_admissions', 'vietnam_article_provenance', 'official_document_versions',
              'uscc_official_source_records', 'treasury_official_source_records',
              'bis_authenticated_official_source_records', 'korea_official_source_records')
    for table in tables:
        columns = {r[1] for r in db.execute('PRAGMA table_info(' + table + ')')}
        keys = columns & {'url', 'source_url', 'canonical_official_url', 'source_identity', 'article_id'}
        matches = []
        for row in db.execute('SELECT * FROM ' + table) if columns else []:
            r = dict(row)
            if any((r[k] == url if 'url' in k else r[k] in identities if k == 'source_identity' else article_id is not None and r[k] == article_id) for k in keys):
                matches.append(r)
                if r.get('source_identity'):
                    identities.add(r['source_identity'])
        if matches:
            result[table] = sorted(matches, key=lambda r: encoded(r))
    return result


def supplement(index, sampled_desks, seed):
    groups = defaultdict(list)
    for r in index['records']:
        if r['record_type'] not in ('official_link', 'machine_explanation') or set(r['desks']) & sampled_desks:
            continue
        item = {'identity': r['id'], 'version_sha256': sha(encoded(r)), 'row': r}
        groups['/'.join(r['desks'])].append(item)
    # Prefer a machine explanation within a desk; otherwise seed-ranked metadata.
    return [min(groups[k], key=lambda r: (r['row']['record_type'] != 'machine_explanation', rank(seed, r))) for k in sorted(groups)][:4]


def worksheet(manifest):
    lines = ['# Independent quality audit — unsigned worksheet', '',
             'No human audit has occurred. Work offline from the frozen evidence. Record verdicts in `reviews.json`; keep a working copy of this worksheet for prose notes.', '',
             'Outcomes: pending / pass / issue / not-assessable. Every non-pending verdict needs your real name, actual review date and a specific evidence note (file, paragraph/page and comparison). Missing evidence or language expertise requires a visible limitation; do not infer a pass.', '',
             'Reviewer: ______   Independence from original author: ______   Language expertise: ______', '',
             'Read `methodology.md` before reviewing. Keep private evidence local. This packet grants no new source use. A final public report needs separately reviewed redaction and editorial approval.', '']
    for section in ('sample', 'supplement'):
        lines += ['## ' + section.title(), '']
        for r in manifest[section]:
            lines += ['### ' + r['identity'], '',
                      '- Publisher: ' + str(r['publisher_url']),
                      '- IPR canonical surface: ' + str(r['canonical_ipr_url']),
                      '- Source / stored institutional attribution: ' + str(r['source']) + ' / ' + str(r['issuer']),
                      '- Dates and meanings: ' + json.dumps(r['dates'], ensure_ascii=False),
                      '- Processing: ' + str(r['processing_state']),
                      '- Evidence: [' + r['evidence_file'] + '](' + r['evidence_file'] + '); [' + r['page_file'] + '](' + r['page_file'] + ')',
                      '- Limits: ' + '; '.join(r['limitations']), '',
                      '| Check | Outcome | Reviewer | Actual date | Evidence note |',
                      '|---|---|---|---|---|']
            lines += ['| ' + k + ' | pending | | | |' for k in CHECKS]
            lines += ['', 'Language expertise / unavailable evidence / editorial correction candidate: ______', '']
    lines += ['## Check instructions', ''] + ['- **' + k + '**: ' + v for k, v in CHECKS.items()]
    lines += ['', 'Known problem candidates are in `known-problems.json`, outside the selected denominator. Do not treat prior assistant observations as independent human findings.', '',
              '## Eventual report', '', 'Record reviewer identity/independence, actual dates, language expertise, snapshot/seed, completed and not-assessable counts per check and stratum, evidence-supported findings and limitations. Keep supplement and known-case findings separate. Report no accuracy percentage over unassessable records or this deliberately disproportionate sample without appropriate stratified weighting. Public excerpts and private evidence need separate source-use review.', '']
    return '\n'.join(lines).encode()


def build(revision, seed, destination):
    revision = git('rev-parse', '--verify', revision + '^{commit}').decode().strip()
    paths = set(git('ls-tree', '-r', '--name-only', revision, 'output/record').decode().splitlines())
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = {}

    def write(name, raw):
        p = destination / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        p.chmod(0o600)
        files[name] = sha(raw)

    raw_db = blob(revision, 'pla_watch.db')
    write('snapshot/pla_watch.db', raw_db)
    index_raw = blob(revision, 'output/archive-research-index.json')
    write('snapshot/archive-research-index.json', index_raw)
    with read_only(destination / 'snapshot/pla_watch.db') as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('committed database integrity failure')
        rows, excluded = load_frame(db, paths)
        selected = select(rows, 20, seed)
        extras = supplement(json.loads(index_raw), {r['row']['desk_id'] for r in selected}, seed)
        manifest = {'schema': 'ipr-independent-audit/1', 'repository_revision': revision,
                    'database_git_blob': git('rev-parse', revision + ':pla_watch.db').decode().strip(),
                    'database_sha256': sha(raw_db), 'seed': seed,
                    'human_audit_completed': False, 'checks': CHECKS,
                    'eligible_population': len(rows), 'excluded': excluded,
                    'composition': [{'stratum': k, 'eligible': n, 'sampled': Counter(r['stratum'] for r in selected)[k]} for k, n in sorted(Counter(r['stratum'] for r in rows).items())],
                    'eligible_roster': [{k: v for k, v in r.items() if k != 'row'} for r in rows],
                    'sample': [], 'supplement': []}
        for section, items in (('sample', selected), ('supplement', extras)):
            for number, item in enumerate(items, 1):
                r = item['row']
                is_sample = section == 'sample'
                url = r['url'] if is_sample else r['source_url']
                refs = provenance(db, url, r.get('source_identity') or r.get('id', ''), r['id'] if is_sample else None)
                ipr = ORIGIN + '/record/%s.html' % r['id'] if is_sample else r['ipr_url'] or ORIGIN + '/' + r['desks'][0] + '.html'
                route = 'output' + urlsplit(ipr).path
                raw_page = blob(revision, route)
                parsed = page_facts(raw_page)
                stem = '%s/%02d' % (section, number)
                write(stem + '.json', encoded({'record': r, 'stored_provenance': refs}))
                write(stem + '.html', raw_page)
                limitations = ['Raw publisher HTML/PDF not included; extracted body is not proof of extraction completeness.', 'Language expertise has not been recorded.'] if is_sample else ['Preserved original unavailable in this packet; no extraction-accuracy denominator.', 'Verify only permitted metadata, labeling and citation identity; explanation support is not assessable without authorized original evidence.']
                if is_sample and not r['language_tag'].startswith('en'):
                    limitations.append('Translation accuracy requires an independent reviewer competent in ' + r['language_tag'] + '.')
                if is_sample and not r['text_english']:
                    limitations.append('No stored full English translation; assess its disclosure, not an absent translation.')
                manifest[section].append({'identity': item['identity'], 'version_sha256': item['version_sha256'],
                    'record_type': 'preserved_extracted_body' if is_sample else r['record_type'],
                    'source': r['display_name'] if is_sample else r['source'],
                    'source_family': r['slug'] if is_sample else next(iter(refs.get('regional_official_source_links', [{}])), {}).get('source_family'),
                    'issuer': r['institution_name'] if is_sample else r['issuer'],
                    'attribution_role': 'stored source institution; document issuer requires review' if is_sample else 'published index attribution; verify issuer versus host',
                    'language': r.get('language_tag'), 'publisher_url': url, 'canonical_ipr_url': ipr,
                    'ipr_url_role': 'record permalink' if is_sample or r['ipr_url'] else 'desk surface; no individual IPR permalink',
                    'dates': {'publication': r['published_date'] if is_sample else r['date'],
                              'publication_meaning': ('publisher posting date' if r['slug'] == 'kr_policy_mnd_releases' else 'stored source-stated publication; not an event or collection date') if is_sample else r['date_kind'],
                              'collected_at': r.get('scraped_at'), 'machine_analyzed_at': r.get('analyzed_at'),
                              'clock_limits': 'Stored clock/timezone semantics are not inferred; see receipts.'},
                    'processing_state': {'stored': r.get('processing_state'), 'passed_relevance': r.get('passed_relevance'), 'analyzed_at': r.get('analyzed_at'), 'model': r.get('model_id'), 'prompt': r.get('prompt_version')} if is_sample else r['processing'],
                    'original_body_sha256': sha(r['text_original'].encode()) if is_sample else None,
                    'stored_content_hash': r.get('content_hash'),
                    'provenance_sha256': sha(encoded(refs)), 'available_version_receipts': refs,
                    'evidence_file': stem + '.json', 'page_file': stem + '.html',
                    'automated_observations_not_verdicts': {'canonical_links': parsed.canonicals, 'expected_publisher_link_present': url in parsed.links},
                    'limitations': limitations})
    known = json.loads(blob(revision, NOTES))
    known_cases = [{k: r[k] for k in ('id', 'source', 'comparison', 'next_step')} for r in known['checks'] if r['comparison'] in ('historical_text_contamination', 'historical_body_absent')]
    for r in known_cases:
        r['also_selected'] = 'article:%s' % r['id'] in {x['identity'] for x in selected}
    write('known-problems.json', encoded({'origin': NOTES, 'origin_sha256': sha(blob(revision, NOTES)), 'status': 'prior_assistant_candidates_not_human_verdicts', 'additional_denominator': 0, 'cases': known_cases}))
    write('methodology.md', blob(revision, METHOD))
    write('worksheet.md', worksheet(manifest))
    (destination / 'reviews.json').write_bytes(encoded(pending_reviews(manifest['sample'] + manifest['supplement'])))
    (destination / 'reviews.json').chmod(0o600)
    manifest['files_sha256'] = files
    (destination / 'manifest.json').write_bytes(encoded(manifest))
    (destination / 'manifest.json').chmod(0o600)
    return manifest


def verify(packet):
    manifest = json.loads((packet / 'manifest.json').read_bytes())
    with tempfile.TemporaryDirectory(prefix='ipr-audit-verify-') as tmp:
        expected = build(manifest['repository_revision'], manifest['seed'], Path(tmp) / 'packet')
        if expected != manifest:
            raise ValueError('manifest differs from committed snapshot or selection')
    for name, expected_hash in manifest['files_sha256'].items():
        if sha((packet / name).read_bytes()) != expected_hash:
            raise ValueError('packet evidence changed: ' + name)
    validate_reviews(json.loads((packet / 'reviews.json').read_bytes()),
                     [r['identity'] for r in manifest['sample'] + manifest['supplement']])
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--seed', default=SEED)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--out', type=Path)
    group.add_argument('--verify', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.verify:
            manifest = verify(args.verify.resolve())
        else:
            out = args.out.expanduser().resolve()
            if out == ROOT.resolve() or ROOT.resolve() in out.parents:
                raise ValueError('working packets must stay outside the repository')
            manifest = build(args.revision, args.seed, out)
        print(json.dumps({'revision': manifest['repository_revision'], 'eligible': manifest['eligible_population'], 'sample': len(manifest['sample']), 'supplement': len(manifest['supplement']), 'human_audit_completed': False}))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, 'Audit packet held: %s\n' % exc)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
