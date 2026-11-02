"""Read-only real-source reconciliation and approved-only Living Dossiers.

Only the deliberately small public projection leaves this module. Originals
are hashed in scratch SQLite custody, never returned to templates or indexes.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, timedelta
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
# Case studies are labelled in code, never by their own manuscript. The label
# appears only while a public thematic dossier actually declares the relation.
CASE_STUDY_LABELS = {'maritime-cooperation-2026': 'Exercise case study'}
KIND_LABELS = {'issuer_statement': 'Issuer statement',
               'documented_publication': 'Publication fact',
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


def claim_source_ids(claim):
    """Corpus record ids (int) and linked external ids ('x1', str) together."""
    return (claim['source_record_ids'] + claim['counterevidence_ids']
            + claim.get('external_source_ids', []) + claim.get('external_counterevidence_ids', []))


def affected_findings(sc, rid):
    return [c['id'] for section in sc['sections'] for c in section['claims']
            if rid in claim_source_ids(c)]


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
            body_hash = hashlib.sha256(body.encode('utf-8')).hexdigest() if body else None
            if not body and rec['source_id'] == 'sg_mindef_releases' and con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='mindef_private_record_bindings'").fetchone():
                binding = con.execute(
                    "SELECT b.original_body_sha256 FROM mindef_private_record_bindings b "
                    "JOIN articles a ON a.id=b.article_id "
                    "WHERE b.article_id=? AND b.original_content_hash=a.content_hash", (rid,)).fetchone()
                body_hash = binding[0] if binding else None
            if not body_hash or not rec['institution_name'] or not rec['source_name']:
                _fail('unavailable_evidence', rid, findings)
            if body_hash != source['stored_original_sha256']:
                _fail('version_mismatch', rid, findings)
            # The reference describes the observable screening disposition;
            # it is never accepted as a stand-alone admission credential.
            if source['editorial_admission_ref'] != 'archive:passed_relevance=1':
                _fail('editorial_admission_mismatch', rid, findings)
            records[rid] = dict(id=rid, url=rec['url'], published_on=rec['published_date'],
                desk=rec['desk'], source_name=rec['source_name'],
                institution_name=rec['institution_name'], language=rec['language'])
    return records


def reconcile_external_sources(sc, db_path):
    """Link-only official sources outside the corpus: identity checks only.

    Nothing is fetched or stored; IPR projects attribution, date, publisher link
    and its own paraphrase. The issuing institution must already be registered.
    """
    externals = sc.get('external_sources', [])
    if not externals:
        return {}
    with read_only(db_path) as con:
        names = dict(con.execute('SELECT institution_id, display_name FROM institutions').fetchall())
    result = {}
    for ext in externals:
        if not names.get(ext['institution_id']):
            _fail('unknown_external_institution', ext['id'], affected_findings(sc, ext['id']))
        result[ext['id']] = dict(id=ext['id'], url=ext['url'], published_on=ext['published_on'],
            publisher=ext['publisher'], institution_id=ext['institution_id'],
            institution_name=names[ext['institution_id']],
            language=ext['language'], retrieved_on=ext['retrieved_on'])
    return result


def derived_chronology(sc):
    """Without a bound Timeline, list dated non-interpretive findings by event date."""
    entries = []
    for section in sc['sections']:
        for claim in section['claims']:
            event = claim['event_period']
            if not event or claim['claim_kind'] == 'editorial_interpretation':
                continue
            evidence = [dict(record_id=rid, basis=event['basis'], published_on=None)
                        for rid in claim['source_record_ids'] + claim.get('external_source_ids', [])]
            entries.append(dict(id=claim['id'], headline=claim.get('heading', claim['id']),
                event=event, observation='', evidence=evidence, qualification=None,
                derived_from=claim['id']))
    return sorted(entries, key=lambda e: (e['event']['start'], e['event']['end'], e['id']))


def chronology_view(sc, records, timelines_dir=TIMELINES_DIR):
    """Reuse the canonical chronology as content, never its approval status."""
    binding = sc.get('chronology')
    if not binding:
        return derived_chronology(sc)
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
    for ext in sc.get('external_sources', []):
        grant = dossier_decisions.SOURCE_USES.get(ext['source_use_decision_ref'], {}).get(ext['id'])
        want = dict(source_binding(ext), public_fields=sorted(PUBLIC_FIELDS - {'record_link'}))
        if grant != want:
            holds.append(dict(code='source_use_hold', external_id=ext['id'],
                              findings=affected_findings(sc, ext['id'])))
    decision = dossier_decisions.PUBLICATIONS.get(sc['slug'])
    expected = dict(content_sha256=dossier_content_digest(sc), approval=sc.get('approval'))
    if sc['editorial_status'] != 'approved' or not decision or decision != expected:
        holds.append(dict(code='editorial_hold'))
    return holds


def reported_windows(sc, chronology):
    """One inclusive day axis, derived from the reconciled manuscript.

    The pilot's verified date assertions intentionally fail on drift. A changed
    source claim needs review before this comparison can be represented again.
    No independent editable interval copy is passed to the template.
    """
    if sc['slug'] != 'maritime-cooperation-2026':
        return None
    claims = {c['id']: c for s in sc['sections'] for c in s['claims']}
    entries = {e['id']: e for e in chronology}
    windows = []
    for cid, eid, label, expected, ids in (
        ('ministry-window', 'ministry-interval', 'China MND',
         ('2026-09-03', '2026-09-09'), {4164}),
        ('singapore-window', 'singapore-interval', 'Singapore MINDEF',
         ('2026-09-05', '2026-09-09'), {4466, 4472}),
    ):
        claim, entry = claims.get(cid), entries.get(eid)
        event = claim.get('event_period') if claim else None
        if (not event or not entry
                or tuple(event[k] for k in ('start', 'end')) != expected
                or tuple(entry['event'][k] for k in ('start', 'end')) != expected
                or set(claim['source_record_ids']) != ids
                or {e['record_id'] for e in entry['evidence']} != ids):
            _fail('reported_window_binding_mismatch', claims=[cid])
        windows.append(dict(label=label, claim_id=cid, start=event['start'],
                            end=event['end'], source_ids=claim['source_record_ids']))
    start = date.fromisoformat(min(w['start'] for w in windows))
    end = date.fromisoformat(max(w['end'] for w in windows))
    days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
    for window in windows:
        window['cells'] = [window['start'] <= day.isoformat() <= window['end'] for day in days]
    return dict(windows=windows, days=[dict(iso=d.isoformat(), day=d.day) for d in days])


def reading_view(sc, records, chronology, externals=None):
    """Derived reading metadata, never additional source text or authority."""
    externals = externals or {}
    sources = {s['record_id']: s for s in sc['sources']}
    disputed = {cid for d in sc['disagreements'] for cid in d['claim_ids']}
    labels = {'pla_daily': 'PLA Daily', 'mod_china': 'China MND',
              'sg_mindef_releases': 'MINDEF'}
    claims = {}
    ordinal = 0
    sections = []
    for section in sc['sections']:
        items = []
        for claim in section['claims']:
            ordinal += 1
            ids = set(claim_source_ids(claim))
            different = (claim['id'] in ('ministry-window', 'singapore-window')
                         or (not sc.get('chronology') and claim['id'] in disputed))
            item = dict(claim, ordinal='%02d' % ordinal, evidence_count=len(ids),
                        external_source_ids=claim.get('external_source_ids', []),
                        external_counterevidence_ids=claim.get('external_counterevidence_ids', []),
                        counter_label='Different account' if different else 'Qualification sources')
            claims[claim['id']] = item
            items.append(item)
        sections.append(dict(section, claims=items))
    ledger = []
    for rec in sorted(records.values(), key=lambda r: (r['published_on'], r['id'])):
        ledger.append(dict(rec, short_name=labels.get(sources[rec['id']]['source_id'], rec['source_name']),
            language_name={'zh-Hans': 'Chinese (Simplified)', 'en': 'English'}.get(rec['language'], rec['language']),
            findings=[c for c in claims.values() if rec['id'] in c['source_record_ids'] + c['counterevidence_ids']]))
    external_ledger = [dict(ext, short_name={'sg_mindef': 'MINDEF', 'cn_mnd': 'China MND'}.get(
            ext['institution_id'], ext['publisher']), external=True,
            language_name={'zh-Hans': 'Chinese (Simplified)', 'en': 'English'}.get(ext['language'], ext['language']),
            findings=[c for c in claims.values() if ext['id'] in
                      c['external_source_ids'] + c['external_counterevidence_ids']])
        for ext in sorted(externals.values(), key=lambda e: (e['published_on'], int(e['id'][1:])))]
    cited = {**{r['id']: r for r in ledger}, **{e['id']: e for e in external_ledger}}
    events = []
    for entry in chronology:
        if entry.get('derived_from'):
            evidence = [dict(ev, published_on=cited[ev['record_id']]['published_on'])
                        for ev in entry['evidence']]
            events.append(dict(entry, evidence=evidence, findings=[claims[entry['derived_from']]],
                               interval_claim=False))
            continue
        ids = {e['record_id'] for e in entry['evidence']}
        candidates = [c for c in claims.values() if c['event_period']
            and c['claim_kind'] != 'editorial_interpretation'
            and c['event_period']['start'] <= entry['event']['start']
            and c['event_period']['end'] >= entry['event']['end']
            and ids.issubset(c['source_record_ids'])]
        if candidates:
            shortest = min((date.fromisoformat(c['event_period']['end']) -
                            date.fromisoformat(c['event_period']['start'])).days for c in candidates)
            candidates = [c for c in candidates if (date.fromisoformat(c['event_period']['end']) -
                date.fromisoformat(c['event_period']['start'])).days == shortest]
        events.append(dict(entry, findings=candidates,
            interval_claim=entry['id'] in ('ministry-interval', 'singapore-interval')))
    return dict(sections=sections, findings=claims, ledger=ledger, external_ledger=external_ledger,
                records=cited, chronology_entries=events,
                jurisdictions=sorted({s['desk'].capitalize() for s in sources.values()}),
                publication_cutoff=max(r['published_on'] for r in cited.values()),
                comparison=reported_windows(sc, chronology))


def dossier_view(sc, records, related, chronology, holds, is_review=False, externals=None):
    result = dict(sc, route='dossier/%s.html' % sc['slug'], is_review=is_review,
                  digest=dossier_content_digest(sc), chronology_entries=chronology,
                  holds=holds, kind_labels=KIND_LABELS,
                  kind='thematic' if 'case_studies' in sc else 'dossier',
                  kind_label='Thematic dossier' if 'case_studies' in sc else 'Living Dossier',
                  case_study_views=[], parent_dossiers=[])
    result.update(reading_view(sc, records, chronology, externals))
    result['related'] = [related[slug] for slug in sc['related_briefs']]
    result['citation'] = '%s. “%s.” Indo-Pacific Record, %s, revision %s, %s%s.' % (
        sc['author_name'], sc['title'], result['kind_label'], sc['revision'], sc['updated_on'],
        ' (unapproved draft; private review)' if is_review else '')
    if not is_review:
        result['citation'] += ' https://indopacificrecord.org/' + result['route']
    return result


def load_dossiers(db_path, related, source_dir=DOSSIERS_DIR, review_path=None,
                  registry=None, timelines_dir=TIMELINES_DIR, related_timelines=None,
                  held_metadata=None):
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
        from core.mindef_public_boundary import editorial_hold
        if not selected and editorial_hold(sc):
            holds = publication_holds(sc)
            if holds:
                _fail('publication_validation_failed: ' + '; '.join(h['code'] for h in holds))
            withheld.append(sc['slug'])
            if held_metadata is not None:
                # Relationship metadata of an approved but held work, from the
                # sidecar already read here. No route, prose or source text.
                held_metadata[sc['slug']] = dict(
                    slug=sc['slug'], title=sc['title'], chronology=sc.get('chronology') or {},
                    related_timelines=list(sc['related_timelines']),
                    case_studies=list(sc.get('case_studies', [])))
            continue
        for slug in sc['related_briefs']:
            if slug not in related or related[slug].get('is_review'):
                _fail('related_brief_not_approved')
        for slug in sc['related_timelines']:
            item = (related_timelines or {}).get(slug)
            if not item or item.get('is_review') or item['editorial_status'] != 'approved':
                _fail('related_timeline_not_approved')
        records = reconcile_dossier_sources(sc, db_path, registry)
        externals = reconcile_external_sources(sc, db_path)
        chronology = chronology_view(sc, records, timelines_dir)
        holds = publication_holds(sc)
        if not selected and holds:
            _fail('publication_validation_failed: ' + '; '.join(
                h['code'] + (' record %s' % h['record_id'] if 'record_id' in h else '')
                + (' external %s' % h['external_id'] if 'external_id' in h else '') for h in holds))
        view = dossier_view(sc, records, related, chronology, holds, selected, externals)
        timeline = (related_timelines or {}).get(sc.get('chronology', {}).get('timeline_slug'))
        view['public_chronology'] = timeline if timeline and not timeline.get('is_review') else None
        views.append(view)
    if review is not None and not found:
        _fail('review_source_not_found')
    link_case_studies(views)
    return sorted(views, key=lambda d: (d['updated_on'], d['slug']), reverse=True), withheld


def link_case_studies(views):
    """Bind thematic → case-study pairs among the views actually being rendered."""
    by_slug = {v['slug']: v for v in views}
    for view in views:
        for slug in view.get('case_studies', []):
            case = by_slug.get(slug)
            if case is None or slug not in CASE_STUDY_LABELS:
                _fail('case_study_not_published', field=slug)
            view['case_study_views'].append(case)
            case['parent_dossiers'].append(view)
            case['kind'], case['kind_label'] = 'case_study', CASE_STUDY_LABELS[slug]


def timeline_dossier_links(timeline_slug, views, held=None):
    """Public and unavailable Dossier destinations for one Timeline.

    Pure selection over already-loaded public views and held-work metadata.
    A Dossier relates through its chronology binding or `related_timelines`;
    a thematic parent relates through its `case_studies`. Review views are
    excluded. Only small dicts are returned, so no view cycle is created.
    """
    def bound(item):
        return (item.get('chronology') or {}).get('timeline_slug') == timeline_slug or \
            timeline_slug in (item.get('related_timelines') or ())

    public = [v for v in views if not v.get('is_review')]
    held = [m for slug, m in sorted((held or {}).items())
            if slug not in {v['slug'] for v in public}]
    cases = {i['slug'] for i in public + held if bound(i)}

    referenced = {c for i in public + held for c in (i.get('case_studies') or ())}

    def is_parent(item):
        return item['slug'] not in cases and bool(cases & set(item.get('case_studies') or ()))

    def label(item, parent):
        if parent:
            return 'Thematic dossier'
        return CASE_STUDY_LABELS.get(item['slug'], 'Living Dossier') if item['slug'] in referenced \
            else 'Living Dossier'

    links, unavailable = [], []
    for parent in (False, True):
        for item in public:
            if (is_parent(item) if parent else bound(item)):
                links.append(dict(title=item['title'], route=item['route'],
                                  kind_label=label(item, parent)))
        for item in held:
            if (is_parent(item) if parent else bound(item)):
                unavailable.append(dict(title=item['title'], kind_label=label(item, parent)))
    return links, unavailable


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
