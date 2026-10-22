"""Korea-specific path inside the shared Analyzer's budgeted model engine.

Inactive in Daily until governed article-corpus admission and automatic
English-publication policy are independently verified. No source crawling,
publication, permissions, or model calls at import time.
"""
import logging

from analysis.korea_prompts import (
    TRANSLATION_PROMPT_ID, TRANSLATION_SYSTEM, TRANSLATION_TOOL,
    translation_messages,
)
from analysis.usage import TASK_TRANSLATION
from config import ANALYSIS_MODEL, RELEVANCE_THRESHOLD, TRANSLATION_MAX_TOKENS
from core.korea_corpus_bridge import document_heading, source_lines
from processing import korea_translation_qa as qa

logger = logging.getLogger(__name__)


def translate(analyzer, body):
    """Line-aligned translation: [{index, text_en}] for every source line.

    Structural failure (no list, malformed entries) is a failed paid call and
    raises AnalysisError; content and alignment are judged by the QA gate.
    """
    from analysis.analyzer import AnalysisError
    lines = source_lines(body)
    if lines is None:
        raise AnalysisError("Korea source line breaks unsupported")
    system = [{"type": "text", "text": TRANSLATION_SYSTEM,
               "cache_control": {"type": "ephemeral"}}]
    data = analyzer._call_tool(
        translation_messages(lines), TRANSLATION_TOOL,
        max_tokens=TRANSLATION_MAX_TOKENS, temperature=0.0,
        system=system, task=TASK_TRANSLATION)
    entries = data.get("translations") if isinstance(data, dict) else None
    if (not isinstance(entries, list) or not entries
            or not all(isinstance(e, dict) for e in entries)):
        analyzer.usage.mark_failed(TASK_TRANSLATION, ANALYSIS_MODEL)
        raise AnalysisError("Korea translation incomplete")
    return entries


def analyze(analyzer, title, body, profile):
    """Relevance, line-aligned Korean→English translation, then summary.

    A missing stage never returns a completed English record. A translation
    that fails the deterministic QA gate stops before the summary call and is
    returned with `translation_qa` for the caller to hold; the gate does not
    establish semantic accuracy.
    """
    from analysis.analyzer import AnalysisError, FatalAPIError
    found = document_heading(body)
    if found is None or qa.dispatch_hold(
            body, max_output_tokens=TRANSLATION_MAX_TOKENS):
        logger.error("Korea source hold before any model call")
        return None
    heading_index = found[0]
    try:
        score, reason = analyzer.score_relevance(title, body, profile=profile)
    except FatalAPIError:
        raise
    except AnalysisError as exc:
        logger.error("Korea relevance hold: %s", exc)
        return None
    partial = {
        "relevance_score": score, "relevance_reasoning": reason,
        "passed_relevance": score >= RELEVANCE_THRESHOLD,
        "requires_translation": True, "model_id": ANALYSIS_MODEL,
        "prompt_version": "%s+%s+%s" % (
            profile.prompt_version, TRANSLATION_PROMPT_ID,
            profile.analysis_prompt_version),
    }
    if not partial["passed_relevance"]:
        return partial
    try:
        entries = translate(analyzer, body)
    except FatalAPIError:
        raise
    except AnalysisError as exc:
        logger.error("Korea translation hold: %s", exc)
        return partial
    checked = qa.check_translation(body, entries)
    if not checked.passed:
        return {**partial, "translation_entries": entries,
                "translation_qa": checked}
    english = qa.align(entries, len(source_lines(body)))
    heading = english[heading_index].strip()
    text = "\n".join(english)
    try:
        summary, flagged, flag_reason = analyzer._desk_summary_and_flag(
            heading, text, profile)
    except FatalAPIError:
        raise
    except AnalysisError as exc:
        logger.error("Korea English processing hold: %s", exc)
        return partial
    return {
        **partial,
        "title_english": heading,
        "text_english": text,
        "summary_english": summary,
        "categories": [],  # No use of China-specific PLA categories.
        "is_significant": flagged,
        "significance_reasoning": flag_reason,
        "translation_entries": entries,  # QA input only; never stored.
        "heading_index": heading_index,
    }
