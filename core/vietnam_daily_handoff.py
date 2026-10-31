"""Signed handoff of approved Vietnam Daily articles: private runner -> public corpus.

The private runner holds the originals. It runs core.vietnam_corpus_bridge on a
copy of public main's database, so its corpus copy is discarded; what crosses
to the canonical database is only the projection the bridge wrote for this
run's PUBLISHED records (the permitted article columns and their provenance),
MAC'd with VIETNAM_PRIVATE_BRIDGE_KEY. Nothing else crosses: no ledger, no
withheld original, no held or screened record, no token.

The public side trusts the MAC for authenticity only. Rights are re-derived
from the owner-sealed decision committed to public main
(config/vietnam_source_use/<family>.json): every record must carry exactly the
permission snapshot that decision gives its identity, omit every field the
decision withholds, and belong to a family with no source hold on a promoted
desk. Records reuse bridge._insert, so a re-admitted handoff is a no-op and a
changed version is held, never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from core import vietnam_corpus_bridge as bridge
from core import vietnam_daily_qa as qa
from core import vietnam_official_link_admission as vn
from core import vietnam_source_use as source_use
from core.collection.vietnam_sources import PROCESSING_SOURCES as SOURCES

SCHEMA = "ipr-vietnam-private-daily-articles/1"
DOMAIN = b"IPR-VIETNAM-PRIVATE-DAILY-ARTICLES-v1\n"
BRANCH = "daily/vietnam"
PATH = "daily/handoff.json"
# The contents API response (base64 plus envelope) must fit
# attest_vietnam_run_state.MAX_API_BYTES; records past this wait for the next
# run, where the bridge offers them again from its ledger without a model call.
MAX_BYTES = 160_000
ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "config" / "vietnam_source_use"
_KEYS = {"schema", "source_repository", "run_id", "generated_utc", "families",
         "deferred", "mac"}
_FAMILY_KEYS = {"source_family", "source_ref", "source_git_commit",
                "rights_decision_sha256", "records"}


class HandoffError(bridge.BridgeError):
    """The handoff is not authentic, not permitted, or not well formed."""


def _need(ok, code):
    if not ok:
        raise HandoffError(code)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _mac(key: bytes, body: dict) -> str:
    return hmac.new(key, DOMAIN + _canonical(body), hashlib.sha256).hexdigest()


def _check_keys(bridge_key: bytes, review_key: Optional[bytes] = None):
    _need(isinstance(bridge_key, bytes) and len(bridge_key) >= 32,
          "vietnam_private_bridge_key_required")
    _need(review_key is None or not hmac.compare_digest(bridge_key, review_key),
          "vietnam_bridge_key_must_differ_from_review_key")


# ── Private runner ───────────────────────────────────────────────────────────

def sign(reports: List[dict], ledgers: Dict[str, dict], *, key: bytes, run_id: str,
         generated_utc: str) -> dict:
    """The MAC'd envelope of this run's PUBLISHED projections, in stable order."""
    _check_keys(key)
    families, size, deferred = [], 2048, 0
    for report in sorted(reports, key=lambda r: r["source_family"]):
        family = report["source_family"]
        items = ledgers[family]["items"]
        records = []
        for identity in sorted(o["source_identity"] for o in report["outcomes"]
                               if o["outcome"] == qa.PUBLISHED):
            article = items[identity]["article"]
            cost = len(_canonical(article))
            if size + cost > MAX_BYTES:
                deferred += 1
                continue
            size += cost
            records.append(article)
        families.append({"source_family": family, "source_ref": report["custody"]["source_ref"],
                         "source_git_commit": report["source_git_commit"],
                         "rights_decision_sha256": report["rights_decision_sha256"],
                         "records": records})
    body = {"schema": SCHEMA, "source_repository": vn.PRIVATE_REPO, "run_id": run_id,
            "generated_utc": generated_utc, "families": families, "deferred": deferred}
    return dict(body, mac=_mac(key, body))


# ── Public side ──────────────────────────────────────────────────────────────

def fetch(private_api) -> dict:
    """The current handoff on the private repository's daily branch."""
    from scripts.attest_vietnam_run_state import encoded_content
    return encoded_content(private_api, PATH, BRANCH, prefix=vn.PRIVATE_PREFIX)


def _decision(family: str, review_key: bytes, as_of: str, decisions: Path):
    path = Path(decisions) / ("%s.json" % family)
    _need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 131072,
          "vietnam_source_use_decision_absent")
    from scripts.publish_shadow_review import strict_loads
    sealed = strict_loads(path.read_text(encoding="utf-8"), "Vietnam source-use decision")
    return source_use.verify_decision(sealed, review_key, family, as_of=as_of[:10])


def _check_record(family: str, entry: dict, policy, article) -> dict:
    _need(isinstance(article, dict) and set(article) == {"row", "provenance"},
          "vietnam_handoff_record_fields")
    row, prov = article["row"], article["provenance"]
    _need(isinstance(row, dict) and set(row) == bridge.ROW_COLUMNS
          and isinstance(prov, dict) and set(prov) == bridge.PROVENANCE_COLUMNS,
          "vietnam_handoff_record_columns")
    identity = prov["source_identity"]
    vn.exact_url(family, identity, prov["canonical_official_url"])
    # An article may be re-offered from the private ledger after new captures
    # advance the family archive tip. Keep its originally authenticated evidence
    # commit; the signed envelope separately identifies the latest archive tip.
    _need(prov["source_family"] == family
          and isinstance(prov["source_git_commit"], str)
          and re.fullmatch(r"[0-9a-f]{40}", prov["source_git_commit"])
          and prov["rights_decision_sha256"] == policy.decision_sha256
          and prov["rights_policy_version"] == policy.policy_version
          and prov["attribution_text"] == policy.attribution_text
          and prov["license_terms"] == policy.license_terms,
          "vietnam_handoff_provenance_mismatch")
    _need(row["content_hash"] == prov["content_sha256"]
          and row["published_date"] == prov["publisher_posted_date"]
          and row["passed_relevance"] == 1
          and isinstance(row["summary_english"], str) and row["summary_english"].strip(),
          "vietnam_handoff_row_mismatch")
    if family == source_use.VPCP:
        proof = json.loads(prov["qa_json"])
        _need(proof.get("outcome") == qa.PUBLISHED and proof.get("second_pass",{}).get("ok") is True,
              "vpcp_handoff_quality_missing")
        document = proof.get("details",{}).get("VPCP_DOCUMENT",{})
        checks = document.get("identity_checks",{})
        _need(document.get("pdf_sha256") == prov["capture_sha256"]
              and type(document.get("page_count")) is int and 1 <= document["page_count"] <= 40
              and all(checks.get(k)=="match" for k in ("number","date","issuer"))
              and checks.get("basis") in ("page_text","page_text_and_widget_appearances"),
              "vpcp_handoff_document_proof_missing")
    perms = policy.snapshot(identity)
    _need(prov["permissions_json"] == json.dumps(perms, sort_keys=True)
          and perms["external_model_transmission"] and perms["public_ipr_analysis"],
          "vietnam_handoff_permissions_mismatch")
    analysis_headline = (family in (source_use.MPS, source_use.VPCP) and not prov["translation_published"]
                         and prov["translation_prompt_version"] is None)
    if analysis_headline:
        from core.title_translation import valid_english
        _need(valid_english(row["title_english"]) and len(row["title_english"]) <= 200,
              "vietnam_handoff_headline_invalid")
    for column, permission in (("title_original", "public_title_display"),
                               ("text_original", "public_original_storage"),
                               ("title_english", "public_ipr_analysis" if analysis_headline
                                else "public_full_translation"),
                               ("text_english", "public_full_translation")):
        _need(row[column] is None or perms[permission], "vietnam_handoff_withheld_field")
    _need(prov["original_withheld"] == (0 if row["text_original"] else 1)
          and prov["translation_published"] == (1 if row["text_english"] else 0),
          "vietnam_handoff_flags_mismatch")
    return {"source_identity": identity, "content_sha256": prov["content_sha256"],
            "canonical_official_url": prov["canonical_official_url"]}


def verify(envelope, *, bridge_key: bytes, review_key: bytes, as_of: str, desk=None,
           decisions: Optional[Path] = None) -> List[tuple]:
    """Every record to admit as (family, record, row, provenance); refuses the whole
    handoff on any defect, before anything is written."""
    _check_keys(bridge_key, review_key)
    _need(isinstance(envelope, dict) and set(envelope) == _KEYS
          and isinstance(envelope["mac"], str), "vietnam_handoff_fields")
    body = {k: v for k, v in envelope.items() if k != "mac"}
    _need(hmac.compare_digest(_mac(bridge_key, body), envelope["mac"]),
          "vietnam_handoff_mac_invalid")
    _need(envelope["schema"] == SCHEMA and envelope["source_repository"] == vn.PRIVATE_REPO
          and isinstance(envelope["families"], list) and type(envelope["deferred"]) is int,
          "vietnam_handoff_scope_invalid")
    if desk is None:
        from core.desk_registry import load_registry
        desk = load_registry().get("vietnam")
    out, seen = [], set()
    for entry in envelope["families"]:
        _need(isinstance(entry, dict) and set(entry) == _FAMILY_KEYS
              and entry["source_family"] in SOURCES
              and entry["source_ref"] == vn.private_ref(entry["source_family"])
              and re.fullmatch(r"[0-9a-f]{40}", str(entry["source_git_commit"]))
              and isinstance(entry["records"], list), "vietnam_handoff_family_invalid")
        family = entry["source_family"]
        if not entry["records"]:
            continue
        if family != source_use.VPCP:
            _need(family not in vn.HOLDS, "vietnam_handoff_source_hold")
        _need(bridge.desk_promoted(desk), "vietnam_desk_not_promoted")
        if family == source_use.VPCP:
            # The legacy original/link-admission map holds every non-MPS
            # source. This separately authorized private-text projection uses
            # its own fail-closed policy, sealed decision and document QA below.
            # Do not clear the original-admission hold or another family's hold.
            from processing.vpcp_policy import require_permission
            require_permission("public_ipr_analysis")
        policy = _decision(family, review_key, as_of, decisions or DECISIONS)
        _need(entry["rights_decision_sha256"] == policy.decision_sha256,
              "vietnam_handoff_decision_mismatch")
        for article in entry["records"]:
            record = _check_record(family, entry, policy, article)
            _need(record["source_identity"] not in seen, "vietnam_handoff_record_repeated")
            seen.add(record["source_identity"])
            out.append((family, record, article["row"], article["provenance"]))
    return out


def admit(conn, records: List[tuple]) -> dict:
    """Insert verified records through the bridge's own write path."""
    counts: Dict[str, int] = {}
    for family, record, row, prov in records:
        outcome, _article_id, code = bridge._insert(conn, family, record, row, prov)
        key = outcome if code is None else "%s:%s" % (outcome, code)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admit_database(db: Path, records: List[tuple]) -> dict:
    """admit() on a sibling copy that replaces db only after integrity checks."""
    if any(Path(str(db) + s).exists() for s in ("-wal", "-shm", "-journal")):
        raise HandoffError("database_has_active_sidecars")
    before = _sha(db)
    fd, name = tempfile.mkstemp(prefix=".vietnam-handoff-", dir=str(db.parent))
    os.close(fd)
    scratch = Path(name)
    try:
        scratch.write_bytes(db.read_bytes())
        with closing(sqlite3.connect(str(scratch), isolation_level=None)) as conn:
            if conn.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise HandoffError("vietnam_daily_requires_single_file_journal")
            conn.execute("PRAGMA foreign_keys=ON")
            from migrations.runner import applied_versions, apply_all, discover
            pending = {m.version for m in discover()} - set(applied_versions(conn))
            if not pending <= {"0017", "0018", "0019"}:
                raise HandoffError("unrelated_pending_migrations")
            apply_all(conn, sync_config=False)
            counts = admit(conn, records)
            if (conn.execute("PRAGMA integrity_check").fetchone() != ("ok",)
                    or conn.execute("PRAGMA foreign_key_check").fetchall()):
                raise HandoffError("vietnam_daily_integrity_failed")
        if _sha(db) != before:
            raise HandoffError("database_changed_concurrently")
        os.chmod(scratch, db.stat().st_mode & 0o777)
        os.replace(str(scratch), str(db))
        return counts
    finally:
        scratch.unlink(missing_ok=True)


def main(argv=None) -> int:
    """Admit the private runner's current handoff into the canonical database.

    Exit 0: admitted, or nothing to admit. Exit 2: held, database untouched.
    Prints counts and codes only, never article text.
    """
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--database", type=Path, default=ROOT / "pla_watch.db")
    p.add_argument("--handoff", type=Path,
                   help="a local signed handoff instead of the private daily branch")
    args = p.parse_args(argv)
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        if args.database.is_symlink():
            raise HandoffError("symlink_database_refused")
        db = args.database.resolve(strict=True)
        bridge_key = os.environ.get("VIETNAM_PRIVATE_BRIDGE_KEY", "").encode()
        review_key = os.environ.get("VIETNAM_SOURCE_USE_REVIEW_KEY", "").encode()
        _check_keys(bridge_key, review_key)
        if args.handoff is not None:
            from scripts.publish_shadow_review import strict_loads
            envelope = strict_loads(args.handoff.read_text(encoding="utf-8"), "Vietnam handoff")
        else:
            token = os.environ.get("VIETNAM_PRIVATE_PROVENANCE_TOKEN")
            if not token:
                raise HandoffError("vietnam_private_provenance_token_required")
            from scripts.attest_vietnam_run_state import GithubRead
            envelope = fetch(GithubRead(token, repository=vn.PRIVATE_REPO))
        records = verify(envelope, bridge_key=bridge_key, review_key=review_key, as_of=as_of)
        counts = admit_database(db, records) if records else {}
        print(json.dumps({"status": "OK", "run_id": envelope["run_id"], "counts": counts,
                          "deferred": envelope["deferred"]}, sort_keys=True))
        return 0
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc) or type(exc).__name__,
                          "database_replaced": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
