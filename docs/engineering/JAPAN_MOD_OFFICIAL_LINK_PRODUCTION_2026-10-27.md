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
