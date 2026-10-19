# Korea desk operation

Verified October 18, 2026 (Eastern time). This procedure uses existing systems
and grants no new source, model or release permission.

## Normal operation

- MND: `indonesia_korea_shadow.yml`, named **South Korea Shadow Collection
  (legacy custody)**, 17:47 UTC, six-day lookback, cap 40. Original-bearing
  writes still target public `shadow/korea-policy-briefing`; the private mirror
  is `ipr-source-evidence-private:archive/korea-policy-briefing`. A mirror is
  not private-first collection. Issue #520 and
  `config/korea_shadow_writer_policy.json` retain a separate cutover hold.
- DAPA: private `korea_dapa_private_first_collector.yml`, 22:17 UTC, one logical
  UTC day, no lookback, at most five complete article/HWPX pairs. Private
  `DAPA_DAILY_ORIGINAL_ACCESS_APPROVED` and both repositories'
  `DAPA_METADATA_BRIDGE_ENABLED` were independently read as `true`.
  Both required private secret names exist; values were not read or changed.
- Retain the existing official-link and standing-original-text publishers.
  Their completion hooks must match the collector's actual workflow name.
  Their existing daily fallback schedules remain; do not add another writer.

## Quiet day, failure and recovery

1. Check actual Actions repository, event, attempt and selected desk. For DAPA,
   require a real scheduled first attempt and the private attempt receipt plus
   collector ledger at an immutable commit. A green contract-only job proves
   no collection. The existing MND slot watchdog reports missing mature slots;
   check private Actions/receipts separately for DAPA missing slots/failures.
   The Operations Center declares the private DAPA schedule without attesting
   its execution. Never interpret absent receipts as a quiet publisher day.
2. `ok_no_publications` requires robots and a complete filtered listing.
   `ok_all_duplicates` can also be healthy. Neither should manufacture a signed
   packet or dispatch a publication. Failed/partial retrieval remains failed.
3. The MND repair permits one additional transient request TOTAL across
   listing/article/HWPX per collection, after the existing crawl delay. Its
   separate single robots-timeout retry remains. Denials/challenges, redirects,
   TLS failures and malformed responses gain no retries. Incomplete batches
   still preserve the prior database and must not publish.
4. For MND recovery, compare preserved identities before fetching originals
   again. Use the existing bounded explicit-date manual recovery only within
   approved source-access policy. Do not rerun a historical event and guess its
   date. Manual recovery never repairs a historical scheduled result.
5. After successful private DAPA capture but failed publication, use private
   `retry_verified_metadata` with the exact saved `source_run_attempt` and no
   original-access approval. It rereads existing evidence, without fetching a
   government original. `scripts/korea_dapa_private_recovery_plan.py` separates
   this from failed/missing capture. Failed source attempts cannot publish.
6. After a main commit but failed Pages/readback, inspect the existing release
   guards and retry the established publisher. Independently compare current
   SQLite identities, generated Korea HTML, Pages bytes and HTTPS. A successful
   main commit alone proves no deployment. Preserve concurrent main changes.

## Editorial action

Production metadata is URL/date/issuer evidence, not reviewed research. Existing
MND staging yields version-pinned candidates without source body/title export.
The standing original-text publisher checks identity, HWPX parity, text licence
and exceptions before releasing eligible future MND text. The private English
handoff selects published originals without delivered/reviewed English; human
review controls release. Preserve the three existing reviewed pairs.

DAPA recurring access and link permission do not authorize original text,
translation, analysis, media or paid models. Its private evidence must receive
source-specific rights and Korean-language review before those treatments.
Revisions, missing evidence and disputes require actual review. MND
`korea-policy:156785161` retains its chronology hold.

## Verified evidence and remaining release boundary

- Failed MND scheduled `39159889610` stays failed. Its `156785190` original is
  already preserved and admitted with text SHA-256
  `c92b0faebb5eac473a96d9b4037bd91c8b5cd97257c970eff694160d24075d7e`.
  Source and private mirror share `cac1f02fb7360385ddcb1b44a5877dfee342da4f`:
  16 originals, 72 captures, 10 successful ledgers, 84 identical evidence files.
  All 16 HWPX/text fidelity checks passed; private repo status was independently
  checked. No off-provider restore is claimed.
- A private local manual October 18 MND check returned `ok_no_publications`:
  robots and one-day listing succeeded, zero candidates, unchanged DB. It used
  the candidate working tree based on `f3ff927b32`, not a scheduled execution
  or immutable release of this repair. It is not production acceptance.
- Genuine private DAPA scheduled run
  [39179758230, attempt 1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39179758230)
  started October 18 at 8:12 PM EDT (October 19 00:12 UTC), correctly attributed
  the delayed execution to October 18, read robots and a complete zero-result
  listing, preserved `ok_no_publications`, independently read back custody,
  and skipped signing/dispatch. Workflow SHA:
  `cf0a556ea2f8f81e8e07fafe467172a9de485f64`; collector SHA:
  `f3ff927b32ebf857e930270e6641fc7abd8a7047`; private receipt commit:
  `7a03ac11555b0d301c64bf5953c255825e988eb5`.
- Reuse DAPA `156785254` acceptance: private `39147821179`, public
  `39147918490`, production `520d661cae4553f273a53a79215976e12807b799`.
  No reimport was performed. SQLite has 15 MND and one DAPA metadata record,
  three licensed originals and three reviewed English/analysis pairs. Existing
  HTTPS returned 200 and matched Pages SHA-256
  `d06dcf7c10be11b579f6b3a2c12e73659e1a6ca0bd28ba32d340121be60ac405`.
- Owner release must cover the MND retry and publisher-hook repair. Private-first
  MND collection needs the separately held one-writer cutover authorization;
  preserve historical exposure and failed receipts. Tests authorize no merge,
  deployment, production DB write, private activation or editorial publication.
