# Public China headline completion

Engineering candidate from main `611c14cb4c1ddeee39844db9ad1f6919525f172f`.
Integrated with newer main `f212e1e04f7ea1793edb6dd50dcbd3803d5930be` before
final verification; its Korea/Indonesia and regional-schema changes are retained.
No production database write, paid model call, merge, publication or deployment
is part of this change. Tracked `output/`, sidecars and editorial records stay
unchanged. Title-only Daily processing defaults to **off**.

## Diagnosis and current public counts

Read-only measurement of the current public China `articles` corpus, joined to
enabled China sources and excluding held processing states and retirement
identities. No private/shadow store or retired article content is enumerated.
The reproducible receipt is
[`dry-run.json`](../evidence/china-title-translation/dry-run.json).

| Processing state | Valid stored English (Chinese source) | English originals | Missing Chinese title translations |
|---|---:|---:|---:|
| Analyzed | 479 | 175 | 0 |
| Not selected for analysis | 0 | 21 | 150 |
| Awaiting screening | 0 | 0 | 1 |
| Analysis incomplete | 0 | 0 | 0 |
| Total | 479 | 196 | 151 |

826 public China records; 654 have a stored English title. **Zero** valid stored
English titles are missing from the committed compact index. Both public
indexes and HTML already prefer `title_english`. The defect is missing
translations, rather than a hidden stored translation: `Analyzer.analyze()`
returns after a screening rejection, and `pipeline.py` previously persisted
`title_english` only through `db.update_analysis()` after a completed summary.
The old body-translation backfill also requires `passed_relevance=1` and runs
translation, summary and categorization together.

Blank and invalid stored translations: **0**. Known stale title receipts: **0**;
legacy titles have no original-title-version receipt, so their historical
staleness cannot be established. They are preserved, not retranslated on an
assumption. The 196 English originals need no new translation; 21 screened-out
English originals already display/search through the original-title fallback.

## Implementation and boundaries

`Analyzer.translate_title()` reuses the existing forced-tool Anthropic client,
account-error classification and usage ledger, on the configured analysis
model. It sends only JSON containing the exact original headline and an explicit
untrusted-data instruction. It requests one `title_en`, with no body, summary,
classification or interpretation. Malformed/empty responses fail validation;
the existing tool wrapper rejects truncation and missing tool blocks.

`storage/title_translation.py` owns eligibility, reservation and completion on
the existing `articles` row. It checks the public China source, source identity,
URL, exact original headline and existing English value under SQLite's writer
lock. A claim is committed before paid dispatch; completion compares the owned
claim again and refuses changed source text, changed eligibility or concurrent
title edits. Successful titles stay in `title_english`, the existing authority.
Full-analysis writes and DB reconciliation preserve valid China titles and
carry successful title-only receipts without inventing completed analysis.

Migration **0011** adds nullable title provenance/retry/claim columns and writes
no observed data. Version 0010 belongs to the integrated regional source index.
Provenance binds SHA-256 of the exact original headline, model, prompt version
and completion time. It does not reuse the body-analysis model fields or set
`analyzed_at`. The fingerprint includes the new title provenance. Existing
screening scores, processing states, flags, bodies and summaries are untouched.

Retry accounting reuses `core.processing_state`'s five-attempt budget, on separate
title columns so a headline error cannot pause body analysis. Failed results
leave the original intact. A process crash leaves an owned claim for one hour;
after expiry, it can be retried within that budget. A crashed request whose
provider response was lost may have consumed tokens: exactly-once billing
cannot be guaranteed across such a crash. Live claims prevent concurrent
duplicate dispatch, and completed valid titles prevent repeat work.

New title receipts are checked when loading HTML and both indexes. Stale or
invalid China translations fall back to the original. Archive rows, record
pages, citation processing notes and CSV/JSON processing labels identify machine
translation without asserting human review. Source-text citations keep the exact
original-source title. The six-column compact index and research export fields
are unchanged; archive bulk records still have no body, summary or source URL.
The existing `data-text` renderer supports the new label without changing any
JavaScript: Archive remains **9,879 raw JS bytes** including `shell.js`.

Official-link/neutral-label metadata, shadow stores, held/paused/terminal or
retired records and other desks are outside the worker's selection. There is no
new service, queue table, source-policy rule or human-review authority. Legacy
English edits are protected; an existing title has no new human-review claim.

## Reproduction and checks

```sh
.venv/bin/python scripts/backfill_china_titles.py --dry-run --limit 20
.venv/bin/python -m unittest tests.test_china_title_translation tests.test_china_titles_public tests.test_reconcile tests.test_llm_usage_telemetry tests.test_archive_integration tests.test_archive_integration_browser tests.test_translation_tool_value_validation tests.test_migrations tests.test_preview_prototype -q
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python scripts/build_archive_js.py --check
.venv/bin/python scripts/validate_output.py
git diff --exit-code -- pla_watch.db output/
```

The new tests exercise the real Daily dispatch with a fake provider, both
screened-out and awaiting-screening states, English originals, human edits,
concurrent claims/writes, changed original/URL/eligibility, malformed responses,
account failure, bounded retries/resume, idempotence, reconciliation and
idempotent migration. A synthetic record in a disposable production DB copy is
rendered through the existing renderer for HTML, both indexes, citation and
desktop/mobile Chromium download/search checks, including no-JS and JS budget.
No real headline receives a fake translation.

Visible browser evidence: [desktop](../evidence/china-title-translation/desktop.png)
and [mobile](../evidence/china-title-translation/mobile.png). These depict only
the explicitly synthetic fixture. The production renderer was also exercised
with that disposable DB and an isolated `/tmp/ipr-china-title-review/final-site`
destination. Full-suite/CI results and any environmental failures are reported
on the focused PR. The integrated focused suite passed **179 tests**; validator
passes with zero errors / ten warnings and the JS bundle check passes. Initial
full local runs were stopped for source/base integration, after reproducing an
existing macOS `/var` versus `/private/var` temporary-path assertion in the
retirement receipt test. The complete local rerun uses `TMPDIR=/private/tmp`;
its outcome and the final Linux CI outcome must be read from the PR receipt.

Tracked database SHA-256 at start and preservation check:
`21012d0e3f04426145ccf9eddae2e2dd9c820e42283230011f62163dd52e48a6`.

## Remaining activation and historical completion

1. Review and merge the source PR only after its full offline CI passes. This
   engineering task does not authorize that merge or any live run.
2. Re-run the dry-run on current main and verify current account headroom before
   separately authorizing spend. At this snapshot, **151** titles are eligible.
   Estimated one-pass cost is **$1.550850**, including all prompt/tool characters,
   a conservative framing allowance and the full 512 output tokens per title.
   First batch of 20: **$0.205566**. Five attempts on every title would estimate
   **$7.754250**. These are estimates, not invoice caps; the existing access
   probe adds a small separate cost. Actual tokenization, SDK retries, failures
   and account limits can change spend. Rates come from the existing pinned
   price table; Sonnet 4.6's $3 input / $15 output per million tokens was
   verified against [official provider pricing](https://platform.claude.com/docs/en/about-claude/pricing).
3. Once separately authorized, run a bounded batch, then repeat the same command
   until `eligible_now` is zero. Successful titles are skipped; failures remain
   bounded and identifiable in the title retry columns:

   ```sh
   .venv/bin/python scripts/backfill_china_titles.py --db pla_watch.db --limit 20 --execute --confirm-spend
   ```

   Inspect a paused title before explicitly resetting only its title budget:

   ```sh
   .venv/bin/python scripts/backfill_china_titles.py --db pla_watch.db --resume-id RECORD_ID --dry-run
   .venv/bin/python scripts/backfill_china_titles.py --db pla_watch.db --resume-id RECORD_ID --execute --confirm-spend
   ```

4. For future Daily completion, separately activate
   `CHINA_TITLE_TRANSLATION_LIMIT=20` in the existing Daily pipeline environment.
   No workflow is changed here. Full analysis runs first and headline completion
   then selects eligible untranslated records independently of relevance. It
   honors `--dry-run`, `--no-analysis` and existing account-block handling;
   title-only failures cannot fail otherwise valid collection.
5. Through the existing authorized DB/render/publication flow, preserve the
   receipt columns, render with `site/render.py`, inspect generated changes,
   validate and publish only after separate authorization. No tracked output
   is regenerated in this PR. Until backfill and a separately approved render,
   the live site's missing titles remain missing.

Collision review: PR #766's private workbench stays untouched. Open #741, #712,
#695 and #694 touch other regions of `generate_preview.py`; #668/#679 touch
storage/retirement code; migration 0010 is retained from the integrated main.
The read-only DB residue contract expects exactly pending 0010 and 0011,
continuing to reject unknown migrations or a non-fail-closed verifier.
No competing active
public China title-completion PR was found in the open-PR inventory.

The first PR CI run also exposed an inherited retry-workflow assertion that two
retired records must still exist. The workflow and retry-history function were
unchanged from base, and both DB blobs were identical. Removed only that
obsolete per-record lookup/print loop: the actual current public-row comparison,
synthetic five-attempt/pause/resume contracts and byte-preservation checks
remain. The updated workflow no longer enumerates those retired identities.
