"""Korea-specific path inside the shared Analyzer's budgeted model engine.

Inactive in Daily until governed article-corpus admission and automatic
English-publication policy are independently verified. No source crawling,
publication, permissions, or model calls at import time.
"""
import logging

from analysis.korea_prompts import (
    TRANSLATION_SYSTEM, TRANSLATION_VERSION, translation_messages,
)
from analysis.usage import TASK_TRANSLATION
from config import ANALYSIS_MODEL, RELEVANCE_THRESHOLD, TRANSLATION_MAX_TOKENS

logger = logging.getLogger(__name__)


def translate(analyzer, title, body):
    """Existing structured translation tool, with Korean-specific instructions."""
    from analysis.analyzer import AnalysisError
    system = [{"type": "text", "text": TRANSLATION_SYSTEM,
               "cache_control": {"type": "ephemeral"}}]
    data = analyzer._call_tool(
        translation_messages(title, body), analyzer._TRANSLATION_TOOL,
        max_tokens=TRANSLATION_MAX_TOKENS, temperature=0.0,
        system=system, task=TASK_TRANSLATION)
    heading, translated = data.get("title_en"), data.get("body_en")
    if (not isinstance(heading, str) or not heading.strip()
            or not isinstance(translated, str) or not translated.strip()):
        analyzer.usage.mark_failed(TASK_TRANSLATION, ANALYSIS_MODEL)
        raise AnalysisError("Korea translation incomplete")
    return heading, translated


def analyze(analyzer, title, body, profile):
    """Relevance, Korean→English translation, then source-grounded summary.

    A missing stage never returns a completed English record. Model semantic
    accuracy is NOT independently established by this structural check.
    """
    from analysis.analyzer import AnalysisError, FatalAPIError
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
            profile.prompt_version, TRANSLATION_VERSION,
            profile.analysis_prompt_version),
    }
    if not partial["passed_relevance"]:
        return partial
    try:
        heading, text = translate(analyzer, title, body)
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
    }
