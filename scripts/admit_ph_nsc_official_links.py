"""Admit Philippine NSC official-link metadata from private custody into SQLite.

Subcommands:
  sign-private  PRIVATE RUNNER ONLY: replay one commit of ``archive/ph-nsc``
                into a metadata-only candidate packet and write it, gzipped and
                MAC'd with ``NSC_BRIDGE_KEY``, to files (never stdout).
  admit         PUBLIC PRODUCTION: authenticate that envelope, re-verify every
                field it carries, then admit authorized rows for the
                Philippines desk under ``core.ph_nsc_official_link_admission``.

The envelope can carry only identity, canonical URL, posted date, hashes and
run ids: exact key sets are enforced, so no title, body, excerpt or
translation can ride along. Custody is checked here before the silent-window
no-op, so even an empty packet from the retired public branch is refused.

Write discipline is AFP's: scratch copy beside the database, admission,
integrity check, independent read-only readback, a byte-identical production
pre-image check, then an atomic rename. A zero-link packet writes nothing, so
quiet days leave the database byte-identical. Only counts and digests print.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import ph_nsc_official_link_admission as nsc  # noqa: E402
from core.indonesia_kemhan_release_validator import (  # noqa: E402
    ValidatorHold, _is_ancestor, _mac, need,
)
from core.regional_official_link_release import (  # noqa: E402
    TABLE, RegionalLinkHold, canonical,
)
from scripts.admit_indonesia_kemhan_official_links import (  # noqa: E402
    _head, _now, _sha256,
)

PRODUCTION_DB = ROOT / "pla_watch.db"
BRIDGE_KEY_ENV = "NSC_BRIDGE_KEY"
REVIEW_KEY_ENV = "NSC_RELEASE_REVIEW_KEY"
ENVELOPE_SCHEMA = "ipr-ph-nsc-official-link-envelope/1"
MAX_ENVELOPE_BYTES = 48 * 1024
RUN = re.compile(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,3}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FIRST_SEEN = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
ENVELOPE_KEYS = {"schema", "source_repository", "source_ref",
                 "source_run_attempt", "validator_ref", "packet"}
PACKET_KEYS = {"schema", "source_family", "desk", "source_ref", "source_git_commit",
               "records", "links", "public_release_authorized",
               "original_content_exported"}
RECORD_KEYS = {"source_identity", "canonical_official_url", "publisher_posted_date",
               "capture_sha256", "content_sha256", "first_seen_run"}
LINK_KEYS = {"source_family", "source_identity", "desk", "canonical_official_url",
             "publisher_posted_date", "official_issuer", "official_publisher",
             "official_republisher", "source_git_commit", "first_seen_run",
             "metadata_version_sha256"}


def sign_envelope(packet, *, key, source_run_attempt, validator_ref):
    """Private runner only: compress and MAC one metadata-only packet."""
    need(RUN.fullmatch(source_run_attempt or "") is not None, "source_run_attempt_invalid")
    need(nsc.SHA40.fullmatch(validator_ref or "") is not None, "validator_ref_invalid")
    verify_packet(packet)
    envelope = {"schema": ENVELOPE_SCHEMA, "source_repository": nsc.PRIVATE_REPOSITORY,
                "source_ref": nsc.PRIVATE_REF, "source_run_attempt": source_run_attempt,
                "validator_ref": validator_ref, "packet": packet}
    body = gzip.compress(canonical(envelope), mtime=0)
    need(len(body) <= MAX_ENVELOPE_BYTES, "signed_envelope_too_large")
    return body, _mac(key, body)


def verify_packet(packet):
    """Re-derive every carried claim that can be checked without the capture."""
    need(type(packet) is dict and set(packet) == PACKET_KEYS
         and packet["schema"] == nsc.PACKET and packet["source_family"] == nsc.FAMILY
         and packet["desk"] == nsc.DESK
         and packet["public_release_authorized"] is False
         and packet["original_content_exported"] is False,
         "nsc_packet_schema_invalid")
    # Custody first: an empty packet is only a no-op when it is private.
    need(packet["source_ref"] == nsc.PRIVATE_REF, "nsc_rows_not_from_private_custody")
    commit = packet["source_git_commit"]
    need(type(commit) is str and nsc.SHA40.fullmatch(commit) is not None,
         "nsc_source_commit_invalid")
    records, links = packet["records"], packet["links"]
    need(type(records) is list and type(links) is list and len(records) == len(links),
         "nsc_packet_schema_invalid")
    by_id = {}
    for r in records:
        need(type(r) is dict and set(r) == RECORD_KEYS
             and type(r["source_identity"]) is str
             and r["source_identity"] not in by_id
             and nsc.canonical_permalink(r["source_identity"], r["canonical_official_url"],
                                         r["publisher_posted_date"])
             and all(type(r[k]) is str and SHA256.fullmatch(r[k])
                     for k in ("capture_sha256", "content_sha256"))
             and type(r["first_seen_run"]) is str
             and FIRST_SEEN.fullmatch(r["first_seen_run"]) is not None,
             "nsc_packet_record_invalid")
        by_id[r["source_identity"]] = r
    seen = set()
    for link in links:
        need(type(link) is dict and set(link) == LINK_KEYS, "nsc_packet_link_invalid")
        r = by_id.get(link["source_identity"])
        need(r is not None and link["source_identity"] not in seen
             and link["source_family"] == nsc.FAMILY and link["desk"] == nsc.DESK
             and link["official_issuer"] is None
             and link["official_publisher"] == nsc.PUBLISHER
             and link["official_republisher"] is None
             and link["source_git_commit"] == commit
             and link["canonical_official_url"] == r["canonical_official_url"]
             and link["publisher_posted_date"] == r["publisher_posted_date"]
             and link["first_seen_run"] == r["first_seen_run"]
             and link["metadata_version_sha256"] == nsc._version(link, r["content_sha256"]),
             "nsc_packet_link_mismatch")
        seen.add(link["source_identity"])
    return packet


def validate_envelope(body, mac_hex, *, key, public_main):
    """Public production: authenticate, bound and re-verify a private envelope."""
    need(type(body) is bytes and 0 < len(body) <= MAX_ENVELOPE_BYTES,
         "signed_envelope_size_invalid")
    need(type(mac_hex) is str and SHA256.fullmatch(mac_hex) is not None
         and hmac.compare_digest(_mac(key, body), mac_hex),
         "signed_envelope_mac_invalid")
    try:
        envelope = json.loads(gzip.decompress(body).decode("utf-8"))
    except (OSError, ValueError, UnicodeError, EOFError):
        raise ValidatorHold("signed_envelope_unreadable") from None
    need(type(envelope) is dict and set(envelope) == ENVELOPE_KEYS
         and envelope["schema"] == ENVELOPE_SCHEMA
         and envelope["source_repository"] == nsc.PRIVATE_REPOSITORY
         and type(envelope["source_run_attempt"]) is str
         and RUN.fullmatch(envelope["source_run_attempt"]) is not None,
         "signed_envelope_schema_invalid")
    need(envelope["source_ref"] == nsc.PRIVATE_REF, "nsc_rows_not_from_private_custody")
    ref = envelope["validator_ref"]
    need(type(ref) is str and nsc.SHA40.fullmatch(ref) is not None
         and _is_ancestor(public_main, ref, "HEAD"),
         "private_validator_code_not_on_public_main")
    return verify_packet(envelope["packet"]), envelope["source_run_attempt"]


def unrelated_digest(conn):
    """Every row of every table except NSC's own index rows."""
    h = hashlib.sha256()
    for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        h.update(name.encode() + b"\0")
        if name == TABLE:
            rows = conn.execute(
                'SELECT * FROM "%s" WHERE source_family<>? '
                "ORDER BY source_family, source_identity" % name, (nsc.FAMILY,))
        else:
            rows = conn.execute('SELECT * FROM "%s" ORDER BY rowid' % name)
        for row in rows:
            h.update(repr(row).encode("utf-8", "surrogatepass"))
    return h.hexdigest()


def _stored(conn):
    return {r[0]: r[1:] for r in conn.execute(
        "SELECT source_identity, canonical_official_url, publisher_posted_date FROM %s "
        "WHERE source_family=?" % TABLE, (nsc.FAMILY,))}


def admit_validated(db_path, packet, *, policy, as_of_utc, sealed=None, secret=None,
                    fail_after_insert=None):
    """Atomically admit one verified NSC packet; returns (receipt, NSC rows after)."""
    db_path = Path(db_path)
    verify_packet(packet)
    offered = {l["source_identity"] for l in packet["links"]}
    before = _sha256(db_path)
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as ro:
        stored = _stored(ro)
    ro.close()
    # Private custody is append-only: an admitted statement absent from a
    # later private commit means history was rewritten or a capture lost.
    need(set(stored) <= offered, "nsc_admitted_record_missing_from_private_source")
    if not offered:
        return nsc.admit(None, packet, policy=policy, as_of_utc=as_of_utc), len(stored)
    fd, tmp_name = tempfile.mkstemp(prefix=".%s.nsc-admission-" % db_path.name,
                                    dir=str(db_path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_bytes(db_path.read_bytes())
        with sqlite3.connect(str(tmp)) as conn:
            unrelated_before = unrelated_digest(conn)
            receipt = nsc.admit(conn, packet, policy=policy, as_of_utc=as_of_utc,
                                sealed=sealed, secret=secret)
            if fail_after_insert:
                fail_after_insert()
            need(conn.execute("PRAGMA integrity_check").fetchone() == ("ok",),
                 "production_sqlite_integrity_failed")
            conn.commit()
            conn.execute("PRAGMA journal_mode=DELETE")
        conn.close()
        with sqlite3.connect(tmp.as_uri() + "?mode=ro", uri=True) as ro:
            need(unrelated_digest(ro) == unrelated_before, "unrelated_production_rows_changed")
            after = _stored(ro)
        ro.close()
        for link in packet["links"]:
            if link["source_identity"] in after:
                need(after[link["source_identity"]] ==
                     (link["canonical_official_url"], link["publisher_posted_date"]),
                     "admitted_row_readback_mismatch")
        need(set(after) <= offered, "unreviewed_record_admitted")
        need(_sha256(db_path) == before, "production_database_changed_concurrently")
        os.chmod(tmp, db_path.stat().st_mode & 0o777)
        os.replace(tmp, db_path)
        return receipt, len(after)
    finally:
        if tmp.exists():
            tmp.unlink()


def _key(env):
    key = os.environ.get(env, "").encode()
    need(bool(key), "nsc_bridge_key_not_configured" if env == BRIDGE_KEY_ENV
         else "nsc_review_key_not_configured")
    return key


def cmd_admit(args):
    db = Path(args.production_db).expanduser().resolve(strict=True)
    if args.rehearsal:
        need(db != PRODUCTION_DB.resolve(), "rehearsal_must_not_target_production")
    else:
        need(db == PRODUCTION_DB.resolve() and not db.is_symlink(),
             "only_canonical_production_database_allowed")
    body = Path(args.signed_envelope).read_bytes()
    mac = Path(args.signed_mac).read_text(encoding="ascii").strip()
    packet, attempt = validate_envelope(body, mac, key=_key(BRIDGE_KEY_ENV), public_main=ROOT)
    sealed = secret = None
    if args.sealed_decision:
        sealed = json.loads(Path(args.sealed_decision).read_text(encoding="utf-8"))
        secret = _key(REVIEW_KEY_ENV)
    receipt, total = admit_validated(db, packet, policy=nsc.load_policy(),
                                     as_of_utc=_now(), sealed=sealed, secret=secret)
    print(json.dumps({
        "status": "ADMITTED" if receipt["status"] == "admitted" else "NO_ELIGIBLE_RECORDS",
        "desk": nsc.DESK, "source_family": nsc.FAMILY,
        "source_git_commit": packet["source_git_commit"], "source_run_attempt": attempt,
        "candidate_sha256": nsc.candidate_digest(packet),
        "replayed_records": len(packet["records"]), "admission_receipt": receipt,
        "nsc_rows_after": total, "published_original_titles_or_bodies": False,
    }, sort_keys=True))
    return 0


def cmd_sign_private(args):
    repo = Path(args.state_repo).expanduser().resolve(strict=True)
    need(args.source_commit == _head(repo), "source_checkout_not_at_requested_commit")
    packet = nsc.prepare(repo, args.source_commit, nsc.PRIVATE_REF)
    body, mac = sign_envelope(packet, key=_key(BRIDGE_KEY_ENV),
                              source_run_attempt=args.source_run_attempt,
                              validator_ref=_head(ROOT))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "nsc-envelope.json.gz").write_bytes(body)
    (out / "nsc-envelope.mac").write_text(mac + "\n", encoding="ascii")
    print(json.dumps({"status": "SIGNED", "replayed_records": len(packet["records"]),
                      "links": len(packet["links"]), "envelope_bytes": len(body),
                      "candidate_sha256": nsc.candidate_digest(packet)}, sort_keys=True))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("admit")
    a.add_argument("--production-db", required=True)
    a.add_argument("--rehearsal", action="store_true",
                   help="target a scratch copy; refuses the tracked database")
    a.add_argument("--signed-envelope", required=True)
    a.add_argument("--signed-mac", required=True)
    a.add_argument("--sealed-decision",
                   help="owner-sealed exact-version decision (key in %s)" % REVIEW_KEY_ENV)
    s = sub.add_parser("sign-private")
    s.add_argument("--state-repo", required=True)
    s.add_argument("--source-commit", required=True)
    s.add_argument("--source-run-attempt", required=True)
    s.add_argument("--output-dir", required=True)
    args = p.parse_args(argv)
    try:
        return cmd_admit(args) if args.command == "admit" else cmd_sign_private(args)
    except (RegionalLinkHold, sqlite3.Error, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, RegionalLinkHold)
                  else "nsc_source_or_database_unavailable")
        print(json.dumps({"status": "HOLD", "reason": reason, "production_changed": False,
                          "published_original_titles_or_bodies": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
