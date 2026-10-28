# Korea desk operation

## Current verification — 28 October 2026

**ENGINEERING READY — RELEASE OR FOLLOW-ON VERIFICATION PENDING.** The repairs
below are a review candidate, not a production release. The October 18–19
checkpoint later in this document is historical. In particular, the private
cutover, Daily activation and watchdog have progressed since that checkpoint.
This procedure grants no source, spending, merge or release permission.

Verified against public main `cc25e3c88da3bc7afb9bca7a03f96e1dbfae7224`,
private main `c1cbff0c0aea493957d156d973c872174d5fd3fd`, their current Actions,
immutable private archive tips, tracked production SQLite, Pages and HTTPS.
Shared `PROJECT_STATE.md` was left untouched while other desk PRs are open.

| Stage | Observed state |
| --- | --- |
| MND collection/custody | Genuine scheduled [40587103070](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/40587103070), nominal October 27: robots read, complete October 21–27 listing, 7 selected/retrieved/extracted, 1 inserted, 6 duplicates, no failures, 25 stored. Private readback passed. Archive `cfe7ed77084290cf73de85e5325d1a5cd8a3d711`; independently verified all 164 capture hashes and the source/HWPX inventory. |
| DAPA collection/custody | Genuine scheduled [40614736442 attempt 1](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/40614736442/attempts/1), nominal October 27, executed October 28 UTC: robots read, complete one-day listing, 1 selected/retrieved/extracted/inserted, no failures. Original `korea-dapa-policy:156786687` is preserved at `f268cc5720469bb0788cea4d359aea2bac4c9d1d`; all 13 capture hashes verified. Collection and independent custody readback succeeded; the subsequent metadata export failed. |
| Public links | Production contains 20 MND + 1 DAPA records. Four additional eligible MND identities remain private: `156786154`, `156786296`, `156786306`, `156786587`. The metadata publisher admits them in runner scratch, then fails its obsolete render-count assertion before committing. The new DAPA identity has not reached public admission. |
| Licensed MND text | Eight original texts are public. The latest scheduled genuine new-text release, [39696987609](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39696987609), released three originals and verified actual HTTPS. Current scheduled [40609331696](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40609331696) stopped with an undifferentiated `HOLD`; its exact cause is not recoverable from that receipt. Preserved-source replay against disposable index/text copies and the current official policy qualified the four pending originals, without production writes. This does not prove the scheduled runner's next attempt. |
| Shared Daily | `KOREA_DAILY_AUTOMATION_ENABLED=true` (since October 21). The registered Korea profile and source-version bridge are active. Five corpus admissions exist: three QA-held, two screened out; zero completed machine analyses. Processing is configured and prior paid attempts are recorded, but a successful machine-analysis-to-live continuation is unverified. |
| Reviewed English | Three reviewed translation/analysis pairs remain public and source-pinned. They remain excluded from machine admission; the existing supersession rule is unchanged. |
| Monitoring | Scheduled private-ledger watchdog [40690021177](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40690021177) passed for the mature October 27 MND slot. It truthfully retains earlier missing slots, including October 22. That failure and DAPA's corresponding failure were Python 3.9 setup on Ubuntu 26.04, before collection; current private workflows already pin Ubuntu 24.04. They were infrastructure failures, not publisher denials or quiet days. DAPA Actions exposes the present handoff failure; recipient delivery of operational notifications was not tested. |

The enabled private variables were independently read as true:
`KOREA_MND_PRIVATE_COLLECTION_ENABLED`, `DAPA_DAILY_ORIGINAL_ACCESS_APPROVED`
and `DAPA_METADATA_BRIDGE_ENABLED`; public `DAPA_METADATA_BRIDGE_ENABLED` is
also true. No variable or secret was changed, and no secret value was read.
Recent publisher logs prove authenticated private MND read access works.

### Confirmed defects and review candidate

1. DAPA's exporter required `target_date_source=explicit`, rejecting a genuine
   `schedule-slot` after successful collection. It now also accepts a first
   scheduled attempt whose preserved timezone-aware start independently
   resolves to the declared date at the existing 22:17 UTC slot. Unknown/manual
   inferred dates, ambiguous reruns, missing timezone and mismatched dates
   remain held. Exact attempt commit, receipt, complete batch, originals,
   issuer, HWPX replay, signature and public metadata-only checks stay intact.
2. Both MND publisher render gates expected a bare link for every nonhistorical
   DB identity. The renderer already represents finished Korea corpus records
   at `record/<id>.html` and removes their duplicate bare links. The checks now
   use the existing corpus publication gate, require each record route, and
   still reject missing/duplicate link entries. The two currently screened-out
   corpus records are finished records under that existing gate; this repair
   changes no relevance, analysis or rendering policy.
3. The original-text CLI now reports fixed gate reason codes on a global hold,
   allowing policy/access/source faults to be distinguished. Arbitrary parser,
   filesystem or source-bearing exception text is never logged. No retry or
   rights check was relaxed to explain the historical generic failure.

The private workflow reads the exporter from public main, so no private
companion change is necessary. No new scheduler, model engine or renderer.
No production DB/output, public source index, reviewed English or retry state
was changed by this phase.

### Acceptance evidence and remaining action

- Focused offline checks: 36 collector/export/publisher contracts and 135
  watchdog/shared-Daily/corpus/QA/render/retry contracts passed. The tests
  execute both actual publisher post-render Python blocks and reject missing
  and duplicate rail entries, not just YAML string shape. Mandatory final-head
  full CI is recorded in the review PR; focused success alone is insufficient.
- Replayed the exact new private DAPA evidence through the repaired exporter,
  signed with a disposable test key and admitted to a disposable SQLite schema:
  1 new record, then 0 new / 1 unchanged on retry. No source title, text, media,
  translation or analysis was exported. This proves engineering recovery,
  not a production signature, public dispatch or deployment.
- Independently verified registered text SHA → renderer → main output → Pages
  → actual HTTPS: 8 originals + desk (9 paths), and 3 reviewed English/analysis
  pairs + desk (7 paths). Existing scheduled production readback
  [40681116462](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40681116462)
  also passed. The live [Korea desk](https://indopacificrecord.org/korea.html)
  shows the existing 21 metadata records, 8 originals and 3 reviewed pairs.
- Immutable production QA holds remain: `156785691`, attempt 3,
  `qa_agreement_unsupported,qa_number_added,qa_number_missing`; `156785888`,
  attempt 3, `qa_agreement_unsupported`; `156786043`, attempt 1,
  `qa_glossary_term_missing`. All use `kr-qa-v2` and the v3 translation prompt.
  `156785986` and `156785987` were screened out on their first attempts.
  None of those outcomes was reset. The chronology hold `156785161` persists.
- Public Daily [40565258649](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40565258649)
  failed its full suite on two Japan navigation assumptions before processing;
  this phase does not alter Japan PR #892 or presentation PR #895. Current
  base failures are distinguished from the Korea repair's CI in the PR.

Next: review the final-head PR and authorize its merge/release separately.
After release, the existing private `retry_verified_metadata` operation can
recover DAPA attempt `40614736442-1` without fetching originals again; it still
requires the applicable dispatch authorization. Observe existing MND publisher
schedules and the shared Daily, then verify newly admitted identities on actual
HTTPS. New paid model attempts, production dispatches and deployment were not
authorized or performed here. Existing per-record QA holds and DAPA text/model
restrictions remain individual dependencies. A new licensed-original replay
or a configured trigger is not verified unattended machine-analysis publication.

## October 18–19 checkpoint (historical)

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
- `156785691` admission and release. The nominal 20:37 and 21:17 UTC scheduled
  publishers had not run by 23:43 UTC on October 19 (recent nights ran about two
  hours late), so it was absent from `main`, `gh-pages` and HTTPS. With the
  owner's explicit one-time authorization (October 19, 23:51 UTC) the existing
  workflows were dispatched manually on `main`, link publisher first. This
  proves the publication pathway, not unattended operation. The link fallback
  subsequently ran successfully as a genuine `schedule` event at 23:55 UTC,
  [39344495959](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344495959):
  0 new, 16 unchanged, `156785161` still held. The scheduled text fallback and
  DAPA evening slot remain unobserved at this checkpoint.
  - Links, [39344115247](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344115247):
    pinned private source `0fe16d7708471a6e019a7e5618fb8c9e9768dd11`; admitted 1,
    unchanged 15, `explicit_exception_held` 1 (`156785161`); validator passed
    with the usual 10 warnings. Main commit `137c8b93c2`, `gh-pages` `3a2decb365`.
    Production table: 17 rows (16 MND, 1 DAPA), `156785691` is
    `official_link_only`, admitted 23:52:16 UTC.
  - Text, [39344401457](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344401457):
    1 new original, 0 held, 14 historical excluded. Main `7347a530e3`,
    `gh-pages` `edc0e2ce7d`. The released text SHA-256 equals the private original
    (`66931c2d…97cf8`). Workflow HTTPS byte readback passed; independently,
    `korea-originals/156785691.html` returns 200 and `korea.html` shows 4
    licensed originals and 3 reviewed English pairs.
  - English owner handoff, workflow_run [39344660562](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39344660562):
    one private draft delivered to the owner only at 23:59:07 UTC (draft SHA-256
    `5a6834fd1821…`, receipt `4f5dbaa4e3`). No reviewed JSON exists and
    `korea-translations/156785691.html` returns 404: nothing English is public
    until human review and the owner release dispatch.
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
