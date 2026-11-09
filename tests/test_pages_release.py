"""Offline tests for the tree-identity Pages release helper.

Every test uses disposable local bare repositories; nothing touches GitHub.
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import pages_release as pr

ENV = {"GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "f@example.invalid",
       "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "f@example.invalid",
       "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def git(cwd, *args, check=True):
    p = subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=str(cwd),
                       capture_output=True, text=True, env={**os.environ, **ENV})
    if check and p.returncode:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


class Clone:
    """A working clone that can write output/ to main."""

    def __init__(self, path):
        self.path = path

    def write(self, name, data):
        f = self.path / "output" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)

    def commit(self, msg, push=True):
        git(self.path, "add", "-f", "-A", "output")
        git(self.path, "commit", "--allow-empty", "-m", msg)
        if push:
            git(self.path, "push", "origin", "HEAD:main")
        return git(self.path, "rev-parse", "HEAD")


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.root = Path(self._t.name)
        self.origin = self.root / "origin.git"
        git(self.root, "init", "--bare", "-b", "main", str(self.origin))
        self.work = self.root / "work"
        git(self.root, "clone", str(self.origin), str(self.work))
        git(self.work, "checkout", "-b", "main")
        self.m = Clone(self.work)
        self.m.write("index.html", b"<h1>one</h1>")
        self.m.write("korea.html", b"Korea one")
        self.m.write("CNAME", b"indopacificrecord.org\n")
        self.m.write(".nojekyll", b"")
        self.v1 = self.m.commit("v1")
        # Legacy Pages tip: exactly main:output, no Source-SHA trailer.
        tree = git(self.work, "rev-parse", "HEAD:output")
        legacy = git(self.work, "commit-tree", tree, "-m", "peaceiris deploy")
        git(self.work, "push", "origin", legacy + ":refs/heads/gh-pages")
        self.legacy = legacy

    # helpers ---------------------------------------------------------------
    def clone(self, name):
        path = self.root / name
        git(self.root, "clone", "--quiet", str(self.origin), str(path))
        return path

    def pages_tip(self):
        return git(self.origin, "rev-parse", "refs/heads/gh-pages")

    def pages_tree(self):
        return git(self.origin, "rev-parse", "refs/heads/gh-pages^{tree}")

    def main_output_tree(self, rev="main"):
        return git(self.origin, "rev-parse", rev + ":output")

    def pages_file(self, name):
        return subprocess.run(["git", "show", "refs/heads/gh-pages:" + name], cwd=str(self.origin),
                              capture_output=True).stdout

    def release(self, repo=None, **kw):
        kw.setdefault("push", True)
        kw.setdefault("writer", "unit-test")
        with mock.patch.dict(os.environ, ENV):
            return pr.release(repo or self.work, **kw)

    def push_pages_directly(self, files, trailer=None):
        """An out-of-band writer: commit straight to gh-pages."""
        c = self.clone("oob-%d" % len(list(self.root.iterdir())))
        git(c, "checkout", "-q", "-B", "pp", "origin/gh-pages")
        for name, data in files.items():
            (c / name).write_bytes(data)
        git(c, "add", "-A")
        msg = "oob" + ("\n\n%s: %s\n" % (pr.TRAILER, trailer) if trailer else "")
        git(c, "commit", "-m", msg)
        git(c, "push", "origin", "HEAD:gh-pages")


class ReleaseTests(Base):
    def test_dry_run_is_default_and_never_writes(self):
        self.m.write("index.html", b"<h1>two</h1>")
        v2 = self.m.commit("v2")
        before = self.pages_tip()
        report = self.release(push=False)
        self.assertEqual(report["action"], "publish")
        self.assertEqual(report["source"], v2)
        self.assertFalse(report["published"])
        self.assertEqual(self.pages_tip(), before)

    def test_publish_makes_pages_tree_equal_main_output_with_trailer(self):
        self.m.write("index.html", b"<h1>two</h1>")
        v2 = self.m.commit("v2")
        report = self.release()
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_tree(), self.main_output_tree())
        self.assertEqual(self.pages_tip(), report["pages_commit"])
        self.assertEqual(git(self.origin, "rev-parse", "gh-pages^"), self.legacy)  # fast-forward
        self.assertIn("%s: %s" % (pr.TRAILER, v2), git(self.origin, "log", "-1", "--format=%B", "gh-pages"))
        self.assertEqual(self.pages_file("CNAME"), b"indopacificrecord.org\n")
        self.assertEqual(self.pages_file(".nojekyll"), b"")
        self.assertEqual(self.pages_file("index.html"), b"<h1>two</h1>")

    def test_publishes_on_a_runner_with_no_git_identity(self):
        """A fresh Actions runner has no user.name/email; the helper supplies one."""
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        bare = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(self.root), "EMAIL": ""}
        with mock.patch.dict(os.environ, bare):
            for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
                os.environ.pop(key, None)
            report = pr.release(self.work, push=True, writer="no-identity")
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_tree(), self.main_output_tree())
        self.assertIn("github-actions[bot]",
                      git(self.origin, "log", "-1", "--format=%an", "gh-pages"))

    def test_idempotent_retry_pushes_nothing(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        first = self.release()
        tip = self.pages_tip()
        again = self.release()
        self.assertEqual(again["action"], "current")
        self.assertFalse(again["published"])
        self.assertEqual(self.pages_tip(), tip)
        self.assertTrue(first["published"])

    def test_legacy_tip_without_trailer_is_attributed_by_tree(self):
        report = self.release(push=False)
        self.assertEqual(report["action"], "current")  # legacy tip already equals main:output
        self.m.write("korea.html", b"Korea two")
        self.m.commit("v2")
        report = self.release(push=False)
        self.assertEqual(report["action"], "publish")
        self.assertEqual(report["attribution"], "legacy-tree-match")
        self.assertEqual(report["previous_source"], self.v1)

    def test_file_only_change_publishes_only_that_file_difference(self):
        self.m.write("korea.html", b"Korea two")
        self.m.commit("korea page only")
        self.release()
        diff = git(self.origin, "diff", "--name-only", "gh-pages^", "gh-pages").splitlines()
        self.assertEqual(diff, ["korea.html"])

    def test_full_tree_release_after_file_only_release_is_not_held(self):
        self.m.write("korea.html", b"Korea two")
        self.m.commit("file-only writer")
        self.release()
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.write("new/page.html", b"new")
        self.m.commit("daily full tree")
        report = self.release()
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_tree(), self.main_output_tree())

    def test_deletion_in_main_output_is_released(self):
        self.m.write("old.html", b"old")
        self.m.commit("add old")
        self.release()
        (self.work / "output" / "old.html").unlink()
        self.m.commit("remove old")
        self.release()
        self.assertEqual(self.pages_file("old.html"), b"")
        self.assertEqual(self.pages_tree(), self.main_output_tree())

    def test_gitignore_cannot_drop_committed_output(self):
        (self.work / ".gitignore").write_text("*.json\n")
        self.m.write("data/feed.json", b"{}")
        self.m.commit("ignored-but-force-added file")
        self.release()
        self.assertEqual(self.pages_file("data/feed.json"), b"{}")
        self.assertEqual(self.pages_tree(), self.main_output_tree())


class HoldTests(Base):
    def test_out_of_band_change_after_a_release_holds(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        self.release()
        self.push_pages_directly({"rogue.html": b"x"}, trailer=self.v1)
        self.m.write("index.html", b"<h1>three</h1>")
        self.m.commit("v3")
        with self.assertRaisesRegex(pr.Hold, "out-of-band|matches no recent"):
            self.release()

    def test_unattributable_pages_only_content_holds_instead_of_being_erased(self):
        self.push_pages_directly({"pages-only.html": b"unique"})
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        before = self.pages_tip()
        with self.assertRaisesRegex(pr.Hold, "no Source-SHA trailer"):
            self.release()
        self.assertEqual(self.pages_tip(), before)
        self.assertEqual(self.pages_file("pages-only.html"), b"unique")

    def test_rollback_request_is_superseded_not_published(self):
        self.m.write("index.html", b"<h1>two</h1>")
        v2 = self.m.commit("v2")
        self.m.write("index.html", b"<h1>three</h1>")
        self.m.commit("v3")
        self.release()
        tip = self.pages_tip()
        report = self.release(source=v2)
        self.assertEqual(report["action"], "superseded")
        self.assertFalse(report["published"])
        self.assertEqual(self.pages_tip(), tip)
        self.assertEqual(self.pages_file("index.html"), b"<h1>three</h1>")

    def test_stale_checkout_cannot_overwrite_newer_pages(self):
        stale = self.clone("stale")
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        self.release()
        self.m.write("index.html", b"<h1>three</h1>")
        self.m.commit("v3")
        self.release()
        tip = self.pages_tip()
        # A job that started from v1 and still holds its job-start tree.
        old_source = git(stale, "rev-parse", "HEAD")
        report = self.release(stale, source=old_source)
        self.assertEqual(report["action"], "superseded")
        self.assertEqual(self.pages_tip(), tip)

    def test_source_not_on_main_holds(self):
        c = self.clone("local")
        (c / "output" / "index.html").write_text("unmerged")
        git(c, "add", "-A")
        git(c, "commit", "-m", "unpushed")
        sha = git(c, "rev-parse", "HEAD")
        before = self.pages_tip()
        with self.assertRaisesRegex(pr.Hold, "not on main"):
            self.release(c, source=sha)
        self.assertEqual(self.pages_tip(), before)

    def test_rewritten_main_holds(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        self.release()
        git(self.work, "reset", "--hard", self.v1)
        self.m.write("index.html", b"<h1>other</h1>")
        git(self.work, "add", "-A")
        git(self.work, "commit", "-m", "rewritten history")
        git(self.work, "push", "--force", "origin", "HEAD:main")
        with self.assertRaisesRegex(pr.Hold, "not on main"):
            self.release()

    def test_symlink_in_output_holds(self):
        os.symlink("index.html", self.work / "output" / "alias.html")
        self.m.commit("symlink")
        with self.assertRaisesRegex(pr.Hold, "unsupported entry"):
            self.release()

    def test_missing_required_files_holds(self):
        (self.work / "output" / "CNAME").unlink()
        self.m.commit("lose CNAME")
        with self.assertRaisesRegex(pr.Hold, "missing required"):
            self.release()

    def test_missing_pages_branch_holds(self):
        git(self.origin, "update-ref", "-d", "refs/heads/gh-pages")
        with self.assertRaisesRegex(pr.Hold, "cannot resolve"):
            self.release()


class ConcurrencyAndRecoveryTests(Base):
    def _interfere(self, other, source):
        """Run a competing release between this writer's read and its push."""
        real = pr._commit
        fired = []

        def commit_then_race(repo, plan, writer):
            commit = real(repo, plan, writer)
            if not fired:
                fired.append(True)
                with mock.patch.dict(os.environ, ENV):
                    pr.release(other, push=True, writer="competitor", source=source)
            return commit
        return mock.patch.object(pr, "_commit", commit_then_race)

    def test_loser_of_a_race_retries_and_does_not_regress_newer_pages(self):
        other = self.clone("other")
        self.m.write("index.html", b"<h1>two</h1>")
        v2 = self.m.commit("v2")
        self.m.write("index.html", b"<h1>three</h1>")
        v3 = self.m.commit("v3")
        # We want v2, but a competitor publishes v3 first.
        with self._interfere(other, v3):
            report = self.release(source=v2)
        self.assertEqual(report["action"], "superseded")
        self.assertEqual(report["attempt"], 2)
        self.assertEqual(self.pages_file("index.html"), b"<h1>three</h1>")
        self.assertIn(v3, git(self.origin, "log", "-1", "--format=%B", "gh-pages"))

    def test_loser_of_a_race_publishes_newer_after_older_wins(self):
        other = self.clone("other")
        self.m.write("index.html", b"<h1>two</h1>")
        v2 = self.m.commit("v2")
        self.m.write("index.html", b"<h1>three</h1>")
        v3 = self.m.commit("v3")
        # We want v3; a competitor lands v2 between our read and push.
        with self._interfere(other, v2):
            report = self.release(source=v3)
        self.assertTrue(report["published"])
        self.assertEqual(report["attempt"], 2)
        self.assertEqual(self.pages_tree(), self.main_output_tree())

    def test_retry_after_failed_push_recovers(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        hook = self.origin / "hooks" / "pre-receive"
        flag = self.root / "reject"
        flag.write_text("1")
        hook.write_text('#!/bin/sh\n[ -e "%s" ] && exit 1\nexit 0\n' % flag)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        before = self.pages_tip()
        with self.assertRaises(pr.Hold):
            self.release()
        self.assertEqual(self.pages_tip(), before)  # last-good site untouched
        flag.unlink()
        report = self.release()
        self.assertTrue(report["published"])

    def test_main_ahead_of_pages_is_healed_by_the_next_release(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("collection committed, release crashed")
        self.m.write("korea.html", b"Korea two")
        self.m.commit("later commit")
        report = self.release()
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_tree(), self.main_output_tree())

    def test_shallow_checkout_is_deepened_for_ancestry(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        shallow = self.root / "shallow"
        git(self.root, "clone", "--quiet", "--depth", "1", "file://%s" % self.origin, str(shallow))
        report = self.release(shallow)
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_tree(), self.main_output_tree())


class CliTests(Base):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, ENV), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = pr.main(["--repo", str(self.work), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_default_is_dry_run_and_exit_zero(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        before = self.pages_tip()
        code, out, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["action"], "publish")
        self.assertEqual(self.pages_tip(), before)

    def test_push_flag_publishes(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        code, out, _ = self.run_cli("--push", "--writer", "ci")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["published"])
        self.assertIn("Released-By: ci", git(self.origin, "log", "-1", "--format=%B", "gh-pages"))

    def test_hold_is_exit_three(self):
        self.push_pages_directly({"x.html": b"x"})
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        code, out, err = self.run_cli("--push")
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out)["action"], "hold")
        self.assertIn("HOLD", err)

    def test_action_is_exposed_to_later_workflow_steps(self):
        gh_out = self.root / "github_output"
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("v2")
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(gh_out)}):
            self.assertEqual(self.run_cli("--push")[0], 0)
            self.assertEqual(self.run_cli("--push")[0], 0)   # now current
        self.assertEqual(gh_out.read_text().split(), ["action=publish", "action=current"])
        self.push_pages_directly({"x.html": b"x"})
        self.m.write("index.html", b"<h1>three</h1>")
        self.m.commit("v3")
        with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(gh_out)}):
            self.assertEqual(self.run_cli("--push")[0], 3)
        self.assertEqual(gh_out.read_text().split()[-1], "action=hold")


if __name__ == "__main__":
    unittest.main()
