# Search scope from the homepage and the Archive — before/after (2026-11-14)

**Question.** A researcher starts with a topic, such as Abukuma, AMRAAM or
Bersama Lima. Can they reach the relevant published material across desks,
and its citable Record or Brief, from where they start searching?

**Finding (before).** After #1046, IPR Briefs and the cited Records reachable
from them exist only in **All published material**. The homepage box
submitted `scope=all` (preserved records only). The Archive starts in the
Research focus, and when the focus was empty it offered "Search all 2,013
records", which is the same `scope=all`. So 10 of the 12 tasks below that
have a published answer showed nothing from either entry point. Neither page
said that All published material held the answer. A non-empty narrow result
(`Laos`: 6 focus or 10 preserved records) hid the Brief and its four
citation Records without any signal. Once the scope was *All published
material*, the first useful result ranked #1 or #2 in every task. The problem
was scope, not ranking.

**Change.** The homepage box submits `scope=published` and still matches
titles (`q`). In the Archive, a filtered search in the Research focus or the
full preserved record counts what All published material adds. It shows
"Search all published material (N more)", and that button widens the scope
and keeps the search. In an empty result this replaces the dead-end
recovery; "Clear the search and filters" remains when the wider scope has
nothing either.

## Research tasks (desktop 1280px; 375px gave identical ranks and steps)

Expected results are links to the current public index. **Rank** is the first
useful result's position on the final results page. **Steps** are keyboard
actions from typing the query: submit, any scope change, and opening
"Citation and provenance". "Needs unprompted scope change" means the reader
had to know to open *Search in* and choose *All published material*; nothing
on the page pointed there. "Via offered widen" means the page offered it.

| Task | Query | Expected public result | Home before | Home after | Archive before | Archive after |
|---|---|---|---|---|---|---|
| Abukuma transfer (cross-desk topic / exact lookup) | `Abukuma` | [independent ref](https://indopacificrecord.org/record/cited-d70488b60735356d.html), [independent ref](https://indopacificrecord.org/record/cited-f7ffe055fe9e45aa.html), [Brief](https://indopacificrecord.org/briefs/japan-philippines-first-destroyer-2026.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| AMRAAM co-production (cross-desk topic) | `AMRAAM` | [Brief](https://indopacificrecord.org/briefs/japan-us-amraam-final-assembly-sm3-production.html), [official ref](https://indopacificrecord.org/record/cited-e1faa3947b716051.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Bersama Lima (cross-desk topic) | `Bersama Lima` | [Brief](https://indopacificrecord.org/briefs/bersama-lima-2026-five-power-coordination-at-sea.html), [official ref](https://indopacificrecord.org/record/cited-6024ad6102eda9b7.html), [official ref](https://indopacificrecord.org/record/cited-c8a4dab9c46ae0c5.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Laos base (cross-desk topic) | `Laos` | [Brief](https://indopacificrecord.org/briefs/what-is-being-built-in-laos.html), [official ref](https://indopacificrecord.org/record/cited-000e046e420d46a0.html), [independent ref](https://indopacificrecord.org/record/cited-ccca94bc10eeb2fd.html) | #2 · 3 steps · needs unprompted scope change | #2 · 2 steps | #2 · 3 steps · needs unprompted scope change | #2 · 3 steps · via offered widen |
| Brief by exact title (exact publication lookup) | `What Is Being Built in Laos` | [Brief](https://indopacificrecord.org/briefs/what-is-being-built-in-laos.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Hegseth readout (exact publication lookup) | `Hegseth` | [official ref](https://indopacificrecord.org/record/cited-de7bd1ecaeb247f8.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Scarborough (English) (cross-desk topic) | `Scarborough` | [PLA Watch issue](https://indopacificrecord.org/the-pla-watch/posts/2026-07-04.html), [PLA Watch issue](https://indopacificrecord.org/the-pla-watch/posts/2026-08-01.html), [PLA Watch issue](https://indopacificrecord.org/the-pla-watch/posts/2026-08-08.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Huangyan (English machine titles) (archive topic) | `Huangyan` | any Huangyan record | #1 · 2 steps | #1 · 2 steps | #1 · 2 steps | #1 · 2 steps |
| 福建舰 (Chinese) (original-language) | `福建舰` | [record](https://indopacificrecord.org/record/2908.html), [record](https://indopacificrecord.org/record/4534.html), [record](https://indopacificrecord.org/record/4539.html) | #2 · 2 steps | #2 · 2 steps | #1 · 2 steps | #1 · 2 steps |
| 中国海軍艦艇 (Japanese) (original-language) | `中国海軍艦艇` | [official ref](https://indopacificrecord.org/record/cited-40f6d9a554dc936b.html), [official ref](https://indopacificrecord.org/record/cited-5ba4e719129d36a2.html), [official ref](https://indopacificrecord.org/record/cited-984b3bff98a5a213.html) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| 북한 탄도미사일 (Korean) (original-language) | `북한 탄도미사일` | [official ref](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784297) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |
| Dalai Lama (generic official-link title) (no-match: metadata-only reference) | `Dalai Lama` | — | no match · 1 step | no match · 1 step | no match · 1 step | no match · 1 step |
| Kiribati (genuine no-match) | `Kiribati` | — | no match · 1 step | no match · 1 step | no match · 1 step | no match · 1 step |
| Held Korea reference 156785161 (held source) | `156785161` | [official ref](https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785161) | #1 · 3 steps · needs unprompted scope change | #1 · 2 steps | #1 · 4 steps · needs unprompted scope change | #1 · 3 steps · via offered widen |

**No-match and held cases.** *Kiribati* has no published title, and both
builds say so with only "Clear" offered. *Dalai Lama* is a real USCC press
release, but its public index title is the generic "USCC official press
reference · 2026-08-26". Title search therefore cannot find it in any scope;
the topic appears only in the source URL, which search does not match by
contract. That is a projection limitation owned by the U.S. desk work, not
changed here. The held Korea reference 156785161 is reached in 2 steps from
the homepage after the change, and its hold text ("Original contains an
unresolved excavation-year discrepancy; no factual account is endorsed.") is
visible on the row before the citation is opened. The *Abukuma* title search
finds the two cited Records. The Brief that cites them, "Japan and the
Philippines Narrow Their Destroyer Talks to a First Ship", has *Abukuma* only
in its summary, so a title search misses it; each cited Record page links
back to that Brief.

## Method

`harness/build.py` renders an isolated production-equivalent site into a
scratch directory with `generate_preview.build`, as
`tests/test_archive_integration_browser.py` does, from the tracked
`pla_watch.db`. "Before" is `main` at `c5fea0899f`; its
`archive-research-index.json` and `browse.js` are byte-identical to the
tracked `output/`, and its HTML differs only in the build date.
`harness/journey.py` drives Chromium (Playwright) with the keyboard. It
types into `#home-q` or `#f-q`, presses Enter, follows a widen control only
if the page offers one, and otherwise changes the scope select (counted as
unprompted). It then opens the result's "Citation and provenance" with Enter.
`harness/measure_tasks.py` lists the tasks. `harness/capture.py` made the
images (left: before, right: after).

| File | What to look at |
| --- | --- |
| `home-abukuma-desktop.webp` | Homepage → `Abukuma`: before, "No records match" with only "Clear"; after, the two cited Records with their independent-publication attribution |
| `home-abukuma-mobile.webp` | Same at 375px |
| `archive-amraam-empty-desktop.webp` | Archive (Research focus) → `AMRAAM`: before, "Search all 2,013 records" (still empty); after, "Search all published material (2 more)" |
| `archive-laos-focus-mobile.webp` | Archive (Research focus) → `Laos` at 375px: after, the widen line under the result count for the 8 published items the focus omits |

These are review evidence only; no build or test uses them.

## Remaining limitations (measured, not changed)

- Title search (`q`) is a literal substring, so a multi-word topic such as
  `Abukuma destroyer` finds nothing by title. **Keywords** (under Filters)
  find all three items. Keywords also match public metadata: `China` goes
  from 283 title matches to 1,929. Changing what the main box means is a
  separate decision.
- Briefs that mention a topic only in their summary need **Keywords**, not
  the title box.
- Original-language and English titles are not cross-linked. `Scarborough`
  finds PLA Watch issues; the Chinese records are titled 黄岩岛 / "Huangyan".
- The widen count appears only after a search or filter. The server-rendered
  first page and an unfiltered sort or page change do not show it.
- Generic official-link titles (USCC, Treasury, BIS, PACOM references) are not
  findable by topic.
