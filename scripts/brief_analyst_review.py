"""Offline analyst packet/return/feedback preparation. No mail, model or release.

All outputs contain private working material and must be outside every Git
checkout. Input decisions are explicit trusted owner files, never fields read
from an analyst return. See docs/IPR_RESEARCH_ANALYST_HANDOFF.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.brief_analyst_packet import AnalystPacketRefused, build_packet, require
from core.brief_analyst_return import extract_docx, extract_memo
from core.brief_analyst_feedback import aggregate_feedback, reconcile_feedback


def _read(path, *, binary=False):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size <= 3_000_000,
            "input must be a bounded regular file, not a symlink")
    return p.read_bytes() if binary else p.read_text(encoding="utf-8")


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        require(k not in out, "duplicate JSON field")
        out[k] = v
    return out


def _json(path):
    return json.loads(_read(path), object_pairs_hook=_pairs)


def _private(path, payload):
    p = Path(path)
    require(p.parent.is_dir() and not p.is_symlink() and not p.exists(), "private output must be new with an existing parent")
    require(not any(parent.is_symlink() for parent in p.parents), "private output parents must not be symlinks")
    resolved = p.resolve()
    require(not any((parent / ".git").exists() for parent in resolved.parents),
            "private analyst artifacts must be outside every Git checkout/worktree")
    raw = payload if isinstance(payload, bytes) else (payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    packet = commands.add_parser("packet")
    packet.add_argument("--worksheet", required=True)
    packet.add_argument("--config", required=True, help="thesis/questions/sources/distribution/deadline JSON")
    packet.add_argument("--manifest-out", required=True)
    packet.add_argument("--docx-out", required=True)
    packet.add_argument("--brief-out", required=True)
    intake = commands.add_parser("intake")
    intake.add_argument("--manifest", required=True)
    returns = intake.add_mutually_exclusive_group(required=True)
    returns.add_argument("--docx")
    returns.add_argument("--memo")
    intake.add_argument("--out", required=True)
    decision = commands.add_parser("reconcile")
    decision.add_argument("--manifest", required=True)
    decision.add_argument("--returned", required=True)
    decision.add_argument("--revised-worksheet", required=True)
    decision.add_argument("--owner-decisions", required=True, help="separate trusted decisions + owner_review JSON")
    decision.add_argument("--out", required=True)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("receipts", nargs="+")
    aggregate.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "packet":
            config = _json(args.config)
            manifest, docx, brief = build_packet(_read(args.worksheet), **config)
            for path, content in ((args.manifest_out, manifest), (args.docx_out, docx), (args.brief_out, brief)):
                _private(path, content)
        elif args.command == "intake":
            manifest = _json(args.manifest)
            report = extract_docx(manifest, _read(args.docx, binary=True)) if args.docx else extract_memo(manifest, _json(args.memo))
            _private(args.out, report)
        elif args.command == "reconcile":
            config = _json(args.owner_decisions)
            report = reconcile_feedback(_json(args.manifest), _json(args.returned), _read(args.revised_worksheet), **config)
            _private(args.out, report)
        else:
            _private(args.out, aggregate_feedback([_json(path) for path in args.receipts]))
    except (AnalystPacketRefused, OSError, ValueError, TypeError, KeyError) as exc:
        # Error messages intentionally identify contracts, never manuscript text.
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print("Private offline review artifacts prepared. No email, model, approval, prompt change or publication.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
