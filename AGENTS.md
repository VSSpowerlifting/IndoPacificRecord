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

Summary of the non-negotiables:

- Work in an isolated worktree of the assigned IPR repository. Access a named
  private evidence companion only when the task authorizes it; never modify
  unrelated repos or another agent's active worktree.
- Never hand-edit `output/` (generated) or sidecar JSON (canonical edition
  records). Fix templates/scripts, then re-render.
- Never invent Chinese text, translations, titles, outlets, dates, units,
  ranks, or claims. Historical gaps stay as recorded warnings.
- Never defeat a source's access challenge or impersonate a browser; an
  institution must be able to recognise this collector and refuse it.
- No automatic promotion or inflated coverage claims: the 2026-10-18 owner
  ruling replaces fixed seven-/30-day launch delays with verified complete-
  desk delivery on primary records, genuine rights and reviewer decisions,
  safe database writes and independent public readback (issue #673).
- Follow specific assignment and standing authority for edits, pushes and
  review PRs; no implied permission to merge, pay for models, change live
  schedules, write production data, publish or contact outsiders.
- Production renderer is `.venv/bin/python site/render.py`; the deploy gate is
  `.venv/bin/python scripts/validate_output.py`, whose governed baseline is
  10 warnings.
- Be token-efficient: smallest safe change, no full-file pastes, no
  unrequested refactors; report files changed + what changed + how to test.
- Session start: read the latest owner decisions and relevant
  `PROJECT_STATE.md` handoff; verify dated claims against main and Actions;
  deeper doctrine in `docs/`
  (product/editorial, architecture & publishing, agent workflows, roadmap,
  shadow collection and review, design system, visual & motion).
