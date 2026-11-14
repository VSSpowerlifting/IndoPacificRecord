# Agent workflows — minimal routing only

This is a *tool-selection note*, not a parallel policy book or a project
memory. Start with [AGENTS.md](../AGENTS.md), and for Claude with
[CLAUDE.md](../CLAUDE.md). For desk work read
[shared architecture](desks/README.md), the applicable
[migration row](desks/MIGRATION.md), and exact current source rights.
Current work lives in real GitHub issues/PRs, code, Actions, custody
evidence and deployed readback—not a dated status note.

## Choose the smallest suitable execution mode

- **Strong reasoning/design model:** trade-offs, product direction, editorial
  judgment support, architecture, visually reviewing rendered UI, and
  reconciling consequential governance questions. Human founder approval
  still governs human-controlled publications and reserved commitments.
- **Implementation model:** one coherent, bounded code objective; actual
  repository inspection, implementation, targeted tests and exact-head CI.
  Stop at the authorized phase rather than expanding into another feature,
  deployment or cleanup.
- **Lightweight model:** targeted inventories, file/link searches, log
  summaries and mechanical checks. It does not independently clear source
  rights, approve editorial claims or certify authentic originals.

Available models, plugins, commands and skills can change; inspect what
is actually installed instead of treating old model names, agent counts,
skills lists or token budgets in repository history as current state.
Parallel agents require independent file ownership and clear integration.

## Existing repository agents and commands

The actual available agent definitions are in `.claude/agents/`;
repository-owned skills are in `.agents/skills/`; optional commands
are in `.claude/commands/`. Invoke them only when they materially
help the current objective. A role or command name alone never supplies
source evidence, independent human review, an approval or a release.

Use `docs/ROADMAP.md` for durable priorities and the appropriate issue/PR
for short-term work. Preserve decisions in `DECISION_LOG.md` and source
governance in its exact policy; do not copy them here. Retire superseded
paths after proven parity and preserve real historic audit evidence in Git.

## Task → capability map

Capabilities come in four layers. Only the first travels with the repository;
the others vary by machine, account and session, so a session uses them when
they are actually present and otherwise takes the fallback. A tool's presence
never authorizes its external actions, and no tool output is evidence for a
quotation, original-language text, date, rank or figure.

- **Repo-tracked** — the shared skills `ipr-source-integrity`, `ipr-design` and
  `ipr-proposal-review`, the agents in `.claude/agents/`, the commands in
  `.claude/commands/`, and the domain scripts. Every session gets these.
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
| Current state and decisions | GitHub issues/PRs, `DECISION_LOG.md`, the PR body | Notion or local memory, as personal aids only | tracked files and live evidence; untracked memory never overrides them |
| Long logs and repeated output | — | Headroom, TokenSave | read the raw output for anything that decides correctness |

Retired, so they do not route work: **Ruflo** swarm orchestration (not
installed; ordinary subagents cover the rare parallel case) and
**awesome-design-md / skillui** extraction (the 2026-07 auto-extracted tokens
were inaccurate; `DESIGN_SYSTEM.md` is authoritative). The untracked local
`pla-watch-live-design` skill is superseded by `ipr-design`.

Shared repository skills have one canonical copy in `.agents/skills/<name>/`,
which Codex reads directly; Claude sees it through the tracked symlink
`.claude/skills/<name>`. Edit only the `.agents` copy. `base.html`,
`pla-watch-base.html` and `pw_env.py` are single-owner, never edited by
concurrent agents. Do not add more agents, commands or project skills
without a recurring need that a doc line cannot serve.

**Do not re-create** `PROJECT_STATE.md` as an append-only session diary,
duplicated per-desk plans, repeated readiness checklists, a manual
"approved" status matrix, or speculative saved-ideas backlogs.
