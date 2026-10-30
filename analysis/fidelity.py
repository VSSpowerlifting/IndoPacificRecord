"""Small source-grounded rejection rules for demonstrated model failures.

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
