"""Official originals cited by approved Briefs, admitted as link-metadata Records.

An approved Brief already publishes each publisher reference's URL, publisher,
issuer, date, language and original title. This module turns the *official*
ones into IPR Records that publish exactly that metadata and nothing more: no
source text, no excerpt, no verification notes, no desk coverage. Every
citing Brief links to the Record and the Record links back to every Brief.

One Record per source URL, keyed on `url_key` (scheme and host lowercased,
fragment dropped) while the exact URL is what the page shows and links. A URL
already held as a corpus record or a released machine explanation resolves to
that page instead of a new one, so manual citation and automated collection
converge on one identity. When that happens to a URL that already had a cited
page, the old route becomes a redirect rather than a dead citation.

The rights gate fails closed. Independent reporting stays an external
citation. Singapore MINDEF is omitted entirely: its 2026-10-29 permission
covers hyperlinks from a Brief, not a standalone page bearing its headline.
The Vietnam MPS, MOIT and VPCP families get no new page without a sealed
decision, but a URL of theirs that IPR already publishes under its own
admission still resolves to that page: linking to it shows nothing of the
source that the page and the Brief do not already show. The Brief's own
publisher reference is left exactly as approved.
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit

from core import vietnam_source_use

ROUTE_DIR = "record"
FIELDS = ("url", "publisher", "issuer", "date", "lang", "original_title")

# Hosts whose family has no public_title_display standing until an owner
# decision is sealed. Those decisions need a secret the renderer never holds.
HELD_HOSTS = {
    "bocongan.gov.vn": vietnam_source_use.MPS,
    "moit.gov.vn": "vn_moit_energy_vi",
    "vanban.chinhphu.vn": vietnam_source_use.VPCP,
    "datafiles.chinhphu.vn": vietnam_source_use.VPCP,
}
MINDEF_HOSTS = {"mindef.gov.sg", "www.mindef.gov.sg"}


def _under(host: str, domains):
    """The listed domain `host` is, or is a subdomain of; None otherwise.

    Gates match subdomains too, so `www.bocongan.gov.vn` is held exactly as
    `bocongan.gov.vn` is: a hold that a host prefix could evade fails open.
    """
    for domain in domains:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def url_key(url: str) -> str:
    """The identity a cited URL is matched and routed by.

    Only what can never name a different document is normalized: scheme and
    host case, and the fragment, which never reaches the server. Path and
    query are kept exactly, because publishers do serve different documents
    under paths that differ only in case or a trailing slash.
    """
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path, parts.query, ""))


def cited_id(url: str) -> str:
    return hashlib.sha256(url_key(url).encode("utf-8")).hexdigest()[:16]


def cited_path(url: str) -> str:
    return "%s/cited-%s.html" % (ROUTE_DIR, cited_id(url))


def omission(ref: dict):
    """Why a publisher reference cannot become a Record; None when it can."""
    return _link_gate(ref) or _new_page_gate(ref)


def _link_gate(ref: dict):
    """Why a reference may not link to any IPR page, even one already held."""
    if ref.get("independence") != "official":
        return "independent_reference"
    url = ref.get("url")
    parts = urlsplit(url) if isinstance(url, str) else None
    if (not parts or parts.scheme != "https" or not parts.hostname
            or parts.username or parts.password or url != url.strip()):
        return "unsafe_url"
    host = parts.hostname.lower()
    if _under(host, MINDEF_HOSTS):
        return "mindef_link_only_permission"
    return None


def _new_page_gate(ref: dict):
    """Why a reference may not mint a cited Record of its own."""
    family = HELD_HOSTS.get(_under(urlsplit(ref["url"]).hostname.lower(), HELD_HOSTS))
    if family and not vietnam_source_use.standing(family).allows("public_title_display"):
        return "held_source_family:" + family
    if not all(isinstance(ref.get(k), str) and ref[k].strip()
               for k in ("publisher", "issuer", "original_title", "lang")):
        return "incomplete_metadata"
    return None


def resolve(collection, *, corpus_by_url=None, machine_by_url=None):
    """Admit approved Briefs' official citations.

    Returns `(records, brief_links, omitted, moved)`:

    * records: one dict per new cited Record, newest source date first;
    * brief_links: {brief slug: {reference id: site-relative route}};
    * omitted: (slug, reference id, url, reason) for every reference left
      as an external citation only;
    * moved: {cited route: corpus or machine route} for every admitted URL
      that resolves to a held page, so a cited route that was published
      before the URL was collected keeps answering with a redirect.

    Corpus records that a Brief cites gain a `brief_reference` entry in their
    own `in_trails`, and machine records one in their `cited_in`, so either
    page links back without a second Record. That lookup runs before the
    held-family gate, which only stops a new page being minted.
    """
    corpus_by_key = {url_key(u): r for u, r in (corpus_by_url or {}).items()}
    machine_by_key = {url_key(u): r for u, r in (machine_by_url or {}).items()}
    by_key, brief_links, omitted, moved = {}, {}, [], {}
    for brief in collection.briefs:
        if brief.get("is_review"):
            continue
        sidecar = collection.sidecars[brief["slug"]]
        if sidecar.get("synthetic"):
            continue
        links = {}
        for ref in sidecar.get("publisher_references") or []:
            reason = _link_gate(ref)
            if reason:
                omitted.append((brief["slug"], ref.get("id"), ref.get("url"), reason))
                continue
            url, key = ref["url"], url_key(ref["url"])
            citing = {"slug": brief["slug"], "issue": brief["issue"],
                      "date": brief["date"], "title": brief["title"],
                      "url": brief["url"], "series_name": brief["series_name"],
                      "publication": brief.get("publication"),
                      "kind": "brief_reference", "anchor": "publisher-" + ref["id"]}
            if key in corpus_by_key:
                rec = corpus_by_key[key]
                trails = rec.setdefault("in_trails", [])
                if not any(t["slug"] == brief["slug"] and t.get("kind") == "brief_reference"
                           for t in trails):
                    trails.append(citing)
                links[ref["id"]] = moved[cited_path(url)] = "%s/%d.html" % (ROUTE_DIR, rec["id"])
                continue
            if key in machine_by_key:
                rec = machine_by_key[key]
                backlinks = rec.setdefault("cited_in", [])
                if not any(c["slug"] == brief["slug"] for c in backlinks):
                    backlinks.append(citing)
                links[ref["id"]] = moved[cited_path(url)] = rec["record_path"]
                continue
            reason = _new_page_gate(ref)
            if reason:
                omitted.append((brief["slug"], ref["id"], url, reason))
                continue
            record = by_key.get(key)
            if record is None:
                record = by_key[key] = dict({k: ref[k] for k in FIELDS},
                    id=cited_id(url), record_path=cited_path(url),
                    cited_only=True, cited_in=[])
            elif any(record[k] != ref[k] for k in FIELDS[1:]):
                # Two Briefs describing one URL differently is an editorial
                # discrepancy to resolve, never one to paper over silently.
                # The URL itself may differ only by what url_key ignores.
                raise ValueError("cited_source_metadata_conflict: %s" % url)
            if not any(c["slug"] == brief["slug"] for c in record["cited_in"]):
                record["cited_in"].append(citing)
            links[ref["id"]] = record["record_path"]
        if links:
            brief_links[brief["slug"]] = links
    records = sorted(by_key.values(), key=lambda r: (r["date"] or "", r["url"]), reverse=True)
    return records, brief_links, omitted, moved


def citation(record: dict, origin: str) -> str:
    return "%s. “%s.” %s. %s. Record: %s/%s" % (
        record["issuer"], record["original_title"], record["date"] or "Undated",
        record["url"], origin, record["record_path"])


def archive_rows(records):
    from core.archive_research import projection, ORIGIN
    for r in records:
        briefs = ", ".join("%s No. %s" % (c["series_name"], c["issue"]) for c in r["cited_in"])
        yield projection(id="cited:" + r["id"], title=r["original_title"],
            original_title=r["original_title"], date=r["date"],
            date_kind="source-stated publication" if r["date"] else "Undated",
            desks=[], source=r["publisher"], issuer=r["issuer"],
            record_type="official_link",
            processing="Official-link metadata cited in " + briefs
                + "; this Record includes no source text or independent verification",
            ipr_url=ORIGIN + "/" + r["record_path"], source_url=r["url"],
            citation=citation(r, ORIGIN))
