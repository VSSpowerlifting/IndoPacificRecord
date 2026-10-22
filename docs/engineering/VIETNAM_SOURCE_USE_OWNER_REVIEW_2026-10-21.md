# Vietnam source-use decisions — owner review, 21 October 2026

**Status: THREE MPS OFFICIAL LINKS LIVE; AUTOMATIC ARTICLE ANALYSIS HELD.**
The metadata-only owner release and PR #848 are complete. They do not grant
original-body model use. No article source-use seal, model call, source-use key
or article activation flag was created in this follow-up.

## Production activation assessment — 21 October 2026

**Standing-policy reconciliation, without article activation.** The MPS
factual-reporting lane may use a dated, owner-sealed, independent source-use
assessment rather than *always* requiring a ministry reuse license. This must
be an actual source-specific document under `docs/engineering/` addressing
private custody and full Vietnamese-body transmission to Anthropic under the
relevant law and publisher terms. The seal records an owner's decision; it
does not establish rights. This path is **MPS-only** and cannot approve public
original headlines, text, excerpts, full translations, or media. An original
IPR English analysis headline need not depend on displaying the original
Vietnamese title. All other source holds, QA and spend limits remain.

**Relevant evidence, not blanket clearance:**
- MPS asserts copyright and requests source credit on reuse:
  https://bocongan.gov.vn/ . It does not expressly authorize AI model inputs.
- Vietnam's IP amendment No. 131/2025/QH15 took effect 1 April 2026:
  https://chinhphu.vn/?classid=1&docid=216511&orggroupid=1&pageid=27160 .
  Decree No. 134/2026/ND-CP addresses certain *noncommercial* AI text/data
  uses; it is not a blanket authorization for every publisher-body-to-API call:
  https://english.luatvietnam.vn/decree-no-134-2026-nd-cp-dated-april-06-2025-of-the-government-amending-and-supplementing-a-number-of-articles-of-the-governments-decree-no-17-202-432164-doc1.html .
- U.S. fair use includes news reporting but depends on purpose, nature, amount
  and market effects, and does not automatically establish rights abroad:
  https://www.copyright.gov/fair-use/ .
- Anthropic's commercial API does not use requests for training by default;
  it generally deletes them within 30 days, subject to exceptions:
  https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training
  and https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data .
  These vendor policies are not a publisher license.

**Current conclusion:** The evidence supports an independent *review path*,
not yet a supported finding that IPR may transmit complete MPS articles to
Anthropic. This change creates no owner seal, paid model calls, live registry
promotion, activation flags or public article release. Three MPS metadata
links remain published.

- Read the current [official MPS portal](https://www.bocongan.gov.vn/) footer:
  copyright belongs to MPS; reused information should credit the portal. It
  supplies no express external-model, retained-copy or full-translation scope.
  This observation is not a finding that factual reporting requires a ministry
  licence, nor a legal determination that all model use is prohibited.
- Connected GW Gmail contains the sent inquiry, subject “Clarification of MPS
  Portal Reuse and English Translation Permissions”, 21 October 2026, 10:33 EDT.
  Searches of the contact, ministry domains and subject found no reply. No
  further correspondence was sent.
- Current private main is `defd100a5bc6cfc1274e8f0e628d676b251dcc8b`;
  the MPS archive remains `25dae9889700e555f69710620d64f1577ac5e219`.
  Verification [#39697545306](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39697545306)
  and [#39702405271](https://github.com/VSSpowerlifting/ipr-source-evidence-private/actions/runs/39702405271)
  succeeded. The archive has 25 authenticated originals; these are not published
  analyzed articles.
- [Metadata publication #39711288743](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39711288743)
  and [Pages #39711423178](https://github.com/VSSpowerlifting/IndoPacificRecord/actions/runs/39711423178)
  succeeded. HTTPS [Vietnam Desk](https://indopacificrecord.org/vietnam.html)
  contains three MPS URL/date/issuer references, and excludes original titles,
  bodies, translations and automatic analysis. Vietnam corpus article count: 0.

**Input/output determination.** The present relevance, analysis and second-pass
calls all transmit the authenticated Vietnamese original title/body to Anthropic.
The previous metadata release does not authorize that. Private preservation
under the separate collector/cutover authority also does not establish external
transmission rights. Independently reporting facts in IPR's own words is a
different use from those copies and from public translations. No source-specific
basis plus owner decision for this exact body-driven model use was established.
The body call therefore remains disabled. This does not make ministry
correspondence universally indispensable: a documented independent rights/terms
assessment and explicit owner authorization could supply the missing decision.

**Narrow alternative assessed.** The approved URL/date/issuer projection supports
an honest source-link index, not substantive article analysis. No recurring,
independently prepared, authorized factual-note feed exists for the shared
Analyzer. Feeding sparse metadata or relabeling source text as “notes” would not
solve that boundary. The existing two human editorial synopses are not a
standing automatic source-input authorization. No alternate engine was built.

**Engineering repair.** The existing runner now passes `model_second_pass` to
`run_family`, using its five-review per-family/run budget and three-attempt
retry/escalation policy. MPS's existing summary call also produces an original
English factual headline; no extra headline API call or full translation is
needed. The public projection, deterministic headline checks, signed handoff
and record-page label distinguish that headline from translation. Existing
successful projection replay avoids new API calls after delayed public admission.
Fixture pipeline/handoff tests passed; no real MPS AI run is claimed.
The first full CI run executed 7,902 tests and exposed seven older Vietnam
fixture/expectation failures after the real metadata release. Disposable
admission databases now remove only their inherited MPS link identities before
fictional review replay; page assertions compare the admitted Vietnam identities
while retaining the zero-article claim. Production rows and release guards are
unchanged. All 10 focused checks covering these failures pass after correction.
The final exact-head gate is recorded on the PR.

**Single remaining external decision.** The owner must approve an evidence-backed
MPS source-use decision for original title/body transmission to Anthropic,
private retention and attributable independent factual headlines/summaries,
with public original bodies, complete translations, excerpts and media excluded.
Use the existing `core.vietnam_source_use.verify_decision` format and a separate
`VIETNAM_SOURCE_USE_REVIEW_KEY`; do not reuse the metadata review key or claim a
publisher licence where the basis is an independent rights assessment.
For MPS, independent IPR English analysis no longer depends on publishing
the original Vietnamese title. No supported source-to-external-model body
decision is ready to sign today.

After that decision, remaining ordinary release work is: provision the separate
review key securely in both repositories, commit the validated seal under
`config/vietnam_source_use/`, promote registry coverage for MPS only, set the two
article flags, run one authenticated MPS item through the existing private
bridge and public Daily receiver, and verify its deployed record and withheld
fields. Those actions remain conditional on the decision. Existing bridge,
provenance and Anthropic secret names are present; values were not read.
Private collection runs at 18:17 UTC, its bridge at 20:17 UTC, and public Daily
receives at 12:23 UTC the following day (with retries through 14:23); the persisted
handoff survives that ordering, so no shared schedule change is needed.

## Baseline Vietnam reporting policy — limited, source-linked, no blanket permission requirement

**Purpose.** Publish independently written news/research based on verified public facts (who acted, what was announced, when, relevant amounts and stages, and what remains uncertain). Factual reporting is not the same use as reproducing copyrighted text. There is no requirement to obtain a ministry's permission simply to accurately report facts; source-access terms, rights in expressive material, and any actual proposed copying or model transmission still matter. This is an editorial policy, not legal advice or automatic license. China's legacy publication history should not be mistaken for a universal rights clearance.

**Baseline public output — subject to source provenance and editorial checks:**
- Canonical official URL, publisher, source-stated date and IPR's own factual event identification; attribute government claims directly to the relevant authority. Link readers to the full original on the official site.
- Independent English headlines, summaries and analysis written in IPR's own language; distinguish meetings, intentions, approvals, financing, commencement and completed outcomes. No fabricated corroboration, no source wording passed off as IPR's.
- No complete source text, substantial quotations, full article translations, photographs, PDF attachments or publisher-branded graphics in the baseline publication. An English factual summary is **not** a line-by-line translation.
- Retain version/provenance records only within independently permitted and authenticated custody; honor access limits, source integrity checks, and corrections. When only official link/date/issuer facts are safely available, publish those rather than claiming to have analyzed unread originals.

**Model boundary.** The current `core.vietnam_corpus_bridge.run_family` sends the preserved Vietnamese body to `analyzer.analyze_record`, and `core.vietnam_source_use.REQUIRES` makes `public_ipr_analysis` depend on `external_model_transmission`. Therefore **the present automatic article path cannot safely be switched on merely by declaring factual reporting permissible**. Full-body Anthropic processing remains HELD pending an actual source-specific use/terms assessment and owner authorization, whether or not a ministry replies. IPR may separately edit *its own* reporting notes and public bibliographic facts; that is not a grant to transmit copyrighted source bodies or to reuse full translations. No shadow-to-live change here.

**Source-specific rollout:**
1. **MPS Foreign Affairs — first practical candidate.** Use the existing `research/vietnam_mps_link_release_candidate.json` and `core.vietnam_official_link_admission` to verify exact original-source identity/version and prepare a URL/date/issuer **metadata-only** release. Those fields are not full original text. Owner/editorial review and the existing signed release mechanics are still needed; a claim of a publisher license must not be fabricated. Independent prose analysis is a separate editorial action. MPS's attribution request is observed, not a blanket license.
2. **MOIT Energy and Foundational Industry — distinct access hold.** Both have unresolved consent/robots and usage conditions (see below). Continue independent journalistic research about public developments where lawfully sourced, but do not unilaterally lift the existing automated access, preservation, metadata-export or full-body processing holds. A single response cannot authorize both categories unless its scope explicitly does.
3. **Broader automated summary lane — later, narrow code review.** Reuse the shared Daily and existing source/QA machinery only after establishing which specific input fields can lawfully go to an external model and what editorial release gate applies. Do **not** create a duplicate Vietnam analyzer, publisher, or database; do not relabel an owner editorial judgment as an official reuse license.

**No longer a launch prerequisite for independent factual reporting:** waiting for ministry correspondence on the ability to report public facts. **Still a blocker for the current automatic text-to-model path:** its separate model/source terms and owner signoff. **Still blocked for MOIT automated access:** unresolved portal restrictions. This distinction prevents a useful basic Desk from being held by unnecessary formalities without silently bypassing actual restrictions.


## Exact official terms and verified contacts

- **MPS (Foreign Affairs; `vn_mps_foreign_affairs_vi`):** The official portal footer asserts Ministry copyright and requests the source credit **“Cổng Thông tin điện tử Bộ Công an”** when its information is reused. It does **not expressly address** automated recurring collection, retained copies for IPR, external Anthropic processing, or full English machine translations. Evidence and official public contact: https://bocongan.gov.vn/lien-he ; **bandoc@mps.gov.vn**. MPS source: https://bocongan.gov.vn/api/rss/34.xml. Do not infer a machine-processing license from the attribution request.
- **MOIT (`vn_moit_energy_vi`, `vn_moit_foundational_industry_vi`):** Official conditions say a user may download/store/print unmodified information subject to copyright and crediting the portal; the same official website's footer requires **prior written consent when exploiting/citing portal content**. Treat this as an unresolved restriction, not blanket automated rights. Conditions: https://moit.gov.vn/quy-che ; official portal contact: https://moit.gov.vn/lien-he ; **BaoCT@moit.gov.vn**. The 19 October project review independently documented a `robots.txt` 200 response served as `text/html`; this needs a separate human access-policy disposition, not an automated allow.
- **MOIT scopes are independent:** Energy https://moit.gov.vn/tin-tuc/phat-trien-nang-luong and Foundational Industry https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang . One permission does not extend to the other.

## Existing restricted-use controls (not the baseline editorial lane)

Seven existing `core.vietnam_source_use.PERMISSIONS` fields apply independently to **each** family. They govern the current body-driven automated bridge and any copied material, **not a universal right to report public facts**. No new model/transmission or full-text decision is ready to sign:

| Permission | MPS | MOIT Energy | MOIT Foundational Industry |
| --- | --- | --- | --- |
| `collect_preserve` (continuing private collection/retention) | HOLD; clarify intended ongoing scope | HOLD; written-consent/access review | HOLD; separately written-consent/access review |
| `external_model_transmission` (sending original to Anthropic) | HOLD; explicit scope needed | HOLD | HOLD |
| `public_title_display` (title + official link) | HOLD pending owner/source review | HOLD | HOLD |
| `public_ipr_analysis` (attributed independent English synthesis) | HOLD pending rights and model permission | HOLD | HOLD |
| `public_full_translation` (machine English translation) | HOLD; separate reuse/derivative right | HOLD | HOLD |
| `public_original_storage` (public original body) | HOLD; not requested for first launch | HOLD | HOLD |
| `public_excerpt` (verbatim short quote) | HOLD; not requested for first launch | HOLD | HOLD |

**Fastest useful scope:** Admit independently authenticated and owner-reviewed **MPS factual metadata** using the existing verified-link route once approved. Produce independent journalistic analysis separately without republishing Vietnamese bodies. For automatic AI analysis, review and document the narrower model-input policy before touching the current sealed-decision gate. Full-text translation, original-body hosting and imagery are not needed for the baseline. The verified-link route is not the same thing as an admitted article.

Released exact MPS metadata candidates (metadata only; article use still held): `mps-vi:1791199100`, `mps-vi:1791199677`, `mps-vi:1791971146`. Their historical source tip and metadata hashes are pinned in the candidate JSON. The signed metadata release records that exact review; it grants no article/model use.

## Historical inquiry drafts — both requests actually sent on 21 October 2026

The following are the prepared working texts, **not exact copies of the sent messages**. The MPS inquiry was sent to `bandoc@mps.gov.vn` and the MOIT inquiry to `BaoCT@moit.gov.vn`, both from `ben.yang@gwmail.gwu.edu`. Replies are pending. These inquiries clarify optional broader uses; their non-response does not prevent independent factual news reporting.

### MPS — `bandoc@mps.gov.vn`

**Subject:** Clarification of reuse and AI translation permissions — Ministry of Public Security portal

Dear Ministry of Public Security Portal Team,

I lead Indo-Pacific Record (https://indopacificrecord.org), an independent research publication documenting official Indo-Pacific policy and security developments. We are reviewing the Ministry's Foreign Affairs news reports (https://bocongan.gov.vn/api/rss/34.xml) and want to respect the portal's copyright and attribution requirements.

Your website asks users to credit “Cổng Thông tin điện tử Bộ Công an” when reusing information. Could you clarify whether, with that attribution and direct links to each official article, we may: (1) periodically retrieve and preserve unchanged report text in a private research archive; (2) submit that text to Anthropic's external AI service for English translation and analysis; (3) publish the original headline and our own attributed English factual summaries; and (4) publish a clearly labeled, unreviewed machine English translation of the full text?

We are not seeking permission to republish original Vietnamese articles publicly or reuse photographs. Please tell us which uses are permitted, any limits or required notice, and whether an official written permission or policy reference is available. Separate answers for each use would help us keep all other uses disabled.

Thank you for your guidance.

Benjamin Yang
Founder & Editor-in-Chief, Indo-Pacific Record
https://indopacificrecord.org

### MOIT — `BaoCT@moit.gov.vn`

**Subject:** Written permission inquiry for two Ministry of Industry and Trade news sections

Dear Ministry of Industry and Trade Portal Team,

I lead Indo-Pacific Record (https://indopacificrecord.org), an independent research publication. We would like to establish the permitted uses of reports in **two distinct** sections of your portal: Energy Development (https://moit.gov.vn/tin-tuc/phat-trien-nang-luong) and Foundational Industry (https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang).

We have read https://moit.gov.vn/quy-che, including its allowance for unmodified downloads/storage under conditions and the footer requiring written consent for exploitation and citation. For **each section separately**, could you confirm in writing whether we may: (1) periodically access official reports and preserve unchanged text privately; (2) send the text to Anthropic for English translation and analysis; (3) publish original headlines, official links, and independently written attributed factual English summaries; and (4) publish clearly labeled full machine English translations?

If broader use is not allowed, would you authorize a narrower presentation of official article URLs, dates, and issuing body, without original headlines, text, or translations? We will not reuse photos or publicly host Vietnamese originals. Please clarify any automated-access or robots requirements, attribution, restrictions, duration, and withdrawal procedure, and identify which uses are permitted for **each section**.

We will keep all activity requiring permission on hold until the scope is clear.

Thank you for your time.

Benjamin Yang
Founder & Editor-in-Chief, Indo-Pacific Record
https://indopacificrecord.org

## Owner closeout — shortest real path, without extra infrastructure

1. Treat the two sent inquiries as supplementary evidence for broader uses, not as a prerequisite to reporting facts. If either ministry replies, retain its exact scope and reference; a non-response grants no text/model license.
2. Review current original/source-version fidelity and the three existing MPS metadata candidates. Under an authorized editorial decision and the repository's existing exact-version signed release mechanism, prepare only the factual URL/date/issuer projection. Preserve all source provenance and holds; do not fabricate a publisher rights grant.
3. Keep MOIT category-specific written-consent/robots access questions on hold. Evaluate any future full-body model transmission and derivative/full-translation proposals separately, using the actual official terms and independent owner/legal review as appropriate.
4. Once the concurrent production launch settles, reconcile #834, migration ordering and private #20, then verify a permitted live metadata/reporting publication. Do not turn on the current full-body AI bridge merely because this editorial policy exists.

**Implementation changes in this document:** one documentation-only policy clarification. **Source captures:** none. **New rights granted:** none. **Ministry inquiries:** two sent, replies not yet established. **Production/CI actions:** none.
