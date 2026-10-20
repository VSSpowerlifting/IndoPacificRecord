# South Korea Desk Daily — activation (2026-10-20)

The activation PR makes Korea a live desk of the shared Daily. It contains code,
the live registry entry and the production manifest. Processing stays off until
the owner sets one repository variable.

## What runs once enabled

1. **Admission** (`core/korea_corpus_bridge.py`, `kr-corpus-bridge-v1`). An MND
   release republished on Korea Policy Briefing enters `articles` once per
   source version. It is admitted only when:
   - its KOGL Type 1 Korean text is in the public release index (`research/korea_published_original_texts.json`);
   - its SHA-256 matches the governed `korea_official_source_records` row.

   The bridge never admits:
   - releases with published editor-reviewed English;
   - the frozen October baseline;
   - the research hold `korea-policy:156785161`.

   A human-handoff receipt alone excludes nothing. A release that later gains
   reviewed English withdraws its machine record (`superseded_by_reviewed_english`).
   Every decision goes to the `korea_corpus_admissions` ledger (m0015). Replays
   do nothing, and a changed SHA is refused.
2. **Processing** (`processing/korea_shared_queue.py`). This is the shared engine
   with the Korea profile:
   - relevance `kr-relevance-v1`;
   - line-aligned translation `kr-translation-v2`, with glossary `kr-glossary-v1`;
   - analysis `kr-analysis-v1`;
   - deterministic QA `kr-qa-v1`.

   A QA failure holds that record with a reason code. The lane has its own cap,
   and a Korea failure never fails the Daily.
3. **Publication**. Records use the existing record, desk, archive and search
   surface. English is labeled an unreviewed machine translation. Analysis is
   labeled machine analysis, with claims attributed to the ministry.

On day one, one release qualifies: `korea-policy:156785691`. After that, a
release qualifies when the scheduled `korea_standing_original_text_production.yml`
workflow adds its text to the public KOGL release index.

## Owner steps

1. Set the repository variables. Code on `main` before this PR never reads them,
   so this step alone changes nothing.

| Variable | Value | Effect |
|---|---|---|
| `KOREA_DAILY_AUTOMATION_ENABLED` | `true` | Turns on admission and the Korea lane. Any other value leaves both off. |
| `KOREA_DAILY_PROCESSING_CAP` | optional; default `4`, max `20` | Maximum Korea records sent to the model per Daily. This bounds spend. |

2. Merge the activation PR. The merge itself starts render-only releases
   (official-link, bibliography and country-research publishers) that show Korea
   as a live desk with no records yet. The next Daily applies m0015, syncs the one
   manual Korea source row, admits `korea-policy:156785691` and processes it.
   Merging before step 1 would show the live desk while the lane is still off.

## Rollback

- To stop admission and processing, unset `KOREA_DAILY_AUTOMATION_ENABLED`.
- To withdraw the desk, revert the activation commit. The build refuses to render
  live Korea records without the live registry entry. Withdraw published records
  through the existing correction path, not by deleting rows.
