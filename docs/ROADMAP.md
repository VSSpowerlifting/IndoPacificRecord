# Roadmap — Indo-Pacific Record

**Active strategic priorities, approved 30 October 2026.** This is a short
forward plan—not a second architecture standard, release checklist, or
historical evidence ledger. Check source/activation state, PRs, Actions and
the actual public site when executing a task. The prior roadmap, including
historic Singapore review debt, screening measurements and pre-Briefs-15
publication planning, remains in Git history. It is **not** a current queue
or launch authorization.

The binding mission and growth test live in
[`docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md`](PRODUCT_AND_EDITORIAL_DOCTRINE.md)
§1b and [`AGENTS.md`](../AGENTS.md). The common desk architecture is
[`docs/desks/README.md`](desks/README.md); actual remaining migration
work is in [`docs/desks/MIGRATION.md`](desks/MIGRATION.md). Existing
source-specific permissions, spending limits, holds and human editorial
approvals remain authoritative.

## A. Finish shared architecture, retire duplication

- Complete real-caller migration of remaining desks and sources under the
  already-approved source/component lifecycle. The AFP/NSC/Kemhan
  source-definition pilot **merged as PR #928**; it did not finish
  all-desk migration.
- Remove replaced active dispatch/admission/publication branches after
  verified parity. Bound and document compatibility paths that must remain.
- Coordinate with public record grouping in open PR #895; don't establish
  a second grouping framework.
- Keep current qualification and Daily safeguards until an actually
  tested revision-aware replacement exists.

**Success means:** fewer active implementations; source-specific rights,
data, costs and holds preserved; real callers verified. Not a new
abstraction that nobody uses.

## B. Prove factual quality and operational reliability

- Complete genuinely independent, source-grounded factual/model-output QA,
  including known failures and withheld outputs. PR #890 contains an
  audit candidate, not a completed reviewer verdict.
- Keep model quality and model-routing decisions distinct. Open PR #919
  documents possible controls, not an approved unattended model swap.
  Lower cost, fluent style and schema validity alone are insufficient.
- Build the code qualification versus routine ingestion versus public
  delivery split as a **separate** engineering phase. Prove revision
  matching, invalidation, runtime invariants and last-good-site
  preservation before replacing any existing Daily CI gate.

**Success means:** independently measured errors and holds; bounded,
accountable spending; verified recovery and legitimate publication.

## C. Deliver distinctive research, then improve discovery

- Prioritize well-evidenced IPR Briefs and durable Dossiers using the
  collection already available. Do not equate additional records with
  additional independent insight.
- Strengthen source → record → Brief/Dossier navigation before building
  unrelated new presentation surfaces. Release a governed Timeline only
  when source and inference boundaries can be checked.
- Judge usefulness through rigorous sources, useful analytical findings,
  reader/editor feedback and recurring usage—not PR counts, corpus size
  or stylistic novelty alone.

**Success means:** consistently source-grounded analysis that policy
readers, researchers and journalists can actually use.

## Deferred unless explicitly justified

New standalone country engines, general-purpose agents, major visual
redesigns, speculative model systems, redundant stores/workflows,
unbounded country expansion and unrelated dashboard-like features. A
material exception requires the **existing** issue/PR body to show a
specific reader/research need, reuse analysis, accountable maintenance
and rights/quality/cost, opportunity cost and retired machinery,
as specified in `AGENTS.md`. Routine defects, access safeguards,
security work and already-authorized research remain in scope.

## Maintain this file, do not accumulate it

Update these priorities in place when the owner changes direction.
Put code boundaries in `docs/desks/MIGRATION.md`, actual operational
snapshots in `PROJECT_STATE.md` (verified against current evidence),
durable decisions in `DECISION_LOG.md`, and historic plans in Git
history. Do not append a dated project diary, additional readiness
program, procedural checklist or CI gate to this roadmap.
