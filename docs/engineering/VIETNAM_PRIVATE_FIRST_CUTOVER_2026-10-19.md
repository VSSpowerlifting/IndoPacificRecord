# Vietnam private-first cutover — performed custody and held activation

PR #827 merged as `31326251c572725089219293ecc0261c7b9f8f0e` before this work.
This is its one coordinated public/private continuation. Collection activation,
public-writer retirement on live main, credentials, production admission and
publication remain owner actions. No new archive framework, adapter, database,
model call or editorial workflow is introduced.

## Actually preserved and restored

The three complete private histories were fetched separately from public Git.
MPS already matched. The two MOIT mirrors were behind the genuine October 19
scheduled attempt; they were fast-forwarded without force, then independently
fetched from private GitHub. No public ref changed.

| Family | Public and independently read-back private tip | Originals / versions | Captures | Ledgers | Reachable Git objects |
| --- | --- | ---: | ---: | ---: | ---: |
| MPS | `cb607582eda7bd8760663540c33de2f73da411ff` | 11 / 11 | 49 | 9 | 113 |
| MOIT Energy | `ac4ea9637a81b766f296239b3813d162830bb792` | 2 / 2 | 13 | 10 | 75 |
| MOIT Foundational Industry | `68440328a801ffac5d1d4c9b37324d040ef49d7e` | 1 / 1 | 12 | 10 | 74 |

The existing ministry reviewer checked original versions, content-addressed
captures, SQLite integrity/hash chains, immutable clocks and ledgers. Public and
private full reachable object sets match. MPS's last healthy logical date remains
October 14. Both MOIT families genuinely completed October 19 independently;
the batch failed MPS. Neither MOIT publication hold changes.

The four requested October 15–18 failed-attempt ZIPs **and the subsequently
observed October 19 failure `39334327055-1`** were downloaded, authenticated
against GitHub's artifact SHA-256/attempt/collector metadata, and retained as
intact ZIPs. They were copied to the private evidence ref
`archive/vietnam-actions-zips-20261019`, then fetched independently and rehashed.
Historical Actions remain failures. No recovery is claimed from these copies.

The owner named Benjamin Yang as custodian and authorized two local destinations.
A real backup and fresh, network-free restore have now completed there. The
private companion's `manifests/vietnam_private_restore_2026-10-19.json` records
pins, counts, the archive commit and receipt hashes, with collection/release
approval explicitly false. Restore receipt SHA-256:
`ee5938ee89e9a94c64ad8be64778e43aea775cea29cee2cd25bbef5c0c96e21b`.
The backup manifest is
`3f78bf90e388aa5a5033bd726e2dd41fbd4d11a828768b9ad1fef6cfe692df6c`;
the seven-ref native Git bundle is
`6b9fdd7a0a7ef2fd3e298e3d1bbee1dd9feae620d796b9d1fbffff011484b3be`.

All three separate restored repositories passed `git fsck --full --strict`, exact
commit/ref/full-history comparisons and the existing ministry evidence reviewer.
Five restored ZIPs passed SHA-256 and ZIP CRC checks. Original repositories,
source captures and failed runs were not modified. Encryption is the owner's
existing **FileVault-encrypted APFS Data volume**, independently checked using
`fdesetup` and `diskutil`; directories are 0700, files 0600 and both roots are
Git-ignored. No encryption credential was invented, displayed or provisioned.
This is an off-GitHub, same-device backup, not a separate-device backup or a
portable encrypted file. FileVault protects storage at rest; an authorized logged-in
user can read the mounted files. Loss of this device can still lose both local
copies. Exact private paths, maintenance and restore commands are in the private
companion's Vietnam runbook.

A separately checksummed private addendum retains the prior local rehearsal's
23 expected identity/content hashes (12 absent from the canonical 11). Its
`canonical_recovery_proven` flag is false. The actual private verifier must first
authenticate genuine private Git/Actions state, then compare that reference;
the reference never creates records or substitutes for real recovery. SHA-256:
`9c678e9b3008c2665a33161b6360e261740d0cb3a4bf3967ca5bf7fb37b65ab2`.

## Implemented boundary

- The public workflow's original writer is inert (`shadow.if: false`), its public
  schedule is removed, and the guarded `reviewed-release` job is retained.
  The declaration audit binds all three families to the private workflow as
  **external scheduled declarations, runs unverified**. A declaration does not
  assert activation or success. The audit refuses a reintroduced public writer.
- The private companion retires only the three Vietnam mirror matrix entries.
  Other source mirrors remain active. One owner-gated private ministry workflow
  uses native private `GITHUB_TOKEN` Contents write / Actions read. It checks
  exact restored public ancestry/tips, retired public writer/mirrors, in-flight
  legacy jobs and optimistic source-head checks. Concurrency serializes private
  writers. Missing state cannot restart the clock or import local rehearsal.
- It runs the same three collectors serially, the same six-day/request budget,
  RSS recovery and shared MOIT host gate. Independent family failures persist
  as private attempt receipts; valid state/captures/ledgers are committed without
  force and cloned independently for integrity readback. Corrupt state cannot be
  pushed. Complete failure artifacts and original-bearing logs stay private.
- `verify-private-state` replays committed state and authenticates completed
  private collector attempts, without a human review or publication claim.
  The private workflow SHA and public collector-code SHA are bound separately
  by source-specific private attempt receipts. Legacy originals retain authentic
  public provenance; new private versions cannot fall back to public attempts.
- Metadata preparation requires a real, separately sealed exact human review,
  source-use authorization and custody attestation. The existing private-runner
  MAC pattern exports **only the approved identity/URL/date/issuer rows and
  bounded provenance hashes**, with strict field/type/digest allowlists. No
  original title/body, HTML, model text or unapproved row is accepted.
- Public release receives that metadata projection, never clones private
  originals, verifies separate bridge/review seals and fresh private ref/attempt
  metadata, then uses the existing atomic SQLite publisher. Exact main/source
  concurrency, Vietnam-only generated output, validation, Pages Git and fixed
  HTTPS readback remain. The owner release variable stays separate and inert.

The public receiver will require an owner-selected Contents-read/Actions-read
credential scoped only to the private repository. No existing secret's scope is
assumed and no credential was created or used for this bridge. The private
collector itself needs no PAT. Future bridge/review keys must be distinct and
owner-provided; none is provisioned or used for a real approval in this work.

## Coordinated owner cutover — commands prepared, not executed

Review exact public/private PR heads and CI together. Keep all release-enable
variables off. The private runbook provides the command sequence and checks:

1. Disable the old public workflow and let every queued/running legacy writer
   finish; retain its outcome/evidence. Reconfirm final public tips equal the
   restored pins above. If any tip changed, refresh the backup and genuinely
   restore it before continuing.
2. Merge the exact reviewed public retirement and private companion commits.
   Vietnam mirror rows become retired; unrelated mirrors remain. Drain any
   already-started mirror run. Re-enable the public workflow only after the
   merged `shadow.if: false` retirement is independently read back.
3. Set the private restore-receipt variable to the exact hash above and enable
   private collection only with explicit owner authorization. Dispatch preflight
   and inspect actual step outcomes; preflight green is not collection proof.
4. Dispatch one bounded **new** recovery attempt with explicit target
   `2026-10-19`, using the five retained failed-attempt IDs. The four October
   15–18 snapshots remain mandatory inputs; the fifth preserves the newer
   observed boundary. Fetch current official RSS/articles normally under current
   robots rules. A lost overlap holds; do not broaden source scope or rewrite
   old clocks/failures. A delayed approval may make this a real source blocker.
5. After it finishes, authenticate the actual committed private source tip and
   new attempt via `verify-private-state`. Compare the expected 23 identities,
   first-version/capture hashes, immutable history and recovery receipts. The
   prior local rehearsal is only an expected-cohort reference, never canonical
   proof. New identities or changed versions must be explained from real source
   evidence, not forced into a count.
6. Dispatch a second explicit collection to prove genuine idempotent replay
   (zero new/changed original versions for the same cohort). Observe a subsequent
   **actual `schedule`** collector job and its private persistence/readback.
   A skipped schedule, manual dispatch or replay does not prove unattended work.
7. Refresh and restore the off-GitHub backup including the genuinely recovered
   state before claiming the recovered corpus independently backed up. Keep MOIT
   histories and their independent holds intact. Do not enable metadata export,
   public admission, models or editorial sending during this assignment.

Public originals remain historical public Git evidence; this cutover cannot undo
past distribution. The existing editorial feeder, two exact-version synopsis
notes and Brief #18 are preserved. New originals receive no automatic model,
translation, public reuse or editorial approval.

## Rollback

First disable `VIETNAM_PRIVATE_COLLECTION_ENABLED`, drain private attempts and
preserve their complete state/artifacts. Leave public original writers and the
three mirror entries retired. Preserve every public/private ref and the ZIP
custody branch; never force-push, erase failures or copy new private originals
back into public Git. Roll back collector **code** through a separately reviewed
private/public code change, keeping the archive history. For corruption/loss,
restore to fresh isolated repositories, verify exact pins/hashes, and prepare a
new private recovery ref for owner review. Never overwrite a live ref from a
backup or resume public collection as a fallback.
