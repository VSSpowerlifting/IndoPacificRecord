# Change report: October 31 Brief, editorial production round

**Branch:** `editorial/manual-source-linked-2026-10-31` (draft PR #938)
**Status after this round:** unapproved draft, no issue number, no human review or approval recorded.

## Manuscript

- **New headline:** "Japan and the United States Agree to Establish AMRAAM Final Assembly in Japan." The old one ("…Move From Missile-Production Plans to an Assembly Agreement") described a process. The new one states the decision.
- **New dek.** It names both decisions and states what the summaries leave out: no site, operator, contract or production rate.
- **Rewritten under Editorial Voice v2.** 10 paragraphs, 810 words, five headings:
  - What the ministers agreed
  - An April possibility becomes a commitment
  - Why the assembly step matters
  - A separate track with the Philippines
  - What to watch
- **Opening.** The piece now opens on the decision itself: who agreed what, when and where.
- **Argument.** The AMRAAM step matters because FACO is the end of the production line, not a component. The agreement is still a political commitment until a site, operator and contract appear.
- **Proposal, agreement and implementation are now separate throughout:**
  - April "possibility"
  - October "agreement to establish"
  - nothing built or produced
- **Repeated limitation clauses and generic significance lines were removed.** Each caveat now appears once, where it applies.

## Factual corrections from the source recheck

- **"Cebu" removed.** The source says only "in the Philippines."
- **Mitsubishi Electric.** The company studied participation under 2024 and 2025 ministry contracts. It did not present itself as the future assembler.
- **31 May baseline** is now described as a consensus to proceed with discussions, not an agreement to transfer.
- **Japanese wording added.** The Japanese text of the Philippines statement frames the destroyer aim as continued consultation (協議を継続). This is reported, and a new reference **s7** (Japanese joint statement) supports it.
- **DICAS.** "Renamed" became "upgraded the forum to 'DICAS 2.0.'"
- **P6** no longer cites the Mitsubishi release for a claim that is in the April ministry summary.

## Source-linked draft and presentation

- **`briefs/japan-us-missile-assembly-2026.json`:**
  - title, dek, body runs, references and paragraph support regenerated from the same build as the Word file
  - every reference locator now says what was actually checked; there are no archive or byte-parity claims
  - the stray `approval: null` key was removed, because repository drafts must not carry one (`test_briefs_collection` was failing on it)
- **`briefs/presentation/japan-us-missile-assembly-2026.json`** (new): a draft reading layout with five sections, bound to fingerprint `c65e2aac…40d`, and no approval.

## Deliverables

| Deliverable | Path |
|---|---|
| Word manuscript for Dylan | `research/briefs/manual_2026-10-31_japan_us_missile_agreement_manuscript.docx` (SHA `807cf4ad…cf3`) |
| Verification and issues docket | `research/briefs/manual_2026-10-31_japan_us_missile_agreement.md` |
| Draft email to Dylan (not sent) | `research/briefs/manual_2026-10-31_dylan_email_draft.md` |

## Checks

The draft passes all of the following:
- source-linked validation
- `author_brief.py check`
- `brief_presentation.py check`
- a private preview, with rendered paragraphs and links matching the frozen runs
- 151 focused unit tests

Release-mode checks refuse, as expected, until a human review, a policy ruling and presentation approval exist.

## Open

- **Japanese originals of the April DICAS summary and the 31 May statement:** not compared.
- **Hegseth's first name:** absent from the source.
- **ACSA month:** July and August conflict between the language versions. The month is not used in the article.
