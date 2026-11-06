"""Authenticated offline replay of an accessible Japan MOD news-feed PDF.

The shadow collector stores the PDF byte hash and extracted text, not PDF bytes.
Reacquisition alone cannot establish that the preserved original was complete.
This source-specific bridge accepts an independently retained local PDF and
checks its *exact bytes and text layer* against an Actions-authenticated shadow
state through the existing Japan link-candidate gate.

This returns private text **in memory** for a later governed processor. It
neither acquires or copies source material, certifies maps/diagrams/photographs,
qualifies PDL rights, calls a model, or admits/publishes a Record.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from core import japan_mod_official_links as gate
from processing import pdf_text

SCHEMA = "ipr-japan-mod-pdf-original-replay/1"


class JapanOriginalHold(ValueError):
    """Fixed-code denial; never contains publisher-controlled prose."""


def require(ok, code):
    if not ok:
        raise JapanOriginalHold(code)


def replay_private_pdf(repo, commit, source_identity, pdf_path, *, fetch_run):
    """Return (safe receipt, private original text) after trusted shadow replay.

    fetch_run must be an independent GitHub Actions metadata verifier; the
    existing candidates() authenticates its repository/run/path/commit, ledger,
    snapshot, first-seen lineage, URL policy and stable metadata. A caller's
    claimed rights or capture receipt is never accepted as authority.
    """
    require(type(source_identity) is str and source_identity.startswith(
        gate.FAMILY + ":"), "japan_source_identity_invalid")
    # No file is fetched over the network and no private PDF/text is written.
    pdf = Path(pdf_path).expanduser()
    root = Path(repo).resolve()
    require(pdf.is_absolute() and pdf.is_file() and not pdf.is_symlink()
            and not pdf.parent.is_symlink()
            and root not in pdf.resolve().parents and pdf.resolve() != root,
            "private_pdf_must_be_regular_external_file")
    size = pdf.stat().st_size
    require(0 < size <= pdf_text.MAX_BYTES, "pdf_original_size_out_of_bounds")

    # This is the same authenticated source batch used for the currently
    # admitted official links; it is not an independent invented proof.
    try:
        rows, evidence = gate.candidates(repo, commit, fetch_run=fetch_run)
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error):
        raise JapanOriginalHold("japan_shadow_lineage_unverified") from None
    candidates = [row for row in rows
                  if row["source_identity"] == source_identity
                  and row["source_family"] == gate.FAMILY
                  and row["canonical_official_url"] ==
                      "https://www.mod.go.jp" +
                      source_identity.removeprefix(gate.FAMILY + ":")]
    require(len(candidates) == 1, "source_not_in_authenticated_pdf_cohort")
    candidate = candidates[0]
    require(candidate["source_git_commit"] == commit
            and evidence["source_commit"] == commit,
            "japan_source_commit_mismatch")

    # Exact verified state, not the mutable working DB or an untrusted receipt.
    try:
        frozen = gate._blob(repo, commit, "state/shadow.db")
    except (ValueError, OSError, IndexError):
        raise JapanOriginalHold("japan_shadow_db_unavailable") from None
    require(hashlib.sha256(frozen).hexdigest() == evidence["state_sha256"],
            "japan_shadow_db_version_mismatch")
    with tempfile.TemporaryDirectory(prefix="ipr-jp-pdf-replay-") as folder:
        path = Path(folder) / "shadow.db"
        path.write_bytes(frozen)
        with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1",
                             uri=True) as conn:
            require(conn.execute("PRAGMA quick_check").fetchone() == ("ok",),
                    "japan_shadow_db_invalid")
            row = conn.execute(
                "SELECT source_slug,content_sha256,capture_sha256,"
                "text_original,first_seen_run,published_date "
                "FROM shadow_records WHERE url=?",
                (candidate["canonical_official_url"],)).fetchone()
    require(row is not None and row[0] == gate.FAMILY
            and row[4] == candidate["first_seen_run"]
            and row[5] == candidate["publisher_posted_date"],
            "japan_shadow_record_identity_mismatch")
    content_sha, capture_sha, archived_text = row[1:4]
    require(isinstance(archived_text, str)
            and hashlib.sha256(archived_text.encode("utf-8")).hexdigest()
            == content_sha, "japan_shadow_text_hash_mismatch")

    raw = pdf.read_bytes()
    require(len(raw) == size and hashlib.sha256(raw).hexdigest()
            == capture_sha, "pdf_capture_version_mismatch")
    result = pdf_text.extract_pdf_text(raw)
    require(result.status == pdf_text.OK, "pdf_original_extraction_unavailable")
    # The generic parser can return OK after skipping a page. That is useful
    # for discovery but insufficient for complete original-text qualification.
    require(result.page_count > 0 and result.pages_failed == 0
            and result.pages_with_text == result.page_count,
            "pdf_text_layer_incomplete_pages")
    require(result.text == archived_text
            and hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            == content_sha, "pdf_text_replay_mismatch")

    receipt = {
        "schema": SCHEMA,
        "status": "PDF_TEXT_LAYER_REPLAYED",
        "source_family": gate.FAMILY,
        "source_identity": source_identity,
        "official_url": candidate["canonical_official_url"],
        "rss_pubdate": candidate["publisher_posted_date"],
        "date_type": gate.DATE_TYPE,
        "source_git_commit": commit,
        "source_state_sha256": evidence["state_sha256"],
        "source_first_seen_run": row[4],
        "pdf_capture_sha256": capture_sha,
        "text_sha256": content_sha,
        "page_count": result.page_count,
        "pages_with_text": result.pages_with_text,
        "pages_failed": result.pages_failed,
        "complete_pdf_visual_content_verified": False,
        "publisher_license_qualified": False,
        "external_model_input_authorized": False,
        "public_original_authorized": False,
        "machine_explanation_authorized": False,
        "publication_authorized": False,
        "private_pdf_copied": False,
    }
    return receipt, result.text


def safe_cli_receipt(receipt):
    """Avoid ever serializing the in-memory private source text to stdout."""
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True)
