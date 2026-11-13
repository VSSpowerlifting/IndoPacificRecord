"""Freeze the Python 3.9 verdicts of the JP MOD and PH AFP robots checks.

Run only against a checkout from before robots_prefix existed (77c5deb2d5)
under Python 3.9, where both adapters still drove urllib.robotparser:

    python3.9 make_oracle.py <old-checkout> > oracle_py39.json

Running it against the current adapters would only test them against
themselves.
"""
import json, sys
sys.path.insert(0, sys.argv[1])
from scraper.sources import jp_mod, ph_afp

SLUG = "afp-chief-visits-northern-luzon-command"
JP_URLS = [
    "https://www.mod.go.jp/j/press/news/2026/08/25a.pdf",
    "https://www.mod.go.jp/j/press/news/2026/08/26b.html",
    "https://www.mod.go.jp/j/資料/x.pdf",
    "https://www.mod.go.jp/j/%E8%B3%87%E6%96%99/x.pdf",
    "https://www.mod.go.jp/a/index.html",
    "https://www.mod.go.jp/sp/j/press/",
    "https://www.mod.go.jp/j/press/a%2Fb.html",
    "https://www.mod.go.jp/j/press/x.html;v=1",
    "https://www.mod.go.jp/j/press/x.html?q=1",
    "https://www.mod.go.jp/j/press/x.html#frag",
    "https://www.mod.go.jp",
    "https://www.mod.go.jp/",
]
PH_URLS = [
    "https://api.afp.mil.ph/articles/%s/" % SLUG,
    "https://api.afp.mil.ph/articles/",
    "https://api.afp.mil.ph/articles/?page=2",
    "https://api.afp.mil.ph/articles/?page=3",
    "https://www.afp.mil.ph/news/%s" % SLUG,
    "https://www.afp.mil.ph/news/%s/" % SLUG,
    "https://api.afp.mil.ph/articles/afp-other-story/",
    "https://api.afp.mil.ph/articles/a%2Fb/",
    "https://api.afp.mil.ph",
]
JP_TOKEN = jp_mod.USER_AGENT.split("/")[0]
PH_TOKEN = ph_afp.USER_AGENT.split("/")[0]
ART = "/articles/%s/" % SLUG
COMMON = [
    None,
    "",
    "User-agent: *\nDisallow: /a/\nDisallow: /sp/j/\n",
    "User-agent: Bingbot\nDisallow: /\n\nUser-agent: *\nDisallow: /a/\n",
    "# comment\nUser-agent: *\n\nDisallow: /a/  # trailing\n",
    "User-agent: *\nDisallow: /j/\n",
    "User-agent: *\nDisallow: /j/資料/\n",
    "User-agent: *\nDisallow: /j/%E8%B3%87%E6%96%99/\n",
    "User-agent: *\nDisallow: /\n\n",
    "User-agent: *\nDisallow: /\n",
    "User-agent: *\nDisallow:\n",
    "User-agent: *\nAllow:\n",
    "User-agent: *\nAllow: /\n",
    "User-agent: *\nDisallow: /j/\n\nUser-agent: *\nDisallow: /a/\n",
    "User-agent: *\nDisallow: /j/press/\nAllow: /j/press/\n",
    "﻿User-agent: *\r\nCrawl-delay: 7\r\n",
    "User-agent: *\nCrawl-delay: 7\n",
    "User-agent: *\nCrawl-delay: 1\n",
    "User-agent: *\nCrawl-delay: 30\nDisallow: /a/\n\nUser-agent: Other\nCrawl-delay: 99\n",
    "User-agent: *\nCrawl-delay: 1.5\n",
    "User-agent: *\nCrawl-delay: unknown\n",
    "User-agent: *\nDisallow: /*.pdf$\n",
    "User-agent: *\nDisallow: /articles/*/\n",
    "User-agent: *\nDisallow: " + ART + "$\n",
    "Disallow: /\n",
    "Crawl-delay: 9\nUser-agent: *\nDisallow: /a/\n",
    "User-agent: *\nRequest-rate: 1/5\nDisallow: /a/\n",
    "User-agent: *\nSitemap: https://example.test/s.xml\nDisallow: /a/\n",
    "User-agent: *\nDisallow: /j/press/a%2Fb.html\n",
    "User-agent: *\nDisallow: /j/press/a/b.html\n",
    "User-agent: *\nDisallow: /articles/a%2Fb/\n",
    "User-agent: *\nDisallow: /articles/a/b/\n",
    "User-agent: *\n\nUser-agent: Other\nDisallow: /\n",
    "User-agent: Other\nUser-agent: *\nDisallow: /j/\n",
    "user-agent: *\nDISALLOW: /j/\n",
    "User-agent: *\nDisallow : /j/\n",
    "User-agent: *\nDisallow /j/\n",
    "User-agent: *\nDisallow: /j/press/x.html;v=1\n",
    "User-agent: *\nDisallow: /j/press/x.html?q=1\n",
    "User-agent: *\nDisallow: /articles/?page=2\n",
    "User-agent: *\nDisallow: /?\n",
    "User-agent: *\nAllow: /\nDisallow: " + ART + "\n",
    "User-agent: *\nAllow: /\nDisallow: /news/%s\n" % SLUG,
    "User-agent: *\nDisallow: /articles/\nAllow: " + ART + "\n",
    "User-agent: OtherCollector\nDisallow: /\n\nUser-agent: *\nAllow: /\n\nUser-agent: *\nDisallow: " + ART + "\n",
]


def agent_texts(token):
    t = token
    return [
        "User-agent: %s\nDisallow: /\n\n" % t.split("-")[0],
        "User-agent: %s\nDisallow: /j/\n\n" % t,
        "User-agent: %s\nAllow: /j/press/\n" % t.lower(),
        "User-agent: %s\nCrawl-delay: 11\nUser-agent: *\nCrawl-delay: 5\n" % t,
        "User-agent: *\nDisallow: /\n\nUser-agent: %s\nAllow: /\n" % t,
        "User-agent: *\nAllow: /\n\nUser-agent: %s\nDisallow: /articles/\n" % t.split("-")[0],
        "User-agent: %s\nAllow: /\n\nUser-agent: %s\nDisallow: %s\n" % (t.lower(), t.upper(), ART),
        "User-agent: %s\nAllow: /\n\nUser-agent: %s\nDisallow: %s\n" % (t, t, ART),
        "User-agent: %s\nDisallow: /articles/afp-\n\nUser-agent: %s\nAllow: %s\n" % (t, t, ART),
        "User-agent: %s\nDisallow: %s\n\nUser-agent: %s\nAllow: %s\n" % (t, ART, t, ART),
        "User-agent: %s\nAllow: %s\n\nUser-agent: %s\nDisallow: %s\n" % (t, ART, t, ART),
        "User-agent: OtherCollector\nDisallow: /\n\nUser-agent: *\nAllow: /\n\n"
        "User-agent: *\nDisallow: %s\n\nUser-agent: %s\nAllow: /\n" % (ART, t),
        "User-agent: %s\nDisallow: /a/\n\nUser-agent: %s\nDisallow: /j/\n" % (t.split("-")[0], t),
        "User-agent: Shadow\nDisallow: /\n",
        "User-agent: %sX\nDisallow: /\n" % t,
        "User-agent: %s/0.1\nDisallow: /\n" % t,
    ]


def run(cls, method, texts, urls):
    rows = []
    for text in texts:
        for url in urls:
            adapter = object.__new__(cls)
            adapter._request_interval = 2.0
            try:
                getattr(adapter, method)(text, url)
                verdict, message = "allowed", None
            except Exception as exc:  # record the exact refusal
                verdict, message = type(exc).__name__, str(exc)
            rows.append({"robots": text, "url": url, "verdict": verdict,
                         "message": message,
                         "interval": adapter._request_interval})
    return rows


oracle = {
    "generated_with": "Python %d.%d.%d urllib.robotparser" % sys.version_info[:3],
    "jp_mod": run(jp_mod.JPModAdapter, "assert_robots_allows",
                  COMMON + agent_texts(JP_TOKEN), JP_URLS),
    "ph_afp": run(ph_afp.PHAfpAdapter, "assert_robots_allow",
                  COMMON + agent_texts(PH_TOKEN), PH_URLS),
}
json.dump(oracle, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
sys.stdout.write("\n")
