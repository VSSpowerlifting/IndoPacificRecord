"""IPR Briefs prose standard: the writer's article instructions and offline checks.

One module owns (1) the reader-facing prose rules given to the Sunday writer and
(2) the offline narrative checks run on its output. Human-readable rules live in
docs/IPR_BRIEFS_WRITING_STANDARD.md; keep the two aligned.

Checks are split deliberately:

* ``errors``: mechanically verifiable defects (a truncated block, a repeated
  paragraph, a doubled word, unbalanced emphasis). They are reported to the
  owner and never trigger another model call.
* ``flags``: editorial heuristics (caveat density, a source-first lead, stock
  phrases). They are prompts for human judgement and never block anything.

Nothing here reads a database, calls a model, edits prose or sends mail.
"""
from __future__ import annotations

import hashlib
import re
from statistics import pstdev

STANDARD_VERSION = "ipr-briefs-prose/1"

MIN_BLOCKS, MAX_BLOCKS = 3, 7
MIN_BLOCK_CHARS, MAX_BLOCK_CHARS = 140, 2600
MIN_ARTICLE_WORDS, MAX_ARTICLE_WORDS = 450, 1500
MAX_HEADING_CHARS = 80
# The DOCX uses this heading to end the article; a story subhead may not.
RESERVED_HEADINGS = frozenset(("source links for context",))

# Section labels from the retired fixed outline. Their presence is a flag, not
# an error: a story may genuinely turn on one of them.
FORCED_HEADINGS = frozenset((
    "overview", "the development", "opening note", "what stood out",
    "why it matters", "what was routine", "what we're watching",
    "what i'm watching next", "across the region", "cross-desk comparison",
    "conclusion", "summary", "background",
))

# Prompt block shared by every article-first Sunday draft. Kept as one string so
# the standard document and the model instruction cannot drift apart silently.
PROMPT_STANDARD = (
    "ARTICLE STANDARD. Write the reader-facing article as a journalist who is also "
    "a careful analyst: clear, concrete, confident where the evidence is firm and "
    "plain where it is not. The article is the product; the audit fields are a "
    "separate ledger for editors and must not leak into it.\n"
    "1. LEAD. The first block opens with the concrete development: who did what, "
    "when and where, with named actors, institutions and dates, and why a reader "
    "outside these institutions should care. Do not open with the publication of a "
    "report, a website, a release date, a count of documents or how the record was "
    "assembled. A source is named when it matters to the claim, not as a preamble.\n"
    "2. PROGRESSION. Write three to six blocks. Each block advances one step of a "
    "single story: what happened; the context that makes it legible (history, "
    "numbers, a comparison with earlier practice); what it shows or changes; what "
    "remains open. Choose each block's step from this story, not from a template. "
    "Give a block a short, specific subhead only when it helps the reader (the "
    "lead has none). Never use stock subheads such as Overview, What Was Routine, "
    "Why It Matters or Across the Region. Never restate the lead in later blocks "
    "or repeat the opening in the close.\n"
    "3. PARAGRAPHS. One to three paragraphs per block, varied in length. Use a "
    "developed analytical sentence where it carries context and a short direct "
    "sentence where it lands a fact. Open a paragraph with the connection to the "
    "previous one when there is one. Prefer active verbs and named subjects. "
    "Avoid filler openers, abstract institutional nouns, mechanical three-part "
    "lists, repeated not-X-but-Y contrasts and gratuitous em dashes.\n"
    "4. TERMS. Explain a specialist term, acronym or system the first time it "
    "appears, in the same sentence or the next, in plain words that stay "
    "technically accurate. Do not stack bureaucratic labels. Do not simplify away "
    "what the term actually means.\n"
    "5. EVIDENCE AND LIMITS. Keep announcements, planned or scheduled activity, "
    "reported exercises, demonstrated operational results and strategic "
    "implications visibly distinct, and attribute each conclusion. State an "
    "uncertainty once, at the point where it changes how the reader should read "
    "the claim, in the same sentence where possible. Do not end paragraphs with "
    "a limitation by habit; do not repeat a limit already stated; do not narrate "
    "what the researcher could not determine. Put open research questions in "
    "editorial_questions and the audit fields, not in the article. Never remove a "
    "limitation that decides how a central claim should be read.\n"
    "6. COMPARISON. Compare institutions or countries inside the article only when "
    "the comparison strengthens the argument and the sources support it. A story "
    "about one country is a complete story. Say in the audit's cross_desk_assessment "
    "whether a comparison was material and what limits it; do not manufacture "
    "symmetry, coordination, silence or a second position.\n"
    "7. SIGNIFICANCE. Earn significance with specifics. Do not claim a story "
    "underscores, highlights or signals importance, and do not close on a generic "
    "geopolitical conclusion. End on the most specific open question or observable "
    "indicator the evidence supports.\n"
    "Write natural, readable English at the sophistication of a serious "
    "foreign-policy publication. Do not imitate any individual writer."
)

# ---------------------------------------------------------------------------
# Lexicons (heuristics only). Reused by the offline editor-return analyzer.
# ---------------------------------------------------------------------------
HEDGE_PATTERNS = (
    ("record_suggests", re.compile(r"\bthe (?:available |public |documentary |stored )?record (?:suggests|indicates|shows|does not)", re.I)),
    ("does_not_establish", re.compile(r"\b(?:does|do|did) not (?:establish|confirm|demonstrate|prove|show|indicate)\b", re.I)),
    ("could_not_determine", re.compile(r"\b(?:could|can|cannot|can't|couldn't) (?:not )?(?:be )?(?:determine|determined|verify|verified|confirm|confirmed|establish|established)\b", re.I)),
    ("not_clear", re.compile(r"\b(?:it is|remains|is) (?:not|un)clear\b|\bremains? (?:to be seen|uncertain|unknown)\b", re.I)),
    ("source_limit", re.compile(r"\b(?:no|without) independent (?:confirmation|corroboration|verification)\b|\bshould be treated with caution\b|\bbeyond the (?:supplied|available|stored) (?:sources|record|text)\b", re.I)),
    ("first_person_limit", re.compile(r"\bI (?:could not|cannot|can't|was unable to|did not find)\b", re.I)),
    ("caution_stock", re.compile(r"\b(?:it is important to note|it should be noted|caution is warranted|care is needed)\b", re.I)),
)
STOCK_PATTERNS = (
    ("significance_stock", re.compile(r"\b(?:underscor\w+|highlights? the (?:importance|need)|signals? (?:a |the )?(?:shift|growing)|testament to|speaks volumes|in an increasingly|rapidly evolving|complex landscape|delve\w*|tapestry|pivotal)\b", re.I)),
    ("not_x_but_y", re.compile(r"\bnot (?:just|only|merely|simply)\b[^.;]{0,90}\bbut\b|\bnot (?:a |an |the )?[^.;,]{3,50}, but\b", re.I)),
    ("filler_opener", re.compile(r"(?:^|(?<=[.!?] ))(?:Notably|Importantly|Interestingly|Ultimately|Overall|Moreover|Furthermore),", re.M)),
)
SOURCE_NOUNS = re.compile(
    r"\b(?:report|release|statement|publication|bulletin|white paper|website|web ?page|"
    r"readout|communiqu[eé]|press conference|document|documents|records?)\b", re.I)
LEAD_DATE = re.compile(
    r"^(?:On|In|By|As of|Since|Between)?\s*(?:\d{1,2}\s+[A-Z][a-z]+|[A-Z][a-z]+\s+\d{1,2}|\d{4}-\d{2}-\d{2})\b")
LEAD_ATTRIBUTION = re.compile(r"^(?:According to|Based on|Drawing on|Using|The (?:stored|available|supplied) )", re.I)
TRANSITION_STARTS = ("But", "Still", "Yet", "That", "This", "Those", "These", "Meanwhile",
                     "By contrast", "As a result", "Even so", "At the same time",
                     "In practice", "Taken together", "The difference")
ACRONYM = re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]{1,4})?\b")
# Acronyms a general foreign-policy reader already knows; not worth a flag.
COMMON_ACRONYMS = frozenset((
    "US", "UK", "EU", "UN", "NATO", "ASEAN", "PLA", "GDP", "AI", "MND", "MOD",
    "CCP", "PRC", "ROC", "DPRK", "ROK", "FY", "II", "III", "IV", "TV", "HQ",
    "AM", "PM", "UTC", "GMT", "ID", "OK", "PDF", "URL", "NO", "VS", "CEO"))
DOUBLED_WORD = re.compile(r"\b([A-Za-z]{2,})\s+\1\b", re.I)
DOUBLED_ALLOWED = frozenset(("had", "that", "bye", "very", "so", "no"))
PLACEHOLDER = re.compile(
    r"\bTODO\b|\bTBD\b|\bTK\b|\[(?:citation|source|insert|verify|check)[^\]]*\]|lorem ipsum|"
    r"\{\{|\}\}|\bXX+\b|<[a-z/][^>]*>", re.I)
LOWER_SENTENCE = re.compile(r"(?<![A-Za-z.])[a-z]{4,}[.?!] [a-z]{3,}")
LOWER_ALLOWED_BEFORE = frozenset((
    "approx", "estim", "dept", "govt", "mins", "vols", "sept", "oct", "nov",
    "dec", "jan", "feb", "mar", "apr", "jun", "jul", "aug"))
TERMINAL = ("." , "?", "!", '"', "”", "’", ")", "*")


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def words(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", str(text or ""))


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", str(text or "")) if p.strip()]


def sentences(text):
    flat = _norm(text)
    parts = re.split(r"(?<=[.!?])\s+(?=[\"“‘'(\[]?[A-Z0-9])", flat)
    return [p for p in parts if p]


def fingerprint(text):
    """Stable short digest of a block's normalized text (for ledger and diffing)."""
    return hashlib.sha256(_norm(text).casefold().encode("utf-8")).hexdigest()[:12]


def _shingles(text, n=6):
    toks = [w.casefold() for w in words(text)]
    return {" ".join(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))}


def article_blocks(manuscript):
    """Return ``[(heading, text)]`` for an article-first or legacy manuscript.

    A legacy fixed-outline manuscript is projected onto the same shape so the
    checks (and the before/after demonstration) can score both.
    """
    if isinstance(manuscript.get("article"), list):
        return [(str(b.get("heading") or "").strip(), str(b.get("text") or ""))
                for b in manuscript["article"]]
    legacy = (("opening_note", "Overview"), ("what_stood_out", "What stood out"),
              ("why_it_matters", "Why it matters"), ("what_was_routine", "What was routine"),
              ("what_im_watching_next", "What we're watching"),
              ("cross_desk_comparison", "Across the region"))
    return [(label, str(manuscript.get(key) or "")) for key, label in legacy
            if manuscript.get(key)]


def check_article(manuscript, *, desk_by_id=None):
    """Offline narrative report for a validated manuscript.

    Returns ``{"errors": [...], "flags": [...], "metrics": {...}, "hold": bool}``.
    Every entry is ``{"code", "where", "detail"}`` with short details that never
    quote more than a few words of prose. ``hold`` is true only for mechanical
    defects that make the draft unfit to hand to an editor unreviewed.
    """
    errors, flags = [], []

    def err(code, where, detail, major=True):
        errors.append({"code": code, "where": where, "detail": detail, "major": major})

    def flag(code, where, detail):
        flags.append({"code": code, "where": where, "detail": detail})

    blocks = article_blocks(manuscript)
    all_paras = []
    for index, (heading, text) in enumerate(blocks, 1):
        where = "block {}".format(index)
        paras = paragraphs(text)
        if not paras:
            err("empty_block", where, "no paragraph text")
            continue
        for p_index, para in enumerate(paras, 1):
            ploc = "{} paragraph {}".format(where, p_index)
            all_paras.append((ploc, para, index))
            if para.count("**") % 2:
                err("unbalanced_emphasis", ploc, "odd number of ** markers")
            if para.count("(") != para.count(")"):
                err("unbalanced_parenthesis", ploc, "unmatched ( or )", major=False)
            if (para.count('"') % 2) or (para.count("“") != para.count("”")):
                err("unbalanced_quote", ploc, "unmatched double quotation mark", major=False)
            if PLACEHOLDER.search(para):
                err("placeholder_text", ploc, "template or placeholder token")
            for m in DOUBLED_WORD.finditer(para):
                if m.group(1).casefold() not in DOUBLED_ALLOWED:
                    err("doubled_word", ploc, 'repeated word "{}"'.format(m.group(1)), major=False)
            if "  " in para or re.search(r"\s[,.;:?!](?=\s|$)", para):
                err("spacing", ploc, "double space or space before punctuation", major=False)
            for m in LOWER_SENTENCE.finditer(para):
                if m.group(0).split(".")[0].split("?")[0].split("!")[0].casefold() not in LOWER_ALLOWED_BEFORE:
                    err("lowercase_sentence_start", ploc, "sentence begins in lower case", major=False)
                    break
        if not text.rstrip().endswith(TERMINAL):
            err("truncated_block", where, "block does not end in sentence punctuation")
        if heading:
            if len(heading) > MAX_HEADING_CHARS or heading != _norm(heading):
                err("bad_subhead", where, "subhead too long or multi-line")
            if heading.casefold() in RESERVED_HEADINGS:
                err("reserved_subhead", where, "subhead collides with a reserved document heading")
            if heading.rstrip().endswith((".", ":")):
                err("subhead_punctuation", where, "subhead ends with a period or colon", major=False)
            if heading.casefold() in FORCED_HEADINGS:
                flag("stock_subhead", where, 'stock subhead "{}"'.format(heading))

    seen = {}
    for ploc, para, _ in all_paras:
        key = _norm(para).casefold()
        if key in seen:
            err("duplicate_paragraph", ploc, "identical to " + seen[key])
        else:
            seen[key] = ploc
    sentence_seen = {}
    for ploc, para, _ in all_paras:
        for sent in sentences(para):
            if len(words(sent)) >= 10:
                key = _norm(sent).casefold()
                if key in sentence_seen and sentence_seen[key] != ploc:
                    err("repeated_sentence", ploc, "sentence repeats " + sentence_seen[key])
                sentence_seen.setdefault(key, ploc)

    article_text = "\n\n".join(text for _, text in blocks)
    n_words = len(words(article_text))
    sents = sentences(article_text)
    lengths = [len(words(s)) for s in sents] or [0]
    mean_len = sum(lengths) / len(lengths)
    para_lengths = [len(words(p)) for _, p, _ in all_paras] or [0]
    metrics = {
        "standard": STANDARD_VERSION,
        "blocks": len(blocks), "paragraphs": len(all_paras), "words": n_words,
        "sentences": len(sents), "mean_sentence_words": round(mean_len, 1),
        "sentence_length_stdev": round(pstdev(lengths), 1) if len(lengths) > 1 else 0.0,
        "mean_paragraph_words": round(sum(para_lengths) / len(para_lengths), 1),
    }

    # -- editorial heuristics ------------------------------------------------
    if blocks:
        lead_sents = sentences(blocks[0][1])
        first = lead_sents[0] if lead_sents else ""
        head = " ".join(first.split()[:16])
        if LEAD_DATE.match(first) and SOURCE_NOUNS.search(head) or LEAD_ATTRIBUTION.match(first):
            flag("lead_source_first", "block 1", "lead opens with a source, release or date rather than the development")
        elif SOURCE_NOUNS.search(head) and re.search(r"\b(?:publish|releas|post|issu|report)\w*", head, re.I):
            flag("lead_source_first", "block 1", "lead centres on a publication event")
        if first and len(words(first)) > 45:
            flag("lead_long_first_sentence", "block 1", "first sentence exceeds 45 words")

    hedge_total, ending = 0, 0
    for ploc, para, _ in all_paras:
        hits = [name for name, rx in HEDGE_PATTERNS if rx.search(para)]
        hedge_total += len(hits)
        last = sentences(para)[-1] if sentences(para) else ""
        if any(rx.search(last) for _, rx in HEDGE_PATTERNS):
            ending += 1
        if len(hits) >= 3:
            flag("caveat_stacking", ploc, "{} caveat formulas in one paragraph".format(len(hits)))
    p_count = max(1, len(all_paras))
    metrics["hedge_formulas"] = hedge_total
    metrics["paragraphs_ending_on_limitation"] = ending
    if ending / p_count > 0.34 and ending >= 2:
        flag("caveat_endings", "article", "{} of {} paragraphs end on a limitation".format(ending, len(all_paras)))
    if hedge_total / max(1, n_words / 100.0) > 1.6 and hedge_total >= 4:
        flag("caveat_density", "article", "{} caveat formulas in {} words".format(hedge_total, n_words))
    if any(rx.search(article_text) for name, rx in HEDGE_PATTERNS if name == "first_person_limit"):
        flag("researcher_limits_in_article", "article", "article narrates what the researcher could not determine")

    for name, rx in STOCK_PATTERNS:
        count = len(rx.findall(article_text))
        if (name == "not_x_but_y" and count >= 2) or (name != "not_x_but_y" and count >= 1):
            flag(name, "article", "{} instance(s)".format(count))

    triplets = len(re.findall(r"\b[\w'’-]+, [\w'’-]+,? and [\w'’-]+\b", article_text))
    if triplets >= 3:
        flag("mechanical_triplets", "article", "{} three-item lists".format(triplets))
    if mean_len > 30:
        flag("long_sentences", "article", "mean sentence length {:.0f} words".format(mean_len))
    if len(lengths) >= 8 and pstdev(lengths) < 5:
        flag("uniform_sentence_length", "article", "little variation in sentence length")
    if len(para_lengths) >= 5 and max(para_lengths) - min(para_lengths) < 0.3 * max(para_lengths):
        flag("uniform_paragraph_length", "article", "paragraph lengths barely vary")
    passive = len(re.findall(r"\b(?:was|were|been|being|is|are)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", article_text))
    if sents and passive / len(sents) > 0.35:
        flag("passive_density", "article", "{} passive-looking constructions in {} sentences".format(passive, len(sents)))

    expanded = set(re.findall(r"\(([A-Z]{2,6}(?:-[A-Z0-9]{1,4})?)\)", article_text))
    unexplained = []
    for m in ACRONYM.finditer(article_text):
        tok = m.group(0)
        if tok in COMMON_ACRONYMS or tok in expanded or tok in unexplained:
            continue
        unexplained.append(tok)
    if unexplained:
        flag("unexplained_acronym", "article", "no expansion for: " + ", ".join(unexplained[:8]))

    if len(blocks) >= 2:
        lead_set = _shingles(blocks[0][1])
        for index, (_, text) in enumerate(blocks[1:], 2):
            shared = lead_set & _shingles(text)
            if len(shared) >= 3:
                flag("restated_lead", "block {}".format(index), "repeats wording from the lead")
        later = [(i, _shingles(t)) for i, (_, t) in enumerate(blocks, 1)]
        for a in range(len(later)):
            for b in range(a + 1, len(later)):
                if a == 0:
                    continue
                if len(later[a][1] & later[b][1]) >= 4:
                    flag("repeated_wording", "blocks {} and {}".format(later[a][0], later[b][0]),
                         "shared six-word phrases")
        for a in range(1, len(blocks)):
            starts = _norm(blocks[a][1]).split(". ")[0].casefold()
            if starts and starts == _norm(blocks[0][1]).split(". ")[0].casefold():
                flag("restated_lead", "block {}".format(a + 1), "opens with the lead's first sentence")

    transitions = sum(1 for _, para, _ in all_paras[1:]
                      if para.startswith(TRANSITION_STARTS))
    metrics["connected_paragraph_openers"] = transitions
    if len(all_paras) >= 5 and transitions == 0:
        flag("no_paragraph_connections", "article", "no paragraph opens by connecting to the one before")

    if desk_by_id and isinstance(manuscript.get("article"), list):
        for index, block in enumerate(manuscript["article"], 1):
            head = (block.get("heading") or "").casefold()
            if head in ("across the region", "cross-desk comparison", "regional comparison"):
                desks = {desk_by_id.get(i) for i in block.get("citations", [])}
                desks.discard(None)
                if len(desks) < 2:
                    flag("comparison_without_two_desks", "block {}".format(index),
                         "comparison block cites fewer than two desks")

    if n_words < MIN_ARTICLE_WORDS:
        flag("short_article", "article", "{} words".format(n_words))
    if n_words > MAX_ARTICLE_WORDS:
        flag("long_article", "article", "{} words".format(n_words))

    hold = any(e["major"] for e in errors)
    return {"standard": STANDARD_VERSION, "errors": errors, "flags": flags,
            "metrics": metrics, "hold": hold}


HOLD_PHRASE = "OWNER REVIEW REQUIRED BEFORE EDITOR DELIVERY"


def summary_line(report):
    majors = sum(1 for e in report["errors"] if e["major"])
    return ("Narrative QA: {} mechanical error(s) ({} major), {} editorial flag(s); {}".format(
        len(report["errors"]), majors, len(report["flags"]),
        HOLD_PHRASE if report["hold"]
        else "no mechanical hold"))


def format_report_lines(report):
    """Private TXT lines; metadata and short mechanical details, never prose."""
    out = [
        "NARRATIVE QUALITY REPORT (offline checks and editorial heuristics; not a fact check):",
        summary_line(report),
    ]
    if report["hold"]:
        out.append("QUALITY HOLD: a major mechanical defect was detected; the owner should "
                   "inspect this exact draft before any editor delivery.")
    m = report["metrics"]
    out.append("Metrics: {blocks} block(s), {paragraphs} paragraph(s), {words} words, "
               "mean sentence {mean_sentence_words} words, "
               "{paragraphs_ending_on_limitation} paragraph(s) ending on a limitation.".format(**m))
    for item in report["errors"]:
        out.append("- ERROR {} ({}): {}{}".format(
            item["code"], item["where"], item["detail"], "" if item["major"] else " [minor]"))
    for item in report["flags"]:
        out.append("- REVIEW {} ({}): {}".format(item["code"], item["where"], item["detail"]))
    out.append("Flags are editorial prompts, not defects; the owner and editor decide.")
    out.append("END OF NARRATIVE QUALITY REPORT")
    return out
