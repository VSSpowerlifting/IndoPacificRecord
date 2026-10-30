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
| Korea | `core/korea_corpus_bridge.py`, `processing/korea_shared_queue.py`, original-text and reviewed-English registries | Common checkpoints/admission and a record assembled from permitted components | HWPX fidelity, verified licence scope, source/version exclusions and reviewed English; DAPA metadata permission is separate |
| Philippines | `processing/daily_intake.py`, `processing/daily_runner.py`, AFP/NSC validators, `daily_machine_records`; source-definition pilot in PR #928 | AFP and NSC registry, lifecycle dispatch, screening and machine-record projection share `core/daily_sources.py` in #928; broader cross-desk convergence remains | English originals remain private; AFP and NSC identities, attribution, policies and exceptional holds remain distinct |
| Indonesia | Same private intake/runner as Philippines, Kemhan validator and Indonesian quality checks; source-definition pilot in PR #928 | Kemhan uses the same shared registry and caller paths as AFP/NSC in #928; source-specific evidence/policy stays authoritative | Preserve accepted output, version bindings, Yonif TP 880 hold, source-use decisions and bounded spend; no new paid attempts are authorized |
| Vietnam | `core/vietnam_corpus_bridge.py`, `core/vietnam_daily_handoff.py`, MPS/VPCP source decisions and factual QA | Common transport, checkpoints, admission and allowed-component interface; preserve source-specific document checks | Private originals, issuer versus decision-maker distinction, formal-document evidence, sealed source-use decisions and prior held/settled versions |
| Japan | Existing RSS/PDF collection, `core/japan_mod_official_links.py` and public link admission | Same metadata/component projection and delivery contracts; no separate Japan publisher | Retrieved/verified news-PDF metadata only under current grant; challenged HTML and all excluded original/model/media uses remain excluded; JCG is separate |
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

**Runtime pilot PR #928 (integration candidate):** AFP, NSC and Kemhan register
in `core/daily_sources.py`. Actual Daily intake, processing, runner, screening,
fetch and machine-record projection callers consume the shared definitions.
Replaced family branching, repeated prompt allowlists and NSC checks were
removed; private signer `REFS` is intentionally a derived compatibility view.
All six existing released-machine-record projections are byte-identical in the
frozen comparison. Unchanged source-policy bytes, custody, holds, budgets and
activation remain mandatory. The pilot's independent pre-integration CI passed
8,291 tests, isolated rendering/validation and tracked DB/output preservation;
final integrated-head verification is separately required before merge.

**Not complete:** the other six desk migrations, source definitions becoming desk manifests,
`core/source_publication_contract.py` convergence, source-component grouping in
#895, model controls in #919, and trusted exact-revision qualification/Daily
split. Existing Daily checks remain. PR #928 is not a deploy authorization or
proof of a live HTTPS publication. Update this receipt with exact merged SHA and
final-head verification once available; do not mark the remaining work done.
