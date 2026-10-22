"""Replay genuine ministry Git into held metadata, optionally rehearse admission.

No ministry network, signing, models, SMTP or production mutation. Admission
requires an actual separately sealed review and fresh GitHub readback; an
unsigned worksheet cannot activate it. The existing publisher owns live writes.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import vietnam_official_link_admission as vn
from scripts.attest_vietnam_run_state import GithubRead
from scripts.publish_shadow_review import strict_loads


def outside_repositories(path):
    resolved = path.resolve()
    vn.need(not any((p / ".git").exists() for p in (resolved.parent, *resolved.parents)),
            "candidate_and_scratch_paths_must_be_outside_git_repositories")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=sorted(vn.SOURCES), required=True)
    ap.add_argument("--state-repo", type=Path, required=True)
    ap.add_argument("--state-commit", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scratch-db", type=Path)
    ap.add_argument("--signed-decision", type=Path)
    ap.add_argument("--private-state", action="store_true")
    ap.add_argument("--sign-private-projection", action="store_true")
    ap.add_argument("--public-frozen-tip")
    args = ap.parse_args(argv)
    try:
        out = args.out
        vn.need(out.is_absolute() and not out.exists() and not out.is_symlink()
                and ROOT not in out.resolve().parents,
                "candidate_output_must_be_new_and_external")
        outside_repositories(out)
        vn.need(args.sign_private_projection or bool(args.scratch_db) == bool(args.signed_decision),
                "scratch_admission_requires_signed_decision")
        if args.sign_private_projection:
            vn.need(args.source == vn.MPS and args.signed_decision and not args.scratch_db,
                    "private_projection_requires_exact_mps_review")
            vn.need(args.signed_decision.is_file() and not args.signed_decision.is_symlink()
                    and args.signed_decision.stat().st_size <= 131072,
                    "signed_decision_unavailable")
            import subprocess
            decision = strict_loads(args.signed_decision.read_text(), "release decision")
            packet = vn.sign_private_projection(args.state_repo, args.state_commit, args.public_frozen_tip,
                decision, api=GithubRead(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
                                        repository=vn.PRIVATE_REPO),
                public_api=GithubRead(), bridge_key=os.environ.get("VIETNAM_PRIVATE_BRIDGE_KEY", "").encode(),
                review_key=os.environ.get("VIETNAM_LINK_REVIEW_KEY", "").encode(),
                as_of_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                validator_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip())
            with out.open('x', encoding='utf-8') as f:
                os.chmod(out, 0o600)
                json.dump(packet, f, sort_keys=True)
            print(json.dumps({"private_projection_prepared": True, "production_changed": False}))
            return 0
        packet = vn.prepare(args.state_repo, args.state_commit, args.source, private=args.private_state)
        result = None
        if args.scratch_db:
            db = args.scratch_db
            outside_repositories(db)
            vn.need(db.is_file() and not db.is_symlink() and ROOT not in db.resolve().parents
                    and db.resolve() != (args.state_repo / "state/shadow.db").resolve(),
                    "only_external_disposable_database_allowed")
            decision_path = args.signed_decision
            vn.need(decision_path.is_file() and not decision_path.is_symlink()
                    and decision_path.stat().st_size <= 131072, "signed_decision_unavailable")
            sealed = strict_loads(decision_path.read_text(encoding="utf-8"), "release decision")
            key = os.environ.get("VIETNAM_LINK_REVIEW_KEY", "").encode("utf-8")
            token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            with sqlite3.connect(str(db)) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                conn.execute("BEGIN IMMEDIATE")
                result = vn.admit(conn, args.state_repo, args.state_commit, args.source,
                                  sealed, api=GithubRead(token), secret=key,
                                  as_of_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        with os.fdopen(os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            json.dump(packet, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"source_family": args.source, "records": len(packet["records"]),
                          "candidate_sha256": vn.digest(packet), "source_hold": packet["source_hold"],
                          "scratch_admission": result, "production_changed": False}))
        return 0
    except (ValueError, OSError, sqlite3.Error, vn.formal.ReviewError):
        print(json.dumps({"status": "HOLD", "production_changed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
