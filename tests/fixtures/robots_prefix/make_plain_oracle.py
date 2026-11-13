"""Freeze plain Python 3.9 urllib.robotparser verdicts as plain_py39.json.

The collectors that called the public RobotFileParser API (parse +
can_fetch, no private hooks) now use robots_prefix.legacy_can_fetch. This
records what the 3.9 stdlib parser itself said, so it must run under 3.9:

    python3.9 make_plain_oracle.py make_oracle.py [checkout] > plain_py39.json

It reuses the robots texts from make_oracle.py and adds plain-caller cases.
"""
import importlib.util, json, sys, urllib.robotparser
spec = importlib.util.spec_from_file_location("mo", sys.argv[1])
mo = importlib.util.module_from_spec(spec)
# make_oracle imports the adapters from the checkout in its argv[1]; any
# checkout works because only its COMMON and agent_texts() are reused.
sys.argv = [sys.argv[0], sys.argv[2] if len(sys.argv) > 2 else
            str(__import__("pathlib").Path(__file__).resolve().parents[3])]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    try:
        spec.loader.exec_module(mo)
    except Exception:
        pass
CMW = ("ChinaMilWatch-ShadowCollector/0.1 "
       "(+https://chinamilwatch.org; research archive; contact via site)")
IPR = "IndoPacificRecordResearchBot/1.0 (+https://indopacificrecord.org/about.html)"
AGENTS = [CMW, IPR, "*"]
texts = list(mo.COMMON)
for tok in ("ChinaMilWatch-ShadowCollector", "IndoPacificRecordResearchBot"):
    texts += mo.agent_texts(tok)
texts += [
    "User-agent: *\nDisallow: /\nAllow: /news/\n",
    "User-agent: *\nDisallow: /\nAllow: /press-releases\n",
    "User-agent: *\nDisallow: /news\nAllow: /news/\n",
    "User-agent: *\nDisallow: /robots.txt\n",
    "User-agent: *\nDisallow: /rss/\n\nUser-agent: *\nDisallow: /j/\n",
    "User-agent: Googlebot\nDisallow: /\n\nUser-agent: *\nAllow: /\n",
    "User-agent: *\nAllow: /\n\nUser-agent: ChinaMilWatch\nDisallow: /\n",
    "User-agent: IndoPacificRecordResearchBot\nDisallow: /\n",
    "User-agent: indopacificrecordresearchbot/1.0\nDisallow: /\n",
    "User-agent: *\nDisallow: /news%20x\n",
    "User-agent: *\nDisallow: /news x\n",
    "User-agent: *\nDisallow: /%7Euser/\n",
    "User-agent: *\nDisallow: /~user/\n",
    "User-agent: *\nDisallow: /a\n\nUser-agent: *\n",
]
texts = [t for t in texts if t is not None]
URLS = ["https://h.test/", "https://h.test", "https://h.test/news/x",
        "https://h.test/news", "https://h.test/rss/unit/USINDOPACOM",
        "https://h.test/press-releases", "https://h.test/j/rss/news.xml",
        "https://h.test/j/press/x.pdf", "https://h.test/robots.txt",
        "https://h.test/a/x", "https://h.test/news%20x", "https://h.test/news x",
        "https://h.test/~user/p", "https://h.test/%7Euser/p",
        "https://h.test/articles/afp-chief-visits-northern-luzon-command/",
        "https://h.test/articles/?page=2", "https://h.test/x.pdf",
        "https://h.test/j/%E8%B3%87%E6%96%99/x.pdf"]
out = {}
for i, t in enumerate(texts):
    for a in AGENTS:
        for u in URLS:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(t.lstrip("﻿").splitlines())
            out["%d|%s|%s" % (i, a[:12], u)] = rp.can_fetch(a, u)
json.dump({"generated_with": "Python %s urllib.robotparser"
                       % sys.version.split()[0],
           "agents": {a[:12]: a for a in AGENTS},
           "texts": texts, "verdicts": out},
          sys.stdout, ensure_ascii=False, indent=0)
print()
