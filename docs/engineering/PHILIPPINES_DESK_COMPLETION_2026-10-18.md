# Philippines Desk — AFP official-link release candidate (18 October 2026)

PR #816 connects the existing AFP shadow evidence to the existing regional
official-link admission, desk renderer and Pages path. It adds no collector,
database table, permission framework or publication system. Branch
`claude/philippines-desk-completion-afp`, stacked on the Indonesia lane (#812).

## Source contract

| Family | Admitted automatically | Public fields | Excluded |
|---|---|---|---|
| AFP articles (`ph_afp_articles`) | Owner-authorized standing verified links for existing and future eligible records (frozen 23 at `8a63ba4`, manifest `c97c1088…`, preserved as pinned baseline) | canonical `afp.mil.ph/news/` URL, publisher date, publisher, Git commit, metadata digest | headline, body, photograph, translation, model text, analysis |
| NSC official statements | No | none | everything |

**Owner authorization updated on October 18.** The owner separately approved
standing publication of verified neutral AFP official-link metadata for
existing and future eligible records without per-record review
(`DECISION_LOG.md`; `config/afp_kemhan_owner_link_activation.json`).
This does not claim any post-pin individual human review. Disputed or
changed/missing previously released records, incompatible metadata, capture
or source-use failures, and substantive anomalies still hold. No additional
rights for titles, bodies or analysis are granted.

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
4. **Authorized standing metadata support.** The owner-approved
   `ph_afp_articles` entry is now present in
   `standing_link_metadata_authorizations`. On an authorized production run:
   - verified post-pin records enter the existing source-link projection under
     `STANDING_REVIEW_BASIS` and receipt v2 counts them as
     `released_without_record_specific_review`, not individually reviewed;
   - a previously released record that changes or disappears holds the whole
     run.

   A forged receipt cannot widen release. This policy commit is only on
   draft PR #816, not `main`. After an approved merge, the workflow's
   main-branch push trigger or daily schedule can use the standing policy.
   No collectors, bridge variables, database or Pages publication are activated
   by the policy commit itself.
5. **Desk contract after admission.** `test_desk_rollout_contract` used to
   require the empty-shadow heading on the Philippines page. That would have
   failed on main after the first production run. It now requires the
   verified-links heading and an exact identity match with the DB once rows
   exist, and still requires an empty public corpus.

## Verification (18 October 2026)

### Final rehearsal under the pinned standing policy

Candidate: main `f3ff927` merged with this branch; scratch copy of main's own
`pla_watch.db`; real `shadow/ph-afp` at `97ec0bf`; real GitHub run records.

- **Selection:** 29 eligible, 29 approved, 0 held. Of the 29, 23 are the
  frozen reviewed cohort and 6 are `released_without_record_specific_review`.
  `record_specific_review_receipts_verified` stays `false`. 12 authenticated
  scheduled days; manifest `ead0fe45…`.
- **Admitted rows:** 29 Philippines rows, publisher dates 2026-09-25 to
  2026-10-16; every URL is on `afp.mil.ph/news/`.
- **Replay:** 0 new rows, 29 unchanged, DB hash unchanged.
- **Integrity:** `integrity_check` ok. Of 19 tables, only
  `regional_official_source_links` differs.
- **Safe failure and recovery:**
  - a wrong source commit holds with `source_checkout_not_at_requested_commit`;
  - an altered, previously released row holds with
    `previously_released_source_version_changed`;
  - both leave the DB byte-identical, with no temp residue;
  - a fresh run afterwards admits the same 29.
- **Rendered page:**
  - `validate_output.py` passes with the 10 governed warnings;
  - the page's `data-regional-official-source-id` set equals the 29 DB rows;
  - none of the 29 preserved originals leaks its title or body text;
  - no other changed output file mentions `afp.mil.ph`.
- **Signed envelope:** a 29-record private envelope is 3,966 gzip bytes
  (5,288 base64 characters), against the 48 KiB limit. The limit is reached
  near ~350 records, so it needs a maintenance follow-up. Over the limit, the
  envelope fails closed (`signed_envelope_too_large`).
- **Cutover compatibility:** main + this branch + #797 merged passes
  #797's AFP readiness, schedule and binding tests plus this lane's suites
  (181 tests), and `audit_shadow_workflow_bindings.py`.

### Earlier frozen-only rehearsal (superseded selection)

Before the standing ruling, the same tip gave 23 approved and 6 held, with the
same replay, integrity and leak results. Its post-merge production state
against main `52667d6` was:

- the main commit touches exactly `pla_watch.db` and `output/philippines.html`;
- the page embeds no render date, so a 0-row daily run commits nothing.

Concurrency and recovery work as follows:

- the workflow has its own concurrency group;
- it refuses to commit if `shadow/ph-afp` or `main` moved since admission;
- it pushes main and gh-pages without force, and aborts if gh-pages moved;
- a failed run leaves production untouched;
- a run that pushed main but failed before Pages republishes the committed
  page on the next run;
- rebasing DB writers use the `reconcile-db` driver, so admitted AFP rows
  survive their rebases.

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
main `52667d6`, on current main `f3ff927` merged with #812, and on this branch.

## Owner-controlled dependencies

- **Merging #816 is the activation point.** The push trigger runs at once and
  publishes every verified, non-held AFP link at the then-current
  `shadow/ph-afp` tip. That is 29 at `97ec0bf`: the frozen 23 plus 6 under the
  standing authorization. The daily cron reconciles afterwards.
- **Collector cutover.** Merging #797 retires the public AFP collector, and
  private #11 starts the private one. Until then the public collector on main
  keeps running.
- **Bridge credentials.** After the cutover, new records reach this workflow
  only with owner-configured bridge credentials.
- **Owner standing metadata decision: APPROVED and pinned.** No further
  per-record review is required for eligible neutral AFP official links.
  This is not permission to merge, start private collection or publish IPR
  editorial content.
- **Sanlakas/JPSCC:** the editorial handoff
  `research/philippines/sanlakas_2026/EDITORIAL_HANDOFF_2026-10-18.md` stays
  pinned, with its opening-venue and Gavan/Galvan holds. No publication is
  made.

## Page copy

The Philippines registry blocker no longer cites the superseded thirty-day
gate. It states the October 18 scope instead: verified link metadata only;
post-cohort links are not individually reviewed; titles, bodies, translations
and corpus admission still need their own review.

Two shared desk-template strings are left unchanged, because Indonesia
renders them too:

- the "Individually reviewed official-source references" lane still reads
  "none" for title-bearing references, which is accurate for that lane;
- the status-panel sentence says "individually admitted", meaning each record
  passed admission, not that it was individually reviewed.
