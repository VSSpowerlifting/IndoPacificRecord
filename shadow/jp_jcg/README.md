# Japan Coast Guard official English releases — isolated shadow pilot

**Status (October 8, 2026): the owner-dispatched shadow collector has archived
three official English HTML releases on isolated `shadow/japan-jcg` (Day 0
commit `81558026117067cbcf54bd7a7859a2d9db168a0c`). A guarded daily
qualification workflow exists but remains **OFF** unless the owner separately
sets `JCG_SHADOW_DAILY_ENABLED=true` after source review. Japan is not a
production desk, and these records do not yet feed the native AI writer.**

The Japan Coast Guard is a maritime law-enforcement authority, **not** the
Japanese Ministry of Defense or Joint Staff. Its English official press-release
index `https://www.kaiho.mlit.go.jp/e/topics_archive/index.html` is a distinct
source family from Japan MOD RSS. It supports maritime safety, law enforcement,
capacity building, and cooperation with foreign coast guards. It cannot stand
in for comprehensive Japanese defense-government coverage.

## Source access and policy

The named GitHub Actions client obtained actual original HTML articles and a
PDF from the host in the bounded October 8 access probe
[run #37816874786](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37816874786).
Robots.txt returned 404, meaning no rules file was published, not a 403
denial. There were no identity switches, cookies, proxies, retries, redirects,
challenge solvers, guessed URLs or third-party text mirrors.

The JCG's publisher content-use notice states ordinary government-created
website content is generally under Japan's Public Data License 1.0, subject to
attribution, edited-content disclosure and exclusions. This does not confer
rights over third-party photographs, logos or attachments. Formal source-use
review is still required before any permanent archival publication.

## Initial scope

Only the English original HTML press-release family, with source-stated dates
on or after **2026-09-01**, is within the initial pilot. Historical index rows
before September remain *counted as pre-scope rows*, not secretly presented as
collected. The parser demands paired index dates and first-party article URLs.

The adapter extracts only the HTML article body inside the publisher's
`section.topics.topics-article` / `div.topics-article__main.tich-text`.
Linked PDF text, images, and external resources are **not** included or
claimed to be archived. A publisher release available only as PDF or whose
HTML is merely a links page fails text-quality review rather than becoming
a fake full-text record. Subsequent optional PDF integration requires
separate extraction, content-boundary and reuse gates.

### Date integrity caveat observed in the real source

On October 8, the Actions adapter-fidelity proof found an October 6, 2026
release whose visible HTML `<time>` text said `06 October, 2026`, but whose
`datetime` attribute was `2021-3-1`. This appears to be stale publisher
template markup, not a valid source event date. It must **not** be silently
treated as valid machine-readable metadata. The adapter recognizes that one
observed constant as a flagged conflict, records the original attribute and
reason in each extracted record, and uses the visible published date **only
when it matches the independently rendered index date**. Any different or
unexplained `datetime` discrepancy is a failure. The reported condition
requires human review before production approval.

Every eligible captured record must include the original English title,
original body, official URL and publisher's article date, plus capture and
content SHA-256 digests. The schema never uses a repeating headline as identity.
The source is not a translation of Japanese MOD publications.

### Index cross-section row observed October 26, 2026

The read-only fidelity proof failed on every run from November 1, 2026
(last pass October 14) with `listing_failure` / "URL is not a JCG English
release identity". A single bounded diagnostic fetch of the English index on
November 2, 2026 (HTTP 200, no redirect, no challenge, `robots.txt` still
absent, publisher `Last-Modified: Mon, 26 Oct 2026 01:46:19 GMT`, capture
SHA-256 `0637653c82fe9b000423dc5caf8496e558f905de7d16e2f09a9ecfcfb9dbbdc5`)
showed 164 dated rows. 163 still link relative `article<digits>.html`
releases. The newest row, dated `26 10 2026`, links the absolute first-party
URL `https://www.kaiho.mlit.go.jp/info/topics/rescueforeignvessels.html`
(`target="_blank"`), titled "Rescue Operations Involving Foreign Vessels in
Waters Surrounding Japan （Update： October 26, 2026）". That is a standing
information page in a different publisher section, not a dated release in
the `topics_archive` family.

**Decision:** this is not a release URL-scheme change, not transient and not
an access block, so the release identity (`article<digits>.html` under
`/e/topics_archive/`, https, no query or fragment) is unchanged and the page
is **not** admitted. The listing parser now records an in-pilot-window row
that links a first-party page *outside* `/e/topics_archive/` as an
uncollected `outside_declared_url_family` row (exact URL and index date) in
the listing report, instead of failing the whole index. Rows inside the
archive directory that are not exact release identities, and any non-https or
off-host rows, still fail the listing as before. The body of the linked page
was not fetched; admitting that page family would need its own template,
scope and rights review.

## Proofs and next steps

- Offline source tests: `python -m unittest tests.test_japan_jcg_shadow_adapter`.
- Live read-only tests: `python -m scripts.probe_japan_jcg_adapter_live`.
  Fixed October 8 source window; no database, no original HTML/PDF persistence,
  no owner approval, no clock and no email.
- `enabled: true` is confined to the isolated shadow manifest. The manual
  collector and guarded daily schedule share an isolated state branch and
  concurrency lock; the daily job is default OFF pending explicit owner
  approval and a separate Actions repository variable.
- The production manifest loader reads only `desks/*/manifest.json`;
  this declaration remains under `shadow/`. The [read-only qualification
  report](../../docs/JAPAN_JCG_SHADOW_QUALIFICATION_STATUS.md) distinguishes
  actual collecting days from publication dates and backfills.

**Confirmed original Day 0:** GitHub Actions [run #37828199188](https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37828199188)
created the actual `shadow/japan-jcg` state branch on October 8, 2026.
The frozen Day 0 had three releases, zero fetch/extraction failures and
machine-integrity review with zero findings. Its publisher date-template
inconsistency and excluded original PDF companions still require independent
human review. Two older September sources have been independently verified
but have **not** been imported into the shadow state.
**Before production:** measure source-specific retrieval and extraction
continuity; complete the Day 7, 14 and 30 human reviews; fix date, charset,
attachment and omission issues; rehearse correction/promotion on a disposable
production database; obtain explicit owner signoff. The automated weekly AI
writer remains restricted to eligible production records.
