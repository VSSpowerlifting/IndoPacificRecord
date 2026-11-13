"""Sign (private custody) and admit (public Daily) Japan Coast Guard official-link parents.

A script rather than part of ``core.japan_jcg_links`` so that module
keeps no dependency on Daily intake: collectors that import it stay inside
their pinned import closure.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import japan_jcg_links as links             # noqa: E402
from processing.daily_intake import verified_source   # noqa: E402


def main(argv=None) -> int:
    """``sign`` runs beside private custody; ``admit`` runs in public Daily.

    Output is a JSON receipt of counts and reason codes. Neither command
    prints the key, an original or a title.
    """
    ap = argparse.ArgumentParser(description="Japan Coast Guard official-link parents")
    sub = ap.add_subparsers(dest="command", required=True)
    sign = sub.add_parser("sign")
    sign.add_argument("--source-checkout", required=True)
    sign.add_argument("--source-commit", required=True)
    sign.add_argument("--output", required=True)
    admit = sub.add_parser("admit")
    admit.add_argument("--database", required=True)
    admit.add_argument("--envelope", required=True)
    args = ap.parse_args(argv)
    key = os.environ.get(links.KEY_ENV, "")
    try:
        if args.command == "sign":
            from core import japan_jcg_rights
            records = links.with_title_hash(verified_source(
                args.source_checkout, args.source_commit, links.FAMILY))
            evidence = japan_jcg_rights.source_evidence(args.source_checkout, args.source_commit)
            envelope = links.sign_links(records, key=key, source_evidence=evidence)
            Path(args.output).write_text(json.dumps(envelope, sort_keys=True))
            receipt = {"signed_links": len(envelope["packet"]["links"]), "source_evidence": evidence}
        else:
            path = Path(args.envelope)
            if not path.exists():
                print(json.dumps({"status": "no_link_envelope_delivered"}))
                return 0
            if path.stat().st_size > links.MAX_ENVELOPE_BYTES:
                raise links.LinkRefused("jcg_link_envelope_too_large")
            envelope = json.loads(path.read_text())
            with sqlite3.connect(args.database, timeout=30) as conn:
                summary = links.admit_signed_links(conn, envelope, key=key)
            receipt = {"admitted": len(summary["admitted"]),
                       "unchanged": len(summary["unchanged"]),
                       "held": summary["held"], "refused": summary["refused"],
                       "source_evidence": envelope["packet"].get("source_evidence")}
    except (links.LinkRefused, ValueError) as exc:
        # IntakeHold is a ValueError: fixed reason codes only, never content.
        reason = str(exc) if isinstance(exc, links.LinkRefused) or type(exc).__name__ == "IntakeHold" \
            else "jcg_link_envelope_invalid"
        print(json.dumps({"status": "held", "reason": reason}))
        return 1
    print(json.dumps({"status": "ok", **receipt}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
