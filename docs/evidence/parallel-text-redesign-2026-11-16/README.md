# Parallel text redesign — rendered evidence (16 November 2026)

Screenshots of the branch `claude/ipr-redesign-completion-0146ee` rendered by
`site/render.py --out <scratch>` from the tracked `pla_watch.db` (snapshot of
15 November 2026, 2,043 records), served locally and captured with Playwright
(Chromium, `reduced_motion=reduce`, device scale 1). Desktop is 1280px wide and
cut at 2,400px; mobile is 375px wide and cut at 3,400px. These show a local
render, not the deployed site; nothing here is merged, deployed or live.

| Page | Route | Desktop | Mobile |
| --- | --- | --- | --- |
| Home, photographic opening (current) | `index.html` | `home-photo-desktop.webp` | `home-photo-mobile.webp` |
| Home, text-only opening (superseded, for comparison) | `index.html` at `11e3832784` | `home-text-only-desktop.webp` | `home-text-only-mobile.webp` |
| Home, first screen only | `index.html` | `home-photo-first-screen-768x1024.webp` | `home-photo-first-screen-320x568.webp` |
| Records (archive) | `archive.html` | `archive-desktop.webp` | `archive-mobile.webp` |
| A full record | `record/476.html` | `record-476-full-desktop.webp` | `record-476-full-mobile.webp` |
| A sparse, metadata-only record (MINDEF) | `record/5834.html` | `record-5834-metadata-desktop.webp` | `record-5834-metadata-mobile.webp` |
| A machine explanation | `record/source-977a9b853c70af8ec1e19c4e.html` | `machine-explanation-desktop.webp` | `machine-explanation-mobile.webp` |
| A desk | `china.html` | `desk-china-desktop.webp` | `desk-china-mobile.webp` |
| Desks directory | `desks.html` | `desks-desktop.webp` | `desks-mobile.webp` |
| Briefs catalogue | `analysis.html` | `briefs-catalogue-desktop.webp` | `briefs-catalogue-mobile.webp` |
| A Brief | `briefs/south-korea-nuclear-submarine-strategy-fuel-2026.html` | `brief-desktop.webp` | `brief-mobile.webp` |
| A dossier | `dossier/china-singapore-naval-cooperation.html` | `dossier-desktop.webp` | `dossier-mobile.webp` |
| Korea reviewed translation | `korea-translations/156784297.html` | `korea-translation-desktop.webp` | `korea-translation-mobile.webp` |

The photographic home, its first-screen captures and the Korea translation
captures are from the committed `output/` at `e840e402f0`, served as it is
committed. On the 320x568 first screen the title search ends at 565px. The
rest are from `11e3832784`; later commits change those pages only in the home
opening, the Briefs card on the home page (which no longer repeats the hero
photograph), the Korea translation mark and the selected-records note on the
Records page, which now hides when another scope is chosen.

At capture, every page had `document.documentElement.scrollWidth` equal to the
viewport (no horizontal scroll at 375px) and logged no console errors.

## Checks run on the committed tree at `e840e402f0`

- The whole committed `output/` was regenerated in place by `site/render.py`
  and then `scripts/rerender_pla_watch.py --no-covers`. A fresh scratch render
  matches it byte for byte, apart from sitemap URL order.
- `scripts/verify_frontend_delivery.py`: 0 budget failures across 3,613
  committed routes (3,595 in the fresh render). Nearest to their caps:
  `korea.html` 118,790 / 120,000 (the cap at capture; 130,000 since the owner's decision of 16 November); `indonesia.html` 122,338 / 130,000;
  `record/476.html` 117,072 / 125,000.
- `scripts/build_archive_js.py --check` passes: `browse.js` 9,485 bytes,
  `citation.js` 4,961 bytes.
- `scripts/validate_output.py` passes with the 10 governed warnings.
- Every original-language text run on `main`'s committed record (2,157),
  Korea (37), Brief (9), dossier (2) and source (16) pages is still present.

The design decisions these pages show are recorded in `DECISION_LOG.md`
(2026-11-16 — Parallel text redesign, pending review) and
`docs/DESIGN_SYSTEM.md` ("Parallel text identity").
