# Government Office primary documents — bounded full-text integration


**Owner release decision, 24 October 2026:** the standing authorization below
was explicitly approved in chat, recorded in `DECISION_LOG.md`, and sealed by
private Actions run `40110461989` using the existing source-use key. The signing
job verified the existing MPS seal before producing the VPCP envelope; collection
and model processing did not run. The current release still requires final
exact-head CI and real production acceptance.

The activated policy enforces two documents/run for collection and processing,
holds unconfirmed administrative Quyết định, and uses complete numbered-page
input without truncation. Before each private processing run it verifies the
provider's current public pricing table against the two pinned model rates.
Before each call, a required, preinitialized CAS spending checkpoint reserves
worst-case cost and records the immutable document version plus route. A missing
checkpoint or repeated paid route fails closed. A format-held retained draft may
complete its previously unexecuted mandatory factual review in a later run;
relevance, explanation and factual-review calls are each dispatched at most once
per immutable version. This does not retry a failed factual review. API-returned
token usage is retained alongside the existing private Daily state.
This follows the completed metadata release at `d8aa9ebc6e`. It does not
reopen PR #863 or change the operating bibliographic collector. The owner has
authorized technical implementation and bounded local assessment, **not new
external-model transmission, spending or explanatory publication**. The latter
remain false in `config/vietnam_vpcp_text_policy.json`; no owner decision is
invented or signed. `config/vietnam_vpcp_owner_request.json` is an unsigned,
all-held request template, not authority.

## The 545 identifier mismatch is resolved

The existing private PDFs were re-hashed locally against the October 23 access
receipts; no further PDF fetch was necessary:

| Document | PDF SHA-256 | Pages |
|---|---|---:|
| 10790/VPCP-CN | `b4ed9b383d46331baff568eaf30d191d8fae302fb9bb99f3aa9e3f675184e2df` | 4 |
| 545/TB-VPCP | `f37efe49b108798c500389c7ea2dad7715f38f416c68add853ed94fe41b940ea` | 5 |

`pdftoppm` rendered each first page locally. Local macOS Vision OCR read the
visible `545/TB-VPCP` and 22 October 2026 header. Direct `pypdf` inspection
explains the discrepancy: ordinary page text has `Số: /TB -VPCP` and blank
number/date slots, while four visible `/Widget` normal appearance streams
supply `545`, `22`, `10` and `2026`. Their rectangles are respectively
`[147,729,176,743]`, `[401,730,425,744]`, `[456,730,480,744]`, and
`[504,730,542,744]` on the A4 first page. This is an omitted appearance layer,
not an absent or contradictory identifier. The portal operator's later
signature timestamp is a distinct fifth annotation and is not the issue date.
Neither image nor original body was uploaded to a hosted model/parser.

The checker reads `pypdf` page text first, then only numeric normal appearance
streams in the observed header slots. It does not trust hidden field values,
filenames, portal metadata as replacement text, signature timestamps, or OCR
confidence. Unicode normalization, whitespace and typographic hyphen differences
are accepted; changed digits, issuer, date or signatory, hidden/ambiguous
appearances and genuinely missing fields hold. Unknown layouts hold instead of
extending the accepted typography speculatively. Digital-signature cryptographic
validation is not claimed.

## Source-use assessment, including 2026 amendments

This is a bounded engineering/source-use assessment for owner review, not a
publisher licence or a legal opinion.

The official [67/VBHN-VPQH consolidation of 23 March 2026](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-67-vbhn-vpqh-469197.htm)
incorporates [Law 131/2025/QH15, effective 1 April 2026](https://congbao.chinhphu.vn/van-ban/luat-so-131-2025-qh15-468691/61687.htm).
In its [official text, printed page 16](https://congbaocdn.chinhphu.vn/180507251028987904/2026/4/10/469197-1775632354_v1_1775783230_signed.pdf),
Article 15(2) still excludes normative legal, administrative and judicial
documents and their official translations from copyright protection. The 2026
amendment adds Article 15(4), covering ideas, slogans and standalone work titles;
it does not remove paragraph 2. Article 7(5), printed page 10, adds conditional
use of lawfully published, publicly accessible material for scientific research,
experimentation and AI training, with further government rules for copyrighted
material. That is not treated here as blanket permission for production
inference or third-party transmission.

[Decree 30/2020/NĐ-CP, Article 7](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-30-2020-nd-cp-30858/30246.htm)
lists formal notices and official communications among administrative document
types. **Inference:** the verified Government Office-issued Công văn and Thông
báo primary documents fit that classification. Hosting alone establishes
neither formal issuer nor the classification of separate attachments. Reports,
photographs, charts and third-party annexes can have separate rights; the lane
holds additional attachments, annex indications and embedded files.

The [publisher's current identification and footer](https://vanban.chinhphu.vn/gioi-thieu-69424)
request attribution to the Government Information and Communications Department
or chinhphu.vn. That attribution condition is retained; it is not construed as
an unlimited licence. Publisher correspondence is not assumed necessary merely
to report official facts. No official term expressly granting external-model
use was established by the reviewed pages.

| Distinct use | Current treatment |
|---|---|
| Copyright status | Narrow administrative-primary-document assessment; no blanket attachment exemption |
| Lawful access | Honest verified HTTPS, exact host/path allowlist, robots/access refusals honored; existing October 23 receipts retained |
| Private custody | Technical implementation ready; production collection flag and owner grant still required |
| Third-party model transmission | Held pending source-specific owner authorization; MPS grant is not inherited |
| Public explanation | Proposed independent, attributed English explanation, at most 90 words, machine-labeled and page-supported |
| Public originals, PDF copies, complete translations, excerpts and annexes | Excluded from this proposed release |

## Shared path and safeguards

The transport salvages the stash's screened PDF adapter, and the shared PDF
extractor now exposes numbered pages. The prototype's optional register crawler,
blank-header acceptance and public-Daily PDF hook were **not** adopted. Its
metadata-source assertion repair is already in production. Stash `c9272b85`
remains intact.

The private source uses the existing evidence repository and a source-specific
`archive/vietnam-vpcp` ref. Immutable `state/captures/<PDF hash>.bin` and
`state/documents/<capture hash>.json` preserve every version; a small JSON index
selects current versions. There is no second article database. Captures are
MAC-bound under a distinct domain using the existing private bridge key, and
replay verifies the pinned Git branch, PDF/content/metadata hashes and successful
private collector Action. Revisions retain prior bytes; unchanged versions reuse
their processing result. Changed published versions are held by the existing
material-change rule, never silently overwritten.

Retrieval is capped at six exact primary files/run, five MB/file and 40 pages.
Unseen metadata versions precede rotating rechecks. Missing, failed, sparse or
lost pages, encryption, identity disagreements and source restrictions hold.
The bounded strategic vocabulary is applied to actual document contents;
paid relevance screening then uses the shared Analyzer, bound to the current
public bibliographic version. A missing/changed public metadata reference holds
before any model spending. Metadata fallback remains
independent when source-text access, policy, processing or QA fails.

The existing Vietnam Daily bridge, private ledger, signed handoff,
`articles`/`vietnam_article_provenance`, normal record renderer and Archive are
reused. Migration 0019 only widens that provenance table's family constraint;
it grants nothing and publishes nothing. Public scraper profiles remain disabled
for VPCP models. MPS/MOIT collection descriptors and source-use decisions remain
separate. New VPCP failures are isolated in the existing multi-family bridge.

Explanations cover the formal instrument, responsible authorities, explicit
instructions/deadlines and conditional or proposed actions. They must not invent
implementation, financing, legal effect or strategic interpretation. Every
sentence requires private evidence on a numbered page; numerical/modality and
source-copy checks plus existing Vietnam QA run before a mandatory bounded
second factual check. Public provenance carries hashes/page references, not
supporting Vietnamese passages. Original bodies and full translations stay out
of the public database, handoff and site.

## Concrete standing authorization proposed for approval

Approve first-party Government Office Công văn, Thông báo and individually
verified administrative Quyết định primary PDFs for compliant unattended private
custody and transmission of complete, identity/coverage-passing Vietnamese text
to the existing Anthropic API client. Permit independent English factual
headlines, explanations of at most 90 words, source attribution, official links,
event labels and automatic ordinary record/Archive publication after the
source-specific QA gates. No routine per-document owner review; hold genuine
rights, authenticity, source-version or fidelity exceptions individually.
Exclude originals, public PDF copies, full translations, substantial excerpts,
images, additional attachments and third-party annexes. No Firecrawl PDF upload
or other hosted parser is authorized by this proposal.

Proposed ceilings: **two documents/run; $0.50/run; $1/day; $10/calendar month**,
with at most 32,000 input bytes/document, no SDK retry, and no automatic cap
increase. Each model call reserves its conservative worst-case priced input
and maximum output in `state/vpcp-spend.json` on the existing private source
archive **before dispatch**, using GitHub's compare-and-swap contents update.
Reservations survive failed jobs and are never refunded; an unavailable,
conflicting or exhausted checkpoint prevents the call. Relevance, explanation
and mandatory factual review are the only allowed model routes; all feed the
existing usage telemetry.

Approval was recorded on 24 October 2026 in the existing owner-sealed source-use
decision and explicit VPCP policy fields. Actual activation and production
acceptance remain separately verifiable release steps.
The source-use review key remains separate from the capture/handoff key.

## Release configuration prepared, not activated

`ops/vpcp-private-workflow.patch` is the exact additive change to the **existing**
private Vietnam collection/bridge workflow, with pre/postimage hashes in its
adjacent JSON manifest. It adds a default-off collection step, the source archive
ref and VPCP bridge arguments; no new scheduler or model engine. It has not been
applied to the private repository. Apply only after the same owner authorization,
public exact-head CI and current private workflow preimage match; preserve
repository protections. An absent decision or archive does not stop MPS.

The operating public metadata flag and completed October 23 deployment are not
changed. Full-document source-to-live-site verification must follow actual
approval and one genuine production record; offline and cached-PDF checks do not
substitute for it.

## Offline evidence before PR CI

The combined Vietnam bridge/handoff, existing MPS compatibility, PDF extraction,
VPCP document and transport contracts passed 135 focused tests. After the final
citation/Archive and proof refinements, 45 targeted contracts passed, including
an ordinary renderer build on a temporary production-database copy. No tracked
DB or output was changed. The two cached official PDFs passed the final local
identity/page/hash verifier; transport-fault tests used synthetic bytes only.
The private workflow patch parsed as YAML and applied cleanly to its pinned
preimage in a temporary directory. Exact-head PR CI remains the merge gate;
none of these offline results claims production model output.


## 24 October production format correction

The retained 10790/VPCP-CN receipt has an 82-word public summary and 122 words of
private evidence notes. All three Vietnamese spans match their cited pages.
Requiring those notes to duplicate the public paragraph verbatim incorrectly
held the draft before its first independent factual review. The corrected rule
keeps the public 90-word ceiling, literal page evidence, number and modality
checks; mandatory independent review now checks every public claim against the
complete source and cited spans. It does not grant publication from a format
check alone. Complete serialized model input is also bounded before reservation.
Private-note numbers must occur on their cited page; public-summary numbers must
occur in the cited spans. The shared attribution check additionally recognizes
Government Office-issued instructions for this source alone. The retained real
draft passes offline mechanical checks; its first-review request is 18,080 bytes.

The existing paid draft is reused for this never-executed review. Relevance and
explanation are not repeated, and an executed factual-review route cannot run
again. A continuation records its own run/cost reservation and counts toward the
two-document run limit. First-party/source identity, current rights, complete
extraction and current metadata are rechecked before review or publication.


## Actual first factual review and queue correction (24 October)

PR #868 merged as `3c326f85ac` after required CI `40156015343` passed all
7,982 tests (15 skips), browser, renderer, validation and preservation gates.
Private bridge `40157663479` made exactly one previously unexecuted factual
review call for 10790/VPCP-CN. The reviewer rejected its reassignment of a
ministry responsibility to provincial chairpersons. It remains held; the
explanation and review will not be regenerated or repeated. The API returned
6,490 input and 271 output Sonnet tokens: $0.023535 at the verified rates.
Cumulative usage cost is $0.124666; durable worst-case reservations are
$0.39265125. The three captured documents remain individually held.

The existing metadata store also contains five permitted, uncaptured Government
Office documents. The previous topic-first queue repeatedly refreshed already
attempted topical captures instead of reaching them. Prioritizing unseen unheld
versions first fixes that starvation without expanding source discovery, document
classes, the two-document limit or the content-screening/model gates. A previous
source hold cannot monopolize collection slots ahead of an unattempted document.
Title-based metadata filtering also previously prevented the text lane from
considering these documents at all. The shared pre-model and final-insertion
checks now accept a subject-filtered identity only when its verified metadata
store has exactly one unambiguous version. Multiple filtered versions or a
withdrawn topical reference remain held; no current version is guessed. Public
bibliographic selection is unchanged, and complete-document relevance, source
identity, rights, budgets and independent factual review remain mandatory.
The public Daily acceptance attempt `40158637403` was canceled at its offline
gate because the actual factual review produced no releasable VPCP handoff.

## 25 October local PDF fidelity correction

10744/VPCP-CN exposed two conservative extraction false rejections. Its PDF
first page renders `10744/VPCP-CN` and the Hanoi issue date, 21 October 2026,
in separate columns. pypdf joins those columns on one line. The identity check
now separates only the recognized Hanoi date column and still compares the
entire remaining identifier; wrong or additional identifier text remains held.
Local rasterization and Apple Vision OCR agree with the pypdf identity fields
and portal metadata. No hosted OCR or external-model processing was used.

The second page contains only its printed page number, `2`. It has one text
operation, no image/form objects, annotations, painted paths or unsupported
fonts. The sparse-text check now recognizes that narrowly defined non-content
page and retains it in the complete, page-aware input. Image/form objects,
annotations, additional text operations, painting and unknown operators prevent
the exception. Scanned, failed, absent and materially sparse content still hold.

The cached two-page PDF is 264,119 bytes, SHA-256
`121670635f065b0ecb1ef38641c5236d634fc5777dc3aa1cc0330caf7580f575`.
Complete extraction is 2,778 UTF-8 bytes, including page 2; content identity is
`842585a4cc35857bf6301e55228c7662d03adc3eeb1bed3a3872cfd3916db56e`.
Issuer, number, issue date and signatory pass local validation. This establishes
extraction eligibility only; ordinary relevance, source-use, spend and factual
publication gates remain mandatory. This version has incurred no model calls.

The PDF repair merged in PR #870 as `d33e127a2c` after exact-head CI
`40186397670` passed 7,988 tests (15 skips), browser, renderer, validation and
preservation gates. Private collection `40188963795` captured 10744/VPCP-CN
with exactly the expected PDF and complete-text hashes. Bridge `40189202615`
made its first relevance and explanation calls ($0.017751). The 86-word draft
has three literal page citations, but was mechanically held before factual QA:
the public paragraph's document number `10744` and issue day `21` occur in the
verified PDF header rather than the three selected body spans.

The numerical support rule now also recognizes the separately verified document
number and issue date when issuer, number and date identity checks all match.
It does not accept numbers from unverified metadata. Other public numbers still
require literal cited-span support, and private evidence notes remain bound to
their cited pages. The complete-source independent factual review remains
mandatory; numeric presence alone establishes no semantic correctness.
The retained draft may proceed only if all current mechanical checks pass, using
the existing first-review continuation and its durable single-use reservation.
Neither relevance nor generation is repeated; an already-executed factual
review cannot run again. Cumulative provider-token cost before this first review
is $0.153260 across ten API calls; durable reservations are $0.48976375.
