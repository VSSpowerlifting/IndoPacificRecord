"""Existing Japan collector -> shared Daily metadata admission; no source fetch.

The repository policy is authoritative. A CLI flag cannot grant permission.
Failures roll back SQLite; Daily continues serving its already released rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path

from core.japan_mod_official_links import (
    ROOT, SOURCE_REF, SOURCE_REPOSITORY, admit, candidates, require_authorization,
)
from core.regional_official_link_release import RegionalLinkHold, need


def github_run(run_id):
    return json.loads(subprocess.check_output([
        "gh", "api", "repos/%s/actions/runs/%s" % (SOURCE_REPOSITORY, run_id)],
        stderr=subprocess.DEVNULL))


def run(repo, commit, db, *, fetch_run=github_run):
    require_authorization()  # Before fetching originals, API calls or DB writes.
    need(Path(db).resolve() != (ROOT / "pla_watch.db").resolve()
         or os.environ.get("JAPAN_MOD_OFFICIAL_LINKS_ENABLED") == "true",
         "japan_production_intake_activation_missing")
    cache = {}
    def fetch(number):
        if number not in cache:
            cache[number] = fetch_run(number)
        return cache[number]
    rows, evidence = candidates(repo, commit, fetch_run=fetch)
    with sqlite3.connect(str(db)) as con:
        con.execute("BEGIN IMMEDIATE")
        result = admit(con, rows, evidence)
        if con.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise RegionalLinkHold("japan_production_sqlite_invalid")
    return dict(result, **evidence)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-repo", default=str(ROOT))
    p.add_argument("--source-commit", default="refs/remotes/origin/" + SOURCE_REF)
    p.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    args = p.parse_args(argv)
    try:
        require_authorization()
        commit = subprocess.check_output(["git", "-C", args.source_repo,
            "rev-parse", "--verify", args.source_commit + "^{commit}"], text=True).strip()
        print(json.dumps(run(args.source_repo, commit, args.db), sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, subprocess.CalledProcessError):
        # Fixed message: never echo publisher-controlled text or credentials.
        print("HOLD: Japan MOD metadata admission unavailable; see source policy and run evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
