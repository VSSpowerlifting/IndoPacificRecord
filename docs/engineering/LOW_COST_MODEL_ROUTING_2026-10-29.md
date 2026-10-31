# Shared task-model routing — qualification complete; replacement not qualified

31 October 2026 merge preparation. PR #919 separates task-model selection,
accounting and provenance from the evaluated prompts and acceptance rules.
**Incumbent production behavior is retained by default. No task is qualified for
replacement.** The revised-prompt trial below remains pinned to its historical
code and inputs, including factual failures and excessive Sonnet holds. Passing
engineering CI does not approve either model or the candidate fidelity rules.
Sonnet also produces errors; retaining it does not certify its factual accuracy.
No new paid calls, activation, framework, merge, deployment or publication is
part of merge preparation. Stop at the verified review PR.

## Concrete task configuration

| Task | Retained production model | Configuration |
|---|---|---|
| Relevance | `claude-haiku-4-5-20251001` | `RELEVANCE_MODEL` default |
| Full translation | `claude-sonnet-4-6` | `ANALYSIS_MODEL` default; `TRANSLATION_MODEL` empty |
| Summary / desk summary, flag and event type | `claude-sonnet-4-6` | `SUMMARY_MODEL` empty |
| Separate China categories and flag | `claude-sonnet-4-6` | `CATEGORIZATION_MODEL` empty |
| Optional task fallback | Disabled | `FALLBACK_MODEL` empty |
| Evaluated prompts / fidelity acceptance rules | Inactive | `MODEL_FIDELITY_CANDIDATE_ENABLED` unset (`false`) |

Empty task overrides inherit `ANALYSIS_MODEL`. Title-only translation keeps its
existing model and independent activation. No repository variable was changed.
No task set passes factual qualification, so **qualified/realized production
savings are 0%** and cost per factually accepted record is not established.

## Existing path and implementation

Collectors, custody and source-use policies remain upstream of the existing
queue. `pipeline.py` calls the shared `Analyzer.analyze_record`, stores partial
relevance for retries, and persists completed analysis through `storage.db` before
`site/render.py`. China translates then summarizes and categorizes in parallel.
English desks skip translation; other desks keep their language profiles,
combined summary/flag schemas, terminology, QA and independent activation gates.

The existing Anthropic Messages interface supports independent task models and
optional task-local fallback. Context is copied to concurrent workers, and actual
attempted analysis models are retained in the existing `model_id` TEXT field.
Relevance retains its task/model usage rows. Source-specific spend wrappers
validate the resolved model before dispatch. No new provider, corpus, renderer,
DB schema or routing framework was added.

With empty overrides and fallback, request content, model, tools, sampling,
caching and acceptance retain the pre-PR base `95c53909cf` contract. China uses
unchanged `v1` prompt builders. Existing translation-value, relevance-value,
truncation/refusal, fatal-account, private evidence, source-specific quality and
budget checks remain. Incumbent China category filtering/coercion and retention
of a successful summary after category failure are preserved. These compatibility
claims do not certify the quality of incumbent accepted text.

Model overrides and fallback do not enable new prompts or fidelity rules. Only
`MODEL_FIDELITY_CANDIDATE_ENABLED=1` explicitly selects the unqualified candidate;
it defaults off and is not forwarded by Daily. The existing `analysis/fidelity.py`
preserves the evaluated `v2-source-fidelity` instructions and narrow deterministic
checks, strict China category rejection and category-failure completion hold.
Candidate message digests match evaluated revision `d731c620a0`. The trial found
missed factual errors and excessive holds; no candidate rule is approved for
production by this PR. An offline opt-in grants no source, spending or activation
authority. Existing source-specific safeguards are independent of this flag.

An enabled fallback can attempt a rejected task once on a different configured
model, using the same prompt and acceptance mode. Fatal account errors propagate.
Existing China JSON-summary repair remains inside each attempt. The incumbent
SDK retry configuration is restored: the general client does not override SDK
transport retries. Telemetry counts application calls and returned usage, not
unobservable SDK attempts or charges without returned usage. Existing bounded
private-source clients still disable SDK retries and retain their spend checks.
The frozen paid trial used explicit zero transport retries at its pinned revision;
its actual-cost evidence is historical and is not recharacterized as production
measurement. Exhaustion reaches the incumbent partial-result/retry/hold behavior.
Production retains whole-record retries, not durable per-task checkpoints;
exactly-once billing across an uncertain process crash is not guaranteed.

Haiku uses the existing disabled-thinking/high-effort request configuration.
Exact evaluated Luna ID was `gpt-6-luna` through Responses/native JSON, not an
Anthropic alias. Its prior factual failures remain; no new provider research or
Luna generation was performed. Existing provider request/pricing references are
[Haiku migration](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)
and [pricing](https://platform.claude.com/docs/en/about-claude/pricing).

## CI failures resolved before paid dispatch

Initial CI [40961085191](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40961085191)
at `22f54b0f0b` failed eight assertions after 8,263 tests. One was introduced here:
the exact workflow-environment test lacked the new model variables. It now checks
both the approved key set and exact mappings/defaults. Seven failures reproduced
on archived original base `58b35065`: 59 selected tests, seven failures, while the
old environment contract passed. They concern moving census fixtures,
Philippines explanation expectations and authored-versus-released machine prose.

With the existing repair owner's confirmation, #918 commits `213eb1a508` and
`a90cb8d9c5` were reused with authorship, including its PR-only Ubuntu runner pin.
No competing repair or weakened check was substituted. Main `301bb766e2`'s newer
metadata admissions were retained. Combined implementation `5b0eef1ab27582117522442c43a01dcc6feb9fa6`
passed mandatory CI [41011436993](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/41011436993)
**before any new paid dispatch**: 8,267 tests, 15 skips, Chromium, isolated
production render and validator with 10 governed warnings, unchanged tracked
DB/output and no SQLite sidecars. Final documentation changes require the PR's
checks at their own exact head; earlier-head success is not final-head evidence.

## Frozen revised-prompt comparison

Ben authorized one **new $3 TOTAL** allowance for both models, all failures,
repairs and fallback, with a durable cumulative ledger. Earlier allowances were
not reused. Evidence stays private at
`/Users/benjaminyang/.codex/private/ipr-task-model-qualification-20261030-2c9e/`:
`manifest.json`, `source-review.json`, `results.json`, `review.json`,
`budget.sqlite`, `usage-audit.json`, `restart-receipt.json`, and `REPORT.md`.

Manifest SHA-256:
`da5e924f2570a0571195823c814170f53c20fc6f80e98de4bc6b005762b036f6`.
It pins code, exact inputs and harness before generation. Ten frozen China
challenges: 5655, 5754, 5748, 5652, 5755, 5742, 5667, 5704, 5664, 5753.
Three holdouts, selected from metadata before generation and absent from prior
evaluation: 5811 (anniversary notice), 5820 (Ghana hospital-ship report), 5816
(long scientist profile). They were previously processed in Daily; their prior
model outputs were not used in selection or review. This is a holdout from the
prior evaluation, not a claim that these are new production records.

Only currently permitted China versions were sent. Coordination with the
Singapore permission owner confirmed that October 29's two-link grant does not
authorize commercial Anthropic processing. **No new Singapore generation** was
performed. Historical Singapore artifacts remain offline evidence only. No
Singapore processing was added by this task. During final review, main merged
#913 at `034c94ec4f`. Base reconciliation inherits that repair and its generated
artifacts; this task authors no DB/output changes relative to the new base.
Existing assertions and the additional machine-prose/desk-scope tests are retained;
mandatory CI must pass the reconciled final head. The frozen paid trial remains
pinned to `5b0eef1ab2` and was not rerun or repriced after base updates.
Head `93e86215bb` subsequently passed full CI 41069406872 (8,306 tests, 15
skips, isolated render/validation with 10 warnings and no tracked DB/output
mutation). Main advanced during that run to `95c53909cf`, including the
mandatory shared-desk standard, source-definition pilot and Daily data. The
branch inherited those shared changes with the paid model code unchanged at
that reconciliation. Merge preparation now isolates the historical candidate
from the default runtime; it does not regenerate paid output or authorize a
production release.

Both models received revised prompts and identical frozen originals. Whole-path
order alternated by record. Separate translation ran even for screened-out
records. Summary/category isolation used the same revised Sonnet English for
both models, and every judgment was checked against the Chinese original, not
model agreement. A held Sonnet translation used as an isolation control remained
held; it was not cleared for admission. Actual Haiku-own-English path outputs
were also inspected. Review is unblinded agent source inspection, not independent
human bilingual acceptance or a population error-rate estimate.

## Task findings and guard failures

| Task | Revised Haiku 5.5 evidence | Revised Sonnet 4.6 evidence / limit |
|---|---|---|
| Relevance | Scores the military Information Support Force unit feature 5742 at 0.50, filtering it; no demonstrated replacement advantage | Scores it 0.72; this is a comparison concern, not a human-adjudicated false-negative rate. Experimental reference uses Sonnet relevance, whereas production uses Haiku 4.5 |
| Translation | 9/13 accepted by code, 4 held. Accepted 5754 adds rappelling and strengthens should to will; 5742 invents home medical visits. Holdout 5820 changes Tema to Takoradi, propagated into its own-input summary | 10/13 accepted, 3 byline holds. 5748/5755 have correct English reporter affiliations and no material defect found in their full inspected bodies: excessive holds under the new anchor contract. 5655's byline alarm is excessive on that span, but its output independently misspells Songmaoling. Accepted 5754 misspells Niu Yusen; 5667 misidentifies ancient Song as a dynasty |
| Summary on common English | 13/13 accepted by code, yet 5755 invents the base's Central Plains location; 5704 excludes a senior/uniformed representative without source support; holdout 5816 turns the report meeting into the conferral of the honor | 13/13 accepted, yet 5748 supplies an undisclosed space-tracking equipment function; 5704 adds a deliberate downgrade and diplomatic-calibration motive. Sonnet is not factual gold |
| Categories / flags on common English | 13/13 structurally accepted, but unsupported `cyber_info` for holdout 5811 and logistics story 5755 conflicts with the enum's cyber operations/information warfare/SSF definition | 13/13 structurally accepted, but flag reasons invent first detailed reporting (5652) and representation-downgrade motives plus South China Sea context (5704) |

Detected Haiku failures include 5652's unsupported live-fire and 5655/5748's
rank/name/affiliation errors. Its 5755 translation also reverses a three-or-four
people minimum versus a full-squad maximum. Missing source anchors caused three
holds on each model; this is a contract check, not proof of factual failure.
Sonnet's excessive holds were reviewed rather than counted as successful QA.
Both models frequently exceed the requested summary length. The long translations
were inspected at factual anchors and sections; no exhaustive completeness/pass
rate is inferred. The private review records coverage and uncertainties.

No unsupported tag or claim was excused because the stronger model agreed, and
no absence of a first-ever flag was treated as proof of accuracy. Prompts were
not retuned or regenerated after viewing the registered holdout. Translation,
summary and categories each have their own negative qualification decision.
Relevance retains its inexpensive incumbent; this sample does not qualify a
replacement. Narrow code checks improve detection but still admit known types
of error. Fallback cannot fix a factual error that the guards do not detect.

## Actual cost, fallback and repeated work

All **119 unique paid responses** settled; no unknown dispatch remains. Returned
model IDs match requests: 67 Haiku / 52 Sonnet. Returned-usage pricing through the
repository's existing table totals **$1.054463875**; conservative ledger charge
including its buffer is **$1.159910286**, below $3. These are usage-priced amounts,
not a provider invoice. One forced summary repair, failed/held outputs and all
fallback responses are included. The trial made no further dispatch after
completion. Restart produced **zero new dispatches** and unchanged ledger/results.

| Measured whole model path, 13 records | Sonnet-only reference | Haiku primary + Sonnet fallback |
|---|---:|---:|
| Code-complete / relevance-filtered / post-screen held | 9 / 1 / 3 | 8 / 2 / 3 |
| Tasks attempted | 43 | 40 |
| Tasks using fallback | 0 | 4 (10.0%) |
| Records using fallback | 0 | 4 (30.8%) |
| Response events including repair/fallback | 43 | 45 |
| Usage-priced whole-path cost | $0.734271000 | $0.223862975 |
| Cost / code-complete record, **not factual acceptance** | $0.081586 | $0.027983 |

The observed candidate path costs **69.51% less** in total, or 65.70% less per
code-complete record, than this experimental Sonnet-only reference. It processed
a different number of records because relevance decisions differed, and includes
Sonnet relevance rather than the incumbent Haiku 4.5. It is **not** a measured
saving against the current production mix or a quality-adjusted saving. These
are actual returned path responses, not the earlier hypothetical 25% fallback.
No daily rollout projection is warranted from this failed, small China sample.

Exact-request response reuse avoids rebilling overlapping isolation/comparison
conditions: 47 logical response reuses overall. In execution order, reference
paths made 40 fresh dispatches and reused 3; candidate paths made 44 and reused 1.
Each path cost counts every response it needed at its returned usage, including
shared responses; do not sum paths as the unique paid-trial total. The remainder
of the paid trial covers isolated/control tasks outside those screened paths.
The private ledger records reservations, settlement and request hashes across
restart; this does not add production stage persistence. No record was admitted
or published by the paid harness. There is no qualified accepted-record cost
denominator and no realized replacement saving.

## Verification, evidence preservation and rollback

Offline compatibility tests compare complete request digests against a frozen
pre-PR base execution for all four tasks, with empty overrides and after fallback.
They pin incumbent acceptance, partial category failure, JSON repair, SDK client
configuration, fatal and response safeguards, and explicit candidate isolation.
Candidate prompt digests preserve the evaluated messages. Additional coverage
includes mixed models/provenance, fallback success/exhaustion,
charging rejected output, fatal errors, private resolved-model budget holds,
rollback and existing desk regressions. A scripted production-pipeline fixture
explicitly opts into the candidate and runs rejection → pending SQLite → restart → accepted mixed-model SQLite →
disposable production render → repeat with no new dispatch/duplicate completed
record. It is offline integration, not live collector/model/publication evidence.
The paid harness uses the same Analyzer but does not write production storage.

The old 111-response Anthropic artifacts and native-Luna artifacts are preserved
unchanged. Old replay remains available without key/network/client construction:

```sh
.venv/bin/python -m tests.replay_model_evaluation \
  --evidence-dir /Users/benjaminyang/.codex/private/ipr-sonnet-haiku-eval-20261028-c73e
```

Those responses predate revised prompts; their replay is regression evidence,
not this qualification. Production DB, output, sidecars, usage history,
permissions and repository variables were not changed. Final PR verification
must use its exact-head checks. No merge or public-site readback is claimed.

Rollback for any separately authorized future activation: clear
`TRANSLATION_MODEL`, `SUMMARY_MODEL`, `CATEGORIZATION_MODEL`, `FALLBACK_MODEL`
and unset `MODEL_FIDELITY_CANDIDATE_ENABLED`;
restore/clear `ANALYSIS_MODEL` to Sonnet 4.6 and `RELEVANCE_MODEL` to Haiku 4.5.
It affects the next process and cannot cancel in-flight calls or rewrite records.
The remaining blocker to cheaper unattended processing is demonstrated factual
quality, including guard-missed holdout errors. This task grants no further
spend, framework work, merge, activation or publication.

## Newly exposed corpus-growth assertion on the final base

CI 41114640637 at `0388e7bde7` ran 8,312 tests and failed only two Korea
unchanged-page assertions after the inherited Daily snapshot crossed the
1,000-record display boundary. Both failures reproduce on exact base
`95c53909cf`: seven focused tests, two failures. This is separate from the
initial introduced environment failure and the earlier seven base failures.
The shared-Daily repair owner confirmed no competing correction or existing
commit for this boundary. Normalize one complete, correctly comma-formatted
numeral, retaining exact nonnumeric page comparison and the original permitted
numeric deltas (zero or two). Regression cases reject wrong deltas, changed
labels, extra quantities and malformed groups. No renderer, DB, generated
output, model configuration or source permission is changed by this correction.
The final combined revision still requires mandatory CI.

## Merge-preparation verification

The earlier combined head `d731c620a0` passed full CI 41119256793 (8,314 tests,
15 skips, isolated render/validation with 10 governed warnings, unchanged tracked
DB/output and no sidecars). That receipt predates the compatibility changes above.
Focused checks and required CI must verify the final merge-preparation head.
Historical trial ledgers, outputs, review and verification receipts remain
unchanged; merge preparation adds its own receipt rather than overwriting them.
