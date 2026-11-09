"""Conservative, explicit PR CI scope boundaries."""
import unittest
from scripts.pr_ci_scope import (Entry, Scope, classify, classify_entries,
                                 parse_raw, require_safe_entries)

Z = "0" * 40
S = "1" * 40


def raw(*records):
    """Build ``git diff --raw -z --no-renames`` bytes from (old, new, status, path)."""
    out = b""
    for old, new, status, path in records:
        out += (":%s %s %s %s %s" % (old, new, Z if old == "000000" else S,
                                         Z if new == "000000" else S, status)).encode()
        out += b"\0" + path.encode() + b"\0"
    return out


def add(path, mode="100644"):
    return ("000000", mode, "A", path)


def mod(path, old="100644", new="100644"):
    return (old, new, "M", path)


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


class TestEditorialLane(unittest.TestCase):
    EDITORIAL = Scope("editorial", True, False)

    def scope(self, *records):
        return classify_entries(parse_raw(raw(*records)))

    def test_parse_raw_reads_modes_status_and_path(self):
        self.assertEqual(parse_raw(raw(add("briefs/x.json"), mod("a b.md"))),
                         [Entry("000000", "100644", "A", "briefs/x.json"),
                          Entry("100644", "100644", "M", "a b.md")])
        self.assertEqual(parse_raw(b""), [])

    def test_malformed_raw_diff_raises(self):
        for data in (b":100644 100644 x y M\0", b"garbage\0path\0",
                     b"100644 100644 a b M\0p\0", b":100644 100644 a M\0p\0"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_raw(data)

    def test_governed_brief_content_and_presentation_assets_are_editorial(self):
        for path in ("briefs/brief-24.json", "briefs/presentation/brief-24.json",
                     "briefs/media/brief-24-cover.webp", "briefs/media/brief-24-cover.json",
                     "site/assets/catalogue/media/patkor-01.jpg",
                     "site/assets/catalogue/admissions.json",
                     "site/assets/editorial/brief-24-master.png",
                     "site/assets/editorial/derivatives/brief-24-1200.webp",
                     "site/assets/editorial/manifest.json", "site/preview/staff.json",
                     "docs/evidence/brief-24/approval.json",
                     "docs/evidence/brief-24/source-capture.png"):
            with self.subTest(path=path):
                self.assertEqual(self.scope(add(path)), self.EDITORIAL)
                self.assertEqual(self.scope(mod(path)), self.EDITORIAL)

    def test_a_typical_brief_publication_bundle_is_editorial(self):
        self.assertEqual(self.scope(add("briefs/brief-24.json"),
                                    add("site/assets/catalogue/media/patkor-01.jpg"),
                                    mod("site/assets/catalogue/admissions.json"),
                                    add("docs/evidence/brief-24/receipt.md"),
                                    mod("PROJECT_STATE.md")), self.EDITORIAL)

    def test_docs_alone_stay_docs(self):
        # Markdown receipts were already source-neutral docs before this lane.
        for path in ("docs/ROADMAP.md", "docs/evidence/brief-24/receipt.md"):
            with self.subTest(path=path):
                self.assertEqual(self.scope(mod(path)), Scope("docs", False, False))

    def test_historical_brief_prs_that_also_pin_tests_or_scripts_are_full(self):
        # Shape of merged Brief PRs to date: content plus per-Brief pins in
        # tests/ or scripts/. Any code path takes the whole PR to full CI.
        for extra in (mod("tests/test_brief_publication.py"), add("tests/test_brief_23.py"),
                      mod("scripts/guard_briefs_render_scope.py"), mod("site/render.py"),
                      mod("site/preview/templates/brief.html"), mod("site/preview/brief.css"),
                      mod(".github/workflows/briefs_render_only_release.yml"),
                      mod("site/assets/timelines/x.webp"), mod("pla_watch.db")):
            with self.subTest(extra=extra[3]):
                self.assertEqual(self.scope(add("briefs/brief-24.json"), extra).mode, "full")

    def test_unsafe_entry_shapes_fail_closed(self):
        cases = {
            "deletion": ("100644", "000000", "D", "briefs/brief-03.json"),
            "symlink": add("briefs/brief-24.json", mode="120000"),
            "executable": add("briefs/brief-24.json", mode="100755"),
            "mode change": mod("briefs/brief-24.json", old="100755"),
            "type change": ("120000", "100644", "T", "briefs/brief-24.json"),
            "submodule": add("briefs/media/x.json", mode="160000"),
            "nested": add("briefs/drafts/brief-24.json"),
            "deep evidence": add("docs/evidence/brief-24/sub/approval.json"),
            "evidence at root": add("docs/evidence/approval.json"),
            "unknown extension": add("briefs/brief-24.py"),
            "image in briefs root": add("briefs/cover.webp"),
            "svg asset": add("site/assets/catalogue/media/x.svg"),
            "dotfile": add("briefs/.brief-24.json"),
            "other staff file": add("site/preview/staff.yaml"),
            "traversal": add("briefs/../scripts/x.json"),
        }
        for name, record in cases.items():
            with self.subTest(name):
                self.assertEqual(self.scope(record).mode, "full")
                self.assertEqual(self.scope(add("briefs/brief-24.json"), record).mode, "full")

    def test_unsafe_documentation_entries_cannot_enter_any_reduced_lane(self):
        unsafe = {
            "deleted doc": ("100644", "000000", "D", "docs/OLD.md"),
            "symlinked doc": add("docs/LINK.md", mode="120000"),
            "executable doc": add("docs/RUN.md", mode="100755"),
            "doc mode change": mod("docs/ROADMAP.md", old="100644", new="100755"),
            "doc type change": ("120000", "100644", "T", "docs/ROADMAP.md"),
            "deleted root doc": ("100644", "000000", "D", "PROJECT_STATE.md"),
            "deleted evidence receipt": ("100644", "000000", "D", "docs/evidence/b/r.md"),
        }
        brief = add("briefs/brief-24.json")
        timeline = mod("site/preview/timelines.css")
        for name, record in unsafe.items():
            with self.subTest(name):
                self.assertEqual(self.scope(record), Scope("full", True, False))
                # Mixed Brief + documentation, and docs + focused timeline.
                self.assertEqual(self.scope(brief, record), Scope("full", True, False))
                self.assertEqual(self.scope(timeline, record), Scope("full", True, False))

    def test_unsafe_timeline_entries_cannot_enter_focused(self):
        for record in (("100644", "000000", "D", "site/assets/timelines/x.webp"),
                       add("site/assets/timelines/x.webp", mode="120000"),
                       mod("site/preview/timelines.css", old="100755")):
            with self.subTest(record=record):
                self.assertEqual(self.scope(record), Scope("full", True, False))

    def test_safe_documentation_mixes_keep_their_lane(self):
        self.assertEqual(self.scope(add("docs/NEW.md"), mod("README.md")),
                         Scope("docs", False, False))
        self.assertEqual(self.scope(mod("site/preview/timelines.css"), add("docs/NEW.md")),
                         Scope("focused", True, False))
        self.assertEqual(self.scope(add("briefs/brief-24.json"), add("docs/NEW.md")),
                         self.EDITORIAL)

    def test_unsafe_entry_keeps_replay_flag_and_never_downgrades(self):
        deleted_pilot = ("100644", "000000", "D", "research/topic_pilot_v1/x.json")
        self.assertEqual(self.scope(deleted_pilot), Scope("full", True, True))
        self.assertEqual(self.scope(deleted_pilot, add("docs/NEW.md")), Scope("full", True, True))
        for scope in (Scope("full", True, True), Scope("data", False, False)):
            self.assertIs(require_safe_entries(scope, parse_raw(raw(
                ("100644", "000000", "D", "docs/OLD.md")))), scope)

    def test_editorial_never_yields_reusable_full_qualification(self):
        # code_qualification reuses only "full" runs; the lane can never be one.
        self.assertNotEqual(self.scope(add("briefs/brief-24.json")).mode, "full")


if __name__ == "__main__":
    unittest.main()
