# Indonesia Desk — private evidence to governed production (18 October 2026)

This connects the existing private Kemhan collection to the existing regional
official-link admission, desk renderer and Pages path. It adds no collector,
database, permission framework or publication system.

## Source contract

| Family | Automated | Public fields | Excluded |
|---|---|---|---|
| Kemhan **Berita** (`id_kemhan_news`) | Yes: private 17:17 UTC collector, `/category/berita` listing + dated article HTML, 6-day lookback, 40 cap | canonical official URL, publisher date, issuer/publisher, Git commit, metadata digest | headline, body, photograph, translation, model text, analysis (owner policy, `config/afp_kemhan_owner_link_activation.json`) |
| Kemhan **Siaran Pers** (`id_kemhan_press`) | No: parser disabled, no collector, no preserved state | two curated outbound links (Oct 12 decision) | everything else |

The Yonif TP 880 record (Kalimantan Utara/Barat publisher geography conflict)
is always held. Its original and discrepancy are preserved unaltered.

## What was missing, and what this change adds

1. **Shared reader cap broke every post-pin snapshot.** A genuine 2026-10-15
   Berita path is 194 characters. `scripts/private_country_desk_reader.py`
   capped identities at 180, so held-candidate staging HOLDs for any commit
   after the frozen pin. Kemhan identities are now bounded by the URL cap they
   are bound to; other families keep 180.
2. **No trusted validator.** `core/indonesia_kemhan_release_validator.py`
   recomputes every gate `admit()` requires from primary evidence: owner pin
   ancestry, capture blobs re-hashed against their content addresses, every
   stored text bound to its digest and to a preserved capture, one-to-one
   ledger ↔ history-commit reconciliation, and GitHub's own run records for
   every `schedule-slot` attempt, healthy or failed. It returns a closure
   accepting only its own receipt, so a caller-supplied or copied receipt
   cannot admit anything.
3. **No production caller.** `scripts/admit_indonesia_kemhan_official_links.py`
   admits on a scratch copy, checks integrity, verifies unrelated rows by
   digest, reads admitted rows back read-only, refuses if the production file
   changed meanwhile, then atomically replaces it.
   `.github/workflows/indonesia_verified_official_link_production.yml` follows
   the Korea pattern: page-only commit, exact main/source/Pages pins, Pages
   reconciliation on retry, and a committed-vs-deployed byte check.
4. **No private → public handoff.** Post-cutover originals exist only in the
   private archive. The private collector (companion private PR) runs the same
   public validator on the read-back private branch, then dispatches a gzip,
   HMAC-signed, metadata-only envelope. The public side re-verifies the MAC,
   rebuilds the frozen baseline from the public frozen branch, checks that the
   private history inherited the exact final public tip, and re-authenticates
   scheduled history from public run records. This path is held until the
   owner sets the credential (below).
5. **Existing page check rejected the admitted state.** Once rows exist the
   desk template already swaps the shadow heading for the admitted one, but
   `scripts/indonesia_operational_health.py` (used by the manual health run
   and both curated-link release workflows) demanded the shadow heading. It
   now accepts the admitted heading only alongside one well-formed admitted
   index: `kemhan.go.id` hrefs equal to their identities, dates matching the
   URL path, no duplicates and no held identity. The production workflow runs
   the same check before committing. The curated 15 + 2 directory and its
   prose-count checks are unchanged.

## Review basis and what may be admitted

The Oct 15 owner policy records that human review occurred for the pinned
frozen cohort (`0595c66`, manifest `2fbb897f…`) and that **no
machine-verifiable record-specific human review receipts exist**. On
18 October the owner added a standing authorization (DECISION_LOG,
#812 comment 6254436315): verified Kemhan Berita link metadata is admitted
automatically for existing and future records, with no per-record review and
no elapsed-time wait. It is pinned in the same policy file as
`standing_link_metadata_authorizations` (family `id_kemhan_news` only;
`load_owner_policy` refuses any other shape). The receipt says exactly that:

* schema `ipr-crossdesk-independent-release-proof/2`;
  `owner_review_declaration_bound_to_frozen_manifest: true`,
  `record_specific_review_receipts_verified: false`,
  `standing_link_metadata_authorization_verified: true`;
* `approved_source_identities` is every eligible record (frozen records still
  must be unchanged against the pin); the ones outside the frozen cohort are
  counted and digested in `released_without_record_specific_review_*`, so the
  receipt never implies they were reviewed.

| Records | Status |
|---|---|
| 30 frozen-cohort Berita records | admitted (Oct 15 review + standing authorization) |
| verified records first collected after the pin (5 at `69b1f9b`) | admitted under the standing authorization, recorded as not individually reviewed |
| Yonif TP 880 | held (semantic geography conflict) |
| a released record later revised in place or missing | HOLD `previously_released_source_missing_or_changed`; admission stops, nothing is overwritten |
| frozen record changed against the pin; URL/date conflict; unverifiable capture, ledger or scheduled claim | HOLD (existing validator reasons) |

Without the standing entry the code falls back to the Oct 15 behaviour: only
the frozen cohort is admissible and `admit()` refuses anything else
(`unreviewed_source_selected_for_release`), whatever validator is passed.

The previous seven-day rule is removed (DECISION_LOG 2026-10-18). The
validator still authenticates every visible `schedule-slot` claim against
GitHub, so a failed run cannot be relabelled and a manual dispatch cannot be
passed off as scheduled, and it requires at least one authenticated healthy
scheduled run. Elapsed days are reported, not required.

## Real-record evidence (18 October 2026)

* **Independent expected set.** An independent regex over the preserved raw
  `/category/berita` listing bytes of all 14 attempts (6–17 Oct) derived 35
  identities, matching the 35 stored, with zero omissions and zero date
  mismatches. This is an independent parse of the collector's retrieval: the
  session's network policy blocks `www.kemhan.go.id`, so no live re-retrieval
  was possible.
* **Frozen pin.** `0595c66` rebuilds to the owner-pinned manifest
  `2fbb897f…` (31 candidates, 1 hold).
* **Validator on real history.** Public frozen tip `4295052` and private tip
  `659ce42`: 34 eligible, 1 semantic hold, 222/209 captures re-hashed, 14/13
  ledger attempts reconciled, 0 unhealthy. GitHub records 11 scheduled healthy
  days (7–17 Oct) for the ledger's `schedule-slot` run IDs (reported only).
  30 of the 34 are in the reviewed cohort; 4 are held as unreviewed.
* **Standing-authorization rehearsal** (scratch copy of production
  `pla_watch.db`, private tip `69b1f9b`): 35 rows admitted, 0 held pending
  approval, 1 semantic hold (Yonif); 5 of the 35 counted as released without
  record-specific review. Replay: 0 new, 35 unchanged, identical bytes.
  Production `pla_watch.db` unchanged. Post-merge sequence: the frozen
  branch `4295052` admits 34 (4 without record-specific review), then the
  real signed private envelope from `69b1f9b` (5,314 bytes gzip, scratch
  key, no title or body fields) adds 1 new with 34 unchanged; a forged MAC
  HOLDs with the database byte-identical.
* **Earlier frozen-only rehearsal** (receipt v2, before the standing
  authorization). 30 rows admitted, 4 held pending approval, 1 semantic hold. Replay was idempotent (0 new, 30 unchanged,
  identical bytes). The admitted rows are dated 2026-09-30…2026-10-14 with no
  Yonif row. The earlier 34-row rehearsal found integrity and foreign-key
  checks clean and unchanged row counts in all 18 other tables plus the
  migration ledger; the 30 rows are a subset of it. Production `pla_watch.db`
  was not modified.
* **Render.** From the rehearsal DB, only `indonesia.html` differs from a
  fresh baseline render, and rendered items match the SQLite identities and
  URLs exactly (the production workflow repeats this check).
* **Signed path.** A real private envelope (5,128 bytes gzip) built from
  `659ce42` with a scratch key admitted with 30 unchanged and the same 4 held
  (no duplicates). A forged MAC returned HOLD.

## Failure and recovery coverage

`tests/test_indonesia_kemhan_release_validator.py` covers:

* **History authenticity:** ledger schedule claims GitHub contradicts; a
  failed or manual run relabelled as scheduled; no authenticated healthy
  scheduled run; one healthy day admits (days measured, not required);
  tampered or missing captures; unexplained
  commits; commits without ledgers; frozen-record date/URL revision; history
  not descending from the pin.
* **Truthful receipts:** a private attempt that died before its ledger is
  counted as a visible failure; unhealthy scheduled attempts are counted as
  failures, not days; the receipt states the actual review basis; a
  post-pin record is admitted on both the source and signed paths under the
  standing authorization and held without it, and the write boundary refuses
  it (or a receipt merely claiming standing) under a permissive validator;
  Yonif stays refused under standing; a released post-pin record later
  revised holds; a malformed standing entry is refused.
* **Database safety:** interruption before commit (rollback, no residue);
  concurrent production writer (HOLD, the other write survives);
  forged receipt or missing validator refused; replay idempotent; unrelated
  Philippines row preserved.
* **Signed envelope:** wrong MAC, wrong key, tampered body, wrong public tip,
  validator code not on public main, and missing key all HOLD. The envelope
  carries no title or body.

Collector-level upstream failures (markup loss, missing or repeated pages,
partial batches, robots timeout, over-cap windows) are already covered in
`tests/test_indonesia_korea_shadow.py`.

## Operating procedure

* **Normal.** 17:17 UTC: the private collector preserves the attempt, rebuilds
  the queue and held candidates, and (once the bridge is active) dispatches
  the envelope. The public workflow re-verifies it, admits only reviewed
  identities, counts the rest as held, commits `pla_watch.db` +
  `output/indonesia.html` only, publishes `indonesia.html` to Pages, and
  checks main and Pages bytes match. Its 19:43 UTC run retries and reconciles.
  A day with zero new items is healthy and commits nothing.
* **Diagnosis.** Every HOLD prints a fixed reason code and never source text.
  * `production_database_changed_concurrently` or "main moved": another desk
    wrote first. The next run retries idempotently.
  * `private_reader_refused_source_snapshot` or a staging failure: inspect the
    private run's ledger.
  * `signed_envelope_mac_invalid`: key mismatch between the repositories.
* **Revised government original.** The collector refuses a changed stored
  identity with "human disposition required". The attempt and captures are
  preserved, but new items in that six-day window are not inserted until an
  operator disposes of the revision in the private archive.
* **Safe retry.** Re-dispatch the public workflow (no inputs) or the private
  collector with `collect_after_cutover`. Both are idempotent and never
  create duplicate public rows.
* **Release authority.** The owner's Oct 15 metadata-only authorization for
  the reviewed frozen cohort, extended on Oct 18 to verified existing and
  future Berita link metadata. Merging this PR runs the push-triggered
  admission once.

## Owner actions still required

1. Merge the public PR. Its push-triggered run admits the 34 verified links
   on the frozen public branch (`4295052`; rehearsed: 34 admitted, 4 without
   record-specific review, Yonif held). Private post-cutover records follow
   via the bridge.
2. To carry post-cutover private records to the public side, configure:
   * one random ≥32-byte `KEMHAN_BRIDGE_KEY` secret in **both** repositories;
   * `IPR_PUBLIC_BRIDGE_TOKEN` in the private repository (a token limited to
     Actions dispatch on the public repository; the Korea DAPA bridge already
     names it, but no dispatch has ever run);
   * variable `KEMHAN_METADATA_BRIDGE_ENABLED=true` in both repositories.

   Then merge the private PR.

## Steady state after the first private release (25 October 2026)

A rehearsal of the real private tip `d8859b5` (49 eligible, production 34)
found that the lane could publish once and then stop. `admit()` requires every
stored Kemhan row to be in the packet it is admitting, and the workflow always
admits the frozen public packet (34 rows) first. After the envelope released
the 15 newer rows, the 19:43 UTC retry (frozen only) and every later envelope
dispatch would HOLD `previously_released_source_missing_or_changed`.

`admit_validated(..., frozen_first=True)` now lets the **frozen baseline
packet only** step aside when every row it approves is already stored exactly
as approved and later released rows exist. It never inserts, so original
frozen provenance is kept. A missing or altered frozen row, or any later packet
(envelope) that omits or changes a released row, still HOLDs, and the shared
`admit()` is unchanged (Philippines and Vietnam unaffected). Rows beyond the
frozen cohort are re-verified at each envelope, not by the frozen-only retry.

Real-data rehearsal on a copy of production `pla_watch.db` (private
`d8859b5`, scratch key): frozen + envelope admits 15 new / 34 unchanged
(49 rows, 34 keep the frozen commit, 15 the private commit); frozen-only
retry and a repeated envelope leave the file byte-identical; a forged MAC and a
wrong key HOLD with the file untouched; Yonif TP 880 absent; other desks'
rows unchanged; the rendered page equals the 49 SQLite rows.

Known limit: the validator rejects envelopes over 48 KiB (about 150 bytes per
record, so roughly 320 records) and fails closed, ahead of the shared reader's
300-record cap (about February 2027).

**Activation order.** (1) Merge the public PR carrying this change (its
push-triggered run replays the frozen history; no data change). (2) Set the
same random `KEMHAN_BRIDGE_KEY` secret in both repositories. (3) Set
`KEMHAN_METADATA_BRIDGE_ENABLED=true` in both. (4) Merge private PR #17.
Activating before step 1 reproduces the single-publication failure above.

## Scope: this is the official-link lane, not the whole desk

This change completes the automated official-link publication lane only. The
desk is not complete end to end. Status of the other agreed requirements:

| Requirement | Status |
|---|---|
| Official-link publication | done once the PR merges |
| New-record admission | done in code (standing authorization); private records need the bridge credentials |
| Translation of Kemhan originals | outstanding: none authorised; no machine translation exists |
| Analysis of Kemhan originals | outstanding: no model or analyst analysis of bodies is authorised |
| Sunday editorial intake | partial: typed `ID-KEMHAN-Wnn-nn` publisher-page items load, but the loader refuses unverifiable shadow commit/digest claims, so exact-version provenance covers only the pinned W42 record |
| Reader-facing page | partial: the automated index shows dated links without headlines (titles excluded by policy); the 15 curated Berita links with descriptions remain the reader-oriented directory |

## Known limits

* The first genuine `schedule` event run of
  `indonesia_private_first_collector.yml` is run 39158713099, attempt 1
  (17:17 UTC cron, started 19:25 UTC on private main `cf0a556`). Collection,
  private commit `69b1f9b`, readback, SQLite integrity and capture hashes
  passed (12 retrieved, 1 new, 36 stored). The run then failed at the
  held-candidate rebuild, which runs public `main` `358a69c`: HOLD
  `pinned_source_validation_failed`, because main still carries the
  180-character reader cap this PR fixes. With this branch, `69b1f9b`
  rebuilds to 36 candidates, 1 semantic hold, all held (manifest
  `f779099b…`), and a scratch admission gives 30 unchanged, 5 held
  unreviewed, 1 semantic hold. Under the Oct 18 standing authorization the
  same tip admits 35 with Yonif held.
* The reader and candidate builder cap one snapshot at 300 records. At
  roughly two new items a day, that limit arrives around February 2027.
