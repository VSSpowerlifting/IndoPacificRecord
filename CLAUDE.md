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

## Standing owner priority — working desks, minimal engineering overhead (20 October 2026)

This instruction applies to **every desk and every future Codex/Claude
session**. The owner values **a public desk that runs automatically** over
internal architecture milestones, test counts, review dockets, shadow streaks,
or a nominal \"100%\" score. Build privately, launch completely, then maintain
only real failures. On a desk assignment: identify the single missing link to
real Daily intake → shared corpus or truthful source-link record → appropriate
translation → model-labeled analysis → source-specific rights/QA gate → shared
site/desk/archive/search → routine automatic publication. Reuse working
collectors, custody, model engine and renderer. Do not start parallel article
pipelines, new phase frameworks, redundant monitoring or speculative source
expansions. Keep doing the actual implementation instead of serial preparatory
PRs. A desk is done when a real eligible record completes the authorized
production path and future eligible records can follow without routine human
intervention; a link-only source remains clearly labeled and does not imply
full-text rights. Test risky paths with focused checks during development and
run required CI once on the final head; verify the actual deployed result.
Do not avoid necessary tests, distort the evidence, bypass access/rights,
automate Briefs, or infer authority to spend, merge or activate publication.
If blocked, report **one concrete blocker and owner action**; otherwise ship.
The source of truth is the 20 October entry in `DECISION_LOG.md` and
`docs/engineering/SHARED_DAILY_DESK_ARCHITECTURE_2026-10-19.md`. This owner
priority supersedes older preparatory waiting schedules and aspirational
roadmaps, not mandatory CI, publisher rights or historical approvals.

## Session start
1. Check latest owner rulings in `DECISION_LOG.md` and
   `docs/engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md`; read relevant
   `PROJECT_STATE.md` sections and verify dated status against real code,
   open PRs, source captures and Actions.
2. For architecture questions, use an existing graph report when present,
   then targeted `rg` and relevant file reads. No broad repo scans.
3. Before design, editorial, pipeline, or agent work, read the governing doc:

| Doc | Governs |
|---|---|
| `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` | identity, audiences, page anatomy, evidence-vs-inference rules |
| `docs/ARCHITECTURE_AND_PUBLISHING.md` | layer map, source vs generated, commands, CI, commit strategy |
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
Follow the owner-approved contract for each desk: official sources → private
source evidence → permitted translation/processing → screening and analysis →
governed SQLite/admission → reader/editor publication → genuine scheduled
maintenance and recovery. Derive expected records from original publisher
material; distinguish manual rehearsal from real unattended operation. Verify
source rights, actual human decisions, idempotent retries and deployed HTTPS
when authorized. Prefer one coherent PR (and only an essential private
companion) to new qualification frameworks or extra approval layers. Finish
at an operating desk or a specific external blocker. See
`docs/engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md` and issue #673.

## Shared Daily target (owner direction, 2026-10-19)

The default end state for every desk is **one logical Daily**: permitted
independently scheduled/private collector → authenticated source-pinned common
intake → explicit desk-language profile on the shared screening/model queue →
source-specific rights and automatic QA gates → existing IPR record/source-link
presentation, search, desk and deployment. **Do not build a second corpus,
country-specific AI engine, parallel article renderer or routine per-record
human publishing workflow.** Source collectors need not run inside the same
Actions job: preserve official access cadence, isolation and private originals.
English originals need no translation. Unknown desks must not use China's
prompts by fallback. A metadata-only licence never approves original text or
public machine explanation. Once separately authorized and verified, routine
machine-labeled records may publish without human approval; Briefs and bylined
analysis remain human controlled. Policy targets are **not** activation,
spending or publication authority. See `docs/engineering/SHARED_DAILY_DESK_ARCHITECTURE_2026-10-19.md`.

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
