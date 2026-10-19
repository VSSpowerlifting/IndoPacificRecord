"""Conservative, explicit PR CI scope boundaries."""
import unittest
from scripts.pr_ci_scope import Scope, classify


class TestPrCiScope(unittest.TestCase):
    def test_markdown_only_does_not_need_browser_or_models(self):
        self.assertEqual(classify(["docs/ROADMAP.md", "CLAUDE.md",
                                   "docs/SHADOW_REVIEW.md"]),
                         Scope("docs", False, False))

    def test_timeline_style_and_template_trigger_relevant_browser_tests(self):
        self.assertEqual(classify(["site/preview/timelines.css",
                                   "site/preview/templates/timeline.html",
                                   "site/assets/timelines/maritime-ocean-texture.webp",
                                   "PROJECT_STATE.md"]),
                         Scope("focused", True, False))

    def test_unrelated_code_forces_full(self):
        for path in ("pipeline.py", "scripts/rescreen_desk.py",
                     "site/preview/generate_preview.py",
                     "site/render.py", "core/timelines.py",
                     "tests/test_timelines.py", "pla_watch.db",
                     "output/analysis.html", ".github/workflows/daily_update.yml",
                     "scripts/pr_ci_scope.py", "desks/registry.json",
                     "timelines/maritime-cooperation-2026.json",
                     "docs/source_policy.json"):
            with self.subTest(path=path):
                self.assertEqual(classify([path]).mode, "full")

    def test_mixed_docs_and_code_fail_closed(self):
        self.assertEqual(classify(["docs/ROADMAP.md", "analysis/analyzer.py"]),
                         Scope("full", True, False))

    def test_historical_evidence_changes_require_replay(self):
        self.assertEqual(classify(["research/topic_pilot_v1/ledger.json"]),
                         Scope("full", True, True))
        self.assertEqual(classify(["tests/test_topic_pilot_review.py"]),
                         Scope("full", True, True))

    def test_empty_and_malformed_diff_is_full(self):
        for paths in ([], ["../foo.md"], ["/foo.md"], ["docs/"],
                      ["docs\\FAKE.md"], [""]):
            with self.subTest(paths=paths):
                self.assertEqual(classify(paths), Scope("full", True, True))


if __name__ == "__main__":
    unittest.main()
