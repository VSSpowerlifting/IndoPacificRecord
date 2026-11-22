"""Global Times military: replay the privately collected, signed captures.

DECISION_LOG 2026-11-22 (action D). The public Daily makes no request to the
publisher for this source. A private collector keeps the custody and signs
``global_times_mil.captures.json``; the Daily's fetch step places it in
``$IPR_DAILY_INTAKE_DIR`` (only when ``CN_GLOBAL_TIMES_HANDOFF_ENABLED`` is
``"true"``). This adapter authenticates it with ``DAILY_GLOBAL_TIMES_MIL_KEY``
and yields one document per record whose ``raw`` is exactly the dict the
legacy scraper's ``parse_article`` produced, so normalisation, dedup, the
keyword filter, ``insert_article`` (and its China hold assertion), the record
id allocator and the model lanes run unchanged.

It fails closed with zero documents and a named failure status: an absent
envelope, a bad MAC or shape, missing collection facts, or a failed or stale
private collection. A degraded GT source degrades the Daily exactly as a
listing failure of the old scraper did. It never reports
``ok_no_publications`` for an envelope it could not trust.

Deliberately imports no network library.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from core.collection import global_times_handoff as handoff
from core.collection import status as st
from core.collection.contract import (CaptureResult, CandidateReference,
                                      CollectionWindow, DiscoveryResult,
                                      ExtractedDocument, ExtractionResult,
                                      SourceAdapter, SourceRunResult)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GlobalTimesHandoffAdapter(SourceAdapter):
    """Signed private-custody replay for ``global_times_mil``."""

    #: The private collector already covers [target-2, target]; the replay is
    #: whatever the latest signed envelope carries.
    production_lookback_days = 0

    def __init__(self, source, *, envelope_path=None, key=None, now=None) -> None:
        super().__init__(source)
        self._envelope_path = envelope_path
        self._key = key
        self._clock = now

    # ── inputs ───────────────────────────────────────────────────────────────

    def envelope_path(self) -> Optional[Path]:
        if self._envelope_path is not None:
            return Path(self._envelope_path)
        root = os.environ.get(handoff.INTAKE_DIR_ENV)
        return Path(root) / handoff.ENVELOPE_NAME if root else None

    def _load(self) -> Tuple[List[dict], Optional[str], Optional[str]]:
        key = self._key if self._key is not None else os.environ.get(handoff.KEY_ENV, "")
        now = self._clock() if callable(self._clock) else self._clock
        return handoff.load_envelope(self.envelope_path(), key, now=now)

    # ── contract (offline: there is nothing to fetch) ────────────────────────

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        records, status, detail = self._load()
        if status is not None:
            return DiscoveryResult(self.slug, status, [], error_detail=detail)
        if not records:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS, [])
        return DiscoveryResult(self.slug, st.OK, [
            CandidateReference(url=r["url"], source_slug=self.slug,
                               discovered_via=handoff.ENVELOPE_NAME,
                               hint_published_date=r["published_date"])
            for r in records])

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        return CaptureResult(reference, st.FETCH_FAILURE, reference.url,
                             error_detail="gt_handoff_has_no_live_fetch")

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        return ExtractionResult(self.slug, st.EXTRACTION_FAILURE, [],
                                error_detail="gt_handoff_has_no_live_fetch")

    def document(self, record: dict) -> ExtractedDocument:
        raw = handoff.public_raw(record)
        return ExtractedDocument(
            url=raw["url"], source_slug=raw["source_slug"],
            title_original=raw["title_original"],
            text_original=raw["text_original"],
            published_date=raw["published_date"],
            language_tag=getattr(self.source, "language_tag", None),
            extra={k: v for k, v in raw.items()
                   if k not in ("url", "source_slug", "title_original",
                                "text_original", "published_date")},
            raw=raw)

    # ── whole-source collection ──────────────────────────────────────────────

    def collect(self, window: CollectionWindow
                ) -> Tuple[SourceRunResult, List[ExtractedDocument]]:
        result = SourceRunResult(source_slug=self.slug, status=st.OK,
                                 desk_id=getattr(self.source, "desk_id", None),
                                 started_at=_now())
        if not getattr(self.source, "enabled", True):
            result.status = st.SKIPPED_DISABLED
            result.completed_at = _now()
            return result, []
        records, status, detail = self._load()
        if status is not None:
            # Fixed codes and validated identifiers only: error_detail is
            # persisted and rendered publicly.
            result.status, result.error_detail = status, detail
            result.completed_at = _now()
            return result, []
        if not records:
            # An authenticated, attested and current collection that observed
            # nothing in its window.
            result.status = st.OK_NO_PUBLICATIONS
            result.completed_at = _now()
            return result, []

        documents = [self.document(r) for r in records]
        result.references_discovered = result.fetched = len(records)
        result.extracted = len(documents)
        # A body held on purpose was read, not lost (as adapters/legacy.py).
        held = [d for d in documents if d.extra.get("text_held")]
        unusable = [d for d in documents
                    if not d.has_usable_text and not d.extra.get("text_held")]
        result.text_unavailable = len(unusable)
        notes = []
        if len(unusable) < len(documents):
            result.status = st.OK
            if held:
                notes.append(
                    "%d of %d parsed page(s) had their body held by the "
                    "parser (%s); titles, URLs and dates were kept"
                    % (len(held), len(documents), ", ".join(sorted(
                        {str(d.extra["text_held"]) for d in held}))))
            if unusable:
                notes.append(
                    "%d of %d parsed page(s) carried no usable text; their "
                    "titles, URLs and dates were kept"
                    % (len(unusable), len(documents)))
        else:
            result.status = st.EXTRACTION_FAILURE
            notes.append("%d page(s) parsed, none carried usable text — check "
                         "for source markup drift" % len(documents))
        if notes:
            result.error_detail = "; ".join(notes)
        result.completed_at = _now()
        return result, documents
