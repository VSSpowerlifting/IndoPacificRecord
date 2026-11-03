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

## Original-backed family qualification — 3 November 2026

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
