"""Read-only HTML presentation of actually admitted regional official links.

This renderer never reads original headlines, bodies, translations or model
text. It never infers live status from a candidate packet or empty table.
A release producer must independently verify the DB and deployed HTML bytes.
"""
from __future__ import annotations

import html
import re
import sqlite3
from datetime import date
from urllib.parse import urlsplit

from core.crossdesk_official_metadata_candidates import FAMILIES, exact_source_url
from core.regional_official_link_release import (
    EXPECTED_TABLE_COLUMNS, TABLE, read_admitted_link_rows,
)

DESK_TO_FAMILY = {
    "philippines": "ph_afp_articles",
    "indonesia": "id_kemhan_news",
    "vietnam": "vn_mps_foreign_affairs_vi",
    "japan": "jp_mod_news_ja",
}
NEUTRAL_LABELS = {
    "ph_afp_articles": "AFP official source",
    "id_kemhan_news": "Kemhan Berita official source",
}
PUBLISHER_LABELS = {
    "ph_afp_articles": "Armed Forces of the Philippines",
    "id_kemhan_news": "Indonesian Ministry of Defense — Berita",
}
NSC_LABEL = "NSC official statement"
NSC_PUBLISHER_LABEL = "National Security Council"
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")


class RegionalRenderHold(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise RegionalRenderHold(reason)


def read_live_links(conn: sqlite3.Connection, desk: str):
    """Rows are drawn only from the production admission table, never shadow."""
    need(desk in DESK_TO_FAMILY, "not_a_supported_regional_live_desk")
    family = DESK_TO_FAMILY[desk]
    if desk == "japan":
        from core.japan_mod_official_links import read_public_links
        return read_public_links(conn)
    if desk == "vietnam":
        return _read_vietnam_links(conn)
    schema = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    need(schema == EXPECTED_TABLE_COLUMNS,
         "regional_source_index_unavailable_or_schema_drift")
    records = read_admitted_link_rows(conn, desk, family)
    need(len(records) <= 5000, "unexpectedly_large_source_index")
    unique_ids, unique_urls, result = set(), set(), []
    for r in records:
        (_, ident, url, day, issuer, publisher, republisher, git_sha,
         meta_sha, proof_sha, scope) = tuple(r)
        need(type(ident) is str and type(url) is str and
             type(day) is str and type(git_sha) is str and
             SHA40.fullmatch(git_sha) is not None and
             type(meta_sha) is str and SHA256.fullmatch(meta_sha) is not None and
             type(proof_sha) is str and SHA256.fullmatch(proof_sha) is not None and
             scope == "official_link_only" and
             issuer == FAMILIES[family]["issuer"] and
             publisher == FAMILIES[family]["publisher"] and
             republisher == FAMILIES[family]["republisher"],
             "published_reference_missing_authenticity")
        try:
            need(date.fromisoformat(day).isoformat() == day,
                 "noncanonical_publisher_date")
        except ValueError:
            raise RegionalRenderHold("invalid_publisher_date") from None
        # Recheck URI grammar at render-time. DB SQL checks alone do not fully
        # establish official HTTPS canonical URLs.
        exact_source_url(ident, url, day, family)
        need(ident not in unique_ids and url not in unique_urls,
             "duplicate_published_source_reference")
        unique_ids.add(ident); unique_urls.add(url)
        result.append({
            "source_identity": ident,
            "canonical_official_url": url,
            "publisher_posted_date": day,
            "label": NEUTRAL_LABELS[family],
            "publisher_label": PUBLISHER_LABELS[family],
        })
    if desk == "philippines":
        # NSC shares the Philippines desk under its own family and checks; it
        # never borrows AFP's issuer, labels or standing approval.
        result = sorted(result + _read_nsc_links(conn, unique_ids, unique_urls),
                        key=lambda r: r["source_identity"])
        result.sort(key=lambda r: r["publisher_posted_date"], reverse=True)
    return result


def _read_nsc_links(conn, unique_ids, unique_urls):
    from core.ph_nsc_official_link_admission import (
        FAMILY, PUBLISHER, canonical_permalink, load_policy,
    )
    records = read_admitted_link_rows(conn, "philippines", FAMILY)
    if not records:
        return []
    # A row admitted while a source-use hold stood is not a reason to show it.
    need(load_policy()["category_anomaly_resolved"] is True, "nsc_source_use_hold")
    result = []
    for (_, ident, url, day, issuer, publisher, republisher, git_sha,
         meta_sha, proof_sha, scope) in records:
        need(issuer is None and publisher == PUBLISHER and republisher is None
             and type(git_sha) is str and SHA40.fullmatch(git_sha) is not None
             and type(meta_sha) is str and SHA256.fullmatch(meta_sha) is not None
             and type(proof_sha) is str and SHA256.fullmatch(proof_sha) is not None
             and scope == "official_link_only",
             "published_reference_missing_authenticity")
        need(type(ident) is str and type(url) is str and type(day) is str
             and canonical_permalink(ident, url, day),
             "nsc_reference_not_canonical")
        need(ident not in unique_ids and url not in unique_urls,
             "duplicate_published_source_reference")
        unique_ids.add(ident); unique_urls.add(url)
        result.append({"source_identity": ident, "canonical_official_url": url,
                       "publisher_posted_date": day, "label": NSC_LABEL,
                       "publisher_label": NSC_PUBLISHER_LABEL})
    return result


def _read_vietnam_links(conn):
    from core.vietnam_official_link_admission import ISSUERS, LABELS, exact_url, HOLDS
    schema = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    need(schema == EXPECTED_TABLE_COLUMNS, "regional_source_index_unavailable_or_schema_drift")
    records = read_admitted_link_rows(conn, "vietnam")
    need(len(records) <= 5000, "unexpectedly_large_source_index")
    result = []
    for family, ident, url, day, issuer, publisher, republisher, commit, meta, proof, scope in records:
        if family == "vn_vpcp_official_documents_vi":
            # Independently validated below; it has a different formal issuer
            # and hosting publisher from the ministry-news families.
            continue
        need(family in ISSUERS and family not in HOLDS, "vietnam_source_rights_hold")
        need(issuer == publisher == ISSUERS[family] and republisher is None
             and type(commit) is str and SHA40.fullmatch(commit)
             and type(meta) is str and SHA256.fullmatch(meta)
             and type(proof) is str and SHA256.fullmatch(proof)
             and scope == "official_link_only", "published_reference_missing_authenticity")
        exact_url(family, ident, url)
        need(type(day) is str and date.fromisoformat(day).isoformat() == day,
             "invalid_publisher_date")
        result.append({"source_identity": ident, "canonical_official_url": url,
                       "publisher_posted_date": day, "label": LABELS[family],
                       "publisher_label": "Vietnam Ministry of Public Security"})
    from processing.government_document_intake import read_links
    return sorted(result + read_links(conn), key=lambda r: (r["publisher_posted_date"], r["source_identity"]), reverse=True)


def render_live_links(conn: sqlite3.Connection, desk: str) -> str:
    """Small accessible link-only desk rail for *admitted* production rows."""
    rows = read_live_links(conn, desk)
    if not rows:
        return ""
    label = {"philippines": "Philippines AFP and NSC", "indonesia": "Indonesia Kemhan",
             "vietnam": "Vietnam ministries", "japan": "Japan MOD"}[desk]
    lines = [
        '<section class="regional-official-source-links" '
        'data-source-scope="official-link-only" '
        'aria-label="%s official source references">' % html.escape(label, quote=True),
        '<h2>Verified official source references</h2>',
        '<p>Source URLs and publisher dates only; original articles are linked at '
        'their official websites.</p>',
        '<ul class="regional-source-reference-list">',
    ]
    for r in rows:
        url = html.escape(r["canonical_official_url"], quote=True)
        ident = html.escape(r["source_identity"], quote=True)
        day = html.escape(r["publisher_posted_date"], quote=True)
        safe_label = html.escape(r["label"], quote=True)
        date_kind = html.escape(r.get("date_kind", ""), quote=True)
        date_prefix = date_kind + " " if date_kind else ""
        lines.append(
            '<li data-official-source-id="%s"><a href="%s" rel="noopener noreferrer">'
            '%s</a> %s<time datetime="%s">%s</time></li>'
            % (ident, url, safe_label, date_prefix, day, day))
    lines += ["</ul>", "</section>"]
    return "\n".join(lines)

def load_admitted_links(db_path, desk: str):
    """Read admitted source metadata from SQLite, not unreviewed shadow state.

    Until the independently gated migration has actually landed, no table
    means no public source-index links. A PRESENT but broken/untrusted schema
    is a failure, never an excuse to substitute private candidate records.
    Scratch-copy reads avoid WAL sidecars beside the tracked production DB.
    """
    need(desk in DESK_TO_FAMILY, "not_a_supported_regional_live_desk")
    from scripts.reconcile_db import read_only
    with read_only(str(db_path)) as conn:
        present = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE,),
        ).fetchone()
        if present is None:
            return []
        return read_live_links(conn, desk)
