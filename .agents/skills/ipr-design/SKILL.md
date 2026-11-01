---
name: ipr-design
description: Indo-Pacific Record design system pointer. Use when building or changing IPR UI — templates, CSS, SVG plates, motion, navigation, or the reader presentation of Briefs, dossiers, timelines, desk pages or editions. Points to the hand-maintained design doctrine and the live token sources.
---

# Indo-Pacific Record design — authoritative pointer

This skill only routes; the doctrine lives in tracked docs. Read, in order,
before writing UI code:

1. `docs/DESIGN_SYSTEM.md` — dual-surface tokens (Paper Ledger / Night Desk),
   typography roles, color meaning, grid, components, accessibility, budgets.
2. `docs/VISUAL_AND_MOTION_SYSTEM.md` — motion primitives and limits, flagship
   visual specs, image policy.
3. `site/templates/base.html` (light) and `site/templates/pla-watch-base.html`
   (dark) — the real CSS custom properties and shared motion primitives.
   Both are single-owner files: one writer at a time.

Use the active coastal palette and semantic tokens specified in the current
doctrine and templates. Historical token tables are retained for reference,
not instructions for active UI. Follow the governing documents for typography,
surfaces, motion, accessibility and responsive behavior rather than duplicating
their rules here. Keep the photography-led journal feel. Presentation must not
imply source diversity, precision or liveness the data lacks.

Rendered `output/` is current truth (never hand-edit it; regenerate with
`site/render.py`). Verify material UI changes at 1280px and 375px.
Generic design skills (see `docs/AGENT_WORKFLOWS.md` §2) refine within this
doctrine; they never override it.
