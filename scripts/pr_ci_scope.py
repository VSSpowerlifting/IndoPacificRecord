"""Fail-closed PR scope selection: small docs/timeline/editorial diffs avoid unrelated full CI.

This selects *which tests to execute*, not publisher/source permissions,
review authority, required deploy validation or production permissions.
Any unrecognised changed path triggers full CI.

The editorial lane admits only governed Brief content and approved
presentation assets (canonical Brief JSON, presentation manifests, the
author registry, admitted photos and their manifests, evidence receipts)
as plain added/modified regular files. Its tests and checks are chosen by
the workflow; it never yields the "full" mode that trusted qualification
reuse requires, so main-push full CI remains the code backstop.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


# Only source-neutral Markdown is docs-only. A new data file, schema, policy
# implementation, workflow or executable at any path is always full CI.
ROOT_DOCS = {
    "AGENTS.md", "CLAUDE.md", "PROJECT_STATE.md", "DECISION_LOG.md",
    "EDITORIAL_QA_CHECKLIST.md", "README.md", "CONTRIBUTING.md",
}
TIMELINE_PRESENTATION = {
    "site/preview/timelines.css",
    "site/preview/templates/timeline.html",
    "site/preview/templates/_timeline_macros.html",
}
TIMELINE_ASSET_PREFIX = "site/assets/timelines/"

IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
# (directory, allowed suffixes). Files must sit directly in the directory,
# except evidence receipts, which live one folder deep under docs/evidence/.
EDITORIAL_DIRS = (
    ("briefs", {".json"}),                       # canonical Brief manuscripts
    ("briefs/presentation", {".json"}),          # rendered-presentation manifests
    ("briefs/media", IMAGE | {".json"}),         # Brief-owned media + sidecars
    ("site/assets/catalogue/media", IMAGE),      # admitted catalogue photos
    ("site/assets/editorial", IMAGE),            # editorial masters
    ("site/assets/editorial/derivatives", IMAGE),
)
EDITORIAL_FILES = {
    "site/assets/catalogue/admissions.json",     # image admissions
    "site/assets/editorial/manifest.json",       # editorial image manifest
    "site/preview/staff.json",                   # author identities / credits
}
EVIDENCE_PREFIX = "docs/evidence/"
EVIDENCE_SUFFIXES = IMAGE | {".md", ".json"}

# The editorial lane's test modules (fnmatch patterns over dotted module
# names). Every test module that reads a governed editorial input, plus the
# real-browser suites that render Brief pages. A contract test re-derives the
# readers from tests/ so a new reader cannot silently fall outside this set;
# each pattern must match at least one discovered module or the lane fails.
EDITORIAL_TEST_PATTERNS = (
    "tests.test_brief_*",
    "tests.test_briefs_*",
    "tests.test_ipr_briefs",
    "tests.test_archive_integration",
    "tests.test_article_media",
    "tests.test_catalogue_media",
    "tests.test_china_active_retirement",
    "tests.test_cited_source_records",
    "tests.test_coastal_palette",
    "tests.test_desks_p4a_release_contract",
    "tests.test_dossier_rendering",
    "tests.test_editorial_staff",
    "tests.test_frontend_production",
    "tests.test_historical_brief_shell",
    "tests.test_home_briefs_band_veil",
    "tests.test_home_paired_records",
    "tests.test_indo_pacific_identity",
    "tests.test_korea_output_release_scope",
    "tests.test_pla_watch_authoring_identity",
    "tests.test_pla_watch_reading_ergonomics",
    "tests.test_pla_watch_veil_contrast",
    "tests.test_preview_prototype",
    "tests.test_public_chrome_is_truthful",
    "tests.test_public_editorial_render_gate",
    "tests.test_public_editorial_research",
    "tests.test_relief_primitives",
    "tests.test_site_mode_contract",
    "tests.test_sitewide_render_preview",
    "tests.test_timeline_rendering",
    "tests.test_timelines",
)


@dataclass(frozen=True)
class Scope:
    mode: str
    browser: bool
    source_replay: bool


def is_doc(path: str) -> bool:
    return path in ROOT_DOCS or (path.startswith("docs/") and path.endswith(".md"))


def is_timeline_presentation(path: str) -> bool:
    if path in TIMELINE_PRESENTATION:
        return True
    return (
        path.startswith(TIMELINE_ASSET_PREFIX)
        and Path(path).suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".svg"}
    )


def is_editorial(path: str) -> bool:
    if path in EDITORIAL_FILES:
        return True
    parent, _, name = path.rpartition("/")
    suffix = Path(name).suffix.lower()
    if not name or name.startswith("."):
        return False
    if any(parent == d and suffix in allowed for d, allowed in EDITORIAL_DIRS):
        return True
    if path.startswith(EVIDENCE_PREFIX):
        rest = path[len(EVIDENCE_PREFIX):].split("/")
        return len(rest) == 2 and suffix in EVIDENCE_SUFFIXES
    return False


def needs_replay(path: str) -> bool:
    return (
        path.startswith("research/topic_pilot_v1/")
        or path.startswith("tests/test_topic_pilot")
        or path.startswith("scripts/topic_pilot")
    )


def classify(paths: list[str]) -> Scope:
    # No diff, invalid path, directories, binary and unknown file types fail
    # closed to full suite. No untrusted filename is ever executed.
    if not paths or any(
        not p or p.startswith("/") or "\\" in p or
        ".." in p.split("/") or p.endswith("/") for p in paths
    ):
        return Scope("full", True, True)
    if all(is_doc(p) for p in paths):
        return Scope("docs", False, False)
    if all(is_doc(p) or is_timeline_presentation(p) for p in paths):
        return Scope("focused", True, False)
    return Scope("full", True, any(needs_replay(p) for p in paths))


@dataclass(frozen=True)
class Entry:
    """One ``git diff --raw`` record: modes, status letter and path."""
    old_mode: str
    new_mode: str
    status: str
    path: str


def parse_raw(data: bytes) -> list[Entry]:
    # -z --raw --no-renames: ":<old> <new> <oldsha> <newsha> <status>\0<path>\0"
    fields = data.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    if len(fields) % 2:
        raise ValueError("malformed raw diff")
    entries = []
    for meta, path in zip(fields[0::2], fields[1::2]):
        parts = meta.decode("ascii").split(" ")
        if len(parts) != 5 or not parts[0].startswith(":"):
            raise ValueError("malformed raw diff record: %r" % meta)
        entries.append(Entry(parts[0][1:], parts[1], parts[4],
                             path.decode("utf-8", "surrogateescape")))
    return entries


def safe_entry(e: Entry) -> bool:
    # Only plain additions/modifications of regular non-executable files may
    # enter any reduced lane (docs, focused, editorial). Deletions, type
    # changes, symlinks, submodules and executables are full, whatever the path.
    return (
        e.new_mode == "100644"
        and ((e.status == "A" and e.old_mode == "000000")
             or (e.status == "M" and e.old_mode == "100644"))
    )


def editorial_entry(e: Entry) -> bool:
    return is_editorial(e.path) and safe_entry(e)


def require_safe_entries(scope: Scope, entries: list[Entry]) -> Scope:
    # "full" and the main-push "data" verdict pass through; any reduced lane
    # holding an unsafe entry becomes full (replay flag from the path scope).
    if scope.mode in ("full", "data") or all(safe_entry(e) for e in entries):
        return scope
    return Scope("full", True, scope.source_replay)


def classify_entries(entries: list[Entry]) -> Scope:
    scope = classify([e.path for e in entries])
    if scope.mode != "full":
        return require_safe_entries(scope, entries)
    if scope.source_replay:
        return scope
    if (any(editorial_entry(e) for e in entries)
            and all(editorial_entry(e) or (is_doc(e.path) and safe_entry(e))
                    for e in entries)):
        return Scope("editorial", True, False)
    return scope


def main_push_scope(root: Path, base: str, head: str, paths: list[str]) -> Scope:
    # Only the workflow's authenticated main-push event uses the data lane.
    # Compare modes/types/blob maps too: a .db symlink or executable HTML is
    # an input change, never mutable data. Unknown paths stay fail-closed.
    from scripts.code_qualification import Git
    git = Git(root)
    if git.inputs(base) == git.inputs(head):
        return Scope("data", False, False)
    return classify(paths)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD^1")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--github-output", type=Path, required=True)
    args = ap.parse_args()
    # Checkout must be the synthetic PR merge: HEAD^1 is the current base.
    # If shallow checkout or Git itself is broken, fail rather than silently
    # assigning an inaccurately small test scope.
    data = subprocess.check_output([
        "git", "diff", "--raw", "-z", "--no-renames", "--no-abbrev",
        args.base, args.head, "--",
    ])
    entries = parse_raw(data)
    paths = [e.path for e in entries]
    scope = classify_entries(entries)
    if os.environ.get("GITHUB_EVENT_NAME") == "push" and os.environ.get("GITHUB_REF") == "refs/heads/main":
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        scope = require_safe_entries(
            main_push_scope(Path.cwd(), args.base, args.head, paths), entries)
    print("PR files:", paths, flush=True)
    print("CI mode:", scope.mode, "browser:", scope.browser,
          "source_replay:", scope.source_replay, flush=True)
    with args.github_output.open("a", encoding="utf-8") as out:
        out.write("mode=" + scope.mode + "\n")
        out.write("browser=" + str(scope.browser).lower() + "\n")
        out.write("source_replay=" + str(scope.source_replay).lower() + "\n")


if __name__ == "__main__":
    main()
