"""
The one pinned model price table.

Two things read it: `scripts/spend_guard.py` (pre-flight estimate for bulk
backfills) and `analysis/usage.py` (run-level cost telemetry). Before this
module existed the table lived only in spend_guard; it moved here so the
telemetry did not become a second copy that drifts from the first.

These are ESTIMATES against a table pinned in the repository. Nothing here is
fetched at run time and nothing here reads an invoice: a price change at the
provider is invisible until someone updates this file. Verify against
https://platform.claude.com/docs/en/about-claude/pricing before trusting a
large figure.

Rates verified 2026-10-01 against that page:

    claude-sonnet-4-6   $3 / $15 per MTok (input / output)
    claude-haiku-4-5    $1 / $5  per MTok
    5-minute cache write = 1.25 x base input; cache read = 0.10 x base input.

Rates verified 2026-10-28 against that page, for the opt-in model only:

    claude-haiku-5-5    prompt <= 100,000 tokens: $0.10 / $0.50 per MTok
                        prompt  > 100,000 tokens: $0.50 / $2.50 per MTok
    "A request's prompt length counts all of its input tokens, including cache
    reads and cache writes. Each request is priced on its own." Cache
    multipliers are the same as above.

A request-tiered model is deliberately NOT in `PRICING_USD_PER_MTOK`: that flat
table is read directly by `scripts/spend_guard.py`, `scripts/rescreen_desk.py`
and `processing/vpcp_policy.py`, none of which can apply a per-request band.
"""

from __future__ import annotations

from typing import Optional

#: Date the rates below were last checked against the provider's page.
PRICING_CHECKED = "2026-10-01"

# USD per million tokens.
PRICING_USD_PER_MTOK = {
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5":           {"input": 1.00, "output":  5.00},
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output":  5.00},
}

#: Models priced per request in two bands by that request's total prompt
#: (uncached input + cache writes + cache reads). The whole request is priced
#: in its band; a prompt of exactly the threshold is in the lower band.
TIERED_PRICING_USD_PER_MTOK = {
    "claude-haiku-5-5": {
        "threshold_prompt_tokens": 100_000,
        "base": {"input": 0.10, "output": 0.50},
        "long": {"input": 0.50, "output": 2.50},
    },
}

#: Multipliers on the base input rate. The pipeline marks its system prompt
#: `{"type": "ephemeral"}`, which is the 5-minute TTL, so that is the write
#: rate that applies.
CACHE_WRITE_5M_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


def estimate_usage_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> Optional[float]:
    """
    Estimated USD for one model's token counts, or None if the model has no
    price on file.

    For a model in `TIERED_PRICING_USD_PER_MTOK` the counts must be ONE
    response's: the band is chosen from that response's total prompt. Summing
    such responses means summing their costs, never their tokens — the ledger
    in analysis/usage.py does exactly that.

    `input_tokens` is the uncached input the API reports; cache writes and
    reads are reported separately by the API and are priced here from their own
    multipliers, so the four terms never overlap.
    """
    price = PRICING_USD_PER_MTOK.get(model)
    tiered = TIERED_PRICING_USD_PER_MTOK.get(model)
    if tiered is not None:
        prompt = (input_tokens + cache_creation_input_tokens
                  + cache_read_input_tokens)
        price = tiered["long" if prompt > tiered["threshold_prompt_tokens"]
                       else "base"]
    if price is None:
        return None
    rate_in, rate_out = price["input"], price["output"]
    return (
        input_tokens * rate_in
        + output_tokens * rate_out
        + cache_creation_input_tokens * rate_in * CACHE_WRITE_5M_MULTIPLIER
        + cache_read_input_tokens * rate_in * CACHE_READ_MULTIPLIER
    ) / 1_000_000
