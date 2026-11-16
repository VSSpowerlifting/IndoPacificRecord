"""The production renderer's reader filters, for tests that render a slice of
a preview template in a bare Jinja environment.

Desk pages print visible dates through `reader_date` (datetime attributes keep
ISO dates), so a bare environment without it cannot compile those templates.
The functions come from `core.reader_format`, which the renderer itself uses
and which needs only the standard library: some CI jobs install only Jinja.
"""
from core.reader_format import count, reader_date


def with_filters(env):
    env.filters["reader_date"] = reader_date
    env.filters["count"] = count
    return env
