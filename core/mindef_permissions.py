"""Safe official outbound MINDEF hyperlinks. Not a licence to republish MINDEF text or media.

This module gates only exact official-host links. Which MINDEF-derived components
may be public is decided per component elsewhere: an independently written,
MINDEF-attributed factual explanation bound to an admitted official-link parent
(``core.mindef_public_boundary.permitted_machine_sql``,
``core.singapore_mindef_links``). Original publisher text, media and any
production activation remain outside this gate. The founder's standing
authorization is recorded in ``config/philippines_daily_policy.json`` and
``docs/desks/MIGRATION.md``; it is not reproduced here.
"""
import re
from urllib.parse import urlsplit

MINDEF_SOURCE_SLUG = "sg_mindef_releases"
MINDEF_LINK_HOST = "www.mindef.gov.sg"
SAFE_PATH = re.compile(r"/[A-Za-z0-9_./-]*\Z")


def is_mindef_source(source_slug):
    return source_slug == MINDEF_SOURCE_SLUG


def source_link_approved(source_slug, url):
    """Exact official-host HTTPS link gate; preserves other sources' treatment."""
    if not is_mindef_source(source_slug):
        return True
    if not isinstance(url, str) or not url or url != url.strip():
        return False
    try:
        p = urlsplit(url)
        path = p.path or "/"  # bare host is the official homepage root
        return (p.scheme == "https" and p.hostname == MINDEF_LINK_HOST
                and p.username is None and p.password is None and p.port is None
                and not p.query and not p.fragment and not p.netloc.endswith(".")
                and SAFE_PATH.fullmatch(path) is not None
                and not path.startswith("//") and ".." not in path.split("/"))
    except ValueError:
        return False


def mindef_metadata_label(record_id):
    """Neutral label, never a MINDEF publisher title."""
    return "Source metadata — Singapore MINDEF record %s" % record_id
