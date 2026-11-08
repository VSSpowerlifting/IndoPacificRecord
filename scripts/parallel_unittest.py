"""Run the complete offline unittest suite across worker processes.

``python -m scripts.parallel_unittest -s tests -t . -v`` is the parallel
equivalent of ``python -m unittest discover -s tests -t . -v``:

* Discovery is the standard ``unittest`` discovery with the same start
  directory, top-level directory and pattern, so a new ``tests/test_*.py``
  module is included automatically. Nothing is selected, filtered or skipped
  by this runner.
* Discovered tests are grouped by the module whose loading produced them
  (``load_tests`` hooks included), and every module runs in its own fresh
  interpreter, loaded by the same ``loadTestsFromModule(..., pattern)`` call.
  A long module without a ``load_tests`` hook is instead split by its
  ``TestCase`` classes, each loaded by ``loadTestsFromTestCase`` exactly as
  module loading does, so one slow file does not set the wall-clock time.
* ``--editorial`` runs the same discovery, then keeps only the modules
  matching ``scripts.pr_ci_scope.EDITORIAL_TEST_PATTERNS`` (each pattern
  must match a discovered module). It is the editorial-only PR lane, never
  the full suite, and never yields full-qualification evidence.
* Completion is proved, not assumed: for every module the multiset of test
  ids the worker actually started must equal the multiset discovery
  produced; ids may be absent only when a recorded class/module-level skip
  covers them. An import error, a crashed or silent worker, a mismatch, a
  failure, an error or an unexpected success makes the run exit non-zero.

The scheduling weights below are only an ordering hint (measured on hosted
CI run 42433257153) so the longest modules start first; unknown modules
fall back to their test count. Weights never decide whether a test runs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import fnmatch
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest


MEASURED_SECONDS = {
    "tests.test_preview_prototype": 291,
    "tests.test_homepage_intro": 144,
    "tests.test_pla_watch_veil_contrast": 141,
    "tests.test_vietnam_daily_pipeline": 136,
    "tests.test_shadow_review_evidence_chain": 53,
    "tests.test_vietnam_private_custody": 52,
    "tests.test_shadow_review_publisher": 52,
    "tests.test_indo_pacific_identity": 46,
    "tests.test_vietnam_daily_handoff": 45,
    "tests.test_identity_assets": 44,
    "tests.test_ph_afp_release_validator": 44,
    "tests.test_vietnam_official_link_admission": 41,
    "tests.test_vietnam_ministry_remote_review": 41,
    "tests.test_source_occurrences_browser": 39,
    "tests.test_indonesia_kemhan_release_validator": 38,
    "tests.test_briefs_collection": 35,
    "tests.test_desk_rollout_contract": 32,
    "tests.test_timeline_rendering": 32,
    "tests.test_dossier_rendering": 32,
    "tests.test_host_gate": 27,
    "tests.test_vietnam_atomic_link_admission": 27,
    "tests.test_source_occurrences_scale": 25,
    "tests.test_pla_watch_reading_ergonomics": 24,
    "tests.test_archive_integration_browser": 23,
    "tests.test_public_chrome_is_truthful": 23,
}

# Modules at least this slow (seconds, per the weights above) run one worker
# per TestCase class when that is provably the same set of tests.
SPLIT_SECONDS = 40

_LEVEL_SKIP = re.compile(r"^(setUpClass|setUpModule) \(([\w.]+)\)$")


def iter_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_ids(item)
        else:
            yield item.id()


class RecordingLoader(unittest.TestLoader):
    """Standard discovery that remembers which module produced each test."""

    def __init__(self):
        super().__init__()
        self.by_module: dict[str, list[str]] = {}
        self._depth = 0

    def loadTestsFromModule(self, module, *args, pattern=None, **kws):
        # A module's load_tests hook may load another module through this
        # loader; those tests belong to the outer module's suite, exactly as
        # in a serial discover run, so only discovery's own calls are keyed.
        self._depth += 1
        try:
            suite = super().loadTestsFromModule(module, *args, pattern=pattern, **kws)
        finally:
            self._depth -= 1
        if self._depth == 0:
            if module.__name__ in self.by_module:
                raise SystemExit("module loaded twice by discovery: " + module.__name__)
            self.by_module[module.__name__] = list(iter_ids(suite))
        return suite


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kws):
        super().__init__(*args, **kws)
        self.started: list[str] = []
        self.level_skips: list[str] = []

    def startTest(self, test):
        self.started.append(test.id())
        super().startTest(test)

    def addSkip(self, test, reason):
        match = _LEVEL_SKIP.match(str(test))
        if not isinstance(test, unittest.TestCase) and match:
            self.level_skips.append(match.group(2))
        super().addSkip(test, reason)


def run_worker(unit: str, pattern: str, verbosity: int, out: Path,
               test_class: str | None = None) -> int:
    loader = unittest.TestLoader()
    if test_class:
        module = importlib.import_module(unit.rpartition(".")[0])
        suite = loader.loadTestsFromTestCase(getattr(module, test_class))
    else:
        suite = loader.loadTestsFromModule(importlib.import_module(unit),
                                           pattern=pattern)
    runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=verbosity,
                                     resultclass=RecordingResult)
    result = runner.run(suite)
    describe = lambda pairs: [[str(t), text] for t, text in pairs]
    out.write_text(json.dumps({
        "unit": unit,
        "started": result.started,
        "level_skips": result.level_skips,
        "tests_run": result.testsRun,
        "failures": describe(result.failures),
        "errors": describe(result.errors) + [["loader", e] for e in loader.errors],
        "skipped": describe(result.skipped),
        "expected_failures": describe(result.expectedFailures),
        "unexpected_successes": [str(t) for t in result.unexpectedSuccesses],
    }), encoding="utf-8")
    return 0 if result.wasSuccessful() and not loader.errors else 1


def check_module(expected: list[str], report: dict) -> list[str]:
    """Return completeness problems; empty means every discovered test ran."""
    want, got = Counter(expected), Counter(report["started"])
    problems = []
    extra = got - want
    if extra:
        problems.append("ran tests discovery did not produce: %s" % sorted(extra))
    missing = want - got
    covered = tuple(name + "." for name in report["level_skips"])
    uncovered = sorted(t for t in missing.elements() if not t.startswith(covered))
    if uncovered:
        problems.append("discovered tests that never started: %s" % uncovered)
    return problems


def weight(module: str, count: int) -> float:
    return MEASURED_SECONDS.get(module, 0.1 * count)


def units_for(module: str, ids: list[str], loaded) -> dict[str, tuple[str | None, list[str]]]:
    """Map run units to (TestCase class name or None, discovered ids).

    A module is split only when every discovered id is ``module.Class.test``
    for a ``TestCase`` class that is a module attribute and there is no
    ``load_tests`` hook; otherwise it runs whole. Either way the units'
    ids partition exactly the module's discovered ids.
    """
    whole = {module: (None, ids)}
    if (weight(module, len(ids)) < SPLIT_SECONDS or loaded is None
            or hasattr(loaded, "load_tests")):
        return whole
    split: dict[str, tuple[str | None, list[str]]] = {}
    for test_id in ids:
        rest = test_id[len(module) + 1:] if test_id.startswith(module + ".") else ""
        name, _, method = rest.partition(".")
        cls = getattr(loaded, name, None) if name and method and "." not in method else None
        if not (isinstance(cls, type) and issubclass(cls, unittest.TestCase)):
            return whole
        split.setdefault(module + "." + name, (name, []))[1].append(test_id)
    return split


def select_modules(modules: dict[str, list[str]], patterns) -> tuple[dict[str, list[str]], list[str]]:
    """Keep modules matching any pattern; also return patterns matching none."""
    unmatched = [p for p in patterns
                 if not any(fnmatch.fnmatchcase(m, p) for m in modules)]
    kept = {m: ids for m, ids in modules.items()
            if any(fnmatch.fnmatchcase(m, p) for p in patterns)}
    return kept, unmatched


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-s", "--start-directory", default=".")
    ap.add_argument("-t", "--top-level-directory", default=None)
    ap.add_argument("-p", "--pattern", default="test*.py")
    ap.add_argument("-v", "--verbose", action="store_const", const=2, default=1,
                    dest="verbosity")
    ap.add_argument("-j", "--workers", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--editorial", action="store_true",
                    help="run only the editorial-lane modules (not the full suite)")
    ap.add_argument("--worker", metavar="MODULE", help=argparse.SUPPRESS)
    ap.add_argument("--report", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--test-class", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    top = os.path.abspath(args.top_level_directory or args.start_directory)
    if top not in sys.path:
        sys.path.insert(0, top)
    if args.worker:
        return run_worker(args.worker, args.pattern, args.verbosity, args.report,
                          args.test_class)

    started = time.monotonic()
    loader = RecordingLoader()
    loader.discover(args.start_directory, pattern=args.pattern,
                    top_level_dir=args.top_level_directory)
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        print("FAILED: %d module(s) could not be imported during discovery"
              % len(loader.errors), file=sys.stderr)
        return 1
    modules = {m: ids for m, ids in loader.by_module.items() if ids}
    if args.editorial:
        from scripts.pr_ci_scope import EDITORIAL_TEST_PATTERNS
        modules, unmatched = select_modules(modules, EDITORIAL_TEST_PATTERNS)
        if unmatched:
            print("FAILED: editorial test patterns matched no discovered module: %s"
                  % unmatched, file=sys.stderr)
            return 1
    expected_total = sum(len(ids) for ids in modules.values())
    if not expected_total:
        print("FAILED: discovery produced no tests", file=sys.stderr)
        return 1
    units: dict[str, tuple[str | None, list[str]]] = {}
    unit_weight: dict[str, float] = {}
    for module, ids in modules.items():
        total = weight(module, len(ids))
        for unit, (cls, unit_ids) in units_for(module, ids, sys.modules.get(module)).items():
            units[unit] = (cls, unit_ids)
            unit_weight[unit] = total * len(unit_ids) / len(ids)
    if sorted(t for _, ids in units.values() for t in ids) != sorted(
            t for ids in modules.values() for t in ids):
        print("FAILED: run units do not partition the discovered tests", file=sys.stderr)
        return 1
    order = sorted(units, key=lambda u: -unit_weight[u])
    workers = max(1, min(args.workers, len(order)))
    print("%s: discovered %d tests in %d modules (%d run units); running on %d workers"
          % ("EDITORIAL LANE" if args.editorial else "Full suite",
             expected_total, len(modules), len(order), workers), flush=True)

    lock = threading.Lock()
    tmp = tempfile.TemporaryDirectory(prefix="ipr-parallel-unittest.")
    totals = Counter()
    problems: list[str] = []
    durations: dict[str, float] = {}

    def run_one(unit: str):
        report_path = Path(tmp.name) / (unit + ".json")
        cls = units[unit][0]
        began = time.monotonic()
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.parallel_unittest",
             "-t", top, "-p", args.pattern, "--worker", unit,
             "--report", str(report_path)]
            + (["--test-class", cls] if cls else [])
            + (["-v"] if args.verbosity > 1 else []),
            cwd=os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        return unit, proc, report_path, time.monotonic() - began

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_one, m) for m in order]
        for future in as_completed(futures):
            module, proc, report_path, seconds = future.result()
            durations[module] = seconds
            output = proc.stdout.decode("utf-8", "replace")
            local: list[str] = []
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                report = None
                local.append("worker exited %d without a result report" % proc.returncode)
            if report is not None:
                local.extend(check_module(units[module][1], report))
                totals["run"] += report["tests_run"]
                for key in ("failures", "errors", "skipped",
                            "expected_failures", "unexpected_successes"):
                    totals[key] += len(report[key])
                bad = (report["failures"] or report["errors"]
                       or report["unexpected_successes"])
                if bad and proc.returncode == 0:
                    local.append("worker reported problems but exited 0")
                if proc.returncode != 0 and not bad:
                    local.append("worker exited %d" % proc.returncode)
                if bad:
                    local.append("%d failure(s), %d error(s), %d unexpected success(es)"
                                 % (len(report["failures"]), len(report["errors"]),
                                    len(report["unexpected_successes"])))
            with lock:
                print("===== %s (%d tests, %.1fs, exit %d) =====" % (
                    module, len(units[module][1]), seconds, proc.returncode), flush=True)
                sys.stdout.write(output)
                for problem in local:
                    print("PROBLEM %s: %s" % (module, problem), flush=True)
                sys.stdout.flush()
                problems.extend("%s: %s" % (module, p) for p in local)
    tmp.cleanup()

    elapsed = time.monotonic() - started
    print("-" * 70)
    print("Slowest run units:")
    for module in sorted(durations, key=durations.get, reverse=True)[:15]:
        print("  %7.1fs  %s" % (durations[module], module))
    print("Ran %d tests in %.3fs (discovered %d, %d modules, %d run units, %d workers)"
          % (totals["run"], elapsed, expected_total, len(modules), len(order), workers))
    if problems:
        print("\nFAILED (failures=%d, errors=%d, unexpected successes=%d, "
              "incomplete or failed run units=%d)" % (
                  totals["failures"], totals["errors"],
                  totals["unexpected_successes"], len(problems)))
        for problem in problems:
            print("  " + problem)
        return 1
    extras = []
    if totals["skipped"]:
        extras.append("skipped=%d" % totals["skipped"])
    if totals["expected_failures"]:
        extras.append("expected failures=%d" % totals["expected_failures"])
    print("\nOK" + (" (%s)" % ", ".join(extras) if extras else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
