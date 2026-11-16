"""Attested GitHub Pages release helper (the one shared Pages publisher, #346).

Every write to ``gh-pages`` goes through this helper. Each release commit
carries, in its message, the complete *attested state* of the site it
publishes, and the helper refuses to build on any tip whose tree does not
equal the tree that state describes.

Attested state
--------------
A state is one **base** main commit ``B`` and an ordered list of zero or more
**overlays** ``(S, path)``::

    Source-SHA: <B>            the last full release; tree starts as B:output
    Overlay: <S> <path>        then path (a file or directory) is replaced by
                               S:output's entries at path (absent = deleted)

The expected tree is ``B:output`` with every overlay applied in order. A tip
is *attributable* when its tree equals its own state's expected tree (any
out-of-band change is then visible as a mismatch and HOLDs). A tip without a
``Source-SHA`` line is a legacy writer's commit: it is attributable only if its
tree equals ``C:output`` for some recent main commit ``C`` (state ``(C, [])``).
No file is added to the public site; provenance lives in the gh-pages history.

Release kinds (all sources must be reachable from freshly fetched main)
-----------------------------------------------------------------------
* **full** ``--source S``: publishes ``S:output``.
  ``S`` an ancestor of ``B`` -> SUPERSEDED (Pages already serves a newer
  generation; nothing is pushed). ``B`` an ancestor of ``S`` -> new state is
  ``(S, overlays newer than S)``: overlays whose source ``S`` already contains
  are dropped, overlays from newer main commits are re-applied so a file-only
  release that landed after ``S`` was rendered is never erased. Divergence
  HOLDs.
* **overlay** ``--source S --overlay PATH...``: a file-only release. Only the
  named paths change; every other Pages file is preserved byte for byte. ``B``
  must be an ancestor of ``S``; a newer overlay of the same path makes it
  SUPERSEDED; a partial or divergent overlap HOLDs.
* **reconcile** ``--reconcile --expect-pages TIP``: the operator-authorized
  way out of a HOLD on an unattributable tip. It requires the exact current
  Pages tip (compare-and-swap), publishes the current main tip's ``output/`` as
  a new base and records the replaced tip. It is never automatic.

Rollback is always forward: revert on main, then release normally. A request
for an older source never overwrites a newer one. Publishing is a non-force
fast-forward from the tip just read, so a concurrent writer makes the push fail
and the decision is re-evaluated against the new tip (``MAX_ATTEMPTS``).

Credentials: a checkout that persists credentials needs nothing more. Otherwise
pass the Actions token as ``PAGES_RELEASE_TOKEN``; it is applied to this
process's fetch/push only (``GIT_CONFIG_*``), never written to ``.git/config``.

Exit status: 0 = published / current / superseded / dry-run, 3 = HOLD,
2 = usage or git error. Without ``--push`` the remote is never written. A HOLD
blocks publication only; it never touches collection, ``main`` or the SQLite
database. Stdlib only; Python 3.9 compatible.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

TRAILER = "Source-SHA"
OVERLAY = "Overlay"
REQUIRED = ("index.html", "CNAME", ".nojekyll")
# A domain is held by one Pages site at a time; the predecessor domain is a
# separate redirect-only site. Every release must keep naming this one.
EXPECTED_CNAME = "indopacificrecord.org"
LEGACY_SEARCH_DEPTH = 2000
MAX_ATTEMPTS = 4
MAX_OVERLAYS = 400
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TRAILER_RE = re.compile(r"^%s: ([0-9a-f]{40})\s*$" % TRAILER, re.MULTILINE)
_OVERLAY_RE = re.compile(r"^%s: ([0-9a-f]{40}) (\S.*?)\s*$" % OVERLAY, re.MULTILINE)
_RESERVED_LINE = re.compile(r"^(%s|%s|Release-Kind|Released-Source-SHA|Previous-Pages-SHA|"
                            r"Released-By|Reconciled-Pages-SHA):" % (TRAILER, OVERLAY))
_BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


class Hold(Exception):
    """Release eligibility failed closed (exit 3)."""


class GitError(Exception):
    """A git command failed (exit 2)."""


TOKEN_ENV = "PAGES_RELEASE_TOKEN"


def _auth_env(env):
    """Scope an Actions token to this process's fetch/push (never .git/config)."""
    token = os.environ.get(TOKEN_ENV)
    if not token:
        return env
    env = dict(os.environ if env is None else env)
    env.pop(TOKEN_ENV, None)
    basic = base64.b64encode(("x-access-token:" + token).encode()).decode()
    count = int(env.get("GIT_CONFIG_COUNT", "0") or 0)
    env.update({"GIT_CONFIG_COUNT": str(count + 1),
                "GIT_CONFIG_KEY_%d" % count: "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_%d" % count: "AUTHORIZATION: basic " + basic})
    return env


def _git(repo, *args, check=True, input_bytes=None, env=None):
    if args and args[0] in ("fetch", "push"):
        env = _auth_env(env)
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
            and not any(ord(c) < 32 or c == "\x7f" for c in path)
            and all(part not in (".", "..", "", ".git") for part in p.parts))


def _under(path, prefix):
    """True when ``path`` is ``prefix`` itself or inside directory ``prefix``."""
    return path == prefix or path.startswith(prefix + "/")


def _overlaps(a, b):
    return _under(a, b) or _under(b, a)


# ── Tree reading and assembly ───────────────────────────────────────────────
class Trees:
    """Per-run cache of ``commit:output`` listings (path -> (mode, oid))."""

    def __init__(self, repo):
        self.repo = repo
        self._cache = {}

    def output_oid(self, commit):
        result = _git(self.repo, "rev-parse", "--verify", "--quiet", commit + ":output", check=False)
        oid = result.stdout.decode().strip()
        if result.returncode or not _SHA_RE.match(oid):
            return None
        kind = _git(self.repo, "cat-file", "-t", oid, check=False).stdout.decode().strip()
        return oid if kind == "tree" else None

    def entries(self, tree_oid):
        if tree_oid in self._cache:
            return self._cache[tree_oid]
        raw = _git(self.repo, "ls-tree", "-r", "-z", tree_oid).stdout
        found = {}
        for entry in raw.split(b"\0"):
            if not entry:
                continue
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split(" ")
            try:
                path = raw_path.decode("utf-8", "strict")
            except UnicodeDecodeError:
                raise Hold("tree contains a non-UTF-8 path")
            if kind != "blob" or mode not in ("100644", "100755"):
                raise Hold("tree contains an unsupported entry (symlink or submodule): %s" % path)
            if not _path_ok(path):
                raise Hold("tree contains an unsafe path: %s" % path)
            found[path] = (mode, oid)
        self._cache[tree_oid] = found
        return found

    def output(self, commit):
        oid = self.output_oid(commit)
        if not oid:
            raise Hold("source %s has no output/ tree" % commit[:12])
        return oid, self.entries(oid)

    def build(self, entries):
        """Write ``entries`` as a tree object and return its id."""
        handle, index = tempfile.mkstemp(prefix="pages-release-index-")
        os.close(handle)
        os.unlink(index)
        env = dict(os.environ, GIT_INDEX_FILE=index)
        try:
            _git(self.repo, "read-tree", "--empty", env=env)
            records = b"".join(("%s %s\t%s" % (mode, oid, path)).encode("utf-8") + b"\0"
                               for path, (mode, oid) in sorted(entries.items()))
            _git(self.repo, "update-index", "-z", "--index-info", input_bytes=records, env=env)
            return _out(self.repo, "write-tree", env=env)
        finally:
            if os.path.exists(index):
                os.unlink(index)


def _apply_overlay(entries, source_entries, path):
    out = {p: v for p, v in entries.items() if not _under(p, path)}
    out.update({p: v for p, v in source_entries.items() if _under(p, path)})
    return out


def assemble(trees, base, overlays):
    """Entries of the state ``(base, overlays)``."""
    _, entries = trees.output(base)
    for source, path in overlays:
        _, src = trees.output(source)
        entries = _apply_overlay(entries, src, path)
    return entries


def _require_site(repo, entries):
    missing = [name for name in REQUIRED if name not in entries]
    if missing:
        raise Hold("assembled Pages tree is missing required files: " + ", ".join(missing))
    cname = _git(repo, "cat-file", "blob", entries["CNAME"][1]).stdout
    if cname.decode("utf-8", "replace").strip() != EXPECTED_CNAME:
        raise Hold("assembled Pages CNAME is not %s" % EXPECTED_CNAME)


def _tree_of(repo, commit):
    return _out(repo, "rev-parse", commit + "^{tree}")


# ── State ───────────────────────────────────────────────────────────────────
def parse_state(message):
    """Return ``(base, overlays)`` from a release commit message, or (None, [])."""
    bases = _TRAILER_RE.findall(message)
    overlays = [(sha, path) for sha, path in _OVERLAY_RE.findall(message)]
    return (bases[-1] if bases else None), overlays


ATTESTED_SEARCH_DEPTH = 500


def _attested_floor(repo, pages_tip):
    """Newest attested release under a trailer-less tip: ``(sha, base, overlays)``.

    ``None`` before the first attested release (bootstrap: any legacy tree
    match is accepted as the base).
    """
    log = _out(repo, "log", "--first-parent", "-n", str(ATTESTED_SEARCH_DEPTH),
               "--format=%H%x1f%B%x1e", pages_tip)
    for record in log.split("\x1e"):
        if "\x1f" not in record:
            continue
        sha, message = record.strip("\n").split("\x1f", 1)
        if re.search(r"(?m)^Release-Kind: ", message):
            base, overlays = parse_state(message)
            if base:
                return sha, base, overlays
    return None


def attribute(repo, trees, pages_tip, main_tip):
    """Return ``(base, overlays, how)`` for the current Pages tip, or raise Hold."""
    pages_tree = _tree_of(repo, pages_tip)
    message = _out(repo, "log", "-1", "--format=%B", pages_tip)
    base, overlays = parse_state(message)
    if base:
        for sha in [base] + [s for s, _ in overlays]:
            if not _rev(repo, sha):
                raise Hold("Pages names source %s, which is not in this repository" % sha[:12])
            if not _is_ancestor(repo, sha, main_tip):
                raise Hold("Pages source %s is not on main" % sha[:12])
        for _, path in overlays:
            if not _path_ok(path):
                raise Hold("Pages records an unsafe overlay path")
        expected = trees.build(assemble(trees, base, overlays))
        if expected != pages_tree:
            raise Hold("gh-pages tip %s does not equal its attested state (out-of-band change); "
                       "review, then reconcile with --reconcile --expect-pages %s"
                       % (pages_tip[:12], pages_tip))
        return base, overlays, "attested"
    # Legacy tip: attribute it to the newest main commit with an identical output tree.
    floor = _attested_floor(repo, pages_tip)
    commits = _out(repo, "rev-list", "-n", str(LEGACY_SEARCH_DEPTH), main_tip).split()
    probe = "".join("%s:output\n" % c for c in commits).encode()
    checked = _git(repo, "cat-file", "--batch-check", input_bytes=probe).stdout.decode().splitlines()
    for commit, line in zip(commits, checked):
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "tree" and parts[0] == pages_tree:
            if floor is None or all(_is_ancestor(repo, sha, commit)
                                    for sha in [floor[1]] + [o for o, _ in floor[2]]):
                return commit, [], "legacy-tree-match"
            # A trailer-less push of an OLDER generation after attested
            # releases began (e.g. a legacy run still in flight at cutover).
            # Accepting it would reset the attested high-water mark and
            # re-enable a rollback or the erasure of a newer file-only
            # release. Keep the last attested state; the next release
            # restores it over the stale push (no unique content is lost:
            # the push equals an older committed main:output).
            floor_sha, base, overlays = floor
            if trees.build(assemble(trees, base, overlays)) != _tree_of(repo, floor_sha):
                raise Hold("attested gh-pages commit %s does not equal its state" % floor_sha[:12])
            return base, overlays, "stale-legacy-over-attested"
    raise Hold("gh-pages tip %s has no Source-SHA trailer and matches no recent main:output; "
               "review, then reconcile with --reconcile --expect-pages %s"
               % (pages_tip[:12], pages_tip))


def _delta(old, new, limit=40):
    added = sorted(p for p in new if p not in old)
    removed = sorted(p for p in old if p not in new)
    changed = sorted(p for p in new if p in old and new[p] != old[p])
    return {"added": len(added), "removed": len(removed), "changed": len(changed),
            "paths": (["+" + p for p in added] + ["-" + p for p in removed]
                      + ["~" + p for p in changed])[:limit]}


def _plan_full(repo, src, base, overlays):
    if src == base and not overlays:
        return (base, overlays), None  # exactly what Pages serves: current
    if _is_ancestor(repo, src, base):
        return None, "Pages already serves base %s, which contains %s" % (base[:12], src[:12])
    if not _is_ancestor(repo, base, src):
        raise Hold("source %s and Pages base %s have diverged" % (src[:12], base[:12]))
    kept = []
    for source, path in overlays:
        if _is_ancestor(repo, source, src):
            continue  # src's own output already holds this or a newer version
        if not _is_ancestor(repo, src, source):
            raise Hold("overlay %s (%s) and source %s have diverged" % (source[:12], path, src[:12]))
        kept.append((source, path))  # newer file-only release: re-apply, never erase
    return (src, kept), None


def _plan_overlay(repo, src, paths, base, overlays):
    if _is_ancestor(repo, src, base):
        return None, "Pages base %s already contains %s" % (base[:12], src[:12])
    if not _is_ancestor(repo, base, src):
        raise Hold("source %s and Pages base %s have diverged" % (src[:12], base[:12]))
    covered = set()
    for source, existing in overlays:
        hits = [p for p in paths if _overlaps(p, existing)]
        if not hits or _is_ancestor(repo, source, src):
            continue
        if not _is_ancestor(repo, src, source):
            raise Hold("overlay %s (%s) and source %s have diverged"
                       % (source[:12], existing, src[:12]))
        partial = [p for p in hits if not _under(p, existing)]
        if partial:
            raise Hold("a newer release (%s) of %s is live; rerun from current main"
                       % (source[:12], existing))
        covered.update(hits)
    if covered and covered == set(paths):
        return None, "a newer release of every requested path is already live"
    if covered:
        raise Hold("a newer release covers only part of the request; rerun from current main")
    remaining = [(s, q) for s, q in overlays if not any(_under(q, p) for p in paths)]
    new = remaining + [(src, p) for p in paths]
    if len(new) > MAX_OVERLAYS:
        raise Hold("too many overlays since the last full release; run a full release")
    return (base, new), None


def evaluate(repo, remote, main_branch, pages_branch, source=None, overlay=None,
             reconcile_expect=None):
    """Decide what a release would do against the *current* remote refs."""
    repo = Path(repo)
    trees = Trees(repo)
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
    paths = list(dict.fromkeys(overlay or []))
    for path in paths:
        if not _path_ok(path) or path in REQUIRED:
            raise Hold("overlay path %r is not a releasable path" % path)
    trees.output(src)  # safety checks on the requested source
    pages_tree = _tree_of(repo, pages_tip)
    pages_entries = trees.entries(pages_tree) if reconcile_expect else None
    kind = "overlay" if paths else "full"
    plan = {"source": src, "main_tip": main_tip, "pages_tip": pages_tip, "kind": kind,
            "overlay_paths": paths}
    if reconcile_expect:
        kind = plan["kind"] = "reconcile"
        if paths:
            raise Hold("--reconcile publishes the full main output; do not pass --overlay")
        if reconcile_expect != pages_tip:
            raise Hold("Pages tip is %s, not the reviewed %s; review again" % (pages_tip, reconcile_expect))
        if src != main_tip:
            raise Hold("--reconcile releases only the current main tip")
        new_state = (src, [])
        plan.update(previous_state=None, attribution="operator-reconcile")
    else:
        base, overlays, how = attribute(repo, trees, pages_tip, main_tip)
        plan.update(previous_state={"base": base, "overlays": overlays}, attribution=how,
                    previous_source=base)
        if paths:
            new_state, why = _plan_overlay(repo, src, paths, base, overlays)
        else:
            new_state, why = _plan_full(repo, src, base, overlays)
        if how == "stale-legacy-over-attested" and (new_state is None
                                                    or new_state == (base, overlays)):
            # Pages serves a stale unattested generation: restore the last
            # attested state instead of reporting success over a rollback.
            new_state, why = (base, overlays), None
        if new_state is None:
            action = "superseded"
            if paths:
                _, src_entries = trees.output(src)
                live = trees.entries(pages_tree)
                if all({q: v for q, v in live.items() if _under(q, p)}
                       == {q: v for q, v in src_entries.items() if _under(q, p)} for p in paths):
                    action, why = "current", "Pages already serves these files"
            plan.update(action=action, detail=why, tree=pages_tree)
            return plan
        if new_state == (base, overlays) and how != "stale-legacy-over-attested":
            plan.update(action="current", detail="Pages already serves this attested state",
                        tree=pages_tree)
            return plan
        pages_entries = trees.entries(pages_tree)
    entries = assemble(trees, *new_state)
    _require_site(repo, entries)
    tree = trees.build(entries)
    plan.update(state={"base": new_state[0], "overlays": new_state[1]}, tree=tree,
                entries=len(entries), delta=_delta(pages_entries, entries))
    if kind == "overlay" and tree == pages_tree:
        # Identical bytes: nothing to publish, and no attestation commit is made.
        plan.update(action="current", detail="Pages already serves these files")
        return plan
    plan.update(action="publish",
                detail="%s release %s -> %s" % (kind, pages_tip[:12], src[:12]))
    return plan


def _message(plan, writer, subject):
    state = plan["state"]
    subject = subject or "Deploy %s" % plan["source"][:12]
    lines = [subject, "", "Release-Kind: %s" % plan["kind"],
             "%s: %s" % (TRAILER, state["base"])]
    lines += ["%s: %s %s" % (OVERLAY, sha, path) for sha, path in state["overlays"]]
    lines += ["Released-Source-SHA: %s" % plan["source"],
              "Previous-Pages-SHA: %s" % plan["pages_tip"]]
    if plan["kind"] == "reconcile":
        lines.append("Reconciled-Pages-SHA: %s" % plan["pages_tip"])
    lines.append("Released-By: %s" % writer)
    return "\n".join(lines) + "\n"


def _commit(repo, plan, writer, subject=None):
    env = dict(os.environ)
    for key, value in (("GIT_AUTHOR_NAME", _BOT[0]), ("GIT_COMMITTER_NAME", _BOT[0]),
                       ("GIT_AUTHOR_EMAIL", _BOT[1]), ("GIT_COMMITTER_EMAIL", _BOT[1])):
        env.setdefault(key, value)
    return _out(repo, "commit-tree", plan["tree"], "-p", plan["pages_tip"],
                "-m", _message(plan, writer, subject), env=env)


def _check_subject(subject):
    if subject is None:
        return
    if not subject.strip() or "\n" in subject or "\r" in subject or _RESERVED_LINE.match(subject):
        raise Hold("--subject must be one non-empty line that is not a release trailer")


def release(repo, *, remote="origin", main_branch="main", pages_branch="gh-pages",
            source=None, overlay=None, push=False, writer="manual", subject=None,
            reconcile_expect=None):
    """Evaluate and (with ``push=True``) publish. Returns a JSON-able report."""
    repo = Path(repo)
    _check_subject(subject)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        plan = evaluate(repo, remote, main_branch, pages_branch, source, overlay, reconcile_expect)
        plan.update(published=False, pushed=push, attempt=attempt, writer=writer)
        if plan["action"] != "publish" or not push:
            return plan
        commit = _commit(repo, plan, writer, subject)
        result = _git(repo, "push", "--quiet", remote,
                      "%s:refs/heads/%s" % (commit, pages_branch), check=False)
        if result.returncode == 0:
            plan.update(published=True, pages_commit=commit)
            return plan
        if reconcile_expect:
            raise Hold("Pages moved during the reconcile; review the new tip")
        # Rejected (a concurrent writer moved Pages) or ambiguous: re-read and
        # re-decide. A push that actually landed is re-evaluated as current.
    raise Hold("Pages moved on every attempt; not forcing (%d attempts)" % MAX_ATTEMPTS)


def _github_output(report):
    """Expose the decision to later workflow steps (no-op outside Actions)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("action=%s\n" % report.get("action", "hold"))
            if report.get("pages_commit"):
                handle.write("pages_commit=%s\n" % report["pages_commit"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".", help="checkout with the remote configured")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--main-branch", default="main")
    ap.add_argument("--pages-branch", default="gh-pages")
    ap.add_argument("--source", help="main commit to release (default: fetched main tip)")
    ap.add_argument("--overlay", action="append", metavar="PATH",
                    help="file-only release of this Pages path (file or directory); repeatable")
    ap.add_argument("--subject", help="first line of the gh-pages commit message")
    ap.add_argument("--writer", default=os.environ.get("GITHUB_WORKFLOW", "manual"),
                    help="label recorded in the release commit")
    ap.add_argument("--reconcile", action="store_true",
                    help="operator-authorized: replace an unattributable tip with main:output")
    ap.add_argument("--expect-pages", help="exact reviewed Pages tip (required with --reconcile)")
    ap.add_argument("--push", action="store_true",
                    help="actually publish; without it the remote is never written")
    args = ap.parse_args(argv)
    if args.reconcile and not (args.expect_pages and _SHA_RE.match(args.expect_pages)):
        ap.error("--reconcile requires --expect-pages <40-character Pages tip>")
    if args.expect_pages and not args.reconcile:
        ap.error("--expect-pages is only used with --reconcile")
    try:
        report = release(args.repo, remote=args.remote, main_branch=args.main_branch,
                         pages_branch=args.pages_branch, source=args.source,
                         overlay=args.overlay, push=args.push, writer=args.writer,
                         subject=args.subject,
                         reconcile_expect=args.expect_pages if args.reconcile else None)
    except Hold as exc:
        _github_output({"action": "hold"})
        print(json.dumps({"action": "hold", "reason": str(exc)}, sort_keys=True))
        print("HOLD: %s" % exc, file=sys.stderr)
        return 3
    except GitError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    _github_output(report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
