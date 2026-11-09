# Singapore MINDEF operational completion — 9 November 2026

Review candidate. Nothing here is merged, deployed, activated or live. No
collector or schedule is enabled, no paid model call was made, no production
database or evidence was modified, and no publisher outreach occurred.

## Decision (founder, recorded as the founder's interpretation)

The founder reports a written relationship with MINDEF Media Relations and
affirms standing authorization for: private custody of eligible MINDEF-owned
official-release originals, bounded external model processing of the English
original, and independently written public factual explanations. A later
publisher message is reported to cover future linking requests. This record
reproduces no private correspondence and invents no further term.

Still protected: third-party media; publisher access restrictions; republication
of MINDEF original text; source integrity; factual accuracy; spending limits;
human-controlled editorial publications (Briefs, Dossiers).

## What changed

| Layer | Change |
| --- | --- |
| Collection | `scripts/shadow_collect.py` stores source identity and metadata per release in private custody (`archive/singapore-mindef`), fails closed on a legacy schema, skips media-only releases. Categorical collection exclusions removed. |
| Processing | `processing/screening.py` registers `SINGAPORE_MINDEF_DAILY_PROFILE` (English, no keyword prefilter, not in the legacy queue); `analysis/singapore_daily_prompts.py` supplies relevance and evidence-bound summary prompts; `analysis/analyzer.py` binds summary facts to evidence passages. |
| Admission | `core/daily_sources.py` registers `sg_mindef_releases` as one `DailySource` through the shared lifecycle. Migration m0022 adds `singapore_mindef_source_records`, a link-only parent, and recreates the m0021 parent triggers. `core/singapore_mindef_links.py` reads pinned custody and writes parents idempotently, holding (not replacing) a drifted version. |
| Boundary | `core/mindef_public_boundary.py` replaces the blanket machine-record abort with a per-component check (`permitted_machine_sql`): not a held identity, not model-flagged, MINDEF-attributed, and bound to an admitted parent with equal metadata, content and capture hashes. Without m0022 the blanket hold remains. Staged databases carry boundary triggers (`mindef_public_no_machine_insert/update`) whose predicate was frozen as `0` at install; m0022 re-issues them with the permitted-component predicate (and `is_already_applied` refuses to count a stale one), so admission is not silently blocked after migration. |
| Delivery | `site/preview/generate_preview.py`, `desk.html` and `_machine_explanation.html` list admitted Singapore records on the Singapore Desk, the Archive (`machine_explanation`) and the search index, and the Record page names the Singapore Desk and the English-source note. `SingaporeRenderedDelivery` renders the full chain from a scratch copy of the tracked database and checks that no original title or body reaches any public file. |
| Audit | `scripts/audit_mindef_public_surfaces.py` still blocks non-permitted machine rows and reports permitted ones separately. |
| Compatibility shims | The two `pipeline.py` MINDEF branches (collection skip, queue hold) are kept as named shims: the public pipeline never collects MINDEF; private custody and the shared Daily lane do. |

## Source-specific exclusions

`15aug26-speech` and `16sep26-speech` (unrepaired charset damage) are excluded in
the policy entry, in the links module, in the boundary, and by a CHECK in the
parent table. A test asserts these lists match `scraper.sources.sg_mindef`.

## Left disabled

All three policy booleans in `config/philippines_daily_policy.json` for
`sg_mindef_releases` are false; the desk manifest registration is unchanged
(`desk_registered=False`); `.github/workflows/singapore_shadow.yml` stays
disabled because it publishes to a public branch; the private custody branch is
not created. The model pair, daily cap (0.35 USD) and one-record-per-run limit
follow the shared policy.

## Shortest separately authorized activation sequence

1. Merge this PR; the daily workflow applies m0022 (or run the migration runner).
2. Create the private custody checkout `archive/singapore-mindef`; run
   `scripts/shadow_collect.py` against it; record the immutable commit.
3. Run `core.singapore_mindef_links.admit_links` on the production DB (parents).
4. Flip the policy booleans and set `DAILY_SG_MINDEF_RELEASES_KEY`,
   `IPR_PRIVATE_DAILY_ENABLED`, `IPR_DAILY_INTAKE_DIR` for one bounded run.
5. `processing.daily_runner.private_run` → sign → admit; then read back
   `record/source-<sha24>.html`, the Singapore Desk and Archive/search on the live site.

## Coordination with PR #1014 (unmerged at head `9523b9481b`)

#1014 records the founder's source-use decision and governance wording. This PR
implements it and does not restate or replace it. Both touch two shared files and
a trivial textual conflict is expected from whichever merges second:

- `core/mindef_permissions.py` (module docstring only): keep #1014's evidence
  classification sentences; keep this PR's pointer to the per-component predicate.
- `site/preview/templates/desk.html` (the Singapore branch of the one-line
  explanation): keep this PR's two Singapore branches, and add #1014's sentence that
  official outbound links follow the standing official-host rule to the fallback
  branch; drop its "model processing … on hold" claim only once activation is
  separately authorized and live-verified.

`desks/registry.json` and `DECISION_LOG.md` from #1014 merge without conflict.
