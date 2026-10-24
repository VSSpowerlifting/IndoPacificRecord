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
checkpoint, repeat route or a version attempted in an earlier run fails closed;
there is no automatic paid retry, even after an interrupted job. API-returned
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
