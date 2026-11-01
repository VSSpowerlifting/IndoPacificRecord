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
| `docs/AGENT_WORKFLOWS.md` (this file) | agent operating constraints, model routing and the task → capability map |
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

## 2. Task → capability map

Capabilities come in four layers. Only the first travels with the repository;
the others vary by machine, account and session, so a session uses them when
they are actually present and otherwise takes the fallback. A tool's presence
never authorizes its external actions. Summarized or compressed tool output
is not authoritative evidence for a
quotation, original-language text, date, rank or figure. Original-source output
must retain its source identity and be checked against the actual source.

- **Repo-tracked** — the shared skills `ipr-source-integrity`, `ipr-design` and
  `ipr-proposal-review`, the agents in §3, the commands in §4, and the domain
  scripts. They travel with the checkout; verify discovery in the actual runtime.
- **Plugin skills** — generic design, writing and research skills installed
  in the session. Optional; they refine within IPR doctrine, never override it.
- **User-level** — Ben's own `ben-*` skills (e.g. `ben-ipr-brief`,
  `ben-source-verify`, `ben-review-change`). Present only in Ben's sessions;
  the repo never depends on them.
- **MCP connectors** — web search/Firecrawl, browser/Playwright, code graphs,
  Context7, Vercel, Notion. Read-only use is ordinary; writes need the
  authorization `AGENTS.md` requires.

| Task | Start with (tracked) | Optional helpers | Fallback |
|---|---|---|---|
| Brief drafting and Sunday selection | `ipr-source-integrity`; `docs/BRIEFS_WEEKLY_SELECTION.md`; `/publish-edition` | `ben-ipr-brief`; newsroom-style, humanizer | the doc's procedure and `scripts/author_brief.py` |
| Fact-check, claim and translation review | `ipr-source-integrity`; **editorial-integrity-reviewer** | `ben-source-verify`; fact-check-workflow, source-verification | hand-built claim ledger from `EDITORIAL_QA_CHECKLIST.md` |
| Research discovery for a Brief or dossier | `ipr-source-integrity` (authority rule) | web search, Firecrawl, deep-research | preserved IPR record plus the original source; discovery never substitutes for either |
| Desk source acquisition | `docs/desks/README.md`, `docs/desks/MIGRATION.md`, the source's decisions | Firecrawl/browser for reading permitted pages | the shared desk path; never defeat access controls |
| Dossiers and evidence timelines | `ipr-source-integrity`; `docs/LIVING_DOSSIERS.md`, `docs/EVIDENCE_TIMELINES.md` | — | `scripts/dossier.py`, `scripts/validate_timelines.py` |
| Challenge a material expansion, source-permission or AI-model change | `ipr-proposal-review`; **proposal-reviewer** | — | the four-part growth rule in `AGENTS.md` |
| Brainstorming and product direction | `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` §1b, `docs/ROADMAP.md` | brainstorming skills | strongest-model lead session; the growth rule in `AGENTS.md` decides admission |
| UI, templates, motion, reader experience | `ipr-design`; **frontend-implementer** | ui-ux-pro-max (IA/flow), impeccable (rendered refinement), design-taste-frontend (drift check) | `docs/DESIGN_SYSTEM.md` + 1280/375 browser check |
| Code navigation and impact | targeted `rg` and file reads | TokenSave, Serena, graphify (only if a current `graphify-out/` exists) | targeted `rg`; graphs guide, source code decides |
| Code review before a PR | full-diff self-review; `docs/desks/CHANGE_TEMPLATE.md` | `ben-review-change`; code-review skills | focused tests plus exact-revision CI |
| Release and rendered QA | **release-qa**; `/release-check` | Playwright / browser pane | `scripts/validate_output.py` (10 governed warnings) |
| Project state and memory | `PROJECT_STATE.md` (in place), `DECISION_LOG.md`, the PR body | Notion or local memory, as personal aids only | tracked files; untracked memory never overrides them |
| Long logs and repeated output | — | Headroom, TokenSave | read the raw output for anything that decides correctness |

Retired, so they do not route work: **Ruflo** swarm orchestration (not
installed; ordinary subagents cover the rare parallel case) and
**awesome-design-md / skillui** extraction (the 2026-07 auto-extracted tokens
were inaccurate; `DESIGN_SYSTEM.md` is authoritative). The untracked local
`pla-watch-live-design` skill is superseded by `ipr-design`.

Shared repository skills have one canonical copy in `.agents/skills/<name>/`,
which Codex reads directly; Claude sees it through the tracked symlink
`.claude/skills/<name>`. Edit only the `.agents` copy.

**Code-index freshness.** TokenSave and graphify index one checkout at one
time. Before relying on them, check TokenSave's `active_branch`/last-sync
(`tokensave_status`) against the branch you are on; if they differ, use
`rg` and the source files. Index results never settle a correctness question.

Parallel agents: only for genuinely independent work, at most four at once;
one writer per file, and `base.html`, `pla-watch-base.html` and `pw_env.py`
are single-owner, never concurrent. The lead session integrates and is the
only writer of PROJECT_STATE.md.

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
  text, citation and metadata accuracy for editions, Briefs, dossiers and
  timelines. Open the database read-only. Output: findings, unchecked claims
  and PASS/FAIL limited to checks actually performed. Use on held Sunday
  drafts and assigned editors' returns as well as before publication.
  Retrieve permitted originals or hand off to an available research-capable
  session; routine source checks do not default to the owner. This agent
  advises; it cannot clear holds, approve, number, publish or send.
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
Do not add more agents, commands or project skills without a recurring need
that a doc line cannot serve.
