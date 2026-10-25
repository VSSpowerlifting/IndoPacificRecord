# Living Dossiers: maintain and review

The Maritime Cooperation 2026 manuscript remains revision 2: eight findings,
five exact preserved source versions and six chronology entries. On 25 October
2026 Benjamin Yang reaffirmed his approval of revision 2 and its reviewed
presentation at head `38f9f2bf8f45e258ad9592272b865d41cd29d72f`. The actual
editorial receipt is recorded in `DECISION_LOG.md`, the dossier metadata and
`core/dossier_decisions.py`. Codex remains credited for preparation; Benjamin
Yang is the responsible human editor. The confirmation date is recorded without
inventing an earlier review date. No finding or presentation source changed.

Release readiness still requires the separate narrow source-use decision for
the five bound versions. Editorial approval alone does not grant it. Merge,
deployment and publication remain unauthorized by this preparation task.

## Ordinary workflow

Use the repository Python environment (on the current machine:
`/Users/benjaminyang/pla-watch/.venv/bin/python`; substitute for `.venv/bin/python`
below). From the task worktree:

```sh
.venv/bin/python scripts/dossier.py check dossiers/maritime-cooperation-2026.json
.venv/bin/python scripts/dossier.py changes dossiers/maritime-cooperation-2026.json
.venv/bin/python scripts/dossier.py ready dossiers/maritime-cooperation-2026.json
.venv/bin/python scripts/dossier.py preview dossiers/drafts/maritime-cooperation-2026.json \
  --out /tmp/ipr-dossier-new-private-review
python3 -m http.server 8785 --bind 127.0.0.1 \
  --directory /tmp/ipr-dossier-new-private-review
```

The preview example requires an actual next draft in `dossiers/drafts/`; it does
not create one. Open `http://127.0.0.1:8785/dossier/maritime-cooperation-2026.html`.
`check` returns 0 after shape, actual source reconciliation and chronology
binding pass; it prints separate source-use/editorial holds. `ready` returns 1
while those decisions are missing, 2 on invalid/stale input, 0 only after all
gates pass. `changes` shows actual authored notes. `--db` selects a frozen input;
all source reads use `scripts.reconcile_db.read_only` scratch custody.
`site/render.py --review-dossier PATH --out NEW_EXTERNAL_DIRECTORY` is the same
shared renderer entry point for draft revisions. The approved canonical file
is not a draft and cannot use that preview flag. A release candidate uses an
isolated normal shared render, which fails closed while source-use holds remain.
No model call is involved.

Review trees are new, disposable directories outside every Git working tree,
with mode 0700. Existing destinations and user-created symlink paths are refused;
macOS's system `/tmp` and `/var` aliases are supported. Serve only on loopback;
there is no upload endpoint. All pages are noindex, without canonicals, feeds or
sitemap. **Noindex is not access control.** The generated tree includes existing
record pages with preserved originals for source review: do not upload it or
copy those bodies/screenshots into a public review artifact. The dossier page
itself contains IPR prose, source metadata and links, never original titles,
quotations, bodies, translations or images.

## Source evidence and exact approval

`core/dossier_contract.py` remains the v1 shape/digest contract. Registered
institution/source IDs now allow their real underscores; URL slugs stay strict.
The optional `chronology` member binds the existing timeline's entire content
SHA-256. Timeline bytes and approval state are unchanged. The dossier displays
only its paraphrase/date/reference projection; it does not publish a Timeline.
Any chronology edit holds the dossier until its binding is deliberately updated
and the resulting new content reviewed. No independently editable chronology
copy is introduced.

`core/dossiers.py` checks ID, exact URL, desk/source/institution/language,
publication date, body SHA, registry eligibility, relevance and tombstones. Errors
name the affected findings. Its template/index projection cannot carry originals
or stored model output. A body hash pins only the body; title continuity or
contemporary publisher-page parity is not asserted. Publisher names and issuer
institutions are read from the registry-backed source records, not guessed.

Actual human authority lives outside manuscript assertions. Follow the existing
owner-message → `DECISION_LOG.md` → reviewed source-change convention. After an
explicit owner decision, an authorized maintainer records its narrow scope in
`core/dossier_decisions.py`: `SOURCE_USES` binds the exact sources and public
fields, and `PUBLICATIONS` binds the exact content digest **and** human approval
receipt. There is no environment flag or CLI argument that grants either.
The revision 2 editorial decision is recorded; the source-use map remains empty
until its separate decision is supplied. Synthetic authority is injected only
by tests, whose draft fixtures are independent of the real canonical status.
Hashes establish integrity, not authorship or legal rights; do not add a registry entry merely because a JSON receipt looks
plausible. A later authentic decision may supersede a hold without reopening
settled questions. Publisher correspondence is not assumed necessary for every
reporting use.

For this candidate the needed public fields are institutional attribution,
publication dates, independent IPR paraphrases, official links and links to the
existing canonical full-body record pages. The October 18 narrower Timeline
selection is useful presentation precedent; its review expressly leaves actual
source-use clearance unresolved. Brief No. 15's October 5 approval is reused
only to identify related approved analysis. It approves neither this dossier
nor these new source uses. No private companion access was necessary: all five
originals are available in the assigned archive.

The editorial decision on the exact findings, scope, chronology, qualifications
and reviewed presentation is now recorded. The remaining human decision is the
narrow source-use determination for the three publisher families. Full originals,
translations, substantial excerpts and media are outside this dossier's public
projection. Subsequent release still needs explicit merge/deploy/publication
authority. The separately tracked Pages writer race/guard work is not resolved
or activated by this implementation; assess the then-current deployer before
an authorized release.

## Reviewed revisions

The approved manuscript is revision 2: a shorter title/answer and tighter finding
prose, with the original revision 1 preparation note retained. The 25 October
approval reaffirmation changes only status, editor/review metadata and its exact
receipt; it does not create revision 3 or rewrite the authored change history.
Edit manuscript JSON through a structured JSON writer and rerun `check`; never edit generated HTML. Preserve stable
finding IDs. Add one concise sequential note for a new revision, naming the
affected current findings and explaining removals in its summary.

After a dossier is approved, keep `dossiers/<slug>.json` as the last approved
publication. Prepare its next version at `dossiers/drafts/<slug>.json`, remove
the old approval, set draft status and unreviewed metadata, increment revision,
update the date/change note, and review that file through the same CLI.
Normal builds ignore the nested draft. An explicit private review replaces only
that route in its disposable tree; the approved source stays unchanged.
Replacing the canonical approved file with an unapproved draft fails explicitly
instead of silently dropping the publication. Promote a new version only after
actual exact-version approval and update the independent decision binding in
the same authorized source change. Git plus the authored change ledger hold
history; no version service or automatic re-authoring is required.

## Verification

```sh
.venv/bin/python -m unittest tests.test_dossier_contract tests.test_dossiers \
  tests.test_dossier_rendering tests.test_timelines tests.test_timeline_rendering -q
```

The new tests use a disposable frozen copy of the real DB and test-only
synthetic approval decisions. They exercise changed/missing/retired evidence,
source-use/publication boundaries, draft exclusion, safe revision review,
approved shared rendering/discovery, links, deterministic output, actual browser
keyboard/citation/no-JS/print/responsive behavior. No original text is copied into
fixtures. Required PR offline CI runs the full suite and a fresh isolated
`site/render.py` + `scripts/validate_output.py` on GitHub's PR merge ref. A green
local subset is not that gate. Tracked DB, output, Brief sidecars and Timeline
must remain unchanged; the accepted output-validator baseline is 10 warnings.

## Reading presentation

The dossier opening uses the existing paper shell and navy comparison panel.
`reported_windows` derives its inclusive September 3–9 day cells from the two
claims and checks their dates/source sets against the bound chronology and the
verified pilot assertions. Both endpoints count; cell fill is a stated window,
not intensity or independent confirmation. Source drift fails before rendering.
`reading_view` derives ordinals, evidence counts, publication-order ledger entries,
readable source/language labels and finding returns without changing custody or
authorization. English publisher abbreviations are English text, even when the
source document is Chinese; the stored language remains available in metadata.

A small optional `dossier.js` marks desktop reading location and measures a
fixed/sticky masthead if present. Native links, history and disclosures work
without it; mobile has one contents disclosure. Print exposes evidence/date
basis and publisher URLs even when disclosures were closed. Dossier CSS, JS and
the existing illustrative texture ship only with a rendered dossier (or, for
the texture, its existing rendered Timeline). A withheld draft adds none of them.

Visual repair (24 October): the owner supplied the actual selected reference
and a two-file CSS/template patch. It was applied and refined using side-by-side
reference/actual comparisons at 1440×1024 and 1280×900, plus 375px mobile and
320px overflow checks. The year is shown in the window heading; the exact
inclusive calendar is a native disclosure and remains expanded for print.
The single private notice sits in the ivory opening, with honest preparation /
review credits below. English source labels, dates and real manuscript facts
are unchanged. `design-qa.md` records actual comparisons and expected differences.

The final targeted correction scopes calendar summary colors to the navy
comparison panel in closed/open/hover/keyboard-focus states and uses its light
focus-ring token. Expanded desktop and mobile screenshots were inspected. All
42 focused dossier, Vietnam admission and tracked-database checks pass after
incorporating main `766aff33f4`; its existing Vietnam fixture repairs are retained
unchanged. Final-head CI and isolated production validation are separately
evidenced in PR #864; these local checks are not substitutes.

## Internal source-to-finding matrix (no source text)

All five bodies were read in full on October 23, 2026 and checked through the
read-only snapshot helper. Exact hashes and identities are in the manuscript;
these locators identify the relevant passages without reproducing them.

| Finding | Supporting records / publication dates | Basis and material limit |
| --- | --- | --- |
| preparation-and-opening | 3924 / Sep 6; 4466 / Sep 5 | PLA Daily September 5 dateline and shore-phase paragraph date preparations to Sep 4; both report Sep 5 opening. Publication agreement is not independent observation. |
| sea-phase-plan-and-report | 4466 / Sep 5; 4102 / Sep 12 | MINDEF prospective schedule; PLA Daily transition paragraph dates Sep 8, later gunnery paragraph dates morning Sep 9. Not every serial independently confirmed. |
| shared-conclusion | 4472 / Sep 9; 4102 / Sep 12 | MINDEF earlier-that-day statement; PLA Daily opening paragraph dates end Sep 9 and describes five days. 4164 qualifies starting boundary. |
| ministry-window | 4164 / Sep 14 | Explicit Sep 3–9 in ministry answer; no separate Sep 3 event or explanation. 3924/4466/4472 qualify the starting boundary. |
| singapore-window | 4466 / Sep 5; 4472 / Sep 9 | Participation interval then explicit exercise interval, both Sep 5–9; one institution, two releases. 4164 differs. |
| boundary-unresolved | all five | Editorial comparison of explicit dates; preparation/opening cannot explain Sep 3. No corrected master date asserted. |
| activity-versus-performance | 4164, 4466, 4472 | Listed serials and participant assessments; no independent performance measurements. |
| replenishment-limit | 4164 / Sep 14; 4102 / Sep 12 | Ministry list and PLA Daily positioning/line-handling paragraph; neither establishes fuel/stores transfer. MINDEF 4466/4472 omission is not proof of absence. |

For PLA Daily, the archive's institution is `cn_cmc_political_work`, its publisher
is `pla_daily`; the ministry answer is `cn_mnd` / `mod_china`. MINDEF is
`sg_mindef` / `sg_mindef_releases`, language `en`; Chinese sources are `zh-Hans`.
No publisher photo or official quotation is needed in the dossier page.
