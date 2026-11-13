# Reader polish — before/after captures (2026-11-13)

Each image places the page rendered from `main` at `771b76d92d` (left, "before")
beside the same page rendered from this branch (right, "after"). Both sides were
rendered locally with `site/render.py --site-origin https://indopacificrecord.org`
from the same tracked `pla_watch.db` and captured with Playwright (Chromium) at
1280px (desktop) or 375px (mobile), full page, then downscaled to WebP.

| File | Page | What to look at |
| --- | --- | --- |
| `record-6392-desktop.webp` | `record/6392.html` (China MND) | Publisher/source line, one machine-output explanation, "Open original source" / "Cite" / "Copy link" actions, available-material list, closed technical provenance |
| `record-6392-mobile.webp` | same, 375px | Same order on a phone; date column folded into the source line |
| `record-4435-mindef-desktop.webp` | `record/4435.html` (MINDEF) | Neutral historical-processing wording; nothing withheld is reproduced |
| `record-5487-vietnam-mobile.webp` | `record/5487.html` (Vietnam) | Machine-generated headline note and the withheld-text explanation beside the original-source link |
| `records-finder-desktop.webp` | `archive.html` | Plain-language lede, "Search in / Source / Sort by" labels, research-focus explanation |
| `home-mobile-header-search.webp` | `index.html`, 375px | Single "Menu" control (no double icon), home search now covers all records |
| `about-desktop-nav.webp` | `about.html` | Five-item primary nav, new "Reusing this material" section |

These are review evidence only; they are not used by any build or test.
