# China summary/category fold: isolated A/B pilot (2026-10-29)

**Status:** implementation of an offline, opt-in experiment. NOT approved for Daily,
scheduled execution, publication, or use on new source families. Do not enable
through a GitHub Actions workflow or replace the existing China analysis path.

## Hypothesis

Following Anthropic's October 22, 2026 guidance on folding tightly coupled
reasoning tasks, test whether one Sonnet call can provide a source-grounded
China summary, taxonomy categories, and model flag without the separate
post-translation categorization request.

This is **task-call consolidation**, not a multi-agent migration. IPR's
relevance screening, source-grounded translation, rights/custody checks and
publication gate remain separate. There is **no new agent framework**.

The current China pass uses relevance -> translation -> (summary in parallel
with categories). The candidate replaces only the last pair with one call.
Singapore, Korea, Vietnam, Philippines, Indonesia and Japan are out of scope.

## Implementation

- `analysis/china_fold_experiment.py` reuses BOTH existing China editorial
  rubrics from `analysis/prompts.py`, removes their conflicting individual
  JSON output contracts, and supplies the already translated source once.
  It performs exactly one new request with a separate usage task label.
- The combined output has exactly `summary`, `categories`, `significance`,
  and `significance_reason`. Invalid/duplicate/out-of-taxonomy categories,
  invented fields, malformed flags, and missing reasons fail closed and are
  counted as failed responses. Nothing is written to a production table.
- `scripts/evaluate_china_fold_experiment.py` compares the same English
  source input using **two original production methods** versus the combined
  experimental method. It is a local-only CLI; without `--execute`, it
  does no paid work. Both API clients use the current configured
  `ANALYSIS_MODEL`; no Haiku substitution occurs.
- Outputs and model text must be written to an explicitly supplied **private**
  file outside the public repository; the report contains IDs and both model
  responses, NOT original or translated full-text source bodies. Never commit
  the results to the public repository.

## Prepare cases

Create a **private** JSONL file using 12-30 records from the existing frozen,
rights-cleared evaluation corpus. Required fields on each line:

```json
{"id":"frozen-001","title_en":"An approved English title","body_en":"Approved source text for model processing."}
```

Do not extract fresh private originals, create new translations, weaken source
permission rules, or silently replace the previously reviewed corpus. If the
frozen local manifest has a different schema, generate this file within the
existing private evaluation workspace while keeping original IDs and source
pins. Human reviewers should be able to read the frozen original separately
to judge mistranslation and attribution. Record selection should include
routine items, significant items, borderline taxonomy cases, and sources
with dates, ranks, names, quantities, and specialized vocabulary.

## Execute locally (not CI)

```sh
python scripts/evaluate_china_fold_experiment.py \
  --input /path/to/private/china-fold-cases.jsonl --max-records 20

# Only after confirming the source material may be sent to Anthropic:
python scripts/evaluate_china_fold_experiment.py \
  --input /path/to/private/china-fold-cases.jsonl \
  --output /path/to/private/china-fold-results-20261029.json \
  --max-records 20 --max-estimated-spend-usd 3 \
  --execute --confirm-model-rights
```

The experiment checks conservative input/output token ceilings before each
pair and stops when the remaining estimated budget cannot cover another pair.
The USD bound is an **estimated preflight guard, not an API-enforced billing
limit**; provider retries and different real token accounting could result in
a discrepancy. Inspect the report and provider charges. Never infer total
program savings from request count alone.

## Independent decision rubric

Evaluate outputs blind to candidate identity, comparing every substantive
claim against pinned original evidence, not just against the model's English
translation. Record:
1. **Factual fidelity:** dates, quantities, actor/issuer, ranks, place names,
   exercise names, chronology, attribution, and unsupported interpretation.
2. **Completeness and prose:** preserves key developments without generic
   claims, within the existing two-to-three sentence summary contract.
3. **Taxonomy/flag:** precision, recall, and disagreement against a reviewed
   reference; investigate each switched label, not merely agreement percentage.
4. **Economics:** paired total billable tokens (including cache writes/reads),
   retries, API calls, elapsed time, and cost per fully valid article. The
   script records API-reported usage-derived estimated cost separately for
   each arm. Measure timing separately if needed.
5. **Reliability:** truncation, parse failures, invalid schemas, and complete
   matched-pair yield. An error in one arm is a failed case, not a free saving.

Do not declare a winner just from lower estimated token cost or fewer calls.
Prefer existing behavior unless the combined approach has **no material
factual-quality regression**, passes the full publication-independent review,
and shows meaningful measured savings on representative source records.

**Stopping point:** this PR supplies a safely isolated candidate and test
harness. It is NOT an authorization to run billable calls or to activate it
in production. Evaluate in a separately approved experiment phase and return
a signed/reviewed comparison with a keep/reject recommendation. Any production
wiring, if justified later, is a separate reviewed phase.

Reference: https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop
