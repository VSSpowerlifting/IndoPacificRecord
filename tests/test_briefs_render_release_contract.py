"""Static contract tests for the manual-only Briefs render/release workflow."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/briefs_render_only_release.yml"
RUNNER = ROOT / "scripts/run_briefs_render_release.py"


class BriefsRenderReleaseContract(unittest.TestCase):
    def test_render_contract_uses_production_collection_admission(self):
        from scripts import run_briefs_render_release as runner
        from core.brief_collection import load_briefs
        from core.desk_registry import load_registry
        published, _ = load_briefs(ROOT / 'briefs', load_registry())
        slug = 'trident-resolve-regional-scale-specific-chinese-tasks'
        with mock.patch.object(runner, '_assert_no17_contract') as check:
            runner._assert_rendered_contract()
        self.assertEqual(check.call_args.args[2], any(s == slug for s, _ in published))
        with mock.patch('core.brief_collection.load_briefs',
                        return_value=([(slug, {})], [])):
            with mock.patch.object(runner, '_assert_no17_contract') as check:
                runner._assert_rendered_contract()
        self.assertTrue(check.call_args.args[2])

    def test_held_no17_requires_absence_and_rejects_public_references(self):
        from scripts.run_briefs_render_release import _assert_no17_contract
        route = 'briefs/trident-resolve-regional-scale-specific-chinese-tasks.html'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            surfaces = ('index.html', 'analysis.html', 'briefs/feed.xml', 'sitemap.xml')
            for name in surfaces:
                p = out / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('unrelated admitted content')
            _assert_no17_contract(out, '', False)
            (out / route).write_text('synthetic forbidden page')
            with self.assertRaisesRegex(AssertionError, 'must remain absent'):
                _assert_no17_contract(out, '', False)
            (out / route).unlink()
            for name in surfaces:
                with self.subTest(surface=name):
                    (out / name).write_text(route)
                    with self.assertRaisesRegex(AssertionError, 'public reference'):
                        _assert_no17_contract(out, '', False)
                    (out / name).write_text('unrelated admitted content')
            with self.assertRaisesRegex(AssertionError, 'catalogue card'):
                _assert_no17_contract(out, 'no-17-trident-resolve-basarnas-drone.jpg', False)

    def test_admitted_no17_retains_content_asset_and_hash_checks(self):
        from scripts import run_briefs_render_release as runner
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'output'
            article = out / 'briefs/trident-resolve-regional-scale-specific-chinese-tasks.html'
            article.parent.mkdir(parents=True)
            article.write_text('trident-resolve-basarnas-drone-800.webp 9957254 '
                               'Sgt. 1st Class Timothy Hughes '
                               'does not imply or constitute DoW endorsement')
            source = root / 'site/assets/editorial/trident-resolve-basarnas-drone.jpg'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'synthetic fixture')
            assets = ('editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg',
                      'editorial/derivatives/trident-resolve-basarnas-drone-800.webp',
                      'editorial/derivatives/trident-resolve-basarnas-drone-1600.webp',
                      'catalogue/media/no-17-trident-resolve-basarnas-drone.jpg')
            for name in assets:
                for base in (root / 'site/assets', out / 'assets'):
                    target = base / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(b'synthetic fixture')
            with mock.patch.object(runner, 'ROOT', root):
                check = lambda: runner._assert_no17_contract(
                    out, 'no-17-trident-resolve-basarnas-drone.jpg', True)
                check()
                target = out / 'assets' / assets[0]
                target.write_bytes(b'drift')
                with self.assertRaisesRegex(AssertionError, 'hash mismatch'):
                    check()
                target.unlink()
                with self.assertRaisesRegex(AssertionError, 'asset is missing'):
                    check()
                article.write_text('incomplete synthetic article')
                with self.assertRaisesRegex(AssertionError, 'article is missing'):
                    check()

    def test_shared_article_styles_trigger_exact_output_replay(self):
        review_paths = self.workflow.split("  pull_request:", 1)[1].split("  workflow_dispatch:", 1)[0]
        for path in ("site/preview/briefs.css", "output/briefs.css"):
            self.assertIn('"' + path + '"', review_paths)

    def test_review_replay_requires_exact_committed_output_and_release_requires_change(self):
        from scripts.run_briefs_render_release import _check_replay_delta
        _check_replay_delta(set(), verify_current=True)
        with self.assertRaisesRegex(SystemExit, "differs from its render"):
            _check_replay_delta({"output/briefs.css"}, verify_current=True)
        with self.assertRaisesRegex(SystemExit, "no changes to release"):
            _check_replay_delta(set())
        _check_replay_delta({"output/briefs.css"})

    def test_current_replay_mode_is_pr_only_and_preserves_manual_publication_gate(self):
        contract = self.workflow.split("  contract:", 1)[1].split("  preview:", 1)[0]
        manual = self.workflow.split("  preview:", 1)[1]
        self.assertIn("--scope strict --verify-current", contract)
        self.assertNotIn("--verify-current", manual)
        self.assertNotIn("git push", contract)
        self.assertNotIn("peaceiris/actions-gh-pages", contract)

    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_release_is_manual_only_and_defaults_to_preview(self):
        text = self.workflow
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("default: false", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.publish == true && github.ref == 'refs/heads/main'", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.publish == false && github.ref == 'refs/heads/main'", text)
        self.assertIn('[[ "$EXPECTED_SHA" =~ ^[a-f0-9]{40}$ ]]', text)
        self.assertIn('test "$ACTUAL_SHA" = "$EXPECTED_SHA"', text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)

    def test_render_reuses_existing_sources_and_never_collects(self):
        text = self.workflow + self.runner
        for required in (
            "scripts/rerender_pla_watch.py", "site/render.py",
            "scripts/validate_output.py", "scripts/build_brief_cover.py",
            "scripts/build_catalogue_media.py", "pla_watch.db-wal",
            "pla_watch.db-shm", "sha256sum", "classify_output_changes",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        for forbidden in (
            "python pipeline.py", "ANTHROPIC_API_KEY",
            "shadow_collect.py", "scripts/shadow_collect",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_scope_gate_precedes_staging_commit_and_deployment(self):
        text = self.workflow
        strict = text.index("python -m scripts.run_briefs_render_release --scope strict")
        stage = text.index("git add -A -- output/")
        push = text.index("git push origin HEAD:main")
        deploy = text.index("uses: peaceiris/actions-gh-pages@v3")
        self.assertLess(strict, stage)
        self.assertLess(stage, push)
        self.assertLess(push, deploy)
        self.assertIn("python -m scripts.guard_briefs_render_scope", text)

    def test_preview_uploads_artifact_and_does_not_commit_or_deploy(self):
        text = self.workflow
        preview = text.split("  preview:", 1)[1].split("  publish:", 1)[0]
        self.assertIn("--scope strict", preview)
        self.assertIn("actions/upload-artifact@v4", preview)
        self.assertIn("output/styles.css", preview)
        self.assertIn("output/assets/identity/selected-ipr/**", preview)
        self.assertIn("output/briefs/media/*.jpg", preview)
        self.assertNotIn("git push", preview)
        self.assertNotIn("peaceiris/actions-gh-pages", preview)

    def test_runner_uses_both_renderers_and_checks_expected_surfaces(self):
        text = self.runner
        self.assertIn('"scripts/rerender_pla_watch.py", "--no-covers"', text)
        self.assertIn('"site/render.py", "--out", "output"', text)
        self.assertIn("no-17-trident-resolve-basarnas-drone.jpg", text)
        self.assertIn("trident-resolve-basarnas-drone-800.webp", text)
        self.assertIn("does not imply or constitute DoW endorsement", text)
        self.assertIn('"site" / "assets" / "editorial" / "trident-resolve-basarnas-drone.jpg"', text)
        self.assertIn("public output asset hash mismatch", text)
        self.assertIn("unmodified source JPEG must not be present in public output", text)
        self.assertNotIn('"assets/editorial/trident-resolve-basarnas-drone.jpg"', text)
        self.assertIn("Downloaded from PLA Daily / 81.cn", text)
        self.assertIn("output deltas", text.lower())


if __name__ == "__main__":
    unittest.main()
