"""Tree-identity GitHub Pages release helper (the one shared Pages publisher).

Contract: the tree of ``gh-pages`` is exactly ``<source>:output`` for one
commit ``<source>`` reachable from ``main``.  A release therefore *is* the
statement "Pages now serves the committed ``output/`` of main commit S".
Provenance lives in the gh-pages commit message (``Source-SHA: <S>``), so no
file is added to the public site.

Rules, all evaluated against freshly fetched refs (never the job-start state):

* ``S`` must be reachable from ``origin/main`` (the default is its tip).
* The current Pages tip must itself be attributable: its tree must equal
  ``<previous-source>:output`` for the ``Source-SHA`` trailer, or, for a tip
  with no trailer (a legacy writer), for some recent commit on main.  A tip
  that matches nothing is out-of-band drift, so the release HOLDs.
* Monotonic: ``S`` must descend from the previous source.  A request that is
  an *ancestor* of what Pages already serves is SUPERSEDED (nothing to do:
  the newer generation contains it).  A divergent source HOLDs.
* If the trees already match nothing is pushed (idempotent retry).
* The commit is built with ``commit-tree`` from main's tree object, so
  ``.gitignore``, ``.gitattributes`` and symlink handling cannot silently drop
  or alter content, and the push is a plain fast-forward (compare-and-swap on
  the tip just read).  A rejected push is re-evaluated, never forced.

Without ``--push`` the command cannot mutate the remote.  Exit status: 0 =
published / already current / superseded / dry-run eligible, 3 = HOLD, 2 =
usage or git error.  A HOLD blocks *publication only*; it never touches
collection, ``main`` or the SQLite database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

TRAILER = "Source-SHA"
REQUIRED = ("index.html", "CNAME", ".nojekyll")
LEGACY_SEARCH_DEPTH = 2000
MAX_ATTEMPTS = 4
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TRAILER_RE = re.compile(r"^%s: ([0-9a-f]{40})\s*$" % TRAILER, re.MULTILINE)


class Hold(Exception):
    """Release eligibility failed closed (exit 3)."""


class GitError(Exception):
    """A git command failed (exit 2)."""


def _git(repo, *args, check=True, input_bytes=None, env=None):
    result = subprocess.run(["git", *args], cwd=str(repo), input=input_bytes,
                            capture_output=True, env=env)
    if check and result.returncode:
        # Do not echo stderr: it can embed remote URLs.
        raise GitError("git %s failed (%d)" % (args[0], result.returncode))
    return result


def _out(repo, *args, **kw):
    return _git(repo, *args, **kw).stdout.decode("utf-8", "strict").strip()


def _rev(repo, spec):
    result = _git(repo, "rev-parse", "--verify", "--quiet", spec + "^{commit}", check=False)
    out = result.stdout.decode().strip()
    return out if result.returncode == 0 and _SHA_RE.match(out) else None


def _is_ancestor(repo, older, newer):
    return _git(repo, "merge-base", "--is-ancestor", older, newer, check=False).returncode == 0


def _fetch(repo, remote, main_branch, pages_branch):
    if _out(repo, "rev-parse", "--is-shallow-repository") == "true":
        _git(repo, "fetch", "--no-tags", "--quiet", "--unshallow", remote)
    spec = "+refs/heads/%s:refs/remotes/%s/%s"
    _git(repo, "fetch", "--no-tags", "--quiet", remote, spec % (main_branch, remote, main_branch))
    pages_ref = "refs/remotes/%s/%s" % (remote, pages_branch)
    if _git(repo, "fetch", "--no-tags", "--quiet", remote, spec % (pages_branch, remote, pages_branch),
            check=False).returncode:
        # Missing or unreachable: never fall back to a stale tracking ref.
        _git(repo, "update-ref", "-d", pages_ref, check=False)


def _path_ok(path):
    p = PurePosixPath(path)
    return (bool(path) and not path.startswith("/") and str(p) == path
            and all(part not in (".", "..", "", ".git") for part in p.parts))


def _output_tree_oid(repo, commit):
    """Object id of ``commit:output`` if it is a tree, else None."""
    result = _git(repo, "rev-parse", "--verify", "--quiet", commit + ":output", check=False)
    oid = result.stdout.decode().strip()
    if result.returncode or not _SHA_RE.match(oid):
        return None
    kind = _git(repo, "cat-file", "-t", oid, check=False).stdout.decode().strip()
    return oid if kind == "tree" else None


def output_tree(repo, commit):
    """Return (tree_sha, entry_count) for ``commit:output`` after safety checks."""
    tree = _output_tree_oid(repo, commit)
    if not tree:
        raise Hold("source %s has no output/ tree" % commit[:12])
    raw = _git(repo, "ls-tree", "-r", "-z", tree).stdout
    names = set()
    count = 0
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, kind, _oid = meta.decode().split(" ")
        try:
            path = raw_path.decode("utf-8", "strict")
        except UnicodeDecodeError:
            raise Hold("output/ contains a non-UTF-8 path")
        if kind != "blob" or mode not in ("100644", "100755"):
            raise Hold("output/ contains an unsupported entry (symlink or submodule): %s" % path)
        if not _path_ok(path):
            raise Hold("output/ contains an unsafe path: %s" % path)
        names.add(path)
        count += 1
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise Hold("output/ is missing required Pages files: " + ", ".join(missing))
    return tree, count


def _tree_of(repo, commit):
    return _out(repo, "rev-parse", commit + "^{tree}")


def _attributed_source(repo, pages_tip, main_tip):
    """Return (source_sha, how) for the current Pages tip, or raise Hold."""
    pages_tree = _tree_of(repo, pages_tip)
    message = _out(repo, "log", "-1", "--format=%B", pages_tip)
    trailers = _TRAILER_RE.findall(message)
    if trailers:
        source = trailers[-1]
        if not _rev(repo, source):
            raise Hold("Pages names source %s, which is not in this repository" % source[:12])
        if _output_tree_oid(repo, source) != pages_tree:
            raise Hold("gh-pages tip %s no longer equals %s:output (out-of-band change)"
                       % (pages_tip[:12], source[:12]))
        return source, "trailer"
    # Legacy tip: attribute it to the newest main commit with an identical output tree.
    commits = _out(repo, "rev-list", "-n", str(LEGACY_SEARCH_DEPTH), main_tip).split()
    probe = "".join("%s:output\n" % c for c in commits).encode()
    checked = _git(repo, "cat-file", "--batch-check", input_bytes=probe).stdout.decode().splitlines()
    for commit, line in zip(commits, checked):
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "tree" and parts[0] == pages_tree:
            return commit, "legacy-tree-match"
    raise Hold("gh-pages tip %s has no Source-SHA trailer and matches no recent main:output"
               % pages_tip[:12])


def evaluate(repo, remote, main_branch, pages_branch, source=None):
    """Decide what a release would do against the *current* remote refs."""
    _fetch(repo, remote, main_branch, pages_branch)
    main_tip = _rev(repo, "refs/remotes/%s/%s" % (remote, main_branch))
    pages_tip = _rev(repo, "refs/remotes/%s/%s" % (remote, pages_branch))
    if not main_tip:
        raise Hold("cannot resolve %s/%s" % (remote, main_branch))
    if not pages_tip:
        raise Hold("cannot resolve %s/%s; bootstrapping a Pages branch is out of scope"
                   % (remote, pages_branch))
    src = _rev(repo, source) if source else main_tip
    if not src:
        raise Hold("cannot resolve source %s" % source)
    if not _is_ancestor(repo, src, main_tip):
        raise Hold("source %s is not on %s: only committed main output may be released"
                   % (src[:12], main_branch))
    src_tree, entries = output_tree(repo, src)
    plan = {"source": src, "main_tip": main_tip, "pages_tip": pages_tip,
            "tree": src_tree, "entries": entries}
    if _tree_of(repo, pages_tip) == src_tree:
        plan.update(action="current", detail="Pages already serves this exact tree")
        return plan
    prev, how = _attributed_source(repo, pages_tip, main_tip)
    plan.update(previous_source=prev, attribution=how)
    if not _is_ancestor(repo, prev, main_tip):
        raise Hold("Pages source %s is not on %s" % (prev[:12], main_branch))
    if _is_ancestor(repo, src, prev):
        plan.update(action="superseded",
                    detail="Pages already serves a newer generation (%s)" % prev[:12])
        return plan
    if not _is_ancestor(repo, prev, src):
        raise Hold("source %s and Pages source %s have diverged" % (src[:12], prev[:12]))
    plan.update(action="publish", detail="fast-forward Pages %s -> %s" % (prev[:12], src[:12]))
    return plan


def _commit(repo, plan, writer):
    env = dict(os.environ)
    for key, value in (("GIT_AUTHOR_NAME", "github-actions[bot]"),
                       ("GIT_COMMITTER_NAME", "github-actions[bot]"),
                       ("GIT_AUTHOR_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com"),
                       ("GIT_COMMITTER_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com")):
        env.setdefault(key, value)
    message = ("Deploy %s\n\n%s: %s\nPrevious-Pages-SHA: %s\nReleased-By: %s\n"
               % (plan["source"][:12], TRAILER, plan["source"], plan["pages_tip"], writer))
    return _out(repo, "commit-tree", plan["tree"], "-p", plan["pages_tip"], "-m", message, env=env)


def release(repo, *, remote="origin", main_branch="main", pages_branch="gh-pages",
            source=None, push=False, writer="manual"):
    """Evaluate and (with ``push=True``) publish. Returns a JSON-able report."""
    repo = Path(repo)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        plan = evaluate(repo, remote, main_branch, pages_branch, source)
        plan.update(published=False, pushed=push, attempt=attempt, writer=writer)
        if plan["action"] != "publish" or not push:
            return plan
        commit = _commit(repo, plan, writer)
        result = _git(repo, "push", "--quiet", remote,
                      "%s:refs/heads/%s" % (commit, pages_branch), check=False)
        if result.returncode == 0:
            plan.update(published=True, pages_commit=commit)
            return plan
        # Rejected non-fast-forward: someone published first. Re-read and re-decide.
    raise Hold("Pages moved on every attempt; not forcing (%d attempts)" % MAX_ATTEMPTS)


def _github_output(action):
    """Expose the decision to later workflow steps (no-op outside Actions)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("action=%s\n" % action)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".", help="checkout with the remote configured")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--main-branch", default="main")
    ap.add_argument("--pages-branch", default="gh-pages")
    ap.add_argument("--source", help="main commit to release (default: fetched main tip)")
    ap.add_argument("--writer", default=os.environ.get("GITHUB_WORKFLOW", "manual"),
                    help="label recorded in the release commit")
    ap.add_argument("--push", action="store_true",
                    help="actually publish; without it the remote is never written")
    args = ap.parse_args(argv)
    try:
        report = release(args.repo, remote=args.remote, main_branch=args.main_branch,
                         pages_branch=args.pages_branch, source=args.source,
                         push=args.push, writer=args.writer)
    except Hold as exc:
        _github_output("hold")
        print(json.dumps({"action": "hold", "reason": str(exc)}, sort_keys=True))
        print("HOLD: %s" % exc, file=sys.stderr)
        return 3
    except GitError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    _github_output(report["action"])
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
