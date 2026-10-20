"""Atomic, exact-review MPS metadata admission; production requires --release.

Uses the existing admission validator and regional table. All validation and
the optional 0013 migration happen on a disposable sibling before replacement.
No source text, signing, models, collection, Git push or deployment.
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

from core import vietnam_official_link_admission as vn
from core.regional_official_link_render import read_live_links
from migrations.runner import applied_versions, apply_all, discover
from scripts.attest_vietnam_run_state import GithubRead
from scripts.publish_shadow_review import strict_loads

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unrelated(conn):
    h = hashlib.sha256()
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if name == "schema_migrations":
            continue
        safe = '"' + name.replace('"', '""') + '"'
        sql = "SELECT * FROM " + safe
        if name == "regional_official_source_links":
            sql += " WHERE desk<>'vietnam'"
        h.update(name.encode() + b"\0")
        for row in sorted(conn.execute(sql).fetchall(), key=repr):
            h.update(repr(row).encode())
    return h.hexdigest()


def admit_atomic(db, state_repo, commit, sealed, *, api, secret, as_of_utc,
                 expected_db_sha256, private_projection=None, bridge_key=None, private_api=None):
    db = Path(db)
    vn.need(db.is_file() and not db.is_symlink() and db.stat().st_nlink == 1,
            "unsafe_admission_database")
    vn.need(not any(Path(str(db) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")),
            "database_has_active_sidecars")
    vn.need(sha(db) == expected_db_sha256, "database_preimage_changed")
    fd, name = tempfile.mkstemp(prefix=".vietnam-admission-", dir=str(db.parent))
    os.close(fd)
    scratch = Path(name)
    try:
        scratch.write_bytes(db.read_bytes())
        with closing(sqlite3.connect(str(scratch))) as conn, conn:
            # Replacement and immutable readback require a self-contained file.
            vn.need(conn.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",),
                    "admission_requires_single_file_journal")
            conn.execute("PRAGMA foreign_keys=ON")
            before = unrelated(conn)
            done = applied_versions(conn)
            pending = {m.version for m in discover()} - set(done)
            vn.need(pending <= {"0013"}, "unrelated_pending_migrations")
            apply_all(conn, sync_config=False)
            conn.execute("BEGIN IMMEDIATE")
            if private_projection is None:
                result = vn.admit(conn, state_repo, commit, vn.MPS, sealed,
                                  api=api, secret=secret, as_of_utc=as_of_utc)
            else:
                result = vn.admit_private_projection(conn, private_projection, sealed,
                    bridge_key=bridge_key, secret=secret, api=api, private_api=private_api,
                    as_of_utc=as_of_utc, public_checkout=ROOT)
            vn.need(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                    and conn.execute("PRAGMA foreign_key_check").fetchall() == [],
                    "vietnam_admission_integrity_failed")
            vn.need(unrelated(conn) == before, "unrelated_database_rows_changed")
            conn.commit()
        with closing(sqlite3.connect(scratch.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            rows = read_live_links(conn, "vietnam")
            vn.need(set(sealed["review"]["approved_source_identities"]) <=
                    {r["source_identity"] for r in rows}, "independent_sqlite_readback_failed")
        vn.need(sha(db) == expected_db_sha256, "database_changed_concurrently")
        vn.need(not any(Path(str(db) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")),
                "database_has_active_sidecars")
        os.chmod(scratch, db.stat().st_mode & 0o777)
        os.replace(str(scratch), str(db))
        return result
    finally:
        scratch.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(scratch) + suffix).unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--state-repo", type=Path)
    p.add_argument("--state-commit")
    p.add_argument("--private-projection", type=Path)
    p.add_argument("--signed-decision", type=Path, required=True)
    p.add_argument("--expected-db-sha256", required=True)
    p.add_argument("--release", action="store_true")
    args = p.parse_args(argv)
    try:
        vn.need(not args.database.is_symlink(), "symlink_database_refused")
        db = args.database.resolve(strict=True)
        if args.release:
            vn.need(db == ROOT / "pla_watch.db", "release_requires_canonical_database")
            vn.need(args.private_projection is not None, "release_requires_private_provenance")
        else:
            vn.need(not any((parent / ".git").exists() for parent in db.parents),
                    "rehearsal_requires_external_database")
        path = args.signed_decision
        vn.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 131072,
                "signed_decision_unavailable")
        sealed = strict_loads(path.read_text(), "Vietnam release")
        projection = None
        if args.private_projection:
            vn.need(not args.state_repo and not args.state_commit,
                    "private_projection_cannot_import_source_bytes")
            vn.need(args.private_projection.is_file() and not args.private_projection.is_symlink()
                    and args.private_projection.stat().st_size <= 250000,
                    "private_metadata_projection_unavailable")
            projection = strict_loads(args.private_projection.read_text(), "private metadata")
        else:
            vn.need(args.state_repo and args.state_commit, "source_history_required")
        result = admit_atomic(db, args.state_repo, args.state_commit, sealed,
                              api=GithubRead(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")),
                              secret=os.environ.get("VIETNAM_LINK_REVIEW_KEY", "").encode(),
                              as_of_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              expected_db_sha256=args.expected_db_sha256,
                              private_projection=projection,
                              bridge_key=os.environ.get("VIETNAM_PRIVATE_BRIDGE_KEY", "").encode(),
                              private_api=GithubRead(os.environ.get("VIETNAM_PRIVATE_PROVENANCE_TOKEN"),
                                                     repository=vn.PRIVATE_REPO))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, vn.formal.ReviewError):
        print(json.dumps({"status": "HOLD", "admission_applied": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
