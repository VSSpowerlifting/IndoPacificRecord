"""Private bilingual QA for Kemhan. No original/translation enters the handoff."""
import re

from analysis.indonesia_prompts import CATEGORIES, VERSION

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
    for f in facts:
        sentence, evidence, translation = f["sentence"], f["evidence"], f["evidence_translation"]
        need(20 <= len(evidence) <= 500 and evidence in record["body"],
             "daily_evidence_not_in_original")
        need(10 <= len(translation) <= 1800 and not re.search(r"[\u3400-\u9fff]", translation),
             "daily_private_translation_incomplete")
        need(re.search(r"\bKemhan\b", sentence) is not None, "daily_attribution_missing")
        original_numbers = set(re.findall(NUMBER, evidence))
        need(set(re.findall(NUMBER, translation)) == original_numbers
             and set(re.findall(NUMBER, sentence)) <= original_numbers,
             "daily_quantity_or_date_unsupported")
        # Preserve names/ranks/units rather than approve model-created aliases.
        for token in re.findall(r"\b[A-Z][A-Za-z'-]+\b", sentence):
            if token not in {"Kemhan", "The", "According", "It", "This"}:
                need(token in evidence, "daily_name_or_office_unsupported")
        if re.search(TENTATIVE, evidence, re.I):
            need(re.search(EN_TENTATIVE, translation, re.I) is not None
                 and re.search(EN_TENTATIVE, sentence, re.I) is not None,
                 "daily_modality_or_contradiction_hold")
        negative = re.search(r"\b(?:tidak|belum|bukan|tak|tanpa)\b", evidence, re.I)
        if negative:
            for english in (translation, sentence):
                need(re.search(r"\b(?:not|no|never|without)\b|n['’]t\b", english, re.I) is not None,
                     "daily_negation_lost")
        if re.search(TENTATIVE, evidence, re.I):
            # A past-tense outcome cannot become safe by placing 'planned' or
            # 'discussions' elsewhere in the sentence.
            need(not re.search(r"\b(?:took place|(?:was|were|has been|have been|had been)\s+(?:held|conducted|completed|delivered|signed|acquired|agreed|deployed))\b", sentence, re.I),
                 "daily_completed_action_unsupported")
            for word in STAGES:
                if re.search(r"\b" + word + r"\b", sentence, re.I):
                    need(re.search(r"\b(?:will|would|may|could|not)\s+(?:be\s+)?" + word + r"\b", sentence, re.I) is not None,
                         "daily_completed_action_unsupported")
        for word, support in STAGES.items():
            if re.search(r"\b" + word + r"\b", sentence, re.I):
                need(re.search(support, evidence, re.I) is not None,
                     "daily_completed_action_unsupported")
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
    return digest({"source": record["content_sha256"], "facts": facts, "version": "id-quality-v1"})
