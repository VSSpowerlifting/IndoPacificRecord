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

After the private-first cutover (#831) every family runs with
--private-custody SOURCE_FAMILY=PUBLIC_FROZEN_TIP (one per family; a bare tip
when one family is named) and --private-state-repo, a clone of the private
evidence repository: each commit must be on that family's archive ref and is
authenticated with VIETNAM_PRIVATE_PROVENANCE_TOKEN (read-only). Because it
reads private originals from that clone, a --private-custody run belongs on
the private runner, never a public job; the corpus, ledgers and report receive
only permitted fields and provenance. Approved records reach the public
corpus only through core.vietnam_daily_handoff.

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
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from core import vietnam_corpus_bridge as bridge
from core import vietnam_official_link_admission as vn
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


def _tips(values, families):
    """{family: public frozen tip}; a bare tip only when one family is named."""
    tips = {}
    for value in values:
        family, sep, tip = value.rpartition("=")
        if not sep:
            if len(families) != 1:
                raise bridge.BridgeError("vietnam_private_custody_needs_family")
            family = families[0]
        if family not in families or family in tips or not re.fullmatch(r"[0-9a-f]{40}", tip):
            raise bridge.BridgeError("vietnam_private_custody_incomplete")
        tips[family] = tip
    return tips


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
        api, analyzer, as_of_utc, custody=None, private_state_repo=None):
    db = Path(db)
    if (custody is None) != (private_state_repo is None):
        raise bridge.BridgeError("vietnam_private_custody_incomplete")
    if custody is not None and set(custody) != {family for family, _ in commits}:
        raise bridge.BridgeError("vietnam_private_custody_incomplete")
    if _sha(db) != expected_db_sha256:
        raise bridge.BridgeError("database_preimage_changed")
    if any(Path(str(db) + s).exists() for s in ("-wal", "-shm", "-journal")):
        raise bridge.BridgeError("database_has_active_sidecars")
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    # Ledgers record outcomes for rows in the scratch copy; they are staged
    # beside the real ones and published only once that copy replaces the DB.
    staging = Path(tempfile.mkdtemp(prefix=".vietnam-ledgers-", dir=str(ledger_dir)))
    fd, name = tempfile.mkstemp(prefix=".vietnam-daily-", dir=str(db.parent))
    os.close(fd)
    scratch = Path(name)
    reports = []
    try:
        for family, _commit in commits:
            current = ledger_dir / ("%s.json" % family)
            if current.is_file():
                shutil.copyfile(current, staging / current.name)
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
                private = custody is not None
                reports.append(bridge.run_family(
                    conn, private_state_repo if private else state_repo, commit, family,
                    api=api, as_of_utc=as_of_utc,
                    source_use=policies[family], analyzer=analyzer,
                    ledger_path=staging / ("%s.json" % family), run_id=run_id,
                    custody=custody[family] if private else None))
            if (conn.execute("PRAGMA integrity_check").fetchone() != ("ok",)
                    or conn.execute("PRAGMA foreign_key_check").fetchall()):
                raise bridge.BridgeError("vietnam_daily_integrity_failed")
        if _sha(db) != expected_db_sha256:
            raise bridge.BridgeError("database_changed_concurrently")
        os.chmod(scratch, db.stat().st_mode & 0o777)
        os.replace(str(scratch), str(db))
        for staged in sorted(staging.iterdir()):
            os.replace(str(staged), str(ledger_dir / staged.name))
        return reports
    finally:
        scratch.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--expected-db-sha256", required=True)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--private-custody", action="append", default=[],
                   metavar="SOURCE_FAMILY=PUBLIC_FROZEN_TIP",
                   help="run each family from its private archive ref")
    p.add_argument("--private-state-repo", type=Path)
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
        custody = private_repo = None
        if args.private_custody or args.private_state_repo is not None:
            tips = _tips(args.private_custody, families)
            if args.private_state_repo is None or set(tips) != set(families):
                raise bridge.BridgeError("vietnam_private_custody_incomplete")
            token = os.environ.get("VIETNAM_PRIVATE_PROVENANCE_TOKEN")
            if not token:
                raise bridge.BridgeError("vietnam_private_provenance_token_required")
            private_api = GithubRead(token, repository=vn.PRIVATE_REPO)
            custody = {family: bridge.PrivateCustody(public_frozen_tip=tip,
                                                     private_api=private_api)
                       for family, tip in tips.items()}
            private_repo = args.private_state_repo
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
                      analyzer=analyzer, as_of_utc=as_of,
                      custody=custody, private_state_repo=private_repo)
        print(json.dumps({"status": "OK", "release": args.release, "runs": reports},
                         sort_keys=True, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "HOLD", "release": args.release,
                          "reason": str(exc) or type(exc).__name__, "database_replaced": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
