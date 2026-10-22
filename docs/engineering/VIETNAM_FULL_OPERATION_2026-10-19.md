# Vietnam desk — recovery and exact release handoff, 19 October 2026

**Follow-up:** #827 has merged. The dated observations below remain historical.
Current performed private mirror/ZIP custody, owner-selected local encrypted
backup/restore, and the still-held coordinated writer/provenance cutover are in
[the private-first receipt](VIETNAM_PRIVATE_FIRST_CUTOVER_2026-10-19.md).

**Status: built further; not operational or maintained end to end.** This is
one integration candidate after merged #824, based on current main
`ce94bd2293130764210e5fe228b1a9072c3d4101`. No production admission, deployment,
source-branch push, schedule activation, source rights grant, signing, paid model
call, or editorial email is authorized or performed by this work.

## Current evidence and dependencies

| Family | Canonical public source head | Preserved originals | Last healthy scheduled logical date | Production links |
| --- | --- | ---: | --- | ---: |
| MPS foreign affairs | `cb607582eda7bd8760663540c33de2f73da411ff` | 11 | October 14 | 0 |
| MOIT Energy | `5d25d68ee5bd3d1e8e5c7759db880a30d172491a` | 2 | October 14 | 0 |
| MOIT Foundational Industry | `75035550a2f9db4f7a1cac57925141961b390d60` | 1 | October 14 | 0 |

Authenticated GitHub reads on October 19 verified these tips and the original
MPS first-seen attempts through the existing admission attestor. All 14 originals
replay through the existing ministry reviewer. The corresponding private
`archive/vietnam-*` refs still have the same three tips. They are mirrors, not
private canonical writers or independent backups. The newest observed scheduled
attempt is October 18's failed `39164567807-1`; October 19's schedule had not
executed at this observation. October 15–18 were real failures; the old workflow
never attempted MOIT after the MPS failure. #824's sibling isolation is on main
but has no subsequent scheduled receipt yet. No competing Vietnam integration
PR was open at inspection. Open #805/#807/#821 own Sunday editorial changes;
this candidate does not duplicate them.

Existing production SQLite, generated Vietnam page and publisher-link rail are
reused. Brief No. 18, *What Is Being Built in Laos?*, remains the public Vietnam
research feature. An admitted link is not an original-text record or desk launch.
Current main, Pages Git and HTTPS Vietnam bytes independently match SHA-256
`ec9e66fd9322779aac2fa77ff302d70e38932008cd931b2ec436e82a736e4654`;
HTTPS returned 200 with Brief #18 and no admitted ministry links. This verifies
the existing public page, not publication by this candidate.

## Bounded RSS recovery actually exercised

A one-day lookback is insufficient. The October 15 preserved RSS introduced
previously unseen items dated October 13 (`1792026540`) and October 14
(`1791960707`) behind its newest item. The October 16 snapshot similarly added
October 15 items. No new archive, API, pagination, category, host or source scope
was requested.

The collector keeps the existing six-day window, cap 40 and daily 18:17 UTC
schedule. It joins captured feeds only across surviving official identities,
checks descending declared instants, rejects publication timestamp changes and
unexplained disappearance above the newer feed's truncation boundary, and
fetches **all** in-window identities from the union, including late inserts.
An entire feed turnover or absent starting boundary holds collection. More
frequent polling would reduce overflow risk but is not activated here.

`coverage_basis=observed_rss_chain` and `archive_completeness_proven=false`
describe the actual contract. This proves the continuity of observed RSS
snapshots, not an exhaustive publisher archive: a release inserted and removed
entirely between observations, or backdated below every visible tail, is not
observable. Never describe that uncertainty as publisher silence.

The four exact failed-attempt ZIPs were downloaded and their bytes checked
against GitHub's authenticated artifact digests. Their MPS ledgers, collector
commits, capture times and individual RSS hashes were checked independently.
Recovery imports only those captured feeds and provenance; it does not rewrite
failed ledgers, borrow another source's clock or import purported article bodies.
Normal current robots/access and article extraction still apply.

| Failed attempt | Artifact | ZIP SHA-256 |
| --- | --- | --- |
| `38809387069-1` | `12006859354` | `094d6ffcd2e46dabff8260890415965e210f045b5185137e7754d51d0a2b38dc` |
| `38967228796-1` | `12076175074` | `08b86fe0f35fa7b272dde77d6ca29ac29f7e56486d38bec04cb6e83b0d361435` |
| `39067453204-1` | `12113912225` | `06dc3d48e6c0d41f2dc1473ffe22b870ea27ffc222d057d2a2431c9371192dd0` |
| `39164567807-1` | `12150192474` | `a4cebc16d7bee7f3f3b09489a36f7bdb5560424215ca0a7ed8f895c6ef149bfc` |

The October 12–18 offline discovery union has 17 references, 12 not present in
the canonical 11-record corpus. A **live local rehearsal** on October 19 then
collected the actual October 13–19 window: 16 articles, 12 new, four unchanged,
23 stored originals, no extraction/fetch failures, 18 requests including robots
and RSS. Required identity and two-second spacing were retained. Originals are
only under `/tmp/ipr-vietnam-20261019/live-mps/state`, outside Git; the ledger
explicitly says `uncommitted-local-rehearsal`, not an authenticated Actions
collector. This is temporary task-local evidence, not a durable private cutover.
Replaying those captured responses offline returned `ok_all_duplicates`, zero
new records, 16 unchanged and the same 23-record archive.
The live result and provider receipts are in `/tmp/ipr-vietnam-20261019/`.

After integration and an authorized recovery dispatch, use the existing workflow
with `operation=collect`, an explicit current logical `target_date`, and
`mps_recovery_attempts` set to the four IDs above, space-separated. Do not rerun
old scheduled jobs or claim their failed dates succeeded. Exact artifacts must
still be available and the live RSS must overlap the recovered frontier. The
newly recovered originals receive the new run's identity. Invalid recovery or
provider failure holds MPS while MOIT still runs independently. Existing failed
Actions, attempt artifacts and the logical-slot watchdog remain owner-visible.
A real scheduled run after merge is still required to prove unattended behavior.

## Exact MPS human review and release

`research/vietnam_mps_link_release_candidate.json` proposes **three** genuine
records: `mps-vi:1791199100`, `mps-vi:1791199677` (October 5), and
`mps-vi:1791971146` (October 14). It includes exact URLs, dates, issuer,
original/capture/metadata hashes and immutable source tip, with every public
permission still held. Concordia's visible title must be read from the preserved
original, never reconstructed from its URL slug. Review original-language
fidelity, publisher attribution, changed-version/anomaly state and source use
for each selected item. Do not mistake the packet for a rights grant or signoff.

The full 11-row candidate digest remains
`93224b092f9a4e2eaa12247e224a4c3c06f2ae559b21a1185e398d749136201a`.
The private existing queue at `/tmp/ipr-vietnam-20261019/review/` supplies original
titles and version locators without adding public originals. The unsigned review
worksheet is `/tmp/ipr-vietnam-20261019/UNSIGNED-mps-release-review.json`.
Reproduce both with the existing `prepare_vietnam_official_links` and
`prepare_vietnam_mps_review_queue` commands against the exact tip above. Any tip
change requires a fresh candidate and exact decision; old approval is not carried.

The decisions remain separate: existing bounded private research capture;
outbound linking; public factual URL/date/issuer metadata; original titles;
full bodies; translations; external-model processing; and images. This proposal
requests only the URL/date/issuer/identity fields. Other reuse receives no new
authority. A protected-custody attestation must describe an actual verified
backup/restore, not merely check a box.

Once that review and custody work is actually approved, the owner must supply
an independent `VIETNAM_LINK_REVIEW_KEY` of at least 32 bytes and the existing
regional HMAC envelope with domain `IPR-VIETNAM-OFFICIAL-LINK-RELEASE-v1\n`.
No key or affirmative envelope was created here. Commit the exact signed
decision under `config/vietnam_link_releases/<name>.json` in a separately
reviewed release. Only then enable `VIETNAM_MPS_RELEASE_ENABLED` and explicitly
dispatch the existing workflow with `operation=reviewed-release`,
`expected_main`, `source_commit` and `decision_name`.

The prepared publisher validates everything on a sibling SQLite copy, permits
only pending migration 0013, preserves every unrelated row, verifies admitted
rows independently and atomically replaces the DB only if its preimage and
sidecar state are unchanged. It renders privately, copies only Vietnam HTML,
validates the site and regional index, checks main/source concurrency and
commits only `pla_watch.db` plus `output/vietnam.html`. It then preserves the
existing Pages tree while publishing only Vietnam HTML, fetches the remote Git
blob back, and independently compares fixed-origin HTTPS bytes and metadata.
A stale deployment fails the release run. The existing job's `daily-update`
concurrency and non-fast-forward checks protect the shared writer boundary.
This is an exact reviewed release, not standing future-record publication.

No signed review, key, release-enable variable, production row, release commit,
Pages update or new HTTPS source row exists from this work. The current path
supports the pinned pre-cutover public history; future private-run provenance
must be integrated with its real private workflow identity before private-only
new records can be admitted. Never point the public attestor at private runs
and claim they are authenticated.

## Minimum private-first cutover: owner action and engineering boundary

Use the existing private repository, native Git histories, collectors and
append-only captures; do not create another storage service. Minimum cutover:

1. Preserve final public source tips and failed-attempt ZIPs. Prove ancestry,
   capture hashes, original versions and source clocks against the three current
   private archive refs. Obtain and restore an **independent off-GitHub** backup
   of all three histories and recovery ZIPs; name its custodian and restore
   receipt. Public history and historical Actions exposure remain intact.
2. Retire all three public source writers and exclude their mirror entries in
   private `sync_source_git_history_private.yml` before activating any private
   writer. Freeze their public tips; do not delete/force-push history. These
   coordinated changes need actual owner release, not an inferred variable.
3. Reuse `vietnam_ministry_remote` in one private workflow, on the same daily
   slot with independent family state and shared MOIT host gate. Its own
   `GITHUB_TOKEN` supplies private Contents write and artifact retention; it
   needs **no new private write PAT**. Preserve the existing `shadow/vietnam-*`
   local branch names for runner/reviewer compatibility, pushing each explicit
   `HEAD:archive/vietnam-*` private destination with an expected-head check.
   Verify that public writers/mirrors are retired on every run. Private failed
   artifacts must remain private; never upload state from a public job.
4. For a public metadata bridge, request a **source-scoped private read**
   credential with Contents read on `ipr-source-evidence-private` (Actions read
   only if the public attestor must verify private attempts). Keep any reviewer
   seal separate. Existing secret names `IPR_PRIVATE_VAULT_READ_TOKEN` and
   `IPR_KOREA_PRIVATE_READ_TOKEN` do not prove Vietnam access/scope; do not reuse
   or inspect their values. Prefer emitting the established authenticated
   metadata projection inside the private runner, so public code never receives
   Vietnamese original text. Bind its real private run, collector commit and
   exact archive head; update the existing admission attestation accordingly.
5. Only after a source-specific restore/cutover approval, merge the essential
   private companion and public writer retirement, configure its credentials,
   activate the private schedule and witness a genuine scheduled success plus
   failure/retry. The current archive mirrors alone cannot satisfy this step.

No Vietnam private workflow, credential scope or restore receipt exists today.
The minimum next owner action is to identify/authorize the backup custodian and
restore destination and approve the coordinated private writer/bridge scope.
That concrete boundary prevents honest completion; a paper attestation does not.

## MOIT: two separate held decisions and unsent permission requests

The official [terms page](https://moit.gov.vn/quy-che) was fetched with the
identified collector on October 19, 18:51 UTC: HTTP 200, SHA-256
`405d839d2f4b08dba576f8b708a807561653bceab7627f88b660386e4b60b822`.
Its body permits qualified download/storage/printing and requires attribution;
the footer still requires prior written consent for extraction/citation.
No machine reading here reconciles that into publication or model permission.
The exact `robots.txt` returned 200 but still serves a rules file as
`text/html; charset=UTF-8`; its content-policy disposition remains a separately
named human decision. Existing transport records the warning rather than
pretending it is absent. See the retained source decision in issue #196.

| Family | Preserved record count | Narrow disposition |
| --- | ---: | --- |
| `vn_moit_energy_vi` | 2 | Keep private review; hold public links/metadata, titles, bodies, translation, external models and images pending source-specific consent/terms and robots review. |
| `vn_moit_foundational_industry_vi` | 1 | Same independent hold; Energy approval would not release this family. |

**Unsent request for Energy:** Please confirm permission for IPR to retain
unaltered originals privately from
`https://moit.gov.vn/tin-tuc/phat-trien-nang-luong`, and independently whether it
may publish only attributed official URL/date/issuer metadata with outbound
links. Please reconcile the download/storage terms with the footer's written
consent requirement and specify attribution, conditions, scope, duration and
withdrawal procedure. Please state separately whether original titles, bodies,
English translations, processing by named external models and images are
permitted; absent an explicit grant, IPR will keep those uses held.

**Unsent request for Foundational Industry:** The same questions apply
independently to
`https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang` and its
one preserved record. Please identify this family explicitly in any response;
consent for the Energy category will not be treated as consent here.

The owner must authorize external contact and identify a legitimate ministry
recipient before either request is sent. No contact, consent or credential is
invented. There is no standing owner-authorized MOIT metadata exception; both
code holds remain unchanged, with no substitute source or scope reduction.

## Editorial integration and verification limits

The existing MPS queue and Sunday feeder joined the two exact-version October
11–17 synopsis notes: five in-window machine-eligible originals, two matching
private synopsis candidates. `--require-vietnam` succeeds. The other three have
no matching synopsis and are not silently sent to models. The published Brief
No. 18 remains featured; no manuscript, byline, editorial approval or Dylan
handoff was rewritten. The newly recovered 12 originals have no source-specific
synopsis/rights decisions and are not model inputs. Recovered local rehearsal
state is deliberately not substituted for authenticated scheduled canonical Git.

Focused tests cover finite-feed overflow, late insertions, withdrawal, date
changes, provider-digest/attempt tampering, unchanged replay, review refusal,
atomic DB preservation, independent HTML/HTTPS parity and production CLI guards.
Full offline/PR CI and output validation receipts belong to the exact PR head.
The graphify code refresh completed (22,471 nodes), reporting 287 files with no
extracted nodes and omitting its oversized HTML view; that map is not source
or claim evidence. Required PR checks, actual scheduled recovery, private
cutover/restore, exact human MPS release and two MOIT permissions remain distinct.

## Shared Daily integration (follow-up candidate, 19 October)

The ministry captures above now have a path into the shared Daily, under
`docs/engineering/SHARED_DAILY_DESK_ARCHITECTURE_2026-10-19.md`. Nothing is
operational: no production run, admission, model call, schedule or publication
was performed, and the registry keeps Vietnam in shadow.

**Reused, not rebuilt.** The existing collectors, private state branches,
`vn.prepare`/`vn.authenticate` source and attempt checks, `ScreeningProfile`,
`Analyzer.analyze_record()` → `analyze_desk()` (never the China `analyze()` path),
the `articles`/`sources` tables and `site/render.py` record pages. There is no
second database, analyzer, sync system or Vietnam site.

**Added.**

- `core/vietnam_corpus_bridge.py` is the thin intake. It reads committed
  captures at an authenticated state commit, with no recrawl. Each version gets
  a stable identity, and duplicates and concurrent commits resolve to a single
  row. A material change is held, never overwritten. Bad dates, missing bodies,
  unsupported versions and unauthenticated sources are refused. Columns are
  projected per permission. The private ledger lives outside the repository.
- **Reconciliation (21 October):** Vietnam provenance uses migration
  `0017`, after shared Daily `0015` and Korea corpus `0016`. Its table
  `vietnam_article_provenance` keeps source identity, publisher date, version
  hash, rights decision, QA and attribution. The `articles` foreign key
  cascades; no original text is stored by this migration. The tracked database
  was derived from main `647a3246d5`, with `0017` applied first on a disposable
  copy. All 21 pre-existing tables retain identical rows and schema; foreign
  keys and integrity pass, and migration replay is a no-op. Only the empty
  provenance table and its migration ledger row are new. The stale #834
  database is not used. Korea record rendering and shared summary recovery
  from main are retained alongside Vietnam's gated rendering.
  Focused offline run: 1,137 passed, eight skipped, one failure out of 1,146.
  The NSC `test_wal_mode_source_read_leaves_no_sidecars` leaves a scratch SHM
  file on this macOS/Python 3.9 environment; the identical failure reproduces
  in its 21-test module on exact main and this branch. Philippines code and
  configuration are unchanged. Separately, all 129 shared analyzer/screening/
  U.S. tests pass. Current-corpus render parity passes across 1,300 files.
- `processing/screening.py` adds three per-family `VIETNAM_*` profiles and a
  refusing desk-level profile. Their event types are distinct: meeting,
  announcement, financing, commencement and completion.
- Terminology lives in `analysis/vietnam_terminology.json`, version
  `vn-terms-2026-10-19.1`.
- `core/vietnam_daily_qa.py` holds the deterministic rubric
  `vn-qa-2026-10-19.1`, a bounded model second pass, failure codes, retryable
  holds that escalate after three attempts, and a Vietnamese evaluation set.
- `core/vietnam_source_use.py` holds the standing policy
  `vn-source-use-2026-10-19.1`. It covers seven separate permissions with their
  dependencies, owner decisions sealed with HMAC, and item exceptions.
  Attribution is a condition, not a basis.
- `scripts/run_vietnam_daily_bridge.py` is the Daily command. It runs on an
  atomic sibling copy and requires `--release` for the canonical database.
  Without a sealed decision it builds no model client. Ledgers are staged and
  published only after the copy replaces the database, so a discarded run
  cannot settle or escalate a record that never reached the corpus.
- After the #831 cutover, the Ministry of Public Security runs with
  `--private-custody PUBLIC_FROZEN_TIP --private-state-repo <private clone>`.
  The bridge reuses `vn.prepare(private=True)` and `vn.authenticate_private`:
  it checks the exact archive commit, frozen public writer, private attempt
  receipts, workflow identity and custody. It reads with a separate read-only
  `VIETNAM_PRIVATE_PROVENANCE_TOKEN`. Records admitted publicly before the
  cutover resolve as duplicates and keep their public commit. The run reads
  originals from a local private clone, so it must execute on the private
  runner (private #20's workflow), never in a public job; the corpus, ledger
  and report receive only the rights-permitted article fields and provenance.
  Returning that database post-image to the public release is the one open
  placement step, following #831's private-projection handoff. MOIT has no
  private authentication path yet: `authenticate_private` is MPS-only, and the
  cutover retires all three public writers, so new MOIT captures have no
  authenticated bridge input until #831's private attestation covers them
  (both MOIT families are rights-held regardless). m0017 stores
  the private commit SHA, not the repository holding it; the record page
  labels it "private evidence commit". #831's metadata-link admission stays a
  supplementary source index for rights-restricted items, not a second writer
  of articles.

**Simulated rehearsal.** `scripts/rehearse_vietnam_daily.py` replays fixture
repositories through the bridge in 16 stages:

1. Rights denied.
2. Unpromoted desk.
3. Backfill, then a rerun that adds zero duplicates.
4. Rights projection.
5. Source mismatch, missing body and wrong date.
6. Model failure, retry and escalation.
7. Retry after a transient failure.
8. Incomplete translation.
9. Material change.
10. Concurrent commit.
11. Unauthenticated source.
12. Private MPS readback, then an identical replay.
13. A pre-cutover public record, not duplicated.
14. Invalid private provenance, held before any model call.
15. Private originals that stay out of the corpus, ledger and report.
16. The record page, with its disclosures.

The receipt is labelled SIMULATED and requires a clean tree at the cited head.
It is not a live or unattended run.

**Open gaps.**

- Dylan Tanzi's October readability feedback is not in the repository. PR #821
  concerns Japan Brief prose, not Vietnamese terminology. The terminology guide
  records the gap; no model was trained or tuned.
- No pass over the 14 real originals has run through the bridge.
- On main, a desk not in `_SOURCE_PROFILES` still receives the China profile.
  Vietnam families are registered explicitly, but the fail-closed target from
  the shared-architecture ruling is not yet general.

**Owner decisions, one per item:**

1. Each family's source-use decision. Generate the exact template with
   `vietnam_source_use.owner_decision_request(family)`. MPS reuse and
   model-transmission terms are not established. Both MOIT families need
   written consent and a robots review.
2. Promote the Vietnam registry entry from shadow.
3. Add the bridge command to an existing scheduled workflow, with
   `VIETNAM_SOURCE_USE_REVIEW_KEY` and model credentials. The MPS
   `--private-custody` step goes in the private runner, with
   `VIETNAM_PRIVATE_PROVENANCE_TOKEN`; only the database post-image returns.
4. Merge #831 and private #20 first, then this PR, which already contains
   #831.
