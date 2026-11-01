"""
The JP MOD and PH AFP robots checks must give the verdicts they were
qualified with on Python 3.9, on every interpreter.

``tests/fixtures/robots_prefix/oracle_py39.json`` was frozen by running the
pre-``robots_prefix`` adapters (``urllib.robotparser`` with private hooks)
under Python 3.9.6. On Python 3.13 those hooks silently allowed every URL;
this replays each frozen row through the current adapters and requires the
same verdict, refusal message and request interval.

``plain_py39.json`` does the same for the collectors that only called the
public ``RobotFileParser.parse``/``can_fetch`` API; they now go through
``robots_prefix.legacy_can_fetch``, which must agree with every 3.9 verdict.
"""

import json
import unittest
from pathlib import Path

from scraper.sources import jp_mod, ph_afp, robots_prefix

FIXTURES = Path(__file__).parent / "fixtures" / "robots_prefix"
ORACLE = json.loads((FIXTURES / "oracle_py39.json").read_text(encoding="utf-8"))
PLAIN = json.loads((FIXTURES / "plain_py39.json").read_text(encoding="utf-8"))
ROOT = Path(__file__).resolve().parents[1]
PLAIN_CALLERS = (
    "scraper/sources/us_dvids.py",
    "scraper/sources/sg_mindef.py",
    "core/japan_mod_official_links.py",
    "scripts/collect_uscc_press_metadata.py",
    "scripts/collect_us_bis_homepage_metadata.py",
    "scripts/collect_us_treasury_press_metadata.py",
)


def replay(cls, method, row):
    adapter = object.__new__(cls)
    adapter._request_interval = 2.0
    try:
        getattr(adapter, method)(row["robots"], row["url"])
        verdict, message = "allowed", None
    except Exception as exc:
        verdict, message = type(exc).__name__, str(exc)
    return {"verdict": verdict, "message": message,
            "interval": adapter._request_interval}


class RobotsPrefixOracleTest(unittest.TestCase):
    def assert_matches_oracle(self, cls, method, rows):
        self.assertGreater(len(rows), 500)
        disallowed = 0
        for row in rows:
            expected = {k: row[k] for k in ("verdict", "message", "interval")}
            with self.subTest(robots=row["robots"], url=row["url"]):
                self.assertEqual(replay(cls, method, row), expected)
            disallowed += row["verdict"] == "RobotsDisallowed"
        # Guard against an oracle that could only ever say "allowed".
        self.assertGreater(disallowed, 100)

    def test_oracle_was_frozen_on_python_39(self):
        self.assertEqual(ORACLE["generated_with"],
                         "Python 3.9.6 urllib.robotparser")

    def test_japan_mod_matches_python_39(self):
        self.assert_matches_oracle(jp_mod.JPModAdapter, "assert_robots_allows",
                                   ORACLE["jp_mod"])

    def test_philippines_afp_matches_python_39(self):
        self.assert_matches_oracle(ph_afp.PHAfpAdapter, "assert_robots_allow",
                                   ORACLE["ph_afp"])

    def test_adapters_no_longer_use_stdlib_robotparser(self):
        for module in (jp_mod, ph_afp):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("robotparser", source, module.__name__)

    def test_legacy_can_fetch_matches_plain_python_39(self):
        self.assertTrue(PLAIN["generated_with"].startswith("Python 3.9"))
        verdicts = PLAIN["verdicts"]
        self.assertGreater(len(verdicts), 4000)
        # Guard against an oracle that could only ever say "allowed".
        self.assertGreater(sum(not v for v in verdicts.values()), 500)
        mismatches = []
        for key, expected in verdicts.items():
            index, agent, url = key.split("|", 2)
            lines = PLAIN["texts"][int(index)].lstrip("\ufeff").splitlines()
            got = robots_prefix.legacy_can_fetch(
                lines, PLAIN["agents"][agent], url)
            if got != expected:
                mismatches.append((key, expected, got))
        self.assertEqual(mismatches, [])

    def test_plain_callers_no_longer_use_stdlib_robotparser(self):
        for name in PLAIN_CALLERS:
            source = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("robotparser", source, name)
            self.assertIn("legacy_can_fetch", source, name)

    def test_no_module_calls_stdlib_robotparser(self):
        # 3.13's RFC 9309 parser gives different verdicts from 3.9; every
        # robots check outside robots_prefix must go through it instead.
        offenders = []
        for top in ("scraper", "core", "scripts", "site", "migrations"):
            for path in sorted((ROOT / top).rglob("*.py")):
                if path.name == "robots_prefix.py":
                    continue
                source = path.read_text(encoding="utf-8")
                if "import urllib.robotparser" in source or \
                        "RobotFileParser(" in source or \
                        "from urllib import robotparser" in source:
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_repeated_wildcard_groups_are_all_kept(self):
        groups = robots_prefix.parse(
            "User-agent: *\nDisallow: /j/\n\nUser-agent: *\nDisallow: /a/\n"
            .splitlines())
        self.assertEqual(len(groups), 2)
        allowed, _ = robots_prefix.evaluate(
            "User-agent: *\nDisallow: /j/\n\nUser-agent: *\nDisallow: /a/\n"
            .splitlines(), jp_mod.USER_AGENT, "https://www.mod.go.jp/a/x.html")
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
