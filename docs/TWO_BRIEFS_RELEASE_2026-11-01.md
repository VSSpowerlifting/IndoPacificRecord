# Two October 25–31 Briefs for owner review

Status: attested by the owner on November 1, 2026 against the exact manuscripts
at commit `a6771416`; numbering and publication follow below. Receipts record the
owner's own chat statements only.

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

Receipts are in `docs/evidence/two-briefs-covers-2026-11-01/`. The owner
approved both cover images on November 1, 2026 (see Presentation approval) for
article and catalogue use with the existing CSS gradient. The 720 by 480
catalogue crops are produced by the existing catalogue builder and admitted
after number assignment.

- Missile: DVIDS image 9245688, VIRIN 250805-M-OV696-1094, Lance Cpl. Bryan
  Giraldo, U.S. Marine Corps, public domain. The public 1000-pixel preview was
  retrieved without login. Historical 5 August 2025 equipment context, not the
  planned Japanese plant or October meeting. Required non-endorsement notice
  is included verbatim. No master-image access is claimed.
- Destroyer: JMSDF photograph of JS Jintsu (DE-230), via Wikimedia Commons,
  explicitly licensed CC BY 4.0 on the file page. Class context only; not an
  identified transfer hull. The file's timestamp is not asserted as a verified
  event date. The publisher attribution and licence link are retained.

## Confirmed source review and release preparation

Benjamin Yang, Founder & Executive Director, made two statements in chat on
November 1, 2026 about both manuscripts at commit `a6771416`. The
`editorial_review` and `policy_ruling` receipts bind the exact-version
fingerprints computed from the manuscripts at that commit, unchanged since:

| Manuscript | Editorial fingerprint |
|---|---|
| `japan-us-amraam-final-assembly-sm3-production` | `c2f58de2fb0c6ddfe4581a20454d419ecf4ddad72c3f39e466d7445f5a670eee` |
| `japan-philippines-first-destroyer-2026` | `2102a7fb69b3a1f26ead62c9a74c2fff119f3d4c219834a88bff96bcc11da612` |

First statement:

> I confirm my final editorial and presentation approval of both briefs at commit `a6771416`, including the rendered pages, headings, bylines, citations, and cover images.
>
> As IPR's Founder & Executive Director, I approve publication of both briefs under the source-linked evidence policy.
>
> For the AMRAAM brief, I explicitly accept the documented s3 limitation: the official war.gov page returns HTTP 403. The U.S. readout comparison is supported by the earlier publisher verification documented in PR #938 and the accessible republication. Do not claim a new successful retrieval of the official page.

Second statement:

> I have completed my original-source review of both briefs at commit a6771416.
>
> For both manuscripts, I confirm the four remaining editorial checks: original_language, claim_support, chronology, and limited_source_use.
>
> I accept the previously documented AMRAAM s3 source-access limitation and reaffirm my approval of both manuscripts, their presentations, covers and bylines.

How each receipt rests on those statements:

- `original_language`, `claim_support`, `chronology` and `limited_source_use`:
  his own original-source review, confirmed in the second statement.
- `authorship`: his approval of the bylines (Benjamin Yang; Benjamin Yang and
  Jophy Lin, co-author). This is the owner's approval of the credit, not a
  separate statement from Jophy Lin.
- `manuscript_fidelity` and `rendered_review`: his final editorial approval of
  both briefs at `a6771416`, including the rendered pages, in the first statement.
- `policy_ruling`: his approval of publication under the source-linked evidence
  policy, in the first statement.

The AI-assisted source-to-claim comparison described under Source verification
and limits was preparation for that review. It is recorded as preparation and is
not attributed to the owner.

AMRAAM source s3 (the U.S. war.gov readout) is covered by the owner's explicit
acceptance of the documented limitation. The page returned HTTP 403 during this
preparation. The readout comparison rests on the earlier publisher verification
in PR 938 and the accessible republication. No new successful retrieval of the
official page is claimed.

## Presentation approval

The first statement approves the rendered pages, headings, bylines, citations and
cover images of both briefs; the second reaffirms the presentations and covers.
The presentation receipts (excerpts, headings, media, rendered page) bind these
digests:

| Manuscript | Presentation digest |
|---|---|
| `japan-us-amraam-final-assembly-sm3-production` | `3030a230d219af8a83032c372f4a7ee8772d2319680a2c61579e0d68bfade0d6` |
| `japan-philippines-first-destroyer-2026` | `a7e8fbaebf5edbca7b753748e18c2347e0aeee3f58f299ca5717edbf5b52f616` |

## Remaining release steps

`scripts/author_brief.py approve` assigns the numbers, AMRAAM first and then the
destroyer brief. With No. 20 the highest assigned issue, these are expected to
be Nos. 21 and 22. The paired catalogue admissions and test allow-list lines
follow, then render, validator, full CI, merge, deploy and live verification.
Approval of content does not assert deployment.
