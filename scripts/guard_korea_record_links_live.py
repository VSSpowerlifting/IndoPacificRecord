"""Hold a Korea-only Pages publication that would link Records not yet live.

The Korea writers publish only Korea pages (``korea.html``, ``korea-originals/``
and the official-link index) to Pages. Record pages ship only with the Daily's
full-site deploy. A Korea page may therefore go to Pages only when every
``record/N.html`` it links is already on the Pages branch.

This gate sits in each writer's Pages job, never before its main commit: the
main commit carries the release register the Daily needs to render the Record
at all, so holding it would hold forever. When held, Pages keeps its last-good
Korea pages; the next Daily deploys the Records and the Korea pages together,
after which the writer's Pages publication proceeds again.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Both forms used by the Korea pages: the desk links "record/N.html" and an
# exhibit links "../record/N.html".
LINK = re.compile(r'href="(?:\.\./)?(record/[0-9]+[.]html)"')
HOLD = "korea_record_page_not_live"
HELD_EXIT = 3


def linked_records(output: Path) -> set:
    """Every record route linked from the pages a Korea-only writer ships."""
    output = Path(output)
    pages = [output / "korea.html"]
    pages += sorted((output / "korea-originals").glob("*.html"))
    found = set()
    for page in pages:
        if page.is_file():
            found |= set(LINK.findall(page.read_text(encoding="utf-8")))
    return found


def _on_pages(pages_repo: Path, ref: str, route: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", "%s:%s" % (ref, route)],
        cwd=str(pages_repo), capture_output=True).returncode == 0


def missing(output: Path, pages_repo: Path, pages_ref: str = "HEAD") -> list:
    """Sorted linked record routes absent from ``pages_ref`` (fail closed)."""
    return [route for route in sorted(linked_records(output))
            if not _on_pages(Path(pages_repo), pages_ref, route)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default="output",
                        help="rendered site whose Korea pages would be published")
    parser.add_argument("--pages-repo", required=True,
                        help="checkout of the Pages branch, before any copy")
    parser.add_argument("--pages-ref", default="HEAD")
    args = parser.parse_args(argv)
    linked = linked_records(Path(args.output))
    gaps = missing(Path(args.output), Path(args.pages_repo), args.pages_ref)
    if gaps:
        print("HOLD %s: %d of %d linked Record page(s) are not yet on Pages. "
              "Pages keeps its last-good Korea pages; the Daily's full-site "
              "deploy publishes these Records with the Korea pages."
              % (HOLD, len(gaps), len(linked)))
        for route in gaps:
            print("  %s not on Pages" % route)
        return HELD_EXIT
    print("Korea Record links live on Pages: %d" % len(linked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
