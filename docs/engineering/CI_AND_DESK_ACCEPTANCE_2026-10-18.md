# Risk-based verification and complete-desk acceptance

**30 October 2026 controlling standard:**
[`../desks/README.md`](../desks/README.md) governs every desk and replaces older
generic architecture/launch procedures. This file specifies current verification
and the qualification/delivery transition. Policy adoption does not mean that
transition is implemented; current gates remain until their tested replacement.

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

## Mandatory shared system

Use the source-definition, optional permitted-component and shared lifecycle
contract in `docs/desks/README.md`. Every desk follows the same implementation
standard; source-specific extraction, permissions and factual QA remain explicit.
An explanation need not have a public original. A metadata-only source does not
gain explanation/text rights. Routine eligible machine records run unattended
under actual authority; human Briefs keep their editorial approval.

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
classifier, workflow, or its tests **itself** gets the full suite. Daily retains
its full offline run as the fail-closed fallback; only authenticated full
qualification for equivalent inputs/environment can replace that development
run. All runtime and live-deployment gates remain mandatory. A focused PR success
cannot supply reusable qualification or authorize production publication.

## Required qualification/ingestion/delivery separation

The 30 October owner decision requires the following boundary. Daily now uses
`scripts/code_qualification.py` and attempt-specific GitHub main-push run/job evidence to
implement the full-qualification/fallback decision. The detailed trust boundary,
invalidation rules and first-use prerequisite are in
[`../ARCHITECTURE_AND_PUBLISHING.md`](../ARCHITECTURE_AND_PUBLISHING.md#2a-mandatory-all-desk-structure--30-october-2026).
PR synthetic merges remain tested with read-only credentials but do not certify
reuse. The same offline workflow qualifies reviewed main pushes; explicit
data-only main changes skip dependencies, tests and rendering. This adds no job,
required status or production operation.

1. **Qualify code:** bind successful applicable checks to the exact executable
   and configuration inputs, dependency/runtime identity and trusted CI evidence.
   A PR success for an unrelated revision is not qualification. Source replay and
   full CI remain required for applicable code/schema/policy/workflow changes.
2. **Ingest routine data:** verify current policy/activation, source identity,
   authentic custody, immutable version binding, budget/retry continuity, schema
   integrity and atomic admission. Reuse qualification only for provably unchanged
   executable inputs; normal data growth need not rerun all development tests.
3. **Deliver:** render from the final reconciled admitted snapshot; validate
   allowed public fields, record/Archive/search parity and output invariants;
   serialize the public writer, verify deployed output and then record success.

Unknown/missing/failed qualification or changed executable/configuration,
dependencies, schema, policies or workflows must invalidate reuse and require
the applicable qualification. Never execute untrusted PR code with production
credentials. A reviewed implementation must test invalidation and failure paths
before replacing the development gate. Existing CI statuses and branch protection remain
in force until explicitly migrated; do not infer settings access from this doc.

Keep tests on fixed evidence and isolated DBs. Runtime checks enforce invariants
rather than freeze the expanding production corpus. Collection/custody success
and public-delivery success are separately recorded; downstream failure preserves
captured evidence and the last verified public site. Isolate a source/version
failure where safe, but fail the affected release on shared integrity or public
projection failure. A quiet source is distinguishable from a missed/failed run.

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
