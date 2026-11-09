# Singapore MINDEF m0022 — controlled migration release runbook (9 November 2026)

Scope: how to release migration m0022 (`singapore_mindef_source_records`) to the
tracked production database, with backup, verification and rollback. This is
release-readiness documentation for the integration of PR #1017 (implementation)
and PR #1014 (governance). It is **not** an authorization. Merging, deploying,
mutating production data, activating MINDEF collection or model processing, and
any paid call each need separate founder authorization.

## 1. What the merge does, and why it matters

m0022 is applied to production by **merging to `main`**, not by a deliberate
deploy step:

| Path | What it does |
| --- | --- |
| `.github/workflows/daily_update.yml` | Five cron slots (12:23, 12:53, 13:23, 13:53, 14:23 UTC) plus `workflow_dispatch`. Checks out `ref: main`, concurrency group `daily-update`. Step 4b runs `python -m migrations.cli --apply`, then `python scripts/verify_db_current.py`, before the offline suite, the baseline hash and the pipeline. |
| `pipeline.py` `init_db()` | Also applies pending migrations at pipeline start. |
| `ph_afp_verified_official_link_production.yml`, `ph_nsc_verified_official_link_production.yml` | Each runs `python -m migrations.cli --apply --db "$GITHUB_WORKSPACE/pla_watch.db"`. Any run of these after the merge also applies m0022. |

The migration lands in the next run of any of these workflows after the merge,
and the run then commits `pla_watch.db` back to `main` through the
`reconcile-db` merge driver. There is no separate approval point after the
merge. All approval therefore has to happen before it.

Runner semantics (`migrations/runner.py`): each migration runs in its own
transaction and rolls back on failure with no `schema_migrations` record;
foreign keys are off during the migration and `foreign_key_check` runs inside
it; `is_already_applied` recognises a database that already has the effect.
A failed migration step fails the Daily job before collection, commit or deploy.

## 2. What m0022 changes (rehearsed on a copy of the tracked database)

Rehearsal date 2026-11-09, code at the integration head, input = the tracked
`pla_watch.db` at git blob `d0fdab6d8e936eb5c4a8643bd5ffaa898672fe2c`
(sha256 `6520f739d2b80934a82636b524907d577c15b47d98c7f92714711be217683324`,
identical on `origin/main` `8a79605212`). The copy lived outside the repository;
the tracked file's hash was unchanged afterwards.

| Check | Before | After |
| --- | --- | --- |
| `migrations.cli --status` | 21 applied, 1 pending (`0022`) | 22 applied, 0 pending |
| `--dry-run` | file hash unchanged | n/a |
| Tables | n/a | one added: `singapore_mindef_source_records` (0 rows) |
| Row counts in every pre-existing table | n/a | unchanged except `schema_migrations` 21 → 22 |
| `daily_machine_records` | 6 rows (AFP 4, NSC 1, Kemhan 1; 0 Singapore) | identical |
| Triggers added / removed | n/a | none; four **replaced**: `mindef_public_no_machine_insert`, `mindef_public_no_machine_update`, `daily_machine_parent_insert`, `daily_machine_parent_update` |
| `integrity_check` / `foreign_key_check` | n/a | `ok` / empty |
| `--verify` | n/a | `RESULT: OK`, all orphan counts 0 |
| `scripts/verify_db_current.py --db` | n/a | `fully_current` |
| Second `--apply` | n/a | applies nothing (idempotent) |

Trigger behaviour on the migrated copy, each probe in a rolled-back
transaction:

| Insert into `daily_machine_records` | Result |
| --- | --- |
| Singapore row, no parent | aborts (`MINDEF machine publication held`) |
| Frozen identity `15aug26-speech` | aborts |
| Parent `public_scope='held'`, released row | aborts |
| Parent `official_link_only`, hashes bound, MINDEF-attributed, not model-flagged | accepted |
| Same, summary lacks "MINDEF" | aborts |
| Same, `model_flagged=1` | aborts |

Before m0022 the two MINDEF triggers abort every Singapore machine row
unconditionally. After it, a Singapore row is accepted only when a link-only
parent with matching metadata, content and capture hashes exists. The migration
creates no parent and no machine row, and publishes nothing.

What the migration does **not** do: it does not set any policy boolean, enable
`singapore_shadow.yml`, create the private custody checkout, supply the HMAC
key or call a model. `desk_registered` stays `False`. The Singapore Desk page
renders its "no admitted records" branch until a parent and a machine record
exist.

## 3. Preconditions (all must hold before requesting merge approval)

1. The integration PR head SHA is qualified: exact-head GitHub CI green, and the
   head still equals the SHA named in the PR (any push voids the qualification).
2. `config/philippines_daily_policy.json` `sg_mindef_releases`:
   `private_model_processing`, `public_machine_explanation` and
   `unattended_release` are all `false`; `singapore_shadow.yml` job still has
   `if: ${{ false }}`; the registry entry is unchanged.
3. No `daily-update` or `ph_*_verified_official_link_production` run is in
   progress or queued (check the Actions tab). A merge during a run lets that run
   finish on its own checkout; the next run applies m0022.
4. `origin/main`'s `pla_watch.db` blob is still the one recorded in the backup
   record below, or the rehearsal in section 2 is repeated against the newer
   blob. The scheduled Daily commits to `main` daily, so this changes.
5. The founder has authorized the merge itself, naming the integration PR head.

## 4. Backup (before the merge)

Record each of these in the release note or PR comment. Do not store any secret.

1. **Git identity of the pre-merge database.** `git rev-parse origin/main` and
   `git rev-parse origin/main:pla_watch.db`; `git show origin/main:pla_watch.db | shasum -a 256`.
2. **Consistent file copy outside the repository:**

   ```bash
   git show origin/main:pla_watch.db > "$BACKUP_DIR/pla_watch.pre-m0022.db"
   shasum -a 256 "$BACKUP_DIR/pla_watch.pre-m0022.db"
   ```

   The tracked file has no `-wal`; if a local live copy is used instead, take it
   with `sqlite3 <db> ".backup '<dest>'"` rather than `cp`.
3. **Private recovery copy** in the owner-approved private evidence repository
   (immutable branch, byte-for-byte checksum, a restore actually performed), as
   in `docs/CHINA_ACTIVE_CORPUS_RETIREMENT_2026-10-15.md`. A public Actions
   artifact must not be the only copy.
4. Record the last successful `daily-update` run before the merge, so a later
   comparison has a known-good baseline.

## 5. Release sequence

This is the sequence to follow **once the founder authorizes the merge**. Steps
marked (external) change repository or workflow state and need their own
authorization if they are used.

1. Confirm section 3. Complete section 4.
2. Choose the merge time. Merging outside 12:23–14:23 UTC (and outside the
   late-start tail, observed up to 100 minutes) means the next scheduled run is
   the first to apply m0022, and the operator is present for it. Alternatively,
   merge and immediately start a `workflow_dispatch` of `daily-update` while
   attended.
3. (external, optional) To avoid any unattended first application, temporarily
   disable the schedule trigger or the workflow before the merge, then run it by
   `workflow_dispatch` while attended. Re-enable afterwards. This changes
   repository settings and is not part of this PR.
4. Merge pinned to the reviewed head (`gh pr merge <n> --merge --match-head-commit <sha>`),
   using the repository's usual merge method. Do not enable auto-merge.
5. Run (or wait for) one `daily-update` and watch step 4b. Expected log lines:
   `applied : ['0022']`, then `database state: fully_current`.
6. Run the verification in section 6 against the committed `pla_watch.db` on `main`.
7. Verify the live site in section 7. State separately what is merged,
   migrated, committed to `main`, deployed and observed live.

## 6. Verification after the migration

Run against a copy of `main`'s committed database (never the working live file):

```bash
git show origin/main:pla_watch.db > "$SCRATCH/post.db"
python -m migrations.cli --status --db "$SCRATCH/post.db"   # 22 applied, 0 pending
python -m migrations.cli --verify --db "$SCRATCH/post.db"   # RESULT: OK
python scripts/verify_db_current.py --db "$SCRATCH/post.db" # fully_current
```

Then, using a read-only connection (`file:...?mode=ro`):

| Query | Expected |
| --- | --- |
| `select version, name, note from schema_migrations where version='0022'` | one row: `singapore_mindef_source_records`, note `applied` |
| `select count(*) from singapore_mindef_source_records` | `0` (no admission has been authorized) |
| `select count(*) from daily_machine_records where source_family='sg_mindef_releases'` | `0` |
| other `daily_machine_records` counts | unchanged apart from rows the day's Daily legitimately added |
| `sql` of `mindef_public_no_machine_insert` | contains `singapore_mindef_source_records`; no unconditional abort |
| `pragma integrity_check` / `pragma foreign_key_check` | `ok` / empty |
| `--verify` orphan counts | all `0` |

If the day's Daily added articles, row counts elsewhere will differ from section
2; compare against the previous day's `main` blob, not against this document.

## 7. Live verification

After the deploy step finishes, with the pages' own text as the source of truth:

- Home, the Singapore Desk page, the Archive and the search index load; the
  Singapore Desk shows the not-yet-admitted branch, including the sentence that
  MINDEF outbound links follow the standing official-host rule and do not extend
  to copying original text or model processing.
- No Singapore machine explanation, MINDEF original title or body appears on any
  public page (`scripts/audit_mindef_public_surfaces.py` reports zero rows).
- `scripts/validate_output.py` on the deployed `output/`: 10 governed warnings is
  the documented baseline; any new warning is investigated, not suppressed.

## 8. Rollback

m0022 is additive (one table, four re-issued triggers) and idempotent. There is
no SQL downgrade.

| Situation | Action |
| --- | --- |
| Migration step fails in the Daily run | Nothing is committed: the job stops before collection, commit and deploy. The runner rolled the migration back. Diagnose from the log; `main`'s database is still at 0021. Revert the merge only if the failure is attributable to the code. |
| Migration committed, a defect appears, nothing admitted | `git revert -m 1 <merge sha>` for the code, plus restoring `pla_watch.db` to the pre-merge blob. Restoring the database alone is not enough: the running pipeline would reapply m0022. Revert both in one change, then verify `--status` shows 21 applied. Leaving m0022 in place is also safe because it is inert while the policy booleans are false. If only the code is reverted and the database keeps the `0022` row, `verify_db_current.py` does not object (it flags missing ledger entries, not extra ones) and the table stays as an unused additive object. |
| Rows were admitted after the release (a later activation) | Do not delete rows by hand. Follow the source-correction path (`core/singapore_mindef_links.py` holds a drifted version rather than replacing it), preserve the ledger, and bring the founder in. |

A revert never un-publishes anything on the live site by itself; redeploy and
verify section 7 afterwards.

## 9. Activation is separate and stays held

None of this runbook activates MINDEF. The shortest separately authorized
activation sequence is in `SINGAPORE_MINDEF_DAILY_COMPLETION_2026-11-09.md`
(private custody checkout, link admission, policy booleans and the
`DAILY_SG_MINDEF_RELEASES_KEY`, one bounded run with its cost cap, live
read-back). Two items to carry into that authorization:

- `desks/registry.json` still states, in wording from PR #1014, that new
  production collection and model processing are held. It must be updated to
  match the activation decision at that time. This PR does not change it.
- The Singapore Desk fallback sentence about model processing is accurate only
  while processing is held; update it at activation.

## 10. Out of scope here

No merge, no deploy, no production database write, no collector or
`singapore_shadow.yml` activation, no policy-boolean change, no paid model call,
no publisher contact and no unrelated CI repair. Known environment-only local
failures (evidence-store root, missing Chromium, file-mode and WAL sidecar
tests) and the intermittent homepage-intro browser test are not touched.
