# Agent Operating Rules — Indo-Pacific Record

Read `CLAUDE.md` for repository operation. For **any desk work**, first read
[`docs/desks/README.md`](docs/desks/README.md), the mandatory all-desk standard,
and the relevant row of [`docs/desks/MIGRATION.md`](docs/desks/MIGRATION.md).
These tracked files are durable Codex/Claude project memory. Do not substitute
old chat history, local auto-memory or a dated rollout plan for current rules.

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

### Documentation authority by subject

| Subject | Governing reference |
|---|---|
| Mission, audience, editorial/evidence trust, growth decisions | `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md`, explicit current owner decisions |
| Source-owned all-desk architecture | `docs/desks/README.md`; verified next code phase in `docs/desks/MIGRATION.md` |
| Source-specific rights, custody, holds, spending, approval | Actual applicable policies and grants; `DECISION_LOG.md` |
| Production and build verification | `docs/ARCHITECTURE_AND_PUBLISHING.md`, actual CI/workflows and code |
| Current strategic priorities | `docs/ROADMAP.md`, checked against real repo/source/site status |
| Agent instructions | This file; `CLAUDE.md` supplies only Claude-specific operating notes |
| Historic evidence and dated plans | Git history, `PROJECT_STATE.md`, older records; not current authority by default |

If references appear to conflict, preserve the stricter real evidence,
source-rights and activation control pending an explicit owner decision.
A general architecture or roadmap instruction never creates a source grant.

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
