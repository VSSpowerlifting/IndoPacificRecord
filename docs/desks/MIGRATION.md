# Desk system migration map

The [mandatory standard](README.md) applies to all eight desks now as an owner
instruction. This map records **code boundaries, not live-service certification**.
Baseline inspected: public `e0c0920cc4628a594df3954556739b6f73915691`,
30 October 2026; runtime migration 1 is recorded in the phase receipt below. Recheck
current main, PRs and actual source decisions before implementation.

## Current boundaries and required convergence

| Desk | Existing integration to preserve | Required convergence | Source-specific boundary |
|---|---|---|---|
| China | `pipeline.py`, ordinary article queue, existing collectors and URLs | Adapt the established record path to the common source/component interface without a bulk rewrite | Chinese terminology, source attribution, actual language and publisher-specific rights; no foreign desk inherits these permissions |
| Singapore | MINDEF boundary in `core/mindef_public_boundary.py`, `core/mindef_permissions.py` and pipeline/renderer holds | Express restrictions through the same permitted-component projection; remove scattered special handling only after equal or stronger enforcement | PR #913 merged; retained evidence is private and written link permission covers exactly two URLs; no collection/model/public-text reactivation is implied |
| Korea | `core/korea_corpus_bridge.py`, `processing/korea_shared_queue.py`, original-text and reviewed-English registries; [bounded timestamp-admission repair candidate](../engineering/KOREA_DESK_OPERATION.md#current-repair-phase--2-november-2026) | Common checkpoints/admission and a record assembled from permitted components; this repair does not migrate the dispatcher | HWPX fidelity, verified licence scope, source/version exclusions and reviewed English; DAPA metadata permission is separate |
| Philippines | `processing/daily_intake.py`, `processing/daily_runner.py`, AFP/NSC validators, `daily_machine_records`; source-definition pilot merged in PR #928 | AFP and NSC registry, lifecycle dispatch, screening and machine-record projection share `core/daily_sources.py` following merged PR #928; broader cross-desk convergence remains | English originals remain private; AFP and NSC identities, attribution, policies and exceptional holds remain distinct |
| Indonesia | Same private intake/runner as Philippines, Kemhan validator and Indonesian quality checks; source-definition pilot merged in PR #928 | Kemhan uses the same shared registry and caller paths as AFP/NSC following merged PR #928; source-specific evidence/policy stays authoritative | Preserve accepted output, version bindings, Yonif TP 880 hold, source-use decisions and bounded spend; no new paid attempts are authorized |
| Vietnam | `core/vietnam_corpus_bridge.py`, `core/vietnam_daily_handoff.py`, MPS/VPCP source decisions and factual QA | Common transport, checkpoints, admission and allowed-component interface; preserve source-specific document checks | Private originals, issuer versus decision-maker distinction, formal-document evidence, sealed source-use decisions and prior held/settled versions |
| Japan | Existing RSS/PDF collection, `core/japan_mod_official_links.py` and public link admission | Same metadata/component projection and delivery contracts; no separate Japan publisher | Retrieved/verified news-PDF metadata only under current grant; challenged HTML and all excluded original/model/media uses remain excluded; JCG is separate (shadow only; its index cross-section rows are disclosed exclusions, not identities, per `shadow/jp_jcg/README.md`) |
| US reference | Existing `core/us_*` metadata adapters and source-specific release paths | Common source-link identity, projection, admission and delivery | Keep publisher access restrictions and narrow source scopes; this does not authorize a broad US collection program |

These are required destinations for all desks, not optional per-country plans.
Existing adapters and negative tests are retained where they encode real source
differences. A map entry does not permit deactivation of a working path.

## Implementation order and ownership

**DAPA source-use qualification, 3 November 2026:** five authentic preserved
HWPX versions passed integrity/structure checks; three stored originals replay
exactly. All five article captures carry text-only Type 0 notices, but applying
that scope to DAPA-authored HWPX prose and authorizing substantive source uses
still need the founder decision specified in the
[Korea operation qualification](../engineering/KOREA_DESK_OPERATION.md#dapa-original-source-qualification--3-november-2026).
`156786687` is the proposed first candidate. Existing four public DAPA links,
private custody, failed-batch and semantic holds remain intact. No adapter,
model call, common dispatcher change or activation occurred; #950 stays separate.

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

**Not complete:** the other six desk migrations, source definitions becoming desk manifests,
`core/source_publication_contract.py` convergence, source-component grouping in
#895 and model controls in #919. The qualification/Daily split above is a review
candidate, not a merged or operationally verified release. The #928 merge did
not authorize deployment or prove a live HTTPS publication.
Verify final-head checks and any operational readback from actual CI and release
evidence; do not mark the remaining work done.

**Shared private-output fetch recovery ([PR #954](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/954), review candidate):**
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
Health shell. Genuine envelope equality with six accepted records is supporting
evidence only: successful authentic MAC/admission replay remains unverified
without an authorized isolated key-bearing validation path. Final exact-head
checks and the remaining gap belong in #954. Stop at engineering review; no
merge, deployment, activation or paid processing is authorized by this phase.
