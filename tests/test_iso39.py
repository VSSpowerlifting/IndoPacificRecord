"""
``tests/fixtures/iso39/oracle_py39.json`` was frozen by running
``make_oracle.py`` under Python 3.9.6: for each string, what 3.9's
``date.fromisoformat`` and ``datetime.fromisoformat`` returned, or null where
they raised. The helpers must give the same answer on every interpreter.
"""

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scraper.sources.iso39 import date_py39, datetime_py39

ORACLE = json.loads((Path(__file__).parent / "fixtures" / "iso39" /
                     "oracle_py39.json").read_text(encoding="utf-8"))


def result(parse, text):
    try:
        return parse(text).isoformat()
    except ValueError:
        return None


class Py39IsoFormatTests(unittest.TestCase):
    def test_accepts_the_py39_forms(self):
        self.assertEqual(date_py39("2026-10-09"), date(2026, 10, 9))
        self.assertEqual(datetime_py39("2026-10-09"), datetime(2026, 10, 9))
        self.assertEqual(datetime_py39("2026-10-09T10:30:00+08:00"),
                         datetime(2026, 10, 9, 10, 30,
                                  tzinfo=timezone(timedelta(hours=8))))
        self.assertEqual(datetime_py39("2026-10-09 10:30:00.123"),
                         datetime(2026, 10, 9, 10, 30, 0, 123000))

    def test_rejects_forms_only_311_accepts(self):
        for text in ("20261009", "2026-W40-5", "2026-282"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                date_py39(text)
        for text in ("20261009", "2026-10-09T10:30:00Z", "2026-10-09T1030",
                     "2026-10-09T10:30:00.1"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                datetime_py39(text)

    def test_rejects_malformed_time_py39_misread(self):
        with self.assertRaises(ValueError):
            datetime_py39("2026-10-091030+08:00")

    def test_matches_python_39_oracle(self):
        self.assertTrue(ORACLE["generated_with"].startswith("Python 3.9"))
        results = ORACLE["results"]
        self.assertGreater(len(results), 10000)
        # Guard against an oracle that could only ever say "rejected".
        self.assertGreater(sum(v[1] is not None for v in results.values()), 200)
        deviations = []
        for text, expected in results.items():
            got = [result(date_py39, text), result(datetime_py39, text)]
            if got == expected:
                continue
            # The one allowed difference: 3.9 took a digit at index 10 as the
            # separator and misread the malformed time after it.
            self.assertEqual(got, [None, None], text)
            self.assertIsNone(expected[0], text)
            self.assertTrue(text[10].isdigit(), text)
            deviations.append(text)
        self.assertEqual(len(deviations), 8, deviations)

    def test_rejects_non_strings(self):
        with self.assertRaises(ValueError):
            date_py39(b"2026-10-09")
        with self.assertRaises(ValueError):
            datetime_py39(None)


if __name__ == "__main__":
    unittest.main()
