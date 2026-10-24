# Living Dossier — selected-reference visual repair, 24 October 2026

**Final result: passed** for local visual/interaction QA. The targeted calendar
correction uses light on-dark tokens for closed/open/hover/keyboard focus, with
a visible 2px light focus ring. Expanded 1280px desktop and 375px mobile captures
were inspected in `dossier-calendar-correction/` beside the evidence directory
below. All 42 focused dossier/admission/database checks pass after incorporating
main `766aff33f4`, including its unchanged Vietnam fixture repairs. Mandatory
final-revision CI is reported separately in PR #864.

## Source truth and actual comparison

The owner supplied `IPR_Dossier_Visual_Repair.zip`, with `READ_ME_FIRST.md`,
`selected-reference.png` and a two-file patch based on `d99c9ff51a`. The patch
passed `git apply --check`, was applied, rendered, inspected, then refined.
Its sample prose and citations were not adopted as evidence or manuscript text.

Local evidence directory, outside Git:
`/Users/benjaminyang/.codex/visualizations/2026/10/24/dossier-visual-repair/`.
The supplied reference is preserved there. `comparison-1440.png` and
`comparison-1280.png` put the reference and actual final rendering side by side
in one comparison image. Both boards were opened and visually inspected.

The reference is 1487×1058 pixels. It is fit proportionally into 1440×1024 or
1280×900, with minimal letterboxing; actual captures use those exact CSS sizes
and device scale 1. `before-opening-*` / `before-finding-*` show the previous
head; `patch-v1-*` show the unrefined patch; `repair-v2-*` show the first repair.
Final `after-*` captures include both desktop openings, the first finding,
expanded evidence/calendar, mobile windows/contents, source ledger/return,
chronology, accounts and print. Focused reading and mobile captures were also
opened individually; whole-page comparison alone was not the acceptance test.
There is no supplied mobile reference; 375px is the responsive adaptation.

## Comparison findings and fixes

- The raw patch kept a full-width preview row above the split, leaving the navy
  panel below the masthead. The one existing notice now sits in the ivory
  column; the navy starts immediately below the unchanged shared masthead.
  This is a local template placement change, not a privacy/publication decision.
- The raw patch's type remained smaller and its panel too tall. The final title
  is Instrument Serif, about 84px at 1440 and 74px at 1280; the subtitle, issuer
  labels and dates share the reference's stronger display-serif treatment.
  Tighter navy spacing keeps real citations, the unresolved-boundary note and
  calendar control while balancing the columns naturally.
- Labelled metadata has fine separators; compact, accurate Codex preparation /
  pending-human-review credits occupy a row below the opening. These credits
  remain present even though the mock omits them.
- Finding headings are lighter, larger display serif. Desktop prose, citations
  and evidence align with their heading after the quiet ordinal. Keyboard focus
  marks the heading rather than outlining the entire long finding. Mobile
  retains the full reading width and a 40px permalink column.
- The first browser checks caught 320px metadata overflow. Two phone columns
  plus a full-width cutoff row now wrap cleanly. Final 320/375/768/960/1280
  checks have no document overflow.

Expected differences are deliberate: current IPR publication-status/masthead
chrome is retained; actual manuscript text is longer than the mock's sample;
real citations, a calendar disclosure, review credits and the real section intro
remain. Consequently the first finding starts lower than in the concept image.
Its heading starts around 878px at 1280×900 and 893px at 1440×1024. The reading
plane is 740px with approximately 704px prose after the ordinal gutter, preserving
readability rather than stretching the mock's sample text across the page.

## Verification surfaces

- Actual local Instrument Serif, Source Serif 4 and Inter fonts loaded.
  Sustained prose remains Source Serif 4 at 19px desktop / 18px phone, line 1.7.
- Existing ivory/navy/turquoise palette and maritime texture retained. Token
  text contrast pairs range 5.11–12.72:1 on paper and 8.47–12.67:1 on navy.
  No replacement logo, stock image, invented evidence graphic or new asset.
- Both date ranges still derive from the same source-bound data. Their year is
  visible in the panel heading; exact datetime attributes and inclusive cells
  are retained. The optional calendar opens with native keyboard interaction,
  works without JS, and prints even when closed.
- Source → ledger → finding, browser Back, active/sticky contents, keyboard
  focus, citation copy success/fallback, mobile contents, reduced motion and
  print were exercised. Captured journeys recorded no page errors, failed
  requests or external requests. Reduced-motion transitions are zero.
- Closed calendar and evidence contents are visible in print. The test PDF
  includes publication dates, qualifications and official URLs; no fake PDF UI.
- All 28 focused dossier source/rendering checks passed. No manuscript, source
  binding, core resolver, decision registry, DB, Brief/Timeline, generated output,
  JavaScript or pipeline file changed in this visual repair.

No actionable P0/P1/P2 visual issue remains against the supplied composition and
retained real content. Remaining publication decisions are unchanged: exact human
editorial review and the narrow source-use determination for the five bound
versions. This candidate has not been merged, deployed or published.
