"""Isolated production-equivalent render, as tests/test_archive_integration_browser.py does."""
import sys; from pathlib import Path
ROOT = Path.cwd(); sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'site/preview'))
import generate_preview as gp
out = Path(sys.argv[1])
gp.build(out, gp.PUBLIC_TITLE, ROOT / 'pla_watch.db', snapshot=gp.snapshot_from_corpus(ROOT / 'pla_watch.db'),
         legacy_routes=True, site_origin='https://indopacificrecord.org')
print('built', out)
