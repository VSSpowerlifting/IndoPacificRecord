"""Private bilingual QA for Kemhan. No original/translation enters the handoff."""
import re
from datetime import date

from analysis.indonesia_prompts import CATEGORIES, VERSION, evidence_passages

# Conservative lexical gates supplement (not certify) bilingual model reading.
NUMBER = r"(?<!\w)[+-]?\d+(?:[.,:/-]\d+)*(?:%)?"
STAGES = {
    "held": r"\b(?:berlangsung|dilaksanakan|melaksanakan|digelar|menggelar)\b",
    "conducted": r"\b(?:dilaksanakan|melaksanakan|digelar|menggelar)\b",
    "completed": r"\b(?:selesai|menyelesaikan|rampung|tuntas)\b",
    "delivered": r"\b(?:diserahkan|menyerahkan|diterima|menerima)\b",
    "signed": r"\b(?:menandatangani|ditandatangani|penandatanganan)\b",
    "agreed": r"\b(?:disepakati|menyepakati|sepakat|kesepakatan)\b",
    "acquired": r"\b(?:diperoleh|memperoleh|diterima|menerima)\b",
    "deployed": r"\b(?:dikerahkan|mengerahkan|ditempatkan|menempatkan)\b",
}
TENTATIVE = r"\b(?:akan|rencana|direncanakan|berencana|diharapkan|diharap|belum|tidak|bukan|membahas|menjajaki|usulan|mengusulkan)\b"
EN_TENTATIVE = r"\b(?:will|plans?|planned|planning|intends?|proposed|proposal|not|never|discuss\w*|explor\w*|expected|hopes?)\b"


MONTHS = {name: i for i, names in enumerate((
    "januari january", "februari february", "maret march", "april", "mei may",
    "juni june", "juli july", "agustus august", "september", "oktober october",
    "november", "desember december"), 1) for name in names.split()}
MONTH_PATTERN = "|".join(MONTHS)
# These observed industry concepts must belong to the cited passage, including
# in its private translation. They are ordinary translated terms, not names.
CONCEPTS = {
    r"\bresearch\b": r"\b(?:riset|penelitian)\b",
    r"\bdevelopment\b": r"\bpengembangan\b",
    r"\bmanufactur\w*\b": r"\b(?:manufaktur|pembuatan)\b",
    r"\bhuman[- ]resources?\b": r"\b(?:sumber daya manusia|SDM)\b",
    r"\btechnology transfer\b": r"\b(?:alih teknologi|transfer teknologi)\b",
}
TRANSLATED_LABELS = {"Research": CONCEPTS[r"\bresearch\b"],
                     "Development": CONCEPTS[r"\bdevelopment\b"],
                     "Human": CONCEPTS[r"\bhuman[- ]resources?\b"],
                     "Resource": CONCEPTS[r"\bhuman[- ]resources?\b"]}


def factual_values(text):
    """Canonical dates, with all remaining numbers kept exact.

    Kemhan numeric dates are day/month/year. Equivalent English/Indonesian
    month names or zero padding change presentation, not the event date.
    """
    from processing.daily_intake import need
    values = set()

    def replace(match):
        parts = match.groupdict()
        day, month, year = parts['day'], parts['month'], parts.get('year')
        month = MONTHS.get(month.casefold(), month)
        try:
            parsed = date(int(year or 2000), int(month), int(day))
        except (ValueError, TypeError):
            need(False, "daily_date_invalid")
        values.add(('date', int(year) if year else None, parsed.month, parsed.day))
        return ' '

    for pattern in (
        r"(?<!\w)(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\w)",
        r"(?<!\w)(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{4})(?!\w)",
        r"(?<!\w)(?P<day>\d{1,2})\s+(?P<month>" + MONTH_PATTERN + r")(?:\s+(?P<year>\d{4}))?(?!\w)",
    ):
        text = re.sub(pattern, replace, text, flags=re.I)
    values.update(('number', number) for number in re.findall(NUMBER, text))
    # Numeric suffixes are part of a unit/model identity, not just a quantity.
    values.update(('identifier', token.upper()) for token in re.findall(
        r'\b(?=[\w/-]*[A-Z])(?=[\w/-]*\d)[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*\b', text))
    return values, text


def check_status(evidence, english):
    from processing.daily_intake import need
    tentative = re.search(TENTATIVE, evidence, re.I)
    if tentative:
        need(re.search(EN_TENTATIVE, english, re.I) is not None,
             "daily_modality_or_contradiction_hold")
    negative = re.search(r"\b(?:tidak|belum|bukan|tak|tanpa)\b", evidence, re.I)
    # A numbered-document abbreviation is not negation and cannot preserve
    # a real source negation. Keep every other negative token eligible.
    english_negative = re.search(r"\b(?:not|never|without)\b|\bno\b(?!\.\s*\d)|n['’]t\b", english, re.I)
    if negative:
        need(english_negative is not None, "daily_negation_lost")
    else:
        need(english_negative is None, "daily_negation_unsupported")
    if tentative:
        need(not re.search(r"\b(?:took place|(?:was|were|has been|have been|had been)\s+(?:held|conducted|completed|delivered|signed|acquired|agreed|deployed))\b", english, re.I),
             "daily_completed_action_unsupported")
        for word in STAGES:
            if re.search(r"\b" + word + r"\b", english, re.I):
                need(re.search(r"\b(?:will|would|may|could|not)\s+(?:be\s+)?" + word + r"\b", english, re.I) is not None,
                     "daily_completed_action_unsupported")
    for word, support in STAGES.items():
        if re.search(r"\b" + word + r"\b", english, re.I):
            need(re.search(support, evidence, re.I) is not None,
                 "daily_completed_action_unsupported")


def office_checked_text(evidence, sentence):
    """Resolve only the observed Head-of appositive, with a local holder.

    Conservative grammar: institution and named holder are comma-delimited.
    A locally supported head-injury compound is medical vocabulary. Other
    unknown forms remain held. This is neither a name nor a word whitelist.
    """
    from processing.daily_intake import need
    source_roles = list(re.finditer(
        r"\bKepala (?P<institution>[^,;\n]+), (?P<holder>[^,;\n]+),", evidence))
    translated = re.compile(
        r"\bHead of (?P<institution>[^,;\n]+), (?P<holder>[^,;\n]+),", re.I)
    replacements = []
    for head in re.finditer(r"\bhead\b", sentence, re.I):
        if re.match(r"head injur(?:y|ies)\b", sentence[head.start():], re.I):
            need(re.search(r"\b(?:cedera kepala|head injur(?:y|ies))\b", evidence, re.I)
                 is not None, "daily_name_or_office_unsupported")
            # Lexical projection only: copying still uses the unmodified fact.
            replacements.append((head.start(), head.end(), "head"))
            continue
        role = translated.match(sentence, head.start())
        supported = False
        if role and not re.search(r"\b(?:acting|deputy|former|assistant|vice)\s+$",
                                  sentence[:head.start()], re.I):
            for source in source_roles:
                # Do not turn an acting/deputy/former role into an unqualified one.
                if re.search(r"(?:\bPlt\.|\bWakil|\bMantan)\s+$",
                             evidence[:source.start()], re.I):
                    continue
                holder = source['holder']
                # Only observed rank/honorific prefixes may be omitted; the
                # complete personal name must remain, with exact spelling.
                name = re.sub(r"^(?:Brigjen TNI |dr\. )+", "", holder)
                if (role['institution'] == source['institution']
                        and role['holder'] in (holder, name)):
                    supported = True
                    break
        need(supported, "daily_name_or_office_unsupported")
        replacements.append((head.start(), head.end(), "Kepala"))
    for start, end, replacement in reversed(replacements):
        sentence = sentence[:start] + replacement + sentence[end:]
    return sentence


def quality_check(record, reading):
    from processing.daily_intake import need, digest
    need(type(reading) is dict and reading.get("passed_relevance") is True
         and reading.get("requires_translation") is False,
         "daily_analysis_incomplete")
    # Only evidence passages are translated privately, never a full article.
    facts = reading.get("facts")
    summary = reading.get("summary_english")
    need(type(summary) is str and 5 <= len(summary.split()) <= 90,
         "daily_summary_invalid")
    need(type(facts) is list and len(facts) == 2
         and all(type(f) is dict and set(f) == {"sentence", "evidence", "evidence_translation"}
                 and all(type(v) is str for v in f.values()) for f in facts),
         "daily_evidence_incomplete")
    need(" ".join(f["sentence"] for f in facts) == summary,
         "daily_summary_coverage_incomplete")
    source = record["title"] + "\n" + record["body"]
    supplied = set(dict(evidence_passages(record["body"])).values())
    for f in facts:
        sentence, evidence, translation = f["sentence"], f["evidence"], f["evidence_translation"]
        need(20 <= len(evidence) <= 500 and evidence in record["body"],
             "daily_evidence_not_in_original")
        need(evidence in supplied, "daily_evidence_not_supplied")
        need(10 <= len(translation) <= 1800 and not re.search(r"[\u3400-\u9fff]", translation),
             "daily_private_translation_incomplete")
        need(not re.search(r"[\[\]]", translation), "daily_private_translation_completion_held")
        need(re.search(r"\bKemhan\b", sentence) is not None, "daily_attribution_missing")
        original_values, _ = factual_values(evidence)
        translation_values, translation_text = factual_values(translation)
        sentence_values, sentence_text = factual_values(sentence)
        need(translation_values == original_values and sentence_values <= original_values,
             "daily_quantity_or_date_unsupported")
        # Names in a sentence must be local to its cited passage. Date words
        # were already compared semantically. Ordinary translated labels must
        # retain their Indonesian concept in that same passage.
        for token in re.findall(r"\b[A-Z][A-Za-z'-]+\b", office_checked_text(evidence, sentence_text)):
            if token not in {"Kemhan", "The", "According", "It", "This"}:
                need(token in evidence or (token in TRANSLATED_LABELS
                     and re.search(TRANSLATED_LABELS[token], evidence, re.I)),
                     "daily_name_or_office_unsupported")
        # A proper source name elsewhere in the article is not evidence for
        # inserting it into this passage's private translation.
        for token in re.findall(r"\b[A-Z][A-Za-z'-]+\b", translation_text):
            if re.search(r"\b" + re.escape(token) + r"\b", source):
                need(re.search(r"\b" + re.escape(token) + r"\b", evidence) is not None,
                     "daily_private_translation_name_unsupported")
        for english in (translation, sentence):
            for concept, support in CONCEPTS.items():
                if re.search(concept, english, re.I):
                    need(re.search(support, evidence, re.I) is not None,
                         "daily_cross_passage_claim_unsupported")
            check_status(evidence, english)
        words = re.findall(r"\w+", sentence.casefold())
        source_words = " " + " ".join(re.findall(r"\w+", source.casefold())) + " "
        need(all(" " + " ".join(words[i:i+12]) + " " not in source_words
                 for i in range(max(0, len(words) - 11))), "daily_original_excerpt_prohibited")
        need(not re.search(r"\b(?:proves?|confirms? readiness|strategic shift|game.chang\w*|unprecedented)\b", sentence, re.I),
             "daily_strategic_inference_unsupported")
        normalized = " " + " ".join(words) + " "
        for original_sentence in re.split(r"(?<=[.!?])\s+", record["body"]):
            original_words = re.findall(r"\w+", original_sentence.casefold())
            if len(original_words) >= 6:
                need(" " + " ".join(original_words) + " " not in normalized,
                     "daily_original_sentence_prohibited")
    cats = reading.get("categories")
    need(type(cats) is list and cats and all(type(c) is str and c in CATEGORIES for c in cats),
         "daily_analysis_incomplete")
    if "south_china_sea" in cats:
        need(re.search(r"\b(?:Laut (?:Cina|China) Selatan|South China Sea)\b", source, re.I) is not None,
             "daily_topic_unsupported")
    # Initial family policy publishes factual explanations, without significance
    # claims. A flag needs a separately reviewed Indonesian evidence rubric.
    need(reading.get("is_significant") is False
         and reading.get("significance_reasoning") is None,
         "daily_indonesia_flag_held")
    need(type(reading.get("model_id")) is str and bool(reading["model_id"])
         and reading.get("prompt_version") == VERSION, "daily_model_provenance_incomplete")
    return digest({"source": record["content_sha256"], "facts": facts, "version": "id-quality-v3"})
