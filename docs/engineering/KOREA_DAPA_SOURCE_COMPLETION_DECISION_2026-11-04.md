# Korea DAPA — source-family decision candidate and offline integration candidate

**Prepared:** 2026-11-04. **Disposition:** DECISION CANDIDATE plus one verified
offline candidate; **no source activation, publisher contact, model spend,
merge or deployment**. **Owner chose option A on 4 Nov 2026 (see §8)**; the
other §8 items remain open.

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

## 3. Result of the offline candidate (no network, no model)

| Identity | Result |
| --- | --- |
| `156786758` | **CANDIDATE** — re-run end to end on 4 Nov against the pinned archive (`shadow.db`, HWPX and page capture all hash-matched, `--page-capture` supplied, `network_requests: 0`). HWPX `1d019223…b415`, 6 body paragraphs, 1,035 characters, selected-prose SHA `fc1caba6…bc0b`. The final paragraph is a quotation whose speaker attribution needs human review. The Type 0 text mark replays from the captured page (mark digest `27af6358…7700`, scope `article_text_only`). |
| `156786687` | HOLD — joint release with an IP office (result of the 3 Nov run; not re-run). |
| `156786759` | HOLD — headline middle-dot variant. |
| `156787071` | Refused. |

Whether the captured page's body text is equivalent to the HWPX prose was **not**
verified in this phase; the stored text is the HWPX extraction.

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
2. Open: confirm public originals stay link-only under the 17 Oct policy, or
   amend it (option A assumes link-only).
3. Open: model input, provider and cost, decided separately, if at all.
4. Open: standing per-version rule (replayed mark plus screens) versus
   per-version sign-off. **Recommendation:** adopt standing routine eligibility
   for future exact-source versions that authenticate the same Type 0 text mark,
   sole DAPA issuer and approved exclusions, keeping changed/ambiguous versions
   held individually. This proposal is **not** a standing activation or release
   grant; provider/model/cost, Korean semantic review and public components
   remain separate decisions.

Verified here: unit tests for the replay, the candidate builder and the HWPX
auditor; the replay against the real preserved page. Not claimed: Korean
semantic review, English explanation, CI on the final head, merge, activation,
deployment or any live change.
