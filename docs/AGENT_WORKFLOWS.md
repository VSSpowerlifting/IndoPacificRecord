# Agent Workflows & Model Routing — Indo-Pacific Record

How future Claude sessions allocate models, skills, and agents, and the
constraints every agent works under. Durable.

## 0. Documentation hierarchy

Start with root `AGENTS.md`: the canonical instruction entrypoint and growth
admission rule. Follow only the domain authority relevant to the assignment.
`CLAUDE.md` adds Claude-specific operation, not a competing policy. Dated
status and past roadmaps do not override real source restrictions or current
owner decisions. Do not duplicate one document's rules inside another.

| Document | Governs |
|---|---|
| `AGENTS.md` | canonical agent instructions, growth admission, stop/completion rules |
| `CLAUDE.md` | Claude-specific implementation notes only |
| `README.md` | public and contributor overview |
| `PROJECT_STATE.md` | current operational snapshot and immediate handoff |
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, editorial standard, provenance, publication principles |
| `docs/desks/README.md` | mandatory all-desk architecture and completion; overrides older generic desk procedures |
| `docs/desks/MIGRATION.md` | existing integration boundaries and next bounded phase; verify current code |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | existing technical layer map, commands, publishing and deployment |
| `docs/AGENT_WORKFLOWS.md` (this file) | agent operating constraints and model routing |
| `docs/ROADMAP.md` | active strategic sequence, not a dated status ledger |
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
- Start with current owner rulings and targeted PROJECT_STATE.md sections.
  Verify operational claims against real source records, latest code, PRs,
  Actions and site output. Update PROJECT_STATE only for meaningful changes
  and only when its ownership is coordinated.
- Editorial-integrity rules (PRODUCT_AND_EDITORIAL_DOCTRINE §4) bind every
  model at every tier: never invent Chinese text, translations, dates,
  ranks, sources, or claims — in code, copy, tests, or fixtures.
- An explicit engineering task may authorize tests, commits, pushes and a
  review PR. Reuse legitimate standing approvals; don't infer permission for
  merge, paid model operation, production mutations, schedule activation,
  publication or external communication.
- Never hand-edit `output/`; never modify `pla_watch.db` outside the pipeline;
  never modify shadow branches, ledgers or stored shadow records.
- Never defeat a source's access challenge, impersonate a browser, or route
  around `robots.txt`, however much coverage it would unlock.
- Never call a shadow desk complete or promote it automatically. The owner-approved
  2026-10-18 standard requires end-to-end real-source operation, a tested
  failure/recovery, verifiable publication, and an explicit release decision.
  Seven-/30-day streaks are ongoing reliability measurements, not automatic
  prelaunch holds. Retain historical checkpoint evidence and human review.
  See docs/engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md.
- The production renderer is `site/render.py`; the deploy gate is
  `scripts/validate_output.py`, whose governed baseline is **10 warnings**.
  A new warning is explained, never invented away.
- **Do not invent facts to fill a documentation gap.** State the uncertainty
  and name the authoritative source — the database, the ledger, the registry,
  the workflow file, or Git history.

## 1a. Mandatory shared desk implementation

Every Codex/Claude session, project agent and assigned private companion follows
`docs/desks/README.md` for China, Singapore, Korea, Philippines, Indonesia,
Vietnam, Japan, the US reference desk and future sources. It replaces divergent
country lifecycle plans. Root `AGENTS.md` and `CLAUDE.md` are durable tracked
coding memory; stale local memories, chat recaps and historical plans cannot
reinstate superseded launch waits or competing pipelines.

Start with the relevant current-code row in `docs/desks/MIGRATION.md` and one
bounded task using `docs/desks/CHANGE_TEMPLATE.md`. Reuse shared mechanisms,
keep genuine source checks as extensions, route real callers, and retire the
replaced active path when parity is proved. One logical record has optional
permitted components; private originals do not become public by normalization.
Do not add unused registries, duplicate signing/queue engines, country renderers,
per-record owner rituals, new qualification programs or another monitor when an
existing signal suffices.

Separate qualification, ingestion and delivery in the implemented design; preserve
current CI until the trusted replacement exists. Use fixed evidence/isolated DBs,
focused development checks and required final-revision CI. A growing valid corpus
must not break the next run. Rights, unsafe writes, version/dedup and spend remain
negative-test boundaries. No repeated paid generation of accepted outputs.

Distinguish policy, implementation, CI, merge, deploy and verified live operation.
Stop at the assigned phase: one reviewable implementation and an essential private
companion only where needed, or an authorized verified release. No unrelated
features, fixes or release follow-on. Record SHA/PR, checks, removed path and exact
next action in repository state; use a fresh session for a substantial next phase.

## 2. Skills and tools

List only what has been seen working here. Rows marked *user-level* live in
the owner's Claude setup, not this repository; Codex does not have them and
no workflow may depend on them.

| Skill / tool | Use for | Not for |
|---|---|---|
| **ui-ux-pro-max** | IA and flow changes, navigation, responsive layout patterns, component behavior review | visual taste decisions (defer to doctrine) |
| **impeccable** | final visual refinement passes on rendered pages: typography, spacing, alignment, hierarchy; live-browser iteration | inventing new direction; anything conflicting with DESIGN_SYSTEM.md (authoritative; auto-extracted token dumps are not doctrine) |
| **design-taste-frontend / taste review** | art-direction checks; catching generic/template drift before it lands | replacing the north star |
| **Journalism skills** (*user-level, optional*: fact-check-workflow, source-verification, ben-source-verify, newsroom-style, ai-writing-detox/humanizer) | claim ledgers and style passes on Brief prose, headline/dek treatment, corrections | approval; rewriting published editions without the analyst |
| **ipr-proposal-review** (shared, `.agents/skills/`) | read-only PROCEED/SIMPLIFY/DEFER/REJECT challenge of a material expansion, source-permission or AI-model change | routine fixes; line-by-line diff review (use `/code-review` or `codex review`) |
| **Playwright** (MCP) | rendered checks of `output/` at 1280/375, keyboard, console errors | publisher sites behind access challenges |
| **Serena / TokenSave** (MCP) | symbol lookup, callers and impact before editing Python | trusting results before checking the index branch (below) |
| **Firecrawl** (MCP) | discovering public background sources while researching a Brief | collection (the pipeline collects), or any site whose terms or challenges forbid it |
| **`gh` CLI** | PR, CI and Actions-run inspection | merging, enabling workflows, or editing repository variables without authorization |
| **Headroom** | compressing long validator logs and repeated inspection output | authoritative reading of original-language text, translations, dates, ranks, claims |
| **graphify** | orientation only: `graphify-out/` exists only in the main checkout and was last built from an older branch | edit decisions; trust current code and `rg` instead |

Shared repository skills have one canonical copy in `.agents/skills/<name>/`,
which Codex reads directly; Claude sees it through the tracked symlink
`.claude/skills/<name>`. Edit only the `.agents` copy.

**Code-index freshness.** TokenSave and graphify index one checkout at one
time. Before relying on them, check TokenSave's `active_branch`/last-sync
(`tokensave_status`) against the branch you are on; if they differ, use
`rg` and the source files. Index results never settle a correctness question.

**Parallel agents.** Use a few agents only for genuinely independent work.
`base.html`, `pla-watch-base.html` and `pw_env.py` have one owner at a time,
never concurrent writers; the lead session integrates and is the only writer
of PROJECT_STATE.md. (The former Ruflo swarm runtime is retired; Claude Code
subagents cover this.)

## 3. Project agents (`.claude/agents/`)

Minimum useful set — four agents plus one human-in-the-loop role:

- **Design Director** — *not an agent file.* This is the Fable-led main
  session role: reviews rendered output against DESIGN_SYSTEM.md +
  VISUAL_AND_MOTION_SYSTEM.md, approves/rejects visual work, updates
  doctrine. Runs before any design release is called done.
- **frontend-implementer** (Sonnet) — implements one bounded ticket:
  templates/CSS/SVG/JS + regenerate + validate + screenshot proof. Stays
  inside the ticket's file list.
- **editorial-integrity-reviewer** (Sonnet, read-only) — source-to-claim
  tracing, evidence-vs-inference presentation, verbatim original-language
  text for every desk, citation and metadata accuracy. Output: findings,
  unchecked claims and a PASS/FAIL on the checks it could run. Beyond
  `/publish-edition`, Ben may run it on a held Sunday draft before
  `scripts.sunday_send_reviewed_packet`, or on Dylan's return after
  `scripts/validate_editorial_return.py`. It is **advisory**: a model reading
  the stored record, not independent verification, and it cannot clear a
  hold, approve or send.
- **release-qa** (Sonnet) — pre-deploy sweep: validator, preview, responsive
  (1280/375), keyboard + focus, reduced motion, console errors, link spot
  checks. Output: go/no-go report with evidence.
- **proposal-reviewer** (inherits the lead model, read-only) — runs
  `ipr-proposal-review` in fresh context so the producer's reasoning does not
  anchor the verdict. Holds no rules of its own.

## 4. Project commands (`.claude/commands/`)

- **/publish-edition** — the brief workflow end to end (scaffold → schema/readiness
  checks → editorial QA/private rendered review → authorized approval → render
  and existing release path; stop only when actual approval is missing).
- **/release-check** — the release-qa sweep on demand.

Commands encode the repeatable workflow; agents supply the reviewer roles.
Do not add more agents/commands without a recurring need that a doc line
cannot serve.
