# Risk-based verification and complete-desk acceptance

**Owner direction, 2026-10-18.** Verification should prove a working IPR
research service, not become an independent backlog of gates. This policy
supersedes earlier automatic seven-/30-consecutive-day **prelaunch** holds.
Older signed reviews, failed days, immutable original captures, and historical
receipts remain intact; do not erase or reclassify them.

## One engineering outcome per desk

Build the agreed official source families, authenticated captures, source custody,
rights-controlled reuse, any necessary translations, IPR analysis, approved public
presentation, and automatic daily maintenance as **one dependable system**.

A desk is:
1. **Built:** the agreed capabilities exist and are connected.
2. **Operational:** a real official-source item has passed an end-to-end
   collection → stored original/metadata → processing → approved presentation
   → actual site readback, and one representative failure/retry was exercised.
   A real source's continued unavailability remains a blocker if the agreed
   service cannot operate; do not substitute simulated fixtures.
3. **Maintained:** the normal operational signals detect a missing collection,
   failed processing, source drift, and deployment error, with a known recovery
   path. Seven- and 30-day histories are reliability **measurements**, not
   automatic waiting periods before stage 2.

A source producing no new records is not a failure by itself; distinguish an
official quiet period from a skipped/failed collection. No one may declare real
model operation from mock replies, or actual HTTPS publication from a passing
build. Only the source families agreed for the desk count toward completeness;
do not inflate desk scope after completion.

## Shared Daily instead of desk-specific publication silos (19 October owner direction)

The complete-desk principle now includes a durable architectural default:
keep source collection separate where warranted, but converge eligible,
source-version-verified data on the shared Daily screening/analysis system,
source-appropriate rights gates and common site publication. Source-language
profiles must be explicit; translate non-English material only; never run
unknown desks through China-specific prompts. Reuse the existing corpus for
rights-cleared full-text records and distinguish restricted neutral source
links from articles. Once independently authorized, quality-passing, labeled
machine record output should publish without routine per-record owner review;
source anomalies and genuine rights/quality failures hold individually.
Human Briefs and bylined editorials still require their normal approvals.
No new permission, spending cap, rollout or claimed real end-to-end proof
is created by this architecture preference. See `docs/engineering/SHARED_DAILY_DESK_ARCHITECTURE_2026-10-19.md`.

## Verification budget

The existing PR workflow keeps its read-only token, no secrets, no write
permissions, PR synthetic-merge checkout, production DB/output preservation
assertion, and single stable required status **PR offline checks**.

Its conservative path classifier (`scripts/pr_ci_scope.py`) chooses:
- **Docs only:** Markdown-only process/copy edits: no Chromium or 7,000-test run.
  Human policy/rights review still applies to any substantive decision.
- **Focused presentation:** only the allowlisted timeline stylesheet, template,
  macros, water assets and optionally Markdown: browser launch, timeline and
  publishing/rights tests, CSS design constraints, and output validator.
- **Full:** every unknown path; Python/JS/data/schema/collector/model/pipeline/
  workflow/registry/rights/security/test/publishing change; source evidence
  changes receive applicable frozen-source replay. Full suite, browser and
  validator remain mandatory in this mode.

The PR classifier fails closed on an absent/invalid diff. An edit to the
classifier, workflow, or its tests **itself** gets the full suite. Daily
production retains its independent full offline run and live-deployment gate;
a focused PR success does not authorize production publication.

Do not add another independent workflow for a test that can run inside the
existing suite. Do not remove source-specific negative tests or boundary
protections. Retire obsolete/duplicative workflow triggers only after
confirming they are not required by branch protection, operations or
publication paths. A source evidence replay belongs to source changes, not CSS.

## Human and integrity boundaries remain absolute

- Obey the official publisher's access controls, source identity and robots.
  Hash/version-bind original evidence; never rewrite history or invent recovery.
- Rights for original text, image/PDF, links, translation and analysis are
  **separate decisions**. Respect licence terms and any permission requirements.
- Human editorial acceptance and document-specific release approval cannot be
  inferred from tests or machine scores. Brief bylines and approvals are
  separate from institutional features like Evidence Timelines.
- Preserve atomic DB writes, deduplication, rollback, private-source custody,
  limits on model spending, and real publisher/site verification.
- Stop at a genuine human or source-access blocker with one precise owner
  action; do not build a new audit pipeline to disguise it.

Existing Day-7/14/30 shadow-review scripts remain **historical evidence tools**.
They do not automatically define how a new desk launches. Keep their actual
review dates and prior dispositions intact. The owner chooses publication
explicitly after the real end-to-end checks and source-use decisions.
