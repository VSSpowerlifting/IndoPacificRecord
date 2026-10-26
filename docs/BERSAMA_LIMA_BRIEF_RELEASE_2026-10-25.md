# Bersama Lima Brief — release preparation, October 25, 2026

**Status: staged, not approved, not numbered, not published.** Every human
attestation below is **open**. Nothing in this file is an approval receipt, and
none of the sidecar's `editorial_review`, `policy_ruling` or `approval` fields,
or the presentation receipt, has been filled in.

Brief: *Bersama Lima 2026 Tests Five-Power Coordination at Sea*, week
18–24 October 2026, slug `bersama-lima-2026-five-power-coordination-at-sea`.
Candidate: the "No MINDEF" six-source alternate (16 paragraphs). The owner's
October 25 "Proceed and then publish" is publication direction and acceptance of
that alternate. It is not a record that the owner read the six originals or saw
the cover.

## What was imported and what differs from the packet

The 16 paragraphs, inline source links, paragraph order, six references and the
`manuscript_sha256` (DOCX `f5b69171…a0c82`) are byte-for-byte the packet's.
Packet manuscript fingerprint `87346879…a6e4` therefore **does not carry over**.
The canonical fingerprint is now

`0d017fb6dec46ab4fe90c615419330a2acfdae7113afb5aedb1b4b27f81d3343`

and the presentation is bound to it.

| Change | Why |
|---|---|
| **Authorship: Dylan Tanzi is sole author** (`author_name` Dylan Tanzi, `author_title` Lead Research Analyst, `author_bio` his verified roster biography from `site/preview/staff.json`); Benjamin Yang's byline and the `research_contributor` block are removed | Owner correction of 25 October 2026: Dylan is the sole author; Benjamin remains Founder & Director of Research and Editorial with final editorial oversight and publication approval, but is not a credited co-author of this issue. Briefs may alternate lead authorship issue by issue; co-authorship is not automatic. |
| s3 (USNI) verification locator now says its participant, ship, submarine and aircraft totals are USNI's reported figures, not an independent count | Honest scope of what the reference verifies. No manuscript text changed. |

Dylan's official title is **Lead Research Analyst**. The packet's "Managing Editor"
was wrong and appears nowhere in the repository's current staff roster, Team page
source, author pages or Brief sidecars (audited 25 October 2026); the only
repository mention was an earlier draft of this note. No historical authorship was
rewritten. The roster carries his LinkedIn link (`https://www.linkedin.com/in/dylan-tanzi/`);
the Brief's byline links to his author page, and the author card shows name,
title and biography.

No paragraph text, link target or `paragraph_support` entry was changed. An
earlier working note suggested adding s4 to paragraph 10's support; paragraph 10
links only s5 and s2 and no phrase there needs s4, so it was not changed. The
presentation (four sections: 1–3, 4–8, 9–14, 15–16) is identical to the packet's
apart from the bound fingerprint.

## Source check (AI-assisted, not human review)

The six pages were fetched from their publishers on 25–26 October 2026 and the
manuscript's claims compared with them. This is working verification by the
preparing agent. It does not satisfy the human exact-version source/rights/editorial
review. USNI's (independent) 23 October roundup supplies the 1,900-participant,
seven-ship, one-submarine, 42-aircraft totals as USNI's own reported figures;
the Brief does not present them as a performance assessment or an independent count. mindef.gov.sg is not linked, cited or used.

## Cover

Staged article-only; see `docs/evidence/bersama-lima-brief-cover-2026-10-25/README.md`.
DVIDS 7379876 (U.S. Navy MC2 Jacob Woitzel, public domain, 11 Aug 2022),
labelled on the page as a context image from Pacific Partnership 2022, not
Bersama Lima 2026. Retained file is the 2000 × 1331 public preview; the master
needs a DVIDS login and was not accessed. The owner's 25 October correction describes the HMS Tamar context cover as
"approved" after the preview and crop were shown; the DECISION_LOG entry naming
the image, scope and treatment is recorded at release approval.

## Open gates (smallest explicit human approvals)

1. Exact-version source, rights and editorial review of fingerprint `0d017fb6…3343`
   (the seven `editorial_review` checks) and the source-linked evidence policy
   ruling.
2. Presentation approval: four headings, excerpts (none), media, rendered page.
3. Cover and 720 × 480 crop: DECISION_LOG entry (owner statement above).
4. Then, and only then: `author_brief.py approve` (the command assigns the
   number; expected No. 20 if No. 19 is still the highest), the paired catalogue
   admission, the `tests/test_catalogue_media.py` allow-list lines, render,
   validator, full CI, one PR.

## Receipts

- Cover receipt: `docs/evidence/bersama-lima-brief-cover-2026-10-25/`.
- Review preview (1280 and 375 px screenshots inspected) was rendered with `brief_presentation.py preview` to a private
  out-of-repo directory; 1280 and 375 px renders showed no horizontal overflow
  or console errors.
