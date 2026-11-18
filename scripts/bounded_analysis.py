"""Bounded, ordered article analysis without concurrent database writes.

Workers may perform independent external-model calls concurrently. Results are
consumed in queue order by the caller, which alone owns SQLite writes and
processing-failure bookkeeping. At most `workers` articles are dispatched,
including on fatal account errors; no eager submission of the whole backlog.
"""

from collections import deque
from concurrent.futures import ThreadPoolExecutor


def process_bounded(items, work, consume, *, workers, fatal_error, on_fatal):
    """Process an iterable with bounded prefetch and ordered result commits.

    `on_fatal(item, error)` records a terminal account-level failure. Any
    already-running peer request may finish, but its result is never committed
    after the first fatal queue position. Unsubmitted items stay retryable.
    Non-fatal processing failures remain values for the caller to persist.
    Unexpected exceptions still fail the pipeline, as in the serial version.
    """
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= 3:
        raise ValueError("analysis workers must be an integer between 1 and 3")

    # Keep the historical path free of executor startup and speculative calls.
    if workers == 1:
        for item in items:
            try:
                result = work(item)
            except fatal_error as exc:
                on_fatal(item, exc)
                break
            consume(item, result)
        return

    source = iter(items)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ipr-analysis") as pool:
        outstanding = deque()

        def submit_one():
            try:
                item = next(source)
            except StopIteration:
                return
            outstanding.append((item, pool.submit(work, item)))

        for _ in range(workers):
            submit_one()

        while outstanding:
            item, future = outstanding.popleft()
            try:
                result = future.result()
            except fatal_error as exc:
                # Cancel anything not yet started. In-flight calls are allowed
                # to finish so usage accounting captures their actual cost.
                for _, pending in outstanding:
                    pending.cancel()
                on_fatal(item, exc)
                break
            consume(item, result)
            # Submit exactly one replacement only after the ordered result has
            # been persisted, bounding both cost exposure and memory.
            submit_one()
