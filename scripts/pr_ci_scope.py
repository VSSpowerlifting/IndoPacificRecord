"""Fail-closed PR scope selection: small docs/timeline diffs avoid unrelated full CI.

This selects *which tests to execute*, not publisher/source permissions,
review authority, required deploy validation or production permissions.
Any unrecognised changed path triggers full CI.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess


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
        "git", "diff", "--name-only", "-z", "--no-renames",
        args.base, args.head, "--",
    ])
    paths = [s.decode("utf-8", "surrogateescape") for s in data.split(b"\0") if s]
    scope = classify(paths)
    print("PR files:", paths, flush=True)
    print("CI mode:", scope.mode, "browser:", scope.browser,
          "source_replay:", scope.source_replay, flush=True)
    with args.github_output.open("a", encoding="utf-8") as out:
        out.write("mode=" + scope.mode + "\n")
        out.write("browser=" + str(scope.browser).lower() + "\n")
        out.write("source_replay=" + str(scope.source_replay).lower() + "\n")


if __name__ == "__main__":
    main()
