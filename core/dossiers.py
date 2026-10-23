"""Read-only real-source reconciliation and approved-only Living Dossiers.

Only the deliberately small public projection leaves this module. Originals
are hashed in scratch SQLite custody, never returned to templates or indexes.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from core.dossier_contract import (
    DOSSIERS_DIR, ROOT, DossierValidationError, dossier_content_digest,
    read_dossier, validate_dossier_shape,
)
from core import dossier_decisions
from core.desk_registry import load_registry
from core.retired_article_urls import url_sha256
from core.timelines import TIMELINES_DIR, read_timeline, content_digest
from scripts.reconcile_db import read_only

# Intentionally no publisher original titles, bodies, quotations or model text.
PUBLIC_FIELDS = frozenset({'attribution', 'publication_date', 'publisher_link',
                           'record_link', 'ipr_paraphrase'})
KIND_LABELS = {'issuer_statement': 'Issuer statement',
               'documented_publication': 'Documented publication',
               'editorial_interpretation': 'Editorial interpretation'}


def _fail(code, rid=None, claims=(), field=None):
    message = code
    if rid is not None:
        message += ' · record %s' % rid
    if field:
        message += ' · ' + field
    if claims:
        message += ' · affected findings: ' + ', '.join(sorted(claims))
    raise DossierValidationError(message)


def affected_findings(sc, rid):
    return [c['id'] for section in sc['sections'] for c in section['claims']
            if rid in c['source_record_ids'] + c['counterevidence_ids']]


def source_binding(source):
    """Identity pin for a separately recorded source-use decision."""
    return {k: v for k, v in source.items() if k != 'source_use_decision_ref'}


def reconcile_dossier_sources(sc, db_path, registry=None):
    validate_dossier_shape(sc)
    registry = load_registry() if registry is None else registry
    declared = {(d.slug, s.slug): s for d in registry
                if d.public and d.is_collecting and d.has_production_records
                for s in d.sources if s.enabled and s.contract_validated}
    ids = [s['record_id'] for s in sc['sources']]
    records = {}
    with read_only(db_path) as con:
        con.row_factory = sqlite3.Row
        retired = con.execute('SELECT original_article_id, url_sha256 FROM retired_article_urls').fetchall()
        retired_ids = {r[0] for r in retired}
        retired_urls = {r[1] for r in retired}
        from core.korea_corpus_bridge import publication_gate
        hidden = publication_gate(con)[1]
        rows = con.execute(
            'SELECT a.id, a.url, a.published_date, a.text_original, a.passed_relevance, '
            's.slug AS source_id, s.desk_id AS desk, s.institution_id, '
            's.language_tag AS language, s.enabled, s.display_name AS source_name, '
            'i.display_name AS institution_name FROM articles a '
            'JOIN sources s ON s.id=a.source_id LEFT JOIN institutions i '
            'ON i.institution_id=s.institution_id WHERE a.id IN (%s)' %
            ','.join('?' for _ in ids), ids).fetchall()
        current = {r['id']: r for r in rows}
        for source in sc['sources']:
            rid = source['record_id']
            findings = affected_findings(sc, rid)
            rec = current.get(rid)
            if rid in retired_ids or (rec and url_sha256(rec['url']) in retired_urls):
                _fail('ineligible_source_retired', rid, findings)
            if rec is None:
                _fail('unavailable_evidence', rid, findings)
            policy = declared.get((rec['desk'], rec['source_id']))
            if (not policy or not rec['enabled'] or rid in hidden
                    or rec['passed_relevance'] != 1):
                _fail('ineligible_source', rid, findings)
            if (policy.institution_id != rec['institution_id']
                    or policy.language_tag != rec['language']):
                _fail('identity_mismatch_registry', rid, findings)
            for key, stored in (('desk', 'desk'), ('source_id', 'source_id'),
                                ('institution_id', 'institution_id'), ('language', 'language'),
                                ('published_on', 'published_date'), ('url', 'url')):
                if source[key] != rec[stored]:
                    _fail('identity_mismatch', rid, findings, key)
            body = rec['text_original']
            if not body or not rec['institution_name'] or not rec['source_name']:
                _fail('unavailable_evidence', rid, findings)
            if hashlib.sha256(body.encode('utf-8')).hexdigest() != source['stored_original_sha256']:
                _fail('version_mismatch', rid, findings)
            # The reference describes the observable screening disposition;
            # it is never accepted as a stand-alone admission credential.
            if source['editorial_admission_ref'] != 'archive:passed_relevance=1':
                _fail('editorial_admission_mismatch', rid, findings)
            records[rid] = dict(id=rid, url=rec['url'], published_on=rec['published_date'],
                desk=rec['desk'], source_name=rec['source_name'],
                institution_name=rec['institution_name'], language=rec['language'])
    return records


def chronology_view(sc, records, timelines_dir=TIMELINES_DIR):
    """Reuse the canonical chronology as content, never its approval status."""
    binding = sc.get('chronology')
    if not binding:
        return []
    timeline = read_timeline(Path(timelines_dir) / (binding['timeline_slug'] + '.json'), timelines_dir)
    if content_digest(timeline) != binding['content_sha256']:
        _fail('chronology_version_mismatch', claims=[c['id'] for s in sc['sections'] for c in s['claims']])
    sources = {s['record_id']: s for s in sc['sources']}
    entries = []
    for entry in timeline['entries']:
        if (entry['event']['start'] < sc['scope']['period_start']
                or entry['event']['end'] > sc['scope']['period_end']):
            _fail('chronology_outside_scope')
        evidence = []
        for ev in entry['evidence']:
            source = sources.get(ev['record_id'])
            if source is None or ev['record_id'] not in records:
                _fail('chronology_dangling_source', ev['record_id'])
            for key in ('desk', 'source_id', 'institution_id', 'published_on', 'url'):
                if ev[key] != source[key]:
                    _fail('chronology_identity_mismatch', ev['record_id'], field=key)
            evidence.append(dict(record_id=ev['record_id'], basis=ev['basis'],
                                 published_on=ev['published_on']))
        entries.append(dict(id=entry['id'], headline=entry['headline'], event=entry['event'],
            observation=entry['observation'], evidence=evidence,
            qualification=entry.get('disagreement_note')))
    return entries


def publication_holds(sc):
    """Actual external decisions, independent of manuscript assertions."""
    holds = []
    for source in sc['sources']:
        rid = source['record_id']
        grant = dossier_decisions.SOURCE_USES.get(source['source_use_decision_ref'], {}).get(rid)
        want = dict(source_binding(source), public_fields=sorted(PUBLIC_FIELDS))
        if grant != want:
            holds.append(dict(code='source_use_hold', record_id=rid,
                              findings=affected_findings(sc, rid)))
    decision = dossier_decisions.PUBLICATIONS.get(sc['slug'])
    expected = dict(content_sha256=dossier_content_digest(sc), approval=sc.get('approval'))
    if sc['editorial_status'] != 'approved' or not decision or decision != expected:
        holds.append(dict(code='editorial_hold'))
    return holds


def dossier_view(sc, records, related, chronology, holds, is_review=False):
    result = dict(sc, route='dossier/%s.html' % sc['slug'], is_review=is_review,
                  digest=dossier_content_digest(sc), chronology_entries=chronology,
                  holds=holds, kind_labels=KIND_LABELS)
    result['ledger'] = sorted(records.values(), key=lambda r: (r['published_on'], r['id']))
    result['related'] = [related[slug] for slug in sc['related_briefs']]
    result['citation'] = '%s. “%s.” Indo-Pacific Record, Living Dossier, revision %s, %s%s.' % (
        sc['author_name'], sc['title'], sc['revision'], sc['updated_on'],
        ' (unapproved draft; private review)' if is_review else '')
    if not is_review:
        result['citation'] += ' https://indopacificrecord.org/' + result['route']
    return result


def load_dossiers(db_path, related, source_dir=DOSSIERS_DIR, review_path=None,
                  registry=None, timelines_dir=TIMELINES_DIR, related_timelines=None):
    root = Path(source_dir)
    if root.is_symlink():
        _fail('dossier_directory_symlink')
    review = Path(review_path) if review_path else None
    if review and (review.is_symlink() or review.parent.is_symlink()
                   or review.parent.resolve() not in (root.resolve(), (root / 'drafts').resolve())):
        _fail('review_requires_canonical_dossier')
    views, withheld, found = [], [], False
    paths = sorted(root.glob('*.json'))
    if review and review.parent.resolve() == (root / 'drafts').resolve():
        # A revision overrides the same route ONLY in the private tree.
        paths = [p for p in paths if p.stem != review.stem] + [review]
    for path in paths:
        sc = read_dossier(path, path.parent)
        selected = review is not None and review.resolve() == path.resolve()
        if selected:
            found = True
            if sc['editorial_status'] != 'draft':
                _fail('review_requires_draft')
        if sc['editorial_status'] == 'draft' and not selected:
            # A new draft revision must never silently remove an approved page.
            if sc['slug'] in dossier_decisions.PUBLICATIONS:
                _fail('unapproved_revision_would_replace_publication')
            withheld.append(sc['slug'])
            continue
        for slug in sc['related_briefs']:
            if slug not in related or related[slug].get('is_review'):
                _fail('related_brief_not_approved')
        for slug in sc['related_timelines']:
            item = (related_timelines or {}).get(slug)
            if not item or item.get('is_review') or item['editorial_status'] != 'approved':
                _fail('related_timeline_not_approved')
        records = reconcile_dossier_sources(sc, db_path, registry)
        chronology = chronology_view(sc, records, timelines_dir)
        holds = publication_holds(sc)
        if not selected and holds:
            _fail('publication_validation_failed: ' + '; '.join(
                h['code'] + (' record %s' % h['record_id'] if 'record_id' in h else '') for h in holds))
        view = dossier_view(sc, records, related, chronology, holds, selected)
        timeline = (related_timelines or {}).get(sc.get('chronology', {}).get('timeline_slug'))
        view['public_chronology'] = timeline if timeline and not timeline.get('is_review') else None
        views.append(view)
    if review is not None and not found:
        _fail('review_source_not_found')
    return sorted(views, key=lambda d: (d['updated_on'], d['slug']), reverse=True), withheld


def validate_review_destination(destination, repo_root=ROOT):
    """New disposable absolute external path, no symlink components/overwrites."""
    path = Path(destination).expanduser()
    target = path.resolve()
    root = Path(repo_root).resolve()
    # /tmp is a platform alias on macOS; allow that OS-owned alias only.
    symlinks = [p for p in (path, *path.parents) if p.is_symlink()
                and str(p) not in ('/tmp', '/var')]
    if (not path.is_absolute() or path.exists() or symlinks
            or target == root or root in target.parents or target in root.parents
            or any((p / '.git').exists() for p in target.parents)
            or target == (ROOT / 'output').resolve()):
        _fail('private_review_requires_new_external_destination_without_symlinks')
    return target
