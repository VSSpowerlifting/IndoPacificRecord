#!/usr/bin/env python3
"""Check, reconcile, read revision notes or privately preview a Living Dossier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.dossier_contract import read_dossier, dossier_content_digest
from core.dossiers import reconcile_dossier_sources, chronology_view, publication_holds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('check', 'ready', 'changes', 'preview'))
    parser.add_argument('path', type=Path)
    parser.add_argument('--db', type=Path, default=ROOT / 'pla_watch.db')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.path.parent.resolve() not in ((ROOT / 'dossiers').resolve(), (ROOT / 'dossiers/drafts').resolve()):
            raise ValueError('read a canonical dossier or dossiers/drafts revision')
        sc = read_dossier(args.path, args.path.parent)
        if args.operation == 'changes':
            print(json.dumps(sc['changes'], ensure_ascii=False, indent=2))
            return 0
        records = reconcile_dossier_sources(sc, args.db)
        chronology = chronology_view(sc, records)
        holds = publication_holds(sc)
        if args.operation == 'preview':
            if args.out is None:
                parser.error('preview requires --out to a new disposable external directory')
            from core.dossiers import validate_review_destination
            validate_review_destination(args.out)
            return subprocess.run([sys.executable, str(ROOT / 'site/render.py'),
                '--review-dossier', str(args.path.resolve()), '--db', str(args.db.resolve()),
                '--out', str(args.out)], cwd=ROOT).returncode
        print(json.dumps(dict(slug=sc['slug'], content_sha256=dossier_content_digest(sc),
            source_reconciled=True, records=sorted(records), chronology_entries=len(chronology),
            editorial_status=sc['editorial_status'], publication_ready=not holds,
            holds=holds), indent=2))
        return 1 if args.operation == 'ready' and holds else 0
    except (ValueError, OSError) as exc:
        print('dossier: %s' % exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
