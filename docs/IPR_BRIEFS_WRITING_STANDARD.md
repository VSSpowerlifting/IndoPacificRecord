# IPR Briefs — writing standard and narrative quality gate

Governs the **machine-drafted Sunday manuscript** that goes to Ben (owner preview)
and then to Dylan. It does not govern human-authored Briefs, bylined analysis or
anything Ben writes directly. Implementation: `core/brief_prose_standard.py`
(`ipr-briefs-prose/1`), `scripts/sunday_briefs_auto_writer.py`, the handoff, readable,
DOCX and importer scripts, and `scripts/analyze_editor_return.py`. Demonstration:
`docs/evidence/briefs-narrative-reform-2026-10-25/before_after.md` (synthetic text).

## 1. The manuscript is an article

The model returns `title`, `dek`, `article`, `audit` and `editorial_questions`.

- `article` is 3–7 blocks (about 450–1,500 words). Block 1 is the lead: it has no
  subhead and presents the concrete development, with the actors, the date and the
  number or action that makes it a story, **before** any statement about sources or
  method.
- Other blocks may carry a short, story-specific subhead or none. Forced section
  names (Overview, What stood out, Why it matters, What was routine, Across the region)
  are flagged. A comparison section appears only when two or more desks' verified
  records actually bear on the same question; a single-country story stays single-country.
- Technical terms are explained once, in plain English, where the reader first meets
  them. Acronyms are expanded on first use. Quotations and figures keep their
  attribution.
- Prose: the standard of a careful foreign-policy journalist who also works with
  analyst discipline. Natural, varied sentences; the claim stated, then its basis;
  no stock significance language ("underscores", "increasingly complex landscape");
  no recap of the lead. This is a register to write toward, not an imitation of any
  one writer.

## 2. Uncertainty: say it once, where it matters

A necessary qualification is never removed. What changes is where it lives:

| Kind | Where it belongs |
|---|---|
| A limitation the reader needs (a figure is the issuer's own; no test conditions given) | In the article, in the sentence or paragraph it qualifies, once |
| Research-process commentary (what the record "does not establish", what the writer "could not determine", baseline and routine notes, terms to verify) | The private `audit` block and the appendix |
| A question for Ben or Dylan | `editorial_questions` (private; not in the Word file or email) |

## 3. The evidence layer is unchanged and private

Citation IDs are not typed into the editable text. Each article block is mapped to its
verified production record IDs and typed external-source IDs in the hash-validated
**ARTICLE SOURCE ACCOUNTING** in the source appendix, keyed by a fingerprint of the
block's text. The source-use receipt, limitations ledger, terms-to-verify list and
NARRATIVE QUALITY REPORT sit in the same appendix. Dylan can reorder, merge, cut and
re-head paragraphs without touching any of it; `validate_return` still requires a
byte-identical appendix and identical protected headings.

## 4. The editorial quality gate

`check_article` runs after structural validation and before the packet is written.
It never edits or deletes prose, never calls a model and never retries.

- **Mechanical errors** (reliably detectable): placeholder text, truncated final
  block, doubled words, duplicate paragraphs, a forced comparison for one desk's
  material, unresolved markup. **Major** errors set `hold`.
- **Editorial flags** (heuristics; prompts, not defects): source-first lead, stock
  subheads, restated lead, caveat density/stacking/endings, researcher limits in the
  article, significance stock phrases, unexplained acronyms, uniform sentence length,
  short article.

Structural or source-ID failures (the existing validator) get the existing single bounded
retry; style findings never raise, so they cannot trigger a second paid call.

**The hold is enforced at send time, and is releasable.** The pre-existing owner-review
gate (`require_owner_review`) covers only the October 10 pilot week, so it cannot stop a
later scheduled Sunday. `send_packet` therefore treats an editor delivery whose packet
reports *OWNER REVIEW REQUIRED BEFORE EDITOR DELIVERY* (or an article-first packet that has
lost its quality line) as held: it is converted to an owner-only notice carrying the
identical TXT and Word bytes and the SHA-256, is never addressed to Dylan, and the job then
fails visibly. With no usable distinct owner address nothing is sent. The release path is
the existing offline `scripts.sunday_send_reviewed_packet` (exact digest, explicit
`--confirm-owner-reviewed`, no model call). Honest limitations: the scheduled workflow
cannot be rerun for a held week without a new model call and possibly a separate Dylan
email, and the manual sender cannot see an earlier Dylan send, so Ben checks Gmail Sent
first. Style flags alone never hold. The headline count appears in the owner preview; the
full report appears only in the private appendix.

The Word projection uses fixed ZIP timestamps so the same reviewed TXT produces
identical DOCX bytes with the same renderer and dependencies. Owner notices include
SHA-256 for both attachments; compare both when releasing. A corrected TXT is a new
artifact requiring its own review and digest.

## 5. Roles

Ben owns accuracy, the argument and publication. Dylan is the language and structure
editor: clarity, order and headings are Dylan's to improve. Neither the model nor the checks
approve a Brief. The Word file is the editing surface; the TXT worksheet is the full record.

## 6. Offline editor-feedback loop

`scripts/analyze_editor_return.py --original SENT.txt --edited RETURN.txt|--edited-word RETURN.docx`
compares what was sent with what came back and writes a **private** analysis (outside
the repository; 0600; never overwrites): paragraph accounting (unchanged, lightly edited,
rewritten, cut or merged, added, moved), what happened to each cited block, figures
introduced or removed, and candidate patterns. It reuses `validate_return`, reads no
correspondence, calls no network or model and **changes no prompt or lexicon**.
`--aggregate` counts the same pattern across analyses; a pattern seen three or more times is
labelled *owner consideration*, never promoted. Promoting a rule into
`PROMPT_STANDARD` or the lexicons is a separate, explicitly owner-approved change with its
own tests.

## 6a. After Dylan edits: reconciliation is mandatory

A substantially edited article is a different text from the one the appendix describes.
The ARTICLE SOURCE ACCOUNTING maps the **original** blocks (by text fingerprint) to their
verified records; `validate_return` and the Word importer prove only that the header,
headings and appendix were not tampered with ("STRUCTURAL REVIEW ONLY — UNAPPROVED"). Neither
is factual, citation or editorial approval of a rewritten paragraph. Before any Brief is
drafted from a return, Ben (or an editorial reviewer) reconciles each changed claim, figure,
name, title, quotation and citation against the original records, working through the
"Reconciliation required before any Brief" list that `scripts/analyze_editor_return.py`
prints. Items it lists: cited blocks that are no longer intact, edited or added paragraphs,
title/dek changes, new figures, new quotations. An added or reworked claim with no verified
record behind it is cut or sourced first; the immutable appendix is never edited to fit.
The checklist is in `EDITORIAL_QA_CHECKLIST.md`.

## 7. What this does not authorize

No model call, SMTP delivery, issue numbering, source-rights decision, merge or
publication. **First safe live check (owner-authorized, manual):** on the next eligible
week, run `sunday_briefs_editorial_handoff.yml` by `workflow_dispatch` with *preview to
owner* on and editor delivery off. Ben receives both the TXT and the Word copy (the owner
preview attaches both, to the owner only), opens the TXT, then inspects the Word copy, the *Narrative QA* line and the appendix's ARTICLE SOURCE ACCOUNTING against
the original sources, and sends nothing to Dylan until satisfied. This spends one model
call and one owner-only email, so it needs fresh authorization.
