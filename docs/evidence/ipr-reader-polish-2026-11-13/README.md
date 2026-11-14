# Reader polish — before/after captures (2026-11-13)

Every image is rendered locally with
`site/render.py --site-origin https://indopacificrecord.org` from the same
tracked `pla_watch.db`. Captures use Playwright (Chromium) at 1280px (desktop)
or 375px (mobile) and are downscaled to WebP.

**Against `main`.** In these images, the left side is `main` at `dd89e95e24` and
the right side is this branch.

| File | Page | What to look at |
| --- | --- | --- |
| `record-6392-desktop.webp` | `record/6392.html` (China MND) | Publisher/source line, one machine-output explanation, "Open original source" / "Cite" / "Copy link" actions, contents panel, closed technical provenance |
| `record-6392-mobile.webp` | same, 375px | Same order on a phone; date column folded into the source line |
| `record-4435-mindef-desktop.webp` | `record/4435.html` (MINDEF) | Neutral historical-processing wording; nothing withheld is reproduced |
| `record-5487-vietnam-mobile.webp` | `record/5487.html` (Vietnam) | Machine-generated headline note and the withheld-text explanation beside the original-source link |
| `records-finder-desktop.webp` | `archive.html` | Lede that calls entries records, "Search in / Source / Sort by" labels, research-focus note |
| `home-mobile-header-search.webp` | `index.html`, 375px | Single "Menu" control, home search covering all records |
| `about-desktop-nav.webp` | `about.html` | Five-item primary nav |

**Against the previous PR head.** Files prefixed `rev-` show what the revision
changed. The left side is the earlier head of this PR, `430b84f927`; the right
side is the revised branch.

| File | Page | What to look at |
| --- | --- | --- |
| `rev-about-reuse.webp` | `about.html#reuse` | Plain-language summary of the rights policy. It no longer says publishers own every text, quotation and image, and it leaves machine output out of scope |
| `rev-record-contents.webp` | `record/6392.html` | Contents panel without notes that repeat the link or its label, and without the duplicate citation row |
| `rev-record-citation.webp` | `record/6392.html#record-citation` | Shorter citation lede, and the locator disclaimer as one sentence that ends in the citation guide link |
| `rev-empty-focus.webp` | `archive.html?q=…`, Research focus | Empty state offering "Search all … records" |
| `rev-empty-all-m.webp` | `archive.html?scope=all&q=…`, 375px | Empty state in a wider scope offering "Clear the search and filters" (the scope is kept) |
| `rev-methodology-head.webp` | `methodology.html` | Sources and Coverage links under the lede |

These are review evidence only; they are not used by any build or test.
