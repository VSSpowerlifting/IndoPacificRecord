"""Admit trusted-validated AFP official-link metadata into SQLite.

Subcommands:
  admit         validate an exact AFP source checkout (``shadow/ph-afp``, the
                public pre-cutover history) and/or a private-runner signed
                envelope, then admit metadata-only rows for the Philippines.
  sign-private  PRIVATE RUNNER ONLY: validate ``archive/ph-afp`` and write a
                MAC'd metadata-only envelope to files (never stdout).

Same write discipline as the Indonesia admission (whose generic GitHub and
file helpers this reuses): scratch copy beside the database, admission,
integrity check, an independent read-only readback, a byte-identical
production pre-image check, then an atomic rename. Only counts and digests
are printed; no AFP title, body, photograph or translation is read out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import ph_afp_release_validator as validator  # noqa: E402
from core.crossdesk_official_metadata_candidates import IntakeHold  # noqa: E402
from core.regional_official_link_release import (  # noqa: E402
    TABLE, RegionalLinkHold, admit,
)
from scripts.admit_indonesia_kemhan_official_links import (  # noqa: E402
    _head, _now, _sha256, github_fetcher,
)

PRODUCTION_DB = ROOT / "pla_watch.db"
DESK = validator.DESK
BRIDGE_KEY_ENV = "AFP_BRIDGE_KEY"


def _unrelated_digest(conn):
    """Digest of every row outside the Philippines admitted links."""
    h = hashlib.sha256()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in tables:
        h.update(name.encode() + b"\0")
        if name == TABLE:
            sql = ('SELECT * FROM "%s" WHERE desk<>? ORDER BY source_family, source_identity'
                   % name)
            rows = conn.execute(sql, (DESK,))
        else:
            rows = conn.execute('SELECT * FROM "%s" ORDER BY rowid' % name)
        for row in rows:
            h.update(repr(row).encode("utf-8", "surrogatepass"))
    return h.hexdigest()


def admit_validated(db_path, validations, *, as_of_utc, fail_after_insert=None):
    """Atomically admit one or more validated AFP packets; returns receipts."""
    db_path = Path(db_path)
    before = _sha256(db_path)
    fd, tmp_name = tempfile.mkstemp(prefix=".%s.philippines-admission-" % db_path.name,
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
        with sqlite3.connect(tmp.as_uri() + "?mode=ro", uri=True) as ro:
            validator.need(_unrelated_digest(ro) == unrelated_before,
                           "unrelated_production_rows_changed")
            stored = {r[0]: r[1:] for r in ro.execute(
                "SELECT source_identity, canonical_official_url, publisher_posted_date "
                "FROM %s WHERE desk=? AND source_family=?" % TABLE,
                (DESK, validator.FAMILY))}
        for v in validations:
            approved = {row["source_identity"] for row in v["approved"]}
            for row in v["approved"]:
                validator.need(stored.get(row["source_identity"]) ==
                               (row["canonical_official_url"], row["publisher_posted_date"]),
                               "admitted_row_readback_mismatch")
            # AFP has no semantic-hold identity; its hold is the unreviewed
            # post-pin cohort, which must never reach the table.
            for row in v["eligible"]:
                validator.need(row["source_identity"] in approved
                               or row["source_identity"] not in stored,
                               "unreviewed_record_admitted")
        validator.need(_sha256(db_path) == before, "production_database_changed_concurrently")
        os.chmod(tmp, db_path.stat().st_mode & 0o777)
        os.replace(tmp, db_path)
        return receipts, len(stored)
    finally:
        if tmp.exists():
            tmp.unlink()


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
        key = os.environ.get(BRIDGE_KEY_ENV, "").encode()
        validator.need(bool(key), "afp_bridge_key_not_configured")
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
        "admission_receipts": receipts, "philippines_rows_after": total,
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
    key = os.environ.get(BRIDGE_KEY_ENV, "").encode()
    validator.need(bool(key), "afp_bridge_key_not_configured")
    body, mac = validator.sign_envelope(
        validated, key=key, source_run_attempt=args.source_run_attempt,
        public_frozen_tip=args.public_frozen_tip)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "afp-envelope.json.gz").write_bytes(body)
    (out / "afp-envelope.mac").write_text(mac + "\n", encoding="ascii")
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
                  else "philippines_source_or_database_unavailable")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "published_original_titles_or_bodies": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
