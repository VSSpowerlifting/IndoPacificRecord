"""Keyboard journeys from the homepage box and the Archive box to a citation.
usage: journey.py SITE_DIR OUT_JSON"""
import functools, json, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent)); from measure_tasks import TASKS

site = Path(sys.argv[1]); out = Path(sys.argv[2])
index = json.loads((site / 'archive-research-index.json').read_text()); disp = index['display']
href_to_id = {('record/' + r['id'][7:] + '.html') if r['id'] in disp else (r['ipr_url'] or r['source_url']): r['id'] for r in index['records']}
class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(site)))
threading.Thread(target=srv.serve_forever, daemon=True).start(); origin = 'http://127.0.0.1:%d' % srv.server_port

def settle(page):
    page.wait_for_load_state('networkidle'); page.wait_for_timeout(350)
def ids(page):
    return [href_to_id.get(h, h) for h in page.eval_on_selector_all('#results .record-row h3 a', 'as => as.map(a => a.getAttribute("href"))')]

results = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for vp in ({'width': 1280, 'height': 900}, {'width': 375, 'height': 812}):
        ctx = b.new_context(viewport=vp); page = ctx.new_page()
        for name, kind, q, expected in TASKS:
            for entry in ('home', 'archive'):
                trail = []
                if entry == 'home':
                    page.goto(origin + '/index.html', wait_until='networkidle'); page.locator('#home-q').fill(q)
                else:
                    page.goto(origin + '/archive.html', wait_until='networkidle'); page.locator('#f-q').fill(q)
                page.keyboard.press('Enter'); settle(page); trail.append('submit')
                first_url = page.url.split('/')[-1]; first_ids = ids(page)
                U = lambda i: expected == ['*'] or i in expected
                got = [i for i in first_ids if U(i)]
                widened = None
                if expected and not got:
                    more = page.locator('#scope-more button')
                    rec = [x for x in page.locator('#no-results button').all() if x.is_visible()]
                    if more.count() and more.is_visible():
                        widened = 'offered: ' + more.inner_text(); more.focus(); page.keyboard.press('Enter'); trail.append('widen (offered)')
                    elif rec and rec[0].get_attribute('value') != 'clear':
                        widened = 'offered: ' + rec[0].inner_text(); rec[0].focus(); page.keyboard.press('Enter'); trail.append('widen (offered)')
                    else:
                        widened = 'not offered'
                    settle(page); got = [i for i in ids(page) if U(i)]
                    if not got and page.locator('#f-scope').input_value() != 'published':
                        page.locator('#f-scope').select_option('published'); settle(page); trail.append('choose "All published material" unprompted')
                        got = [i for i in ids(page) if U(i)]
                rank = ids(page).index(got[0]) + 1 if got else None
                citation = hold = None
                if got:
                    row = page.locator('#results .record-row').nth(rank - 1)
                    hold = row.locator('.archive-hold').inner_text() if row.locator('.archive-hold').count() else None
                    summ = row.locator('details summary'); summ.focus(); page.keyboard.press('Enter'); trail.append('open citation')
                    citation = row.locator('.archive-citation').inner_text()
                    hold_before_cite = None
                results.append(dict(viewport=vp['width'], task=name, kind=kind, q=q, entry=entry, first_url=first_url,
                    first_shown=len(first_ids), first_useful_in_first_view=bool([i for i in first_ids if U(i)]),
                    widen=widened, final_url=page.url.split('/')[-1], rank=rank, steps=len(trail), trail=trail,
                    citation=(citation or '')[:160], hold=hold, range=page.locator('#result-range').inner_text(),
                    hint=page.locator('#scope-more').inner_text() if page.locator('#scope-more').count() and page.locator('#scope-more').is_visible() else ''))
        ctx.close()
    b.close()
srv.shutdown(); out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
for r in results:
    print(r['viewport'], f"{r['task'][:26]:26} {r['entry']:7} first={r['first_shown']:3} rank={r['rank']} steps={r['steps']} {' > '.join(r['trail'])} | {r['widen'] or ''}"[:230])
