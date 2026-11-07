# Korea DAPA — source-family decision candidate and offline integration candidate

**Prepared:** 2026-11-04. **Disposition:** DECISION CANDIDATE plus one verified
offline candidate; **no source activation, publisher contact, model spend,
merge or deployment**. **Owner chose option A on 4 Nov 2026 and adopted
standing conditional eligibility on 7 Nov 2026 (see §8)**; model, provider,
cost and public release remain open. §9 records the disabled-by-default
shared-pipeline integration and the consolidated activation proposal.

This completes the bounded DAPA source-completion phase on top of the earlier
qualification and offline-candidate work (#975, #976), which it carries
forward and supersedes as a single reviewable change. Those two PRs are not
closed by this one. Authority: `CONTENT_AND_DATA_RIGHTS.md` §7 (a basis per
activity; public access, private custody and an owner signature are not by
themselves a basis) and the shared-desk rules in `docs/desks/README.md`
(sources own evidence and policy; no new per-country engine).

## 1. Bottom line

- DAPA releases are **authentic, first-party in substance and already in
  private custody**, and the Policy Briefing article page that republishes them
  carries a **published KOGL Type 0 notice for its text**. That is a real §7
  basis for the page text, not merely a founder interpretation.
- The one step that remains interpretive is applying that page-text mark to the
  DAPA-authored prose inside the linked HWPX. It is documented, plausible and
  favourable, but not an explicit attachment licence. The owner chose to rely on it (option A, §8).
- The shortest defensible path to a source-grounded Record is therefore
  *decision on §5, then one bounded shared-pipeline profile*, not new
  collection, a publisher letter or a new engine.
- This PR adds the missing piece that needs no decision: a **per-version replay
  of the Type 0 mark from the exact preserved page bytes**, now required
  before the existing offline candidate builder can label prose CANDIDATE.

## 2. Evidence reviewed

| Question | Finding | Limit |
| --- | --- | --- |
| Issuer identity | Page names issuer 방위사업청 (portal filter `B00008`) and states the item is a reprint ("전재하여 제공") of the agency's press release. The HWPX template has a single responsible-department block for `156786758`. | No DAPA-hosted page exists. Identity rests on the portal's statement plus HWPX structure, not on a DAPA-origin URL. |
| Licence terms | Text-only KOGL Type 0 mark on the article page; photographs, images, illustrations and video are excluded because the portal states it does not hold their copyright. | The mark covers the **page text**. Extension to the HWPX is the open interpretation. |
| Version | Terms replayed from the page captured 28 Oct 2026 (SHA-256 `c45188ef…461ab`, 150,928 bytes, hash-verified). A Firecrawl retrieval on 4 Nov (not forced live, so possibly cached) shows the same notice. | Today's terms are a different observation from the captured version; both are recorded, neither substitutes for the other. |
| Custody | Private `archive/korea-dapa-policy-briefing` (commit `85cefcc4…`) holds the row, page capture, HWPX, ledgers. Shadow DB SHA-256 `58b97902…e5ed`. | Public repository holds signed link metadata only. |
| Existing holds | Joint release `156786687` (HOLD), heading-variant `156786759` (HOLD), orphan `156787071` (refused), historical `156785254` (no pinned row). | Unchanged. |
| Page ↔ HWPX binding (7 Nov) | Surveyed pages: the 5 pinned rows in DB `4150a9cd…` and the 3 in `58b97902…`. On every surveyed page, the attachment list has exactly one `.hwpx`, and its `fileId` equals the collector's recorded `document_url`. There is also one PDF. The marked article body holds no inline prose: it is only a document-viewer `iframe` (a server-side conversion of an attachment) plus the DAPA reprint remark. | The viewer conversion is not preserved and does not name its source attachment. Page-text/HWPX equivalence therefore **cannot be verified offline**. The binding proves only that the HWPX is the one listed on the marked page version. |
| Reprint remark | The same remark appears on the joint releases `156786687` and `156787670`. | It corroborates DAPA as the reprinted source. It never proves sole issuance. |

## 3. Result of the offline candidate (no network, no model)

| Identity | Result |
| --- | --- |
| `156786758` | **CANDIDATE** — re-run end to end on 4 Nov against the pinned archive (`shadow.db`, HWPX and page capture all hash-matched, `--page-capture` supplied, `network_requests: 0`). HWPX `1d019223…b415`, 6 body paragraphs, 1,035 characters, selected-prose SHA `fc1caba6…bc0b`. The final paragraph is a quotation whose speaker attribution needs human review. The Type 0 text mark replays from the captured page (mark digest `27af6358…7700`, scope `article_text_only`). |
| `156786687` | HOLD — joint release with an IP office (issuer). |
| `156786759` | HOLD — headline middle-dot variant. |
| `156787670` | HOLD — `joint_release_masthead` (a "공동보도자료" masthead table; not a DAPA single-issuer template). |
| `156788018` | **Structural CANDIDATE** (first preserved in run `42150393907-1`). HWPX `fileId` 198584502, 6 body paragraphs, 968 characters, selected-prose SHA `01f48248…`. Eligible under the 7 Nov standing conditional rule (§8) when its exact version authenticates; in the offline integration rehearsal (§9) it did, and it reached a rendered Record with synthetic processing output. |
| `156787071` | Refused. |

**Re-run on 7 Nov** against the newer private archive state (archive commit `7542326`, run `42326645197-1`, shadow DB SHA-256 `4150a9cd…c903`). Every row above reproduces. `156786758` stays CANDIDATE with the same prose SHA `fc1caba6…`. The older DB `58b97902…e5ed` gives identical results for its three rows. Every row binds cleanly (§2).

Page-text/HWPX equivalence is **not verifiable from the preserved page**: the page body is a viewer frame, not text. The stored text is the HWPX extraction. The receipt records this as `page_text_hwpx_equivalence: not_verifiable_from_preserved_page`.

## 4. Basis per activity (§7)

| Activity | Basis | Status |
| --- | --- | --- |
| Retain the original in private custody | Existing owner-gated collection | Supported |
| Independent analysis from facts, without reproducing DAPA wording | Strongest position; needs no licence beyond lawful access | Supported |
| Quote or translate DAPA prose, attributed | Type 0 for page text; for HWPX prose, interpretation | Option A chosen 4 Nov (§8): allowed per version under the §5 conditions; not yet wired |
| Machine-model input | Licence breadth would cover it, but provider, retention, cost and task authority are separate | Pending; not authorized here |
| Public original text | Conflicts with the 17 Oct 2026 official-link policy (`config/korea_dapa_official_link_automatic_admission.json`) | Owner decision; recommend keep link-only |
| Photographs, images, video, contact blocks | Excluded by the mark and by the candidate's screens | Excluded |

## 5. Options

**A — Accept the documented interpretation for DAPA-authored prose (recommended).**
Rely on Type 0 for the HWPX's DAPA-authored prose, per version, only when the
page mark replays from preserved bytes (this PR), the issuer is structurally
sole, and the candidate's screens pass. Allow private inference/translation and
independently worded attributed explanations as *source uses*; model calls and
public delivery still need their own authority. Public originals stay link-only.

**B — Page text only.** Treat the HWPX as unlicensed beyond independent analysis
of facts. Safest; slows the path because the page's text has not been shown
equivalent to the HWPX prose that the candidate selects.

**C — Seek narrow clarification from the publisher.** The one question is
whether the article's text-only Type 0 notice covers DAPA-authored prose in its
named HWPX. Publisher contact is **not authorized** and was not made.

## 6. Activation facts (why nothing is switched on)

- `core/standing_source_rights.py` `POLICIES` contains only `jp_mod_news_ja` and
  `kr_policy_mnd_releases`. Every Korea admission caller and
  `core/korea_corpus_bridge.py` is hard-coded to the MND slug. Adding a DAPA
  policy entry alone would **not** activate DAPA, and an entry added before a
  Type 0-aware shared profile exists would invite misuse. Recommendation: add
  none until the profile in §7.
- The existing Type 1 replay (`core/korea_archived_kogl_replay.py`) is
  MND/Type 1-bound and is left untouched.

## 7. What this PR contains and what follows

Contains (offline, no network, no model, no generated output):

- `core/korea_dapa_archived_kogl_replay.py` — read-only Type 0 text-mark replay:
  one canonical link equal to the expected article URL; one licence wrapper; the
  text-only Type 0 marker; a badge consistent with the text; the non-text
  exclusion notice; no conflicting type label. Fixed-code errors, no source text.
- `--page-capture` / `page_capture_path` in the existing candidate builder.
  A valid preserved article capture is **required for CANDIDATE/private prose
  export** under owner option A. Missing or failed replay produces a
  `license_mark:*` HOLD, leaves prose private and unexported, and records an
  explicitly held HWPX use rather than treating the interpretation as a usable
  basis without the mark. The existing CLI can still report a safe HOLD when
  `--page-capture` is omitted.
- `inspect_page_binding`: from the same hash-bound page bytes, it requires:
  - exactly one listed `.hwpx` equal to the collector's `document_url`
  - a viewer-only article body with no inline prose
  - the single DAPA reprint remark

  Any failure is a `page_binding:*` HOLD. A changed body form, or inline prose
  that would need an equivalence review, is held rather than assumed. An invalid
  `document_url` in the pinned row is treated as provenance drift.
- A joint-release masthead table is now an issuer HOLD (`joint_release_masthead`)
  rather than an unrecognized template.
- The receipt's HWPX prose basis reads `interpretation_accepted_by_owner_option_a`
  only on a fully clean CANDIDATE. Any hold (issuer, mark, binding, headline,
  dates, screens) records `held_pending_clean_candidate`.
- Tests with synthetic fixtures built from the real wrapper structure (no
  capture is committed). The previously staged #975/#976 code, tests and
  operating notes are carried here.

Follows, now that option A is chosen and once the open §8 items are settled: one DAPA profile in the existing shared
source definition and lifecycle (coordinate with the shared-pipeline owner and
#950; do not duplicate the Philippines work), with the policy entry added at
that point and gated off until each separate authority exists.

## 8. Owner decision — option A chosen; remainder pending

1. **Decided 4 Nov 2026 (Ben, in chat): option A** in §5 for HWPX DAPA-authored
   prose. Applies per version, only under the §5 conditions; it does not
   activate the source or authorize model or public use.
1a. **Resolved 7 Nov 2026 by item 4**: `156788018` needs no separate
   signature; it is eligible when its exact version satisfies the standing
   conditions.
2. Open: confirm public originals stay link-only under the 17 Oct policy, or
   amend it (option A assumes link-only).
3. Open: model input, provider and cost, decided separately, if at all.
4. **Decided 7 Nov 2026 (founder): standing conditional eligibility** under
   option A replaces per-release signatures. An exact version is eligible only
   when it authenticates the preserved page's Type 0 text mark, the page-to-HWPX
   attachment binding, the sole DAPA issuer and the approved lead/body prose
   scope. Joint, ambiguous, changed or excluded material stays held. Public
   originals stay link-only. **Limitation kept:** page-to-attachment binding
   does not prove licence equivalence; the owner accepted the documented
   interpretation, and equivalence was not verified. This is not an activation
   or release grant; provider/model/cost, Korean semantic review and public
   components remain separate decisions.

Verified here: unit tests for the replay, the candidate builder and the HWPX
auditor; the replay against the real preserved page. Not claimed: Korean
semantic review, English explanation, CI on the final head, merge, activation,
deployment or any live change.

## 9. Shared-pipeline integration (7 Nov 2026) and activation proposal

**What the integration PR adds (disabled by default).** One `DailySource`
profile, `kr_policy_dapa_releases` (desk `korea`, `desk_registered=False`), in
the existing shared definition and lifecycle: custody → `process` (existing
`Analyzer` interface) → signed handoff → `admit` → reader → render. No new
engine, queue or workflow. The material expansions are:

- **Migration `m0021_dapa_daily_machine_parent`**: m0015's single foreign key
  points at `regional_official_source_links`, but DAPA links live in
  `korea_official_source_records`, so a DAPA machine row could never be
  written. m0021 rebuilds `daily_machine_records` with identical columns, keys
  and CHECKs, replacing the foreign key with family-scoped insert/update
  triggers: DAPA rows need a `korea_official_source_records` parent with
  `official_issuer='kr_dapa'` and `public_scope='official_link_only'`; every
  other family keeps its exact `regional_official_source_links` parent. A DAPA
  Record therefore binds to the same link-only identity the site already
  lists, and every reader re-reads the parent and fails closed when it is
  missing or at another version. Admission refuses DAPA
  envelopes until the migration is present (`admission_migration`,
  fixed code `daily_migration_required`).
- **New `DailySource` hooks** (`approved_input`, `parent`,
  `admission_migration`, `desk_registered`): the approved-input hook passes
  only the authenticated lead/body paragraphs to the model; the parent hook
  binds admission, loading, reconciliation and the weekly audit to the Korea
  link row by candidate version and text/page hashes; the others keep an unregistered desk and
  an unmigrated database fail-closed; an unregistered source gets no
  governed-admission row in `pipeline.py`. Existing sources use the defaults
  and are unchanged.
- `_dapa_links` re-derives eligibility from pinned private custody on every
  run (mark replay, page binding, sole issuer, headline/date screens) and binds
  each record to a `metadata_version_sha256` over identity, URL, posted date
  and the original text/page/HWPX hashes. Any failure is a fixed-code HOLD
  (`capture_missing_at_pin`, `document_capture_missing`, `issuer:*`,
  `license_mark:*`, `page_binding:*`, `headline_punctuation_variant`,
  `joint_release_masthead`). Logs carry no Korean text.
- DAPA prompts (`analysis/korea_dapa_prompts.py`) and output quality screens
  (`processing/korea_dapa_quality.py`: modality and negation holds).
- Policy entry `kr_policy_dapa_releases` with every flag false.
- The shared machine-explanation partial names the correct desk and source
  language for Korea (Philippines and Indonesia output unchanged).

**Offline rehearsal (no network, no model, isolated scratch DB).** Against
the pinned private archive: `156788018` and `156786758` reached CANDIDATE;
`156786759` held (`headline_punctuation_variant`), `156787670` held
(`joint_release_masthead`), `156786687` held on three `issuer:*` codes;
`156785254` has no rows at pin `c87b219`. The two candidates ran through
`process` with a clearly labelled **synthetic** reading (model id
`synthetic-offline-rehearsal`; text states "synthetic offline rehearsal
text"). It is not generated research and not semantic review. They were
signed (envelope: 2 records, ASCII only), admitted (`admitted: 2`; re-run
`admitted: 0`), loaded by the reader and rendered to an isolated output
directory. Each Record page carried no Hangul, linked the korea.kr original
only, named DAPA as publisher and issuer, and showed the synthetic label.
Nothing was written to `pla_watch.db`, `output/` or any canonical sidecar.

**Consolidated activation proposal (requires separate owner authorization).**

| Item | Proposal |
| --- | --- |
| Permitted inputs | Only the authenticated lead/body paragraphs of an eligible exact version, read from pinned private custody; at most 1 record and 16,000 characters per run (policy caps). No page images, tables, attachments other than the bound HWPX, or held versions. |
| Permitted outputs | An English machine explanation (summary plus attributed facts naming DAPA), the official korea.kr link only, and private evidence translations kept in private custody. No Korean original text, no reproduced prose, no images. |
| Provider handling | The provider behind the existing shared Analyzer path, private runner only; API key held only as a repository secret; prompts, inputs and readings never logged. The owner confirms the provider's retention/training terms are acceptable for Korean government prose before enabling. |
| Model | **Proposed, subject to owner approval:** the configured defaults in `config.py`, `claude-haiku-4-5-20251001` for relevance (500 max output tokens) and `claude-sonnet-4-6` for the summary (2200). The shared cost guard binds the run to exactly those two calls. At the 16,000-character input cap (about 52 KB of UTF-8 Hangul with framing) the guard reserves about $0.07 + $0.23 = **$0.30 per run**, computed with `analysis.pricing.estimate_usage_cost_usd`; that is an estimated reservation, not observed spend. |
| Cost cap | `max_estimated_cost_usd_per_run: 0.35`, the ceiling the policy validator allows and the peer sources use; the shared guard reserves estimated cost before each call and refuses calls beyond it. |
| Activation changes | (1) a Korea desk manifest entry and `desk_registered=True`; (2) add `korea` to the desk-page machine-explanation filter in `site/preview/generate_preview.py`; (3) set `private_model_processing`, then `public_machine_explanation` and `unattended_release`, with a dated `owner_decision`; (4) add the `DAILY_KR_POLICY_DAPA_RELEASES_KEY` secret on both private and public sides; (5) m0021 itself: the daily workflow runs `python -m migrations.cli --apply` before collection, so **merging this change applies m0021 to the production database on the next scheduled run**. Rehearsed on a scratch copy of the tracked `pla_watch.db` at 0020: all 6 existing rows (AFP 4, NSC 1, Kemhan 1) survive byte-identical, `integrity_check` is `ok` and `foreign_key_check` is empty. |
| Release steps | Merge (m0021 applies on the next daily run; confirm the schema is at 0021 with rows intact) → enable private processing only and review the private outputs for one run → enable the public explanation → enable unattended release → verify the deployed Record page (link-only, attribution, no Korean text) and the validator's governed-warning baseline. |

**Genuine blockers:** the owner's approval of the proposed model pair and
provider retention/training terms, and the owner's merge (which applies m0021
to production on the next daily run). Neither is authorized here.
