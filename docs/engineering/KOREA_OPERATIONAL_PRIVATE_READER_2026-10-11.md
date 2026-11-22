# Korea Desk operational private reader — manual Actions workflow

**Implemented October 11, 2026.** Standalone `workflow_dispatch` and PR QA for the **existing** South Korea shadow MND republication family, with a **manual acknowledgement** and **zero publisher traffic**. It runs against current `shadow/korea-policy-briefing` Git objects pinned at one exact commit. The reader and private review workbench are now merged in main via [#410](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/410) and [#413](https://github.com/VSSpowerlifting/China-Mil-Watch/pull/413).

## How to use (no terminal needed)

1. Open the repository's GitHub Actions tab and workflow **Korea Desk — real private operational reader (on demand)**.
2. Select `main`. Click **Run workflow**, deliberately acknowledge **existing shadow Git only**, and optionally enter a Korean/English search phrase. The run reads existing GitHub shadow state, not korea.kr.
3. After a successful run, open the run's **Artifacts** and download `korea-metadata-only-reader-<run>-<attempt>`.
4. Open `reader.html` locally: official source titles, publisher link, dates, institution, and exact state hash. Use `unsigned-review.html` as the separate five-original review checklist. Never treat it as completed Korean human-source review.

**Privacy qualification:** A GitHub Actions artifact is accessible to users permitted to read run artifacts and may be visible to the public if this repo is public. **Only already-public official titles/links and technical provenance** are placed there. Never upload signed reviewer identities, private analysis, full Korean source bodies, or preserved HWPX to this artifact. Do actual reviewer annotations in access-controlled storage.

## What the workflow checks on real state

- The Git fetch is limited to existing `shadow/korea-policy-briefing` in this repo and pinned to a literal 40-character SHA. No live third-party or Korean government source request.
- Real SQLite original-language body search is performed **in memory**. The only exported fields are source identifier, title, first-seen run, institution, official link, publication day and pinned state SHA; body, screenshots and media never leave private Git state.
- Five preserved candidate origins continue to be reported as **unsigned/HOLD**, and reviewer/rights/owner publication approvals remain false.
- Production database, tracked output hashes and shadow Git state are checked unchanged.
- Querying current shadow may yield newer **private research** records than the five frozen publication candidates; **this never adds them to the allowlist**. The current release-candidate snapshot remains strictly five archival identities.

## Gating and release track

Operational **private** browsing ≠ public Korea Desk. Actual source-specific original-language/HWPX QA, content/media reuse boundaries and human publication approval remain governed by [the source-use standard](../../CONTENT_AND_DATA_RIGHTS.md#7-research-first-source-use-standard), [the shared desk standard](../desks/README.md), the current policy and `DECISION_LOG.md`. The superseded October 11 pilot release plan is retained in Git history, not an active launch gate. Only genuinely permitted and source-verified components can reach a reviewed private preview; publication requires separate authority. This dated status does not prove DAPA, scheduler, public ingestion, Sunday use or model input was activated.
