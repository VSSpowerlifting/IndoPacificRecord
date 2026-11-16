# Parallel text redesign — rendered evidence (16 November 2026)

Screenshots of the branch `claude/ipr-redesign-completion-0146ee` rendered by
`site/render.py --out <scratch>` from the tracked `pla_watch.db` (snapshot of
15 November 2026, 2,043 records), served locally and captured with Playwright
(Chromium, `reduced_motion=reduce`, device scale 1). Desktop is 1280px wide and
cut at 2,400px; mobile is 375px wide and cut at 3,400px. These show a local
render, not the deployed site; nothing here is merged, deployed or live.

| Page | Route | Desktop | Mobile |
| --- | --- | --- | --- |
| Home | `index.html` | `home-desktop.webp` | `home-mobile.webp` |
| Records (archive) | `archive.html` | `archive-desktop.webp` | `archive-mobile.webp` |
| A full record | `record/476.html` | `record-476-full-desktop.webp` | `record-476-full-mobile.webp` |
| A sparse, metadata-only record (MINDEF) | `record/5834.html` | `record-5834-metadata-desktop.webp` | `record-5834-metadata-mobile.webp` |
| A machine explanation | `record/source-977a9b853c70af8ec1e19c4e.html` | `machine-explanation-desktop.webp` | `machine-explanation-mobile.webp` |
| A desk | `china.html` | `desk-china-desktop.webp` | `desk-china-mobile.webp` |
| Desks directory | `desks.html` | `desks-desktop.webp` | `desks-mobile.webp` |
| Briefs catalogue | `analysis.html` | `briefs-catalogue-desktop.webp` | `briefs-catalogue-mobile.webp` |
| A Brief | `briefs/south-korea-nuclear-submarine-strategy-fuel-2026.html` | `brief-desktop.webp` | `brief-mobile.webp` |
| A dossier | `dossier/china-singapore-naval-cooperation.html` | `dossier-desktop.webp` | `dossier-mobile.webp` |

At capture, every page had `document.documentElement.scrollWidth` equal to the
viewport (no horizontal scroll at 375px) and logged no console errors.

## Checks run on the same build

- `scripts/verify_frontend_delivery.py --root <render>`: 3,543 routes, 0 budget
  failures. Nearest to their caps: `korea.html` 118,586 / 120,000;
  `indonesia.html` 122,338 / 130,000; `record/476.html` 117,072 / 125,000;
  dossier 214,381 / 230,000.
- `scripts/build_archive_js.py --check`: passes; `browse.js` 9,485 bytes,
  `citation.js` 4,961 bytes.
- `scripts/validate_output.py` on the render with the carried-forward
  `data/` and `the-pla-watch/` trees: passes with 7 warnings, the same 7 that
  `main`'s committed `output/` produces unchanged (PLA Watch pilot-edition
  sidecars and one cadence gap). The change adds no warning.

The design decisions these pages show are recorded in `DECISION_LOG.md`
(2026-11-16 — Parallel text redesign, pending review) and
`docs/DESIGN_SYSTEM.md` ("Parallel text identity").
