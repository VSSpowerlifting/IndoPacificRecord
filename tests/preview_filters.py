"""The production renderer's reader filters, for tests that render a slice of
a preview template in a bare Jinja environment.

Desk pages print visible dates through `reader_date` (datetime attributes keep
ISO dates), so a bare environment without it cannot compile those templates.
Registering the renderer's own functions keeps the test's view of the markup
identical to production rather than approximating it.
"""
import sys
from pathlib import Path

PREVIEW = Path(__file__).resolve().parents[1] / "site" / "preview"
if str(PREVIEW) not in sys.path:
    sys.path.insert(0, str(PREVIEW))


def with_filters(env):
    import generate_preview as gp
    env.filters["reader_date"] = gp.reader_date
    env.filters["count"] = lambda n: "{:,}".format(n) if isinstance(n, int) else n
    return env
