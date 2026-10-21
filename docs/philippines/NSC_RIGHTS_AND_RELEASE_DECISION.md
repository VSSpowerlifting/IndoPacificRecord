# Philippine NSC — rights and release decision (owner)

**Owner decision (20 October 2026):** Standing neutral-link metadata and narrowly
attributed, nonverbatim NSC machine explanations are authorized, under the
specific limits and source-quality conditions recorded in `DECISION_LOG.md`.
This decision is separate from AFP. The two NSC policy files now reflect it,
but **authorization alone does not prove that a record was captured, admitted,
processed, or published**. Initial private NSC custody contains zero article
records; historic July material needs genuine private collection and admission
before model processing. An accessible government website or `robots.txt` does
not grant a full-text licence.

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
  category. The Oct 2 direct collector examination did not reproduce it; an
  independent Oct 20 review of the official category found six coherent,
  canonical official-security statements dated June 3–July 8, with no such
  unrelated content. The owner authorizes **bounded clearance of this historical
  observation only**. The collector must still refuse a mismatched host,
  category, canonical permalink, template, article identity, capture, date,
  or source provenance. Recurrence automatically holds affected records; this
  is not a permanent guarantee that the site is uncompromised.

## The seven decisions

| # | Use | Current position | Who decides |
|---|---|---|---|
| 1 | Private preservation of originals | Implemented in private PR [ipr-source-evidence-private#19](https://github.com/VSSpowerlifting/ipr-source-evidence-private/pull/19): `archive/ph-nsc` continues the frozen public history. | Owner merges #19. |
| 2 | Public URL, publisher date, publisher identity and attribution | **Authorized standing, neutral metadata only** on official, verified NSC permalinks. | Owner approval Oct 20. |
| 3 | Original title in public | Not authorized. The envelope cannot carry a title. | Owner, separately from #2. |
| 4 | Short excerpts | Not authorized. No pipeline exists. | Owner, after the source's terms are reviewed. |
| 5 | Full text | Not authorized. It stays private. | Owner. Website access is not a licence. |
| 6 | Model processing of the text | **Authorized narrowly for first-party factual statements:** the same private shared Daily engine as AFP, nonverbatim 90-word maximum, clear NSC-website attribution, machine label and source URL. No original titles/bodies/images public. One record/two intended calls per run, $0.35 estimated/run, zero SDK retries, five failed attempts then hold. Publisher is not presumed issuer. | Owner approval Oct 20; distinct from editorial Brief approval. |
| 7 | IPR-authored reporting that cites NSC | Allowed through the existing editorial route: an analyst writes, an editor reviews and the owner approves. It cites the official URL. | The existing Sunday Brief workflow. |

## Current activation, not a new architecture

1. Recover the genuine July 8 statement using the already-built private collector `collect_after_cutover` with explicit `target_date=2026-07-14` (six-day window). Verify publisher URL, canonical identity, original captured bytes, actual date, and original/issuer attribution. Do not publish from the website or prior synthetic fixtures alone.
2. Use the existing NSC signed metadata bridge to admit the official link into the shared public `regional_official_source_links`. Provision `NSC_BRIDGE_KEY` securely in private and public repositories, and the private repository's limited public Actions dispatch credential. Enable `NSC_METADATA_BRIDGE_ENABLED`. If the collector only signs after a new attempt, dispatch its existing `collect_after_cutover` again with an explicit date after credentials are set; do not invent a separate workflow.
3. Configure matching `DAILY_PH_NSC_OFFICIAL_STATEMENTS_KEY` in both repositories. The already enabled shared private Daily processes one verified, **publicly admitted** NSC source; manual dispatch can follow link admission. If the model output fails source-grounded quality, hold that record and select another genuine statement rather than weakening the controls.
4. Dispatch the existing public `daily_update.yml` to admit the signed machine output and deploy its machine-labeled record, Philippines Desk, and archive/search. Read back actual live HTTPS and confirm AFP remains unchanged. Normal private NSC collection and the shared Daily then run unattended. A quiet new-publication window remains a valid no-op.

No NSC original titles, source bodies, captures, photographs, verbatim excerpts, or unrestricted republication are authorized by this decision. No claim of live NSC publication is made before the above deployment succeeds.

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
