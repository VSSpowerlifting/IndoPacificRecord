# Patkor Indopura Brief: release record

Status: **held at the owner gate.** No issue number has been assigned and no
review, ruling or presentation approval has been recorded. Every
release step that does not need a human decision is done.

| Field | Value |
|---|---|
| Slug | `singapore-indonesia-first-joint-fighter-patrol` |
| Headline | Singapore and Indonesia Fly Their First Joint Fighter Patrol |
| Credit | Benjamin Yang and Dylan Tanzi (`research_contributor`) |
| Body | 9 paragraphs, 1,011 words, 6 publisher references |
| Manuscript SHA-256 | `dea90e45…ec70` (approved DOCX) |
| Editorial fingerprint | `a31ffed37cc8e180f6f8a09f063082aee8324c4b459f3660ce08accca51d4857` |
| Presentation digest | `a28fee5f86fae3268c39fb3b70f0b348a9e9b3b4c8c844886b530613ec33000c` |
| Week | 1–7 November 2026 |

## What is verified

- `author_brief.py check` passes (draft contract).
- `author_brief.py ready` fails only on the two human attestations:
  `editorial_review` and `policy_ruling`.
- A private unnumbered review (`site/render.py --review-presentation`, outside
  the repository) was rendered from the sidecar and inspected at 1280px and 375px.
  It has 9 manuscript paragraphs and 3 proposed section headings. There was no
  horizontal overflow and no console errors.
- `manuscript_html_errors` returns no differences, so the rendered text, paragraph
  order and inline source links match the sidecar exactly.
- The fingerprint above is the approved fingerprint, unchanged.

These are AI-assisted preparation checks. They are not the owner's
original-source review.

## Blockers needing a human

### 1. MINDEF link approval (PR #1004)

On `main`, `APPROVED_MINDEF_LINKS` admits only two MINDEF URLs. This Brief
cites five other MINDEF pages (s1, s3, s4, s5, s6), so the publication gate
holds it. PR #1004 replaces the list with an exact-host gate. Two commits on
that PR fix its CI regressions:

- The bare `https://www.mindef.gov.sg` homepage link is accepted.
- Stale test imports are retired.
- The PR head is `d2e623db25`.

Green CI does not authorize merging. The PR's own conditions still need the
founder's substantive policy review and reconciliation of the rights evidence.
The founder-reported reply granting "all linking requests" has not been
authenticated in the repository. It covers linking only, not reproduction.

### 2. MINDEF speech quotation (paragraph 6, s5)

Paragraph 6 quotes 14 words from Minister Chan Chun Sing's August 2025 speech,
attributed and linked:

> “Many of us in my generation grew up together with our counterparts in Indonesia,”

There is no recorded basis for this. The original linking request
(`docs/SINGAPORE_MINDEF_LIMITED_LINK_PERMISSION_2026-10-29.md`) told MINDEF
that the Brief uses "independent commentary and factual paraphrase, not ...
article text". The link grant does not cover reproduction, and MINDEF Terms of
Use §§5–6 still apply.

A short attributed quotation for commentary may be supportable under Singapore
Copyright Act 2021 fair use, or under 17 U.S.C. §107. Under
`CONTENT_AND_DATA_RIGHTS.md` §7.1 and §7.3, that is a legal determination for
the owner to record. It conflicts with the representation made to MINDEF, so it
is not something to infer. Choose one:

- **A. Paraphrase (recommended).** Replace runs 1–3 of paragraph 6 with:
  - "…recalled his years serving in the country. He told them that many in his
    generation had "
  - [s5] "grown up alongside their Indonesian counterparts"
  - ", drawing a line from personal friendships to decades of military
    exchanges. In the same speech, …" (the rest is unchanged)

  This changes the editorial fingerprint. You would approve the new text and
  fingerprint.
- **B. Keep the quotation.** Record your own ruling and its legal basis in the
  existing MINDEF decision. Your ruling must acknowledge the representation made
  to MINDEF.

### 3. Owner review and approvals

These must be the owner's own statements, made in chat, against the final
commit and fingerprint. A template follows. Adjust it if it does not describe
what you actually did.

> I have completed my original-source review of the Patkor Indopura Brief at
> commit `<sha>` (fingerprint `<fingerprint>`). I confirm original_language,
> claim_support, chronology and limited_source_use, including my decision on the
> paragraph 6 MINDEF speech quotation.
>
> I confirm my final editorial and presentation approval of the rendered page,
> headings, bylines (Benjamin Yang and Dylan Tanzi), citations and the DVIDS
> 8879603 cover captioned as a separate February 2025 refuelling exercise.
>
> As Founder & Executive Director, I approve publication under the
> source-linked evidence policy, and I approve merging PR #1004. I hold the
> original MINDEF reply on which it relies.

After these statements, the steps are:

1. Record the review, ruling and presentation receipts.
2. Run `author_brief.py approve`. It assigns the next canonical number, which
   is expected to be No. 23 but is not to be invented.
3. Admit the cover and the 720 × 480 catalogue crop under that number.
   The crop must carry the DVIDS credit and the non-endorsement notice.
4. Render, run the validator (10 governed warnings at baseline), open the PR,
   wait for CI, merge, deploy output only, and verify over HTTPS.

## Cover

The receipt is `docs/evidence/brief-cover-patkor-2026-11-07/`. It is not yet
admitted, because admission depends on the assigned issue number.

- DVIDS 8879603, VIRIN 250219-Z-RV808-7846, U.S. Air National Guard photo by
  Master Sgt. Mysti Bicoy, 19 February 2025. Public domain, subject to the DVIDS
  non-endorsement notice.
- Original SHA-256:
  `0178cc48b180125e5d9e59248b0e67e6601d46189c70927b8b8ab6f65184afe4`.
- It depicts a separate 2025 refuelling mission. It must never be captioned as
  the November 2026 patrol.
