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
| Collection | `scripts/shadow_collect.py` stores source identity and metadata per release in private custody (`archive/singapore-mindef-daily`), fails closed on a legacy schema, skips media-only releases. Categorical collection exclusions removed. |
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
disabled because it publishes to a public branch. Current-schema private custody
`archive/singapore-mindef-daily` is **not yet created**. The older private
`archive/singapore-mindef` is a *legacy-schema evidence copy* (no `source_identity`
or `metadata_json`): it is preserved untouched, the collector refuses to write to it,
and `links_from_custody` refuses it by name (`singapore_link_custody_schema_legacy`).
The model pair, daily cap (0.35 USD) and one-record-per-run limit
follow the shared policy.

## Shortest separately authorized activation sequence

Candidate code: this PR (public) plus the companion private PR that adds the
dispatch-only `sg_mindef_releases` matrix row to `shared_daily_processing.yml`
(own gate `vars.SG_MINDEF_DAILY_ENABLED`, required `singapore_identity` input,
never enabled by `workflow_run`, never runs other families in the same dispatch).
Recurrence stays off. Secrets are checked by presence only.

1. Merge the public PR; Daily applies m0022 (or run the migration runner). Then merge
   the private PR and re-run its `offline-contracts` against public `main`.
2. Create the new private custody ref `archive/singapore-mindef-daily` (never reuse the
   legacy `archive/singapore-mindef`); run `scripts/shadow_collect.py` against it;
   record the immutable commit. Confirm media-only and both held speeches
   (`15aug26-speech`, `16sep26-speech`) are absent or held.
3. Run `core.singapore_mindef_links.admit_links` on the production DB (link parents).
4. Set the secret `DAILY_SG_MINDEF_RELEASES_KEY` (private repo and public Daily),
   variables `SG_MINDEF_DAILY_ENABLED=true` and `IPR_PRIVATE_DAILY_ENABLED=true`, and
   flip the three `sg_mindef_releases` policy booleans in a reviewed change.
5. Dispatch the private workflow once with `singapore_identity=<one identity>`
   (cap 0.35 USD, one Record); the next attended Daily fetches the signed envelope.
6. Read back `record/source-<sha24>.html`, the Singapore Desk and Archive/search
   live. Afterwards set the variable and booleans back off unless recurrence is authorized.

Founder decision needed separately: the public `shadow/singapore-mindef` branch
holds 105 historical original-body rows (historical-content treatment is not
decided here). Because custody, policy and secrets are not installed, the
10 November scheduled Daily will **not** produce a MINDEF Record; the recommended
path is a later attended Daily after step 4.

## Coordination with PR #1014 (integrated; both PRs still unmerged)

#1014 (head `9523b9481b`) records the founder's source-use decision and governance
wording. #1017 (head `ecee078bf7`) implements it and does not restate or replace it.
The integration branch merges both onto `main` `8a79605212` (later refreshed with
Daily-update commits `aafddd1397` and `b4323c13ad`, which touch no shared file) and
resolves the two shared files as follows:

- `core/mindef_permissions.py` (module docstring only): #1014's evidence
  classification sentences are kept, with this PR's pointer to the per-component
  predicate (`core.mindef_public_boundary.permitted_machine_sql`).
- `site/preview/templates/desk.html` (the Singapore branch of the one-line
  explanation): both of this PR's Singapore branches are kept, and #1014's
  sentence that official outbound links follow the standing official-host rule is
  added to the fallback branch. The "model processing on hold" claim stays accurate
  while activation is unauthorized and is to be revised at activation.

`desks/registry.json` and `DECISION_LOG.md` from #1014 merge without conflict. The
registry's "held" wording is not changed here; see the m0022 release runbook,
`SINGAPORE_MINDEF_M0022_RELEASE_RUNBOOK_2026-11-09.md`, for the migration release
sequence and the items to update at activation.
