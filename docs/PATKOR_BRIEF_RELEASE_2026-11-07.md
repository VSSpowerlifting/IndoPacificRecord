# Patkor Indopura Brief: release record

Status: **owner review, policy ruling and presentation approval recorded; release
in progress.** No issue number has been assigned yet.

Owner receipts, 7 November 2026 (PR #1005, comment 6715346963):

- Benjamin Yang stated that he completed his review of the Brief at
  `94e08c9792` against fingerprint `21ab36ab…`. He approved all seven
  `editorial_review` checks and the paragraph 6 paraphrase, and confirmed the
  paragraph 4 March 2024 DCA claim against s3. These are recorded in the
  sidecar's `editorial_review`.
- As Founder & Executive Director he approved publication under the
  source-linked evidence policy. This is recorded as `policy_ruling`.
- He approved the presentation at digest `d45f371e…`: headings, excerpts and the
  rendered article. The manifest has no in-body figures, so the `media` check
  covers none. The numbered cover and catalogue image remain subject to his
  separate visual check.
- For #1004 he approved the outbound-link policy on the permission wording
  previously supplied. The later MINDEF correspondence is still unverified. He
  did not authenticate it, and nobody else has either.
- `author_brief.py ready` now passes.

An earlier statement the same day (comment 6715316389) expressly did not claim
personal review, so it was not recorded as `editorial_review`.

| Field | Value |
|---|---|
| Slug | `singapore-indonesia-first-joint-fighter-patrol` |
| Headline | Singapore and Indonesia Fly Their First Joint Fighter Patrol |
| Credit | Benjamin Yang and Dylan Tanzi (`research_contributor`, Lead Research Analyst) |
| Body | 9 paragraphs, 1,009 words, 6 publisher references, no direct quotations |
| Manuscript SHA-256 | `dea90e45…ec70` (approved DOCX; see the paragraph 6 change below) |
| Editorial fingerprint | `21ab36abf8fd700a5c65c56f0fa46c42b889d1b7b67a7298f1d7efedc90272fc` |
| Presentation digest | `d45f371e65305102e4cc396a5ac9d8cd9ab535309963d04a0cd373f78c8bbbe8` |
| Week | 1–7 November 2026 |

## Manuscript change from the approved DOCX

At the owner's direction, paragraph 6 no longer quotes Minister Chan Chun Sing's
August 2025 speech (s5). The 14-word quotation was replaced with the attributed
paraphrase proposed earlier. The meaning, the attribution and the s5 link are
unchanged:

- Before: …recalled his years serving in the country. “[s5: the 14-word
  quotation],” he told them, drawing a line from personal friendships…
- After: …recalled his years serving in the country. He told them that many in
  his generation had [s5: grown up alongside their Indonesian counterparts],
  drawing a line from personal friendships to decades of military exchanges.

Nothing else in the text changed. `manuscript_sha256` still records the approved
DOCX, so it no longer matches paragraph 6 exactly. Because of the change, the
editorial fingerprint is now `21ab36ab…` (it was `a31ffed3…`). The presentation
manifest's `manuscript_fingerprint` was updated to match. Section headings and
emphasis are unchanged, but the presentation digest is now `d45f371e…` (it was
`a28fee5f…`).

## What is verified

- `author_brief.py check` passes (draft contract).
- `author_brief.py ready` fails only on the two human attestations:
  `editorial_review` and `policy_ruling`.
- A private unnumbered review (`site/render.py --review-presentation`, rendered
  outside the repository) was built from this sidecar and inspected at 1280px and
  375px:
  - It shows the 9 manuscript paragraphs under the 3 proposed section headings.
  - There is no horizontal overflow and no console errors.
  - The byline reads "By Benjamin Yang and Dylan Tanzi". Dylan Tanzi's contributor
    credit, Lead Research Analyst, is shown.
- `manuscript_html_errors` finds no differences, so the rendered text, paragraph
  order and inline source links match the sidecar exactly. Both s5 links in
  paragraph 6 point to MINDEF's 5 August 2025 speech page.
- Source associations by paragraph:

  | Paragraph | Sources |
  |---|---|
  | 1 | s6, s1 |
  | 2 | s1, s2 |
  | 3 | s1, s2 |
  | 4 | s3, s4 |
  | 5 | s3, s1 |
  | 6 | s5 |
  | 7 | s6 |
  | 8 | s1 |
  | 9 | s1 |

These are AI-assisted preparation checks. They are not the owner's
original-source review.

## MINDEF: linking is not reproduction

On `main`, `APPROVED_MINDEF_LINKS` admits only two MINDEF URLs, the two covered by
the 29 October 2026 reply. That evidence is in
`docs/SINGAPORE_MINDEF_LIMITED_LINK_PERMISSION_2026-10-29.md`; the correspondence
itself is held privately. This Brief links five other MINDEF pages (s1, s3, s4,
s5 and s6), so the publication gate holds it.

PR #1004 replaces that list with an exact-host HTTPS gate. At head `d2e623db25`
every required check, `offline-checks` included, has passed. The PR is open and
mergeable, and it has not been merged.

Its own conditions remain:

- It needs the founder's substantive policy review.
- The wording granting "all linking requests" is attributed to a later MINDEF
  contact, but nobody has inspected the original message in the repository. The
  founder must hold it privately.
- It authorizes outbound links only. It does not permit reproducing MINDEF text or
  media. MINDEF Terms of Use §§5–6 continue to apply.

Because the body no longer reproduces MINDEF text, the Brief now matches IPR's
26 October representation to MINDEF: "independent commentary and factual
paraphrase, not … article text". On its face the
Brief therefore no longer relies on reproduction permission, but that is the
owner's decision. Nobody has yet compared the remaining link-anchor phrasing
against the s1–s6 pages. The owner's limited_source_use check is the step that
confirms it.

## Remaining release steps

The review render has no cover, because cover admission needs the issue number.
After `approve`, the cover, its caption and the catalogue crop are checked in the
final numbered render and shown to the owner before the release PR merges. The
caption must say that the photograph shows a separate February 2025 refuelling
exercise.

Steps:

1. Record the review, ruling and presentation receipts (done).
2. Merge PR #1004 after recording the founder ruling and its limitation. Its
   head must still be green.
3. Run `author_brief.py approve`, which assigns the next canonical number. No. 23
   belongs to the Western Pacific Brief (PR #1003). No number is to be invented or
   reserved here.
4. Admit the cover and the 720 × 480 catalogue crop under that number, with the
   DVIDS credit and the non-endorsement notice.
5. Render and run the validator (10 governed warnings at baseline). Then open the
   PR, wait for CI and merge.
6. Deploy the output only, and verify it over HTTPS.

## Cover

The receipt is `docs/evidence/brief-cover-patkor-2026-11-07/`. The cover is not
yet admitted, because admission depends on the assigned issue number.

- DVIDS 8879603, VIRIN 250219-Z-RV808-7846, U.S. Air National Guard photo by
  Master Sgt. Mysti Bicoy, 19 February 2025. It is in the public domain, subject
  to the DVIDS non-endorsement notice.
- Original SHA-256:
  `0178cc48b180125e5d9e59248b0e67e6601d46189c70927b8b8ab6f65184afe4`. This was
  re-verified against `site/assets/editorial/patkor-indopura-context-2025.jpg`.
- It shows a separate 2025 refuelling mission. It must never be captioned as the
  November 2026 patrol.

### Unlinked derivatives

`scripts/pw_env.py` `copy_editorial_assets` copies only manifest-listed originals,
but it copies every file in `site/assets/editorial/derivatives/` regardless. It runs
from `scripts/rerender_pla_watch.py` and from the legacy generator. If this branch
merged before `approve`, a rerender would place the three Patkor derivatives at
public URLs that no page links to. Merge this branch only as part of the numbered
release PR.
