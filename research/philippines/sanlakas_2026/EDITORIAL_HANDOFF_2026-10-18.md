# Philippines AFP — Sanlakas / JPSCC editorial handoff (18 October 2026)

**Status:** metadata-only engineering handoff, **not** a human-reviewed manuscript, final research packet, publication authorization, or a new editorial queue. Reuse the existing Philippines research/editorial intake and PR #661; do not create a competing draft.

## Exact preserved evidence references

Derived from the existing `source_event_candidates.json`. These identifiers and hashes point to historical preserved captures, not a claim of fresh live-source inspection. Refer to the existing original evidence under proper access controls for substantive review; do not copy original texts into public Git or Actions.

- Source branch: `shadow/ph-afp`
- Exact historical evidence commit: `492001f34ba6176169b6acc96a237f05592a3395`
- Stored state DB blob: `e42f8f0dde480a99452d89bcfc7ee84b5aa55f13`
- Collector attempt: `37631681338-1`
- Source institution: Armed Forces of the Philippines (AFP); AFP statements are publisher claims, not independent corroboration.
- Source language: English in these four records; do not invent an English translation process.

| Identity | Publisher timestamp (+08:00) | Official AFP URL | Stored content SHA-256 | Original capture SHA-256 |
|---|---|---|---|---|
| `afp:1390` | 2026-09-30 12:22 | https://www.afp.mil.ph/news/afp-pnp-pcg-strengthen-joint-peace-and-security-coordination | `c51136832b8271f81957a021bc68b6588fa7e1d65fff4ca9979ec74593e2faea` | `4120dd834b5bb5fbce8616f51e5bf0fe8c1c4fc289c04476187d2af48b4fc864` |
| `afp:1391` | 2026-10-01 12:24 | https://www.afp.mil.ph/news/afp-pnp-pcg-sustain-joint-readiness-through-2026-inter-agency-exercise | `2207cc71ef080ebfecbf35dba117ce775b3583b043415b39352a65622d62f724` | `721e5379732008b4a1ecfe9b45fe93b41200e9bda97243fef157f1247bcd22ae` |
| `afp:1393` | 2026-10-02 12:39 | https://www.afp.mil.ph/news/afp-pnp-pcg-strengthen-interagency-response-through-field-training-exercise | `b6b50aea327ea452e62f7ba0b9d5278c165a27da08686cbeddee65e5f54a71da` | `b00b39d3647c7786e2d63b8775125e7a1bbd790ec463b79e3d089a6f5df7bf64` |
| `afp:1394` | 2026-10-03 12:42 | https://www.afp.mil.ph/news/afp-pnp-pcg-conclude-interagency-exercise-pagsasanay-sanlakas-2026 | `0f99d426c5860b25788a152f7a487463bf6979db84915b58c9509b5817dce003` | `168ba1fba196d133676c68f8fd79365d86666473f0b9959185111fa795c51064` |

## Event grouping and facts requiring review

- `afp:1391`, `afp:1393`, and `afp:1394` describe stages of the **same AFP-reported Sanlakas interagency exercise**, not three independent institutional confirmations. Opening, field-exercise, and closing **event dates** differ from release dates.
- `afp:1390` concerns the **separate September 29 JPSCC meeting** and AFP-reported cyber-plan signing. Do not merge its event into Sanlakas merely because overlapping agencies participated.
- **Opening venue:** the source-event candidate flags differing venue indications; retain an unresolved location hold rather than geolocating by inference.
- **Gavan / Galvan:** the source-event candidate records divergent personal-name spellings; retain the exact source forms pending qualified review, without silently resolving identity.
- **Claims versus results:** AFP-reported participation and simulated disaster response are not independent proof of actual emergency or combat readiness. A reported signed plan is not evidence of implementation.
- **Source-use:** check applicable publisher terms and the API `X-Robots-Tag` evidence before any public content reuse. The October 15 owner authorization covers verified *neutral official-link metadata* for the approved AFP family, not AFP headlines, bodies, photographs, translations, model summaries, or publication of IPR analysis.

## Existing editorial route and smallest remaining decisions

The original research candidate and claim-to-evidence mapping remain at `research/philippines/sanlakas_2026/source_event_candidates.json`. The existing draft is [PR #661](https://github.com/VSSpowerlifting/IndoPacificRecord/pull/661); it has **not** received human source/semantic review, resolution of the two holds, publication-use clearance or owner/editorial approval.

A qualified reviewer should inspect the four referenced authentic originals against the manuscript, decide the outstanding venue/name treatment, confirm allowed citation/link use, and then use the **existing IPR editorial approval and publication process**. Do not use this metadata-only note as a substitute for any of those decisions.

The source-index admission engineering is a separate content lane: admitting verified official AFP links to public SQLite does **not** publish this manuscript or count these references as independently authored articles.

## Re-verification against private custody (19 October 2026)

This was a read-only check. It resolves neither hold, and it is not a human
source review.

- **Versions unchanged.** I compared the four records with the private AFP
  archive branch (`archive/ph-afp` at
  `d48bb3873fe3df554f5fbed5adaeafb7cdd6d876`). All four have the same content
  and capture SHA-256 values as the table above, so the pinned evidence has not
  drifted since the public writer was retired.
- **F02 (name).** The exact publisher strings are as recorded:
  - among these four records, `Galvan` appears only in `afp:1390`;
  - `Gavan` appears only in `afp:1394`.

  The external Gavan evidence cited in `README.md` remains a lead. It has not
  been admitted to the archive. The hold stays open.
- **F06 (venue).** All four AFP records carry a `CAMP AGUINALDO` dateline,
  including the field-exercise and closing stories. None names PCG National
  Headquarters. The observation is consistent with the dateline marking where
  AFP prepared each story, but that remains an inference. The hold stays open
  until an authenticated first-party PCG source is preserved.
- **Event grouping.** The private Philippines research packet
  (`scripts/ph_private_research_packet.py` in the private repository) reached
  its grouping independently, by keyword rules with no model:
  - it proposes `afp:1391`, `afp:1393` and `afp:1394` as possible repeat
    coverage of one exercise;
  - it does not cluster `afp:1390` with them.

  This matches F01. It is machine agreement, not editorial confirmation.

PR #661 remains an open draft. Its route is unchanged: a qualified reviewer,
then the existing editorial approval process.
