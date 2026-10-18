# Philippines Desk — AFP official-link release candidate (18 October 2026)

PR #816 connects the existing AFP shadow evidence to the existing regional
official-link admission, desk renderer and Pages path. It adds no collector,
database table, permission framework or publication system. Branch
`claude/philippines-desk-completion-afp`, stacked on the Indonesia lane (#812).

## Source contract

| Family | Admitted automatically | Public fields | Excluded |
|---|---|---|---|
| AFP articles (`ph_afp_articles`) | The Oct 15 frozen cohort only: 23 records at pin `8a63ba4`, metadata manifest `c97c1088…` | canonical `afp.mil.ph/news/` URL, publisher date, publisher, Git commit, metadata digest | headline, body, photograph, translation, model text, analysis |
| NSC official statements | No | none | everything |

**Future AFP records are held.** The Oct 18 standing future-record
authorization (DECISION_LOG) names Kemhan Berita only and lists other source
families as not authorized. Post-pin AFP records therefore hold with
`unreviewed_source_selected_for_release`. No per-record review is claimed or
fabricated.

## What this change adds

1. **Trusted validator.** `core/ph_afp_release_validator.py` recomputes every
   gate that `admit()` requires from primary evidence:
   - owner pin ancestry;
   - re-hashed capture blobs;
   - ledger ↔ history-commit reconciliation;
   - GitHub's own records for every scheduled attempt.

   It reuses only the source-neutral helpers from the Indonesia validator. No
   Kemhan exclusions, publisher assumptions or scheduled-run minimums are
   copied. Approval is recomputed from the public baseline, never taken from a
   receipt.
2. **Admission CLI.** `scripts/admit_ph_afp_official_links.py` follows the
   same steps for live, rehearsal and replay runs:
   - writes a scratch copy;
   - compares a digest of the unrelated rows;
   - reads the copy back read-only;
   - swaps it in atomically with `os.replace`.
3. **Page-only production workflow.**
   `.github/workflows/ph_afp_verified_official_link_production.yml` is
   triggered by a push to main, a daily cron at `29 16 * * *`, or a manual
   dispatch.
   - It commits only `pla_watch.db` and `output/philippines.html`, and
     publishes only `philippines.html` to gh-pages.
   - Post-cutover private records arrive only through the HMAC envelope
     bridge, which stays dormant unless `vars.AFP_METADATA_BRIDGE_ENABLED` is
     `true` and `secrets.AFP_BRIDGE_KEY` is set.
4. **Dormant standing support.** If the owner adds one `ph_afp_articles` entry
   to `standing_link_metadata_authorizations`:
   - post-pin records are released under
     `STANDING_REVIEW_BASIS`, and receipt v2 counts them as released without
     record-specific review;
   - a previously released record that changes or disappears holds the whole
     run.

   A forged receipt flag without a policy entry cannot widen release. The
   policy file is not a push-trigger path, so an activation edit takes effect
   at the next daily cron.
5. **Desk contract after admission.** `test_desk_rollout_contract` used to
   require the empty-shadow heading on the Philippines page. That would have
   failed on main after the first production run. It now requires the
   verified-links heading and an exact identity match with the DB once rows
   exist, and still requires an empty public corpus.

## Verification (18 October 2026)

The rehearsal ran on a scratch copy of `pla_watch.db` against the real
`shadow/ph-afp` at `97ec0bf`, with real GitHub run records.

- **Selection:** 29 eligible, 23 approved, 6 held, 0 released without review,
  12 authenticated scheduled days.
- **Replay:** 0 new rows, 23 unchanged, DB hash unchanged.
- **Integrity:** `integrity_check` ok; no unrelated table differs.
- **Admitted rows:** 23 Philippines rows, dated 2026-09-25 to 2026-10-14.
- **Rendered page:**
  - the page's `data-regional-official-source-id` set equals the DB rows;
  - none of the 29 preserved originals leaks its title or body text;
  - none of the other 950 render-drift files mentions `afp.mil.ph`.
- **Post-release state:** with tracked `output/` plus only the newly rendered
  `philippines.html` and the admitted DB, exactly those two files differ and
  `validate_output.py` passes with the 10 governed warnings.
- **Tests:**
  - 84 desk/regional/Philippines/Indonesia modules (1,337 tests) pass against
    the admitted DB;
  - the focused AFP set (219 tests) passes.
- **Concurrency and recovery:** the workflow has its own concurrency group.
  Before committing, it refuses to continue if `shadow/ph-afp` or `main` has
  moved since admission. It pushes main and gh-pages without force, and it
  aborts if gh-pages has moved. A failed or rejected run therefore leaves
  production untouched, and the next cron retries from fresh state. A run
  that pushed main but failed before Pages republishes the committed page on
  the next run.
- **Source tip:** `shadow/ph-afp` was still `97ec0bf` at verification.

**Full offline suite.** `unittest discover` ran on the candidate merged into
main `52667d6`: 7,531 tests, 7 failures, 28 errors and 11 skipped. Running
the same 34 IDs alone on plain `52667d6` gives the same result, so none is a
regression. The causes:

- macOS `/private` temp-path resolution: 21 evidence-store `unsafe_store_root`
  errors and 3 path-equality mismatches;
- the missing `docx` module (4) and `gpg` binary (2);
- one Sunday-writer citation rule;
- four `test_preview_prototype` record-page assertions.

None of them touches AFP or Philippines code.

The earlier #812 `TestRecordSemantics` failure is **inherited from main**. It
reproduces on main `87196e9` alone, with the same 20 IDs, and passes on
current main `52667d6` and on this branch.

## Owner-controlled dependencies

- **Merging #816 is the activation point.** The push trigger and the daily cron
  then write `pla_watch.db` and `philippines.html` for the 23-record cohort
  under the Oct 15 decision.
- **Collector cutover.** Merging #797 retires the public AFP collector, and
  private #11 starts the private one. Until then the public collector on main
  keeps running.
- **Bridge credentials.** After the cutover, new records reach this workflow
  only with owner-configured bridge credentials.
- **Owner question (open):** "May the existing AFP source family automatically
  publish verified neutral official-link metadata for future records under the
  existing source, provenance, rights, and anomaly safeguards, without new
  per-record human approval?"
- **Sanlakas/JPSCC:** the editorial handoff
  `research/philippines/sanlakas_2026/EDITORIAL_HANDOFF_2026-10-18.md` stays
  pinned, with its opening-venue and Gavan/Galvan holds. No publication is
  made.

## Known page-copy staleness (not changed here)

The desk registry's barrier text still cites the superseded thirty-day
reliability gate. The "Individually reviewed official-source references" lane
still reads "none" under the admitted links. That is accurate for that lane,
but it reads awkwardly. Both need an editorial copy decision; neither affects
admission.
