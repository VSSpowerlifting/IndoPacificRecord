"""Side-by-side before/after WebP captures. usage: capture.py BEFORE AFTER OUTDIR"""
import functools, io, sys, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
class Q(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
def serve(d):
    s = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Q, directory=d)); threading.Thread(target=s.serve_forever, daemon=True).start()
    return 'http://127.0.0.1:%d' % s.server_port
before, after, outdir = serve(sys.argv[1]), serve(sys.argv[2]), Path(sys.argv[3]); outdir.mkdir(parents=True, exist_ok=True)
SHOTS = [  # name, width, start, typed query (None: open URL), field, anchor to scroll to, height
 ('home-abukuma-desktop', 1280, '/index.html', 'Abukuma', '#home-q', '#result-range', 760),
 ('home-abukuma-mobile', 375, '/index.html', 'Abukuma', '#home-q', '#result-range', 900),
 ('archive-amraam-empty-desktop', 1280, '/archive.html', 'AMRAAM', '#f-q', '#result-range', 420),
 ('archive-laos-focus-mobile', 375, '/archive.html', 'Laos', '#f-q', '#result-range', 640),
]
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, start, q, field, anchor, h in SHOTS:
        imgs = []
        for origin in (before, after):
            page = b.new_page(viewport={'width': w, 'height': h}, reduced_motion='reduce')
            page.goto(origin + start, wait_until='networkidle'); page.locator(field).fill(q); page.keyboard.press('Enter')
            page.wait_for_load_state('networkidle'); page.wait_for_timeout(600)
            page.evaluate('a => { document.querySelector(a).scrollIntoView({block:"start"}); scrollBy(0, -24); }', anchor)
            imgs.append(Image.open(io.BytesIO(page.screenshot())).convert('RGB')); page.close()
        gap = 24; W = imgs[0].width * 2 + gap; canvas = Image.new('RGB', (W, max(i.height for i in imgs)), (200, 200, 200))
        canvas.paste(imgs[0], (0, 0)); canvas.paste(imgs[1], (imgs[0].width + gap, 0))
        if canvas.width > 1600: canvas = canvas.resize((1600, round(canvas.height * 1600 / canvas.width)))
        canvas.save(outdir / (name + '.webp'), 'WEBP', quality=72); print(name, canvas.size)
    b.close()
