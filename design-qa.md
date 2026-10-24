# Living Dossier refinement — local design QA

**Final result: passed** against the owner's explicit written composition and
reading requirements. Image-level fidelity is unverified: the selected generated
image and named screenshot attachments were unavailable. The brief explicitly
authorizes this fallback. No substitute design selection was made.

## Evidence and comparison

Source truth: `IPR_Dossier_Design_Refinement_Codex_Prompt.md`, selected first
concept's written composition, current IPR tokens/fonts, and the actual previous
private candidate at head `d569f00b8f75adbf4048bb3550f3d9ac9b781311`.

Local evidence directory (outside Git and private review trees):
`/Users/benjaminyang/.codex/visualizations/2026/10/23/dossier-refinement/`.
The before/after pairs are `before-` / `after-` plus `desktop.png`,
`evidence.png`, `chronology.png`, `accounts.png`, `ledger.png`, `mobile.png`,
`mobile-evidence.png` and `print.png`. Additional after states cover return,
mobile windows/contents and no-JS. `qa.json` records computed geometry, fonts,
requests, responsive sizes and contrast. No publisher original is pictured.

Desktop pairs: 1280×900 CSS and image pixels, device scale 1. Mobile pairs:
375×812 CSS and image pixels, device scale 1. Both use locally loaded fonts and
the same route, preserved source packet, draft status and interaction state.
No density normalization was needed. Full openings and focused finding,
chronology, ledger and print captures were opened and visually inspected.
The before/after opening images were presented together for comparison.
This is an intentional redesign of the previous candidate, not its reproduction.

## Findings resolved

- Inherited generic heading padding/rules inflated the navy opening. Scoped
  heading resets, a shorter actual draft title/overview and compact spacing
  produce a balanced 60.8% / 39.2% opening. The first finding heading begins at
  about 889px; comparison and answer finish within the first 900px. The prose
  column is 680px, beside a 180px rail and 48px gutter.
- Target styling initially tinted whole sections and outlined a source entry.
  It now marks the finding/section heading or ledger heading only, retaining
  native keyboard focus. Post-fix reading and ledger captures verify the change.
- Early expanded-state captures caught the shared 180ms disclosure transition.
  Final captures wait for its settled state. Evidence remains native and visible
  without JS; print exposes closed disclosure contents.

## Required surfaces and interactions

- Typography: actual Instrument Serif title 56px; Source Serif 4 finding
  headings 26px desktop / 23px phone; reading text 19px / 18px at line-height
  1.7. Inter metadata, dates and controls. Locally served fonts loaded correctly.
- Layout: one split opening, one common-axis comparison, ruled scope strip,
  quiet derived ordinals, event/publication tracks and deduplicated source
  ledger. Rail disappears at 960px; mobile contents is one native disclosure.
  No document overflow at 320, 375, 768, 960 or 1280px, or clipped date content.
- Color: existing ivory/navy/turquoise tokens; source statements neutral.
  Measured paper text pairs range 5.11–12.72:1; on-navy pairs 8.47–12.67:1.
  Evidence tint and target treatment retain reading contrast.
- Assets: existing IPR masthead retained; existing maritime texture is faint
  at the navy outer edge. No generated/stock image, new logo or evidence image.
- Content: manuscript revision 2 has a 45-word overview, all eight stable
  findings, original source bindings and material limits. Exact seven-day
  inclusive geometry agrees with bound claims/chronology. Starting boundary,
  independent-performance and replenishment-transfer qualifications survive.
- Interaction: keyboard disclosure/focus, desktop current-section state,
  citation → ledger → finding, natural browser Back, canonical record links,
  citation-copy success and selectable fallback, short-viewport rail scrolling,
  mobile contents and touch links checked. No page errors, failed requests or
  external requests in captured reading journeys. No-JS and reduced-motion
  paths pass; reduced-motion transition duration is zero.
- Print: neutral single-column output, both windows and caveat, expanded date
  basis/source references, visible URLs and selectable citation. The 19-page A4
  test PDF contains source publication dates and all material qualifications;
  there is no decorative PDF control.

## Verification boundary

120 focused contract/source/render/timeline checks passed; all 10 dossier
rendering checks passed after the final target-style adjustment. Exact final
revision CI and isolated production validation are reported in PR #864, not
inferred from these local checks. The real dossier remains draft and adds zero
public routes, discovery entries, feeds, sitemap entries or backlinks.

No remaining actionable P0/P1/P2 issue was observed against the written brief.
The outstanding decisions are the narrow source-use determination for five
bound versions across three publisher families, exact human editorial review,
and separately authorized release. No human approval, merge or publication is
claimed here.
