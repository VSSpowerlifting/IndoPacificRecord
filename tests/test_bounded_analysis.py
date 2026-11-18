"""Offline contracts for ordered, cost-bounded Daily analysis scheduling."""

import threading
import time
import unittest

from scripts.bounded_analysis import process_bounded


class AccountBlocked(Exception):
    pass


class BoundedAnalysisTests(unittest.TestCase):
    def test_one_worker_preserves_serial_order_and_no_prefetch(self):
        events = []

        def work(item):
            events.append(("work", item))
            return item * 2

        def consume(item, result):
            events.append(("write", item, result))

        process_bounded(range(4), work, consume, workers=1,
                        fatal_error=AccountBlocked, on_fatal=lambda *_: self.fail("fatal"))
        self.assertEqual(events, [
            ("work", 0), ("write", 0, 0),
            ("work", 1), ("write", 1, 2),
            ("work", 2), ("write", 2, 4),
            ("work", 3), ("write", 3, 6),
        ])

    def test_parallel_calls_are_bounded_and_results_commit_in_queue_order(self):
        lock = threading.Lock()
        active = 0
        peak = 0
        writes = []

        def work(item):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.025 if item == 0 else 0.004)
            with lock:
                active -= 1
            return item * 2

        process_bounded(range(8), work, lambda item, value: writes.append((item, value)),
                        workers=2, fatal_error=AccountBlocked,
                        on_fatal=lambda *_: self.fail("fatal"))
        self.assertEqual(writes, [(i, i * 2) for i in range(8)])
        self.assertLessEqual(peak, 2)
        self.assertEqual(peak, 2)

    def test_fatal_cancels_tail_and_never_commits_speculative_result(self):
        gate = threading.Event()
        both_started = threading.Barrier(2)
        started = []
        writes = []
        failures = []
        lock = threading.Lock()

        def work(item):
            with lock:
                started.append(item)
            both_started.wait(timeout=2)
            if item == 0:
                raise AccountBlocked("credit exhausted")
            gate.wait(timeout=2)
            return item

        def on_fatal(item, error):
            failures.append((item, str(error)))
            gate.set()

        process_bounded(range(8), work, lambda item, value: writes.append(item),
                        workers=2, fatal_error=AccountBlocked, on_fatal=on_fatal)
        self.assertEqual(failures, [(0, "credit exhausted")])
        self.assertEqual(writes, [])
        self.assertEqual(sorted(started), [0, 1])

    def test_later_fatal_stops_dispatch_while_earlier_result_is_pending(self):
        # A later worker can discover a 402 before the first queued request
        # completes. Do not dispatch article 2 while waiting to commit 0.
        allow_first_finish = threading.Event()
        later_failed = threading.Event()
        started = []
        writes = []
        fatals = []
        lock = threading.Lock()

        def work(item):
            with lock:
                started.append(item)
            if item == 0:
                self.assertTrue(allow_first_finish.wait(timeout=3))
                return item
            if item == 1:
                later_failed.set()
                raise AccountBlocked("credit exhausted")
            return item

        def release_first_after_second_fails():
            try:
                self.assertTrue(later_failed.wait(timeout=3))
                # Let the executor wrapper mark the fatal condition before
                # releasing the earlier result into the commit loop.
                time.sleep(0.05)
            finally:
                allow_first_finish.set()

        releaser = threading.Thread(target=release_first_after_second_fails)
        releaser.start()
        try:
            process_bounded(
                range(8), work, lambda item, _: writes.append(item),
                workers=2, fatal_error=AccountBlocked,
                on_fatal=lambda item, exc: fatals.append((item, str(exc))),
            )
        finally:
            allow_first_finish.set()
            releaser.join(timeout=3)

        self.assertFalse(releaser.is_alive())
        self.assertEqual(started, [0, 1])
        self.assertEqual(writes, [0])
        self.assertEqual(fatals, [(1, "credit exhausted")])

    def test_nonfatal_empty_result_is_persisted_and_unexpected_errors_propagate(self):
        writes = []
        process_bounded([1, 2], lambda item: None if item == 1 else item,
                        lambda item, result: writes.append((item, result)),
                        workers=2, fatal_error=AccountBlocked,
                        on_fatal=lambda *_: self.fail("fatal"))
        self.assertEqual(writes, [(1, None), (2, 2)])
        with self.assertRaisesRegex(RuntimeError, "unexpected"):
            process_bounded([1], lambda _: (_ for _ in ()).throw(RuntimeError("unexpected")),
                            lambda *_: self.fail("should not commit"),
                            workers=2, fatal_error=AccountBlocked,
                            on_fatal=lambda *_: self.fail("fatal"))

    def test_analyzer_failure_context_is_isolated_between_article_threads(self):
        # Test the actual Analyzer attribute used by the pipeline, with no
        # network calls or API client construction.
        from concurrent.futures import ThreadPoolExecutor
        from analysis.analyzer import Analyzer

        analyzer = Analyzer.__new__(Analyzer)
        barrier = threading.Barrier(2)

        def remember(value):
            analyzer.last_relevance_failure = value
            barrier.wait(timeout=2)
            return analyzer.last_relevance_failure

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(remember, "invalid_response")
            second = pool.submit(remember, "api_error")
            self.assertEqual(first.result(), "invalid_response")
            self.assertEqual(second.result(), "api_error")

    def test_invalid_environment_workers_fall_back_to_serial(self):
        from config import _daily_analysis_workers
        self.assertEqual(_daily_analysis_workers("2"), 2)
        self.assertEqual(_daily_analysis_workers("999"), 3)
        for raw in (None, "", "invalid", "0", "-2"):
            with self.subTest(raw=raw):
                self.assertEqual(_daily_analysis_workers(raw), 1)

    def test_out_of_bounds_worker_counts_fail_before_dispatch(self):
        for workers in (0, 4, -1, "2", True, None):
            with self.subTest(workers=workers):
                with self.assertRaises(ValueError):
                    process_bounded([1], lambda _: self.fail("dispatched"),
                                    lambda *_: self.fail("committed"), workers=workers,
                                    fatal_error=AccountBlocked,
                                    on_fatal=lambda *_: self.fail("fatal"))


if __name__ == "__main__":
    unittest.main()
