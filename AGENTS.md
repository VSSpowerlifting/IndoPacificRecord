# Agent Operating Rules — Indo-Pacific Record

Read `CLAUDE.md` first — it is the authoritative operating file for this
repository (orientation, hard rules, commands, doc map). This file exists
for tools that read AGENTS.md instead.

The public identity is **Indo-Pacific Record**. "China Mil Watch" is the
retired predecessor name and is used only when describing history.
**Indo-Pacific Record Briefs** is the continuing analytical collection. "The
PLA Watch" is the predecessor attribution its existing issues keep; no new
issue is authored or published under it (DECISION_LOG 2026-09-23).
The 2026-10-09 owner ruling supersedes preservation of historical page chrome:
all article pages should use the current IPR shell, with original publication
identity retained in a provenance note and citation. See editorial doctrine §5a.

**Standing multi-desk direction (owner, 2026-10-19):** one logical shared
Daily processing/record publishing system, not a separate article/AI/site
pipeline per desk. Independent private/source-specific collectors remain
allowed and necessary. Translation only when needed; automated, labeled
record output after source-specific rights/QA/spend authorization; Briefs
remain human editorial. This is a target, not current release permission.
See `docs/engineering/SHARED_DAILY_DESK_ARCHITECTURE_2026-10-19.md`.

**Owner's permanent desk-delivery rule (20 October 2026, all desks and sessions):**
The deliverable is a **working unattended desk**, not another audit, roadmap,
shadow milestone, or PR. Reuse one shared Daily corpus/processing/publishing
path, and use separate private collectors only where source access/custody
requires them. For authorized, quality-passing machine-labeled records,
automate translation when needed, analysis, and site updates without routine
per-article approval; hold real rights/accuracy exceptions individually.
Use focused tests while implementing, the repository's mandatory CI at the
final exact revision, and one real successful source-to-live-site result.
No arbitrary 7/30-day waits, repeat full suites, extra rehearsal programs,
parallel AI engines, or desk-specific article renderers. Preserve source-use
permissions, provenance, model spending limits, the existing China/Singapore
service, and human approval for Briefs. Explicit authority is still required
for new source-use/spend/publishing activation. Stop when the agreed desk
works—or report the one precise external blocker. **Do not manufacture more
work to chase a percentage.**

Summary of the non-negotiables:

- Use a separate worktree for each assigned IPR repository. Coordinate with
  the named private evidence companion only where authorized; do not modify
  unrelated repositories or another agent's active worktree.
- Never hand-edit `output/` (generated) or sidecar JSON (canonical edition
  records). Fix templates/scripts, then re-render.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay as recorded warnings.
- Never defeat a source's access challenge or impersonate a browser; an
  institution must be able to recognise this collector and refuse it.
- No shadow desk is promoted automatically or called qualified without
  actual source-to-site acceptance and owner release. Follow the October 18
  complete-desk/CI policy in `docs/engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md`;
  seven-/30-day streaks measure reliability rather than delay launch.
- Use the task's explicit authority (and valid standing owner decisions) for
  edits, commits, pushes and review PRs. Do not infer permission to merge,
  spend, activate schedules, mutate production or publish. CI deploys the
  authorized changes committed to main.
- Production renderer is `.venv/bin/python site/render.py`; the deploy gate is
  `.venv/bin/python scripts/validate_output.py`, whose governed baseline is
  10 warnings.
- Be token-efficient: smallest safe change, no full-file pastes, no
  unrequested refactors; report files changed + what changed + how to test.
- Session start: check latest owner decisions and relevant
  `PROJECT_STATE.md` sections against live code, PRs and Actions; doctrine in `docs/`
  (product/editorial, architecture & publishing, agent workflows, roadmap,
  shadow collection and review, design system, visual & motion).
