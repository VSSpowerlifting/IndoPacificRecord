---
name: ipr-source-integrity
description: Indo-Pacific Record source and claim integrity routing. Use when drafting, checking or reviewing a Brief, Sunday selection, dossier, evidence timeline, translation, desk source record or any IPR prose that makes factual claims — or when researching sources for one. Routes to the governing checklist, doctrine, reviewer agent and domain scripts.
---

# IPR source integrity — routing

This skill only routes; the rules live in tracked docs. Apply them before
treating any claim, quotation, translation, date or citation as settled.

1. **Rules:** `docs/PRODUCT_AND_EDITORIAL_DOCTRINE.md` §4 (trust ladder,
   evidence vs inference) and `EDITORIAL_QA_CHECKLIST.md` (the gate).
   Standing rulings: `DECISION_LOG.md`.
2. **Authority:** the preserved IPR record and the original-language source
   are the evidence. Web search, deep-research, Firecrawl or fact-check
   skills help discovery and cross-checking; they never replace the original
   text, and compressed or summarized output is never a source for
   quotations, original-language text, dates, ranks or figures.
3. **Workflow by product** (the governing doc owns the procedure):
   - Briefs — `docs/BRIEFS_WEEKLY_SELECTION.md`; `scripts/author_brief.py
     check|ready`, private review via `site/render.py --review-brief`.
     Approval stays with the human editor.
   - Dossiers — `docs/LIVING_DOSSIERS.md`; `scripts/dossier.py
     check|changes|ready|preview`. Review trees stay local and private.
   - Timelines — `docs/EVIDENCE_TIMELINES.md`; `scripts/validate_timelines.py`.
   - Desk sources — `docs/desks/README.md` and the source's actual
     source-use decisions. Never defeat access controls or robots rules.
4. **Independent check:** run the `editorial-integrity-reviewer` agent
   (read-only, pass/fail findings) before an approval or an editorial ship.
   Where Ben's user-level `ben-source-verify` skill is present, use it for
   the claim ledger; otherwise build one by hand from the checklist.

Never invent text, translations, titles, dates, units, ranks, sources or
review results. State uncertainty and name the authoritative record instead.
Model agreement or fluent prose is not independent factual review.
