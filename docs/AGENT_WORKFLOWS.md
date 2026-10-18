# Agent Workflows & Model Routing — Indo-Pacific Record

How future Claude sessions allocate models, skills, and agents, and the
constraints every agent works under. Durable.

## 0. Documentation hierarchy

An agent reads down this list and stops at the document that governs the change
it is making. Do not restate one document's content inside another.

| Document | Governs |
|---|---|
| `README.md` | public and contributor overview |
| `PROJECT_STATE.md` | current operational snapshot and immediate handoff |
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, editorial standard, provenance, publication principles |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | technical layer map, commands, publishing and deployment |
| `docs/AGENT_WORKFLOWS.md` (this file) | agent operating constraints and model routing |
| `docs/ROADMAP.md` | older priority context; verify current owner decisions |
| `DECISION_LOG.md` | durable decisions that constrain future work |
| Git history | superseded state and incident history |

`PROJECT_STATE.md` is a **current snapshot, not a diary**. Update it in place
and let Git hold the previous version; do not append a new dated section for
every session.

## 1. Model routing

### Fable (or the strongest available tier)
Product direction, information architecture, design-system decisions,
flagship-visual design judgment, cross-route refactors, rendered-output
design review, tradeoff resolution, final integration review, roadmap
re-planning, edits to the durable docs (docs/*.md doctrine files).
**Do not spend Fable on:** repetitive CSS edits, page regeneration,
mechanical consistency fixes, log reading.

### Sonnet (default implementation model)
Implementing ROADMAP tickets, template/CSS/SVG/JS work inside an approved
spec, generator changes, responsive and accessibility fixes, re-render +
validate loops, documentation updates tied to implementation, bounded
refactors, test/validation runs.

### Haiku / lightweight
File and route inventory, repeated-pattern searches, link checking, log and
validator-output summarization, screenshot batch triage. Never let a
lightweight model decide design direction, editorial meaning, or
architecture.

### Standing rules (any model)
- At session start, read latest relevant owner decisions and targeted
  PROJECT_STATE.md handoff sections; verify time-sensitive claims against
  real sources, current code, PRs, Actions and output. Update the snapshot
  only when you own it and the task makes a meaningful change.
- Editorial-integrity rules (PRODUCT_AND_EDITORIAL_DOCTRINE §4) bind every
  model at every tier: never invent Chinese text, translations, dates,
  ranks, sources, or claims — in code, copy, tests, or fixtures.
- The assignment may authorize edits, tests, commits, pushes and a review
  PR. Reuse valid standing permissions, but never infer approval to merge,
  spend, change production, activate schedules, publish or send messages.
- Never hand-edit `output/`; never modify `pla_watch.db` outside the pipeline;
  never modify shadow branches, ledgers or stored shadow records.
- Never defeat a source's access challenge, impersonate a browser, or route
  around `robots.txt`, however much coverage it would unlock.
- Never silently promote or overclaim source coverage. Under the October 18
  owner decision, seven-/30-day histories are ongoing reliability evidence,
  not universal launch waiting periods. Preserve rights, legitimate human
  review and independent real-record release gates.
- The production renderer is `site/render.py`; the deploy gate is
  `scripts/validate_output.py`, whose governed baseline is **10 warnings**.
  A new warning is explained, never invented away.
- **Do not invent facts to fill a documentation gap.** State the uncertainty
  and name the authoritative source — the database, the ledger, the registry,
  the workflow file, or Git history.

## 1a. Complete-desk engineering and acceptance

Work on one assigned desk and its approved source families, not another
qualification program. Begin with primary publisher listings and details,
private captured original bytes/Git versions, authentic human decisions,
Actions attempts (including failures), production SQLite rows, rendered pages
and deployed HTTPS where authorized. Repository summaries and old PRs are
navigation aids, not independent proof of operation.

Close the existing source → protected capture → translation/processing →
screening and analysis → approved admission → public/Archive and editorial
intake → scheduled maintenance/recovery path. A functioning agreed contract
is the completion standard; no reduced source scope, arbitrary date gate,
readiness percentage or cosmetic status card substitutes for it. Do not force
weak releases into articles or label machine output human reviewed.

Independently identify expected official records from a bounded source window;
reconcile them through storage, processing, database and page. Exercise a real
eligible record, malformed or unavailable input, duplicate/revision, absent
approval, atomic rollback, private leakage and idempotent recovery. Distinguish
replay, manual rehearsal, and genuine scheduled operation. Human review or
full-text reuse cannot be inferred from a green test or link permission.

Reuse existing collectors, vault, DB, validation, rendering, monitoring and
model clients. Discover skills/connectors once and use only those relevant to
a concrete need; targeted Git/rg/Python/SQLite/GitHub/browser reads beat broad
scans and repeated model calls. One isolated worktree and one owner of shared
files. Avoid speculative architecture, duplicate verification frameworks,
overlapping PRs and unrelated fixes. Run focused checks during implementation
and required full checks once the candidate stabilizes.

Deliver one coherent reviewable PR (and a private companion only if needed),
grounded SHAs and run/source/output evidence, normal schedule/recovery and the
smallest unresolved owner action. Stop at an operational desk or a verified
candidate with a specific real external blocker. Start substantial subsequent
phases in a new agent session with a concise checkpoint. See October 18
`DECISION_LOG.md` ruling and issue #673.

## 2. Skills

| Skill | Use for | Not for |
|---|---|---|
| **ui-ux-pro-max** | IA and flow changes, navigation, responsive layout patterns, component behavior review | visual taste decisions (defer to doctrine) |
| **impeccable** | final visual refinement passes on rendered pages: typography, spacing, alignment, hierarchy; live-browser iteration | inventing new direction; anything conflicting with DESIGN_SYSTEM.md |
| **design-taste-frontend / taste review** | art-direction checks; catching generic/template drift before it lands | replacing the north star |
| **awesome-design-md / skillui** | keeping design documentation synchronized after approved visual changes | generating auto-extracted token dumps as doctrine (the 2026-07 skillui extraction was inaccurate and was retired — DESIGN_SYSTEM.md is authoritative) |
| **Journalism skills** (fact-check-workflow, source-verification, newsroom-style, ai-writing-detox/humanizer) | editorial passes on edition prose, headline/dek treatment, corrections handling, evidence presentation | rewriting published editions without the analyst |
| **graphify** | architecture/where-should-I-edit questions (`graphify-out/GRAPH_REPORT.md` first, then targeted rg); refresh with `graphify update .` after structural changes | decorative relationship visuals for the site |
| **Ruflo (swarm)** | genuinely parallel work only — e.g., one agent per route family in a multi-route implementation, or research/verification/QA role separation on a publish | single-file fixes, nav changes, README edits, routine build errors |
| **Headroom / TokenSave** | compressing long validator logs, screenshot batches, repeated repo inspection | authoritative reading of Chinese text, translations, dates, ranks, claims |

Ruflo limits: max 4 agents; one owner per template file (`base.html`,
`pla-watch-base.html`, and `pw_env.py` are single-owner, never concurrent);
the lead session integrates and is the only writer of PROJECT_STATE.md.

## 3. Project agents (`.claude/agents/`)

Minimum useful set — three agents plus one human-in-the-loop role:

- **Design Director** — *not an agent file.* This is the Fable-led main
  session role: reviews rendered output against DESIGN_SYSTEM.md +
  VISUAL_AND_MOTION_SYSTEM.md, approves/rejects visual work, updates
  doctrine. Runs before any design release is called done.
- **frontend-implementer** (Sonnet) — implements one bounded ticket:
  templates/CSS/SVG/JS + regenerate + validate + screenshot proof. Stays
  inside the ticket's file list.
- **editorial-integrity-reviewer** (Sonnet, read-only) — source-to-claim
  tracing, evidence-vs-inference presentation, verbatim Chinese text,
  citation and metadata accuracy. Output: pass/fail findings list.
- **release-qa** (Sonnet) — pre-deploy sweep: validator, preview, responsive
  (1280/375), keyboard + focus, reduced motion, console errors, link spot
  checks. Output: go/no-go report with evidence.

## 4. Project commands (`.claude/commands/`)

- **/publish-edition** — the brief workflow end to end (scaffold → schema/readiness
  checks → editorial QA/private rendered review → authorized approval → render
  and existing release path; stop only when actual approval is missing).
- **/release-check** — the release-qa sweep on demand.

Commands encode the repeatable workflow; agents supply the reviewer roles.
Do not add more agents/commands without a recurring need that a doc line
cannot serve.
