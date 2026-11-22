"""Interim, disabled-by-default source-use hold for three China Desk publishers.

When (and only when) ``IPR_CHINA_SOURCE_USE_HOLD`` is exactly ``"true"``, the
three host sources below are held *as sources*: no publisher request, no new
row in the public database, and no title or body sent to an external model.
With the variable unset, empty or malformed every function here is inert and
current behaviour is unchanged, so merging this module activates nothing.

The hold is keyed on the host source slug only. It never inspects a byline:
MOD China pages can carry a PLA Daily byline and the two institutions stay
distinguishable. Records already stored stay exactly as they are; the hold
writes no processing state, flips no ``sources.enabled`` flag and removes no
public output. Retrospective treatment of existing records is a separate owner
decision. Whether any metadata-only discovery would be permitted is also left
to that decision, so the hold covers collection as a whole.

This is an engineering switch, not a source-use decision. It adopts no
publisher grant or restriction. The pattern is the one used for MINDEF
(``core.mindef_permissions``); the status reported is the existing
``SKIPPED_DISABLED``, which is non-failure and non-collecting.
"""
import os

HOLD_ENV = "IPR_CHINA_SOURCE_USE_HOLD"

HELD_SOURCE_SLUGS = frozenset({"global_times_mil", "mod_china", "pla_daily"})

#: Stable prefix of the ``error_detail`` recorded for a held source, so a hold
#: is distinguishable from a quiet source, an access refusal or an outage.
HOLD_DETAIL_PREFIX = "source-use hold"


class SourceUseHold(RuntimeError):
    """A write for a held source was attempted while the hold is enabled."""


def hold_enabled() -> bool:
    """Read at call time, exact ``"true"``; anything else is off."""
    return os.environ.get(HOLD_ENV) == "true"


def is_held_source(source_slug) -> bool:
    return hold_enabled() and source_slug in HELD_SOURCE_SLUGS


def is_held_row(row) -> bool:
    """``is_held_source`` for a stored-article row (``sqlite3.Row`` or dict).

    Fails closed while the hold is enabled: a row that carries no usable
    ``source_slug`` (key absent, ``None`` or empty) has unknown provenance and
    is treated as held, so it can never bypass the hold on the way to a model.
    ``storage.db.get_articles_for_desks`` always selects ``source_slug`` from
    the joined source, so real rows are unaffected. Disabled, nothing is held.
    """
    if not hold_enabled():
        return False
    try:
        slug = row["source_slug"]
    except (KeyError, IndexError, TypeError):
        return True
    if not isinstance(slug, str) or not slug:
        return True
    return slug in HELD_SOURCE_SLUGS


def hold_detail(source_slug) -> str:
    return "%s: %s; no collection, storage or model processing" % (
        HOLD_DETAIL_PREFIX, source_slug)


def held_article_ids(get_ids_for_source) -> set:
    """Ids of already-stored records from held sources; empty unless enabled.

    ``get_ids_for_source`` is ``storage.db.get_article_ids_for_source``. It is
    injected and not called when the hold is off, so the disabled path performs
    no extra query.
    """
    if not hold_enabled():
        return set()
    ids = set()
    for slug in sorted(HELD_SOURCE_SLUGS):
        ids |= get_ids_for_source(slug)
    return ids


def assert_not_held(source_slug) -> None:
    """Fail loudly. Returning ``None`` would read as a duplicate URL."""
    if is_held_source(source_slug):
        raise SourceUseHold(hold_detail(source_slug))
