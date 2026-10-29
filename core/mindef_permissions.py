"""Narrow written hyperlink approval for two Singapore MINDEF releases.

MINDEF Media Relations approved a *limited linking request* on 2026-10-29
for the two URLs below. The correspondence is retained privately in the
IPR/Source Permissions Gmail label. It is NOT a copyright/republication
license, approval for other MINDEF URLs, or automated collection authority.
See https://www.mindef.gov.sg/terms-of-use/ sections 5-6.
"""

MINDEF_SOURCE_SLUG = "sg_mindef_releases"
APPROVED_MINDEF_LINKS = frozenset({
    "https://www.mindef.gov.sg/news-and-events/latest-releases/23oct26-nr2/",
    "https://www.mindef.gov.sg/news-and-events/latest-releases/31may25_nr3/",
})


def is_mindef_source(source_slug):
    return source_slug == MINDEF_SOURCE_SLUG


def source_link_approved(source_slug, url):
    """Apply the narrow exception; preserve existing handling for other sources."""
    if not is_mindef_source(source_slug):
        return True
    return isinstance(url, str) and url in APPROVED_MINDEF_LINKS


def mindef_metadata_label(record_id):
    """IPR's neutral stand-in for a withheld MINDEF headline. Never a publisher title."""
    return "Source metadata — Singapore MINDEF record %s" % record_id
