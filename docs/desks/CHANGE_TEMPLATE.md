# Bounded desk-system change

Use this as the task/PR body for one coherent engineering phase. It is a scope
and review aid, not another release approval gate. The [desk standard](README.md)
governs every desk; consult [current migration boundaries](MIGRATION.md).

## Objective and stop condition

State one concrete shared mechanism or source integration, the behavior that
changes, and the observable point at which this phase is complete. Identify
whether this is policy, runtime migration or authorized release work. Do not
extend into unrelated bugs, models, sources, releases or follow-on features.

## Repository state

- Public repo, base SHA, isolated branch/worktree and relevant existing PRs.
- Essential private companion and its base SHA, if assigned; no private evidence
  in the public body. Existing paths/callers and accepted output to preserve.
- Current source-use decisions, spending/retry bounds and runtime activation.
  Link authoritative records; do not transcribe new grants into the task.

## Implementation

- Which source definition, permitted components and existing shared modules are
  used? Which source-specific adapter/profile/check is actually necessary?
- Which real callers move, and which replaced active path or trigger retires?
  If one must remain, give the precise temporary compatibility reason.
- How are identity, immutable versions, checkpoint/resume, signed handoff,
  public-field projection and atomic writes preserved as applicable?
- No new country-specific engine, corpus, signing framework or renderer. A
  competing mechanism requires the owner-decided exception in the desk standard.

## Verification

Use targeted checks while implementing and applicable final-revision CI. Test
meaningful risks: duplicate/revision replay, budget continuity, genuine holds,
forbidden-field rejection, interrupted-stage recovery and common public-view
parity. Use isolated DBs and fixed evidence; valid corpus growth must not fail.
Do not add a test workflow or repeat paid generation for accepted results.

Runtime/CI separation changes must verify trusted qualification identity,
invalidation, missing/failed-receipt rejection and runtime projection gates before
replacing any existing full-suite gate. Current requirements remain until then.

## Delivery and handoff

Report exact PR/SHA, checks, replacement/removal, limitations and next action.
Distinguish built, tested, merged, deployed and verified live. Release only within
actual task/standing authority; otherwise stop at the reviewable implementation.
When release is authorized, reconcile one authentic source-to-HTTPS result,
representative failure/recovery and unattended continuation. No arbitrary wait,
per-record approval ritual, additional backfill program or readiness percentage.
