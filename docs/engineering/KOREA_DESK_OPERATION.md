# Korea desk operation

Verified October 18–19, 2026. This procedure uses existing systems
and grants no new source, model or release permission.

## Normal operation

- MND: the public legacy collector is a no-source tombstone. The private repo
  `ipr-source-evidence-private` is the sole writer and custodian of
  `archive/korea-policy-briefing`. Its `korea_mnd_private_first_collector.yml`
  runs at 17:47 UTC (six-day lookback, cap 40) with
  `KOREA_MND_PRIVATE_COLLECTION_ENABLED=true` (set October 19, 18:40 UTC). MND
  is excluded from the private fast-forward mirror. The first genuine scheduled
  run, [39329889889](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39329889889)
  (`schedule`, slot attributed to October 19, started 21:44 UTC, about four hours
  after the 17:47 slot), succeeded: robots read, 10 listed and retrieved, 10
  duplicates, no failures, 17 stored, ledger and independent readback preserved
  at `0fe16d7708`. GitHub cron delay on these repositories is routinely hours.
- DAPA: private `korea_dapa_private_first_collector.yml`, 22:17 UTC, one logical
  UTC day, no lookback, at most five complete article/HWPX pairs. Private
  `DAPA_DAILY_ORIGINAL_ACCESS_APPROVED` and both repositories'
  `DAPA_METADATA_BRIDGE_ENABLED` were independently read as `true`.
  Both required private secret names exist; values were not read or changed.
- Retain the existing official-link and standing-original-text publishers.
  Their completion hooks must match the collector's actual workflow name.
  Their existing daily fallback schedules remain; do not add another writer.

## One-writer MND private cutover — completed October 19 (record)

All steps below were executed on October 19, 2026: public PRs #825/#826 and
private PR #18 merged (private merge 17:28 UTC), the public read token was
fixed after a 403 on the first publisher dispatch (18:24 UTC) and both
publishers then passed, and the private gate variable was set at 18:40 UTC.
Retain this order only as the record or for a future re-cutover.

Owner approved private GitHub custody as the primary archive and accepted that
this is not an independent off-provider disaster-recovery backup. Do not claim
otherwise. The historical public branch remains in Git history; no force-push,
erasure or secret rotation is implied.

1. Before merging either PR, confirm that public and private MND branches
   have the same final legacy tip and all legacy/public mirror jobs are idle.
   Record that exact commit and verify the existing immutable source/DB/ledger
   equality. A private mirror is not itself proof of independent backup.
2. Provision a **fine-grained token with Contents: Read on the existing private
   evidence repository only** into the PUBLIC repo Actions secret
   `IPR_KOREA_PRIVATE_READ_TOKEN`. Do not print its value.
3. Merge the PUBLIC companion first. It retires the legacy collector and
   changes both existing publishers to clone the private archive into
   ephemeral runner scratch. Check the scheduled publishers are able to
   read the exact preserved private source; no raw evidence reaches Pages.
4. Merge private companion PR #18 only after the public writer is retired
   and source history is still identical. This removes MND alone from the
   old fast-forward mirror and stages one private daily writer. It must not
   disturb DAPA, Indonesia or the seven other mirror families.
5. Finally, enable `KOREA_MND_PRIVATE_COLLECTION_ENABLED=true` in PRIVATE
   repo Actions variables. Check the next scheduled genuine private MND run
   or deliberately authorized single-day manual run, its Git attempt
   commit/readback and SHA-256 original preservation.
6. Run the existing official-link and licensed-Korean-text publishers (or
   observe their existing daily fallback); verify production SQLite,
   generated Korea HTML, Pages and actual HTTPS. A genuine zero-new day
   proves collection operation, not a new source's admission.
7. If a token, provenance, source, completeness or concurrency check fails,
   hold publication and diagnose the precise issue. Do not silently
   reenable the old public original-bearing writer or the mirror.

The private writer has no authority to widen source access, reproduce
restricted HWPX/media, auto-publish DAPA text or change reviewed English.
Manual source recovery does not rewrite historical scheduled failures.

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
  preserved and admitted (text SHA-256
  `c92b0faebb5eac473a96d9b4037bd91c8b5cd97257c970eff694160d24075d7e`).
- Genuine private MND run
  [39304457445](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39304457445)
  (`workflow_dispatch`, target date October 19, collector `2a710132f4`): robots
  read, six-day listing proven (10 listed), 9 duplicates, 1 new record
  `korea-policy:156785691` (HWPX retrieved; text SHA-256
  `66931c2d0f4d9d187cbe17d68a124882a3e6ed4a5c059754639dbcd0e1697cf8`), no
  failures, 17 stored. Private archive tip `02090fc258bedc4bcadc0c788e078fa8b56afc05`
  with independent clone readback (fsck, SQLite integrity, capture SHA-256 names).
  It is a manual run and does not attest the schedule.
- Before that run, production had 15 MND + 1 DAPA link records, 3 licensed
  originals and 3 reviewed English/analysis pairs, identical on `gh-pages` and
  HTTPS (`korea.html` SHA-256
  `b9f3e7380838fa204f07f5d197a5480ae4dac741d5de9b561968a909a9e6ba14`). Held
  by decision, not defect: `korea-policy:156785161` (chronology exception,
  link-only on the historical bibliography, absent from the production table).
- `156785691` reaches production only through the established daily fallbacks
  (link publisher 20:37 UTC, standing-text publisher 21:17 UTC, English owner
  handoff after the text release). A scratch dry run against a copy of production
  predicted one link admitted, one text eligible (hash identical to the private
  original) and zero held. **Not yet observed:** at 23:43 UTC on October 19 neither
  publisher had a scheduled run for that evening (recent nights ran roughly two
  hours late: October 18 at 22:35 and 23:13 UTC); `main` (16 production rows),
  `gh-pages` (`6715da1514`) and HTTPS `korea.html` lack the record, and
  `korea-originals/156785691.html` returns 404. Classify as pending, or a possibly
  dropped schedule if still absent after the next slot. Do not dispatch manually
  without owner authorization; admission and release stay with the publishers.
- Known stale check (not changed here): `korea_shadow_slot_watchdog.yml` reads
  the frozen public `shadow/korea-policy-briefing` branch (tip `cac1f02fb7`, last
  ledger October 16), so it reports "no successful scheduled-run ledger" and has
  failed daily since cutover (e.g. `39256411507`). That is a false alarm about
  public custody, not an MND collection failure; private receipts above are
  authoritative. Retargeting it to the private archive is a separate fix.
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
- The MND retry, publisher-hook repair and one-writer cutover are merged.
  Preserve historical exposure and failed receipts. Tests authorize no further
  merge, production DB write, schedule or permission change, or editorial
  publication; English release still requires the human review and owner
  dispatch described in `KOREA_ENGLISH_TRANSLATION_ANALYSIS_RELEASE_2026-10-15.md`.
