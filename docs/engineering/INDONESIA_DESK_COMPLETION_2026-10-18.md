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
   every `schedule-slot` attempt. It returns a closure accepting only its own
   receipt, so a caller-supplied or copied receipt cannot admit anything.
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
  `659ce42`: 34 eligible, 1 held, 222/209 captures re-hashed, 14/13 ledger
  attempts reconciled, 0 unhealthy. GitHub records 11 scheduled healthy days
  (7–17 Oct) for the ledger's `schedule-slot` run IDs.
* **Rehearsal on a scratch copy of production `pla_watch.db`.** 34 rows
  admitted, 1 held. Replay was idempotent (0 new, 34 unchanged, identical
  bytes). An independent read-only query found integrity and foreign-key
  checks clean, 34 distinct URLs dated 2026-09-30…2026-10-16, no Yonif row, no
  legacy URL collision, and unchanged row counts in all 18 other tables plus
  the migration ledger. Production `pla_watch.db` was not modified.
* **Render.** From the rehearsal DB, only `indonesia.html` differs from a
  fresh baseline render. 34 rendered items match the SQLite identities and
  URLs exactly.
* **Signed path.** A real private envelope (4,817 bytes gzip, 6,424 base64
  characters) built from `659ce42` admitted with 34 unchanged (no duplicates).
  A forged MAC returned HOLD.

## Failure and recovery coverage

`tests/test_indonesia_kemhan_release_validator.py` covers:

* **History authenticity:** ledger schedule claims GitHub contradicts;
  fewer than 7 authenticated days; tampered or missing captures; unexplained
  commits; commits without ledgers; frozen-record date/URL revision; history
  not descending from the pin.
* **Truthful receipts:** a private attempt that died before its ledger is
  counted as a visible failure; unhealthy scheduled attempts do not count as
  days.
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
  the envelope. The public workflow admits new links, commits `pla_watch.db` +
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
* **Release authority.** The owner's Oct 15 standing metadata-only
  authorization. Merging this PR runs the push-triggered admission once.

## Owner actions still required

1. Merge the public PR (it triggers admission of the 34 frozen-era links).
2. To admit post-cutover records automatically, configure:
   * one random ≥32-byte `KEMHAN_BRIDGE_KEY` secret in **both** repositories;
   * `IPR_PUBLIC_BRIDGE_TOKEN` in the private repository (a token limited to
     Actions dispatch on the public repository; the Korea DAPA bridge already
     names it, but no dispatch has ever run);
   * variable `KEMHAN_METADATA_BRIDGE_ENABLED=true` in both repositories.

   Then merge the private PR.

## Known limits

* The automated index shows dated official links without headlines, because
  the owner policy excludes titles. The 15 curated Berita links with
  descriptions remain the reader-oriented directory.
* No machine translation or model analysis of Kemhan bodies is authorized.
  English research enters the Sunday intake as typed `ID-KEMHAN-Wnn-nn`
  publisher-page items. The loader still refuses unverifiable shadow commit
  and digest claims for new Kemhan items, so exact-version provenance in that
  pack is limited to the pinned W42 record.
* The reader and candidate builder cap one snapshot at 300 records. At
  roughly two new items a day, that limit arrives around February 2027.
