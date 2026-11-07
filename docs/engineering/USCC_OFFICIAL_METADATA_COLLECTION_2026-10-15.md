# USCC first-party official metadata collection — October 15, 2026

## Source and identity
The [U.S.-China Economic and Security Review Commission](https://www.uscc.gov/) is a **U.S. legislative-branch commission**, not U.S. Pacific Command, a military service, the Defense Department or an independent verification of its own assessments.

Its [first-party press-release listing](https://www.uscc.gov/press-releases) publishes dated announcements on China–U.S. security, technology, economics and Indo-Pacific policy. Examples displayed as of October 15, 2026 include the September 22 report announcement on threats to trans-Pacific undersea cables and a September 21 announcement of research on China–Russia military cooperation.

At 20:05 UTC October 15, a bounded GitHub Actions runner **actually fetched a readable robots policy permitting `/press-releases`**, and received the publisher's own listing HTML. In the same run, the distinct U.S. Seventh Fleet and Pacific Fleet hosts returned HTTP 403 for their robots files and were not fetched further. This independent permitted USCC host is the first eligible technical access path for a new U.S. family; it is **not** a workaround host for either Navy command.

## What is collected

`scripts/collect_uscc_press_metadata.py` reads the official `robots.txt` for a declared IPR user agent each attempt and contacts precisely the **one listing** if policy permits it. No navigation to individual article bodies, no pagination/backfill, no search, no tags, no proxies, redirects, retries, alternate identity or challenge-solving.

It extracts a bounded (1–75) set of dated first-party link **cards**. Each must provide a stable official `/press-releases/<slug>` URL, a valid independently associated `MM/DD/YYYY` (or `YYYY-MM-DD`) listing date, a unique identity, an authenticated official publisher host and exact fixed issuer. Missing dates, fabricated IDs, conflicting duplicate values, future-dated rows, changed layouts, disallowed robots or unavailable access produce a HOLD. Only these six fields are stored per row:

- `source_identity`, `canonical_official_url`, `publisher_posted_date`;
- `official_issuer`, `official_publisher`, `publisher_listing_url`.

The collection receipt additionally hashes the whole ephemeral listing HTML (`official_listing_sha256`), dates the genuine UTC observation, preserves the count of *visible dated listing cards*, and explicitly disclaims complete coverage, original content retention, publication, data-model approval or production admission. **The HTML itself, headlines, articles, photographs, documents, excerpts, translations, summaries and analysis are NOT copied.** A listing digest does not restore those original bytes if the government removes them.

## Genuine scheduled evidence
The minimal append-only public `shadow/uscc-press` branch contains only the scoped README and `observations/YYYY-MM-DD.json` metadata receipts. Scheduled collector calls run daily at 11:20 UTC; manual dispatch requires `owner_authorized_source_collection=true`. The workflow runs positive and negative synthetic tests, validates source access before any Git mutation, then writes **only** an observed UTC date's metadata JSON, refusing different bytes for an existing date and never force-pushing. It does not merge to `main`, modify `pla_watch.db`, touch public Pages or count a source success based solely on a green CI test.

The first actual post-merge run is the first possible remote collecting day and must be inspected for valid collection, observed rows, exact state-branch Git ref and no failed policy fetch. Passing one source-observation run doesn't establish complete listing history or every-day reliability. Scheduled gaps remain gaps.

## Next release boundary
When genuine observation history exists, build an **idempotent USCC source metadata importer**, separate from the command-derived PACOM static links, into a typed production-only metadata table. The owner's narrow standing principle of verified URL/date/issuer-only publication can then govern a separately tested U.S. congressional commission release path; any source-specific extensions require review. A guarded publisher should read only admitted official metadata and publish **only** `us-indopacific.html` after exact source-version and collision checks. Never silently classify USCC announcements as PACOM orders or count them as IPR-authored analysis.

The public U.S. Desk's existing nine PACOM official outbound URLs and the factual `access_blocked` status of direct PACOM collection must remain intact during USCC activation.

## Current decision — 3 November 2026

The founder accepted the exact July 18/July 25 **unquoted narrative** source-use
assessment and proposed attributed factual-note scope of at most 90 words per
release, including disclosed drafting uncertainty. See the authoritative
[decision record](../../DECISION_LOG.md#2026-11-03--owner-exact-two-uscc-narrative-source-use-assessment-accepted)
for exact versions, quotation/third-party exclusions and all operational holds.
Unsigned drafting alone does not require a named employee or a blanket hold.
No model transmission, spending, implementation, recurring collection,
activation or publication is authorized. June 25 remains outside this decision.
Earlier assessments below are dated evidence; this decision supersedes their
blanket July source-use holds, not their custody findings or operational limits.

## Original-backed family qualification — 3 November 2026

**Initial assessment below; bounded capture findings and the updated next decision
are recorded in the follow-up section at the end of this document.**

**Recommendation: retain USCC as the selected candidate; defer original-backed
implementation and activation.** Listing access and stable dated identities are
confirmed. Complete original retrieval, private custody, authorship clearance,
external commercial model input and source-grounded explanation quality are
**not qualified**. This is a source-specific research finding, not a grant,
activation instruction or desk-completion claim. The October metadata-only
contract above remains unchanged.

### Scope, repository and ownership

This phase implements §3.8 of the
[eight-desk plan](../desks/EIGHT_DESK_OPERATIONAL_COMPLETION_PLAN.md#38-us-reference--one-qualifying-family-uscc-first).
Public main advanced from the supplied `9095590fa30baccbbaca4bb4f7c312e5591cabba`
to `e6ad526d85929622dbb880844295cc70ec95ad67`; this isolated worktree's
`codex/uscc-original-qualification` branch starts at the latter. GitHub inspection
confirmed #950 open at `4e6c2773e02e5db11b6909d8c97ae6c84c8c9717`, #953 draft/open
at `27851ea1b20a90091d66e5b94da192fd1c922ae8` and stacked on #950, and #943
draft/open at `8e0cc1798e968fd7888f352890ced9ae1b15f7e2`. These are observation
pins, not merge or CI findings. Open-PR changed-file inspection found no competing
USCC-document edit. #736 and #895 own overlapping U.S./shared presentation work;
none of their files is changed here. No migration-map edit competes with #950/#953.

The private companion's main was `a3f6299bd783b9624d0754707572dbb89abdd860`.
Its README confirms the owner-selected private GitHub archive and expressly
separates storage from reuse rights. That README's nine-source frozen inventory
does not include USCC. This is not an exhaustive private-branch inventory or
proof that no private grant exists. No private originals were fetched, and no
private files or refs were changed. No USCC original-use grant was established
in the inspected public decisions, USCC documents or private README.

### Primary evidence and limits

| Finding | Primary reference / exact locator | Status and limitation, checked 3 November 2026 |
|---|---|---|
| Publisher is a legislative-branch commission with both staff and contracted research | [USCC privacy page](https://www.uscc.gov/privacy), institutional navigation and Privacy section | Directly documented institutional statement; government hosting does not prove individual authorship |
| Current robots policy permits the press-release paths under its wildcard group | [robots.txt](https://www.uscc.gov/robots.txt) | Direct local HTTP 200, `text/plain; charset=UTF-8`, at 22:06:27 UTC; SHA-256 `8e8cb58d810473a52cce903be5ffb73d948eef981bbd101cffbf8dc2c02fcf4e`. No press-release-path disallow or crawl-delay observed; not a content licence |
| Existing declared-client listing collection works | [official listing](https://www.uscc.gov/press-releases); `scripts/collect_uscc_press_metadata.py:collect` | Local collection begun 22:07:42 UTC returned ten dated rows; listing SHA-256 `cf65412b371d477b9660a5b65edc65c76e0b08870e554e4d31212bde1db9b72c`. This is a listing hash, never an original/version hash |
| Privacy policy governs visitor information | [Privacy](https://www.uscc.gov/privacy), Privacy section | No express original-retention, model-input or republication grant in that section. No comprehensive site-wide reuse terms were established; absence of a notice is not permission |
| Government-work copyright rule is conditional on actual authorship | [Copyright Office, Title 17 chapter 1](https://www.copyright.gov/title17/92chap1.html), §§101 and 105(a) | Official-duty works of federal officers/employees lack protection under this title; government can also hold transferred copyrights. Contracted authorship is not automatically covered. This statutory basis is not a publisher grant or worldwide clearance |
| IPR authority currently covers metadata | [USCC admission decision](USCC_LIVE_OFFICIAL_METADATA_ADMISSION_2026-10-15.md), Standing approval bullet; [scope decision](../../DECISION_LOG.md), 2 November eight-desk entry | URL/date/issuer authority does not authorize originals, external model input or substantive output; the eight-desk selection adds no such authority |

The robots-only request used the descriptive agent
`IndoPacificRecord/1.0 (source qualification; policy only)`; the actual collector
then independently fetched robots and the listing using the existing
`IndoPacificRecordResearchBot/1.0 (+https://indopacificrecord.org/about.html)`.
It uses bounded reads and rejects redirects. No browser impersonation, proxy,
challenge-solving or publisher contact occurred. This local result does not
prove current GitHub-runner access to individual release pages. Web research
returned rendered listing material and an indexed release excerpt; neither is
an authenticated retained original or a fidelity test. No release-body HTTP
probe, PDF/media download, original fixture or private original capture was
made in this phase. The listing bytes were ephemeral, as in the existing contract.

### Representative identities and authorship boundary

Dates below are **listing publication dates**, not verified event dates or
original-page modification dates. For every linked slug, the existing identity
is `uscc-press:<slug>`; preserve it rather than minting another publication
because an explanation component is later allowed.

| Official release URL | Listing date | Qualification role |
|---|---|---|
| [Commission returns from China](https://www.uscc.gov/press-releases/press-release-us-china-commission-returns-fact-finding-trip-china) | 2026-07-25 | Strong candidate for Commission-origin institutional prose; confirm authorship and complete original before accepting |
| [Commission departs for China](https://www.uscc.gov/press-releases/press-release-us-china-commission-departs-fact-finding-trip-china) | 2026-07-18 | Separate publication, not a revision of the return announcement |
| [AI glossary announcement](https://www.uscc.gov/press-releases/press-release-plain-english-guide-ai-tech-stack) | 2026-06-25 | Candidate Commission announcement; linked glossary is a separate work/version |
| [Undersea-cable report announcement](https://www.uscc.gov/press-releases/press-release-new-report-chinas-gray-zone-threats-trans-pacific-undersea-cables) | 2026-09-22 | Listing identifies China Strategic Risks Institute as contracted report author; release and study require separate authorship determinations |
| [Dalai Lama succession report announcement](https://www.uscc.gov/press-releases/press-release-dalai-lamas-succession-geopolitical-implications-and-policy) | 2026-08-26 | Listing identifies Michael Schiffer / Sankhara Strategies, LLC as contracted report author; do not ingest that study through release permission |

The announcement of a third-party study may itself be Commission-authored, but
its location and issuer label alone do not establish that. Admit only verified
Commission-written release prose; exclude linked research, testimony, third-party
quotations requiring separate clearance, photographs, logos, charts and attachments.
Hold ambiguous authorship rather than declaring the whole press section public
domain. Describe a release's statements as USCC's announcements or assessments;
do not convert them into independently confirmed findings or military orders.

**Original completeness/version result: unresolved.** The current collector
never visits these detail URLs. It cannot establish complete paragraphs,
closing text, attachment-only releases, canonical tags, detail/listing date
agreement, correction history or raw-body hashes. A search excerpt cannot fill
those gaps. There is no authenticated USCC body version from this qualification,
no demonstrated historic revision chain and no tested English explanation.
After capture is authorized, compare complete main release text to the served
page, record retrieval time/final URL/status, canonical and displayed date,
raw capture SHA-256, extracted-text hash and extractor version. Preserve each
changed original and prior accepted output; do not overwrite by slug or treat
changing navigation bytes alone as a substantive revision. Unavailable or
incomplete originals must remain holds, never reconstructed from listing teasers.

### Authority by intended use

| Use | Publisher/legal basis established here | IPR owner authority / disposition |
|---|---|---|
| Existing bounded listing retrieval and official metadata | Readable robots and authentic listing; no general reuse licence inferred | Existing metadata-only authority; preserve current operation |
| Direct release retrieval and private original retention | Potential §105 basis only for verified official-duty prose; actual per-release authorship and any exceptions unresolved | No extension established; do not capture/retain originals yet |
| Transmission to an external commercial model | No express USCC model grant found; verified government-work status could supply a basis without a bespoke grant, subject to actual content, jurisdiction and provider handling | Not authorized by metadata grant; provider/use/retention and spend limits require an explicit applicable decision |
| Public independently worded English explanation | Potentially supportable from cleared release facts; not permission to copy linked studies or imply endorsement | No substantive-output activation; public originals are not necessary for a permitted explanation |
| Collection, processing and publication activation | Publisher access or a copyright basis does not activate IPR | Separate founder authority; nothing enabled here |

Do not require publisher correspondence merely because an express AI licence is
absent if documented official-duty authorship and applicable law adequately
support the intended uses. Conversely, founder acceptance cannot grant rights
owned by third parties. Any needed contact remains separately unauthorized.

### Smallest later implementation, after the decision

- Keep `scripts/collect_uscc_press_metadata.py` and
  `core/uscc_official_metadata.py` as the bounded discovery/metadata contract.
  They are not original collectors or body-admission APIs. Do not add bodies to
  public `shadow/uscc-press` receipts or the existing metadata tables.
- Add only a source-specific official release fetch/extract/authorship adapter
  using the existing source-adapter and private capture/history pattern
  (`scraper/sources/ph_afp.py`, `core/ph_afp_release_validator.py` as examples,
  not AFP rights or URL rules). Private custody must use the assigned evidence
  repository with immutable captures, version hashes and authenticated readback.
  A USCC custody ref and validator do not exist in the inspected shared source
  definitions; they require actual integration, not a claim of ready support.
- Extend `core/daily_sources.py` and `processing/screening.py` with an explicit
  USCC English source/profile and grounded institutional-attribution checks.
  Reuse `Analyzer.analyze_record` / `analyze_desk` in `analysis/analyzer.py`;
  English needs no translation. Never inherit China or Singapore permissions,
  rubrics, activation or spend. Existing `processing/daily_intake.py` owns
  versioned state, bounded attempts, signing and admission; its
  `english_official_quality` is a starting point for factual checks, not proof
  that USCC prose already passes them.
- Bind existing metadata identity to the permitted explanation through the
  common source/component interface, `core/daily_machine_records.py` and the
  actual governed dispatcher after coordinating #950/#953. Current metadata
  binding is source/table-specific and needs an explicit USCC adaptation;
  merely registering a name will not connect custody to admission. Keep the
  existing renderer/public writer. No second U.S. engine, queue or publisher.
- `core/source_publication_contract.py` and `storage/evidence_custody.py` label
  themselves synthetic-only prototypes/rehearsals. They are **not** a deployed
  USCC path and must not be presented as production-ready custody/admission.

### Exact next decision and stop

Founder: decide whether to authorize a **bounded, non-production original
qualification** of the three Commission-institutional candidates above (July
18, July 25 and June 25), with direct robots-respecting HTML retrieval, private
capture retention/readback and manual authorship/completeness/version checks,
excluding all linked works and media. Record the applicable statutory/permission
basis and any jurisdiction or third-party uncertainty in the existing decision
mechanism. This proposed decision is **not adopted by this document**.

Before any external model test or public explanation is permitted, separately
identify the approved provider/data handling, permitted input/output components,
per-run spend/retry limits and accountable owner. No paid test, schedule,
production admission or release follows from a capture-only decision. If the
three originals cannot be cleared, record that precise exception for founder
selection; do not substitute another source automatically.

The next authorized qualification should prove full originals and byte/text
version bindings, changed-source replay and no-op/failure recovery, then test
short attributed English explanations only within actual model authority.
Source-specific tests must reject contractor studies, missing/truncated bodies,
misbound dates/identities, forbidden public fields and unauthorized model calls.
Success later requires the real shared caller and appropriate source-to-reader
verification; this documentation phase stops at the unresolved decision above.

### Verification of this documentation phase

The three existing USCC suites (`test_uscc_press_metadata`,
`test_uscc_official_metadata_admission`, `test_uscc_public_production_links`)
passed: **10 tests** using the existing repository Python 3.9 environment.
The system `python3` lacked BeautifulSoup; no dependency was installed or changed.
Local Markdown file targets and `git diff --check` passed. No executable
contract, generated output, production data, workflow, registry or source-use
policy changed. These tests protect the existing metadata behavior; they do
not establish original completeness, rights, model quality, CI or live delivery.

## Authorized three-release capture follow-up — 3 November 2026

**Result: all three qualify for bounded private retrieval/custody and served-body
structural fidelity. The July unquoted narrative scope is now accepted under
the decision above; June and excluded/broader uses remain HELD.** This closes
the original-access/custody evidence gap for these exact observations, not the
family's processing/publication or recurring-operation qualification.

### Authority checked before retrieval

The founder's follow-up in the #973 task authorizes these three release HTML
pages, private capture/readback, authorship/completeness/identity/date/version
checks, and an update to #973. It withholds external model transmission, paid
processing, activation, public explanations, contact, merge and deployment.
This supersedes the earlier **owner capture-authorization** gap only; it grants
no third-party rights. No runtime policy or source-use grant was changed.

Public decisions/configuration/USCC documentation and private main
`a3f6299bd783b9624d0754707572dbb89abdd860` (AGENTS, CLAUDE, README, docs,
manifests and config), private issue bodies and branch names were checked.
No additional USCC original-use grant was found in that inspected scope. #950
and #953 remained open at the heads recorded above; no shared files are touched.
The public isolated branch remained at `5ee650e9c4` before this follow-up.

For **each** release, bounded private research retrieval/retention rests on the
recorded [§107 assessment](https://www.copyright.gov/title17/92chap1.html#107):
authorship/integrity examination without distribution or model use; published
factual institutional communication; complete HTML necessary for boundary and
byte verification, limited to three pages; restricted evidence offering no
public substitute. Possible future commercial use is not treated as a nonprofit
exemption. This is a reasoned limited-use assessment, not publisher permission,
a judicial ruling or worldwide clearance. The possible §105 official-duty basis
remains distinct and unresolved for broader uses. Full pre-request reasoning is
in the private `AUTHORITY.md` linked below. Retention is for this qualification's
evidence, not an activated or general-purpose corpus; preserve it pending the
next source-use decision under existing evidence rules.

### Exact private evidence and readback

Private source evidence, never to be merged into public or private main:
[`archive/uscc-qualification-20261103`, commit `9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab`](https://github.com/VSSpowerlifting/ipr-source-evidence-private/tree/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab).

- [Pre-request authority/retention assessment](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab/qualification/2026-11-03/AUTHORITY.md)
- [Per-release findings and limitations](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab/qualification/2026-11-03/REPORT.md)
- [Request ledger: exact URLs, response headers and UTC clocks](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab/ledger/uscc-qualification-20261103-1.json)
- [Body/date/authorship indicators and hashes](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab/qualification/2026-11-03/results.json)
- [File manifest](https://github.com/VSSpowerlifting/ipr-source-evidence-private/blob/9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab/manifest.json): SHA-256 `4b7bae838f62e7c9f3043305be0551a81caa4b6eaeeb22e0dc5df122d0ca8f2d`.

The existing declared-agent/NoRedirect transport and private shadow custody
layout were reused: SHA-addressed `captures/*.bin`, `ledger/*.json`, normalized
original text and native private Git. One-time acquisition and offline replay
scripts remain only with the essential private qualification evidence; no
production adapter or new custody service was added. Authenticated API confirmed
repository ID `1420273320` is private before writing. A separate authenticated
clone of the new private archive ref matched all **24 reachable Git objects**
using `scripts/verify_private_github_ref_parity.py`; all 16 manifest entries
rehash correctly and all three extractions replay without source requests.
This establishes GitHub-only readback/restore at that revision, not an independent
provider backup. The parity tool's rights/visibility booleans are deliberately
false: those matters are assessed separately, not certified by Git parity.

### Per-release result and immutable version references

The release URLs and existing `uscc-press:<slug>` identities remain the exact
ones in the representative-identity table above. Captures occurred at 22:20 UTC
on 3 November 2026, using the declared IPR bot. Current robots policy permitted
all three paths and was preserved privately. No redirect, linked work, attachment
or media request occurred. No body text or quote is copied into this public note.

| Release | HTTP / capture UTC | Raw HTML bytes / SHA-256 | Extracted UTF-8 bytes / SHA-256 | Result |
|---|---|---|---|---|
| July 18 departure | 200 / 22:20:02.896243 | 52,063 / `0336e745d8a0866484d63f0c2f702eac03de9a1de239db3abffd33843594d71e` | 2,352 / `494261ada2847eeaabf4e44fa2c09dd9af7f6792ff1dbca8bde556ffd57ec549` | Qualified custody/fidelity; narrow narrative scope accepted, operations held |
| July 25 return | 200 / 22:20:05.522922 | 56,636 / `cd3111f115ea501ddf544655a37ca46827715f6bfd2193dacdb5a1991b9cb648` | 2,103 / `0f468f672df1c13d2becbd614957f345cc80194e037eeac75b3a94fc8d856a87` | Qualified custody/fidelity; narrow narrative scope accepted, operations held |
| June 25 glossary announcement | 200 / 22:20:08.164255 | 51,350 / `93a7514453f6bbf73b27054f8ff3cfe598b6de69f99d366bd8d5cb55ca59f446` | 1,857 / `8dc9eb078f4999b266ec45879197172c3af11b84ed78e219fd4dce4310c80d0d` | Qualified bounded custody/fidelity; broader use HELD |

**Identity/dates:** final URL, canonical link and article RDFa identity agree for
each. Visible dates match the selected listing dates; CMS `<time>` values use
the matching day plus `T12:00:00Z`. That noon field is not proof of an exact
publication or event hour. No publication/modified meta field was found. These
are present-day captures, not authenticated historical versions from June/July.

**Completeness:** each response has a complete HTML closing tag and passes
applicable transport length checks. Each has one full press-release article and
one body within it; a site-wide body selector would incorrectly include repeated
navigation blocks. Release bodies contain one h2 plus respectively 8, 6 and 7
nonempty paragraphs. Stored text conserves all body text nodes, including link
labels and institutional boilerplate, in order; a separate stdlib HTMLParser
pass agrees after whitespace/NFC comparison. Stored text is UTF-8,
BeautifulSoup `stripped_strings` joined with LF and terminal LF (no stored NFC
normalization). Raw-byte, extracted-text and serialized-fragment hashes remain
distinct. No inline media occurs in the release bodies; referenced site assets
remain HTML references only. The June announcement links two research pages;
neither was followed. This proves the served HTML body, not linked-publication
completeness, browser layout, historic revisions or recurring delivery.

**Authorship evidence and hold:** each is an institutional press-release article
with Commission identification and Chair/Vice Chair attribution, including
Schriver/Kuiken name indicators. No author meta tag, article author field,
contractor/prepared-by credit indicator or reuse notice was found by the recorded
checks. Those facts support Commission-announcement classification and distinguish
these pages from commissioned studies. They do not identify the drafting employee,
prove the official-duty origin of every quotation, or establish every intended
reuse. Absence of a detected credit is not clearance. No human legal review or
signoff is represented. Accordingly broader original-backed source use remains
held outside the accepted July narrative scope; June remains held. This is not
evidence that a contractor actually authored any of them. The accepted assessment
does not require identification of the drafting employee.

### Historical decision request — now resolved for the July scope; operations held

The current decision above resolves the following earlier request for the July
scope; it is retained here as assessment history. No further capture authorization
is needed for the work just completed. The earlier request was: review
the preserved institutional/official-attribution evidence and decide whether a
documented, source-specific official-duty assessment adequately supports the
narrow Commission-written release family, with actual third-party/quotation
exceptions held. Founder acceptance cannot itself grant third-party rights;
if material ambiguity remains, name the missing evidence or narrower usable
scope. Publisher contact is neither automatically required nor authorized.

Before any subsequent model test, specify the applicable provider/data handling,
permitted input/output components, spend/retry limits and accountable owner.
This phase grants none of those uses. After adequate source-use authority, the
smallest implementation remains the USCC adapter/custody validator and explicit
English profile connected to existing shared lifecycle/admission, in coordination
with #950/#953. No shared dispatcher, workflow, renderer, registry, production
data or source activation changed here. Stop at review of these findings.

## Offline exact-version input adapter — superseded by the family qualifier

*Historical record of the exact-two slice. The family qualifier described under
"Implementation state" below replaces its runtime allow-list; the two pinned
versions now live only in `tests/fixtures/uscc_accepted_regression_versions.json`
as regression cases, and `config/uscc_offline_accepted_versions.json` is retired.*

The follow-up task authorizes offline implementation only, overriding the earlier
implementation hold solely for this slice. `core/uscc_offline_input.py` provides
`derive_input(raw, source_identity=..., canonical_url=..., publication_date=...)`.
It accepts in-memory bytes already in private custody and returns private
`potential_input` plus a derived manifest. It has no acquisition, model, storage,
registration or publication entry point. Never print or commit its returned
prose in public. Complete originals are untouched.

`config/uscc_offline_accepted_versions.json` pins exactly the two accepted
capture/text hashes and all ordered paragraph hashes from private evidence
`9036f2fc91ff59ddbbfd8f0d6655b00a6efa51ab`; it is an extraction constraint,
not a runtime permission grant or new source registry. The adapter reuses USCC
canonical identity normalization and the preserved BeautifulSoup text extraction
algorithm. It validates exact raw bytes/length, canonical/final publication
identity, article RDFa, visible and machine dates, complete HTML, unique body,
text hash and ordered paragraph hashes before selection. It never trusts a
caller-supplied permission policy. Fixed hold diagnostics contain no prose.

Zero-based nonempty paragraph boundaries: July 18 includes 0–3 (the narrative
subtitle and three narrative paragraphs), excludes 4–5 as whole quotation
paragraphs and 6–7 as institutional boilerplate/social labels. July 25 includes
0–1, excludes 2–3 as quotations and 4–5 as boilerplate/social labels. These map
to the quotation line exclusions in the accepted decision. Link labels in
excluded paragraphs never enter input; no linked work or media is read. The
body h2 supplies the accepted title separately. Every included/excluded paragraph
has its index/hash and exclusion reason in the manifest, alongside source
identity, date/URL, evidence commit, decision reference and capture/text hashes.
The potential input is canonically JSON-hashed; it is explicitly incomplete as
an original input, with transmission/publication authority false and the potential
note limit 90 words. No note is generated or publication eligibility granted.

Private offline replay of both original captures passed twice with identical
results. July 18 potential-input digest:
`7d29108f450a4ce40b3dd5f322ad801a2dfc3e3ab9677c044f49568b4b9c65a5`;
July 25: `bf1d2926736f58fc675f7bba54f517129f04633ac21379631a30381cbf080d26`.
Derived JSON remains only in an access-restricted local private directory, not
public fixtures or Git. Existing native private custody/readback of the complete
originals remains authoritative; no evidence ref or original was rewritten.

Synthetic tests cover deterministic scoping/accounting, unsupported publication,
changed/truncated bytes, mismatched identity/date, incomplete HTML even with a
matching fixture hash, duplicate/missing paragraph selection, altered paragraph
hashes, quote inclusion, linked input and embedded media. They do not use private
prose. No shared dispatcher/workflow/renderer/registry, dependency, production DB
or generated output changes. This is not a live caller migration: deliberately
no runtime caller exists until separately authorized integration. Remaining
holds on transmission, spending, recurring acquisition, activation, publication,
contact, merge and deployment remain. Future versions and June 25 are rejected.

## Standing-family assessment — founder-approved text, pending merge (4 November 2026)

**Status: text approved by the founder in chat on 4 November 2026; on
7 November the founder directed that it be adopted together with its
implementation as one review candidate (`DECISION_LOG.md`, 2026-11-07). It takes
effect only when that candidate is merged.** The founder supported extending the 11-03
assessment to a narrowly defined standing family of unsigned, Commission-issued
institutional press releases, subject to the corrections incorporated below, and
then approved this text. The approval is recorded in `DECISION_LOG.md`
(2026-11-04, "USCC standing-family assessment text approved"), as
`CONTENT_AND_DATA_RIGHTS.md` §7.4 requires a new basis to be reconciled with the
existing source-specific decision. It approves policy text only: it is not a
merge approval and authorizes no code change, model transmission, spend,
collection, activation, publication or deployment. Until the PR is merged the
11-03 decision is the only recorded basis and covers the two exact captures.
Nothing here widens the adapter. No release body was fetched.

### What is established, and what is not

**Established legal principle.** 17 U.S.C. § 105 denies copyright protection to a
"work of the United States Government", which § 101 defines as a work prepared by
an officer or employee of the U.S. Government as part of that person's official
duties. The U.S. Copyright Office, *Compendium of U.S. Copyright Office Practices*
(Third) § 313.6(C)(1), "U.S. Government Works" (official edition at
`copyright.gov/comp3/chap300/ch300-copyrightable-authorship.pdf`, retrieved
4 November 2026), states that this principle expressly extends to Congress and to
federal "departments, agencies, boards, bureaus, or commissions", for works of an
officer or employee within the course of official duties. The Compendium quotes
*Georgia v. Public.Resource.Org, Inc.*, 140 S. Ct. 1498, 1509–10 (2020), for the
point that the bar covers works of all federal officers or employees without
regard to the nature of their position or the scope of their authority. (The
*Georgia* holding is cited here as the Compendium reports it; the opinion was not
separately read for this section. Another, older Compendium copy on a third-party
site omits the word "commissions"; the Copyright Office's own current text is the
authority used.) The Compendium is the Office's registration guidance rather than
binding law, so the statute and the case remain the underlying authority.

The same Compendium section also records the limits that matter here: the
government can hold a copyright acquired by assignment, so a contractor's work
that was assigned to an agency can be copyrighted; a work prepared outside a
person's official duties is outside the bar; and a few statute-specific
carve-outs exist (Smithsonian trust-fund staff, certain National Defense
University faculty works, NTIS standard reference data). None of those is shown
for USCC; the first two are the live ones.

**What the principle does not settle.** Category coverage is not authorship.
Whether a given unsigned release was in fact prepared by a Commission officer or
employee in the course of official duties, rather than by a contractor, a
commissioned author or another non-employee, is a question of fact about that
release. 22 U.S.C. § 7002 (retrieved 4 November 2026) does not say who drafts
press releases. Its subsection (e)(3) deems Commission employees to be § 2105
employees "for purposes of chapters 63, 81, 83, 84, 85, 87, 89, and 90" of
title 5 only, which is a limited-purpose personnel provision and not a finding
under §§ 101 and 105; subsection (e)(4) permits details of federal employees and
(e)(6) lets the Chairman procure temporary and intermittent services, so
non-employee contributors are lawful. The 11-03 residual drafting-arrangement
uncertainty is the only treatment of that question, and only for two captures.
A search limited to `uscc.gov` for a copyright, reuse or terms notice surfaced
none (excerpts only). That neither adds a restriction nor grants permission.

### The standing assessment is rebuttable and evidence-based

This is not blanket public-domain clearance of USCC material. The proposal is that
a release inside the family is treated as a § 105 work **unless the evidence
rebuts it**, release by release. A single affirmative sign of non-employee
authorship, assignment or licence, or a source notice, withdraws the presumption
for that release, and a pattern of them withdraws it for the class.

**Routine new releases qualify without per-record founder approval** when every
one of these holds, checked from the capture rather than assumed:

1. **First-party identity.** The release is on the Commission's own domain under
   its canonical press-release URL, with a single consistent publication identity.
2. **Official narrative.** The text in scope is the unquoted institutional
   narrative, not a speech, testimony, quotation or linked work.
3. **Structure.** The page matches a structure that can be mechanically verified
   (one body, one date, one title, no scripts, media or embeds in the body).
4. **Authorship indicators.** The release is unsigned and carries
   Commission-only identification: no named external author or organization,
   contractor or commissioned-study credit, "prepared by" line or third-party
   attribution.
5. **Access conditions.** The page is lawfully and publicly retrievable with no
   login, paywall, access control or robots restriction in the way, and no
   copyright, reuse or terms notice that contradicts the assessment.
6. **Source-specific exclusions.** None of the exception classes below applies to
   the portion in scope, and no existing source-specific hold (for example the
   June 25 research-linked glossary announcement) covers that release.

A release that passes is not individually presented to the founder. A release
that fails any item is held individually, as are those whose pattern the checks
cannot recognise.

**A changed version of an existing release keeps strict version-integrity
review.** A prior qualification attaches to the exact captured version (capture,
content and paragraph hashes), never to the release's URL or to the family. A
changed version is a new version: it is compared against the version assessed,
the change is explained (correction, addition, removal), and it re-qualifies
under all six checks before use. A mismatch is held; it is never carried forward
automatically.

### Components that stay held individually

1. **Contractor, commissioned-study or other third-party expression**, including
   releases that credit an external author or organization (the 2026-08-26 and
   2026-09-22 announcements).
2. **Quotations** of any kind. Attribution to a speaker does not establish who
   wrote the words.
3. **Attachments and linked works**, including research products and glossaries
   a release points to (the June 25 pattern). The announcement alone can be
   metadata and a link.
4. **Media**: photographs, graphics, video and embeds.
5. **Boilerplate and social labels.**
6. **Testimony excerpts and other third-party material.**
7. **Any release or component without Commission-only identification** or whose
   structure falls outside what can be verified, and anything else unsupported.

### The 90-word limit is not a legal authorization

An independent, attributed factual note of at most 90 words may be eligible as an
output. The limit is a size control on IPR's own wording. It does not authorize
anything: whether the input may be retained and used rests on the § 105 analysis
above (and facts are not protected, § 102(b)), and the note must contain no
verbatim source text. A note within 90 words drawn from an input that fails the
checks is still held.

### Activities, separately

| Activity | Exact July 18/25 narratives (11-03) | Routine releases in the proposed family |
|---|---|---|
| Discover and link metadata | Supported (existing metadata path) | Supported (existing metadata path) |
| Retrieve and retain in private custody | Supported within 11-03 | Proposed: rebuttable § 105 presumption when the six checks pass; residual authorship uncertainty remains and is the point of founder review |
| Extract facts; write an independent attributed note of at most 90 words | Accepted scope (no verbatim text) | Proposed on the same basis; output only, never reproduction |
| Send input to an external model | Not authorized by 11-03 | **Separately governed**: provider terms, data handling and spend |
| Quote, translate or reproduce | Not supported | Not supported |
| Public components | Metadata and link only | Metadata and link only |
| Changed versions | Held (`capture_version_mismatch`) | Strict version-integrity review; held until re-qualified |

Section 107 is not relied on: the factor analysis for full-text model input and
whole-release retention is not made out here, and a per-release four-factor
judgement is not a standing basis.

### Separately governed, not decided here

External-model transmission, provider handling and data terms, spending,
recurring collection, activation, publication, deployment and outside contact
each need their own decision. Neither the family assessment nor the chat
endorsement authorizes them.

### Gaps that remain

- No Commission-specific authority located on how §§ 101 and 105 apply to
  Commission staff drafting (employee status beyond the limited § 7002(e)(3)
  deeming is not separately researched here).
- No affirmative evidence of who drafts routine releases: staff, detailees or
  contractors engaged under § 7002(e)(6). The rebuttable presumption and the
  Commission-only identification check are the response to that gap, not a
  closure of it.
- No site-wide legal or copyright notice located.
- Quotation provenance and future release templates are unknown; a new template
  fails the structure check and is held.

### Implementation state

Adoption candidate (7 November 2026): policy and implementation together, in
effect only on merge. `core/uscc_offline_input.py` implements the six checks as
policy `uscc-standing-family/1`; there is no parallel engine, permission file or
shared-file change.

- **`qualify(raw, *, source_identity, canonical_url, publication_date, access,
  robots_txt)`** runs, in order: identity-keyed holds (June 25 stays held under
  the 11-03 decision), first-party identity (canonical/final URL, RDFa article
  identity, single title, visible and machine dates equal to the admitted date),
  access conditions (the capture's access receipt must match the bytes' SHA-256
  and length, an unredirected public HTML 200 response, and a robots.txt whose
  hash matches the receipt and that permits the fetching agent and `*`), page
  gates (paywall/login or copyright/licence notice holds), authorship indicators
  (bylines, credit lines, author metadata, "prepared/contracted by" language
  hold), template structure (narrative → whole-paragraph quotations →
  institutional boilerplate → social labels; anything else holds as
  `unrecognized_release_structure`, links or media in narrative hold) and
  non-narrative forms (testimony, speeches, remarks, op-eds hold).
- **Output.** Private `potential_input` (title, canonical URL, date, narrative
  paragraphs only) plus a hash-only manifest (`ipr-uscc-family-potential-input/2`)
  recording every paragraph's index, hash and inclusion or exclusion reason. The
  manifest states `complete_original_input`, `model_transmission_authorized` and
  `publication_authorized` false, `public_scope` `official_link_only` and the
  90-word note cap as an output limit.
- **Lifecycle integration.** `qualify_admitted(con, raw, …)` reads URL and date
  from the existing `uscc_official_source_records` row (unadmitted identities
  hold), and writes one row per capture to `uscc_narrative_eligibility_receipts`
  (FK to that table, hash-only manifest, custody commit, `public_scope` and
  `model_transmission_authorized` fixed by CHECK constraints). Re-qualifying the
  same capture is idempotent; a differing result raises. Any held version keeps
  the release held (`prior_version_held`); a changed version must name the
  latest receipt it supersedes and records a paragraph-hash change summary. The
  caller commits; no public loader or renderer reads this table.

**Demonstrated.** Offline replay of the two preserved accepted captures through
the family qualifier reproduces their accepted potential-input digests exactly
(July 18 `7d29108f…`, July 25 `bf1d2926…`), and the preserved June 25 capture
holds (by identity, and by structure if that hold is removed). Synthetic tests,
all labelled as such, cover positive eligibility, every hold code, changed and
truncated captures, leakage of excluded components, receipt integrity and
isolation from public loading.

**Not demonstrated.** No additional authentic routine release was available
without new acquisition, so general-family success rests on two regression
positives and one authentic hold. Template drift, quotation provenance and actual
drafting authorship remain open (see "Gaps that remain"). No note was generated,
no model called and nothing published.
