#!/usr/bin/env python3
"""Persistent complete-route HTML/CSS/JS gate and conservative asset inventory.

Runs against a governed render; never renders or modifies production itself.
Fonts/image variants are counted once per route. Browser delivery receipts
measure the smaller actually requested subset. Historical images/fonts retain
their provenance and are reported rather than silently recompressed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.frontend_budget import measure_page

INDEX_NAMES = ('index.html', 'archive.html', 'analysis.html', 'corpus.html', 'pla-watch.html', 'desks.html')
# Owner authorization, DECISION_LOG 2026-10-26, raised 2026-11-13: individual
# dossier pages (dossier/<slug>.html only) may deliver up to 230 KB of HTML+CSS.
DOSSIER_HTML_CSS_CAP = 230000
# Owner authorization, DECISION_LOG 2026-11-13: temporary 130 KB HTML+CSS
# allowance for the root Indonesia desk page only, while its admitted Kemhan
# link list grows. Raised to 160 KB by the founder on 21 Nov 2026 (eight-desk
# lead session, PR for this constant) after 100 admitted links reached
# 130,483 bytes and would have failed every desk's Daily offline suite. The
# desk now lists only the latest 60 admitted links (core.official_link_index
# DESK_LINK_LIMIT); the full index moved to indonesia-official-links.html and
# indonesia-official-links/YYYY-MM.html, which keep the default 120 KB cap. A
# month page over that cap holds its writer. Every other desk, record and
# nested route keeps its cap.
INDONESIA_HTML_CSS_CAP = 160000
# Owner authorization, DECISION_LOG 2026-11-13 (PR #1055): temporary 125 KB
# HTML+CSS for record/476.html only. That page carries 54,211 bytes of
# preserved stored source text (the 20 May 2026 China-Russia joint
# statement) and sat 656 bytes under 120 KB before the #1053 Record CSS.
# Every other record keeps 120 KB.
RECORD_476_HTML_CSS_CAP = 125000
# Owner authorization, DECISION_LOG 2026-11-16 (PR #1064): temporary 130 KB
# HTML+CSS for the root Korea desk page only, while its admitted MND and DAPA
# official-link list grows (about 510 bytes a link). Raised to 160 KB by the
# founder on 21 Nov 2026 after the committed page reached 132,857 bytes and
# failed every desk's Daily offline suite. The desk's new-link rail now lists
# only the latest 60 (core.official_link_index DESK_LINK_LIMIT); the full index
# is korea-official-links.html and korea-official-links/YYYY-MM.html at the
# default 120 KB cap, and a month page over it holds its writer. Every other
# desk, record and nested route keeps its cap.
KOREA_HTML_CSS_CAP = 160000


def html_css_cap(route):
    if route == 'indonesia.html':
        return INDONESIA_HTML_CSS_CAP
    if route == 'record/476.html':
        return RECORD_476_HTML_CSS_CAP
    if route == 'korea.html':
        return KOREA_HTML_CSS_CAP
    parts = route.split('/')
    if parts[0] == 'dossier':
        # Nothing under dossier/ takes the hub allowance; nested or index
        # paths keep the strict cap.
        return DOSSIER_HTML_CSS_CAP if len(parts) == 2 and parts[1] != 'index.html' else 120000
    # Index/archive hubs have the governed 300 KB allowance. Individual
    # records, Briefs, week shards and the dossier collection retain 120 KB.
    return 300000 if parts[-1] in INDEX_NAMES else 120000


def verify(root, only=None):
    """Measure every HTML route, or just the site-relative routes in `only`."""
    root = Path(root).resolve()
    routes, failures = [], []
    pages = (sorted(root.rglob('*.html')) if only is None
             else [root / route for route in sorted(set(only))])
    for page in pages:
        route = page.relative_to(root).as_posix()
        html_cap = html_css_cap(route)
        js_cap = 12000 if route == 'index.html' else 10000
        values = measure_page(page, root)
        item = dict(route=route, html_css_limit=html_cap, js_limit=js_cap, **values)
        item['local_delivery_bytes'] = values['html_css_bytes'] + values['js_bytes'] + values['asset_bytes']
        routes.append(item)
        if values['html_css_bytes'] > html_cap or values['js_bytes'] > js_cap:
            failures.append(item)
    if not routes:
        raise ValueError('No HTML routes found')
    return {'routes_checked': len(routes), 'failures': failures,
            'largest_html_css': max(routes, key=lambda r: r['html_css_bytes']),
            'largest_local_delivery': max(routes, key=lambda r: r['local_delivery_bytes']),
            'routes': routes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', required=True); parser.add_argument('--receipt', required=True)
    # A page-only writer gates exactly the routes it will commit; repeatable.
    # A named route that is missing fails rather than being skipped.
    parser.add_argument('--only', action='append', metavar='ROUTE')
    args = parser.parse_args()
    if args.only is not None:
        for route in args.only:
            target = (Path(args.root) / route).resolve()
            if (Path(args.root).resolve() not in target.parents
                    or not route.endswith('.html') or not target.is_file()):
                print('Missing or invalid gated route: %s' % route)
                sys.exit(1)
    result = verify(args.root, only=args.only)
    Path(args.receipt).write_text(json.dumps(result, indent=2) + '\n')
    print('Checked %s routes: %s delivery budget failures' % (result['routes_checked'], len(result['failures'])))
    if result['failures']:
        print([(v['route'], v['html_css_bytes'], v['js_bytes']) for v in result['failures']])
        sys.exit(1)
