"""
Desk-scoped relevance screening.

Both screening stages were written for the China Desk: the keyword pre-filter
matches PLA vocabulary (and the US spelling "defense", which a Singapore
release never uses), and the model prompt asks whether a Chinese-language
article covers Chinese military organisations. Applied to Singapore MINDEF
releases they reject by construction — 13 of 14 Singapore records screened by
2026-09-28 were rejected by the model as "not Chinese military", and the 14th
failed the keyword stage.

A `ScreeningProfile` says, per desk, how each stage judges a record:

  * `keyword_prefilter` — True: the shared China keyword lists
    (processing.relevance.passes_keyword_filter). False: the source itself is
    the desk's declared scope, so every record from it goes on to the model
    stage. Nearly every MINDEF release names "MINDEF" or "Minister for
    Defence", so a keyword list there would filter nothing.
  * `build_messages` / `system_prompt` — the model prompt for the desk.
    `system_prompt` is None for the Analyzer's existing system prompt. A desk
    prompt is built on first use from the desk's scope in desks/registry.json,
    so routing and the daily-queue gate never read that file.
  * `build_analysis_messages` / `analysis_system_prompt` — what follows a
    pass. None is the China path, Analyzer.analyze(): translation from
    Chinese, the China summary and the PLA category taxonomy. A desk builder
    is Analyzer.analyze_desk(): one call that summarises the original text and
    sets the model flag, with no translation and no categories. A desk whose
    sources publish in English (Singapore) must never take the China path.
  * `daily_queue` — whether pipeline.py sends the desk's records to the model
    at all. A desk is in the daily queue only when it has both its own
    screening and its own post-pass analysis; any other non-China desk is held
    out, and its records stay `passed_relevance IS NULL` ("awaiting
    screening"). Singapore was held on this ground from 2026-09-29 until its
    analysis path existed (docs/SINGAPORE_SCREENING_REPAIR_2026-09-29.md §6).

Unregistered desks are held out of Daily and cannot dispatch model calls.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, List, Optional

from analysis.korea_prompts import (
    RELEVANCE_VERSION as KOREA_RELEVANCE_VERSION,
    ANALYSIS_VERSION as KOREA_ANALYSIS_VERSION,
    relevance_messages as build_korea_relevance_messages,
    analysis_messages as build_korea_analysis_messages,
    system_prompt as build_korea_system_prompt,
)

from analysis.prompts import (
    PROMPT_VERSION,
    SINGAPORE_ANALYSIS_PROMPT_VERSION,
    SINGAPORE_RELEVANCE_PROMPT_VERSION,
    build_relevance_messages,
    build_singapore_analysis_messages,
    build_singapore_analysis_system_prompt,
    build_singapore_relevance_messages,
    build_singapore_system_prompt,
)

DEFAULT_DESK = "china"


def _declared_scope(desk_id: str) -> str:
    from core.desk_registry import get_desk_registry
    entry = get_desk_registry().get(desk_id)
    if entry is None or not entry.scope:
        raise LookupError("desks/registry.json declares no scope for %r" % desk_id)
    return entry.scope


@dataclass(frozen=True)
class ScreeningProfile:
    desk_id: str
    keyword_prefilter: bool
    daily_queue: bool
    build_messages: Callable[[str, str], List[dict]]
    prompt_version: str
    build_system_prompt: Optional[Callable[[str], str]] = None
    build_analysis_messages: Optional[Callable[[str, str], List[dict]]] = None
    build_analysis_system_prompt: Optional[Callable[[str], str]] = None
    analysis_prompt_version: Optional[str] = None
    categories: tuple = ()

    @property
    def system_prompt(self) -> Optional[str]:
        if self.build_system_prompt is None:
            return None
        return self.build_system_prompt(_declared_scope(self.desk_id))

    @property
    def analysis_system_prompt(self) -> Optional[str]:
        if self.build_analysis_system_prompt is None:
            return None
        return self.build_analysis_system_prompt(_declared_scope(self.desk_id))

    @property
    def translates(self) -> bool:
        """True for the China path: a pass is translated from Chinese."""
        return self.build_analysis_messages is None


CHINA_PROFILE = ScreeningProfile(
    desk_id="china",
    keyword_prefilter=True,
    daily_queue=True,
    build_messages=build_relevance_messages,
    prompt_version=PROMPT_VERSION,
)

SINGAPORE_PROFILE = ScreeningProfile(
    desk_id="singapore",
    keyword_prefilter=False,
    daily_queue=True,
    build_messages=build_singapore_relevance_messages,
    prompt_version=SINGAPORE_RELEVANCE_PROMPT_VERSION,
    build_system_prompt=build_singapore_system_prompt,
    build_analysis_messages=build_singapore_analysis_messages,
    build_analysis_system_prompt=build_singapore_analysis_system_prompt,
    analysis_prompt_version=SINGAPORE_ANALYSIS_PROMPT_VERSION,
)

# Installed but kept out of paid Daily until source admission and publication
# QA are complete. Model processing can be verified offline and on scratch DBs.
KOREA_PROFILE = ScreeningProfile(
    desk_id="korea",
    keyword_prefilter=False,
    daily_queue=False,
    build_messages=build_korea_relevance_messages,
    prompt_version=KOREA_RELEVANCE_VERSION,
    build_system_prompt=build_korea_system_prompt,
    build_analysis_messages=build_korea_analysis_messages,
    build_analysis_system_prompt=build_korea_system_prompt,
    analysis_prompt_version=KOREA_ANALYSIS_VERSION,
)

def _unsupported(*args):
    raise LookupError("unsupported_desk_processing_profile")


UNSUPPORTED_PROFILE = ScreeningProfile(
    desk_id="unsupported", keyword_prefilter=False, daily_queue=False,
    build_messages=_unsupported, prompt_version="unsupported",
    build_analysis_messages=_unsupported,
)

from analysis.philippines_prompts import (  # explicit English-only contract
    relevance_messages, analysis_messages, system_prompt, CATEGORIES,
)

PHILIPPINES_PROFILE = ScreeningProfile(
    desk_id="philippines", keyword_prefilter=False,
    # Private originals use the shared private intake; never the public
    # articles queue, whose schema contains publisher title/body text.
    daily_queue=False, build_messages=relevance_messages,
    prompt_version="ph-relevance-v1", build_system_prompt=system_prompt,
    build_analysis_messages=analysis_messages,
    build_analysis_system_prompt=system_prompt,
    analysis_prompt_version="ph-analysis-v8", categories=CATEGORIES,
)

_PROFILES: Dict[str, ScreeningProfile] = {
    "china": CHINA_PROFILE,
    "singapore": SINGAPORE_PROFILE,
    "korea": KOREA_PROFILE,
    "philippines": PHILIPPINES_PROFILE,
}

# A non-China desk in the daily queue without its own analysis would have its
# passes translated "from Chinese" and tagged with the PLA taxonomy.
for _p in _PROFILES.values():
    if _p.daily_queue and _p is not CHINA_PROFILE and _p.translates:
        raise AssertionError(
            "%s is in the daily queue without its own analysis" % _p.desk_id)


def profile_for_desk(desk_id: Optional[str]) -> ScreeningProfile:
    """Explicit registered desks only; missing/unknown desks fail closed."""
    return _PROFILES.get(desk_id, UNSUPPORTED_PROFILE)


@lru_cache(maxsize=1)
def _desk_by_source() -> Dict[str, str]:
    from core.manifests import load_all_desks
    return {src.slug: desk_id
            for desk_id, desk in load_all_desks().items()
            for src in desk.sources}


def desk_for_source(source_slug: Optional[str]) -> Optional[str]:
    """The desk a source belongs to, from desks/*/manifest.json."""
    if not source_slug:
        return None
    return _desk_by_source().get(source_slug)


def profile_for_source(source_slug: Optional[str]) -> ScreeningProfile:
    if source_slug in ("ph_afp_articles", "ph_nsc_official_statements"):
        return PHILIPPINES_PROFILE
    return profile_for_desk(desk_for_source(source_slug))
