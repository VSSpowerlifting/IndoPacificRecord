# Two October 25–31 Briefs for owner review

Status: two complete unapproved manuscripts and proposed covers. No issue numbers,
human source-review attestations, presentation approvals or publication recorded.

| Manuscript | Public credit | Body | References |
|---|---|---|---|
| `japan-us-amraam-final-assembly-sm3-production` | Benjamin Yang | 11 paragraphs, approximately 820 words | 5 |
| `japan-philippines-first-destroyer-2026` | Benjamin Yang and Jophy Lin | 13 paragraphs, approximately 930 words | 9 |

Canonical manuscripts are `briefs/<slug>.json`; reading structures are
`briefs/presentation/<slug>.json`. Both use the existing source-linked editorial
contract and one Briefs collection. No dependency on PRs 945–947 is required to
publish these manually prepared manuscripts. Those PRs remain separate work.

## Editorial preparation

The missile candidate was recovered from the supplied final manuscript and
rebuilt with the owner-designated Benjamin Yang credit. The unsupported location
"in Washington" was removed from the date of the U.S. readout. The AMRAAM and
SM-3 developments remain together; the Japan–Philippines transfer material is
absent. Its naval-vessel sentence concerns the Japan–U.S. meeting agenda only.

The destroyer candidate was recovered from the supplied archive, rather than
replaced with a new writing project. Jophy's co-author credit uses the existing
research_contributor schema and verified staff biography. Revisions remove the
inaccessible Inquirer page and its venue/payment claims, distinguish a first ship
from a limit on the entire program, narrow the English/Japanese training
comparison, and distinguish diplomatic notes from entry into force. Prospective
decommissioning and transfer are never presented as completed.

## Source verification and limits

AI-assisted verification is separate from the required human exact-version
editorial and source-use review. Each manuscript carries the source's exact URL,
publisher, date, language, original title, relationship to the event and
paragraph support. The citation IDs are local to each manuscript.

Missile sources checked against publisher pages: Japan MOD's October 28 English
and Japanese meeting summaries, April 14 DICAS plenary summary, and Mitsubishi
Electric's April 28 release. Mitsubishi is an interested co-production participant,
classified official rather than independent corroboration. The U.S. war.gov
readout returns HTTP 403 during this preparation. Its reference and the comparison
are retained from the prior publisher verification documented in PR 938 and the
supplied editorial handoff; no fresh successful retrieval or archived bytes are
claimed. Final source review must account for that limitation.

Destroyer sources checked: MOD October 28 English/Japanese, May 5 English and May
31 English/Japanese statements; MOFA's ACSA treaty record; PNA's October 29
report; Naval News's July 7 report; and JIIA's October 14 analysis. PNA is an
official government news service. Naval News is explicitly attributed for
Teodoro's reported July remarks, rather than treated as a Japanese transfer
instrument. The MOFA treaty record gives August 22 entry into force and July 23
exchange of notes; this supports the article's correction of the English October
statement and PNA report. The original Japanese October statement says August.

## Record admission

These are publisher references, not production corpus Records. No source bytes
were admitted into the Record, no record IDs or source versions were invented,
and no production database mutation occurred. Existing Japan MOD activation is
for the authenticated news-feed PDF metadata path, not general HTML admission.
No source-rights override or parallel collector is included. Any subsequent
manual corpus admission requires qualification under an applicable existing grant;
that is not a prerequisite for an explicitly approved source-linked Brief.

## Cover candidates

Receipts are in `docs/evidence/two-briefs-covers-2026-11-01/`. Both photographs
are proposed for article and catalogue use with the existing CSS gradient;
the current manifest stages only the article review surface. Neither is an
approved owner use decision. Proposed 720 by 480 catalogue crops were generated
with the existing catalogue builder for owner review; admission follows actual
number assignment after approval.

- Missile: DVIDS image 9245688, VIRIN 250805-M-OV696-1094, Lance Cpl. Bryan
  Giraldo, U.S. Marine Corps, public domain. The public 1000-pixel preview was
  retrieved without login. Historical 5 August 2025 equipment context, not the
  planned Japanese plant or October meeting. Required non-endorsement notice
  is included verbatim. No master-image access is claimed.
- Destroyer: JMSDF photograph of JS Jintsu (DE-230), via Wikimedia Commons,
  explicitly licensed CC BY 4.0 on the file page. Class context only; not an
  identified transfer hull. The file's timestamp is not asserted as a verified
  event date. The publisher attribution and licence link are retained.

## Remaining release action

The owner must review the exact manuscripts, source-use limitations, headings,
rendered presentation and proposed cover/crop and provide the actual attestations
required by `core/brief_source_linked.py` and `core/brief_presentation.py`.
The preparing agent must not fill those receipts on the owner's behalf.
Then use `scripts/author_brief.py approve` to allocate the next two available
numbers, complete paired catalogue admissions and their exact allow-lists, run
release verification, and perform the authorized merge/deploy and live readback.
No additional writing-workflow engineering is required for this release.
