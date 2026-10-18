"""Private export / public import CLI for DAPA's signed metadata-only bridge.

No network. Source originals stay in the restricted repository. No operation
performs a website publish; the existing serialized Korea publisher owns that.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import korea_dapa_private_to_production as b

ROOT = Path(__file__).resolve().parents[1]


def safe_new(path, contents):
    path = Path(path)
    b.need(path.is_absolute() and not path.exists()
           and not path.is_symlink() and path.parent.is_dir()
           and not path.parent.is_symlink(),
           "dapa_private_packet_output_not_new")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(contents)


def export(args):
    # Private producer refuses to sign an empty result; no dummy new source.
    checkout = Path(args.private_checkout)
    attempt = args.run_attempt
    ledgers = list((checkout / "state/ledger").glob("*-" + attempt + ".json"))
    b.need(len(ledgers) == 1, "dapa_private_ledger_missing")
    ledger = b._json(ledgers[0])
    if ledger.get("result") in ("ok_no_publications", "ok_all_duplicates") and (
            ledger.get("inserted") == 0):
        print("DAPA_NO_NEW_RELEASE_NO_DISPATCH")
        return 0
    packet = b.export_from_private_checkout(checkout, attempt)
    key = os.getenv("DAPA_BRIDGE_KEY", "")
    mac = b.sign(packet, key)
    safe_new(args.packet_output, base64.b64encode(b.canonical(packet)))
    safe_new(args.mac_output, mac.encode("ascii"))
    print("DAPA_PRIVATE_BOUNDED_BATCH_SIGNED; sanitized_records=%d; "
          "no original content exported" % len(packet["records"]))
    return 0



def export_historical(args):
    # A distinct signed type and a separately reviewed/private Git source.
    # No government network access and no retrospective green collector run.
    from core.korea_dapa_historical_owner import export_from_private_checkout
    packet = export_from_private_checkout(Path(args.private_checkout))
    key = os.getenv("DAPA_BRIDGE_KEY", "")
    mac = b.sign(packet, key)
    safe_new(args.packet_output, base64.b64encode(b.canonical(packet)))
    safe_new(args.mac_output, mac.encode("ascii"))
    print("DAPA_OWNER_HISTORICAL_METADATA_ONLY_SIGNED; records=1; originals_held")
    return 0


def admit(args):
    packet_encoded = os.getenv("DAPA_PACKET_B64", "")
    mac = os.getenv("DAPA_PACKET_MAC", "")
    key = os.getenv("DAPA_BRIDGE_KEY", "")
    b.need(type(packet_encoded) is str and 0 < len(packet_encoded) <= 18000,
           "dapa_dispatch_packet_missing_or_oversized")
    try:
        raw = base64.b64decode(packet_encoded, validate=True)
        b.need(len(raw) <= 12000, "dapa_dispatch_decoded_packet_oversized")
        packet = json.loads(raw)
    except (ValueError, binascii.Error, UnicodeError):
        raise b.DAPABridgeHold("dapa_dispatch_packet_cannot_be_decoded") from None
    b.verify_signed_packet(packet, mac, key)  # Before touching production.
    db = Path(args.production_db).expanduser().resolve(strict=True)
    b.need(db == ROOT / "pla_watch.db" and not db.is_symlink(),
           "dapa_only_canonical_production_database_allowed")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with sqlite3.connect(str(db)) as conn:
            # The MND publisher already applies the shared migrations before
            # this stage; silently creating an unexpected schema is forbidden.
            receipt = b.admit(conn, packet, mac, key, as_of_utc=now)
            b.need(conn.execute("PRAGMA quick_check").fetchone() == ("ok",),
                   "dapa_metadata_sqlite_integrity_failed")
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error:
        raise b.DAPABridgeHold("dapa_production_sqlite_write_failed") from None
    print(json.dumps(receipt, sort_keys=True))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="mode", required=True)
    exp = sub.add_parser("export-private")
    exp.add_argument("--private-checkout", required=True)
    exp.add_argument("--run-attempt", required=True)
    exp.add_argument("--packet-output", required=True)
    exp.add_argument("--mac-output", required=True)
    hist = sub.add_parser("export-owner-historical")
    hist.add_argument("--private-checkout", required=True)
    hist.add_argument("--packet-output", required=True)
    hist.add_argument("--mac-output", required=True)
    imp = sub.add_parser("admit-public")
    imp.add_argument("--production-db", required=True)
    args = p.parse_args(argv)
    try:
        if args.mode == "export-private":
            return export(args)
        if args.mode == "export-owner-historical":
            return export_historical(args)
        return admit(args)
    except (b.DAPABridgeHold, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, b.DAPABridgeHold) else "dapa_bridge_io_hold"
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_rows_written": 0,
                          "public_original_content_exported": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
