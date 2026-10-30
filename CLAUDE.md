# Indo-Pacific Record — Claude Operating Rules

Independent, source-grounded monitoring and analysis of official Indo-Pacific
defense and security publication. Two layers under one masthead: the **record**
(automated preservation and rendering from `pla_watch.db`) and
**Indo-Pacific Record Briefs** (the human-controlled analytical collection).
Its existing issues were published as *The PLA Watch*, the China Desk's weekly
series: that is predecessor attribution they keep, and no new issue is
authored or published under it (DECISION_LOG 2026-09-23). Never "OSINT tool,"
never intelligence cosplay.

"China Mil Watch" is a **legacy name**: the predecessor identity, retired
2026-08-27. Use it only when describing history.

## Mandatory desk system — owner decision, 30 October 2026

Read [`docs/desks/README.md`](docs/desks/README.md) before any desk assignment.
It is the authoritative all-desk engineering contract, not an optional future
aspiration. Applies to China, Singapore, Korea, Philippines, Indonesia, Vietnam,
Japan, the US reference desk and all future sources, including assigned private
custody work. The tracked root `AGENTS.md` and this file are durable coding memory.

The three requirements are: **source definitions and optional permitted record
components; one shared lifecycle/admission/public interface; separate code
qualification, ingestion and delivery.** Source access, extraction, language,
terminology and necessary QA remain explicit adapters/profiles. Do not create
country-specific lifecycle machinery or leave a replaced active path alongside
an unused abstraction. Rights, display labels and runtime activation are distinct.

Use [`docs/desks/MIGRATION.md`](docs/desks/MIGRATION.md) for the actual existing
paths and the next bounded phase. Policy adoption is not runtime migration or
live verification. Current CI gates remain until a verified replacement exists.
Older common-architecture and launch-process instructions are superseded by the
standard; genuine source decisions, holds, spending limits and editorial approvals
are not. A desk's source scope does not expand merely to satisfy a checklist.

## Session start
1. For desk work, read `docs/desks/README.md` and the relevant migration row;
   check actual source-use/activation rulings in `DECISION_LOG.md` and the
   existing acceptance policy, then read relevant
   `PROJECT_STATE.md` sections and verify dated status against real code,
   open PRs, source captures and Actions.
2. For architecture questions, use an existing graph report when present,
   then targeted `rg` and relevant file reads. No broad repo scans.
3. Before design, editorial, pipeline, or agent work, read the governing doc:

| Doc | Governs |
|---|---|
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, audiences, page anatomy, evidence-vs-inference rules |
| `docs/desks/README.md` | mandatory architecture, lifecycle, CI/delivery separation and completion for every desk |
| `docs/desks/MIGRATION.md` | current code boundaries, coordination and next bounded phase; not live certification |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | existing layer map, source vs generated, commands, CI, commit strategy |
| `docs/AGENT_WORKFLOWS.md` | model routing, skills, agents, parallelism limits |
| `docs/ROADMAP.md` | dated priorities; verify current owner direction |
| `docs/DESIGN_SYSTEM.md` | dual-surface tokens, typography, color, a11y + performance budgets |
| `docs/VISUAL_AND_MOTION_SYSTEM.md` | motion rules, flagship visual specs, image policy, metadata fields |
| `docs/SHADOW_COLLECTION.md` / `docs/SHADOW_REVIEW.md` | historical shadow isolation/review; not launch-clock gates |
| `DECISION_LOG.md` / `EDITORIAL_QA_CHECKLIST.md` | standing rulings; weekly publish gate |

## Hard rules
- Use an isolated worktree of the assigned IPR repository. Coordinate with
  the private source-evidence companion when explicitly authorized. Never
  modify unrelated repositories or another agent's active worktree.
- **Never hand-edit `output/`** — it is generated. Fix templates/scripts/
  sidecars and re-render. Sidecar JSON (`output/the-pla-watch/posts/*.json`)
  is the canonical edition record — no casual edits, ever.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay recorded as warnings, not fixed.
- Public label is "model-flagged," never "significant" (see DECISION_LOG).
- `executive_readout` is analyst-authored only — never synthesize it.
  `recurring_threads` slugs only from the V&M §4 vocabulary, only for
  threads the edition materially analyzes.
- Never defeat a source's access challenge, impersonate a browser, or route
  around `robots.txt`. An institution must be able to recognise this collector
  and refuse it.
- No shadow desk is promoted automatically or called operational without
  real-source end-to-end acceptance and a demonstrated failure/retry. The
  owner's October 18 complete-desk standard supersedes seven-/30-day
  *prelaunch* waiting periods, not historical receipts or human source/rights
  and editorial approvals. See `docs/engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md`.
- A task may authorize edits, commits, pushes and one reviewable PR. Apply
  established standing decisions, but never infer merge, model spending,
  production DB writes, schedule activation, publication or outside contact.
  Deployment remains separately governed by production release procedures.
- `base.html`, `pla-watch-base.html`, `scripts/pw_env.py` are single-owner
  files — no concurrent agent edits.

## Complete-desk working method

Follow `docs/desks/README.md` and scope one coherent phase with
`docs/desks/CHANGE_TEMPLATE.md`. Source collection and private evidence may run
independently; authenticated permitted components converge through the common
lifecycle, record interface and coordinated public writer. Preserve accepted
output and source-specific negative tests. Code qualification is separate from
routine data checks only after its trusted replacement is implemented; do not
remove today's gates based on a design statement.

Routine permitted machine output publishes unattended within actual source-use,
quality, spending and activation authority; hold only genuine exceptions.
Translate only when needed, never default unknown sources to China, and keep
human-controlled editorial products separate. Verify one authentic source-to-site
result and representative failure/recovery when a release is authorized. Stop
at the assigned phase's finish line or one concrete external blocker. Retain
historical evidence; no arbitrary launch clock, extra qualification program,
per-record owner ritual, source expansion or unrequested cleanup.

## Commands
```bash
.venv/bin/python scripts/validate_output.py                 # deploy gate — run before/after output changes
.venv/bin/python site/render.py                             # PRODUCTION renderer: daily site from the DB
.venv/bin/python scripts/rerender_pla_watch.py --no-covers  # weekly pages from sidecars
```
`site/render.py` is the only place a frontend is selected. `DEFAULT_SITE_MODE`
is `indo-pacific-record`; `site/generator.py` is the `legacy` renderer and is
the rollback path only — never call it as the production build.

Preview: Browser-pane server `pla-watch-site` (port 8765, serves `output/`).
Full-page visual review: Playwright in `.venv` at 1280 + 375 (in-app
screenshots go stale after scrolling).
Baseline: **validator passes with 10 governed warnings**; explain any new one
in `PROJECT_STATE.md` and never fix one by invention.

## Design north star (details in docs/DESIGN_SYSTEM.md)
The October frontend candidate follows the reviewed photograph-led direction,
selected lowercase ipr identity and Instrument Serif / Inter / Source Serif 4.
Paper Ledger remains the reading ground and Night Desk identifies analysis.
The 2026-10-09 owner ruling requires historical articles to use the current IPR
shell; historical publication identity survives in provenance and citations,
not a competing masthead. The consolidation is implemented as a review candidate;
evidence is `docs/BRIEFS_CONSOLIDATION_2026-10-09.md`, alongside the frontend
review in `docs/FRONTEND_PRODUCTION_2026-10-09.md`. Keep
the jade editorial family for human analysis and slate-blue for machine output
(owner-directed coastal supersession, 2026-10-14; DESIGN_SYSTEM §3).
No SaaS/dashboard/terminal aesthetics; no box shadows; mono never in prose;
motion is reveal-based, reduced-motion-safe, transform/opacity only.

## Model routing (details in docs/AGENT_WORKFLOWS.md)
Fable: direction, design judgment, cross-route architecture, final review.
Sonnet: ticket implementation, generators, fixes, re-renders, QA.
Haiku: inventory, link checks, log summarization.
Parallel agents only for genuine parallelism (max 4); long-log compression
tools are never authoritative for Chinese text or claims.

## Working style
Token-efficient by default: smallest safe change; no full-file pastes; no
unrequested refactors; summarize long outputs; report files changed + what
changed + how to check. After meaningful work update `PROJECT_STATE.md` —
keep it a current snapshot, not a diary; after structural changes run
`graphify update .`; record constraining rulings in `DECISION_LOG.md`.
