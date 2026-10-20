"""Run the Vietnam Desk Daily step: authenticated captures -> shared corpus.

One invocation processes each named ministry family at its private state
commit through core.vietnam_corpus_bridge.run_family, on a sibling copy of the
database that replaces the original only after every family finishes and the
copy passes integrity checks. Production requires --release.

A family with no --decision runs under the standing source-use policy: every
record is held for rights before any model call, so the run constructs no
model client, spends nothing and writes no article. A decision file is an
owner-sealed source-use decision, verified with VIETNAM_SOURCE_USE_REVIEW_KEY;
this script never creates one. Model calls need ANTHROPIC_API_KEY and happen
only for records whose decision grants model transmission and public analysis
on a promoted desk.

No collection, signing, Git push, schedule or deployment.

    .venv/bin/python scripts/run_vietnam_daily_bridge.py \\
        --database /tmp/scratch/pla_watch.db --expected-db-sha256 <sha> \\
        --state-repo /path/to/private-state-clone \\
        --family vn_mps_foreign_affairs_vi=<commit> \\
        --ledger-dir /path/outside/repo --run-id manual-2026-10-19
"""
import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core import vietnam_corpus_bridge as bridge
from core import vietnam_source_use as source_use
from core.collection.vietnam_sources import SOURCES
from migrations.runner import applied_versions, apply_all, discover
from scripts.attest_vietnam_run_state import GithubRead
from scripts.publish_shadow_review import strict_loads

ROOT = Path(__file__).resolve().parents[1]


class _NoModel:
    """Stands in for the Analyzer when no family may reach a model."""

    def analyze_record(self, *_args, **_kwargs):
        raise bridge.BridgeError("vietnam_model_call_without_decision")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _pair(text):
    slug, sep, value = text.partition("=")
    if not sep or slug not in SOURCES or not value:
        raise argparse.ArgumentTypeError("expected SOURCE_FAMILY=VALUE for a Vietnam family")
    return slug, value


def _policies(decisions, families, as_of):
    secret = os.environ.get("VIETNAM_SOURCE_USE_REVIEW_KEY", "").encode()
    out = {}
    for family in families:
        path = decisions.get(family)
        if path is None:
            out[family] = source_use.standing(family)
            continue
        path = Path(path)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 131072:
            raise bridge.BridgeError("vietnam_source_use_decision_unavailable")
        sealed = strict_loads(path.read_text(), "Vietnam source-use decision")
        out[family] = source_use.verify_decision(sealed, secret, family, as_of=as_of)
    return out


def run(db, state_repo, commits, policies, *, ledger_dir, run_id, expected_db_sha256,
        api, analyzer, as_of_utc):
    db = Path(db)
    if _sha(db) != expected_db_sha256:
        raise bridge.BridgeError("database_preimage_changed")
    if any(Path(str(db) + s).exists() for s in ("-wal", "-shm", "-journal")):
        raise bridge.BridgeError("database_has_active_sidecars")
    fd, name = tempfile.mkstemp(prefix=".vietnam-daily-", dir=str(db.parent))
    os.close(fd)
    scratch = Path(name)
    reports = []
    try:
        scratch.write_bytes(db.read_bytes())
        with closing(sqlite3.connect(str(scratch), isolation_level=None)) as conn:
            if conn.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise bridge.BridgeError("vietnam_daily_requires_single_file_journal")
            conn.execute("PRAGMA foreign_keys=ON")
            pending = {m.version for m in discover()} - set(applied_versions(conn))
            if not pending <= {"0015"}:
                raise bridge.BridgeError("unrelated_pending_migrations")
            apply_all(conn, sync_config=False)
            for family, commit in commits:
                reports.append(bridge.run_family(
                    conn, state_repo, commit, family, api=api, as_of_utc=as_of_utc,
                    source_use=policies[family], analyzer=analyzer,
                    ledger_path=Path(ledger_dir) / ("%s.json" % family), run_id=run_id))
            if (conn.execute("PRAGMA integrity_check").fetchone() != ("ok",)
                    or conn.execute("PRAGMA foreign_key_check").fetchall()):
                raise bridge.BridgeError("vietnam_daily_integrity_failed")
        if _sha(db) != expected_db_sha256:
            raise bridge.BridgeError("database_changed_concurrently")
        os.chmod(scratch, db.stat().st_mode & 0o777)
        os.replace(str(scratch), str(db))
        return reports
    finally:
        scratch.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--expected-db-sha256", required=True)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--family", type=_pair, action="append", required=True,
                   metavar="SOURCE_FAMILY=COMMIT")
    p.add_argument("--decision", type=_pair, action="append", default=[],
                   metavar="SOURCE_FAMILY=SEALED_DECISION_JSON")
    p.add_argument("--ledger-dir", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--release", action="store_true")
    args = p.parse_args(argv)
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if args.database.is_symlink():
            raise bridge.BridgeError("symlink_database_refused")
        db = args.database.resolve(strict=True)
        if args.release:
            if db != ROOT / "pla_watch.db":
                raise bridge.BridgeError("release_requires_canonical_database")
        elif any((parent / ".git").exists() for parent in db.parents):
            raise bridge.BridgeError("rehearsal_requires_external_database")
        families = [slug for slug, _ in args.family]
        if len(set(families)) != len(families):
            raise bridge.BridgeError("vietnam_family_repeated")
        policies = _policies(dict(args.decision), families, as_of[:10])
        needs_model = any(pol.allows("external_model_transmission") for pol in policies.values())
        if needs_model:
            from analysis.analyzer import Analyzer
            analyzer = Analyzer()
        else:
            analyzer = _NoModel()
        reports = run(db, args.state_repo, args.family, policies,
                      ledger_dir=args.ledger_dir, run_id=args.run_id,
                      expected_db_sha256=args.expected_db_sha256,
                      api=GithubRead(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")),
                      analyzer=analyzer, as_of_utc=as_of)
        print(json.dumps({"status": "OK", "release": args.release, "runs": reports},
                         sort_keys=True, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "HOLD", "release": args.release,
                          "reason": str(exc) or type(exc).__name__, "database_replaced": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
