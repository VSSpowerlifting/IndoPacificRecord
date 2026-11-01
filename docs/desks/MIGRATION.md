# Desk system migration map

The [mandatory standard](README.md) applies to all eight desks now as an owner
instruction. This map records **code boundaries, not live-service certification**.
Baseline inspected: public `e0c0920cc4628a594df3954556739b6f73915691`,
30 October 2026; runtime migrations 1–3 are recorded in the phase receipt below. Recheck
current main, PRs and actual source decisions before implementation.

## Current boundaries and required convergence

| Desk | Existing integration to preserve | Required convergence | Source-specific boundary |
|---|---|---|---|
| China | `pipeline.py`, ordinary article queue, existing collectors and URLs | Adapt the established record path to the common source/component interface without a bulk rewrite | Chinese terminology, source attribution, actual language and publisher-specific rights; no foreign desk inherits these permissions |
| Singapore | MINDEF boundary in `core/mindef_public_boundary.py`, `core/mindef_permissions.py` and pipeline/renderer holds | Express restrictions through the same permitted-component projection; remove scattered special handling only after equal or stronger enforcement | PR #913 merged; retained evidence is private and written link permission covers exactly two URLs; no collection/model/public-text reactivation is implied |
| Korea | `core/korea_corpus_bridge.py`, `processing/korea_shared_queue.py`, original-text and reviewed-English registries | Common checkpoints/admission and a record assembled from permitted components | HWPX fidelity, verified licence scope, source/version exclusions and reviewed English; DAPA metadata permission is separate |
| Philippines | `processing/daily_intake.py`, `processing/daily_runner.py`, AFP/NSC validators, `daily_machine_records`; source-definition pilot merged in PR #928; manual production manifest `desks/philippines/manifest.json` and governed dispatch (runtime migration 3, review candidate) | AFP and NSC registry, lifecycle dispatch, screening and machine-record projection share `core/daily_sources.py` following merged PR #928; admission runs through `pipeline.run_governed_manual_sources` with every other manual source; broader cross-desk convergence remains | English originals remain private; AFP and NSC identities, attribution, policies and exceptional holds remain distinct |
| Indonesia | Same private intake/runner as Philippines, Kemhan validator and Indonesian quality checks; source-definition pilot merged in PR #928; manual production manifest `desks/indonesia/manifest.json` (runtime migration 3, review candidate) | Kemhan uses the same shared registry, caller paths and governed dispatch as AFP/NSC; source-specific evidence/policy stays authoritative | Preserve accepted output, version bindings, Yonif TP 880 hold, source-use decisions and bounded spend; no new paid attempts are authorized |
| Vietnam | `core/vietnam_corpus_bridge.py`, `core/vietnam_daily_handoff.py`, MPS/VPCP source decisions and factual QA | Common transport, checkpoints, admission and allowed-component interface; preserve source-specific document checks | Private originals, issuer versus decision-maker distinction, formal-document evidence, sealed source-use decisions and prior held/settled versions |
| Japan | Isolated shadow RSS/PDF collection under `shadow/jp_mod/`, `core/japan_mod_official_links.py` and public link admission; manual production manifest `desks/japan/manifest.json` registering only `jp_mod_news_ja` (runtime migration 3, review candidate) | Same metadata/component projection and delivery contracts; link admission runs through the governed dispatcher rather than a separate Daily step; no separate Japan publisher | Retrieved/verified news-PDF metadata only under current grant; challenged HTML and all excluded original/model/media uses remain excluded; JCG is separate |
| US reference | Existing `core/us_*` metadata adapters and source-specific release paths | Common source-link identity, projection, admission and delivery | Keep publisher access restrictions and narrow source scopes; this does not authorize a broad US collection program |

These are required destinations for all desks, not optional per-country plans.
Existing adapters and negative tests are retained where they encode real source
differences. A map entry does not permit deactivation of a working path.

## Implementation order and ownership

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

**Not complete:** US reference families (USCC, Treasury, BIS) still have no
manifest/registry entry and keep their separate release workflows; folding them
into the same dispatcher is the next bounded phase. Vietnam governed admission
(PR #933 bridge) is not routed through the dispatcher. `scripts/check_source_liveness.py`
is keyed on `articles`, so manual link/machine-record sources stay `INERT` even
when their `source_run_results` rows are `OK`; the W1 stop condition needs a
liveness check keyed on `source_run_results`. A missing Daily envelope with
activation on is reported as `FETCH_FAILURE` because the public pipeline cannot
distinguish a private-side outage from a run that produced nothing. Tracked DB
rows for the three desks appear only after Daily's migration step; registry-only
source views render without institution names until then (Daily renders after
migration, so the public site is unaffected). Remaining from earlier phases:
China and Singapore migrations, `core/source_publication_contract.py`
convergence, source-component grouping in #895 and model controls in #919. The
qualification/Daily split and runtime migration 3 are review candidates, not
merged or operationally verified releases. The #928 merge did not authorize
deployment or prove a live HTTPS publication. Verify final-head checks and any
operational readback from actual CI and release evidence; do not mark the
remaining work done.
