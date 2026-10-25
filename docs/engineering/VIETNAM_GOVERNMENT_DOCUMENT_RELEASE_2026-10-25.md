# Government Office document integration — 25 October 2026 receipt

**Status: technical integration merged and activated; public full-document
acceptance is NOT complete.** Real source collection, model generation and
independent factual review ran. Neither reviewed explanation passed factual QA.
No Government Office English explanation was admitted to production or deployed.
The completed October 23 metadata release, PR #863 and evidence `d8aa9ebc6e`,
remain intact and were not rebuilt.

## Authority and architecture

The October 24 owner decision covers `vn_vpcp_official_documents_vi`, verified
first-party Government Office Công văn and Thông báo primary PDFs, and only
individually confirmed administrative Quyết định. The current implementation
holds Quyết định for individual classification. The existing owner-sealed
source-use decision has SHA-256
`cb8daea696a892936be617f64dca2988d5d77dd402fdb42cab29d3ab22995f65`.
Its legal/publisher-access assessment is in
`VIETNAM_GOVERNMENT_DOCUMENT_TEXT_2026-10-23.md`, including the 2026 amendments.

Private originals, immutable PDF/content identities, the existing Anthropic
client, shared Daily processing, independent QA and ordinary record renderer
are reused. No second database, Government Office model engine or parallel
publication pipeline was created. The source-specific limits remain two
documents/run, $0.50/run, $1/day, $10/calendar month and 32,000 complete input
bytes/document. SDK retries, additional providers, Firecrawl PDF uploads,
public originals/PDF copies, full translations, substantial excerpts, images,
additional attachments and third-party annexes remain excluded.

The existing private workflow is
`.github/workflows/vietnam_private_first_collector.yml`, main commit
`42bf7adbf54ed2bdcdc83ffe3e56c3d8d88a118e`, SHA-256
`761d08439b1e27123b40ec0321e6d88dac123cd6eacd5bd869f6aa3ce496116f`.
The initial additive patch was applied only after the exact preimage
`c1bda60a6413b6a3ed1587ee36863c35402f99251ee563c684ce62d91c593378`
matched. Private CI `40113092411` passed 95 tests. Its manual VPCP action uses
that same workflow and preserves existing MPS conditions. Collection at 18:17
UTC, shared bridging at 20:17 UTC and the ordinary public Daily remain enabled.
No per-document approval was introduced for future eligible first-pass records.

## Merged code and exact-head CI

Each code revision passed the mandatory offline suite, Chromium launch,
ordinary rendering/output validation and tracked database/output preservation.
The validator retained the governed ten-warning baseline. No protection was
changed or bypassed; merges used the verified expected PR head.

| PR | Approved head | Merge commit | Required CI | Tests / skips |
| --- | --- | --- | --- | --- |
| #865 | `54eb9a39ec2ce67f4a79fd6cff42f1647fa92f59` | `4623535eb6c3be3b62ff94f30b2e2c6ce2b0e71a` | `40111052902` | 7,978 / 15 |
| #866 | `1c0e9e81456ac79a98c27e90e276f9088e6df966` | `7fe28116530b354fc6b456e74b8f8a60059c02fc` | `40114027350` | 7,978 / 15 |
| #868 | `01123f984ee5fc3956d6b7d69704e1c66c12c233` | `3c326f85ac27bb988baf30c4d8823215956c0b0b` | `40156015343` | 7,982 / 15 |
| #869 | `6646a92c24f0b92d2a2d71c802f412b608f09ac0` | `358d6f6752fb2ff8af90cb322d27f6a6eb27ba52` | `40161854298` | 7,984 / 15 |
| #870 | `317358b20b15ab5e91af2e0ba9b8ecba9f5fe0ca` | `d33e127a2c966365bf2ad8cf62b8204335e58a99` | `40186397670` | 7,988 / 15 |
| #871 | `0daf34f66058306d52e3c2951565ab56d5096ece` | `dd74966e8b145708521c2faa84fe844786c0acc9` | `40189895824` | 7,990 / 15 |
| #872 | `b002b62d46716f9d2743fca83ea195eff2856fa0` | `b735161305e3096a4006e7a6e9705ead48782429` | `40195436669` | 7,991 / 15 |

The final 112 focused contracts cover source identity/coverage, malformed and
updated files, unchanged reprocessing, denied policy/spend routes, retained
drafts, unresolved-hold settlement and existing MPS compatibility. Local
checks do not claim real factual-QA success. The unrelated AFP metadata update
`dc9fe6351c05155fcb595df3aa944f0d39e8408a` was preserved exactly: its database
blob `bc60e1a6b0ca5de2bf37a5fd02a65a76ec81910f` is unchanged in the code merges.
No dossiers worktree or other desk pipeline was modified.

## Real 10744/VPCP-CN attempt

The first page renders `10744/VPCP-CN`, issued 21 October 2026. Local raster/OCR
and pypdf agree with the portal. The second page contains only its page number;
the narrowly checked exception retains that page and excludes images/forms,
annotations, extra text, paint, unknown operators and unsupported fonts.

- PDF SHA-256: `121670635f065b0ecb1ef38641c5236d634fc5777dc3aa1cc0330caf7580f575`.
- Complete source: two pages, 2,778 UTF-8 bytes; content SHA-256
  `842585a4cc35857bf6301e55228c7662d03adc3eeb1bed3a3872cfd3916db56e`.
- Metadata SHA-256: `4bf6537753bfdbed85f39359a596b4de6ce17eb6a3c7d3aad9ee76d4f2a7d695`.
- Private capture descriptor:
  `7208538640bc6f7e6ff1a676f3f6f7955eb063f53ea8cc41796b8379787f4d4d`.
- Capture run `40188963795`; source archive commit
  `1c5e7228010536d09f0050cdc549d55d4de0c4e6`.

Bounded collection runs `40188357997`, `40188659775`, `40188815487` and
`40188963795` succeeded. Each processed at most two PDFs and made zero model
calls. Collection stopped as soon as this source version was captured.

Bridge `40189202615` made the first relevance and generation calls, costing
$0.017751. Its 86-word draft had three literal page citations. Mechanical
false holds concerned verified header numbers and the expanded abbreviation
PM; they were fixed without regenerating the draft. Bridge `40192646938`
made zero calls because deterministic QA stopped before factual review.

The original paid reading remains in private Git commit
`3364d3072421ffd13450ac2e29db705c8705d95c`. One-time recovery commit
`1c2b0b8e53070d4400718f59f4c6b522c1b83b0f` restored the identical reading and
original generation-run identity against exact ledger preimage
`41d2e515afeb1f892ded8b40b435224713127d07`. Its reading SHA-256 is
`26efd68a6cd71b95605da9fe7ed833d098ce675bfc428378612d91ace7066ed7`.
Readback confirmed that the MPS ledger, signed handoff and spending checkpoint
were unchanged by recovery. The original QA hold was retained.

**Bridge `40197695872` executed exactly the first factual-review call.** It
returned `ok: false`, `E_SECOND_PASS`: the explanation assigned instructions
to the Government Office when that office was conveying the Prime Minister's
instructions. The draft remains held, and all three paid routes for this
immutable source version are now spent. No corrected generation or repeated
factual review has been authorized or attempted. Final private Daily commit:
`3599a8af74cd1498957c7902b48203760fe00a9d`; approved VPCP handoff records: zero.

## Current document dispositions

| Official document / portal identity | Disposition |
| --- | --- |
| 545/TB-VPCP / `220078` | Paid draft was not retained by the initial format-hold implementation; held, no regeneration. Verified PDF/identity retained privately. |
| 10747/VPCP-CN / `220079` | Same initial unavailable-draft hold; no regeneration. |
| 10790/VPCP-CN / `220077` | First factual review `40157663479` rejected reassignment of a ministry responsibility to provincial chairpersons. Held, no repeated review. |
| 10744/VPCP-CN / `220065` | First factual review `40197695872` rejected issuer/decision-maker attribution. Held. |
| 543/TB-VPCP / `220061` | Primary PDF identity/signatory and five text-bearing pages pass locally, but an enclosed-annex reference remains unresolved. Source-use/completeness hold; no model transmission. |
| 536/TB-VPCP / `220041` | No pypdf text layer on any of three pages. Held; no Firecrawl upload or unsupported OCR claim. |
| 535/TB-VPCP / `220030` | Source captured; first relevance call screened it out in `40163894928`. |
| 10667/VPCP-KGVX / `220040` | Source captured; deterministic body-topic screen excluded it without a model call. |
| 10610/VPCP-PL / `220024` | Source captured; same body-topic exclusion, no model call. |

A fresh successful first-page listing read made two requests, fetched no detail
page or PDF, and found no new Government Office identity in the existing
50-entry discovery window. Listing SHA-256:
`869cb8277aad9c4c3395e354cd955d3a33a5626b8370971851989fa2b7e3f825`.
This is a quiet bounded frontier, not an access failure or proof that the entire
government portal has no other documents. No broader crawl was attempted.

## Expenditure and durable reservations

Provider-returned usage reconciles to **11 API calls, $0.162665** at the freshly
verified standard prices. This is token-priced usage, not a separately retrieved
billing invoice. The last factual review returned 2,240 Sonnet input tokens and
179 output tokens, costing **$0.009405**. Relevance/generation were not repeated.

Durable worst-case reservations total **$0.53030875**: $0.31267125 on UTC
October 24 and $0.21763750 on UTC October 25. Every run is within $0.50, each
day within $1 and the calendar month within $10. No reservation was refunded or
reset. Authoritative checkpoint blob:
`a7421c998518a197249e3ed66edca21ca4d5428f`; file SHA-256:
`b5db4e65a3dee59c2ec2d9cb55d64d300cbdc114d1f193e7abbd60edf2326068`.
The `10744` entry records generation `40189202615-1`, first review
`40197695872-1` and exactly the existing relevance, generation and review
routes. Pricing or checkpoint uncertainty still fails closed before dispatch.

## Production readback and remaining release constraint

At main `b735161305e3096a4006e7a6e9705ead48782429`, the production database
retains **four VPCP bibliographic records and zero VPCP corpus articles**.
The live [Vietnam Desk](https://indopacificrecord.org/vietnam.html),
[Government Office source page](https://indopacificrecord.org/source/vn_vpcp_official_documents_vi.html)
and [Archive](https://indopacificrecord.org/archive.html) return HTTPS 200.
Those responses do not prove a new explanation: there is no accepted/generated
VPCP article and no new full-document publication URL. No public Daily was
dispatched after the final rejection. The earlier acceptance attempt
`40158637403` was canceled at its offline gate after its candidate failed
factual QA; it did not publish a Government Office explanation.

The owner has now approved **one** manual correction for this exact immutable
10744 version, confirmed twice without adding an allowance. The dated
`DECISION_LOG.md` entry binds the source, PDF and metadata hashes and prior
generation/rejection runs. At most one shared corrected-generation call and one
independent factual review may reserve **$0.15 additional total**; all existing
source-use, provider, input and aggregate spending caps remain unchanged. Other
holds remain settled. The attribution repair removes compulsory issuer names
from each private fact sentence, retains public source attribution, and requires
the actual actor/action supported by page evidence. Independent factual review
explicitly rejects issuer/instruction-giver and ministry/provincial confusion.

Only a manual private Daily bridge dispatch can use this allowance. The CAS
checkpoint appends a separate correction receipt within the same immutable
document entry, preserving all old routes and costs. One generation and then one
review in the same run are the only allowed additional routes. A failed stage
cannot continue automatically; the private ledger retains the previous rejection
and corrected reading. Exact-head CI and actual execution remain to be verified.
Future eligible first-pass documents use the already active shared pipeline.
Full-document source-to-live acceptance remains outstanding.
