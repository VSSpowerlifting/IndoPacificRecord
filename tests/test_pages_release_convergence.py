"""Failure-case proofs for the converged Pages release protocol (#346).

Every case runs the real ``scripts/pages_release.py`` against disposable local
bare repositories. Nothing touches GitHub. The fixtures (a main clone with
``output/`` and a legacy, trailer-less ``gh-pages`` tip) come from
``tests/test_pages_release.py``.
"""
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from scripts import pages_release as pr
from tests.test_pages_release import ENV, Base, Clone, git


class ConvergenceBase(Base):
    def setUp(self):
        super().setUp()
        self.m.write("korea-originals/1.html", b"original one")
        self.m.write("indonesia.html", b"Indonesia one")
        self.base = self.m.commit("v1b")
        self.release()  # first helper release: Pages == v1b:output, attested

    def other(self, name):
        path = self.clone(name)
        git(path, "checkout", "-q", "main")
        return Clone(path)

    def pages_message(self):
        return git(self.origin, "log", "-1", "--format=%B", "refs/heads/gh-pages")

    def pages_has(self, name):
        return subprocess.run(["git", "cat-file", "-e", "refs/heads/gh-pages:" + name],
                              cwd=str(self.origin)).returncode == 0

    def overlay(self, repo, paths, **kw):
        return self.release(repo, overlay=list(paths), **kw)

    def sync(self, clone):
        git(clone.path, "pull", "--quiet", "--rebase", "origin", "main")


class StaleFullTreeTests(ConvergenceBase):
    def test_daily_after_newer_file_only_release_keeps_both(self):
        """Daily commits D; Korea publishes K (after D) file-only; Daily then
        releases D. Old peaceiris erased Korea's file; a naive high-water mark
        would call Daily 'superseded' and leave D's content unpublished."""
        self.m.write("index.html", b"<h1>daily D</h1>")
        daily = self.m.commit("Daily D")
        korea = self.other("korea")
        korea.write("korea.html", b"Korea K")
        k = korea.commit("Korea K")
        self.assertEqual(self.overlay(korea.path, ["korea.html"], source=k)["action"], "publish")
        report = self.release(source=daily)
        self.assertEqual(report["action"], "publish")
        self.assertEqual(self.pages_file("index.html"), b"<h1>daily D</h1>")
        self.assertEqual(self.pages_file("korea.html"), b"Korea K")
        self.assertEqual(report["state"], {"base": daily, "overlays": [(k, "korea.html")]})
        # The next full release from a commit containing K drops the overlay.
        self.sync(self.m)
        self.m.write("index.html", b"<h1>daily E</h1>")
        e = self.m.commit("Daily E")
        report = self.release(source=e)
        self.assertEqual(report["state"], {"base": e, "overlays": []})
        self.assertEqual(self.pages_tree(), self.main_output_tree())

    def test_stale_manual_deploy_after_daily_is_superseded_not_published(self):
        manual_source = git(self.work, "rev-parse", "HEAD")  # manual job checked out here
        self.m.write("index.html", b"<h1>daily two</h1>")
        self.m.commit("Daily two")
        self.release()
        tip = self.pages_tip()
        report = self.release(source=manual_source)
        self.assertEqual(report["action"], "superseded")
        self.assertEqual(self.pages_tip(), tip)
        self.assertEqual(self.pages_file("index.html"), b"<h1>daily two</h1>")

    def test_ci_green_but_stale_overlay_is_superseded_by_newer_full_release(self):
        korea = self.other("korea")
        korea.write("korea.html", b"Korea stale")
        stale = korea.commit("Korea stale")
        self.sync(self.m)
        self.m.write("korea.html", b"Korea newer")
        self.m.commit("Korea newer, rendered by Daily")
        self.release()
        tip = self.pages_tip()
        report = self.overlay(korea.path, ["korea.html"], source=stale)
        self.assertEqual(report["action"], "superseded")
        self.assertEqual(self.pages_tip(), tip)
        self.assertEqual(self.pages_file("korea.html"), b"Korea newer")

    def test_stale_overlay_after_newer_overlay_of_same_path_is_superseded(self):
        a = self.other("a")
        a.write("korea.html", b"Korea A")
        older = a.commit("A")
        b = self.other("b")
        b.write("korea.html", b"Korea B")
        newer = b.commit("B")
        self.assertEqual(self.overlay(b.path, ["korea.html"], source=newer)["action"], "publish")
        report = self.overlay(a.path, ["korea.html"], source=older)
        self.assertEqual(report["action"], "superseded")
        self.assertEqual(self.pages_file("korea.html"), b"Korea B")


class FileOnlyScopeTests(ConvergenceBase):
    def test_overlay_publishes_only_its_paths_never_unreleased_main_output(self):
        """A merged-but-unvalidated main:output (Daily's validator hold) must not
        go live because a Korea file-only job ran."""
        self.m.write("index.html", b"<h1>unreleased, failed validation</h1>")
        self.m.write("korea.html", b"Korea two")
        s = self.m.commit("both")
        report = self.overlay(self.work, ["korea.html"], source=s)
        self.assertEqual(report["action"], "publish")
        self.assertEqual(self.pages_file("korea.html"), b"Korea two")
        self.assertEqual(self.pages_file("index.html"), b"<h1>one</h1>")
        self.assertEqual(report["delta"]["changed"], 1)
        self.assertEqual(report["delta"]["added"] + report["delta"]["removed"], 0)

    def test_overlay_directory_is_mirrored_exactly_including_withdrawal(self):
        (self.work / "output/korea-originals/1.html").unlink()
        self.m.write("korea-originals/2.html", b"original two")
        s = self.m.commit("withdraw 1, add 2")
        self.overlay(self.work, ["korea.html", "korea-originals"], source=s)
        self.assertFalse(self.pages_has("korea-originals/1.html"))
        self.assertEqual(self.pages_file("korea-originals/2.html"), b"original two")

    def test_overlay_of_a_file_absent_from_source_deletes_it(self):
        (self.work / "output/indonesia.html").unlink()
        s = self.m.commit("hold Indonesia page")
        self.overlay(self.work, ["indonesia.html"], source=s)
        self.assertFalse(self.pages_has("indonesia.html"))
        self.assertTrue(self.pages_has("CNAME") and self.pages_has(".nojekyll"))

    def test_required_site_files_cannot_be_overlaid(self):
        with self.assertRaisesRegex(pr.Hold, "not a releasable path"):
            self.overlay(self.work, ["CNAME"])
        with self.assertRaisesRegex(pr.Hold, "not a releasable path"):
            self.overlay(self.work, ["../x"])

    def test_release_that_would_change_the_custom_domain_holds(self):
        self.m.write("CNAME", b"chinamilwatch.org\n")
        self.m.commit("wrong domain")
        tip = self.pages_tip()
        with self.assertRaisesRegex(pr.Hold, "CNAME"):
            self.release()
        self.assertEqual(self.pages_tip(), tip)

    def test_identical_overlay_is_current_and_pushes_nothing(self):
        tip = self.pages_tip()
        report = self.overlay(self.work, ["korea.html"])
        self.assertEqual(report["action"], "current")
        self.assertEqual(self.pages_tip(), tip)

    def test_legacy_tip_bootstrap_accepts_an_overlay(self):
        # Reset Pages to a legacy, trailer-less tip that equals main:output.
        tree = self.main_output_tree()
        legacy = git(self.work, "commit-tree", tree, "-p", self.pages_tip(), "-m", "legacy")
        git(self.work, "push", "origin", legacy + ":refs/heads/gh-pages")
        self.m.write("korea.html", b"Korea two")
        s = self.m.commit("Korea two")
        report = self.overlay(self.work, ["korea.html"], source=s)
        self.assertEqual(report["attribution"], "legacy-tree-match")
        self.assertEqual(report["action"], "publish")


class ConcurrencyTests(ConvergenceBase):
    def _race(self, competitor):
        """Run ``competitor`` once between this writer's evaluation and push."""
        real, fired = pr._commit, []

        def commit_then_race(repo, plan, writer, subject=None):
            commit = real(repo, plan, writer, subject)
            if not fired:
                fired.append(True)
                competitor()
            return commit
        return mock.patch.object(pr, "_commit", commit_then_race)

    def test_concurrent_disjoint_file_only_writers_both_land(self):
        korea, indo = self.other("korea"), self.other("indo")
        korea.write("korea.html", b"Korea K")
        k = korea.commit("K")
        self.sync(indo)
        indo.write("indonesia.html", b"Indonesia I")
        i = indo.commit("I")
        with self._race(lambda: self.overlay(indo.path, ["indonesia.html"], source=i)):
            report = self.overlay(korea.path, ["korea.html"], source=k)
        self.assertTrue(report["published"])
        self.assertEqual(report["attempt"], 2)  # first push lost the compare-and-swap
        self.assertEqual(self.pages_file("korea.html"), b"Korea K")
        self.assertEqual(self.pages_file("indonesia.html"), b"Indonesia I")

    def test_full_release_racing_a_newer_overlay_reapplies_it(self):
        self.m.write("index.html", b"<h1>D</h1>")
        d = self.m.commit("D")
        korea = self.other("korea")
        korea.write("korea.html", b"Korea K")
        k = korea.commit("K")
        with self._race(lambda: self.overlay(korea.path, ["korea.html"], source=k)):
            report = self.release(source=d)
        self.assertTrue(report["published"])
        self.assertEqual(self.pages_file("index.html"), b"<h1>D</h1>")
        self.assertEqual(self.pages_file("korea.html"), b"Korea K")

    def test_pages_tip_advancing_by_an_out_of_band_push_mid_release_holds(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("two")
        with self._race(lambda: self.push_pages_directly({"x.html": b"x"})):
            with self.assertRaisesRegex(pr.Hold, "reconcile --expect-pages"):
                self.release()
        self.assertTrue(self.pages_has("x.html"))  # never overwritten

    def test_persistent_push_failure_holds_without_partial_write(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("two")
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        tip = self.pages_tip()
        with self.assertRaisesRegex(pr.Hold, "not forcing"):
            self.release()
        self.assertEqual(self.pages_tip(), tip)

    def test_push_that_landed_but_reported_failure_is_not_published_twice(self):
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("two")
        real = pr._git

        def flaky(repo, *args, **kw):
            result = real(repo, *args, **kw)
            if args and args[0] == "push" and not flaky.done:
                flaky.done = True
                return subprocess.CompletedProcess(result.args, 1, b"", b"")
            return result
        flaky.done = False
        before = git(self.origin, "rev-list", "--count", "refs/heads/gh-pages")
        with mock.patch.object(pr, "_git", flaky):
            report = self.release()
        self.assertEqual(report["action"], "current")
        after = git(self.origin, "rev-list", "--count", "refs/heads/gh-pages")
        self.assertEqual(int(after), int(before) + 1)


class RecoveryAndRollbackTests(ConvergenceBase):
    def test_missing_success_marker_rerun_is_current_without_redeploy(self):
        self.m.write("index.html", b"<h1>two</h1>")
        s = self.m.commit("two")
        self.assertTrue(self.release(source=s)["published"])
        tip = self.pages_tip()
        # The job died before "Record successful run"; the retry re-releases s.
        report = self.release(source=s)
        self.assertEqual(report["action"], "current")
        self.assertEqual(self.pages_tip(), tip)

    def test_unauthorized_rollback_to_an_older_source_is_refused(self):
        old = self.base
        self.m.write("index.html", b"<h1>withdrawn content removed</h1>")
        self.m.commit("withdraw")
        self.release()
        self.sync(self.m)
        self.m.write("korea.html", b"Korea corrected")
        self.m.commit("correct Korea")
        self.overlay(self.work, ["korea.html"])
        tip = self.pages_tip()
        for kw in ({"source": old}, {"source": old, "overlay": ["korea.html"]}):
            self.assertEqual(self.release(**kw)["action"], "superseded")
        self.assertEqual(self.pages_tip(), tip)

    def test_legitimate_forward_rollback_is_a_revert_on_main(self):
        v1_tree = self.main_output_tree()
        self.m.write("index.html", b"<h1>bad</h1>")
        bad = self.m.commit("bad")
        self.release()
        git(self.work, "revert", "--no-edit", bad)
        git(self.work, "push", "origin", "HEAD:main")
        report = self.release()
        self.assertEqual(report["action"], "publish")
        self.assertEqual(self.pages_tree(), v1_tree)
        self.assertIn("Source-SHA: " + git(self.work, "rev-parse", "HEAD"), self.pages_message())

    def test_identical_tree_still_advances_attestation_so_a_revert_cannot_be_undone(self):
        self.m.write("index.html", b"<h1>X</h1>")
        x = self.m.commit("X")  # never released
        self.m.write("index.html", b"<h1>one</h1>")
        back = self.m.commit("back to one")
        report = self.release(source=back)
        self.assertEqual(report["action"], "publish")  # attestation-only commit
        self.assertEqual(report["delta"], {"added": 0, "removed": 0, "changed": 0, "paths": []})
        self.assertEqual(self.release(source=x)["action"], "superseded")
        self.assertEqual(self.pages_file("index.html"), b"<h1>one</h1>")


class OutOfBandTests(ConvergenceBase):
    def test_out_of_band_change_holds_and_reconcile_needs_the_exact_tip(self):
        self.push_pages_directly({"social-card.png": b"owner push"})
        self.m.write("index.html", b"<h1>two</h1>")
        self.m.commit("two")
        with self.assertRaisesRegex(pr.Hold, "reconcile --expect-pages"):
            self.release()
        with self.assertRaisesRegex(pr.Hold, "reconcile --expect-pages"):
            self.overlay(self.work, ["korea.html"])
        tip = self.pages_tip()
        with self.assertRaisesRegex(pr.Hold, "not the reviewed"):
            self.release(reconcile_expect="0" * 40)
        dry = self.release(reconcile_expect=tip, push=False)
        self.assertEqual(dry["action"], "publish")
        self.assertIn("-social-card.png", dry["delta"]["paths"])  # shown for review
        report = self.release(reconcile_expect=tip)
        self.assertTrue(report["published"])
        self.assertIn("Reconciled-Pages-SHA: " + tip, self.pages_message())
        self.assertEqual(self.pages_tree(), self.main_output_tree())
        self.assertEqual(self.overlay(self.work, ["korea.html"])["action"], "current")

    def _legacy_push(self, commit):
        """An in-flight old-text writer: push ``commit:output`` with no trailers."""
        tree = git(self.work, "rev-parse", commit + ":output")
        git(self.work, "fetch", "-q", "origin", "gh-pages")
        c = git(self.work, "commit-tree", tree, "-p", "origin/gh-pages", "-m", "peaceiris deploy")
        git(self.work, "push", "origin", c + ":refs/heads/gh-pages")

    def _stale_legacy_over_newer_overlay(self):
        korea = self.other("korea")
        korea.write("korea.html", b"Korea K")
        k = korea.commit("K")
        self.overlay(korea.path, ["korea.html"], source=k)
        attested = self.pages_tree()
        self._legacy_push(self.v1)  # e.g. an old-text run still in flight at merge
        self.assertEqual(self.pages_file("korea.html"), b"Korea one")  # rolled back live
        return k, attested

    def test_stale_unattested_push_cannot_reset_the_base_full_release_restores(self):
        k, attested = self._stale_legacy_over_newer_overlay()
        # An older full release is NOT reported superseded/current over the
        # rollback, and the high-water mark is not reset to v1: the attested
        # state (base + Korea overlay) is restored.
        report = self.release(source=self.v1)
        self.assertEqual(report["attribution"], "stale-legacy-over-attested")
        self.assertEqual(report["action"], "publish")
        self.assertEqual(self.pages_tree(), attested)
        self.assertEqual(self.pages_file("korea.html"), b"Korea K")
        self.assertEqual(report["state"]["overlays"], [(k, "korea.html")])
        # A later stale full release from v1 is superseded again.
        self.assertEqual(self.release(source=self.v1)["action"], "superseded")

    def test_stale_unattested_push_overlay_release_keeps_attested_state(self):
        k, attested = self._stale_legacy_over_newer_overlay()
        report = self.overlay(self.work, ["indonesia.html"])  # unrelated desk
        self.assertEqual(report["attribution"], "stale-legacy-over-attested")
        self.assertEqual(self.pages_file("korea.html"), b"Korea K")
        self.assertEqual(self.pages_file("index.html"), b"<h1>one</h1>")

    def test_unattested_push_of_a_newer_generation_is_still_attributed(self):
        self.m.write("index.html", b"<h1>newer</h1>")
        newer = self.m.commit("newer")
        self._legacy_push(newer)
        report = self.release(source=newer)
        self.assertEqual(report["attribution"], "legacy-tree-match")
        self.assertEqual(report["action"], "current")

    def test_reconcile_releases_only_the_main_tip(self):
        self.push_pages_directly({"x.html": b"x"})
        with self.assertRaisesRegex(pr.Hold, "only the current main tip"):
            self.release(reconcile_expect=self.pages_tip(), source=self.v1)

    def test_tampered_state_claim_holds(self):
        """A commit that copies a release's trailers onto a different tree."""
        msg = self.pages_message()
        c = self.clone("tamper")
        git(c, "checkout", "-q", "-B", "t", "origin/gh-pages")
        (c / "index.html").write_bytes(b"<h1>tampered</h1>")
        git(c, "add", "-A")
        git(c, "commit", "-m", msg)
        git(c, "push", "origin", "HEAD:gh-pages")
        with self.assertRaisesRegex(pr.Hold, "out-of-band"):
            self.release()

    def test_source_not_on_main_holds(self):
        git(self.work, "checkout", "-q", "-b", "side")
        self.m.write("index.html", b"<h1>side</h1>")
        side = self.m.commit("side", push=False)
        git(self.work, "push", "origin", "side")
        git(self.work, "checkout", "-q", "main")
        with self.assertRaisesRegex(pr.Hold, "not on main"):
            self.release(source=side)


class SubjectAndCliTests(ConvergenceBase):
    def test_writer_subject_is_kept_and_cannot_forge_state(self):
        self.m.write("korea.html", b"Korea two")
        self.m.commit("Korea two")
        self.overlay(self.work, ["korea.html"],
                     subject="Korea: publish newly verified MND outbound links only")
        self.assertTrue(self.pages_message().startswith(
            "Korea: publish newly verified MND outbound links only\n"))
        with self.assertRaisesRegex(pr.Hold, "subject"):
            self.overlay(self.work, ["korea.html"], subject="Source-SHA: " + "a" * 40)

    def test_cli_requires_exact_tip_for_reconcile(self):
        with self.assertRaises(SystemExit):
            pr.main(["--repo", str(self.work), "--reconcile"])


if __name__ == "__main__":
    unittest.main()
