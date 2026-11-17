# Regional atlas: before and after (17 November 2026)

**Before** is the live site at `https://indopacificrecord.org/` (main
`a6484f5c47`, deployed 16 November). **After** is this branch rendered in
place by `site/render.py` from the tracked `pla_watch.db` and served locally.
Both were captured with Playwright (Chromium, `reduced_motion=reduce`).
Desktop is 1280px wide; mobile is 375px. Both are cut at 1,700px.

| Page | Route | Desktop | Mobile |
| --- | --- | --- | --- |
| Desks: the atlas opens the page | `desks.html` | `desks-1280-before.webp` / `desks-1280-after.webp` | `desks-375-before.webp` / `desks-375-after.webp` |
| A collecting desk with a locator | `china.html` | `china-1280-before.webp` / `china-1280-after.webp` | `china-375-before.webp` / `china-375-after.webp` |
| A one-institution desk | `singapore.html` | `singapore-1280-before.webp` / `singapore-1280-after.webp` | `singapore-375-before.webp` / `singapore-375-after.webp` |
| The outside-the-frame desk (no locator, waterline rule only) | `us-indopacific.html` | `us-indopacific-1280-before.webp` / `us-indopacific-1280-after.webp` | `us-indopacific-375-before.webp` / `us-indopacific-375-after.webp` |

## What to look for

- **One real coastline.** The geometry is Natural Earth 1:50m, the same base
  the retired Desks map drew. The lines in the sea repeat that coastline at
  fixed distances. They are not depth contours.
- **Seats, not coverage.**
  - Each point marks where a desk's publishing institutions are based.
  - No country is filled.
  - Each mark is the desk's registry state glyph, with no colour-only meaning.
  - The US desk is an edge pointer ("United States, outside this map"), not a Hawaii seat.
- **Directory unchanged.** The rows below the atlas, their counts, states and parallel-text titles are unchanged. Each row gains "Seat: <place>" with a link back to the atlas.
- **Waterline rule.** Every page head's 2px rule now has two faint hairlines beneath it.

These captures show this branch, not production, until the PR is merged and
deployed.
