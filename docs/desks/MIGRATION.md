# Desk system migration map

The [mandatory standard](README.md) applies to all eight desks now as an owner
instruction. This map records **code boundaries, not live-service certification**.
Baseline inspected: public `e0c0920cc4628a594df3954556739b6f73915691`,
30 October 2026; runtime migrations 1–4 are recorded in the phase receipts below. Recheck
current main, PRs and actual source decisions before implementation.

## Research-first governance reconciliation — 4 November 2026

The [canonical source-use standard](../../CONTENT_AND_DATA_RIGHTS.md#7-research-first-source-use-standard)
replaces blanket publisher-letter prerequisites with documented use-specific
legal bases. The [eight-desk account](EIGHT_DESK_OPERATIONAL_COMPLETION_PLAN.md#61-source-use-reconciliation--4-november-2026)
indexes actual policies, supported uses, restrictions and owner decisions.
This candidate reconciles agent/shared-desk/editorial instructions and the
offline typed private-synopsis decision vocabulary; it does not change runtime
source eligibility, manifests, sealed policies, allowed fields, holds or switches.
The synopsis validator retains its owner/source-version checks and all false
dispatch/publication outputs. Its expanded `SYNOPSIS_RIGHTS_BASES` is separate
from the legacy `RIGHTS` imported by Vietnam, so MOIT and existing MPS/VPCP
source-specific limits do not broaden. No shared-engine migration is claimed.

The private governance companion is based on `a3f6299`; founder-approved public
policy merges first, private references second. Final PR/head/check evidence
belongs in the paired PR bodies. Neither merge activates a source or deploys
behavior. The [project-source replacement package](../engineering/PROJECT_SOURCE_UPDATE_PACKAGE_2026-11-04.md)
is prepared separately; ChatGPT Project Sources are not installed by Git changes.

## Current boundaries and required convergence

| Desk | Existing integration to preserve | Required convergence | Source-specific boundary |
|---|---|---|---|
| China | `pipeline.py`, ordinary article queue, existing collectors and URLs | Adapt the established record path to the common source/component interface without a bulk rewrite | Chinese terminology, source attribution, actual language and publisher-specific rights; no foreign desk inherits these permissions |
| Singapore | MINDEF boundary in `core/mindef_public_boundary.py`, `core/mindef_permissions.py` and pipeline/renderer holds | Express restrictions through the same permitted-component projection; remove scattered special handling only after equal or stronger enforcement | PR #913 merged; retained evidence is private and written link permission covers exactly two URLs; no collection/model/public-text reactivation is implied |
| Korea | `core/korea_corpus_bridge.py`, `processing/korea_shared_queue.py`, original-text and reviewed-English registries; [bounded timestamp-admission repair candidate](../engineering/KOREA_DESK_OPERATION.md#current-repair-phase--2-november-2026) | Common checkpoints/admission and a record assembled from permitted components; this repair does not migrate the dispatcher | HWPX fidelity, verified licence scope, source/version exclusions and reviewed English; DAPA metadata permission is separate |
| Philippines | `processing/daily_intake.py`, `processing/daily_runner.py`, AFP/NSC validators, `daily_machine_records`; source-definition pilot merged in PR #928; manual production manifest `desks/philippines/manifest.json` and governed dispatch (runtime migration 3, review candidate) | AFP and NSC registry, lifecycle dispatch, screening and machine-record projection share `core/daily_sources.py` following merged PR #928; admission runs through `pipeline.run_governed_manual_sources` with every other manual source; broader cross-desk convergence remains | English originals remain private; AFP and NSC identities, attribution, policies and exceptional holds remain distinct |
| Indonesia | Same private intake/runner as Philippines, Kemhan validator and Indonesian quality checks; source-definition pilot merged in PR #928; manual production manifest `desks/indonesia/manifest.json` (runtime migration 3, review candidate) | Kemhan uses the same shared registry, caller paths and governed dispatch as AFP/NSC; source-specific evidence/policy stays authoritative | Preserve accepted output, version bindings, Yonif TP 880 hold, source-use decisions and bounded spend; no new paid attempts are authorized |
| Vietnam | `core/vietnam_corpus_bridge.py`, `core/vietnam_daily_handoff.py`, MPS/VPCP source decisions and factual QA; run-result reporting through the governed dispatcher in review candidate #953 | Common transport, checkpoints, admission and allowed-component interface; preserve source-specific document checks | Private originals, issuer versus decision-maker distinction, formal-document evidence, sealed source-use decisions and prior held/settled versions |
| Japan | Isolated shadow RSS/PDF collection under `shadow/jp_mod/`, `core/japan_mod_official_links.py` and public link admission; manual production manifest `desks/japan/manifest.json` registering only `jp_mod_news_ja` (runtime migration 3, review candidate) | Same metadata/component projection and delivery contracts; link admission runs through the governed dispatcher rather than a separate Daily step; no separate Japan publisher | Retrieved/verified news-PDF metadata only under current grant; challenged HTML and all excluded original/model/media uses remain excluded; JCG is separate (shadow only; its index cross-section rows are disclosed exclusions, not identities, per `shadow/jp_jcg/README.md`) |
| US reference | Existing `core/us_*` metadata adapters and source-specific release paths | Common source-link identity, projection, admission and delivery | Keep publisher access restrictions and narrow source scopes; this does not authorize a broad US collection program |

These are required destinations for all desks, not optional per-country plans.
Existing adapters and negative tests are retained where they encode real source
differences. A map entry does not permit deactivation of a working path.

## Implementation order and ownership

**Indonesia recovery candidate, 2 November 2026:** shared intake preserves
deferred retry/QA dispositions; the existing private runner retains parsed
readings with immutable source/version and attempt context in its already
uploaded private handoff directory. No QA, source policy, retry reset, queue
selection, workflow or activation change. The medical v4 record is already
live; newer ADMM-Plus output remains QA-blocked and historical rejected readings
are unavailable. See the [current source checkpoint](../engineering/INDONESIA_SHARED_DAILY_2026-10-27.md#current-checkpoint--2-november-2026-recovery-review-candidate)
for real run/state pins, no-cost replay, release boundary and exact next action.
This candidate does not certify recurring new delivery or replace #950/#954.

1. **Shared source/component and lifecycle integration:** use the already shared
   Philippines/Indonesia lane as the first bounded implementation. Replace real
   hardcoded registration/handoff behavior, preserve accepted output and budgets,
   and route existing public consumers through the same allowed projection.
   Do not merely add unused abstractions. Review public/private changes together
   where essential; do not change live flags as part of the refactor.
2. **Other current paths:** migrate Vietnam, Korea, Japan, US reference, China
   and Singapore in bounded phases against that proven interface. Every desk is
   in scope of the standard; no one is required to migrate all production lanes
   in one PR. Preserve real source restrictions and remove replaced active
   branches after parity, rather than layering a third path over them.
3. **Qualification and delivery separation:** implement trusted exact-revision
   qualification and runtime checks, then replace Daily's redundant development
   suite gate. It may proceed as its own bounded engineering phase; it must not
   use this documentation as evidence that a reusable qualification exists.
   Coordinate the final snapshot renderer and single public writer with source
   migrations; never allow less-tested code or invalid projections to publish.

Only mark a row or phase implemented when real callers use the common mechanism
and the replaced active path is removed or its temporary compatibility need is
explicit. Record the implementation PR/SHA and applicable verification here,
replacing this baseline rather than appending a session diary. A release requires
separate actual authorization and verified deployment evidence. Do not manufacture
completion percentages or launch clocks.

## Coordination at the baseline

- Public PR #895 is open and proposes exact-identity grouping of public record
  components. Inspect and reuse compatible work; do not assume it is merged,
  overwrite its branch or duplicate its proposed `core/public_records.py`.
- Public PR #919 is open for model-task controls. This migration does not change
  incumbents, qualify cheaper models, or take over that PR.
- PR #913 and #920 are merged at this baseline. Their merge is not a fresh
  production/readback certification. Verify the relevant live state only when a
  release task needs it.
- Preserve current private custody refs, signatures, ledgers, accepted Kemhan
  results and all prior model spending/holds. Use the explicitly assigned private
  companion; never copy private source evidence into a public PR.

## Current phase receipt

**Architecture guidance merged:** public PR #925 at `a8f151973b4e1a68103a3f77f5b250e7c3e6ee8a` and private
PR #33 at `f956de3ded4cd23ae52ddcce58055fb125fea8f3`. These are engineering
rules only; no production source/model or workflow flags changed.

**Runtime pilot PR #928 merged (30 October 2026; merge commit `d2feb72b4ca6a7d55700abad0b3659a6785b5cd5`):** AFP, NSC and Kemhan register
in `core/daily_sources.py`. Actual Daily intake, processing, runner, screening,
fetch and machine-record projection callers consume the shared definitions.
Replaced family branching, repeated prompt allowlists and NSC checks were
removed; private signer `REFS` is intentionally a derived compatibility view.
All six existing released-machine-record projections are byte-identical in the
frozen comparison. Unchanged source-policy bytes, custody, holds, budgets and
activation remain mandatory. The pilot's independent pre-integration CI passed
8,291 tests, isolated rendering/validation and tracked DB/output preservation;
pre-integration CI alone is not evidence of a production release or live delivery.

**Runtime migration 2 (official-link read-path candidate):** the actual
readers for Japan MOD, Vietnam ministry official links, Philippines AFP/NSC and
Indonesia Kemhan all request admitted SQLite rows through
`core.regional_official_link_release.read_admitted_link_rows`, one
parameterized read from the existing regional official-link table. The
replaced per-country/per-family SQL queries have been removed.
All source-specific URL, attribution, policy, hold, issuer, proof and
date verification stays with the original readers; this shared transport
does not infer new public components, perform admission or authorize source
reuse. One focused synthetic family-isolation test supplements the
existing real migration/renderer/negative fixtures. This work is a
**review candidate**, not a merged, deployed or live-verified release.

**Qualification/Daily split ([PR #935](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/935), engineering review candidate):** Daily calls
`scripts/code_qualification.py` to compare its actual checkout and environment
with authenticated full main-push run/attempt/job evidence. PR synthetic-merge
assertions cannot certify themselves; reviewed code is qualified on main and
that qualification survives explicitly classified data growth.
Unknown changes, environment drift or unavailable evidence retain the original
full-suite fallback. Runtime migration/schema, DB preservation, reconciliation,
admission, rendering, output validation and publication/readback controls remain.
Offline tests use disposable snapshots and mocked GitHub evidence; final PR CI
must pass before integration. No production workflow or source activation is
authorized by this phase. Initial reuse requires a full successful main-push
offline run with the new workflow version after integration; old runs cannot
certify themselves. The existing offline workflow gains the main-push trigger
and a bounded data-only lane, with no new job or required status.

**Runtime migration 3 (manual production registration and one governed
dispatch; review candidate on `claude/indo-pacific-record-desks-c2452e`):**
`desks/philippines/manifest.json`, `desks/indonesia/manifest.json` and
`desks/japan/manifest.json` register AFP, NSC, Kemhan and the Japan MOD news
feed (`jp_mod_news_ja` only) as **manual** production sources on desks whose
registry status stays `shadow` and non-collecting; `desks/registry.json` now
points at these manifests instead of `shadow/` ones, and `shadow/*/manifest.json`
stay separate and unchanged. `migrations.runner.apply_all` syncs the rows into
`desks`/`institutions`/`sources` at Daily's migration step, so every manual
source has a production source row before the pipeline runs.
`pipeline.run_governed_manual_sources` dispatches every manual source through
one `GovernedAdmission` table (`_governed_admissions()`): the Korea bridge, the
three Daily families through `processing.daily_runner.intake_family`, and Japan
official links through `scripts.admit_japan_mod_official_links.run`. Each writes
a `source_run_results` row with the shared disposition: `SKIPPED_DISABLED`
while the existing owner activation variable (`IPR_PRIVATE_DAILY_ENABLED`,
`JAPAN_MOD_OFFICIAL_LINKS_ENABLED`, `KOREA_DAILY_AUTOMATION_ENABLED`) is absent
or source-use policy withholds unattended release; `OK`, `OK_ALL_DUPLICATES`,
`OK_NO_PUBLICATIONS` or `OK_ALL_FILTERED` (`held: <codes>`) from the receipt;
`ADAPTER_ERROR` carrying only the fixed hold code on a hold, never source text;
`FETCH_FAILURE` when activation is on but no signed envelope arrived;
`LISTING_FAILURE` when `refs/remotes/origin/shadow/jp-mod` is not fetched.
Replaced paths removed: `processing.daily_runner.public_intake` and its Stage 14
call, and Daily's separate `python -m scripts.admit_japan_mod_official_links`
step (that workflow step now only fetches the collector ref; the pipeline step
receives the same activation variables, whose values are unchanged). The public
Daily still fetches nothing from these publishers; only verified link metadata
or signed machine output enters through these rows, and no original document
reaches the public record. `core.viewmodel.SourceView` carries `access_method`
so desk and source pages label these rows "enabled for governed admission".
`scripts/operations_center.assemble` now expects source health rows for every
source with a production registration, so the manual rows are observed
(`source_health_observed`) without the desk being counted as collecting; the
four manual slugs also carry authority tier A in `processing/dedup.py` beside
the other registered sources.
Verification: new `tests/test_manual_source_definitions.py` (registration,
dispatch dispositions, liveness) plus the updated roster/contract tests, the
full offline suite (its only failures also fail on the unchanged base commit:
macOS WAL `-shm` retention in the NSC/Vietnam sidecar tests, `/private/var`
realpath pins, missing Playwright/gpg/docx/evidence-store fixtures),
`scripts/validate_output.py` at the 10 governed warnings, and a local
`site/render.py` inspection (new desk/source wording; the three shadow-era
Japan source pages are no longer rendered). Generated `output/` and the
tracked `pla_watch.db` are deliberately not committed in this change: Daily's
migration step inserts the rows and its render republishes the pages.

**Runtime migration 4 (US reference families through the same dispatcher;
review candidate on `claude/indo-pacific-record-desks-c2452e`):**
`desks/us-indopacific/manifest.json` registers `uscc_press_official_metadata`
and `us_treasury_press_official_metadata` as **manual** production sources
(authority tier A, `official_statement`, institutions `us_uscc` and
`us_treasury`, English) on a desk whose registry status stays `access_blocked`
and non-collecting. `desks/registry.json` points at that manifest and its first
limit sentence now says what the two registrations are; `has_production_records`
stays false, the owner-approved Pacific Command wording is unchanged, and the
shadow DVIDS manifest under `shadow/us_indopacom` stays unwired.
`pipeline._us_metadata_admission` adds one `GovernedAdmission` per family that
reuses the existing importers (`scripts.admit_uscc_official_metadata.run`,
`scripts.admit_us_treasury_official_metadata.run`) and their fixed-code holds
(`USCCAdmissionHold`, `TreasuryAdmissionHold`) unchanged. Dispositions:
`SKIPPED_DISABLED` ("preserved source history not delivered to this run") when
the workflow hands the pipeline no checkout path (`IPR_USCC_SOURCE_CHECKOUT`,
`IPR_US_TREASURY_SOURCE_CHECKOUT`); `LISTING_FAILURE` with
`uscc_source_checkout_unavailable` / `treasury_source_checkout_unavailable`
when the path has no `.git`; `OK` with the receipt's new-record count or
`OK_ALL_DUPLICATES` when it admitted nothing new; `ADAPTER_ERROR` carrying only
the fixed hold code on a hold; any other exception reported by type name only.
No new activation variable exists: the standing owner approval of 15 October
2026 (`docs/engineering/USCC_METADATA_ONLY_PRODUCTION_RELEASE_2026-10-15.md`,
`docs/engineering/US_TREASURY_LIVE_METADATA_ADMISSION_2026-10-15.md`) governs
these admissions exactly as it governed the retired jobs, and the gate is
whether Daily delivered the preserved history. Daily gains one
`continue-on-error` step after the Japan collector fetch that clones
`shadow/uscc-press` and `shadow/us-treasury-press` into `runner.temp` with the
workflow token, and its pipeline step receives the two paths, so one job runs
migrate → verify → clone → admit → render → commit `pla_watch.db output/` →
deploy. Retired from `uscc_verified_official_links_release.yml` and
`treasury_verified_official_links_release.yml`: the `production-metadata-page-only`
writer jobs, their `push`/`workflow_run`/`schedule` (22:17 and 22:31 UTC)/
`workflow_dispatch` triggers and the `daily-update` concurrency claim; each
keeps only its `isolated-render-contract` pull-request rehearsal, which writes
nothing to main, the database or Pages. `us_metadata_migration_preflight.yml`
now also runs for Daily edits. Two operational consequences are deliberate:
admission follows Daily's schedule (nominal 12:23–14:23 UTC crons; GitHub
scheduling delays actual starts by hours) instead of the evening
crons, so an observation committed after Daily is admitted on the next run
(the importers are append-only and idempotent); and the retired jobs'
refusal of a moving source branch is replaced by the importer pinning each
run to the clone's HEAD (`source_commit_sha` in its receipt). BIS is excluded
on purpose: its release is bound by its owner document and
`tests/test_us_bis_verified_official_links_release.py` to a `workflow_run`
event with REST-authenticated run attestation, which this dispatcher does not
reproduce. Both slugs carry tier A in `processing/dedup.py`.
Verification: `tests/test_manual_source_definitions.py` gains
`TestUSMetadataGovernedDispatch` (importer/hold reuse, no activation variable
awaited, missing clone, dry run, receipt statuses with pinned importer
arguments, hold codes without source text, exception type only, family
independence) and the roster now includes `pipeline._US_METADATA_FAMILIES`;
`tests/test_us_metadata_migration_preflight.py` pins Daily's
migrate → verify → clone → pipeline → commit order and the retired writers'
PR-only shape; roster/contract pins moved to 8 desks and 15 registered sources;
the affected modules (832 tests) pass, `scripts/validate_output.py` reports
the 10 governed warnings, and a local `site/render.py` inspection shows the
desks table at 2 configured / 2 enabled for the US desk, the desk page listing
both sources as enabled with no records, and the two new source pages. The
full offline suite result is recorded in the commit message. PR CI then
showed eight workflow guards still pinning the pre-migration registry (no
Japan production manifest; Indonesia and US `manifest` null); they now assert
the registered state (Japan's manifest lists `jp_mod_news_ja` only and no
Coast Guard source, Indonesia's lists `id_kemhan_news` only, the US desk's
two sources are manual and none is Pacific Command, and the
country-research loop records Vietnam as live with records), while Korea's
deliberately refusing guard in `korea_pages_file_only_release.yml` is
untouched. The push-only `release` job of
`country_research_render_only_release.yml` last ran on `main` on 23 October
2026 and failed at the editorial-research gate; commit `13e658653b`, merged
later that day, repaired the Vietnam page for that gate, and the job has not
been retriggered since. Its later page-scope step still pinned headings the
desks no longer render (`Shadow evaluation` for Indonesia and Japan, the
pre-live Vietnam research heading, and the old `8 declared / 3 collecting`
summary wording); those pins now name each desk's current status-panel lane,
the research section by its heading id, Japan's admitted-links lane, and the
desks summary markup (8 declared, 4 collecting), all checked against a fresh
`site/render.py` build of this branch. The Japan Coast Guard live adapter probe
(`japan_jcg_adapter_proof.yml`) fails on every branch since 1 November 2026
for a publisher-side reason unrelated to this branch. Generated
`output/` and the tracked `pla_watch.db` are deliberately not committed:
Daily's migration step inserts the desk/institution/source rows and its render
republishes.

**Not complete:** BIS keeps its separate `workflow_run`-bound release and has no
manifest/registry entry; folding it in needs a dispatcher-side run attestation
or an owner decision to drop that binding. The first scheduled Daily run on the
merged branch must show one `source_run_results` row for each of the nine
registered manual source slugs (Korea, AFP, NSC, Kemhan, Japan MOD, USCC,
Treasury, Vietnam MPS and VPCP). The two U.S. families require an
`OK`/`OK_ALL_DUPLICATES` receipt or truthful `LISTING_FAILURE` after a failed
clone. Under runtime migration 5 (#953), the Vietnam families must report
their actual signed-handoff and bibliographic-collector outcomes rather
than the previous artificial `SKIPPED_DISABLED` "no governed admission"
disposition. The Vietnam admission steps still run separately, because the
signed handoff replaces the DB atomically: the governed dispatcher records
their outcomes, rather than repeating admission. The first real scheduled
Daily cycle after integration must verify each family and the failure/quiet
distinction; code integration alone does not certify live recurrence.
MOIT stays unregistered.
`scripts/check_source_liveness.py` is keyed on `articles`, so manual
link/metadata/machine-record sources stay `INERT` even when their
`source_run_results` rows are `OK`; the W1 stop condition needs a liveness
check keyed on `source_run_results` (the shared Daily families now have one:
see "Shared Daily collector heartbeat" below). A missing Daily envelope with activation
on is reported as `FETCH_FAILURE` because the public pipeline cannot
distinguish a private-side outage from a run that produced nothing. Tracked DB
rows for the four manual-source desks appear only after Daily's migration
step; registry-only source views render without institution names until then
(Daily renders after migration, so the public site is unaffected). Remaining
from earlier phases: China and Singapore migrations,
`core/source_publication_contract.py` convergence, source-component grouping
in #895 and model controls in #919. The qualification/Daily split and runtime
migrations 3 and 4 are review candidates, not merged or operationally verified
releases. The #928 merge did not authorize deployment or prove a live HTTPS
publication. Verify final-head checks and any operational readback from actual
CI and release evidence; do not mark the remaining work done.

**Runtime migration 5 — Vietnam source-run reporting (PR #953; 5 November
2026 review candidate):** Reconciled the draft Vietnam-only reporting phase
against merged #950 and current main. MPS reports the signed handoff's
versioned per-family disposition; VPCP combines its own bibliographic
collector's run record with its handoff outcome, with failures never hidden
by successful or quiet peers. No ingestion step, issuer, policy, schedule,
activation or publisher source changed. Required final-head CI and genuine
post-integration scheduled outcomes remain separate evidence.

**Shared private-output fetch recovery ([PR #954](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/954), review candidate):**
*Status 3 November 2026:* merged at `dc7beaa76c` (16:54 UTC); post-merge CI
passed. Scheduled Daily [41705243710](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41705243710)
processed and published on 3 November: AFP/NSC/Kemhan each admitted zero with
no holds; shared fetch failures were zero. This is authentic authenticated
duplicate-replay evidence, not new-record admission or proof of every recovery
case. The Health gate failed on Vietnam article recency after delivery. Pages
build [41709726446](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41709726446)
succeeded for `9e729b827feb4f1d7035613b2d3b8329f0cd93be`. Independent HTTPS
readback of `vietnam.html` on 3 November matched its deployed SHA-256
`e34d488b0abcd7c22a6b5f2500531bf086d3cdfed72e5109204f4f013b3fe958`.
Later guard-skipped Daily runs add no operational evidence. #950 originally
merged #954 main in `2dfaa0b4ec`.
AFP/NSC/Kemhan fetching removes stale invocation-local inputs before refresh,
installs valid JSON objects atomically (including isolated rejection of deeply
nested JSON), and reports failed-family counts to the existing post-delivery
Health gate. Authentication, source/version/policy checks and accepted DB rows
remain in the existing admission path; no rights, QA, retries or spending change.

The 3 November integration combines original #954 head
`fc965dbe6c9165035bd638fef1cc2f609a588a48`, correction `38a39e0` and main
`3d78978abe2d1234db4ce1c2382cd843b2cdf530`, preserving #964 and #965 (merged as
`20957b582c23439543830cf29a01ba5e2c574940`). No #950/#953 changes are included.
Synthetic tests cover partial AFP/NSC fetch through authenticated admission,
accepted-row preservation, duplicate replay, quiet Kemhan input and the actual
Health shell. The subsequent production run above closes the authentic MAC/duplicate-replay
gap; new-record admission and other recovery cases remain separate claims.

**Shared Daily collector heartbeat (issue #673, review candidate, 4 November 2026):**
*Problem.* The signed Daily packet is exactly `{schema, family, source_repository,
source_ref, processor_commit, records, held}`: it carries no collection time, and
public admission applies no freshness bound. A stopped private collector therefore
yields the same envelope and the same `ok_all_duplicates` as a publisher with
nothing new, the shared-Daily `source_run_results` rows have empty
`started_at`/`completed_at`, and `check_source_liveness.py` (which reads
`sources LEFT JOIN articles`) can only call these families `INERT`. Keying
liveness on admission recency is rejected: NSC last posted in July and would be
permanently red. This is the gap `docs/desks/README.md` §4 forbids ("quiet source
... missed cycle ... must remain distinguishable").

| | **A. Signed collection time in the packet** | **B. Read private custody metadata from the public side (implemented)** |
|---|---|---|
| Signal | `collected_at` inside the MAC'd packet | Committer date of the head commit of the family's `archive/<…>` custody branch (`SOURCES[family].custody_ref`) |
| Public files | `processing/daily_intake.py` (packet key set, `admit`), `core/daily_sources.py`, `processing/daily_runner.py`, `pipeline.py` (record it), `scripts/check_source_liveness.py`, tests | `scripts/fetch_daily_machine_outputs.py`, `processing/daily_runner.py`, `pipeline.py`, `scripts/check_source_liveness.py`, tests; no workflow or secret change |
| Private files | the processor's `sign_outputs` call path and the collector/processor workflow that supplies the time (private checkout was not available; exact files to be confirmed by the private-repo owner), plus a schema bump and a coordinated rollout | none |
| Trust | tamper-evident (MAC) | unsigned, read with the existing CI token; forging it can change only a monitoring result, because `admit` never reads it |
| Closes | collector stall **and** processor/signing stall (if the time is stamped at signing) | collector stall |
| Does not close | a collector that runs but fails to preserve (the custody commit still lands) | processor/signing stall while the collector keeps committing; a collector that runs but fails |
| Needs founder authorization | yes: private repo, signing contract/schema, secret/rollout | no (public, read-only, no new secret); activation and merge/deploy are still separate |

*Recommendation: B now, A only if processor stalls prove to matter.* B is entirely
inside the shared lifecycle, changes neither keys nor signing nor the private
repo, and is testable offline. The brief's premise needs one correction: B does
read private-repo *metadata* (one `gh api .../commits?sha=<ref>&per_page=1`
call per active family, no content), but it modifies nothing there.

*Implementation (B).* The fetch step writes an unsigned sidecar
`<family>.collection.json` (`{"collector_last_run_at": "<UTC stamp>"}`) beside the
envelope, deleting any prior one first. `pipeline.GovernedAdmission.heartbeat`
reads it and `run_governed_manual_sources` records it as that run's
`source_run_results.completed_at` for every outcome of an active admission
(OK, duplicates, held, `FETCH_FAILURE`); inactive or dry-run admissions record
none. `check_source_liveness.py` reads the latest row per source: a manual family
with a heartbeat no older than `--heartbeat-max-days` (default 3, a founder-tunable
value; `silence_threshold_days` is deliberately not reused because it measures
publisher silence) is `HEALTHY` however old its last article, an older one is
`UNHEALTHY`, and a family with no heartbeat (not activated, disabled, date
unreadable) is judged exactly as before. An unreadable heartbeat prints a
`::warning` annotation and is not counted in `failed_families`.

*Semantics to preserve.* For governed manual rows, `completed_at` means "the
private collector's last preserved attempt (unsigned)", not this process's run
time. `storage/db.py` `get_last_success_by_source`, `scripts/source_health_report.py`
and `scripts/operations_center.py` read `completed_at` for last-collection
displays and will now show it for these families. Checked: they only take
`MAX(completed_at)` (no duration arithmetic, so the still-empty `started_at`
is harmless), `FETCH_FAILURE` rows are excluded from "last successful
collection", and `record_source_run_result` stores the value untouched (a
round-trip test covers dispatch, recorder, migrated table and `heartbeats()`).

*Needs founder decision or check (nothing here is done by this change):*
(1) whether to authorize Option A, a private packet/signing/schema change, to
also cover processor stalls; (2) confirm that the CI read token
(`IPR_DAILY_OUTPUT_READ_TOKEN`/`IPR_PRIVATE_VAULT_READ_TOKEN`) can read commits on
the `archive/*` branches (verified only with the owner's admin token; if not, the
warning appears and behaviour is unchanged); (3) the 3-day staleness value;
(4) activation of the private Daily lane; (5) merge and deploy. Vietnam,
Indonesia and DAPA are untouched; `id_kemhan_news` is covered generically if its
policy is enabled.

**#950 integration checkpoint — 3 November 2026:** founder explicitly authorized
this integration and its ordinary release, conditional on final qualification.
The qualified `520d55d094de66c345f5c13b4652a4b3acf4699d` candidate was merged
locally with main `9095590fa30baccbbaca4bb4f7c312e5591cabba` without conflicts.
Only current production DB/output and run-state advances were incorporated;
no dispatcher, rights, source activation, spend or editorial changes were
needed. One publication-coordination correction removes the country render-only
workflow from its own push trigger: its seven-file publication would otherwise
link to newly registered source pages that it does not stage. Catalog changes
and explicit exact-main manual releases remain supported. Daily owns the full
source-page publication. Final CI at `684a4376a2` ran 8,566 tests and failed
on two corpus-growth fixture defects: the snapshot-race mutation deleted only
publication-hidden rows, and a source's factual participant quantity collided
with the current original-text count. The repair mutates actual visible records
and proves count/fingerprint drift, while distinguishing explicit participant
quantities from archive totals without exempting files or numeric values.
Production code, templates, source policy, DB and output remain unchanged by
that repair. Final revision/check and release evidence belongs in
[PR #950](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/950).
The first genuine scheduled Daily on the integrated revision must still prove
nine manual-source rows and source-specific dispositions, accepted-data
preservation and DB-to-public delivery. Guard-skipped runs do not qualify.
Do not force an additional paid Daily cycle to replace that evidence. #953
remains outside this phase; its integration requires a new bounded session.

**China Desk interim source-use hold (PR #980 merged at `7cc77270`; separately inactive unless configured):**
`core/china_source_use_hold.py` is one exact-`"true"`, call-time switch,
`IPR_CHINA_SOURCE_USE_HOLD`, inert when unset. Enabled, it holds the host
sources `global_times_mil`, `mod_china` and `pla_daily` (never by byline) at
every active route: the source loop (no adapter, no request; the existing
`SKIPPED_DISABLED` with a `source-use hold:` detail, a non-failure), the
`insert_article` and `insert_articles_atomic` write seams (both raise, so
neither can read as a duplicate; the atomic batch is refused before any write
transaction opens), the
relevance screen, the daily analysis queue including stored backlog, headline
translation candidates (also the China title batch scripts that call them), the Sunday and weekly briefs writers' evidence selection, and the
operator scripts `backfill_unscored.py`, `backfill_translations.py` and
`rescreen_desk.py`. It writes no processing state, flips no
`sources.enabled`, and removes, rewrites or regenerates nothing: the 1,513
existing records, their text, hashes, dates and source identities,
`pla_watch.db`, Git history and the private backup are unchanged, and
rendering is untouched. `xinhua_mil`, `china_mil_online` and all other desks
are unaffected.

`china_title_completion_batch.yml` runs from main but checks out the separate
`ops/china-title-completion-20261018` branch, which predates the hold, so an
env mapping alone protects nothing there. Its job is therefore gated from
main: `batch` runs only when `vars.IPR_CHINA_SOURCE_USE_HOLD != 'true'`, and a
`hold-notice` job (no checkout, key or push) runs instead. The ops branch's own
copy of the workflow keeps its `github.ref == 'refs/heads/main'` guard, so it
cannot be dispatched from that ref. Actions compares strings case-insensitively
while the Python switch requires exactly lowercase `true`; set the variable to
exactly `true`. Every workflow that holds `secrets.ANTHROPIC_API_KEY` must map
the switch or be listed in `tests/test_china_source_use_hold.py` with a reason.

Fail-closed identity: with the hold enabled, a row whose `source_slug` is
absent, null or empty counts as held at the Briefs writers and the relevance
model boundary, so unknown provenance cannot bypass it. Integration
candidate: #979 composed onto #950 (merge order #950, then #979); the held
slugs are not in #950's governed-admission families, and the hold check
precedes its manual dispatch in `pipeline.py`. No new policy packet.

All three adapters retrieve full article bodies, so the hold is a
whole-collection hold, not a metadata-only mode. Whether metadata-only
discovery would be permitted, and for Global Times the difference between
restrictions on automated collection, on linking and on derived content,
awaits the #978 owner decisions.

Closed or inactive, no change needed: `scripts/generate_pla_watch.py` is
refused unconditionally by `refuse_predecessor_authoring()` and no workflow
calls it. Residual risk: an operator script written later that reads stored
text and calls a model without going through the covered seams; content
already public in the database and in Git history is untouched by design.
Nothing here adopts a publisher grant or restriction, activates the hold, or
changes the live site. Activation, legacy-record treatment and publisher
correspondence remain separate founder decisions.
