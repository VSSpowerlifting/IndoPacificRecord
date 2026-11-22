"""Private bilingual QA for DAPA. No original or translation enters the handoff.

Conservative lexical gates supplement, and never certify, the model reading.
They cannot establish Korean semantic accuracy; that remains a separate review.
Error codes are fixed and carry no source text.
"""
import re

from analysis.korea_dapa_prompts import CATEGORIES, VERSION, evidence_passages

QUALITY_VERSION = "kr-dapa-quality-v1"
CJK = r"[ᄀ-ᇿ㄰-㆏가-힯㐀-鿿豈-﫿]"
DIGITS = r"\d+(?:[.,]\d+)*"
# Plans, reviews and discussions are not completed acts.
MODAL = r"(?:예정|계획|추진|검토|논의|협의|협상|희망|기대|목표)"
EN_MODAL = (r"\b(?:will|would|plans?|planned|planning|intends?|aims?|expects?|"
            r"expected|review\w*|discuss\w*|consult\w*|negotiat\w*|seeks?|"
            r"proposed|scheduled|pursu\w*|goal|hopes?)\b")
COMPLETED = (r"\b(?:took place|(?:was|were|has been|have been|had been)\s+"
             r"(?:held|conducted|completed|delivered|signed|concluded|deployed|"
             r"awarded|approved|finalized|agreed))\b")
NEGATION = r"(?:않|못|없|아니|미\s?체결|불가)"
EN_NEGATION = r"\b(?:not|never|without|no)\b|n['’]t\b"
STRATEGIC = (r"\b(?:proves?|confirms? readiness|strategic shift|game.chang\w*|"
             r"unprecedented|signals?|demonstrates? resolve|deterr\w*)\b")


def _numbers(text):
    return {n.replace(",", "") for n in re.findall(DIGITS, text)}


def check_status(evidence, english):
    from processing.daily_intake import need
    if re.search(MODAL, evidence):
        need(re.search(EN_MODAL, english, re.I) is not None,
             "daily_modality_or_contradiction_hold")
        need(re.search(COMPLETED, english, re.I) is None,
             "daily_completed_action_unsupported")
    english_negative = re.search(EN_NEGATION, english, re.I) is not None
    if re.search(NEGATION, evidence):
        need(english_negative, "daily_negation_lost")
    else:
        need(not english_negative, "daily_negation_unsupported")


def quality_check(record, reading):
    from processing.daily_intake import need, digest
    need(type(reading) is dict and reading.get("passed_relevance") is True
         and reading.get("requires_translation") is False,
         "daily_analysis_incomplete")
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
    need(facts[0]["evidence"] != facts[1]["evidence"]
         or facts[0]["sentence"] != facts[1]["sentence"], "daily_evidence_incomplete")
    supplied = set(dict(evidence_passages(record["body"])).values())
    for f in facts:
        sentence, evidence, translation = f["sentence"], f["evidence"], f["evidence_translation"]
        need(20 <= len(evidence) <= 500 and evidence in record["body"],
             "daily_evidence_not_in_original")
        need(evidence in supplied, "daily_evidence_not_supplied")
        need(10 <= len(translation) <= 1800 and not re.search(CJK, translation),
             "daily_private_translation_incomplete")
        need(not re.search(r"[\[\]]", translation), "daily_private_translation_completion_held")
        need(not re.search(CJK, sentence), "daily_public_text_not_english")
        need(re.search(r"\bDAPA\b", sentence) is not None, "daily_attribution_missing")
        need(not re.search(r"[\"“”]", sentence), "daily_original_excerpt_prohibited")
        source_numbers = _numbers(evidence)
        need(_numbers(sentence) <= source_numbers and _numbers(translation) <= source_numbers,
             "daily_quantity_or_date_unsupported")
        check_status(evidence, translation)
        check_status(evidence, sentence)
        words = re.findall(r"\w+", sentence.casefold())
        private = " " + " ".join(re.findall(r"\w+", translation.casefold())) + " "
        need(all(" " + " ".join(words[i:i + 12]) + " " not in private
                 for i in range(max(0, len(words) - 11))),
             "daily_original_excerpt_prohibited")
        need(re.search(STRATEGIC, sentence, re.I) is None,
             "daily_strategic_inference_unsupported")
    cats = reading.get("categories")
    need(type(cats) is list and cats and len(set(cats)) == len(cats)
         and all(type(c) is str and c in CATEGORIES for c in cats),
         "daily_analysis_incomplete")
    if "south_china_sea" in cats:
        need("남중국해" in record["title"] + "\n" + record["body"], "daily_topic_unsupported")
    # Initial family policy has no significance rubric; a flag is held.
    need(reading.get("is_significant") is False
         and reading.get("significance_reasoning") is None,
         "daily_dapa_flag_held")
    need(type(reading.get("model_id")) is str and bool(reading["model_id"])
         and reading.get("prompt_version") == VERSION, "daily_model_provenance_incomplete")
    return digest({"source": record["content_sha256"], "facts": facts, "version": QUALITY_VERSION})
