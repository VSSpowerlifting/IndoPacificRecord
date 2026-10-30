# Shared desk system — mandatory architecture

**Owner decision: 30 October 2026. Applies to every current and future desk:**
China, Singapore, Korea, Philippines, Indonesia, Vietnam, Japan and the US
reference desk. Applies in the public repository and the explicitly assigned
private evidence companion, to Codex, Claude and other coding agents.

This is the authoritative desk engineering standard. It replaces the earlier
shared-Daily *aspiration* with a mandatory implementation contract. Older desk
plans, examples and launch procedures cannot authorize a competing design.
Specific source-use decisions, genuine evidence, spending limits, access
restrictions and human editorial approvals remain authoritative in their scope.

**Adoption is not migration.** This documentation change does not consolidate
the running code, qualify a revision, grant source rights, activate a collector,
increase spending, merge another PR or deploy. Existing verified paths remain
in service until a replacement has passed the applicable checks. The bounded
[migration map](MIGRATION.md) distinguishes those paths from the required design.

## 1. Sources own evidence and policy; desks are views

A desk groups sources and records by editorial scope. A country name must not
select a separate storage, signing, retry, admission or publishing subsystem.
Independent collectors, schedules, extraction formats, languages, institutional
attribution, licences and factual checks remain source-specific where needed.

Each source has one validated definition referencing:

| Concern | Required reference or value |
|---|---|
| Identity | Stable source family, desk membership, publisher and issuer rules |
| Collection | Adapter, official discovery routes, access contract and cadence |
| Custody | Evidence location, source version/hash rule and authenticated readback |
| Processing | Explicit language, screening/analysis profile and prompt compatibility |
| Source use | Actual decisions for retention, model input and each public component |
| Limits | Existing spending reservations, per-run bounds, retries and exclusions |
| Activation | Collection, processing and publication switches; separate from permission |

Use existing manifests, registries and decision files while implementing this
interface. Reference an authoritative permission record; do not copy its grants
into several independently editable files. Register sources that currently lack
a normal desk manifest through an explicit reviewed migration, never by silently
making a shadow manifest discoverable. Do not create an unused parallel registry.

Display status, source rights and runtime activation are distinct. A `live` or
`shadow` label grants nothing. Report collection health, available public
components and publication freshness from actual evidence; do not make agents
reconcile multiple hand-maintained narratives to determine what may run.

## 2. One logical record, with permitted components

The logical record key is an exact source-family/publication identity. Preserve
immutable source versions and their evidence bindings. Separate publications
and publishers remain separate even when their titles or subjects match.

A record may have an official link, original title/text, translation, machine
explanation or reviewed analysis. Each component is optional and independently
governed. An English explanation does not require a public original. A link-only
record is a valid limited product and must not masquerade as a full-text record.
Private evidence stays in its authorized custody. A public record contains only
permitted fields and safe provenance, never a convenience copy of restricted
input. Public DB/download/export/search/feed/HTML surfaces share that boundary.

This is one **logical interface**, not a requirement for a new universal table
or a bulk database rewrite. Normalize existing stores through the existing
contracts first. Keep stable public URLs, record IDs, citations, source hashes
and historical approvals. Do not regenerate accepted model output merely to
change its wrapper. Group components only by verified exact identity; ambiguous
bindings hold rather than merge by title similarity.

All reader surfaces consume the same permitted record projection: record pages,
desk lists, Archive, search, counts and freshest dates. Source-specific loaders
may adapt legacy data during migration; templates must not become independent
country-specific publication engines. Machine output remains clearly labeled;
bylined Briefs and other human-controlled editorial products retain approval.

## 3. One lifecycle and admission mechanism

Extend the existing Analyzer, processing-state, custody, projection and renderer
modules. Do not add another engine, queue service, orchestration platform or
authentication framework to implement this rule.

The common lifecycle owns source-version deduplication, processing checkpoints,
spend reservations, retries, holds, authenticated handoff, public projection,
atomic admission and publication/readback receipts. Source adapters own honest
access and extraction. Profiles own language, terminology, relevance and factual
checks. Existing distinct permissions and narrower budgets must survive intact.

Common implementations must provide:

- **Versioned work:** distinguish publication identity, evidence version,
  processing/profile version and public component. A retry never resets a held
  version's budget. A source revision cannot overwrite historical evidence or
  automatically reopen a genuine accuracy/rights hold. Handle allowed new
  versions under the source's standing policy with explicit supersession rules.
- **Checkpoints:** resume an unfinished permitted stage without repeating paid
  work already accepted. Record model/prompt provenance and actual attempts.
  Preserve failed output privately when needed for diagnosis; never leak it.
- **Bounded retries:** share the mechanism, preserve each source's limits.
  Transient failures can retry within bounds; exhausted or substantive holds
  need an actionable reason. A permission grant is not a retry reset.
- **One handoff contract:** share envelope authentication, version binding,
  replay/idempotency checks and public-field validation. Keep source-specific
  evidence verification as adapters and retain the existing trust separation,
  key scopes and source-specific negative tests. Do not collapse secrets merely
  to reduce configuration. Never expose private bodies through a common type.
- **Compatibility:** define producer/consumer prompt and schema compatibility
  once in the registered contract, not independent executable allowlists.
  Unknown sources or incompatible versions cannot default to China's profile.
- **Isolation:** hold the affected source, version or component. Continue
  unrelated eligible work where safe. Shared integrity, secret exposure,
  invalid public projection or unrecoverable transaction failures still block
  the affected release. `continue-on-error` without an explicit disposition
  and failure signal is not isolation.

Once standing source-use, quality, spending and activation decisions permit
routine machine records, eligible records publish unattended. Do not invent
per-record owner review, new ministry-correspondence prerequisites or seven-
permission forms. Respect actual access/terms and unresolved source-use limits.
Translate only when needed; English originals do not acquire a translation job.

## 4. Qualify code separately from delivering data

The required design has three responsibilities:

| Responsibility | What it must prove |
|---|---|
| Code qualification | Applicable PR checks for the exact executable/configuration revision, dependencies, schema and workflow environment; source replay where relevant |
| Routine ingestion | Current source/policy/activation eligibility, authentic evidence, version binding, schema integrity, deduplication, bounded cost and recoverable state |
| Public delivery | Render from the final admitted snapshot, validate permitted fields and site invariants, serialize publication, verify deployed output, then record success |

Do not rerun the whole development suite for every data-only update when valid
qualification for the same executable environment can be verified. Qualification
reuse must bind the executable/configuration inputs, dependency/runtime identity,
required checks and trusted CI evidence; data-only commits are not new code.
Missing, failed, incompatible or unverifiable qualification fails closed to
qualification, never to deployment. Code, schema, source-use, executable config,
workflow and dependency changes invalidate affected qualification. Never run
untrusted PR code with production secrets to manufacture a receipt.

**Transition:** Daily currently runs its full offline suite. Until a reviewed,
tested exact-revision qualification mechanism replaces that gate, continue to
run it. This standard authorizes the structural change, not deleting a check
without its replacement. The current CI contract is described in
[the acceptance policy](../engineering/CI_AND_DESK_ACCEPTANCE_2026-10-18.md).

Tests use isolated databases and frozen source fixtures. Production checks
assert invariants, not an exact ever-growing record list. A valid newly
published record must not break the next run. Rights, unsafe-write, source
identity, duplicate/version, spending and disclosure regressions remain tested.
Keep applicable checks in the existing suite; do not add a workflow per test.

Collection/custody success and public-delivery success have separate receipts.
Preserve authentic captures if processing or rendering fails. Preserve the last
verified site on failed candidate validation. Render after final reconciliation,
not against a pre-rebase database. One coordinated writer owns public DB/site
publication; independent collectors need not become a single giant job.
Quiet source, disabled source, access refusal, missed cycle, processing hold and
deployment failure must remain distinguishable in operational signals.

## 5. Repository ownership and removal rules

| Existing location | Responsibility under this standard |
|---|---|
| `desks/`, `core/manifests.py`, `core/registry.py` | Source registration and desk membership; consolidate references, preserve current loader behavior until migrated |
| `scraper/`, `core/collection/`, private collectors | Source access, extraction, evidence and custody adapters |
| `analysis/`, `processing/` | Shared model tasks and lifecycle; source profiles/checks are extensions |
| `core/source_publication_contract.py`, existing admission modules | Common allowed-component projection and authenticated admission; legacy wrappers retire as parity is proved |
| `storage/`, `migrations/` | Atomic storage, version bindings and reviewed compatibility migrations |
| `site/render.py`, existing record/Archive/search builders | One public record interface and common templates |
| `.github/workflows/` | Thin orchestration of qualified code and delivery; separate collection when justified |
| `docs/desks/` | This standard, one current migration map and the bounded change template |

Do not move files for cosmetic uniformity or build empty target directories.
Each implementation must route real callers through the shared replacement and
remove the replaced active path, or name the precise compatibility reason it
must remain temporarily. Preserve immutable evidence and historical source
decisions. A date-stamped recovery script is not a template for future onboarding.
Retire workflow triggers only after checking real callers, schedules, required
statuses, source custody and the supported recovery path. Do not delete useful
negative tests or weaken enforcement in the name of cleanup.

## 6. Completion, exceptions and agent stop condition

A new source normally requires an adapter, one source definition referencing its
decisions, an explicit profile when processing is permitted, and source-specific
fixtures. A new lifecycle/signing/queue/rendering system is an architecture
exception: explain why the common mechanism cannot support it and obtain an
explicit owner decision before introducing that competing system. Routine
implementation choices inside the common design need no additional approval.

Use [the change template](CHANGE_TEMPLATE.md) to scope one coherent engineering
phase, not to create a second approval process. During implementation use focused
checks; run mandatory CI on the final exact revision. Establish authentic
source-to-live readback and a representative failure/recovery when release is
authorized. State configured follow-on automation separately from observed runs.
No arbitrary 7/30-day launch waits, expanding historical backfill, serial
rehearsal programs or routine human machine-record approvals.

Stop when the assigned phase is verified, with one reviewable PR and an essential
private companion only where needed. A docs phase ends at an honest reviewed
contract; a runtime migration ends at routed callers, parity and retired
duplication; an authorized release ends at verified public results and the
unattended path. Never substitute one finish line for another. Preserve the next
action in repository state and use a fresh coding session for a substantial
next phase. Do not sweep in unrelated bugs, deployments or features.
