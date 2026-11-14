"""Hermetic reproductions of gh-pages stale-deployment interleavings (#346).

Every repository here is a temporary local bare repo reached over file://.
Nothing touches GitHub, the network, production SQLite or real output/.

The publish primitives mirror the release mechanics in this repository:

* ``full_tree``: peaceiris/actions-gh-pages@v3 (373f7f26). It clones gh-pages
  at depth 1, runs ``git rm -r '*'`` unless keep_files, copies publish_dir,
  commits and runs a NON-force ``git push origin gh-pages``. It does not retry.
* ``file_only``: the korea/us/treasury/uscc/bis workflows. They check out
  gh-pages, copy one file, require ``origin/gh-pages`` to be unchanged, then
  push without force.

Tests named ``test_current_*`` CHARACTERIZE the legacy writers that have NOT
been migrated (peaceiris full-tree, file-only, overlay, out-of-band pushes),
including their unsafe outcomes. They pass because the hazard is real.

``HelperProtocol`` drives the real ``scripts/pages_release.py`` through its
CLI against the same sandbox and asserts that each hazard is refused or
recovered. Provenance is the ``Source-SHA`` trailer on the gh-pages commit.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "pages_release.py"
TRAILER = "Source-SHA"


class StaleRefused(Exception):
    """A guarded writer refused to publish."""


class GitSandbox:
    def __init__(self, root: Path):
        self.root = root
        self.origin = root / "origin.git"
        self.url = self.origin.as_uri()
        self.n = 0
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        GIT_TERMINAL_PROMPT="0", HOME=str(root), GIT_AUTHOR_DATE="2026-10-15T00:00:00Z",
                        GIT_COMMITTER_DATE="2026-10-15T00:00:00Z")
        self.git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))

    def git(self, cwd, *args):
        cmd = ["git", "-c", "user.name=sandbox", "-c", "user.email=sandbox@example.invalid",
               "-c", "commit.gpgsign=false", "-c", "protocol.file.allow=always", *args]
        return subprocess.run(cmd, cwd=cwd, env=self.env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def workdir(self, label):
        self.n += 1
        path = self.root / ("%02d-%s" % (self.n, label))
        return path

    # ── main branch ──
    def seed(self, files):
        work = self.workdir("seed")
        self.git(self.root, "clone", "-q", self.url, str(work))
        self.git(work, "checkout", "-q", "-b", "main")
        self._write(work / "output", files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "seed")
        self.git(work, "push", "-q", "origin", "main")
        self.git(work, "checkout", "-q", "--orphan", "gh-pages")
        self.git(work, "rm", "-r", "-q", "--cached", ".")
        for child in work.iterdir():
            if child.name != ".git":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        self._write(work, files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "initial pages")
        self.git(work, "push", "-q", "origin", "gh-pages")

    def checkout_main(self, label="job"):
        """actions/checkout of main at job start: a frozen snapshot."""
        work = self.workdir(label)
        self.git(self.root, "clone", "-q", "--branch", "main", self.url, str(work))
        return work

    def commit_main(self, files, label="writer"):
        work = self.checkout_main(label)
        self._write(work / "output", files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", "update " + ",".join(sorted(files)))
        self.git(work, "push", "-q", "origin", "HEAD:main")
        return work

    def main_sha(self):
        return self.git(self.origin, "rev-parse", "main")

    # ── gh-pages writers ──
    def full_tree(self, src_output, message="Deploy", keep_files=False, before_push=None,
                  extra=None):
        work = self.workdir("peaceiris")
        self.git(self.root, "clone", "-q", "--depth=1", "--single-branch", "--branch",
                 "gh-pages", self.url, str(work))
        if not keep_files:
            self.git(work, "rm", "-r", "-q", "--ignore-unmatch", "*")
        for path in sorted(Path(src_output).rglob("*")):
            if path.is_file():
                dest = work / path.relative_to(src_output)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
        if extra:
            self._write(work, extra)
        self.git(work, "add", "-A")
        if self.git(work, "status", "--porcelain"):
            self.git(work, "commit", "-q", "-m", message)
        if before_push:
            before_push()
        self.git(work, "push", "-q", "origin", "gh-pages")
        return work

    def file_only(self, src_file, name, message="file-only", before_push=None):
        work = self.workdir("file-only")
        self.git(self.root, "clone", "-q", "--branch", "gh-pages", self.url, str(work))
        old = self.git(work, "rev-parse", "HEAD")
        shutil.copyfile(src_file, work / name)
        self.git(work, "add", "--", name)
        staged = self.git(work, "diff", "--cached", "--name-only")
        if staged:
            self.git(work, "commit", "-q", "-m", message)
        if before_push:
            before_push()
        self.git(work, "fetch", "-q", "origin", "gh-pages")
        if self.git(work, "rev-parse", "origin/gh-pages") != old:
            raise StaleRefused("gh-pages moved; never overwrite a concurrent release")
        if staged:
            self.git(work, "push", "-q", "origin", "HEAD:gh-pages")

    def out_of_band(self, files, message="owner-local scoped push"):
        work = self.workdir("owner")
        self.git(self.root, "clone", "-q", "--branch", "gh-pages", self.url, str(work))
        self._write(work, files)
        self.git(work, "add", "-A")
        self.git(work, "commit", "-q", "-m", message)
        self.git(work, "push", "-q", "origin", "HEAD:gh-pages")

    # ── reads ──
    def pages(self, path):
        return self._show("gh-pages", path)

    def main(self, path):
        return self._show("main", "output/" + path)

    def pages_message(self):
        return self.git(self.origin, "log", "-1", "--format=%s", "gh-pages")

    def _show(self, ref, path):
        try:
            return self.git(self.origin, "show", "%s:%s" % (ref, path))
        except subprocess.CalledProcessError:
            return None

    @staticmethod
    def _write(base, files):
        for rel, body in files.items():
            dest = Path(base) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")


class RaceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.box = GitSandbox(self.tmp)
        self.box.seed({"index.html": "home v1", "korea.html": "korea v1",
                       "desks.html": "desks v1", "CNAME": "example.invalid\n",
                       ".nojekyll": ""})


class CurrentProtocol(RaceCase):
    def test_current_stale_full_tree_overwrites_newer_file_only_release(self):
        box = self.box
        a = box.checkout_main("A-daily")                      # A: job-start snapshot
        b = box.commit_main({"korea.html": "korea v2"}, "B-korea")
        box.file_only(b / "output" / "korea.html", "korea.html")
        self.assertEqual(box.pages("korea.html"), "korea v2")
        box.full_tree(a / "output", "Deploy: 1001")           # A publishes later
        self.assertEqual(box.pages("korea.html"), "korea v1")  # B was rolled back
        self.assertEqual(box.main("korea.html"), "korea v2")   # main still has B

    def test_current_parent_cas_only_covers_clone_to_push_window(self):
        box = self.box
        fresh = box.checkout_main("A")
        mover = box.commit_main({"desks.html": "desks v2"}, "B")

        def concurrent():
            box.file_only(mover / "output" / "desks.html", "desks.html")

        with self.assertRaises(subprocess.CalledProcessError):
            box.full_tree(fresh / "output", before_push=concurrent)
        self.assertEqual(box.pages("desks.html"), "desks v2")
        # The same stale tree, re-cloned a moment later, publishes cleanly.
        box.full_tree(fresh / "output")
        self.assertEqual(box.pages("desks.html"), "desks v1")

    def test_current_file_only_cas_refuses_when_pages_moved(self):
        box = self.box
        b = box.commit_main({"korea.html": "korea v2"}, "B")
        with self.assertRaises(StaleRefused):
            box.file_only(b / "output" / "korea.html", "korea.html",
                          before_push=lambda: box.out_of_band({"other.html": "x"}))
        self.assertEqual(box.pages("korea.html"), "korea v1")

    def test_current_fresh_full_tree_erases_pages_only_content(self):
        box = self.box
        box.out_of_band({"receipts.html": "reviewed receipt"})
        fresh = box.checkout_main("A-fresh")
        box.full_tree(fresh / "output")
        self.assertIsNone(box.pages("receipts.html"))

    def test_current_overlay_preserves_others_but_stale_overlay_reverts_its_own(self):
        box = self.box
        stale = box.checkout_main("A-desks")
        newer = box.commit_main({"desks.html": "desks v2", "korea.html": "korea v2"}, "B")
        box.full_tree(newer / "output")
        patch = self.tmp / "patch"
        patch.mkdir()
        shutil.copyfile(stale / "output" / "desks.html", patch / "desks.html")
        box.full_tree(patch, keep_files=True)
        self.assertEqual(box.pages("korea.html"), "korea v2")  # unrelated page kept
        self.assertEqual(box.pages("desks.html"), "desks v1")  # own page reverted

    def test_current_daily_no_commit_path_reverts_out_of_group_writer(self):
        box = self.box
        daily = box.checkout_main("daily")                    # daily-update lock
        korea = box.commit_main({"korea.html": "korea v2"}, "korea-verified")
        box.file_only(korea / "output" / "korea.html", "korea.html")
        box.git(daily, "add", "output")
        self.assertEqual(box.git(daily, "diff", "--cached", "--name-only"), "")  # nothing new
        box.full_tree(daily / "output", "Deploy: 2002")       # Step 7 still deploys
        self.assertEqual(box.pages("korea.html"), "korea v1")

    def test_current_daily_commit_path_window_after_rebase(self):
        box = self.box
        daily = box.checkout_main("daily")
        (daily / "output" / "index.html").write_text("home v2", encoding="utf-8")
        box.git(daily, "commit", "-q", "-am", "daily")
        box.git(daily, "pull", "-q", "--rebase", "origin", "main")
        box.git(daily, "push", "-q", "origin", "HEAD:main")
        korea = box.commit_main({"korea.html": "korea v2"}, "korea-verified")
        box.file_only(korea / "output" / "korea.html", "korea.html")
        box.full_tree(daily / "output")
        self.assertEqual(box.pages("index.html"), "home v2")
        self.assertEqual(box.pages("korea.html"), "korea v1")
        self.assertEqual(box.main("korea.html"), "korea v2")

    def test_current_serialized_writers_that_refetch_are_safe(self):
        box = self.box
        b = box.commit_main({"korea.html": "korea v2"}, "B")
        box.file_only(b / "output" / "korea.html", "korea.html")
        a = box.checkout_main("A-after-lock")                 # snapshot AFTER B finished
        box.full_tree(a / "output")
        self.assertEqual(box.pages("korea.html"), "korea v2")

    def test_current_protocol_cannot_tell_rollback_from_stale_republish(self):
        box = self.box
        v1 = box.checkout_main("v1")
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        box.full_tree(v2 / "output", "Deploy: 3003")
        box.full_tree(v1 / "output", "Deploy: 3004")          # "authorized rollback"
        rollback_tree = box.git(box.origin, "rev-parse", "gh-pages^{tree}")
        box.full_tree(v2 / "output", "Deploy: 3005")
        box.full_tree(v1 / "output", "Deploy: 3006")          # stale republish
        self.assertEqual(box.git(box.origin, "rev-parse", "gh-pages^{tree}"), rollback_tree)

    def test_current_crash_after_deploy_leaves_no_source_attestation(self):
        box = self.box
        daily = box.commit_main({"index.html": "home v2"}, "daily")
        box.full_tree(daily / "output", "Deploy: 4004")
        # Crash here: Step 8 never writes .github/state/last_daily_run_date.txt.
        message = box.pages_message()
        self.assertNotIn(box.main_sha()[:7], message)
        self.assertNotIn(TRAILER, box.git(box.origin, "log", "-1", "--format=%B", "gh-pages"))


class HelperProtocol(RaceCase):
    """The real release helper against the same hazards."""

    def release(self, checkout, push=True, writer="test"):
        """Run the CLI from a checkout, releasing that checkout's HEAD."""
        sha = self.box.git(checkout, "rev-parse", "HEAD")
        cmd = [sys.executable, str(HELPER), "--repo", str(checkout), "--source", sha,
               "--writer", writer]
        if push:
            cmd.append("--push")
        done = subprocess.run(cmd, cwd=REPO, env=self.box.env, capture_output=True, text=True)
        return done, sha

    def pages_trailer(self):
        body = self.box.git(self.box.origin, "log", "-1", "--format=%B", "gh-pages")
        for line in body.splitlines():
            if line.startswith(TRAILER + ":"):
                return line.split(":", 1)[1].strip()
        return None

    def pages_tree(self):
        return self.box.git(self.box.origin, "rev-parse", "gh-pages^{tree}")

    def main_tree(self):
        return self.box.git(self.box.origin, "rev-parse", "main:output")

    def test_stale_full_tree_cannot_overwrite_a_newer_scoped_release(self):
        box = self.box
        a = box.checkout_main("A-daily")                       # job-start snapshot
        b = box.commit_main({"korea.html": "korea v2"}, "B-korea")
        box.file_only(b / "output" / "korea.html", "korea.html")   # legacy scoped push
        done, _ = self.release(a)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(box.pages("korea.html"), "korea v2")  # B survives
        self.assertIn('"action": "superseded"', done.stdout)

    def test_daily_no_commit_path_cannot_revert_an_out_of_group_writer(self):
        box = self.box
        daily = box.checkout_main("daily")
        korea = box.commit_main({"korea.html": "korea v2"}, "korea-verified")
        self.assertEqual(self.release(korea)[0].returncode, 0)
        done, _ = self.release(daily)                          # Step 7 still runs
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(box.pages("korea.html"), "korea v2")

    def test_release_after_clone_to_push_window_reevaluates_not_overwrites(self):
        # The helper decides from freshly fetched refs, so a stale snapshot
        # that "re-clones a moment later" is still refused.
        box = self.box
        stale = box.checkout_main("A")
        mover = box.commit_main({"desks.html": "desks v2"}, "B")
        self.assertEqual(self.release(mover)[0].returncode, 0)
        self.assertEqual(self.release(stale)[0].returncode, 0)
        self.assertEqual(box.pages("desks.html"), "desks v2")

    def test_pages_only_content_is_held_not_erased(self):
        box = self.box
        box.out_of_band({"receipts.html": "reviewed receipt"})
        tip = box.git(box.origin, "rev-parse", "gh-pages")
        fresh = box.commit_main({"index.html": "home v2"}, "daily")
        done, _ = self.release(fresh)
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertEqual(box.pages("receipts.html"), "reviewed receipt")
        self.assertEqual(box.git(box.origin, "rev-parse", "gh-pages"), tip)

    def test_stale_overlay_is_held_not_compounded(self):
        box = self.box
        stale = box.checkout_main("A-desks")
        newer = box.commit_main({"desks.html": "desks v2", "korea.html": "korea v2"}, "B")
        self.assertEqual(self.release(newer)[0].returncode, 0)
        patch = self.tmp / "patch"
        patch.mkdir()
        shutil.copyfile(stale / "output" / "desks.html", patch / "desks.html")
        box.full_tree(patch, keep_files=True)                  # legacy overlay reverts desks
        self.assertEqual(box.pages("desks.html"), "desks v1")
        follow = box.commit_main({"index.html": "home v2"}, "C")
        done, _ = self.release(follow)                         # drift is detected, not hidden
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertEqual(box.pages("desks.html"), "desks v1")

    def test_stale_republish_is_not_a_rollback(self):
        box = self.box
        v1 = box.checkout_main("v1")
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        self.assertEqual(self.release(v2)[0].returncode, 0)
        done, _ = self.release(v1)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"action": "superseded"', done.stdout)
        self.assertEqual(box.pages("index.html"), "home v2")
        self.assertEqual(self.pages_trailer(), box.git(v2, "rev-parse", "HEAD"))

    def test_rollback_is_a_new_main_commit_and_publishes_forward(self):
        box = self.box
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        self.assertEqual(self.release(v2)[0].returncode, 0)
        revert = box.commit_main({"index.html": "home v1"}, "revert")
        done, sha = self.release(revert)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(box.pages("index.html"), "home v1")
        self.assertEqual(self.pages_trailer(), sha)

    def test_fresh_descendant_publishes_exact_tree(self):
        box = self.box
        v2 = box.commit_main({"desks.html": "desks v2"}, "v2")
        done, sha = self.release(v2)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.pages_tree(), self.main_tree())
        self.assertEqual(self.pages_trailer(), sha)

    def test_crash_recovery_reads_the_trailer_and_does_not_redeploy(self):
        box = self.box
        daily = box.commit_main({"index.html": "home v2"}, "daily")
        self.assertEqual(self.release(daily)[0].returncode, 0)
        tip = box.git(box.origin, "rev-parse", "gh-pages")
        # Crash before the success marker: a retry is idempotent.
        done, _ = self.release(daily)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"action": "current"', done.stdout)
        self.assertEqual(box.git(box.origin, "rev-parse", "gh-pages"), tip)

    def test_dry_run_never_writes(self):
        box = self.box
        v2 = box.commit_main({"index.html": "home v2"}, "v2")
        tip = box.git(box.origin, "rev-parse", "gh-pages")
        done, _ = self.release(v2, push=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('"published": false', done.stdout)
        self.assertEqual(box.git(box.origin, "rev-parse", "gh-pages"), tip)


if __name__ == "__main__":
    unittest.main()
