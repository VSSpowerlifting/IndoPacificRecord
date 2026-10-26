# Government Office document integration — 25 October 2026 receipt

**Status: the approved 10744 correction is published as article 5646.**
Private correction, independent factual review, authenticated public admission,
production database, generated article and live HTTPS readback have succeeded.
The browser readback additionally identified missing direct Desk presentation;
the common renderer now lists admitted explanations and links the retained
bibliography. Post-deployment Desk/Archive browser evidence belongs to the
presentation release PR. Historical rejected attempts below remain recorded.
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
immutable source version are now spent. At that checkpoint no corrected generation or repeated
factual review had been authorized or attempted; the later single owner exception
and its actual execution are recorded below. Final private Daily commit:
`3599a8af74cd1498957c7902b48203760fe00a9d`; approved VPCP handoff records: zero.

## Initial document dispositions before the one-time correction

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

## Historical expenditure before the one-time correction

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

## Historical production readback before the one-time correction

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


## Actual correction and consumer-boundary readback (25 October)

The single approved correction has executed and **must not repeat**. PR #874,
head `cf1d9fadcde10254836ee1debb74af7021ba4e47`, passed required full CI
`40215557973` (7,995 tests, 15 skips, Chromium, render, validator 10 warnings,
tracked-data preservation) and merged as
`46298fe95ccb50b472a7908b1e5716b71cd56dcc`. Private workflow main remains
`42bf7adbf54ed2bdcdc83ffe3e56c3d8d88a118e`, with exact workflow SHA-256
`761d08439b1e27123b40ec0321e6d88dac123cd6eacd5bd869f6aa3ce496116f`;
no further private workflow patch was necessary.

Private Daily [40217218707](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/40217218707)
made exactly two successful Sonnet calls: corrected generation then independent
factual review, no relevance repeat. The accepted explanation is 65 words and
its headline is 20 words. Private Daily commit
`7fa140ec8b80c0677370ffe6d22d7963d7adb008` retains the prior rejection and
corrected reading; every other VPCP ledger item and the MPS ledger are unchanged.
The source remains the approved complete two-page 10744 PDF/version. Its
processing provenance pins source archive commit
`ba58d2bc38e1c73f7aa6e11b00e0f3758a0aa8c8` and the existing sealed rights decision.

Provider-returned usage: 4,137 input and 704 output tokens, zero cache tokens,
**$0.022971** at freshly verified prices. Correction reservations were
**$0.08767125**, below the $0.15 allowance. Cumulative history is **13 calls,
$0.185636 token-based cost, $0.61798 reserved**. Checkpoint blob
`1a6ce3bfc036522b678bd68287d3ec9c69b62d85`, SHA-256
`ef8dc12bdff2e3f75e4e3918bd2403171307601fd264136506d8483c11ae708e`, preserves
all original run/routes and adds the one correction receipt. UTC 25 October
reservations total $0.30530875; calendar-month reservations total $0.61798.
These are provider-token charges at official prices, not a retrieved invoice.

Public Daily [40217519927](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40217519927)
passed its full offline suite (7,995/15), 55 reconciliation checks, pipeline,
validator and deployment. Production commit
`c6df7a123fbeb061537845886091b8bbd4c5d30e` and Pages commit
`7f6ad86008d92be8ea7595dc882e012d7f382cfd` deployed through successful Pages
run `40219969391`. **This did not publish the VPCP record.** Independent database
readback found zero VPCP articles. The admission report explicitly held with
`vietnam_handoff_source_hold`; its successful workflow step preserves other
desks after a hold and is not an admission receipt.

The defect is the consumer's legacy original/link hold map, which assigns the
MOIT consent/robots hold to every non-MPS family, including VPCP. The narrow
consumer repair routes only the VPCP private projection through its dedicated
permission gate, owner-sealed decision, envelope MAC and document/second-pass QA.
The general original/link hold and all other families' holds remain intact.
A regression now goes from private signing through actual public verification
and admission, including policy denials, rejected QA, forbidden originals,
idempotency and MPS-hold compatibility. The existing signed approved record can
be admitted after the repair without any new model call. Exact-head CI and
actual source-to-live readback of that repair remain required.


## Actual public admission and presentation release

Consumer PR #875, head `8cf858572ae043674f9def688bf6c696c22fd243`, passed
exact-head CI `40220705488` (7,996 tests, 15 skips, browser, renderer,
validator ten warnings, tracked-data preservation) and merged as
`6475e9d92ecc89d7bd5d0f19d3d4b3461d30d085`. It changes only the VPCP private
projection boundary; the legacy original/link holds and other-family policy
remain enforced.

Public Daily [40237439135](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40237439135)
ran the mandatory 7,996-test suite (15 skips), database-preservation and
reconciliation gates, normal pipeline, output validator and deployment.
The actual admission report was `status: OK`, `counts: {published: 1}`,
`run_id: 40217218707-1`; this is not inferred from a successful step.
Production commit `9d6d690efd3de0b6b17dd0a233d00b67ad51f508` and telemetry commit
`fdb3cc8973753c3cb2db4ae4ad0425839f6bd94d` preserve the concurrent AFP metadata
and Sunday handoff repairs. No other desk pipeline or worktree was edited.
Pages [40239937602](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/40239937602)
succeeded at `985992425fc7049c9105a0d95221b47b04779d4b`.

The production database has genuine article **5646**, source `vpcp-vi:220065`,
issued 21 October 2026. Its PDF/content/metadata identity is the exact approved
10744 version above, source archive commit
`ba58d2bc38e1c73f7aa6e11b00e0f3758a0aa8c8`, sealed rights decision
`cb8daea696a892936be617f64dca2988d5d77dd402fdb42cab29d3ab22995f65`,
positive independent QA, two complete pages and 65-word English explanation.
The 20-word headline plus explanation total 85 words. Database integrity and
foreign keys pass; original title, original body and complete translation are
null. Generated and live [article](https://indopacificrecord.org/record/5646.html)
returned identical SHA-256
`7db74272acbee32f4deb79b6f9c69e2504112e5cea1ee38dac96e8bbf9eee850`.

The first Desk browser readback correctly failed: the common desk page exposed
only the metadata entry, despite the accepted article being in the corpus and
Archive. The repair reuses the ordinary `_records.html` rows for the latest
admitted, published Vietnam explanations. Matching bibliographic entries link
to their English record; the bibliography remains separate and cannot admit
private captures or held documents. Metadata copy no longer falsely says the
PDF has never been read. The renderer changes no database or other desk page.
The ordinary source page continues to link to its filtered Archive; it has no
per-article list for any source. It is checked as that source-navigation surface,
not treated as a second article renderer.

No new Government Office model calls were made by public admission or this
presentation repair. Read-only reconciliation after the public run confirmed
**13 calls, $0.185636 provider-token cost, $0.61798 durable reservations**,
unchanged checkpoint blob `1a6ce3bfc036522b678bd68287d3ec9c69b62d85` and file hash
`ef8dc12bdff2e3f75e4e3918bd2403171307601fd264136506d8483c11ae708e`.
The manual allowance is consumed permanently; 10790 and the other holds remain
unchanged. Existing active collection, private bridge and public Daily schedules
provide the unattended first-pass path under the original caps and source-use
exclusions. Quyết định remain held for individual administrative classification;
unsupported extraction/attachments, factual errors and material version drift
remain individual exceptions, not permission to retry paid routes.
