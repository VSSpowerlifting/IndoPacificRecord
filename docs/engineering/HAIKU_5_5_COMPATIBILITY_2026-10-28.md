# Haiku 5.5 opt-in compatibility and request-level cost accounting (28 October 2026)

**Status: readiness only.** Nothing is activated. `RELEVANCE_MODEL` stays
`claude-haiku-4-5-20251001`, `ANALYSIS_MODEL` stays `claude-sonnet-4-6`, and
`DAILY_ANALYSIS_CAP` stays 55. The change lets a separately approved run set
`ANALYSIS_MODEL=claude-haiku-5-5` without the API rejecting the request and
without the ledger misstating its cost. No paid call was made. Nothing here
validates translation, summary or categorization quality on Haiku 5.5.

## Why

The public ledger (`.github/state/llm_usage.jsonl`, 2–28 October) records
31 runs, 3,556 wrapper calls, 74 failures, 693 main-queue completions and
**$35.886787** estimated spend. Translation accounts for **$20.168344** of
that. These figures are pinned-table estimates, not a reconciled invoice.
Haiku 5.5's lower band ($0.10 input / $0.50 output per million tokens) is far
below Sonnet 4.6 ($3 / $15), so it is worth a bounded quality comparison. That
comparison needs a model the wrapper can actually call and a cost record that
prices it correctly.

## Official references (checked 28 October 2026)

- Migration guide: <https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide>
- Prompting guide: <https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5>
- Pricing: <https://platform.claude.com/docs/en/about-claude/pricing>
- Models overview: <https://platform.claude.com/docs/en/models/overview>

Facts relied on:
- The exact ID is `claude-haiku-5-5` and there is no alias.
- Context is 1M tokens and maximum output is 128K, so the 32,000-token
  translation ceiling fits.
- `temperature`, `top_p` and `top_k` are rejected.
- Thinking is adaptive by default. `thinking: {"type": "disabled"}` is
  supported at low, medium and high effort.
- Forced named `tool_choice` is supported.
- `refusal` and `model_context_window_exceeded` are possible stop reasons.

## Request behavior

| | Old models (unchanged) | `claude-haiku-5-5` (opt-in) |
|---|---|---|
| Text (`_call`) | `model, system, messages, max_tokens, temperature` | `model, system, messages, max_tokens`, plus body `thinking={"type":"disabled"}`, `output_config={"effort":"high"}` |
| Translation / tool (`_call_tool`, streamed) | the above plus `tools`, `tool_choice` | the same, with sampling replaced by the two settings |

- The two settings go through the SDK's `extra_body`, so they serialize under
  any `anthropic>=0.40.0,<1`. The installed 0.100.0 was checked offline with
  a mock HTTP transport, and `requirements.txt` is unchanged.
- Disabled thinking with high effort is a candidate setting for instruction
  fidelity and cost. It has not been evaluated.
- Prompts, token ceilings, completeness rules, thresholds, category semantics
  and publication fields are unchanged.

## Response handling (all models)

- Text is read from every `text` block, in order and joined. Thinking blocks
  and tool blocks are never treated as the answer. No usable text raises
  `Empty response content`.
- `refusal`, `model_context_window_exceeded` and `max_tokens` stops fail the
  call even when the content looks valid.
- Each response's usage is recorded exactly once and marked failed.
  Connection and status errors record no tokens, as before.
- Translation fails closed on a non-object tool input, or on a missing, empty
  or non-string `title_en`/`body_en`.
- No repair call, model fallback or retry was added.
- Summary already had a forced-tool path for malformed JSON. It is unchanged.
- One small change applies to the old models too. A whitespace-only response
  or a response with no text block now fails as `Empty response content`
  instead of reaching the JSON parser. A second text block is now joined
  instead of dropped.

## Tier accounting

`analysis/pricing.py` holds one pinned table. Haiku 5.5 lives in
`TIERED_PRICING_USD_PER_MTOK`:

| Request prompt tokens | Input | Output | Cache write (1.25×) | Cache read (0.1×) |
|---|---|---|---|---|
| ≤ 100,000 | $0.10 | $0.50 | $0.125 | $0.01 |
| > 100,000 | $0.50 | $2.50 | $0.625 | $0.05 |

- The band is chosen per response. Prompt tokens are uncached input plus cache
  writes plus cache reads.
- The whole response is priced in that band.
- `UsageLedger` adds per-response costs for a tiered model. The run record
  sums them, so two 60k-token requests stay in the lower band and an earlier
  short call is never repriced when a later one crosses 100k.
- The record schema, rounding and raw token counters are unchanged.
- Flat-rate models are still priced from summed counters, and every row in
  the tracked history still reprices to its stored value.
- Unknown models stay in `unpriced_models`.

**Boundary:** these are estimates from standard, global, non-batch rates with
the 5-minute cache.
- `pricing_checked` in each record stays `2026-10-01`, which is the date for
  the flat table. The Haiku 5.5 rates were checked 28 October.
- A rate or band change needs a code change and a new check.
- `core/vietnam_corpus_bridge.py` prices aggregated deltas. For a tiered
  model that can only overstate cost, and Haiku 5.5 does not reach that path.
- `scripts/china_title_release_batch.py` already prices one response at a
  time.

## Explicitly unsupported: bulk estimates

`scripts/spend_guard.py` estimates by characters and old output ratios. It
**refuses** Haiku 5.5 with a `KeyError`, because one Chinese character is not
a calibrated Haiku 5.5 token count and old ratios are not a bound. Rescreening
(`scripts/rescreen_desk.py`) inherits the refusal. A bulk estimate needs measured per-request usage first.

## Shared consumers

- **VPCP bridge** (`processing/vpcp_policy.py`): still pins the default
  models and returns `vpcp_model_not_authorized` for any other. Its price
  verification still covers only the flat table.
- **Private Daily intake** (`processing/daily_intake.bound_private_calls`):
  - Still allows one relevance call and one summary call, with no retries.
  - Its reservation prices UTF-8 bytes, an upper bound on tokens, as cache
    writes. A request that could cross 100k is therefore reserved at the
    upper band.
  - Default models are unchanged, and no private processing is activated.
- **Korea, screening and runner:** unchanged and covered by their existing
  suites.

## Rollback

- To stop using the model, unset `ANALYSIS_MODEL`. The default is untouched.
- To remove the code, revert the PR. No data, schema, history or output
  migration exists.

## Future evaluation outline (not authorized by this change)

1. Get owner approval for a bounded comparison: **$3 total API spend**, and
   only source versions whose use with an external model is already
   authorized.
2. Run the same inputs on the default `claude-sonnet-4-6` and on
   `ANALYSIS_MODEL=claude-haiku-5-5`, one model per invocation, using
   temporary state only.
3. Compare translation completeness and fidelity, summary accuracy, category
   agreement, failure and stop reasons, and measured per-request tokens and
   cost.
4. Decide from the evidence. Changing a default, calibrating bulk estimates
   or migrating relevance are separate decisions.
