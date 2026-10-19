"""Bounded continuity of observed official RSS snapshots, never an archive claim.

Keep the six-day window. Join snapshots only across a surviving identity and
refuse withdrawals above the newer feed's truncation boundary. New entries
inserted behind the head (late publication) are collected too. An entire feed
turnover, changed timestamp, or missing snapshot fails closed.
"""
from datetime import datetime


def stitch(snapshots, start, end):
    if not snapshots or len(snapshots) > 64:
        raise ValueError("RSS snapshot budget exceeded or empty")
    snapshots = sorted(snapshots, key=lambda s: s["retrieved_at"])
    boundary = [n for n, s in enumerate(snapshots)
                if s["items"][-1]["date"] < start]
    if not boundary:
        raise ValueError("RSS history has no proven window boundary")
    chain = snapshots[boundary[-1]:]
    union = {}
    previous = None
    for snapshot in chain:
        items = snapshot["items"]
        stamps = [datetime.fromisoformat(i["rss_instant_utc"]) for i in items]
        if stamps != sorted(stamps, reverse=True):
            raise ValueError("RSS is not newest-first by declared instant")
        current = {i["url"]: i for i in items}
        if len(current) != len(items):
            raise ValueError("RSS repeats an identity")
        if previous is not None:
            if not set(previous) & set(current):
                raise ValueError("RSS frontier lost: no surviving identity; recovery required")
            tail = stamps[-1]
            required = {u for u, i in previous.items()
                        if datetime.fromisoformat(i["rss_instant_utc"]) >= tail}
            if not required <= set(current):
                raise ValueError("RSS item disappeared above the truncation boundary")
        for url, item in current.items():
            if url in union and union[url]["rss_instant_utc"] != item["rss_instant_utc"]:
                raise ValueError("RSS identity publication timestamp changed")
            union[url] = item
        previous = current
    selected = [i for i in union.values() if start <= i["date"] <= end]
    selected.sort(key=lambda i: (i["rss_instant_utc"], i["url"]), reverse=True)
    return selected, [s["sha256"] for s in chain]
