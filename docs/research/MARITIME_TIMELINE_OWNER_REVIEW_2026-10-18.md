# Maritime Cooperation 2026 — corrected owner-review candidate

Prepared by Codex on 18 October 2026 against main
`3ee6735338a4f23f71bf67fa18a838c82bef62d6` (merged frontend #798).
This is the source-reading result for the existing pilot, complementing the
publication preflight in [PR #697](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/697),
not another engine, preflight framework or publication authorization.

Canonical candidate: `timelines/maritime-cooperation-2026.json`.
Status remains **draft**; author remains **Codex (draft preparation)** and editor
**Pending owner review**. The October 18 review date records machine-assisted
source reconciliation, as labelled in the private render, not human approval.
The Flowing Chronology frontend, stable entry IDs, dates, source identities,
ten verbatim excerpts, Brief No. 15, database and production output are unchanged.

## Six-entry evidence review

All five **complete captured originals**, their original-language titles,
publication metadata and embedded datelines were read through
`scripts.reconcile_db.read_only()`: Chinese records 3924, 4102 and 4164;
English records 4466 and 4472. Model English titles/translations were not
substituted for Chinese evidence. This verifies fidelity to preserved official
accounts, not the completeness of the captures against today's publisher pages
or an independently observed operational history.

| Entry | Evidence checked and locator | Result / correction | Remaining uncertainty |
| --- | --- | --- | --- |
| `ministry-interval`: September 3–9 | 4164, published September 14: opening briefing date and spokesman's exercise answer | Interval is explicit. Name the defence ministry precisely and identify September 3 as the unexplained boundary. | No explanation for September 3 in this packet; do not reconcile it to MINDEF's September 5. |
| `preparatory-meetings`: September 4 | 3924, published September 6: September 5 Zhanjiang dispatch; harbour-phase paragraph dates meetings/planning to the 4th | Retain. September 4 refers to those preparations, not a demonstrated formal exercise opening. The September 5 dateline is distinct from September 6 publication. | The record does not date every preparatory activity. |
| `opening-ceremony`: September 5 | 4466, September 5: opening earlier that day; 3924: September 5 dateline and opening sentence | Retain both attributed opening accounts and their separate publication dates. | Agreement between official accounts is not independent observation. |
| `singapore-interval`: September 5–9 | 4466 opening participation sentence; 4472, September 9, exercise-period sentence | Retain. Opening release describes participation September 5–9; closing release expressly repeats the exercise interval. | Still conflicts with 4164's earlier starting boundary. |
| `sea-phase`: September 8–9 | 4466's prospective shore/sea schedule; 4102, published September 12: sea-phase transition paragraph and later gunnery paragraph explicitly dated the morning of the 9th | Correct incomplete description: later reporting covers both the September 8 move to sea and September 9 morning gunnery. Retain the planned/reported distinction and qualify the extent of confirmation. The short existing excerpt supports September 8; the September 9 passage is further down the same linked record. | Dated reported activity supports both days, but does not independently confirm the complete announced programme or every serial. No capability conclusion is adopted. |
| `conclusion`: September 9 | 4472: conclusion earlier on its September 9 publication day; 4102's lead: five-day exercise ended September 9 | Attribute the headline to both closing accounts; clarify the five-day description's relationship to the unresolved interval. | Do not turn the five-day description into an inferred explanation or correction of the ministry's September 3 boundary. |

A follow-up locator in the sea-phase evidence claim explicitly distinguishes the
September 8 excerpt from the later gunnery paragraph supporting September 9.
The existing schema validator passes on that final draft; excerpts and draft
status are unchanged. Earlier browser receipts below predate this locator-only
wording change; the final preview has not been independently rerendered here.

All ten excerpt strings remain exact contiguous substrings of their preserved
bodies; no excerpt was expanded, translated or newly introduced. Publication
dates remain September 5 / 6 / 9 / 12 / 14. The evidence basis labels and
disagreement notes are supported; no claim of causality, intent or comparative
capability was added.

## Actual source uses and current measurement

These are separate decisions, even when they appear on the same page:

| Use in this candidate | Exact scope | Unresolved decision |
| --- | --- | --- |
| IPR paraphrases | Scope, observations, claim descriptions and comparison prose | Owner/editor acceptance of this exact wording and its qualifications. These are original editorial paraphrases, not permission receipts for other material. |
| Publisher quotations and original-language titles | Ten existing quotation blocks: five MINDEF (74 whitespace-delimited words, excluding titles), four PLA Daily and one China MOD. All five original titles appear in evidence/ledger displays. No publisher photographs are added. | Source/use-specific basis for the actual quotations and titles; preservation and Brief approval do not supply that basis. |
| Outward publisher links | The five stored release URLs in evidence panels and ledger; record pages also link outward | Review linking separately, particularly MINDEF's express hyperlink terms. |
| Linked IPR record pages | `record/3924.html`, `4102.html`, `4164.html`, `4466.html`, `4472.html` | Acceptable continued display of complete captured bodies on the pages this timeline directs readers to, or an explicitly authorized narrower presentation. |

**Remeasured October 18**, using the existing
`scripts/audit_generated_record_text.py`: Singapore MINDEF now has **86** stored
records and **86** generated pages; **85** nonempty bodies are displayed in full
after whitespace normalization, with zero mismatches. Record 4936 has no body;
all 86 pages carry the stored original URL. The October 9 figure of 83/84 is
historical and is not used as the current inventory.

All five pilot IPR pages were also opened live at
`https://indopacificrecord.org/record/<id>.html` on October 18: HTTP 200, original
publisher links and captured-body display were observed. Each normalized live
body's SHA-256 matched the corresponding stored body. This is bounded live
verification of **these five routes**, not all 85 Singapore pages or every CDN
cache. The private review render also displays these bodies on its linked record
pages; closing a disclosure or adding noindex does not remove body bytes.

The repository is currently PUBLIC and still tracks `pla_watch.db` and
`output/`. A renderer-only reduction cannot establish private custody of those
originals or erase historical Git/Pages copies. This is an existing distribution
issue, not a claim that publishing the timeline would create all those bodies.

## Current decisions and concrete publication choices

[Issue #326](https://github.com/VSSpowerlifting/IndoPacificRecord/issues/326)
and all eight comments were read. Its latest comment is October 10; no permission
grant or final rights disposition is recorded there. The inquiry remains marked
unsent. Current `CONTENT_AND_DATA_RIGHTS.md` §§2–5 distinguishes IPR prose, public
facts, metadata and third-party expression; it does not license publisher text.

There **is** a later architectural decision: [#332's October 15 comments](https://github.com/VSSpowerlifting/IndoPacificRecord/issues/332#issuecomment-6185501162)
approve a private-evidence direction, choose private GitHub and report a
README-only private destination. The latest setup comment expressly grants no
rights and reports no source transfer or production cutover. This resolves the
direction/provider question, not the uses above.

The current official [MINDEF terms](https://www.mindef.gov.sg/terms-of-use/),
retrieved October 18 and marked updated July 15, 2026, address prior permission
for links in §5 and public reproduction/use in §6. Whether permission or a
statutory exception covers these exact uses requires qualified human assessment;
this review makes no legal determination. The [official MOD sitemap's](https://www.mod.gov.cn/zjlm/wzdt_226173/index.html) indexed
copyright notice concerns material supplied by other publishers; it is not a
blanket reuse licence for record 4164. Direct retrieval of that official page
failed certificate hostname validation; no bypass was attempted. The 81.cn
homepage's [copyright link](http://www.81.cn/aboutus/node_74105.htm) led to a not-found page. Neither access limit is a
missing source original: all five preserved bodies were available and reviewed.
Neither establishes permission for Chinese quotations, titles or bodies.

Ben's concrete choices are:

1. **Accept the exact presentation after source-use review.** Record the
   actual permission or qualified use determination for MINDEF records
   4466/4472, PLA Daily 3924/4102 and MOD 4164, separating quotations/titles,
   publisher links and local full-body destinations. If the existing uses are
   supported, no archive migration is a demonstrated prerequisite to this
   timeline's release. Owner editorial approval alone grants no third-party rights.
2. **Choose a narrower public presentation.** Specify which quotations,
   original titles, outward links and full-body record destinations may remain.
   The present template always emits excerpts, titles and both link types;
   a paraphrase/metadata-only version therefore needs a separately authorized,
   narrowly scoped render change and another exact-content review. Removing
   quotation blocks alone does not alter the five linked body pages or public
   SQLite/history. A broader custody migration is relevant if the chosen
   decision requires the originals themselves to become nonpublic, not merely
   because this timeline exists. None is implemented here.
3. **Hold this timeline unpublished** while those exact decisions are pending.
   This is its current state; it does not authorize changing existing public
   records, Briefs or source storage.

Before any publication, Ben must also accept/correct the six entries and choose
the actual author/editor credits. No human reading, rights receipt or approval
was fabricated. Brief No. 15's existing approval remains separate. Publication
still needs Ben's explicit authorization for the reviewed artifact.

## Exact candidate and verification

`core.timelines.content_digest()` for the corrected canonical draft:

```text
26e027cb404ad61e9422351652773497deb4e5d11ec691b28e6d117a286eef64
```

This binds the current draft, including pending-review metadata. The existing
implementation recomputes the digest if status, editor, dates or wording change;
no approval block is present or supplied by this review.

Private candidate: `http://127.0.0.1:8783/timeline/maritime-cooperation-2026.html`;
library: `http://127.0.0.1:8783/timelines.html`.
Render tree: `/tmp/ipr-maritime-owner-review-20261018`.

```sh
/Users/benjaminyang/pla-watch/.venv/bin/python scripts/validate_timelines.py
/Users/benjaminyang/pla-watch/.venv/bin/python site/render.py \
  --review-timeline timelines/maritime-cooperation-2026.json \
  --out /tmp/ipr-maritime-owner-review-20261018
python3 -m http.server 8783 --bind 127.0.0.1 \
  --directory /tmp/ipr-maritime-owner-review-20261018
/Users/benjaminyang/pla-watch/.venv/bin/python -m unittest \
  tests.test_timelines tests.test_timeline_rendering -q
```

Source parity passed: six entries / five records. All **22** existing timeline
tests passed, including browser, draft exclusion and approval-digest rejection.
No full-suite rerun was needed for these content/document changes.
Desktop/mobile checks at 1280/375/320px passed with all six evidence disclosures
expanded and no horizontal overflow; mobile native disclosure also works with
JavaScript disabled. All five record destinations, the library and the actual
related Brief No. 15 opened correctly; no page errors were observed. The
candidate is visibly unpublished, `draft`, `noindex, nofollow`, with no canonical.

Local screenshots are under
`/Users/benjaminyang/.codex/visualizations/2026/10/18/maritime-owner-review/`:
`desktop.png`, `mobile.png`, `desktop-opening.png`, `mobile-sea-phase.png`,
and `sea-phase-expanded.png`. The expanded capture hides source quotation
blocks; no full publisher body is copied into this memo or its screenshots.

Production DB/output, approved Brief, source records and frontend code remain
byte-identical to the stated base. No collection, permission request, approval,
publication, deployment or source-storage migration was performed.
