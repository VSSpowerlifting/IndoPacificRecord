# Philippine NSC — rights and release decision (owner)

**Status (19 October 2026): the owner has not decided.** This document sets out
the decision. It does not make it. Both flags in
`config/ph_nsc_official_link_policy.json` are `false`, and admission holds with
`nsc_category_anomaly_unresolved` or `nsc_metadata_publication_not_authorized`
until the owner changes them.

The AFP standing authorization (DECISION_LOG, 2026-10-15) does not extend to
NSC. An accessible government website, or its `robots.txt`, does not grant a
full-text licence.

## Source as observed

- **Family:** `ph_nsc_official_statements`. Source:
  <https://nsc.gov.ph/category/official-statements/>. English originals, so no
  translation step applies.
- **What exists.** A live check on 2026-10-02 found six statements dated
  2026-06-03 to 2026-07-08 and no pagination. No statement has been posted
  since 2026-07-08.
- **Schedule.** The public schedule ran from 2026-10-02 with a six-day
  lookback. Every window since has been quiet, so the shadow state
  (`shadow/ph-nsc`, `1a313e04` as of 2026-10-19) holds **zero** records. The
  public schedule keeps advancing the tip until the retirement merges; the
  private seed reads the tip at that point. The six earlier
  statements predate every collected window. They are not missing captures,
  and none has been backfilled.
- **Rehearsal.** A bounded rehearsal on 2026-10-02 fetched `nsc:3108` and
  `nsc:2269`. It wrote nothing to a database or to output. It proves access
  and extraction only; it is not a stored record.
- **Category anomaly.** An earlier observation found gambling content in the
  category. It did not reproduce on 2026-10-02. It is neither dismissed nor
  treated as proof of compromise (`shadow/ph_nsc/README.md` item 5).

## The seven decisions

| # | Use | Current position | Who decides |
|---|---|---|---|
| 1 | Private preservation of originals | Implemented in private PR [ipr-source-evidence-private#19](https://github.com/VSSpowerlifting/ipr-source-evidence-private/pull/19): `archive/ph-nsc` continues the frozen public history. | Owner merges #19. |
| 2 | Public URL, publisher date, publisher identity and attribution | Not authorized. The pipeline is built and tested, and holds at admission. | Owner: standing flag, or a sealed exact-version decision. |
| 3 | Original title in public | Not authorized. The envelope cannot carry a title. | Owner, separately from #2. |
| 4 | Short excerpts | Not authorized. No pipeline exists. | Owner, after the source's terms are reviewed. |
| 5 | Full text | Not authorized. It stays private. | Owner. Website access is not a licence. |
| 6 | Model processing of the text | Not authorized. The private research packet uses keyword rules only (`model_processing: none`). | Owner, including the spending limit. |
| 7 | IPR-authored reporting that cites NSC | Allowed through the existing editorial route: an analyst writes, an editor reviews and the owner approves. It cites the official URL. | The existing Sunday Brief workflow. |

## How the owner records a decision

- **Standing link publication.** In
  `config/ph_nsc_official_link_policy.json`:
  - set `standing_metadata_publication_authorized: true`;
  - set `owner_decision_reference` to a DECISION_LOG entry;
  - set `category_anomaly_resolved: true` with `category_anomaly_reference`.

  Each flag needs its own reference, or the policy is refused.
- **Exact-version release.** Leave the standing flag `false`. Seal a decision
  with `NSC_RELEASE_REVIEW_KEY`. The decision binds:
  - the candidate digest;
  - the approved identities;
  - the reviewer;
  - the date;
  - the rights basis;
  - the custody reference.

  The production workflow verifies the seal. A sealed decision does not lift
  the category-anomaly hold.

Neither path publishes titles, text, images, translations or model output. The
envelope carries only these fields: `source_identity`, `canonical_official_url`,
`publisher_posted_date` and `official_publisher`.

## Release order and its risk

1. Merge the private PR #19.
2. Merge the IndoPacificRecord PR that retires the public NSC writer.
3. Dispatch `seed_frozen_public_history`. It creates `archive/ph-nsc` at the
   frozen public tip, without force.
4. Dispatch `collect_after_cutover`. Then set
   `NSC_PRIVATE_SCHEDULE_ENABLED=true` (daily at 10:10 UTC).
5. Optional: configure the bridge. It needs the variable
   `NSC_METADATA_BRIDGE_ENABLED`, the secret `NSC_BRIDGE_KEY` (separate from
   `AFP_BRIDGE_KEY`) and the secret `IPR_PUBLIC_BRIDGE_TOKEN`. The bridge only
   signs and dispatches. Publication still requires a decision above.

**Gap warning.** Each run looks back six days. If more than six days pass
between step 2 (the public writer stops) and the first private run in step 4,
publications from those days can be missed. Recover them by dispatching
`collect_after_cutover` with an explicit `target_date` for each missed UTC
day. The private runbook is `docs/PH_NSC_PRIVATE_FIRST_RUNBOOK.md` in the
private repository.

## Screening and editorial path (both Philippine families)

The private `scripts/ph_private_research_packet.py` builds a deterministic,
no-model packet from one pinned private state commit. For each record it holds:

- identity and immutable versions;
- publisher chronology, kept separate from event chronology;
- screening labels, so no record is discarded;
- proposed repeat coverage;
- existing research references;
- the rights position.

Analyst fields start empty.

Packets stay private because they contain original titles. They feed the
existing Sunday Brief through its existing topics:

- `maritime_security`;
- `alliance_diplomacy`;
- `defense_exercises`.

An item enters the public weekly evidence pack only once its title or text
rights permit. There is no Philippines-only Brief, queue or manuscript schema.
