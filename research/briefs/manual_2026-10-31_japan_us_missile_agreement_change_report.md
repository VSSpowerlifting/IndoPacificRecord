# Change report: October 31 Brief, editorial production round

**Branch:** `editorial/manual-source-linked-2026-10-31` (draft PR #938)
**Status after this round:** unapproved draft, no issue number, no human review or approval recorded.

## Manuscript

- **New headline:** "Japan and the United States Agree to Establish AMRAAM Final Assembly in Japan." The old one ("…Move From Missile-Production Plans to an Assembly Agreement") described a process. The new one states the decision.
- **New dek.** It names both decisions and states what the summaries leave out: no site, operator, contract or production rate.
- **Rewritten under Editorial Voice v2.** 10 paragraphs, 839 words after the review round (810 before), five headings:
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
- **`briefs/presentation/japan-us-missile-assembly-2026.json`** (new): a draft reading layout with five sections, bound to fingerprint `ac8afe50…6f2f`, and no approval.

## Deliverables

| Deliverable | Path |
|---|---|
| Word manuscript for Dylan | `research/briefs/manual_2026-10-31_japan_us_missile_agreement_manuscript.docx` (SHA `3095c21e…2eda`) |
| Verification and issues docket | `research/briefs/manual_2026-10-31_japan_us_missile_agreement.md` |
| Draft email to Dylan (not sent) | `research/briefs/manual_2026-10-31_dylan_email_draft.md` |

## Checks

The draft passes all of the following:
- source-linked validation
- `author_brief.py check`
- `brief_presentation.py check`
- a private preview, with rendered paragraphs and links matching the frozen runs
- 151 focused unit tests
- an isolated full-mode render and `validate_output.py` run, with 10 warnings (the governed baseline); the draft does not appear in the output

The local full suite reported 8,259 tests, 4 failures and 31 errors. All of them come from this Mac's environment: python-docx is not installed in the venv, `gpg` is absent, and macOS resolves `/var` to `/private/var`. One test from each of the other failing groups fails the same way on clean `main`. The 88 docx-dependent tests pass once python-docx is present.

Release-mode checks refuse, as expected, until a human review, a policy ruling and presentation approval exist.

## Review round (independent quality review, 31 October 2026)

- **Attribution correction (material).** Both missile decisions appear only in Japan's records (s1, s4). The U.S. Department of War readout, added as **s8**, mentions neither; it records only a commitment to continue close coordination on critical munitions production. P1 now says so, with s8 cited.
- **Full name.** P1 now reads "U.S. Secretary of War Pete Hegseth," from s8.
- **Japanese originals of s2 and s6** were read against the article. Both match; no wording change.
- DOCX, sidecar runs, paragraph support, references and the presentation fingerprint were regenerated together from the one build. The presentation sections are unchanged.

## Open

- **ACSA month:** July and August conflict between the language versions. The month is not used in the article.
