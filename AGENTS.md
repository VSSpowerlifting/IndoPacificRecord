# Agent Operating Rules — Indo-Pacific Record

Read `CLAUDE.md` for repository operation. For **any desk work**, first read
[`docs/desks/README.md`](docs/desks/README.md), the mandatory all-desk standard,
and the relevant row of [`docs/desks/MIGRATION.md`](docs/desks/MIGRATION.md).
These tracked files are durable Codex/Claude project memory. Do not substitute
old chat history, local auto-memory or a dated rollout plan for current rules.

## Research-first source use — owner decision, 4 November 2026

Read [`CONTENT_AND_DATA_RIGHTS.md` §7](CONTENT_AND_DATA_RIGHTS.md#7-research-first-source-use-standard)
for the canonical source-use rule in both repositories. Establish a defensible
basis for each intended activity; written publisher permission is one alternative,
not a universal prerequisite. Public domain, applicable licences, statutory
exceptions and other demonstrated legal authority must be evaluated in their
actual scope, jurisdiction and binding terms. Public access, private custody,
research purpose and an owner signature do not establish a basis by themselves.

This general reform does not clear unresolved uses or change runtime authority.
Keep source-specific grants, legitimate publisher/access and third-party
restrictions, component-level holds, budgets and activation controls.

**MINDEF updated founder decision (9 November 2026):** the founder attests
standing written publisher authorization for eligible MINDEF-owned official
release original custody, bounded external-model use and independently worded
public factual explanations, in addition to standing official outbound links.
Do not reimpose the superseded two-link ceiling or treat the old source-family
collection/model ban as a newly required per-article publisher request.
The later publisher original remains unindependently authenticated in this
repository; do not claim that it explicitly enumerates the above components.
The existing MINDEF runtime acquisition, model and public-data holds remain
**technically active until separately implemented, qualified and authorized
for activation**. Third-party media, original-text republication, privacy,
provenance, QA and paid/release safeguards are not cleared by this decision.
Routine eligible records under established standing authority need no new
publisher request or per-record owner approval. Substantive governance/source-
rights amendments stop at founder PR review; collection/model activation,
deployment, historical-content treatment and outside contact remain separate.

## Founder decision — minimum operational desks and removal of redundant gates (11 November 2026)

**First milestone: one genuinely operational source family per desk; second milestone:
all sixteen previously agreed source families.** The eight-desk completion plan
defines the two milestones. Do not claim full-scope coverage from a single family
or call a metadata-only link an original-backed Record. The first milestone
requires permitted authentic original retrieval and custody, source-appropriate
factual QA, shared authenticated admission, real Record/desk/Archive/search
delivery and independent HTTPS readback, followed by a genuine unattended cycle
and recoverable failures. No fixed seven-/thirty-day clock or country-specific
review ceremony is a prerequisite.

**Remove process, not controls.** The 1 November waiting period for seven
consecutive eight-desk Daily runs before even proposing a new workflow file is
retired. Reuse or repair the shared workflow first; new workflows must have a
demonstrated nonduplicative need, owner, exact-head verification and separate
authorization for their operational effects. Older Day 7/14/30 checkpoint
requirements are historical, not live launch instructions. Retain real missing
runs, unresolved failures, publisher terms, source rights, quality, custody,
budgets, model/provider restrictions, final-head CI, production readback and
last-good-site protections. Do not turn source-specific factual review into
universal per-record editorial approval. Standing-authority eligible machine
Records already run automatically; human-controlled Briefs and other articles
retain their human approvals.

**Proportionate processing limits, challenged rather than blindly removed.**
The shared private intake presently enforces exactly one processed Record,
16,000 input characters and 90-word public explanations. These are not universal
legal safe harbors or evidence of quality. Prefer a tested cost-bounded,
multiple-eligible-record queue and full-source section-aware processing over
unnecessary hard rejections; retain intact originals and fact-to-passage
citation, source-specific rights/word limits, reasonable model context,
provider limits, per-run spending ceilings, attempt history and safe holds.
The one-original attended Singapore pilot, DAPA's inactive model authority,
and source-specific <=90-word decisions cannot be silently broadened by this
direction. Implementing any capacity change needs its own bounded, source-aware
engineering verification and separately applicable paid/activation authorization.

**Execution discipline:** consolidate the overlapping review candidates
rather than opening another parallel engine or conflicting integration lane.
Reuse existing authenticated CI qualification for unchanged data-only Daily
runs, with its fail-closed fallback. Do not require publisher correspondence,
a founder signature per permitted Record or a new independent reviewer when
the specific standing determination already applies. No broad merge,
activation, external provider, spend, public-writer or editorial authority
is created by this decision. Governance changes themselves still require
a separately authorized merge.

### Narrow standing merge delegation (founder approval 9 November; reaffirmed 11 November)

Without seeking an additional per-PR founder decision, an agent may merge
only *wholly* non-governing documentation spelling/formatting/internal-link
repairs, or strictly additive offline synthetic tests/fixtures that do not
change, delete, weaken or rebaseline an existing check, after normal required
review and exact-final-head checks. The agent must verify clean mergeability,
no outstanding reviewer objection or ownership conflict, and that the resulting
main-push workflows cannot dispatch models, publish, deploy, spend, activate a
source or mutate production. Record exact head and verification in the PR.

**Excluded:** AGENTS.md, CLAUDE.md, decision/governance documents, source rights
and policies, budgets, private evidence, collector/processing/application code,
workflows, DB/migrations, generated content, editorial work, all other
production-impacting changes, and stacked/conflicted PRs. If uncertain, stop
at a reviewed PR. The delegation never authorizes external contact,
source/model activation, expenditure, deployment or public release.
This governance cleanup PR is itself outside the delegation.

## Standing owner decision — 30 October 2026

Applies to China, Singapore, Korea, Philippines, Indonesia, Vietnam, Japan, the
US reference desk and every future source, in public and assigned private work.

1. **Sources own evidence and policy; desks are views.** One validated source
   definition references the collector/custody, explicit language/profile,
   source-use decisions, permitted public components, limits and activation.
   Rights, display status and activation are separate. One exact publication
   identity has versioned, optional permitted components; a public original is
   not required for a permitted explanation. Private evidence stays private.
2. **Share the lifecycle, admission and public record interface.** Reuse existing
   Analyzer, processing state, custody, projection, DB and renderer. Common
   mechanisms own version/dedup, checkpoints, bounded spend/retry, authenticated
   handoff, allowed fields and atomic admission. Source adapters/profiles keep
   real access, extraction, terminology and QA differences. No new per-country
   engine, queue, signing framework, corpus or renderer. Migrate real callers
   and retire the replaced active path; unused abstractions do not count.
3. **Separate code qualification, routine ingestion and public delivery.**
   Implement trusted exact-revision qualification reuse and runtime validation;
   until that replacement is reviewed and tested, current CI/Daily gates stay.
   Isolated fixtures test code; production checks enforce invariants and must
   survive valid corpus growth. Collection success and deploy success differ.
   Preserve captures on downstream failure and the last verified public site.

These requirements replace older architectural *preferences* and artificial
7/30-day launch programs. Existing dated guidance cannot authorize a competing
system. The standard documents the narrow owner-decided architecture exception;
normal implementation within the shared design needs no extra approval.

## Authority, work admission and completion — owner decision, 30 October 2026

**Default to improving research, not enlarging software.** IPR is a
source-grounded research publication supported by software. Do not add
a major desk, reader surface, model workflow, data store, publishing
mechanism or collector merely because it can be built.

For a *material expansion*, demonstrate in the existing issue or PR
body (not a new approval document):

1. **Research or reader need:** specific evidence, reliability, accessibility,
   editorial or reader problem; how success will be checked.
2. **Reuse:** why the existing source/component architecture, editorial
   product or current system cannot already meet that need.
3. **Cost and maintainer:** ongoing operations, QA, source-use rights,
   model expense, support burden and the person accountable.
4. **Opportunity cost and retirement:** work displaced, and the old active
   path or rule that will be removed instead of indefinitely duplicated.

Defer unclear expansions; the owner can explicitly authorize an exception.
Routine bugs, incident recovery, source-specific protections, security fixes
and low-risk accessibility work are exempt from the expansion justification.
**Do not create a new form, PR gate, CI job, readiness score or launch clock.**

Before starting a material expansion, or when asked to challenge a plan, use
the shared `ipr-proposal-review` skill for a read-only PROCEED, SIMPLIFY, DEFER
or REJECT verdict recorded in that same issue or PR body. It is advice for
the owner, not a gate, and exempt work does not need it.

### Documentation authority by subject

| Subject | Governing reference |
|---|---|
| Mission, audience, editorial/evidence trust, growth decisions | `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md`, explicit current owner decisions |
| Source-owned all-desk architecture | `docs/desks/README.md`; verified next code phase in `docs/desks/MIGRATION.md` |
| General source-use evaluation; source-specific rights, custody, holds, spending, approval | `CONTENT_AND_DATA_RIGHTS.md` §7; actual applicable law, terms, grants and source decisions; `DECISION_LOG.md` |
| Production and build verification | `docs/ARCHITECTURE_AND_PUBLISHING.md`, actual CI/workflows and code |
| Current strategic priorities | `docs/ROADMAP.md`, checked against real repo/source/site status |
| Agent instructions | This file; `CLAUDE.md` supplies only Claude-specific operating notes; shared skills live in `.agents/skills/` |
| Historic evidence and dated plans | Git history, `PROJECT_STATE.md`, older records; not current authority by default |

If references appear to conflict, preserve the stricter real evidence,
source-rights and activation control pending an explicit owner decision.
A general architecture, roadmap or research-first instruction never establishes
a source-specific legal basis or operational authority. Superseded blanket
publisher-letter rules are not real source restrictions; actual restrictions
and unresolved material questions remain protected under §7.

### Different definitions of done

- **Engineering verified:** actual caller and old-path migration complete,
  relevant checks pass at the final revision, and any retained compatibility
  route is justified and bounded.
- **Operational verified:** *when release is authorized*, a genuine source
  through delivery and appropriate live readback succeed, with failure
  recovery and legitimate holds protected.
- **Research delivered:** *when the assignment is a research capability*,
  a usable, source-grounded output passes the appropriate independent check.

These are different states. Do not substitute merged PRs, documents, test
counts, successful collectors, or readiness percentages for later states.
Stop at the assigned phase; no implicit production authorization.

## Execution and stop rules

- Use an isolated worktree. Read current owner decisions and relevant code/PRs
  once; verify changing state when necessary. Coordinate any essential private
  companion explicitly; do not touch unrelated repositories or another worktree.
- Before building a workaround, use the skills, tools, MCP servers and agents
  actually available in the session. A configured integration is unverified
  until it works; report a missing one instead of reimplementing it.
- Scope one coherent phase with `docs/desks/CHANGE_TEMPLATE.md`. Use focused
  development checks and required CI on the final exact revision. Stop when
  that phase is verified; do not expand into unrelated fixes or deployment.
- Routine eligible machine records run unattended under actual standing
  rights/quality/spend/activation authority. Hold real exceptions individually.
  English originals need no translation; unknown profiles never use China by
  fallback. Briefs and human-controlled editorial work keep their approvals.
- Preserve exact source identities, immutable evidence/version hashes, accepted
  paid output, retry/spending history, URLs/citations and source-specific holds.
  Never invent text, translations, titles, dates, units, ranks, claims or review.
- Never defeat publisher access controls, impersonate a browser or route around
  robots restrictions. Private custody does not itself grant model/public reuse.
- Never hand-edit generated `output/` or canonical edition sidecars. The
  production renderer is `site/render.py`; deployment validator is
  `scripts/validate_output.py`, with 10 governed warnings at this baseline.
- Task/standing authority governs edits, commits and review PRs. Do not infer
  merge, new paid operation, production DB mutation, schedule activation,
  publication or outside contact. Reuse authority already given; do not ask again.
- Be explicit: policy adopted, code migrated, tested, merged, deployed and live
  verified are different states. This policy change does not migrate runtime.
- Keep continuity in code, commits, PRs and the current migration map. Report the
  exact result, verification and next action; use a fresh session for a substantial
  next phase. No serial rehearsal programs, readiness percentages or new launch
  prerequisites after authentic authorized acceptance.

The public identity is **Indo-Pacific Record**. Predecessor names are historical
provenance only. Human Briefs and historical issues retain their genuine bylines,
approvals and original publication attribution under the current IPR shell.
