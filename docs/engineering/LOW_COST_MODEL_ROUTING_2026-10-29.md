# Shared task-model routing — implementation candidate, not a cutover

29 October 2026. No paid calls, production writes, activation or publication in
this implementation. Neither tested cheaper candidate is factually qualified.
The incumbent models therefore remain the production defaults.

| Task | Default | Independent override |
|---|---|---|
| Relevance | `claude-haiku-4-5-20251001` | `RELEVANCE_MODEL` |
| Full translation | `claude-sonnet-4-6` | `TRANSLATION_MODEL` |
| Summary and desk summary/flag/event type | `claude-sonnet-4-6` | `SUMMARY_MODEL` |
| Separate China categories/flag | `claude-sonnet-4-6` | `CATEGORIZATION_MODEL` |

Empty task overrides inherit `ANALYSIS_MODEL`, whose default remains Sonnet 4.6.
Title-only translation keeps its existing model and independent activation.
`FALLBACK_MODEL` is empty by default; an authorized canary can explicitly select
`claude-sonnet-4-6`. No repository variable was changed by this work.

## Existing path and changed behavior

Collectors, source custody and intake policies remain upstream of the existing
queue. `pipeline.py` screens through `Analyzer.analyze_record`, stores partial
relevance for retries, and writes completed analysis with `storage.db` before
calling `site/render.py`. China translates then summarizes and categorizes in
parallel. English desks skip translation and combine summary/flag; Vietnam and
Korea keep their language profiles, event vocabularies and existing QA holds.
Unknown/held desks keep their existing dispatch and publication gates.

The shared Analyzer now resolves a model for each task, through the existing
Anthropic Messages requests. Haiku 5.5 retains its already implemented disabled
thinking/high effort request, without sampling fields. No provider adapter or
second processing pipeline was added. `gpt-6-luna` is the exact evaluated Luna
Responses model ID; it is not an Anthropic alias and is not added here.
Provider settings/prices were checked against the official
[migration guide](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide)
and [pricing](https://platform.claude.com/docs/en/about-claude/pricing).

Rejected values, truncation/refusal, connection/status failures and detectable
fidelity failures can retry that task once on a different configured fallback.
Fatal account errors propagate immediately. Existing China JSON-summary repair
remains inside each attempt. SDK transport retries are now zero, so every
application dispatch has a ledger entry; requests are not silently retransmitted.
A failed fallback reaches the existing partial-result/retry/hold path. Rejected
categorization now also prevents completion, rather than persisting its summary
with a silently empty taxonomy/false flag. No DB schema change is needed.

Task-local context keeps concurrent workers' primary/fallback choices separate.
Actual attempted analysis models are retained in the existing `model_id` TEXT
field: one model ID for single-model work, sorted `task=model` entries for mixed
work. Relevance retains separate task/model usage rows. Accepted records leave
the existing queue; incomplete records retain the existing whole-record retry
policy and reversible attempt limit. This does not create durable per-stage
checkpoints or guarantee exactly-once billing across an uncertain process crash.

Source-specific private spend wrappers check the resolved model **before**
reservation/dispatch. They retain their authorized routes, prices, token/call
ceilings and rejection behavior. An override or fallback cannot acquire a new
source-use/model permission. Korea's downstream translation QA can still hold
content without an extra model call. Article caps and independent desk switches
are unchanged; no new model schedule is introduced.

## Narrow factual protections

China prompts now request exact names, numbers, dates, quotation boundaries,
byline affiliations, distinct rank grades, all sections and embedded English.
China's prompt provenance advances to `v2-source-fidelity`. The translation
contract additionally retains original graded NCO ranks and identifiable reporter
bylines alongside English. Missing anchors or explicit source years reject a
full translation. Old responses lacking anchors can therefore be held even when
their English might otherwise be acceptable.

Small deterministic checks reject unsupported simulated/mock/notional submarine
qualifiers, unsupported live-fire, and an unambiguous transfer-year change.
They apply to summaries, flag reasoning and relevance as appropriate; source
rank/byline requirements apply only to full translations of matching Chinese
source text. Other desks retain their source-specific terminology and QA.

These checks do **not** verify arbitrary names, affiliation alignment, every
number, quotation semantics, completeness, or all chronology. Preserving source
anchors does not prove the adjacent English is correct. Omitting chronology in
a summary does not qualify that chronology challenge. The revised prompts have
not been generated against a real model. No factual acceptance is inferred from
schema success, source anchors, baseline agreement or offline replay.

## Preserved evidence and offline results

Frozen evaluation manifest SHA-256:
`bda59247ed4f264181ea482d1a1556599c620e7dffa2e26761391c8797daca35`.
The original private Sonnet/Haiku and Luna evaluations were read, never changed.

Replay all 111 stored Anthropic responses through the revised Analyzer:

```sh
.venv/bin/python -m tests.replay_model_evaluation \
  --evidence-dir /Users/benjaminyang/.codex/private/ipr-sonnet-haiku-eval-20261028-c73e
```

This verifies input hashes, uses no key/network/client construction, emits no
source prose, and prices returned usage through the existing ledger/table.
Responses were generated under the **old** prompts; this is rejection-code
regression evidence, not live qualification of revised prompts.

| Model / task | Accepted by revised code | Held by revised code |
|---|---:|---:|
| Sonnet relevance | 12 | 0 |
| Sonnet translation | 7 | 3 |
| Sonnet summary | 12 | 0 |
| Sonnet categories | 10 | 0 |
| Haiku relevance | 10 | 2 |
| Haiku translation | 7 | 3 |
| Haiku own-input summary | 11 | 1 |
| Haiku controlled-English summary | 8 | 2 |
| Haiku own-input categories | 10 | 0 |
| Haiku controlled-English categories | 10 | 0 |

Haiku's eight held outcomes include live-fire in 5754 relevance/summary,
malformed relevance and the submarine qualifier in 5652, missing anchors in
5755/5748/5655 translations, and the 5748 transfer-year swap. The three Sonnet
translation holds are missing anchors under the new contract, not proof of three
English factual errors. The new qualifier check also rejects native-schema
Luna's preserved 5652 summary. Other documented factual defects remain beyond
these narrow checks. Neither model's acceptance counts are factual pass rates.
Categories have structural acceptance here; their factual qualification remains
unresolved. The prior category agreement of 5/10 and flag agreement of 8/10 are
not accuracy against source truth. No human-accepted-record denominator exists.

Replay prices reproduce Sonnet $0.712149 across 45 responses and Haiku $0.040844
across 66, including original repairs and controlled tasks. In the original
matched workload, Haiku cost $0.030723370 versus Sonnet $0.712149000, or 95.69%
less before any new cross-model fallback. Translation alone cost $0.016414400
versus $0.389031000. Matched controlled-English summary/category cost was
$0.010786375 versus $0.223965000. These are returned-usage estimates, not invoices.

For a **hypothetical** workload with this sample's task/token mix, retaining
all cheap attempts and adding baseline-cost fallback for a cost-weighted share
`f` yields cost `0.030723370 + f * 0.712149000` per 12-record sample. At 25%
fallback the projected saving is 70.69%; the 50% target requires `f <= 45.69%`.
This assumes comparable fallback usage/caching and excludes new-prompt token
changes and correction labor. No observed fallback frequency or quality-adjusted
cost per accepted record exists for the revised configuration. Production cost
reduction from this implementation is **0% until a qualified cutover**.

The existing usage history also supplies actual Daily workload sizes. A separate
illustrative scenario uses the four completed 26–29 October runs, retains
incumbent title-only costs, assumes 30% more tokens for the candidate and all
candidate requests in the <=100k band, then adds Sonnet fallback at 25% of each
switched task's token volume. Relevance fallback is priced as Sonnet, not as the
cheaper incumbent relevance model. All prices use `estimate_usage_cost_usd`.

| Daily date | Actually analyzed | Recorded baseline | Projected with fallback | Projected saving |
|---|---:|---:|---:|---:|
| 26 October | 23 | $1.075084 | $0.420057 | 60.93% |
| 27 October | 23 | $1.404893 | $0.519922 | 62.99% |
| 28 October | 19 | $1.034471 | $0.409932 | 60.37% |
| 29 October | 33 | $1.415910 | $0.516817 | 63.50% |

This is a sensitivity estimate, not a forecast or observed saving. Aggregated
usage cannot establish each request's candidate price band, actual token uplift,
new-prompt cost or fallback frequency. Source/model authorizations and all four
tasks would have to qualify for this scenario. It does not change a held desk's
eligibility or provide a cost-per-factually-accepted-record denominator.

Focused checks cover mixed models and attribution, fallback success/exhaustion,
usage of rejected responses, fatal errors, resolved-model private budget holds,
configuration rollback and existing desk regressions. A scripted production
pipeline test exercises rejection → pending SQLite row → restart → accepted
mixed-model SQLite row → production renderer in a disposable directory →
second run with no new model dispatch or duplicate record. It omits unrelated
dossiers whose cited records are absent from its tiny fixture. This is offline
integration, not genuine collector/model execution or HTTPS publication.

## Release gate and immediate rollback

The next external action is a **new explicitly bounded paid qualification grant**
for revised prompts on source versions currently authorized for model use.
The prior $3 Anthropic and $1 Luna experiment allowances are not reusable spending
permission. Resolve factual acceptance independently for each task; retain the
incumbent for any task that fails. Exact-head mandatory PR CI is an engineering
gate, not a model-quality approval or merge/publication authorization.

After quality and release authority exist, select only qualified task overrides
and Sonnet fallback using the already scheduled Daily's repository variables;
use its existing cap for the authorized canary. Verify actual task/model usage,
accepted SQLite versions, generated public records where eligible, and HTTPS
readback before expansion. A skipped/green workflow is insufficient evidence.
No held desk or source permission changes with this model configuration.

Rollback requires no new deployment: clear `TRANSLATION_MODEL`, `SUMMARY_MODEL`,
`CATEGORIZATION_MODEL` and `FALLBACK_MODEL`; restore/clear `ANALYSIS_MODEL` to
Sonnet 4.6 and `RELEVANCE_MODEL` to Haiku 4.5. This affects the next process/run;
it does not cancel in-flight requests or rewrite previously stored records.
