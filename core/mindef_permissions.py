"""Safe official outbound MINDEF hyperlinks; NOT a content reuse license.

Founder-reported standing link permission requires private provenance review
before this amendment merges. Historic 2026-10-29 two-URL grant is documented
separately. No right to reproduce text/media or invoke collectors/models follows.
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
        return (p.scheme == "https" and p.hostname == MINDEF_LINK_HOST
                and p.username is None and p.password is None and p.port is None
                and not p.query and not p.fragment and not p.netloc.endswith(".")
                and SAFE_PATH.fullmatch(p.path) is not None
                and not p.path.startswith("//") and ".." not in p.path.split("/"))
    except ValueError:
        return False


def mindef_metadata_label(record_id):
    """Neutral label, never a MINDEF publisher title."""
    return "Source metadata — Singapore MINDEF record %s" % record_id
