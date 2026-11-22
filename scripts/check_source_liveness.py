#!/usr/bin/env python3
"""Report sources that have gone quiet.

Background (2026-08-09). MOD China (国防部) last produced an article on
2026-07-10 and nothing noticed for four weeks: PLA Daily supplies ~87% of all
articles, so a dead secondary source does not dent the daily totals and the
pipeline stays green. This check makes that visible.

A source is UNHEALTHY when it is expected to collect and its most recent
article is older than its own silence threshold. Sources that have never
produced anything are unhealthy immediately unless they are not expected to
collect at all.

Where the expectations come from (2026-09-20)
---------------------------------------------
Nowhere in this file. Both the "this source is allowed to be silent" list and
the per-source thresholds used to be hand-maintained dictionaries here, and
both drifted: Xinhua Military was rewritten into a working adapter on
2026-09-16 and delivered four new articles on 2026-09-20, while this script
still carried the stub's obituary and reported it INERT. An INERT source is
exempt from every recency threshold, so Xinhua could have died the next day and
this gate would have said nothing.

A second copy of a fact is a second chance to be wrong about it. Both
dictionaries are gone. Expectations are now derived:

  * whether a source can collect at all — from the adapter's own offline
    `healthcheck()`, which reports NOT_IMPLEMENTED for a class declaring
    `IS_STUB` and SKIPPED_DISABLED for one the desk manifest disables. A
    source becomes exempt by being a declared stub, not by being named here.
  * how long it may stay quiet — from `silence_threshold_days` in the desk
    manifest, the same field `core.collection.health.silence_verdict` reads.

A source whose adapter will not even import is UNHEALTHY, not INERT. That is
the failure this gate exists for, and it must never be reachable by accident.

Governed sources are judged by their recorded runs (2026-11-21)
---------------------------------------------------------------
A manual source stores what it admits in its own family tables, not in
`articles`, so judging it by article count left every governed family INERT
("nothing admitted yet") however many records it held and however long its
admission had been failing. INERT is exempt from every threshold. The
pipeline already records one `source_run_results` row per governed source per
Daily; that is now the signal. A run is healthy when its stored `is_failure`
is 0 AND its status is a collection success (`st.SUCCESS_STATUSES`, which
includes `ok_all_filtered` for an admission that reached its source but held
what it found). `skipped_disabled` and `not_implemented` are stored with
`is_failure` 0 yet collected nothing, so they never count as a healthy run.
The run date is `scrape_runs.started_at`; governed rows leave their own
`started_at` NULL.

A manual source with no articles and no run that attempted collection (no
rows at all, or only skipped/not-implemented rows awaiting activation) stays
INERT; one with articles but no such run is judged by its articles alone.
Otherwise it is UNHEALTHY when its last healthy run is older than its
threshold. When it also holds articles, the article-recency verdict is still
applied and the worse of the two wins: the signal can turn an INERT source
into a judged one, or a HEALTHY one UNHEALTHY when its admission has stopped,
but it never turns an UNHEALTHY verdict HEALTHY. A latest failed run is shown
in the detail even when the state is HEALTHY. A run whose Daily has no
parseable date is ignored. A database without the run tables is judged
exactly as before.

Exit codes:
    0  all sources healthy (or only inert ones are quiet)
    1  at least one source is unhealthy

Usage:
    .venv/bin/python scripts/check_source_liveness.py
    .venv/bin/python scripts/check_source_liveness.py --max-silent-days 14
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                       # noqa: E402
from core.registry import get_registry                         # noqa: E402
from scripts.reconcile_db import read_only                     # noqa: E402

DEFAULT_DB = REPO_ROOT / "pla_watch.db"

#: Configuration states in which a source is not expected to produce anything,
#: and its silence is therefore not a defect. Both are declarations made
#: elsewhere and merely read here: `IS_STUB` on the adapter class, `enabled`
#: in the desk manifest. Neither is a failure, and neither is a judgement this
#: file is entitled to make on its own.
INERT_STATUSES = {
    st.NOT_IMPLEMENTED: "declared stub — no working collection path",
    st.SKIPPED_DISABLED: "disabled in its desk manifest",
}


@dataclass(frozen=True)
class Expectation:
    """What configuration says this source should be doing.

    `threshold` of None means the manifest states no cadence for this source
    and the run-wide `--max-silent-days` applies.
    """

    inert: bool = False
    broken: bool = False
    reason: Optional[str] = None
    threshold: Optional[int] = None
    #: Never fetched: records arrive only through a governed admission step
    #: (pipeline.run_governed_manual_sources). Until that step has admitted
    #: anything there is no collection to be silent; after it has, the source
    #: is judged by its threshold like any other.
    manual: bool = False
    #: Set when the shared Daily policy has this governed source's recurring
    #: release switched off. Its silence is then a recorded owner decision, not
    #: a fault: it is reported as PAUSED on every run and never fails the gate.
    #: Turning the switch back on restores the ordinary threshold at once.
    paused: Optional[str] = None
    #: A shared-Daily family (core.daily_sources.SOURCES) admits into its own
    #: family tables and never writes `articles`. Any article rows it has are a
    #: closed pre-cutover corpus (MINDEF: public scraper, 2026-08-19..10-29), so
    #: their age says nothing about collection; it is judged on governed runs.
    articles_closed: bool = False


def _daily_families() -> frozenset:
    try:
        from core.daily_sources import SOURCES
    except Exception:
        return frozenset()
    return frozenset(SOURCES)


@dataclass(frozen=True)
class GovernedRuns:
    """What `source_run_results` records for one governed source.

    `collected` is True once any run attempted collection (a success or a
    failure); skipped and not-implemented rows alone leave it False.
    """

    last_healthy: Optional[str] = None
    collected: bool = False
    latest_date: Optional[str] = None
    latest_status: Optional[str] = None
    latest_failure: bool = False
    latest_detail: Optional[str] = None


#: Run tables present, nothing recorded for this slug.
NO_GOVERNED_RUNS = GovernedRuns()

#: Longest error_detail quoted in a report line.
DETAIL_LIMIT = 160


#: The expectation for a slug no desk manifest declares. Deliberately not
#: inert: a source in the database that configuration has forgotten is still
#: expected to produce, and the generic threshold applies. Exemption is
#: something a manifest grants, never something absence produces.
UNDECLARED = Expectation()


def paused_by_policy() -> Dict[str, str]:
    """Governed families that no scheduled run may release: the Daily policy has
    recurring release off, or the attended-pilot gate still holds the family.

    Read from the policy file and the gate, never listed here. An unreadable policy pauses
    nothing, so a broken file cannot hide a silent source.
    """
    try:
        from core.daily_sources import attended_only
        from processing.daily_intake import POLICY_PATH, load_policy
        sources = load_policy()["sources"]
    except Exception:
        return {}
    paused = {}
    for family, policy in sources.items():
        if not policy["unattended_release"]:
            paused[family] = "recurring release switched off in %s" % Path(POLICY_PATH).name
        elif attended_only(family):
            # Switches on, but no scheduled run may handle the family until the
            # attended-pilot gate is removed (core/daily_sources.ATTENDED_PILOT_ENV).
            paused[family] = "attended-pilot gate: no scheduled runs"
    return paused


def expectations(registry=None, paused=None) -> Dict[str, Expectation]:
    """Derive per-source expectations from adapters and desk manifests.

    Offline: `healthcheck()` is specified to perform no network I/O, which is
    what lets this run inside the test suite and on a fresh clone.
    """
    registry = registry or get_registry()
    paused = paused_by_policy() if paused is None else paused
    daily = _daily_families()
    out: Dict[str, Expectation] = {}
    for result in registry.healthcheck_all():
        source = registry.get_source(result.source_slug)
        threshold = getattr(source, "silence_threshold_days", None)
        if result.status in INERT_STATUSES:
            out[result.source_slug] = Expectation(
                inert=True,
                reason=result.detail or INERT_STATUSES[result.status],
                threshold=threshold,
            )
        elif st.is_failure(result.status):
            # An adapter that cannot be imported or resolved. Silence from it
            # is guaranteed and meaningless, so recency would report HEALTHY
            # for as long as the corpus stayed warm.
            out[result.source_slug] = Expectation(
                broken=True,
                reason="adapter unusable (%s): %s"
                % (result.status, result.detail or "no detail"),
                threshold=threshold,
            )
        else:
            out[result.source_slug] = Expectation(
                threshold=threshold,
                manual=getattr(source, "access_method", None) == "manual",
                paused=(paused.get(result.source_slug)
                        if getattr(source, "access_method", None) == "manual" else None),
                articles_closed=(getattr(source, "access_method", None) == "manual"
                                 and result.source_slug in daily))
    return out


def rows(db_path: Path, today: date):
    # Reads a scratch copy, not the tracked file. A direct `mode=ro` URI on a
    # sidecar-less WAL database is not portable: depending on SQLite, the VFS
    # and the filesystem it either fails to open or creates the sidecars beside
    # the input (DECISION_LOG 2026-08-17). Where it failed, running this on a
    # fresh clone died with an unhandled OperationalError — the health gate is
    # the last step of the daily run, and it survived there only because an
    # earlier step had already created the sidecars.
    with read_only(db_path) as conn:
        return conn.execute(
            """
            SELECT s.slug,
                   s.display_name,
                   COUNT(a.id)             AS total,
                   MAX(date(a.scraped_at)) AS last_seen
              FROM sources s
              LEFT JOIN articles a ON a.source_id = s.id
             WHERE s.is_active = 1
             GROUP BY s.id
             ORDER BY total DESC
            """
        ).fetchall()


def governed_runs(db_path: Path) -> Optional[Dict[str, GovernedRuns]]:
    """Per-slug run history, or None when the database predates run tables.

    Read through the same scratch copy as `rows()`. Runs are dated and
    ordered by their Daily (`scrape_runs.started_at`, then id).
    """
    with read_only(db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not {"source_run_results", "scrape_runs"} <= tables:
            return None
        try:
            found = conn.execute(
                """
                SELECT r.source_slug, date(s.started_at), r.status,
                       r.is_failure, r.error_detail
                  FROM source_run_results r
                  JOIN scrape_runs s ON s.id = r.scrape_run_id
                 WHERE date(s.started_at) IS NOT NULL
                 ORDER BY r.source_slug, s.started_at, s.id, r.id
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return None
    out: Dict[str, GovernedRuns] = {}
    for slug, day, status, is_failure, detail in found:
        if not day:                     # an undated run cannot be judged
            continue
        prior = out.get(slug, NO_GOVERNED_RUNS)
        succeeded = not is_failure and status in st.SUCCESS_STATUSES
        out[slug] = GovernedRuns(
            last_healthy=day if succeeded else prior.last_healthy,
            collected=prior.collected or bool(is_failure) or succeeded,
            latest_date=day,
            latest_status=status,
            latest_failure=bool(is_failure),
            latest_detail=detail,
        )
    return out


def _quote(detail: Optional[str]) -> str:
    text = " ".join((detail or "").split())
    if len(text) > DETAIL_LIMIT:
        text = text[:DETAIL_LIMIT - 1] + "…"
    return text


def _latest(runs: GovernedRuns) -> str:
    out = "latest %s %s" % (runs.latest_date, runs.latest_status)
    # Quoted on success too: a held admission (e.g. "held: ...; signed_held: N")
    # is reported here without changing the verdict.
    if runs.latest_detail:
        out += ": " + _quote(runs.latest_detail)
    return out


def _classify_governed(total, last_seen, today, max_silent, expectation, runs):
    """A manual source with run evidence: the worse of runs and articles."""
    has_articles = bool(total) and last_seen is not None
    if expectation.articles_closed and runs.collected:
        has_articles = False
    if not has_articles and not runs.collected:
        detail = "manual source — nothing admitted yet; no governed run recorded"
        if runs.latest_status:
            detail += " (%s)" % _latest(runs)
        return "INERT", None, detail

    threshold = expectation.threshold or max_silent
    verdicts = []                       # (unhealthy, days, detail)
    if has_articles:
        days = (today - datetime.strptime(last_seen, "%Y-%m-%d").date()).days
        verdicts.append((days > threshold, days,
                         f"last article {last_seen} ({days}d ago, threshold {threshold}d)"))
    if runs.collected:
        if runs.last_healthy:
            days = (today - datetime.strptime(runs.last_healthy, "%Y-%m-%d").date()).days
            verdicts.append((days > threshold, days,
                             "governed: last healthy run %s (%dd ago, threshold %dd); %s"
                             % (runs.last_healthy, days, threshold, _latest(runs))))
        else:
            verdicts.append((True, None, "governed: no healthy run recorded; %s"
                             % _latest(runs)))

    detail = "; ".join(v[2] for v in verdicts)
    failing = [v for v in verdicts if v[0]]
    deciding = failing or verdicts
    days = max((v[1] for v in deciding if v[1] is not None), default=None)
    if failing:
        if expectation.paused:
            return "PAUSED", days, "%s; %s" % (detail, expectation.paused)
        return "UNHEALTHY", days, detail
    return "HEALTHY", days, detail


def classify(slug: str, total: int, last_seen: str | None,
             today: date, max_silent: int,
             expectation: Expectation = UNDECLARED,
             runs: Optional[GovernedRuns] = None):
    """Return (state, days_silent, detail).

    `runs` is consulted only for a manual source; None (no run tables, or no
    caller evidence) keeps the article-only judgement.
    """
    if expectation.broken:
        return "UNHEALTHY", None, expectation.reason

    if expectation.inert:
        return "INERT", None, expectation.reason

    if expectation.manual and runs is not None:
        return _classify_governed(total, last_seen, today, max_silent,
                                  expectation, runs)

    if total == 0 or last_seen is None:
        if expectation.manual:
            return "INERT", None, "manual source — nothing admitted yet"
        return "UNHEALTHY", None, "no articles have ever been collected"

    threshold = expectation.threshold or max_silent
    days = (today - datetime.strptime(last_seen, "%Y-%m-%d").date()).days
    detail = f"last article {last_seen} ({days}d ago, threshold {threshold}d)"
    if days > threshold:
        if expectation.paused:
            return "PAUSED", days, "%s; %s" % (detail, expectation.paused)
        return "UNHEALTHY", days, detail
    return "HEALTHY", days, detail


def emit_github(unhealthy: list[tuple[str, str]], lines: list[str],
                paused: list[tuple[str, str]] = ()) -> None:
    """Annotate the Actions run and write a step summary, when running in CI."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return

    for name, detail in unhealthy:
        print(f"::warning title=Source silent::{name}: {detail}")
    for name, detail in paused:
        print(f"::notice title=Source paused by owner decision::{name}: {detail}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("### Source liveness\n\n```\n")
            fh.write("\n".join(lines))
            fh.write("\n```\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--max-silent-days", type=int, default=7)
    parser.add_argument(
        "--today", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(), help="override today's date (testing)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        sys.exit(f"ERROR: database not found: {args.db}")

    expected = expectations()
    runs = governed_runs(args.db)
    unhealthy: list[tuple[str, str]] = []
    paused: list[tuple[str, str]] = []
    lines: list[str] = []

    for slug, name, total, last_seen in rows(args.db, args.today):
        state, _days, detail = classify(
            slug, total, last_seen, args.today, args.max_silent_days,
            expected.get(slug, UNDECLARED),
            runs=None if runs is None else runs.get(slug, NO_GOVERNED_RUNS),
        )
        lines.append(f"{state:<10} {name:<28} {total:>5} article(s)  {detail}")
        if state == "UNHEALTHY":
            unhealthy.append((name, detail))
        elif state == "PAUSED":
            paused.append((name, detail))

    print(f"Source liveness — threshold {args.max_silent_days}d, as of {args.today}")
    print("-" * 78)
    for line in lines:
        print(line)
    print("-" * 78)

    emit_github(unhealthy, lines, paused)

    if unhealthy:
        print(f"\n{len(unhealthy)} source(s) need attention.")
        return 1

    if paused:
        print(f"\n{len(paused)} source(s) paused by owner decision; not a fault.")
    print("\nAll non-inert sources are producing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
