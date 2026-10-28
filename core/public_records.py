"""One reader-facing public record per admitted source publication.

A read-only post-pass over the Archive research index (``build_index``). It
adds no loader, query or field: each component stays the exact projection
row its own adapter produced and validated. It only decides which already
public components belong to one source publication, so that the Desks
directory, desk pages and Archive search count and present them the same way.

Grouping uses exact identities only:

* components whose ids share a source identity after the type prefix
  (``official:``, ``original:``, ``reviewed_translation:``,
  ``reviewed_analysis:``, ``machine:``), optionally through an explicit alias
  that a caller has verified by exact official URL;
* a corpus ``record:N`` joins a group only through an explicit binding whose
  stored corpus URL equals the group's official URL.

Every component of a group must name the same official URL. A mismatch is
reported and the components stay separate. Two groups that happen to share a
URL are reported, never merged. Titles and subjects are never compared.
Briefs and dossiers are analysis about records, not source records, so they
are not counted.
"""
from __future__ import annotations

from collections import Counter, defaultdict

SCHEMA = 'ipr-public-records/1'
NOT_SOURCE_RECORDS = frozenset({'human_analysis', 'living_dossier'})
# The component a reader opens first. Earlier wins.
LEAD_ORDER = ('archive_record', 'preserved_original', 'official_link',
              'reviewed_translation', 'reviewed_analysis', 'machine_explanation')
COMPONENT_LABELS = {
    'archive_record': 'IPR record',
    'preserved_original': 'Original text',
    'official_link': 'Official source',
    'reviewed_translation': 'Editor-reviewed translation',
    'reviewed_analysis': 'Editor-reviewed analysis',
    'machine_explanation': 'Machine explanation',
}
# A desk card names what kind of date its latest record carries, briefly.
DATE_KIND_LABELS = {
    'source-stated publication': 'publication date',
    'publisher-posted date': 'publisher posting date',
    'document issue date': 'document issue date',
    'RSS pubDate (not independently verified document issue date)': 'RSS listing date, not verified issue date',
}


def identity(record_id):
    kind, _, ident = record_id.partition(':')
    return kind, ident


def group(records, *, aliases=None, bindings=None, corpus_urls=None):
    """Group the index's public records into source publications.

    ``aliases`` maps a component source identity to another identity of the
    same publication; ``bindings`` maps a corpus record id (int) to a source
    identity; ``corpus_urls`` gives each bound corpus record's stored URL.
    Callers pass only pairs they have verified; this function re-verifies
    every pair against the official URL and reports, never forces, a mismatch.
    """
    aliases, bindings, corpus_urls = aliases or {}, bindings or {}, corpus_urls or {}
    unresolved = []
    buckets = defaultdict(list)
    for r in records:
        if r['record_type'] in NOT_SOURCE_RECORDS:
            continue
        kind, ident = identity(r['id'])
        if kind == 'record':
            bound = bindings.get(int(ident))
            key = ('id', aliases.get(bound, bound)) if bound else ('record', ident)
        else:
            key = ('id', aliases.get(ident, ident))
        buckets[key].append(r)

    groups = []
    for key, parts in buckets.items():
        urls = {r['source_url'] for r in parts if r['source_url']}
        for r in parts:
            if r['record_type'] == 'archive_record':
                urls.add(corpus_urls.get(int(identity(r['id'])[1])))
        lead_types = Counter(r['record_type'] for r in parts)
        if len(parts) > 1 and (len(urls) != 1 or None in urls or
                               any(n > 1 for n in lead_types.values())):
            unresolved.append({'identity': key[1], 'components': sorted(r['id'] for r in parts),
                               'reason': 'official URL mismatch' if len(urls) != 1 or None in urls
                               else 'two components of one type'})
            groups.extend([r] for r in parts)
        else:
            groups.append(parts)

    result = []
    for parts in groups:
        parts = sorted(parts, key=lambda r: (LEAD_ORDER.index(r['record_type']), r['id']))
        result.append(parts)
    result.sort(key=lambda parts: parts[0]['id'])
    return result, sorted(unresolved, key=lambda u: u['identity'])


def project(records, desk_slugs, **binding):
    """Counts, latest dates and component links for every public surface."""
    groups, unresolved = group(records, **binding)
    counts = {slug: 0 for slug in desk_slugs}
    sources = defaultdict(Counter)
    latest = {}
    lead_of, parts_of = {}, {}
    by_url = defaultdict(list)
    for parts in groups:
        lead = parts[0]
        for desk in lead['desks']:
            counts[desk] = counts.get(desk, 0) + 1
            sources[desk][lead['source']] += 1
            # Latest uses the lead's own stated date and keeps its kind, so an
            # RSS listing or IPR publication date never reads as an issue date.
            if lead['date'] and (desk not in latest or lead['date'] > latest[desk][0]):
                latest[desk] = (lead['date'], lead['date_kind'])
        url = lead['source_url'] or next((p['source_url'] for p in parts if p['source_url']), None)
        if url:
            by_url[url].append(lead['id'])
        if len(parts) > 1:
            parts_of[lead['id']] = [[COMPONENT_LABELS[p['record_type']], p['ipr_url'] or p['source_url']]
                                    for p in parts[1:]]
            for p in parts[1:]:
                lead_of[p['id']] = lead['id']
    return {
        'schema': SCHEMA,
        'desks': {slug: {'records': counts[slug],
                         'latest': latest.get(slug, (None, None))[0],
                         'latest_kind': latest.get(slug, (None, None))[1],
                         'latest_label': DATE_KIND_LABELS.get(latest.get(slug, (None, None))[1],
                                                              latest.get(slug, (None, None))[1]),
                         # Per source label as the adapter wrote it; labels are never merged.
                         'sources': dict(sorted(sources[slug].items()))}
                  for slug in sorted(counts)},
        'total': len(groups),
        'lead': dict(sorted(lead_of.items())),
        'parts': dict(sorted(parts_of.items())),
        # Briefs and dossiers stay searchable as published material, never as records.
        'analysis': {r['id']: 1 for r in sorted(records, key=lambda r: r['id'])
                     if r['record_type'] in NOT_SOURCE_RECORDS},
        'unresolved': unresolved,
        'shared_url': sorted(sorted(ids) for ids in by_url.values() if len(ids) > 1),
    }
