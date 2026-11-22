"""The Korea public-release rule, reproduced independently of the renderer.

Tests that count the public corpus straight from SQL use this instead of
calling generate_preview, so a renderer change cannot agree with itself.

A Korea row is public when its ledger row is admitted and either finished
processing (processed / not_relevant) or is unfinished (pending / retryable /
qa_held / paused) but backed by a released original with the same identity
and the same original-text SHA-256, and is not an excluded identity.
"""
import json
from pathlib import Path

RELEASE_INDEX = (Path(__file__).resolve().parents[1]
                 / "research" / "korea_published_original_texts.json")
UNFINISHED = ("pending", "retryable", "qa_held", "paused")


def original_only_ids(con):
    """Article ids shown only for their released original (English held)."""
    from core.korea_corpus_bridge import excluded_identities
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                       "AND name='korea_corpus_admissions'").fetchone():
        return []
    released = {r["source_identity"]: r["original_text_sha256"] for r in
                json.loads(RELEASE_INDEX.read_text(encoding="utf-8"))["records"]}
    excluded = set(excluded_identities())
    return sorted(
        aid for aid, ident, digest in con.execute(
            "SELECT article_id, source_identity, original_text_sha256 "
            "FROM korea_corpus_admissions WHERE state = 'admitted' "
            "AND article_id IS NOT NULL AND processing_state IN (%s)"
            % ",".join("'%s'" % s for s in UNFINISHED))
        if digest and released.get(ident) == digest and ident not in excluded)


def public_filter(con, alias="a", source="s"):
    """SQL predicate over ``articles {alias} JOIN sources {source}``."""
    extra = original_only_ids(con)
    return (
        "((COALESCE({s}.desk_id, '') != 'korea' "
        "AND {s}.slug != 'kr_policy_mnd_releases') "
        "OR EXISTS (SELECT 1 FROM korea_corpus_admissions k "
        "WHERE k.article_id = {a}.id AND k.state = 'admitted' "
        "AND k.processing_state IN ('processed', 'not_relevant'))"
        "{more})").format(
            a=alias, s=source,
            more=(" OR %s.id IN (%s)" % (alias, ",".join(map(str, extra)))
                  if extra else ""))
