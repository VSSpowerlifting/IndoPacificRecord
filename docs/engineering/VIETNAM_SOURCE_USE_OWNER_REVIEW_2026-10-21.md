# Vietnam source-use decisions — owner review, 21 October 2026

**Status: UNSIGNED / ALL HOLDS RETAINED.** This is the minimum evidence and correspondence needed to unblock a real Vietnam article, not a grant of collection, model use, source redistribution, or publication. It does not create `config/vietnam_source_use/*.json`, a signed review, or a live workflow.

## Exact official terms and verified contacts

- **MPS (Foreign Affairs; `vn_mps_foreign_affairs_vi`):** The official portal footer asserts Ministry copyright and requests the source credit **“Cổng Thông tin điện tử Bộ Công an”** when its information is reused. It does **not expressly address** automated recurring collection, retained copies for IPR, external Anthropic processing, or full English machine translations. Evidence and official public contact: https://bocongan.gov.vn/lien-he ; **bandoc@mps.gov.vn**. MPS source: https://bocongan.gov.vn/api/rss/34.xml. Do not infer a machine-processing license from the attribution request.
- **MOIT (`vn_moit_energy_vi`, `vn_moit_foundational_industry_vi`):** Official conditions say a user may download/store/print unmodified information subject to copyright and crediting the portal; the same official website's footer requires **prior written consent when exploiting/citing portal content**. Treat this as an unresolved restriction, not blanket automated rights. Conditions: https://moit.gov.vn/quy-che ; official portal contact: https://moit.gov.vn/lien-he ; **BaoCT@moit.gov.vn**. The 19 October project review independently documented a `robots.txt` 200 response served as `text/html`; this needs a separate human access-policy disposition, not an automated allow.
- **MOIT scopes are independent:** Energy https://moit.gov.vn/tin-tuc/phat-trien-nang-luong and Foundational Industry https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang . One permission does not extend to the other.

## Minimum permission decision

Seven existing `core.vietnam_source_use.PERMISSIONS` fields apply independently to **each** family. There is **no decision ready to sign**:

| Permission | MPS | MOIT Energy | MOIT Foundational Industry |
| --- | --- | --- | --- |
| `collect_preserve` (continuing private collection/retention) | HOLD; clarify intended ongoing scope | HOLD; written-consent/access review | HOLD; separately written-consent/access review |
| `external_model_transmission` (sending original to Anthropic) | HOLD; explicit scope needed | HOLD | HOLD |
| `public_title_display` (title + official link) | HOLD pending owner/source review | HOLD | HOLD |
| `public_ipr_analysis` (attributed independent English synthesis) | HOLD pending rights and model permission | HOLD | HOLD |
| `public_full_translation` (machine English translation) | HOLD; separate reuse/derivative right | HOLD | HOLD |
| `public_original_storage` (public original body) | HOLD; not requested for first launch | HOLD | HOLD |
| `public_excerpt` (verbatim short quote) | HOLD; not requested for first launch | HOLD | HOLD |

**Fastest useful scope:** Ask first for bounded private preservation, permission for external model transmission, original title/link, IPR's independent sourced analysis, and an optional clearly marked full machine translation. Keep originals in private custody; do not request images or public body republication. If translation is denied but analysis and model processing are expressly permitted, the existing rights policy can represent a summary-only outcome. Official URL/date/issuer metadata-only review is separately governed by `research/vietnam_mps_link_release_candidate.json`; do not count it as an article or as a rights decision.

Existing exact MPS metadata candidates (all still held): `mps-vi:1791199100`, `mps-vi:1791199677`, `mps-vi:1791971146`. Their historical source tip and metadata hashes are pinned in the candidate JSON. Owner must independently review exact originals and current editions before any metadata release.

## Two concise inquiries — DRAFT, NOT SENT

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

## Owner closeout — no additional engineering required for this decision

1. Owner reviews these inquiries and explicitly authorizes each send; no email has been sent. The addresses above are published portal contacts, not verified rights-officer identities.
2. Retain written responses or precise official terms **per family**, with date and URL/correspondence reference; review any MOIT robots policy. No response is not consent. Distinguish public factual links from original titles, external model input and translated bodies.
3. Only after sufficient evidence: set the corresponding values in an *actual* owner-reviewed source-use decision; keep every other permission false, assign the proper `rights_basis_type` (`explicit_official_reuse_terms` or `written_rights_owner_permission`) and verifiable `rights_basis_reference`, then independently seal using the existing workflow. A MAC is not evidence of a legal grant.
4. Do not enable production, sign a mock decision, trigger private collection, or run external models as part of this review.

**Code changes:** none. **Source captures:** none. **Rights approved:** none. **Ministry contacts:** zero.
