"""
ISO 8601 parsing with Python 3.9's acceptance, on any interpreter.

From 3.11, `date.fromisoformat` and `datetime.fromisoformat` also accept basic
forms (`20261009`), week dates (`2026-W40-5`), a trailing `Z` and other
spellings 3.9 refused. Adapters that read a publisher's date string relied on
the 3.9 refusal to reject an unexpected format; these helpers keep it. A string
outside the 3.9 grammar raises ValueError, as 3.9 itself would.

One deliberate deviation fails closed: 3.9 took any character at index 10 as
the separator and then accepted a malformed three-digit time, so it read
`2026-10-091030+08:00` as 03:00 on 9 October. The grammar here rejects it.
"""
import re
from datetime import date, datetime

# 3.9's grammar: YYYY-MM-DD, optionally a one-character separator, HH[:MM[:SS
# [.fff|.ffffff]]] and an offset [+-]HH:MM[:SS[.ffffff]].
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"(?:.[0-9]{2}(?::[0-9]{2}(?::[0-9]{2}(?:\.(?:[0-9]{3}|[0-9]{6}))?)?)?"
    r"(?:[+-][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{6})?)?)?)?",
    re.DOTALL)


def date_py39(text: str) -> date:
    if not isinstance(text, str) or not _DATE.fullmatch(text):
        raise ValueError("Invalid isoformat string: %r" % (text,))
    return date.fromisoformat(text)


def datetime_py39(text: str) -> datetime:
    if not isinstance(text, str) or not _DATETIME.fullmatch(text):
        raise ValueError("Invalid isoformat string: %r" % (text,))
    return datetime.fromisoformat(text)
