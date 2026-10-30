# Korea Desk — shared Daily processing convergence

> **Desk architecture/process supersession — 30 October 2026:** the
> [mandatory shared desk standard](../desks/README.md) governs every current and future
> desk. This document's older common architecture, onboarding order and launch
> clocks do not override it. Source-specific decisions, restrictions, real
> evidence and still-used commands remain valid in their actual scope. This
> notice does not claim runtime migration, change permissions or activate a source.


The target is **one** IPR article-processing pipeline, not two Korean collectors.
Korea has working private MND capture, standing verified metadata and licensed
Korean-text publication. China's historical model route is Chinese/PLA-specific;
it must not be invoked for Korean documents.

## Phase 1 (this PR): inactive Korean-specific model path
- Versioned Korean relevance, translation glossary and source-attributed summary
  /significance builders; no China taxonomy or China relevance fallback.
- Reuses Analyzer's existing billing safeguards, model/tool schema, usage telemetry,
  and translation token limits. Holds incomplete translation or summary rather
  than marking the analysis finished.
- Korean profile is registered with daily_queue=False until corpus/provenance
  and automatic English-publication gates are verified. No costs, collection,
  production DB writes, site change or editorial permission change.

## Next coherent phase: reviewed-license original → main article corpus
Implement one read-only bridge from the **published, hash-verified** Korea MND
original-text registry into the shared articles DB, with original publisher
title verified from private custody, exact version identity, source-use rights
and dedup. Reuse MND private collection, never crawl twice. DAPA remains
metadata-only pending its own rights review. Keep the legacy Korea publication
and approved English pages until the unified renderer has exact parity.

## Final phase: unattended English processing and publication
Owner wants the same unattended source-to-English pathway as China. This
requires an automatic fail-closed source-rights/prompt-injection/translation
QA gate and proper machine-generated disclosures (not per-document approval).
Version glossary, name/date/number consistency, source attribution and held
results. Establish bounded model costs, failure/retry budget, source SHA
bindings and post-deploy readback. No model can itself attest semantic truth:
use a reviewed Korean test suite and withhold low-confidence items for
exceptional editorial review, not routine approval.

Do not change Korea to live or enable automated publication until actual
corpus/renderer/rights verification succeeds. No artificial 7/30-day gate.
