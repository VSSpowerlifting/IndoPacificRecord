"""Freeze Python 3.9 date/datetime.fromisoformat results as oracle_py39.json.

scraper/sources/iso39.py must accept exactly what 3.9 accepted and return the
same value. This records what the 3.9 stdlib itself returned for a corpus of
ISO-like strings, so it must run under 3.9:

    python3.9 make_oracle.py > oracle_py39.json

Each value is [date result, datetime result]: the result's isoformat(), or
null where 3.9 raised. The corpus is deterministic (fixed seed).
"""
import itertools, json, platform, random, sys
from datetime import date, datetime

assert sys.version_info[:2] == (3, 9), "run under Python 3.9"
random.seed(9)
DATES = ["2026-10-09", "20261009", "2026-W40-5", "2026W405", "2026-282",
         "2026-10", "2026-1-09", "0001-01-01", "2026-02-30",
         "２０２６-10-09", "2026-10-09 "]
SEPARATORS = ["", "T", " ", "t", "x", "\n", "TT"]
TIMES = ["", "10", "10:30", "1030", "10:30:15", "103015", "10:30:15.123",
         "10:30:15.123456", "10:30:15.1", "10:30:15,123", "10:30:15.1234567",
         "24:00", "10:30:60"]
OFFSETS = ["", "+08:00", "-05:30", "+0800", "+08", "Z", "z", "+08:00:30",
           "+08:00:30.123456", "+08:00:30.123", "+25:00", "+08:00Z"]
corpus = {"".join(parts) for parts in
          itertools.product(DATES, SEPARATORS, TIMES, OFFSETS)}
for _ in range(3000):
    corpus.add("".join(random.choice("0123456789-:T+.Z W")
                       for _ in range(random.randint(8, 30))))


def result(parse, text):
    try:
        return parse(text).isoformat()
    except (ValueError, OverflowError):
        return None


results = {text: [result(date.fromisoformat, text),
                   result(datetime.fromisoformat, text)]
           for text in sorted(corpus)}
# One string per line keeps a regenerated oracle reviewable as a diff.
print('{"generated_with": %s,' % json.dumps(
    "Python %s date/datetime.fromisoformat" % platform.python_version()))
print(' "results": {')
print(",\n".join("  %s: %s" % (json.dumps(text, ensure_ascii=False),
                               json.dumps(value))
                 for text, value in results.items()))
print(" }}")
