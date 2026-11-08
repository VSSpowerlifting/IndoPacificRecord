"""The parallel suite runner must fail closed exactly where serial unittest does.

Each case builds a throwaway test package in a temporary directory and runs
the real runner over it as a subprocess, so discovery, worker processes and
completeness checking are all exercised end to end. No repository data,
network or tracked database is touched.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from unittest import mock

from scripts import parallel_unittest as pu
from scripts.pr_ci_scope import EDITORIAL_TEST_PATTERNS

ROOT = Path(__file__).resolve().parent.parent


class SuiteTree:
    def __init__(self, files):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-pu-test.")
        self.top = Path(self.tmp.name)
        pkg = self.top / "sample_suite"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        for name, body in files.items():
            (pkg / name).write_text(textwrap.dedent(body), encoding="utf-8")

    def run(self, *extra):
        return subprocess.run(
            [sys.executable, "-m", "scripts.parallel_unittest",
             "-s", str(self.top / "sample_suite"), "-t", str(self.top), "-j", "3", *extra],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            timeout=120)

    def serial_ids(self):
        loader = unittest.TestLoader()
        suite = loader.discover(str(self.top / "sample_suite"), top_level_dir=str(self.top))
        return sorted(pu.iter_ids(suite))

    def close(self):
        self.tmp.cleanup()


PASSING = """
    import unittest
    class A(unittest.TestCase):
        def test_one(self): pass
        def test_two(self): pass
"""


class TestEndToEnd(unittest.TestCase):
    def tree(self, files):
        tree = SuiteTree(files)
        self.addCleanup(tree.close)
        for module in [m for m in sys.modules if m.startswith("sample_suite")]:
            del sys.modules[module]
        return tree

    def test_complete_passing_suite_is_ok_and_counts_every_test(self):
        tree = self.tree({"test_a.py": PASSING, "test_b.py": PASSING})
        proc = tree.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("Ran 4 tests", proc.stdout)
        self.assertIn("discovered 4, 2 modules", proc.stdout)
        self.assertTrue(proc.stdout.rstrip().endswith("OK"), proc.stdout)

    def test_a_failing_test_fails_the_run(self):
        tree = self.tree({"test_a.py": PASSING, "test_bad.py": """
            import unittest
            class B(unittest.TestCase):
                def test_fails(self): self.fail("boom")
        """})
        proc = tree.run()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAILED (failures=1", proc.stdout)

    def test_an_import_error_fails_discovery(self):
        tree = self.tree({"test_a.py": PASSING,
                          "test_broken.py": "import a_module_that_does_not_exist\n"})
        proc = tree.run()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("could not be imported during discovery", proc.stdout)

    def test_a_silently_exiting_worker_is_not_success(self):
        tree = self.tree({"test_a.py": PASSING, "test_exit.py": """
            import os, unittest
            class C(unittest.TestCase):
                def test_exits(self): os._exit(0)
        """})
        proc = tree.run()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("without a result report", proc.stdout)

    def test_load_tests_hook_and_class_level_skip_match_serial(self):
        tree = self.tree({
            "test_hook.py": """
                import unittest
                class Hidden(unittest.TestCase):
                    def test_kept(self): pass
                    def test_dropped(self): pass
                def load_tests(loader, tests, pattern):
                    return unittest.TestSuite([Hidden("test_kept")])
            """,
            "test_skip.py": """
                import unittest
                class S(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls): raise unittest.SkipTest("no browser here")
                    def test_one(self): pass
                    def test_two(self): pass
            """,
        })
        self.assertEqual(len(tree.serial_ids()), 3)
        proc = tree.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("discovered 3, 2 modules", proc.stdout)

    def test_a_setup_class_error_is_a_failure_not_a_skip(self):
        tree = self.tree({"test_err.py": """
            import unittest
            class E(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise RuntimeError("browser did not launch")
                def test_one(self): pass
        """})
        proc = tree.run()
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_recording_discovery_equals_serial_discovery(self):
        tree = self.tree({"test_a.py": PASSING, "test_b.py": PASSING, "test_hook.py": """
            import unittest
            class H(unittest.TestCase):
                def test_x(self): pass
            def load_tests(loader, tests, pattern):
                tests.addTests(loader.loadTestsFromTestCase(H))
                return tests
        """})
        serial = tree.serial_ids()
        for module in [m for m in sys.modules if m.startswith("sample_suite")]:
            del sys.modules[module]
        sys.path.insert(0, str(tree.top))
        self.addCleanup(sys.path.remove, str(tree.top))
        loader = pu.RecordingLoader()
        loader.discover(str(tree.top / "sample_suite"), top_level_dir=str(tree.top))
        recorded = sorted(t for ids in loader.by_module.values() for t in ids)
        self.assertEqual(recorded, serial)
        self.assertEqual(len(serial), 6)


class TestCompletenessAndSplitting(unittest.TestCase):
    def test_missing_or_extra_ids_are_problems_unless_a_level_skip_covers_them(self):
        expected = ["m.A.test_1", "m.A.test_2", "m.B.test_1"]
        report = {"started": ["m.A.test_1"], "level_skips": []}
        self.assertTrue(pu.check_module(expected, report))
        report = {"started": ["m.A.test_1", "m.A.test_2"], "level_skips": ["m.B"]}
        self.assertEqual(pu.check_module(expected, report), [])
        report = {"started": expected + ["m.A.test_1"], "level_skips": []}
        self.assertTrue(pu.check_module(expected, report))

    def fake_module(self, hook=False):
        module = types.ModuleType("tests.test_fake")
        module.A = type("A", (unittest.TestCase,), {"test_1": lambda s: None})
        module.B = type("B", (unittest.TestCase,), {"test_1": lambda s: None})
        if hook:
            module.load_tests = lambda *a: None
        return module

    def test_slow_module_splits_into_a_partition_of_its_ids(self):
        ids = ["tests.test_fake.A.test_1", "tests.test_fake.B.test_1"]
        with mock.patch.dict(pu.MEASURED_SECONDS, {"tests.test_fake": 100}):
            units = pu.units_for("tests.test_fake", ids, self.fake_module())
        self.assertEqual(set(units), {"tests.test_fake.A", "tests.test_fake.B"})
        self.assertEqual(sorted(t for _, u in units.values() for t in u), ids)

    def test_hook_fast_or_unusual_modules_run_whole(self):
        ids = ["tests.test_fake.A.test_1", "tests.test_fake.B.test_1"]
        whole = {"tests.test_fake": (None, ids)}
        with mock.patch.dict(pu.MEASURED_SECONDS, {"tests.test_fake": 100}):
            self.assertEqual(pu.units_for("tests.test_fake", ids, self.fake_module(True)), whole)
            self.assertEqual(pu.units_for("tests.test_fake", ids, None), whole)
            odd = ids + ["tests.test_fake.Missing.test_1"]
            self.assertEqual(pu.units_for("tests.test_fake", odd, self.fake_module()),
                             {"tests.test_fake": (None, odd)})
        self.assertEqual(pu.units_for("tests.test_fake", ids, self.fake_module()), whole)


class TestEditorialLane(unittest.TestCase):
    # Any test module mentioning a governed editorial input must run in the
    # editorial lane, so a new Brief/media/credit reader cannot fall outside it.
    READS_EDITORIAL_INPUT = re.compile(
        r'"briefs"|briefs/|staff\.json|catalogue/admissions|admissions\.json'
        r'|editorial/manifest|docs/evidence|BRIEFS_DIR|catalogue/media|assets/editorial')
    # Lane-selection tests name editorial paths as literals but read none.
    NOT_READERS = {"tests.test_parallel_unittest", "tests.test_pr_ci_scope"}

    def test_every_editorial_input_reader_is_in_the_lane(self):
        readers = [
            "tests." + f.stem for f in sorted((ROOT / "tests").glob("test*.py"))
            if self.READS_EDITORIAL_INPUT.search(f.read_text(encoding="utf-8"))
            and "tests." + f.stem not in self.NOT_READERS
        ]
        self.assertGreater(len(readers), 20)
        kept, _ = pu.select_modules({m: ["x"] for m in readers}, EDITORIAL_TEST_PATTERNS)
        self.assertEqual(sorted(set(readers) - set(kept)), [])

    def test_every_pattern_names_an_existing_test_module(self):
        modules = {"tests." + f.stem: ["x"] for f in (ROOT / "tests").glob("test*.py")}
        _, unmatched = pu.select_modules(modules, EDITORIAL_TEST_PATTERNS)
        self.assertEqual(unmatched, [])

    def test_selection_filters_and_reports_unmatched_patterns(self):
        modules = {"tests.test_brief_cover": ["a"], "tests.test_briefs_x": ["b"],
                   "tests.test_pipeline": ["c"]}
        kept, unmatched = pu.select_modules(
            modules, ("tests.test_brief_*", "tests.test_briefs_*", "tests.test_gone"))
        self.assertEqual(set(kept), {"tests.test_brief_cover", "tests.test_briefs_x"})
        self.assertEqual(unmatched, ["tests.test_gone"])

    def test_editorial_run_fails_when_a_pattern_matches_nothing(self):
        tree = SuiteTree({"test_a.py": PASSING})
        self.addCleanup(tree.close)
        proc = tree.run("--editorial")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("editorial test patterns matched no discovered module", proc.stdout)


if __name__ == "__main__":
    unittest.main()
