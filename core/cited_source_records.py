"""Official originals cited by approved Briefs, admitted as link-metadata Records.

An approved Brief already publishes each publisher reference's URL, publisher,
issuer, date, language and original title. This module turns the *official*
ones into IPR Records that publish exactly that metadata and nothing more: no
source text, no excerpt, no verification notes, no desk coverage. Every
citing Brief links to the Record and the Record links back to every Brief.

One Record per exact source URL. A URL already held as a corpus record or a
released machine explanation resolves to that page instead of a new one, so
manual citation and automated collection converge on one identity.

The rights gate fails closed. Independent reporting stays an external
citation. A source family whose title display or linking is held (MINDEF
outside its two approved links; the Vietnam MPS, MOIT and VPCP families
without a sealed decision) is omitted from Records, while the Brief's own
publisher reference is left exactly as approved.
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from core import vietnam_source_use
from core.mindef_permissions import MINDEF_SOURCE_SLUG, source_link_approved

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


def cited_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def cited_path(url: str) -> str:
    return "%s/cited-%s.html" % (ROUTE_DIR, cited_id(url))


def omission(ref: dict):
    """Why a publisher reference cannot become a Record; None when it can."""
    if ref.get("independence") != "official":
        return "independent_reference"
    url = ref.get("url")
    parts = urlsplit(url) if isinstance(url, str) else None
    if (not parts or parts.scheme != "https" or not parts.hostname
            or parts.username or parts.password or url != url.strip()):
        return "unsafe_url"
    host = parts.hostname.lower()
    if host in MINDEF_HOSTS and not source_link_approved(MINDEF_SOURCE_SLUG, url):
        return "mindef_link_not_approved"
    family = HELD_HOSTS.get(host)
    if family and not vietnam_source_use.standing(family).allows("public_title_display"):
        return "held_source_family:" + family
    if not all(isinstance(ref.get(k), str) and ref[k].strip()
               for k in ("publisher", "issuer", "original_title", "lang")):
        return "incomplete_metadata"
    return None


def resolve(collection, *, corpus_by_url=None, machine_by_url=None):
    """Admit approved Briefs' official citations.

    Returns `(records, brief_links, omitted)`:

    * records: one dict per new cited Record, newest source date first;
    * brief_links: {brief slug: {reference id: site-relative route}};
    * omitted: (slug, reference id, url, reason) for every reference left
      as an external citation only.

    Corpus records that a Brief cites gain a `brief_reference` entry in their
    own `in_trails`, so their page links back without a second Record.
    """
    corpus_by_url = corpus_by_url or {}
    machine_by_url = machine_by_url or {}
    by_url, brief_links, omitted = {}, {}, []
    for brief in collection.briefs:
        if brief.get("is_review"):
            continue
        sidecar = collection.sidecars[brief["slug"]]
        if sidecar.get("synthetic"):
            continue
        links = {}
        for ref in sidecar.get("publisher_references") or []:
            reason = omission(ref)
            if reason:
                omitted.append((brief["slug"], ref.get("id"), ref.get("url"), reason))
                continue
            url = ref["url"]
            citing = {"slug": brief["slug"], "issue": brief["issue"],
                      "date": brief["date"], "title": brief["title"],
                      "url": brief["url"], "series_name": brief["series_name"],
                      "publication": brief.get("publication"),
                      "kind": "brief_reference", "anchor": "publisher-" + ref["id"]}
            if url in corpus_by_url:
                rec = corpus_by_url[url]
                trails = rec.setdefault("in_trails", [])
                if not any(t["slug"] == brief["slug"] and t.get("kind") == "brief_reference"
                           for t in trails):
                    trails.append(citing)
                links[ref["id"]] = "%s/%d.html" % (ROUTE_DIR, rec["id"])
                continue
            if url in machine_by_url:
                links[ref["id"]] = machine_by_url[url]["record_path"]
                continue
            record = by_url.get(url)
            if record is None:
                record = by_url[url] = dict({k: ref[k] for k in FIELDS},
                    id=cited_id(url), record_path=cited_path(url),
                    cited_only=True, cited_in=[])
            elif any(record[k] != ref[k] for k in ("date", "original_title", "issuer")):
                # Two Briefs describing one URL differently is an editorial
                # discrepancy to resolve, never one to paper over silently.
                raise ValueError("cited_source_metadata_conflict: %s" % url)
            if not any(c["slug"] == brief["slug"] for c in record["cited_in"]):
                record["cited_in"].append(citing)
            links[ref["id"]] = record["record_path"]
        if links:
            brief_links[brief["slug"]] = links
    records = sorted(by_url.values(), key=lambda r: (r["date"] or "", r["url"]), reverse=True)
    return records, brief_links, omitted


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
