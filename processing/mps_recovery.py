"""Owner's one MPS number-only recovery attempt; never an unattended retry policy.

Ten exact Foreign Affairs versions were held only for E_NUMBER_MISMATCH by
the date-reading defect fixed in #955. Each may be processed once more, in a
manual private daily-bridge dispatch, one reviewed batch at a time. Their
outputs, accepted or rejected, stay in the private Daily ledger, and an
accepted projection is withheld from the signed handoff until it is named in
RELEASED by a reviewed change.
"""
from processing.vpcp_correction import manual_context

DECISION = 'DECISION_LOG.md#2026-11-02--owner-one-mps-number-only-recovery-attempt'
FAMILY = 'vn_mps_foreign_affairs_vi'
PRIOR_FAILURES = ['E_NUMBER_MISMATCH']
# identity -> (content_sha256, run that recorded the hold)
RECORDS = {
    'mps-vi:1791803388': ('2fc8d711881ea1125d9825ecd3150f2c6a4e346315a682fdda5ca6ec67e4c3f9', '39806266450-1'),
    'mps-vi:1791881212': ('dd1c2144e9c74e2754fd8229c32d2e69b14f5e20d55c8acb2afc365dfc5e90b6', '39806266450-1'),
    'mps-vi:1791882878': ('a65fb441e41d0cc521e4c709b2fb251b29c12a82aef3e348550a57ef3eaa087e', '39806266450-1'),
    'mps-vi:1791960707': ('e05c9b1890f77bebe812536aa3c121bb66b6c8c7ccdd62a283d0443b2f18c7c1', '39806266450-1'),
    'mps-vi:1792026540': ('020b852fb882384b0b991290e08dc86d8df3fffd1821664a2b0155f55b530ecd', '39806266450-1'),
    'mps-vi:1792227611': ('9c5a6271a347b9fd6e3d371335f7151ef8099d49490530495489d980f541e379', '39806266450-1'),
    'mps-vi:1792371761': ('575a473af394bc387a2cfb6c633e0652a0b8cf9d3de23e14888a32b77feff988', '39806266450-1'),
    'mps-vi:1792511119': ('08bb04b90325af92ed797a3a214a350907f7ccdb1ac96e8212fb0fd60a99faac', '40037837163-1'),
    'mps-vi:1792566483': ('70fa877a5d13827901c92dc36433787cdfc9369871479db24afad4a88dcda471', '40037837163-1'),
    'mps-vi:1793249662': ('675f3880fd802b06be671228c0a7da0db9f4cf2a228b40138c9d96b25f1caaf4', '41166873695-1'),
}
# Two first, then two batches of four: each fits the run's five second passes.
BATCHES = (
    ('mps-vi:1791803388', 'mps-vi:1791881212'),
    ('mps-vi:1791882878', 'mps-vi:1791960707', 'mps-vi:1792026540', 'mps-vi:1792227611'),
    ('mps-vi:1792371761', 'mps-vi:1792511119', 'mps-vi:1792566483', 'mps-vi:1793249662'),
)
# The one batch a manual dispatch may attempt; advanced only after review.
# Batch 0 ran once in 41565761646-1; both outputs were inspected and accepted.
OPEN_BATCH = 1
# Accepted recoveries the owner has released to the public handoff.
RELEASED = frozenset()
# Private model output kept for inspection, accepted or rejected.
RETAINED = ('passed_relevance', 'relevance_score', 'relevance_reasoning', 'title_english',
            'summary_english', 'categories', 'is_significant', 'significance_reasoning',
            'model_id', 'prompt_version')


def eligible(family, identity, prior):
    """The exact held version, in its open batch, never attempted before."""
    pinned = RECORDS.get(identity)
    return bool(manual_context() and family == FAMILY and pinned
        and identity in BATCHES[OPEN_BATCH]
        and prior.get('content_sha256') == pinned[0] and prior.get('run_id') == pinned[1]
        and prior.get('outcome') == 'held_review' and prior.get('failures') == PRIOR_FAILURES
        and not prior.get('recovery_exception'))


def withheld(identity, item):
    return bool(item.get('recovery_exception')) and identity not in RELEASED


def retain(result):
    return {k: (result or {}).get(k) for k in RETAINED}


def snapshot(usage):
    """The analyzer's usage ledger before one record, or nothing to compare."""
    if usage is None:
        return None
    return {(r['task'], r['model']): r for r in usage.rows()}, usage.tiered_costs()


def usage_delta(before, usage):
    """Provider-returned tokens for one record, priced as analysis/usage.py prices a run."""
    from analysis.pricing import TIERED_PRICING_USD_PER_MTOK, estimate_usage_cost_usd
    if before is None:
        return {'tasks': [], 'cost_usd': None}
    rows, tiered = before
    after = usage.tiered_costs()
    out = []
    for r in usage.rows():
        key = (r['task'], r['model'])
        old = rows.get(key, {})
        delta = {k: (v - old.get(k, 0) if type(v) is int else v) for k, v in r.items()}
        if delta.get('calls', 0):
            if delta['model'] in TIERED_PRICING_USD_PER_MTOK:
                # Per-response bands: never priced from summed tokens.
                delta['estimated_cost_usd'] = after.get(key, 0.0) - tiered.get(key, 0.0)
            else:
                delta['estimated_cost_usd'] = estimate_usage_cost_usd(
                    delta['model'], delta['input_tokens'], delta['output_tokens'],
                    delta['cache_creation_input_tokens'], delta['cache_read_input_tokens'])
            out.append(delta)
    costs = [r['estimated_cost_usd'] for r in out]
    return {'tasks': out, 'cost_usd': None if None in costs else sum(costs)}
