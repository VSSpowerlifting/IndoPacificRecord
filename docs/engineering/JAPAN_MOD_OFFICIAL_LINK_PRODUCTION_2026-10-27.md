# Japan MOD news official links — source use approved, release held

> **Desk architecture/process supersession — 30 October 2026:** the
> [mandatory shared desk standard](../desks/README.md) governs every current and future
> desk. This document's older common architecture, onboarding order and launch
> clocks do not override it. Source-specific decisions, restrictions, real
> evidence and still-used commands remain valid in their actual scope. This
> notice does not claim runtime migration, change permissions or activate a source.


The initial review found no standing Japan MOD grant. Benjamin Yang then
explicitly approved the narrow `jp_mod_news_ja` standing source-use scope on
27 October 2026. `config/japan_mod_official_link_policy.json` records that grant
and references its `DECISION_LOG.md` entry. The grant excludes merge, intake
activation, manual workflow dispatch and deployment: those require a separate
release decision after verification. The shared Daily activation variable is
unset, and the production admission CLI checks that gate independently. No
production data, schedules, repository variables or public output are changed
by this task. Historical PDF navigation and Brief approvals are separate grants.

## Genuine source evidence

The latest completed scheduled collection inspected was
[40433531306, attempt 1](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40433531306),
finished 27 October at 01:37:14 UTC for the **26 October schedule slot**. Its
collector revision was `448991c5619de9980454416d426d5cf944e28c89`.
The preserved state is commit `4ac08f6f95e8d8859501ffa567d6bd76a049091b`
on `shadow/jp-mod`; SQLite SHA-256 is
`76917f9a5b839d3224faf9a03a3718f41e25f1d97a40c93b6f8971130c6829a1`,
matching the exact ledger in both Git and artifact `12703107202`.

The news source discovered 135 entries: 87 known challenges, two extraction
failures and one oversized PDF retrieval failure were recorded in its source
bucket. The overall collector reports partial health and 197 outstanding gaps
across both feeds. Workflow success does not qualify these entries for release.

Seven successfully retrieved, text-bearing records have `source_slug` exactly
`jp_mod_news_ja`. Their official paths are:

| MOD `/j/press/news/` path | Preserved RSS date | First-seen run |
|---|---|---|
| `2026/08/27b.pdf` | 2026-08-27 | 33147429840 |
| `2026/08/28a.pdf` | 2026-08-28 | 33232394996 |
| `2026/08/28b.pdf` | 2026-08-28 | 33232394996 |
| `2026/08/28f.pdf` | 2026-08-28 | 33232394996 |
| `2026/10/05b.pdf` | 2026-10-05 | 37404326269-1 |
| `2026/10/22a.pdf` | 2026-10-22 | 40047801924-1 |
| `2026/10/23a.pdf` | 2026-10-23 | 40047801924-1 |

The four first-seen run identities and the latest run were checked against the
GitHub Actions API: repository, workflow path, event, branch, attempt, successful
completion and collector SHA. The extracted-text hashes match the first-seen
ledgers. The latest real robots observation is rehashed and checked for the feed
and every eligible URL. No request is made to a challenged publisher route.

The collector stores `hint_published_date` from RSS `pubDate` directly in each
record. It does not establish the document's issue date. The public label is
**RSS pubDate (not independently verified document issue date)**; a date is never
inferred from the filename or changed to the run's date. The existing regional
column `publisher_posted_date` retains its name; this family's presentation and
archive/search projection always carry the explicit RSS date type.

This is replay of authenticated collector state, **not a fresh PDF byte audit**:
the state retains extracted text and PDF capture hashes, but not raw PDF or RSS
bytes. No headline or body is exported in the public metadata fixture. First-seen
provenance comes from actual recorded runs, not a newly invented receipt. The
source manifest attributes this Japanese ministry news family to `jp_mod`; it
does not carry the separate Joint Staff source.

## Existing production path, intake disabled until release approval

```text
existing scheduled Japan collector → immutable shadow/jp-mod state
  → shared Daily (explicit activation variable + recorded owner policy)
  → source-specific evidence checks → shared regional_official_source_links
  → existing production desk + archive/search renderer → existing Pages writer
  → exact SQLite/HTML/Pages Git bytes and HTTPS readback
```

Migration 0020 extends the existing table constraints and preserves its current
Vietnam document family and every existing row. It creates no Japan article or
parallel corpus. The shared atomic store rejects duplicates, changed released
metadata and legacy article URL collisions. Unchanged retries preserve the
original release commit, proof and timestamp. The shared DB reconciler preserves
Japan additions over unrelated Daily rebases; the final database is rendered
again before deployment. Failed Japan intake rolls back and leaves other desks'
intake available; it cannot manufacture an empty successful source observation.

Only successfully retrieved news-feed PDF records qualify. Challenged HTML,
failed PDFs, site-update RSS, undated/unassigned and pre-bootstrap rows are
excluded. The two visually reviewed September PDFs remain historical navigation,
not automatically admitted records. Existing curated links remain separately
labeled and are not counted as a second admission. There is no model call,
translation, copied title, PDF/media mirror or machine explanation.

## Verification and limits

The initial private rehearsal used a disposable production DB copy and a **test-only in-process
policy override**, never an edited approval file. Seven links were admitted;
the repeat admitted zero and left the database byte-identical. All non-Japan rows
in all 24 existing tables were unchanged. Source replay, invalid/duplicate
rejection, atomic rollback, policy refusal, first-release preservation, rebase
preservation and exact HTML readback have focused tests. The frozen source replay
runs in the existing required PR check, using pinned Git source objects and the
metadata-only saved API receipts; this offline replay does not assert a new live
API verification at CI time.

After the owner's source-use approval and current-main integration, the private
rehearsal was repeated under the actual policy with fresh read-only Actions API
checks, without a policy override. Seven links were admitted, zero on retry;
existing rows in all 24 tables were preserved, with only the expected 0020
schema-ledger addition and Japan metadata rows. The production database remained
byte-identical. The 239-test focused run passed. A separate activation-boundary
test verifies that the approved source grant alone cannot write production.

The production renderer was exercised in an external scratch output tree, carrying
the existing publication data and historical pages. Its validator passed with
seven warnings (the scratch carry path includes historical LinkedIn files). The
unchanged tracked output separately passed with its ten governed warnings.
Japan HTML+CSS was 102,354 bytes with the final neutral filename labels,
under the existing 120,000-byte cap. Browser checks at 1280 and 375 pixels found
seven admitted entries and no horizontal overflow. The all-route delivery check
originally reported an unrelated Indonesia page excess: 127,903 bytes in both
the then-current tracked baseline and rehearsal. Main subsequently fixed that
in #889; this branch integrates the approved repair and raises no budget.
The post-integration private render passes all 2,298 route budgets. Japan remains
102,354 HTML+CSS bytes, with seven rows and no overflow at 1280 or 375 pixels.

The first full PR run (`40453284956`, 8,080 tests) exposed migration-fixture
compatibility and template extraction assertions; these were repaired without
widening Vietnam's production migration guards. The expanded 167-test focused
run then passed, including the previously failing tests. The read-only-tool
failure was its explicit pending-version assertion, not actual DB residue.
The prior revision's second full run (`40456671270`, 8,080 tests) had only the
Indonesia budget failure remaining. At that revision the page was identical to
its main baseline (SHA-256
`7cd4712fc4343cbbddb31c9dfd90728c25305dabd050ef841ec8256ead5d037a`).
Final-head CI status is recorded in the PR; passing focused checks does not
establish a green full gate. Four ancillary workflows additionally failed before
tests because their Ubuntu 26.04 runners could not install Python 3.9.
Production admission, Pages publication and HTTPS readback remain **unexecuted**
because the owner has explicitly withheld release activation and deployment.
The readback command is prepared, not claimed successful on a public page.

## Recorded owner decision and separate release procedure

Standing source-use scope approved by the owner (the authoritative wording is
recorded in `DECISION_LOG.md`):

> Authorize standing, unattended publication of existing and future verified
> `jp_mod_news_ja` official-link metadata through the existing shared Daily:
> canonical official URL, source identity, RSS pubDate with its explicit date
> type, and Japan Ministry of Defense institutional attribution. Limit initial
> eligibility to successfully retrieved news-feed PDFs. Exclude challenged,
> failed, undated and unassigned records. No original headlines, bodies,
> excerpts, PDF copies, photographs, translations, external model processing or
> machine explanations are authorized. No routine per-record approval is
> required within that scope; actual exceptions remain held individually.

The source-use decision is now recorded and the policy authorization is true.
The owner explicitly requires current-main integration, CI repair and safeguard
verification before a separate release decision. Current main `8b69d1f2c6`
contains the independently merged Indonesia budget repair (#889), dossier
presentation (#887) and PR timeout maintenance (#885). This branch integrates
those changes intact; it does not relax a budget. The four observed Python 3.9
setup failures are addressed by pinning their read-only jobs to Ubuntu 24.04.

Review the exact policy/release revision and pass the required PR offline check.
Merge only under a separate owner release decision. Set repository variable
`JAPAN_MOD_OFFICIAL_LINKS_ENABLED=true` only under explicit activation authority.
The next eligible existing Daily run fetches the collector state and admits
metadata; a separately authorized manual Daily dispatch can be used instead.
Confirm the run's Japan admission and readback steps, including at least one real
public result, before calling the service operational. Future eligible records
then follow the same path without per-item approvals. No paid processing or
additional schedule is needed. To pause new intake, unset the variable; preserve
already released rows and their approved presentation.

## 6 November 2026 — authenticated PDF original replay, offline candidate

The next source-to-reader prerequisite is **raw original-byte fidelity**. The
current shadow collector's genuine `jp_mod_news_ja` state preserves the source
PDF SHA-256, normalized extracted text SHA-256, dates and scheduled-run ledger,
but **not the original PDF bytes**. A later successful PDF URL fetch is not proof
that the publisher served the same version. No historical capture can be
manufactured from a digest.

A bounded read-only bridge is proposed in
`core/japan_mod_original_replay.py` with the no-body-output CLI
`scripts/verify_japan_mod_original.py`. It accepts an already privately held
raw PDF **outside the repository**, an exact `shadow/jp-mod` state commit and
the existing `jp_mod_news_ja` source identity. It first reuses the live
`core.japan_mod_official_links.candidates` authenticated metadata route:
verified Actions source commit, frozen ledger, robots/access observation,
correct source family and first-seen identity. It then compares:

- the exact state DB SHA-256 and archived row with the verified candidate;
- the **PDF byte SHA-256** against the originally archived capture hash;
- the current project's normal PDF extractor with its exact archived
  normalized text and text hash; and
- every page's text-layer presence and extraction success, rather than
  treating a partial PDF text layer as a complete document.

The result is a **private in-memory text value** plus a public-safe hash/count
receipt. The CLI prints only the receipt and never persists source bytes,
publisher prose or a PDF copy. Missing/changed originals, missing text-layer
pages, unverified source/run lineage and foreign source families hold. This
does not resolve maps, diagrams, photographs, overall visual-document
completeness, third-party material or PDF redistribution. A PDF containing
illustration-only pages can match bytes and still be held from full-text
qualification.

This is an **engineering candidate**, not an adopted use-rights amendment,
source activation or production machine record. The current metadata-only
release policy remains effective while [PR #994](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/994)
is separately reviewed. No external model, translation, English explanation,
new source collection/custody, public original, machine record, DB mutation or
site publication is authorized by replay.

**Concrete next boundary:** obtain a legitimately retained, version-bound
official PDF through an authorized private custody path, run this exact replay
against its authentic state/version and independently assess each candidate's
text/media exceptions. Only afterward should a separately approved provider
and bounded shared-source profile generate an English explanation and pass
existing QA/admission and site readback. Japan still requires JCG English HTML
as a separate qualifying family for the eight-desk certification.

## 6 November 2026 — narrower PDL text boundary proposed for founder review

This is a **source-specific policy amendment candidate**, not a grant already
effective on `main`. The 27 October metadata-only approval and its existing
activation gate remain in force unless a separately reviewed change is merged.
The authoritative research-first standard is
[`CONTENT_AND_DATA_RIGHTS.md` §7](../../CONTENT_AND_DATA_RIGHTS.md#7-research-first-source-use-standard).

The [MOD's first-party current reuse notice](https://www.mod.go.jp/j/info/contents.html)
states that covered ministry-owned website content may be reproduced, translated
and adapted, including commercial uses, under PDL1.0 conditions. The
[Digital Agency PDL1.0 terms](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0)
require attribution, modification/translation disclosure, third-party rights
screening, and respect for separate terms and other legal exclusions.
This supports **conditional eligibility** of qualifying *extracted first-party
official news text* and unofficial English text derivatives. It does not
establish that a PDF with maps, photographs, mixed copyright, incomplete
extraction, revised pages or alternate terms passes.

The proposed `config/japan_mod_official_link_policy.json` now expresses
that narrower boundary rather than an undifferentiated text-and-translation
ban. Every eligible version must pass the existing
`core.standing_source_rights.qualify_standing_text` contract's trusted
source/capture, completeness, fresh publisher-license and exception replays,
attribution and derivative notice. No per-record signature is needed for an
actual passing standing-license qualification, but all failed/missing checks
hold. The historical archive preserves extracted text and capture hashes,
**not authenticated complete raw PDF custody**, so the existing seven metadata
items are not thereby declared text-qualified.

Still **not authorized by this proposal**: external commercial-model input,
automated text processing, public original/translation pages, complete PDF or
media reproduction, machine explanations, collector activation, manual
dispatch, source admission, spending, or deployment. Existing metadata-only
`permitted_fields`, source family/URL/date checks, public link projection,
recovery holds and the production activation switch stay unchanged. No
production text caller is added; source-to-reader substantive delivery needs
its own rights, custody, quality, provider and release integration phase.

**Next decision:** founder reviews this exact source-specific policy
amendment in the draft PR. If adopted, integrate the qualified text stage with
the shared lifecycle in a separate bounded task without weakening current
source/quality protections. Verify actual PDF version and licensing on genuine
evidence before any substantive publication.

## 7 November 2026 — first authentic PDF through the standing gate: HOLD

This section reports the first real run of the 6 November bridge
([PR #996](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/996),
head `9de51d855a`) against a genuine, privately held MOD original. No
publisher bytes or text entered the repository, logs, PR or any external
provider. Every probe printed only status codes, counts and hashes.

**Bound evidence**

| Item | Value |
|---|---|
| Source identity | `jp_mod_news_ja:/j/press/news/2026/10/23a.pdf` (RSS date 2026-10-23) |
| Private custody | `ipr-source-evidence-private`, ref `archive/jp-mod-pdf-originals`, blob `1e4322192baa2e046ceab4210439ea558798593a` |
| PDF SHA-256 | `7069b9baea136b9c96be13948e9628748ba48e45905ea024047189121b83b53d` (4,432,617 bytes) |
| Archived text SHA-256 | `56c4d16e8aecf054735b6700fc1828db1b173d996f8e9bad1cfa277481d621a1` |
| `shadow/jp-mod` state commit | `4ac08f6f95e8d8859501ffa567d6bd76a049091b` (run `40433531306-1`; first seen `40047801924-1`) |

**Replay result (passed).** `replay_private_pdf` returned
`PDF_TEXT_LAYER_REPLAYED`: 5/5 pages carry a text layer, 0 extraction
failures, PDF and normalized-text hashes both equal the archived capture,
source lineage authenticated. The extracted text is 1,576 characters.

**Standing qualification result (held).** `qualify_private_pdf_text` reached
`core.standing_source_rights.qualify_standing_text` and held with
`trusted_source_policy_and_exception_verifiers_required`. That is the correct
outcome: neither a trusted MOD `policy_replay` nor an `exception_replay`
exists. None was fabricated, and the gate was not relaxed.

**Why each open question stays held**

1. *Fresh publisher-policy verification. Blocked by an access control.*
   `https://www.mod.go.jp/j/info/contents.html`, `/j/` and `/en/` return
   HTTP 403 with a Cloudflare JavaScript challenge to automated clients on
   2026-11-07. `robots.txt` disallows only `/a/` and `/sp/j/`, so this is
   bot detection, not a robots rule. Under `AGENTS.md`, an automated policy
   replay cannot be built by impersonating a browser, solving the challenge,
   or substituting an archive or cache copy. The Digital Agency PDL1.0 terms
   page is reachable (HTTP 200), but it supports the MOD notice rather than
   replacing it as `official_policy_url`.
2. *Third-party expression. Unresolved, with a specific risk.* A structural
   screen found no embedded files, forms or annotations, and page 1 has no
   images. Pages 2–5 carry **9 raster images totalling 4,212,956 bytes
   (~95% of the file)**, in repeated size pairs (1517×600 ×2, 1840×477/476 ×3,
   1459×548 ×2, 1194×453 ×2). Such images commonly hold photographs, maps or
   figures whose credits and labels are absent from the text layer. A
   booleans-only Japanese marker screen of the text layer found zero hits for
   credit, co-issuance, separate-terms, secrecy, personal-data, figure-label
   and foreign-government-attribution markers. That screen can add holds but
   **cannot clear anything**, because most of the document is outside the
   text layer. The government URL, the clean extraction and the general PDL
   notice prove nothing about third-party content either.
3. *Separate terms.* No marker was found in the text layer, but whether the
   images carry their own terms is unknown.
4. *Privacy or secrecy.* The PDF metadata includes Microsoft MSIP
   sensitivity-label keys (label name, content bits, tenant/site identifiers).
   The label values were deliberately not read. What the label means is a
   human judgment and cannot be inferred automatically.
5. *Media.* `complete_pdf_visual_content_verified` remains `false`. A
   text-only release would exclude the images, but `exception_replay` must
   still certify what the released artifact embeds.

**Extractor-version sensitivity.** The exact replay depends on the pypdf
version. 6.20.1, 6.21.0, 6.21.2 (the capture run's version) and 6.21.4
reproduce the archived text hash, and 6.16.2 does not. `requirements.txt`
allows `pypdf>=6.0.0`. CI currently resolves ≥6.21, so it matches, but a
lower environment fails closed with `pdf_text_replay_mismatch`. That is a
safe hold, not silent drift. Any replay of this capture must run under
pypdf ≥6.20. The shared requirements pin was left unchanged here so it can
be coordinated separately.

### Hash-bound private review procedure (human, outside Claude and CI)

This procedure binds a reviewer's determination to the exact evidence above.
It produces a private record. It does not produce an automated verifier.

1. **Policy capture.** In the reviewer's own normal browser session, open
   `https://www.mod.go.jp/j/info/contents.html` and save the raw response body
   of the document request from the browser's developer tools (Network panel).
   Do not use "Save Page As", which can rewrite HTML. Record its SHA-256, the UTC observation time and the browser
   used. Confirm that the page still (a) applies PDL1.0 to ministry-owned
   site content, (b) permits reproduction and translation, (c) preserves the
   third-party, separate-terms and legal exclusions, and (d) is neither
   withdrawn nor changed in substance. Note the PDL1.0 version it cites.
   Under the gate's `MAX_POLICY_AGE`, qualification must run **within 7 days**
   of this observation. The hash binds this reviewer's capture; it is not
   expected to be reproducible later.
2. **Document fetch binding.** Retrieve blob
   `1e4322192baa2e046ceab4210439ea558798593a` from the private evidence
   repository. Confirm SHA-256 `7069b9ba…b83b53d` before opening it.
3. **Page-by-page review (all 5 pages, including every image).** For each
   page, record: any third-party photograph, map, chart or figure and its
   credit or label; any joint statement or co-issued or quoted foreign text;
   any separate licence or terms; any personal data beyond named public
   officials acting officially; any secrecy or handling marking; and whether
   the text layer fully represents the page's textual content. Open the
   document properties and record the MSIP label's display name and whether
   it implies any restriction.
4. **Record.** Store a JSON record in `ipr-source-evidence-private` (never in
   this repository) with these fields: reviewer, UTC time, the policy-page
   SHA-256 and observation time, the PDF SHA-256, text SHA-256 `56c4d16e…`,
   state commit `4ac08f6f…` and state SHA-256 `76917f9a…`, the per-page findings, and
   the eight `policy_replay` fields (`policy_id`, `official_policy_url`,
   `observed_at_utc`, `publisher_policy_sha256`, `text_reproduction_permitted`,
   `derivatives_permitted`, `third_party_exclusions_preserved`,
   `policy_changed_or_withdrawn`), and the six `exception_replay`
   determinations (`first_party_official_text`, `third_party_text_present`,
   `separate_terms_apply`, `privacy_or_secrecy_exception`,
   `released_artifact_embeds_media`, `entire_source_text_version_sha256`).
   Any "unsure" answer is a HOLD.
5. **No downstream authority.** A favourable record would at most qualify
   the extracted **text** of this one version. It would not authorize
   external model input, translation, public text, media reuse, activation,
   spending or deployment.

### Owner decision required

The standing gate's contract says self-reported booleans or caller-made JSON
cannot replace a trusted verifier. The Korea precedent
(`core/korea_text_only_exception_replay.py`) clears its exception replay
only because each item carries a machine-verifiable per-item KOGL Type 1
mark. Japan has only the general PDL notice, and image-heavy PDFs like this
one defeat a text-layer screen. Japan therefore has no automated path to a
passing `exception_replay` or `policy_replay` for this document class. The
founder must decide whether a **human-attested, hash-bound private review
record** (the procedure above) may serve as the trusted verifier for
individual Japan MOD PDF versions. If not, Japan MOD text remains held and
the desk stays metadata-only. Operating cost: the gate's 7-day
`MAX_POLICY_AGE` and the bot challenge together mean that a "yes" requires a
fresh human policy capture at least weekly, indefinitely, plus a per-version
human review. That is recurring human work, not unattended routine
ingestion. No code was added for either branch. That
decision comes first.
