"""Admit trusted-validated Kemhan Berita official-link metadata into SQLite.

Subcommands:
  admit         validate an exact source checkout (normally the public frozen
                ``shadow/indonesia-kemhan`` branch) and/or a private-runner
                signed envelope, then admit metadata-only rows.
  sign-private  PRIVATE RUNNER ONLY: validate the private archive and write a
                MAC'd metadata-only envelope to files (never stdout).

Writes happen on a scratch copy beside the database: admission, integrity
check and an independent read-only readback run there, the production file
must be byte-identical to its pre-run state, and only then is the copy
atomically renamed over it. No publisher title, body, translation or media is
read into output, and nothing is printed except counts and digests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import indonesia_kemhan_release_validator as validator  # noqa: E402
from core.crossdesk_official_metadata_candidates import IntakeHold  # noqa: E402
from core.regional_official_link_release import (  # noqa: E402
    TABLE, RegionalLinkHold, admit,
)

PRODUCTION_DB = ROOT / "pla_watch.db"
DESK = "indonesia"


def github_fetcher(repositories, token=None, api="https://api.github.com"):
    """Return fetch_run(run_number) -> run JSON, or None if not visible."""
    cache = {}

    def fetch_run(number):
        if number in cache:
            return cache[number]
        found = None
        for repo in repositories:
            req = urllib.request.Request(
                "%s/repos/%s/actions/runs/%s" % (api, repo, number),
                headers={"Accept": "application/vnd.github+json",
                         **({"Authorization": "Bearer " + token} if token else {})})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    found = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue
                raise validator.ValidatorHold("github_run_records_unavailable") from None
            except (OSError, ValueError):
                raise validator.ValidatorHold("github_run_records_unavailable") from None
        cache[number] = found
        return found
    return fetch_run


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _head(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL).stdout.decode().strip()
    except (OSError, subprocess.SubprocessError):
        raise validator.ValidatorHold("validator_checkout_unidentified") from None


def _unrelated_digest(conn):
    """Digest of every row outside this desk's admitted links."""
    h = hashlib.sha256()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in tables:
        where = " WHERE desk<>'indonesia'" if name == TABLE else ""
        h.update(name.encode() + b"\0")
        for row in conn.execute('SELECT * FROM "%s"%s ORDER BY rowid' % (name, where)
                                if name != TABLE else
                                'SELECT * FROM "%s"%s ORDER BY source_family, source_identity'
                                % (name, where)):
            h.update(repr(row).encode("utf-8", "surrogatepass"))
    return h.hexdigest()


def admit_validated(db_path, validations, *, as_of_utc, fail_after_insert=None):
    """Atomically admit one or more validated packets; returns receipts."""
    db_path = Path(db_path)
    before = _sha256(db_path)
    fd, tmp_name = tempfile.mkstemp(prefix=".%s.indonesia-admission-" % db_path.name,
                                    dir=str(db_path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_bytes(db_path.read_bytes())
        with sqlite3.connect(str(tmp)) as conn:
            unrelated_before = _unrelated_digest(conn)
            receipts = []
            for v in validations:
                receipts.append(admit(
                    conn, v["packet"], v["policy"], v["receipt"],
                    as_of_utc=as_of_utc, trusted_validator=v["trusted_validator"],
                    baseline_packet=v["baseline_packet"]))
                if fail_after_insert:
                    fail_after_insert()
            validator.need(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                           "production_sqlite_integrity_failed")
            conn.commit()
            conn.execute("PRAGMA journal_mode=DELETE")
        conn.close()
        # Independent read-only readback of the staged file.
        with sqlite3.connect(tmp.as_uri() + "?mode=ro", uri=True) as ro:
            validator.need(_unrelated_digest(ro) == unrelated_before,
                           "unrelated_production_rows_changed")
            stored = {r[0]: r[1:] for r in ro.execute(
                "SELECT source_identity, canonical_official_url, publisher_posted_date "
                "FROM %s WHERE desk='indonesia' AND source_family=?" % TABLE,
                (validator.FAMILY,))}
        for v in validations:
            for row in v["approved"]:
                validator.need(stored.get(row["source_identity"]) ==
                               (row["canonical_official_url"], row["publisher_posted_date"]),
                               "admitted_row_readback_mismatch")
        validator.need(validator.HELD_IDENTITY not in stored, "semantic_hold_admitted")
        validator.need(_sha256(db_path) == before, "production_database_changed_concurrently")
        os.chmod(tmp, db_path.stat().st_mode & 0o777)
        os.replace(tmp, db_path)
        return receipts, len(stored)
    finally:
        if tmp.exists():
            tmp.unlink()


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_admit(args):
    db = Path(args.production_db).expanduser().resolve(strict=True)
    if args.rehearsal:
        validator.need(db != PRODUCTION_DB.resolve(), "rehearsal_must_not_target_production")
    else:
        validator.need(db == PRODUCTION_DB.resolve() and not db.is_symlink(),
                       "only_canonical_production_database_allowed")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    fetch = github_fetcher([validator.PUBLIC_REPOSITORY], token)
    ref = args.validator_ref or _head(ROOT)
    checkout = Path(args.source_checkout).expanduser().resolve(strict=True)
    tip = _head(checkout)
    validator.need(args.source_commit == tip, "source_checkout_not_at_requested_commit")
    validations = [validator.validate_source_checkout(
        checkout, tip, fetch_run=fetch, validator_ref=ref)]
    if args.signed_envelope:
        key = os.environ.get("KEMHAN_BRIDGE_KEY", "").encode()
        body = Path(args.signed_envelope).read_bytes()
        mac = Path(args.signed_mac).read_text(encoding="ascii").strip()
        validations.append(validator.validate_signed_envelope(
            body, mac, key=key, public_checkout=checkout, public_frozen_tip=tip,
            validator_ref=ref, public_main=ROOT, fetch_run=fetch))
    receipts, total = admit_validated(db, validations, as_of_utc=_now())
    print(json.dumps({
        "status": "ADMITTED", "desk": DESK,
        "validations": [{"source_git_commit": v["packet"]["source_git_commit"],
                         "metadata_manifest_sha256": v["packet"]["metadata_manifest_sha256"],
                         "eligible": len(v["eligible"]),
                         "approved_reviewed_cohort": len(v["approved"]),
                         "held_unreviewed": v["receipt"]["held_unreviewed_count"],
                         "authenticated_scheduled_days": len(
                             v["receipt"]["authenticated_scheduled_days"])}
                        for v in validations],
        "admission_receipts": receipts, "indonesia_rows_after": total,
        "published_original_titles_or_bodies": False,
    }, sort_keys=True))
    return 0


def cmd_sign_private(args):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    fetch = github_fetcher([validator.PUBLIC_REPOSITORY, validator.PRIVATE_REPOSITORY], token)
    checkout = Path(args.source_checkout).expanduser().resolve(strict=True)
    validator.need(args.source_commit == _head(checkout), "source_checkout_not_at_requested_commit")
    validated = validator.validate_source_checkout(
        checkout, args.source_commit, fetch_run=fetch, validator_ref=_head(ROOT))
    key = os.environ.get("KEMHAN_BRIDGE_KEY", "").encode()
    body, mac = validator.sign_envelope(
        validated, key=key, source_run_attempt=args.source_run_attempt,
        public_frozen_tip=args.public_frozen_tip)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "kemhan-envelope.json.gz").write_bytes(body)
    (out / "kemhan-envelope.mac").write_text(mac + "\n", encoding="ascii")
    print(json.dumps({"status": "SIGNED", "eligible": len(validated["eligible"]),
                      "approved_reviewed_cohort": len(validated["approved"]),
                      "envelope_bytes": len(body),
                      "metadata_manifest_sha256": validated["packet"]["metadata_manifest_sha256"]},
                     sort_keys=True))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("admit")
    a.add_argument("--source-checkout", required=True)
    a.add_argument("--source-commit", required=True)
    a.add_argument("--production-db", required=True)
    a.add_argument("--rehearsal", action="store_true",
                   help="target a scratch copy; refuses the tracked database")
    a.add_argument("--validator-ref", help="IPR commit running this validator")
    a.add_argument("--signed-envelope")
    a.add_argument("--signed-mac")
    s = sub.add_parser("sign-private")
    s.add_argument("--source-checkout", required=True)
    s.add_argument("--source-commit", required=True)
    s.add_argument("--source-run-attempt", required=True)
    s.add_argument("--public-frozen-tip", required=True)
    s.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    try:
        if args.command == "admit" and bool(args.signed_envelope) != bool(args.signed_mac):
            raise validator.ValidatorHold("signed_envelope_and_mac_required_together")
        return cmd_admit(args) if args.command == "admit" else cmd_sign_private(args)
    except (RegionalLinkHold, IntakeHold, sqlite3.Error, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, (RegionalLinkHold, IntakeHold))
                  else "indonesia_source_or_database_unavailable")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "published_original_titles_or_bodies": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
