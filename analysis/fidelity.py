"""Unqualified source-fidelity candidate; inactive unless explicitly enabled.

These checks detect specific contradictions, not general semantic correctness.
They never repair prose, infer missing facts, or certify a model's quality.
"""
import re

# Retain the source rank alongside English so distinct grades cannot silently
# collapse to the same English rendering. Only Chinese source text uses this
# vocabulary; other desks retain their own terminology and QA.
_RANKS = re.compile(r"[一二三四]级军士长|[一二]级上士")
_BYLINE = re.compile(r"(?:解放军报|新华社)记者\s+[\u4e00-\u9fff]{2,4}(?=\s|[，。])")
_SIMULATED_SUB = re.compile(r"\b(?:simulated|mock|notional)\s+(?:blue[- ]force\s+)?submarine\b", re.I)
_LIVE_FIRE = re.compile(r"\blive[- ]fire\b", re.I)
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


def check(source: str, output: str, *, translation=False):
    """Return a content-free hold reason or None. No source text enters logs."""
    if translation:
        for rank in set(_RANKS.findall(source)):
            if rank not in output:
                return "source_rank_anchor_missing"
        for byline in _BYLINE.findall(source):
            if re.sub(r"\s+", "", byline) not in re.sub(r"\s+", "", output):
                return "source_byline_anchor_missing"
        # Full translation preserves every explicit year, unlike a summary.
        if set(_YEAR.findall(source)) - set(_YEAR.findall(output)):
            return "source_chronology_missing"
    if _SIMULATED_SUB.search(output) and not (
            _SIMULATED_SUB.search(source)
            or re.search(r"(?:模拟|假想|仿真)潜艇", source)):
        return "unsupported_submarine_qualifier"
    if _LIVE_FIRE.search(output) and not (
            _LIVE_FIRE.search(source) or "实弹" in source):
        return "unsupported_live_fire"
    # Catch the observed transfer/construction date swap without requiring a
    # summary to repeat the whole chronology. An omitted event is not a pass
    # for that event. Restrict to sentences with a single explicit year.
    source_transfer_years = set()
    for sentence in re.split(r"[.!?。！？\n]+", source):
        years = set(_YEAR.findall(sentence))
        if len(years) == 1 and re.search(r"\btransfer(?:red)?\b", sentence, re.I):
            source_transfer_years.update(years)
    if len(source_transfer_years) == 1:
        for sentence in re.split(r"[.!?。！？\n]+", output):
            years = set(_YEAR.findall(sentence))
            if (len(years) == 1 and re.search(r"\btransfer(?:red)?\b", sentence, re.I)
                    and years != source_transfer_years):
                return "transfer_chronology_changed"
    return None


# Preserved evaluated instructions. Production builders remain in prompts.py.
PROMPT_VERSION = "v2-source-fidelity"
_TRANSLATION_NOTE = """\
Preserve every name, date, number, byline, affiliation and quotation boundary.
Do not merge reporter commentary into a speaker's quotation. Keep embedded official
English passages and all sections, including captions and endings. Do not silently
collapse repeated bilingual material. Never narrow a general NCO designation to a
specific rank. For graded NCO ranks (一级上士, 二级上士, 一级军士长, 二级军士长,
三级军士长, 四级军士长), retain each exact Chinese rank in parentheses next to its
English rendering. Retain a Chinese reporter byline verbatim in parentheses next
to its translation, preserving which named person belongs to which outlet.

"""

_ANALYSIS_NOTE = """\
Source fidelity: attach a qualifier only to the action or entity it qualifies in
the source. A simulated attack does not establish a simulated submarine. Live-force
activity with simulated strikes does not establish live-fire activity. Preserve
which event each date describes: a transfer date and later construction date are
not interchangeable. Do not invent reporting rarity, firsts, affiliations, names,
ranks, numbers or Chinese terminology. Attribute official claims, distinguish
interpretation explicitly, and omit interpretations without source support.

"""


def build_translation_messages(title, body):
    from analysis import prompts
    messages = prompts.build_translation_messages(title, body)
    marker = "Do not add explanatory content"
    messages[0]["content"] = messages[0]["content"].replace(
        marker, _TRANSLATION_NOTE + marker, 1)
    return messages


def build_summary_messages(title, body):
    from analysis import prompts
    messages = prompts.build_summary_messages(title, body)
    messages[0]["content"] = messages[0]["content"].replace(
        "Title: ", _ANALYSIS_NOTE + "Title: ", 1)
    return messages


def build_category_messages(title, body):
    from analysis import prompts
    messages = prompts.build_category_messages(title, body)
    messages[0]["content"] = messages[0]["content"].replace(
        "Title: ", _ANALYSIS_NOTE + "Title: ", 1)
    return messages
