"""Verify exact reviewed external Japan references before country-page release.

This is a public-presentation contract, never an original-body admission gate.
It inspects generated HTML, so a template-only green test cannot authorize a
release that accidentally omits an approved source link.

Two rendered sections are outside the static human-reviewed link list and are
reconciled separately against the tracked SQLite instead (never skipped):

* ``section.regional-official-live-links`` -- MOD news official-link metadata,
  verified by ``scripts.verify_japan_mod_official_links``.
* ``section[data-japan-machine-explanations]`` -- shared-Daily machine
  explanations of Japan Coast Guard English releases. Every entry must be a
  released ``jp_jcg_press_en`` machine record whose ``japan_jcg_source_records``
  parent is admitted ``official_link_only`` with the same source binding, and
  its single "Official source" link must be that parent's canonical URL.

Standard library only: the release workflow runs these tests before it
installs the render dependencies.
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


JCG_PREFIX = "https://www.kaiho.mlit.go.jp/e/topics_archive/article"
MOD_PREFIX = "https://www.mod.go.jp/j/press/news/2026/"
JCG_LINKS = tuple(JCG_PREFIX + str(n) + ".html" for n in
                  (9399, 9424, 9436, 9453, 9455, 9465))
MOD_LINKS = tuple(MOD_PREFIX + name for name in
                  ("08/27b.pdf", "08/28a.pdf", "08/28b.pdf",
                   "08/28f.pdf", "09/17a.pdf", "09/29d.pdf", "10/05b.pdf"))
REVIEWED_LINKS = frozenset(JCG_LINKS + MOD_LINKS)
REQUIRED_TEXT = (
    "Six official Japan Coast Guard publication links",
    "Seven official Japan Ministry of Defense PDF links",
    "external official-source links only",
    "not production IPR records",
    "All Japan production records remain held",
    "Japan remains shadow-only; no production or model use is authorized",
    "repository gate was observed unset or unavailable",
    "Visual original review only: no extractable PDF text layer",
    "No extractable text layer; not eight independent archive originals",
    "The oversized October 2 original remains intentionally excluded.",
)

LIVE_SECTION_CLASS = "regional-official-live-links"
MACHINE_SECTION_ATTR = "data-japan-machine-explanations"
MACHINE_ENTRY_ATTR = "data-machine-source"
MACHINE_FAMILY = "jp_jcg_press_en"
MACHINE_ISSUER = "jp_coast_guard"
# The desk template renders ``daily_machine_records[:5]``.
MACHINE_DISPLAY_LIMIT = 5
MACHINE_LINK_TEXT = "Official source"
# Inside the machine section any link to these official hosts counts, whatever
# its path, query or fragment: the narrow static-list prefix match is not
# enough to prove no unreconciled official link is present there.
OFFICIAL_HOSTS = ("kaiho.mlit.go.jp", "mod.go.jp")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "pla_watch.db"


def _official_host(href: str) -> bool:
    try:
        host = (urlsplit(href.strip()).hostname or "").lower()
    except ValueError:
        return True  # An unparseable link inside the section is never accepted.
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def _static_official(href: str) -> bool:
    return ((href.startswith(JCG_PREFIX) and href.endswith(".html"))
            or (href.startswith(MOD_PREFIX) and href.endswith(".pdf")))


class _JapanLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.official_links = []
        self.live_section_depth = 0
        self.has_live_feed = False
        self.machine_section_depth = 0
        self.machine_sections = 0
        self.machine_entries = []   # [{"id": str, "links": [[href, rel, text]]}]
        self.machine_errors = []
        self._li_depth = 0
        self._entry = None
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "section":
            is_live = LIVE_SECTION_CLASS in (d.get("class") or "").split()
            is_machine = MACHINE_SECTION_ATTR in d
            if is_machine and self.live_section_depth:
                self.machine_errors.append(
                    "Japan machine section nested inside the live-links section")
            if is_live and self.machine_section_depth:
                self.machine_errors.append(
                    "Japan live-links section nested inside the machine section")
            if self.machine_section_depth or is_machine:
                if is_machine:
                    self.machine_sections += 1
                self.machine_section_depth += 1
            elif self.live_section_depth or is_live:
                self.live_section_depth += 1
                self.has_live_feed = True
        if self.machine_section_depth:
            self._machine_starttag(tag, d)
            return  # Separately reconciled against admitted SQLite, below.
        if self.live_section_depth:
            return  # Separately reconciled against admitted SQLite, below.
        if tag != "a":
            return
        href = d.get("href") or ""
        if _static_official(href):
            self.official_links.append((href, set((d.get("rel") or "").split())))

    def _machine_starttag(self, tag, d):
        if tag == "li":
            if MACHINE_ENTRY_ATTR in d:
                ident = (d.get(MACHINE_ENTRY_ATTR) or "").strip()
                if self._li_depth:
                    self.machine_errors.append(
                        "Japan machine entry nested inside another list item: " + ident)
                elif not ident:
                    self.machine_errors.append("Japan machine entry without a source identity")
                else:
                    self._entry = {"id": ident, "links": []}
                    self.machine_entries.append(self._entry)
            self._li_depth += 1
            return
        if tag != "a":
            return
        href = d.get("href") or ""
        if not _official_host(href):
            return
        if self._entry is None:
            self.machine_errors.append(
                "Official Japan link outside a machine entry in the machine section: " + href)
            return
        self._anchor = [href, set((d.get("rel") or "").split()), ""]
        self._entry["links"].append(self._anchor)

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor[2] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._anchor = None
        if self.machine_section_depth and tag == "li" and self._li_depth:
            self._li_depth -= 1
            if not self._li_depth:
                self._entry = None
        if tag == "section":
            if self.machine_section_depth:
                self.machine_section_depth -= 1
                if not self.machine_section_depth:
                    self._li_depth, self._entry, self._anchor = 0, None, None
            elif self.live_section_depth:
                self.live_section_depth -= 1


def admitted_jcg_machine_records(db) -> list:
    """Released JCG machine records with an admitted link-only parent.

    Ordered as the renderer orders them (official date, then identity, newest
    first). The parent must carry the same version, text and page hashes the
    record was made from, which is the renderer's own source binding.
    """
    uri = Path(db).resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"daily_machine_records", "japan_jcg_source_records"} <= tables:
            return []
        rows = conn.execute(
            "SELECT d.source_identity, j.canonical_official_url, j.publisher_posted_date "
            "FROM daily_machine_records d JOIN japan_jcg_source_records j "
            "ON j.source_identity = d.source_identity "
            "WHERE d.source_family = ? AND d.publication_state = 'released' "
            "AND j.public_scope = 'official_link_only' AND j.official_issuer = ? "
            "AND j.metadata_version_sha256 = d.metadata_version_sha256 "
            "AND j.content_sha256 = d.content_sha256 "
            "AND j.capture_sha256 = d.capture_sha256",
            (MACHINE_FAMILY, MACHINE_ISSUER)).fetchall()
    finally:
        conn.close()
    return sorted(({"source_identity": r[0], "canonical_official_url": r[1],
                    "publisher_posted_date": r[2]} for r in rows),
                  key=lambda r: (r["publisher_posted_date"], r["source_identity"]),
                  reverse=True)


def _reconcile_machine_section(p, admitted) -> list:
    errors = list(p.machine_errors)
    if p.machine_sections > 1:
        errors.append("Expected at most one Japan machine section; found "
                      + str(p.machine_sections))
    by_id = {r["source_identity"]: r for r in admitted}
    ids = [e["id"] for e in p.machine_entries]
    for ident, n in sorted(Counter(ids).items()):
        if n > 1:
            errors.append("Duplicate Japan machine entry: " + ident + " (" + str(n) + ")")
    expected = admitted[:MACHINE_DISPLAY_LIMIT]
    if len(ids) != len(expected):
        errors.append("Japan machine entries: expected " + str(len(expected))
                      + " (min(" + str(MACHINE_DISPLAY_LIMIT) + ", " + str(len(admitted))
                      + " admitted released JCG records)); found " + str(len(ids)))
    if p.machine_sections and not ids:
        errors.append("Japan machine section rendered without any entry")
    for entry in p.machine_entries:
        ident, parent = entry["id"], by_id.get(entry["id"])
        if parent is None:
            errors.append("Unadmitted or held Japan machine record in machine section: " + ident)
            continue
        links = entry["links"]
        if len(links) != 1:
            errors.append("Japan machine entry " + ident + ": expected exactly one official "
                          "link; found " + str(len(links)))
            continue
        href, rel, text = links[0]
        if href != parent["canonical_official_url"]:
            errors.append("Japan machine entry " + ident + ": official link " + href
                          + " differs from admitted canonical "
                          + parent["canonical_official_url"])
        if not {"noopener", "noreferrer"} <= rel:
            errors.append("Missing external-link protection: " + href)
        if " ".join(text.split()) != MACHINE_LINK_TEXT:
            errors.append("Japan machine entry " + ident + ": official link text is not '"
                          + MACHINE_LINK_TEXT + "'")
    if not errors and ids != [r["source_identity"] for r in expected]:
        errors.append("Japan machine entries are not the latest admitted records in "
                      "renderer order: " + ", ".join(ids))
    return errors


def _validate(html: str, db=None):
    errors = []
    p = _JapanLinks()
    p.feed(html)
    p.close()
    counts = Counter(url for url, _ in p.official_links)
    for url in sorted(REVIEWED_LINKS):
        if counts[url] != 1:
            errors.append("Expected exactly one link for " + url
                          + "; found " + str(counts[url]))
    for url in sorted(set(counts) - REVIEWED_LINKS):
        errors.append("Unreviewed official Japan link: " + url)
    for url, rel in p.official_links:
        if not {"noopener", "noreferrer"} <= rel:
            errors.append("Missing external-link protection: " + url)
    for phrase in REQUIRED_TEXT:
        if p.has_live_feed:
            phrase = {
                "All Japan production records remain held": "Japan original-text production records remain held",
                "Japan remains shadow-only; no production or model use is authorized":
                    "The news-feed official-link metadata service is separate; original-text and model use remain held",
            }.get(phrase, phrase)
        if phrase not in html:
            errors.append("Missing Japan release qualification: " + phrase)
    for forbidden in ("state/shadow.db", "text_original", "body_original",
                      'href="archive.html?desk=japan"', "data-reference-list"):
        if forbidden in html:
            errors.append("Japan shadow corpus boundary violated: " + forbidden)
    if db is not None:
        errors.extend(_reconcile_machine_section(p, admitted_jcg_machine_records(db)))
    elif p.machine_sections or p.machine_entries or p.machine_errors:
        errors.append("Japan machine section requires SQLite reconciliation; no database given")
    return errors, len(p.machine_entries)


def validate_japan_release_html(html: str, db=None) -> list[str]:
    """Errors for a rendered Japan page; ``db`` reconciles the machine section.

    Without ``db`` a page carrying the machine section is always blocked, so the
    section can never pass merely by being excluded from the static count.
    """
    return _validate(html, db)[0]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--page", type=Path, default=Path("output/japan.html"))
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args(argv)
    machine = 0
    try:
        html = args.page.read_text(encoding="utf-8")
        if not args.db.is_file():
            raise ValueError("Japan release database not found: " + str(args.db))
        errors, machine = _validate(html, args.db)
        if not errors and LIVE_SECTION_CLASS in html:
            from scripts.verify_japan_mod_official_links import verify
            verify(args.db, args.page)
    except (OSError, UnicodeDecodeError, ValueError, sqlite3.Error) as exc:
        errors = [str(exc)]
    for error in errors:
        print("BLOCKED: " + error)
    if errors:
        return 1
    print("Japan release: 6 JCG + 7 MOD original links, " + str(machine)
          + " admitted JCG machine explanation link(s), boundaries and qualifications verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
