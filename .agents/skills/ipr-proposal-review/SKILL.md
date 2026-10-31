---
name: ipr-proposal-review
description: Read-only skeptical review of a substantial IPR proposal (new subsystem, desk mechanism, model workflow, data store, reader surface, collector, source-permission or AI-model change) that ends in PROCEED, SIMPLIFY, DEFER or REJECT. Use when asked to challenge, critique or second-guess a plan, or before starting a material expansion as defined in AGENTS.md. Not for routine bug fixes or line-by-line diff review.
---

# IPR proposal review

The proposal is the user's request, the named issue or PR, or the text passed
to this skill. `AGENTS.md` remains the authority; this skill applies it.

## Rules of the review

- **Read-only.** Do not edit files, commit, push, comment, run collectors,
  renderers or paid models, or change databases, schedules or settings. Use
  `git status/log/diff/show`, `gh pr view`/`gh issue view`, `rg` and file reads.
- **Evidence before conclusions.** Inspect the repository before saying how
  something works or whether it already exists. Cite files, PRs or command output.
- **Do not manufacture criticism.** A sound proposal gets PROCEED, said plainly.
  Preference, novelty or size alone is not a finding.
- **Disagree once, clearly, then step aside.** State the disagreement with its
  evidence. The verdict is advice to the owner, not a gate; the owner can
  authorize an exception.
- **Safeguards are constraints, not vetoes.** An improvement that keeps them
  intact is not blocked for being new.

## 0. Is a review warranted?

AGENTS.md exempts routine bugs, incident recovery, source-specific protections,
security fixes and low-risk accessibility work; copy fixes and work inside an
already-bounded task need no review either. Reply in one line,
`No proposal review needed: <reason>`, and stop.

Not exempt, even when framed as a fix: changes to source rights, permissions or
activation; AI model, prompt, evaluation, fallback or budget changes; anything
altering accepted records or what is published. Review those rigorously.

## 1. Objective

State the actual research, reader or reliability outcome sought, not the
proposed mechanism, and how success would be checked. If no objective can be
stated from the evidence, say so; that alone usually means DEFER.

## 2. Repository facts

Inspect what the proposal touches: current code paths, the relevant row of
`docs/desks/MIGRATION.md`, `docs/desks/README.md`, `DECISION_LOG.md`, open PRs
and issues in the same area, and existing tests or CI. Report three lists:

- **Verified:** with file, PR or command evidence.
- **Inferred:** reasoning not yet checked.
- **Unknown:** and the cheapest way to resolve it.

## 3. Reuse and alternatives

Compare at least: the proposal as stated; the simplest version that meets the
objective (often extending an existing mechanism); and no change. Name the
existing component that could absorb the need. Apply the 30 October owner
decision: no new per-country engine, queue, signing framework, corpus or
renderer, and the replaced active path is retired rather than duplicated.

## 4. Costs and risks

Only what applies: implementation effort; ongoing maintenance and accountable
owner; runtime and model cost (calls, retries, budgets); failure mode and its
effect on captures and the last verified site; reliability; and opportunity
cost, meaning the research work it displaces.

## 5. IPR safeguards

For each safeguard the proposal touches, say preserved, at risk or unknown:

- Source provenance, rights, permissions and activation (rights, display status
  and activation are separate; private evidence stays private; publisher access
  controls are respected).
- Data custody and publication accuracy (exact source identities, hashes,
  citations; no invented text, translations, dates or claims).
- AI evaluation, acceptance, fallback and budget (evidence of evaluation, bounded
  spend, no repeated paid generation of accepted output; model agreement or
  schema success is not factual review).
- Shared desk architecture (`docs/desks/README.md`).
- Production reliability (qualification, ingestion and delivery stay separate;
  current CI gates and the validator warning baseline hold).
- Accepted records and outputs (no hand-edited `output/` or canonical sidecars).

For a source-permission or AI-model change, require the primary evidence (the
grant or policy text, evaluation results) rather than the proposal's summary.

## 6. Verdict

- **PROCEED:** justified as stated. Name the bounded scope and stop condition
  using `docs/desks/CHANGE_TEMPLATE.md`.
- **SIMPLIFY:** the objective is valid, but a smaller or reused design meets it.
  Specify that design.
- **DEFER:** the objective or evidence is insufficient now. Name what would
  unlock it.
- **REJECT:** it duplicates an existing capability, conflicts with an owner
  decision or safeguard, or costs more than it returns. Cite which.

Use only these four. If the proposal bundles separable changes, give each part
its own verdict line rather than a combined or new label.

```text
Verdict: PROCEED | SIMPLIFY | DEFER | REJECT
Objective:
Verified / Inferred / Unknown:
Options compared (proposal, simpler, no change):
Costs and risks:
Safeguards:
Scope and stop condition (PROCEED or SIMPLIFY):
Strongest counterargument to this verdict:
Evidence that would change it:
```

Keep it to what the decision needs. For a material expansion, the verdict
belongs in the existing issue or PR body; do not create a separate document.

## Completion check

When asked whether finished work matches its proposal, compare the claimed
state with the AGENTS.md definitions of done (engineering verified, operational
verified, research delivered) and check the shipped scope against the verdict
and stop condition. For line-by-line diff review, use the existing review tools
(Claude Code `/code-review`, `codex review`) rather than this skill.

## Fresh context

For a substantial proposal, run the review in a separate read-only context so
the producer's reasoning does not anchor it. Pass the objective and pointers
(issue, PR, files), not your own conclusion.

- Claude Code: the `proposal-reviewer` agent.
- Codex: a spawned subagent told to use this skill, or
  `codex exec --sandbox read-only --ephemeral "Use the ipr-proposal-review skill on: <proposal>"`.
