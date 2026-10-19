#!/usr/bin/env python3
"""Serial, bounded ministry batch; publication is the workflow's success step."""
import argparse
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.shadow_schedule import SOURCE_EXPLICIT, parse_run_attempt, resolve_target_date
from scripts.shadow_collect_vietnam import assert_isolated, host_gate
from scripts.shadow_collect_vietnam_ministry import collect, load_source
from scripts.review_vietnam_ministry_state import inventory, review, require
from scripts.review_vietnam_shadow_state import check_tree
from scripts.review_shadow_state import git, ReviewError

SOURCES = ("vn_mps_foreign_affairs_vi", "vn_moit_energy_vi", "vn_moit_foundational_industry_vi")


def preserved(state):
    return {n: h for n, h in inventory(state).items()
            if n == "clock.json" or n.startswith(("ledger/", "captures/"))}


def prepare(root, gate_dir):
    """Refuse foreign/malformed state, then seed all prior host completions."""
    before = {}
    for slug in SOURCES:
        repo, state = root / slug, root / slug / "state"
        assert_isolated(repo)
        require(not repo.is_symlink(), "symlink state repository")
        require(git(["branch", "--show-current"], repo).stdout.strip() == load_source(slug).state_branch,
                "wrong state branch")
        if git(["rev-parse", "--verify", "HEAD"], repo, check=False).returncode == 0:
            require(git(["ls-tree", "--name-only", "HEAD"], repo).stdout.strip() == "state",
                    "state branch contains unrelated files")
            require(not git(["status", "--porcelain"], repo).stdout.strip(), "dirty state checkout")
            check_tree(list(inventory(state)))
            review(state, slug)
        else:
            require(not state.exists(), "bootstrap cannot import rehearsal state")
        before[slug] = preserved(state)
        host_gate(state, gate_dir)
    return before


def resolve_targets(event_name, run_attempt, cron_utc, mps_target=None, moit_target=None,
                    started=None):
    """Resolve one scheduled slot or an explicit manual recovery without guessing."""
    parse_run_attempt(run_attempt)
    explicit = mps_target is not None or moit_target is not None
    if explicit:
        require(mps_target is not None and moit_target is not None,
                "manual recovery requires both ministry target dates")
        require(event_name == "workflow_dispatch",
                "explicit ministry target dates are manual recovery only")
        return mps_target, moit_target, SOURCE_EXPLICIT
    require(event_name == "schedule",
            "manual dispatch requires an explicit target date")
    target, target_source = resolve_target_date(
        started or datetime.now(timezone.utc), event_name=event_name,
        cron_utc=cron_utc, run_attempt=run_attempt)
    return target, target, target_source


def run_batch(root, gate_dir, mps_target, moit_target, lookback, cap, run_id, commit,
              collector=collect, target_source=SOURCE_EXPLICIT, successful_sources=None):
    require(lookback in (0, 6) and cap in (2, 40), "unapproved remote budget")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "full collector SHA required")
    before = prepare(root, gate_dir)
    failures = []
    for slug in SOURCES:
        state = root / slug / "state"
        target = mps_target if slug == SOURCES[0] else moit_target
        try:
            entry = collector(state, slug, target, lookback, cap, run_id, commit,
                              gate_dir=gate_dir, target_source=target_source)
            require(entry["health"] == "ok", "collection failed")
        except (ValueError, OSError, ReviewError):
            # Keep the failure and all captures in the attempt artifact. A
            # failed MPS feed must not starve the independent MOIT families.
            failures.append(slug)
            continue
        # Integrity corruption remains a hard batch stop; it is different from
        # a bounded publisher failure and must never authorize a state push.
        after = preserved(state)
        require(all(after.get(n) == h for n, h in before[slug].items()), "historical evidence changed")
        check_tree(list(inventory(state)))
        review(state, slug)
        if successful_sources is not None:
            successful_sources.append(slug)
    require(not failures, "batch has failed sources: " + ", ".join(failures))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--gate-dir", type=Path, required=True)
    ap.add_argument("--mps-target", type=date.fromisoformat)
    ap.add_argument("--moit-target", type=date.fromisoformat)
    ap.add_argument("--lookback", type=int, choices=(0, 6), required=True)
    ap.add_argument("--cap", type=int, choices=(2, 40), required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--event-name", choices=("schedule", "workflow_dispatch"), required=True)
    ap.add_argument("--run-attempt", required=True)
    ap.add_argument("--cron-utc", required=True)
    ap.add_argument("--publication-list", type=Path,
                    help="new external file listing only independently verified successful sources")
    args = ap.parse_args(argv)
    successful_sources = []
    publication_list = None
    try:
        if args.publication_list:
            publication_list = args.publication_list
            require(not publication_list.exists() and not publication_list.is_symlink(),
                    "publication list must be new")
            require(REPO not in publication_list.resolve().parents
                    and args.root.resolve() not in publication_list.resolve().parents,
                    "publication list must be outside collector and source checkouts")
        mps_target, moit_target, target_source = resolve_targets(
            args.event_name, args.run_attempt, args.cron_utc,
            args.mps_target, args.moit_target)
        return run_batch(args.root, args.gate_dir, mps_target, moit_target,
                         args.lookback, args.cap, args.run_id, args.commit,
                         target_source=target_source, successful_sources=successful_sources)
    except (ValueError, OSError, ReviewError) as exc:
        print("remote batch refused: %s" % exc, file=sys.stderr)
        return 1
    finally:
        if publication_list is not None and successful_sources:
            with publication_list.open("x", encoding="utf-8") as stream:
                stream.write("".join(slug + "\n" for slug in successful_sources))


if __name__ == "__main__":
    raise SystemExit(main())
