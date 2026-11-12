# Indo-Pacific Record — Claude-specific operating notes

**Read [AGENTS.md](AGENTS.md) first.** It is the canonical entrypoint for
mission-based work admission, authority, evidence and source safeguards,
engineering scope, stop conditions and definitions of completion. This file
adds tool-specific implementation notes rather than duplicating those rules.
For domain authority, follow the documentation map in `AGENTS.md`.
For source use, read `CONTENT_AND_DATA_RIGHTS.md` §7: evaluate an evidenced
use-specific legal basis rather than demanding a publisher letter for every use.
Preserve actual publisher/access, third-party content, budget and release
safeguards. For MINDEF, the founder's **9 November standing-source-use
direction** (see `AGENTS.md` and `DECISION_LOG.md`) accepts eligible official
release custody, bounded external-model processing and independent factual
machine explanations in addition to standing links. Do not resurrect the
superseded two-link limit. Existing MINDEF collection/model/public-data
**runtime controls are still deployed** until a separate reviewed engineering
change; removing an obsolete permission hold from policy text does not
authorize executing a collector, spending, a public DB mutation or publishing.
Original media and unrestricted source-body republication remain excluded.

IPR is an independent, source-grounded research publication. Automated
source records are not human-authored IPR Briefs. *The PLA Watch* and
*China Mil Watch* are historical names, not new publication identities.
Never describe IPR as an OSINT tool or intelligence agency.

## Start and stop a coherent work phase

1. Read `AGENTS.md`. For any desk task, also read the binding
   `docs/desks/README.md` and relevant live migration boundary in
   `docs/desks/MIGRATION.md`, then the actual source-specific decisions.
2. Check the current repository, live evidence and PR state; the retired
   `PROJECT_STATE.md` diary is not an active task or status source. Read only
   the governing files needed for this task, using targeted searches rather
   than full-repository scans.
3. Use an isolated worktree, one engineering objective, focused risk-based
   tests and final exact-revision checks. Use the existing issue/PR body for
   any major-growth justification; do not create a new policy packet.
4. Stop at the bounded implementation/verification finish line.
   A verified PR is not automatically merged, deployed, activated or live.
   Do not expand into unrelated cleanup, follow-on releases or paid models.

Never hand-edit generated `output/` or published canonical edition sidecars.
Preserve source and copyright restrictions, accepted outputs, real holds and
source identities. Never invent text to make a test pass or circumvent
publisher access controls. Coordinate edits to single-owner
`base.html`, `pla-watch-base.html` and `scripts/pw_env.py`.

## Production and preview

```bash
.venv/bin/python scripts/validate_output.py
.venv/bin/python site/render.py
.venv/bin/python scripts/rerender_pla_watch.py --no-covers
```

The IPR site is rendered through `site/render.py`.
`site/generator.py` is the legacy rollback path, not the production
build. Local preview server `pla-watch-site` serves `output/` on port
8765. For material UI changes, verify 1280px and 375px Playwright views.
At the documented baseline, the deployment validator has **10 governed
warnings**; investigate any new warnings and never fix by invention.

## Visual, model and operating conventions

Follow `docs/DESIGN_SYSTEM.md` and
`docs/VISUAL_AND_MOTION_SYSTEM.md` for current editorial visuals,
typography, accessibility and performance. Keep the established
photography-led journal feel—not a dashboard, terminal or simulated
intelligence operation. Superseded mockups are not permanent authority.

Model/agent routing lives in `docs/AGENT_WORKFLOWS.md`. Use parallel
agents only for genuine parallel work and avoid unnecessary deep scans
or expensive model calls. Schema success, model agreement or fluent
machine prose is not independent factual review.

Retain durable continuity in code, decisions, tests and PRs. Update
a relevant current state/migration record concisely after meaningful
changes, rather than append a project diary. Report actual changed
files, commit, checks, precise limitations and next bounded action.
