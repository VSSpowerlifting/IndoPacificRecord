"""Signed collection-attempt facts and the freshness verdict read from them.

A signed Daily envelope proves the private signer ran. It does not prove the
private collector's latest attempt succeeded: a failed attempt still commits a
ledger, so a fresh envelope can sit on top of a failed collection. The private
signer (a later change) carries a small, closed block of the ledger's own
facts inside the signed envelope; this module validates that block and turns
it into a run-result status.

Pure functions, no I/O. Every string a verdict returns is built from validated
codes, dates and run identifiers only: ``error_detail`` is persisted and
rendered publicly, so no error text, URL or request data may reach it.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from core.collection import status as collection_status
from core.shadow_schedule import SOURCES as TARGET_DATE_SOURCES
from core.shadow_schedule import ScheduleError, scheduled_slot_date

SCHEMA = "ipr-collection-attempts/1"

_KEYS = {"schema", "family", "custody_commit", "attested", "reason", "latest",
         "latest_healthy_target_date", "unledgered_exit"}
_LATEST_KEYS = {"run_id", "target_date", "target_date_source", "finished_utc",
                "result", "health", "healthy"}
_EXIT_KEYS = {"run_id", "collector_exit_status"}
_RUN_ID = re.compile(r"[A-Za-z0-9_.-]{1,80}\Z")
_COMMIT = re.compile(r"[a-f0-9]{40}\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_CODE = re.compile(r"[a-z0-9_]{1,80}\Z")
_HEALTH = ("ok", "partial", "fail")


def _date(value) -> Optional[object]:
    if not (isinstance(value, str) and _DATE.fullmatch(value)):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _utc(value) -> Optional[datetime]:
    """An aware UTC instant from a Z or +00:00 stamp; None for anything else."""
    if not (isinstance(value, str) and (value.endswith("Z") or value.endswith("+00:00"))):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _latest_ok(latest) -> bool:
    return (isinstance(latest, dict) and set(latest) == _LATEST_KEYS
            and isinstance(latest["run_id"], str) and bool(_RUN_ID.fullmatch(latest["run_id"]))
            and _date(latest["target_date"]) is not None
            and latest["target_date_source"] in TARGET_DATE_SOURCES
            and _utc(latest["finished_utc"]) is not None
            and latest["result"] in collection_status.ALL_STATUSES
            and (latest["health"] is None or latest["health"] in _HEALTH)
            and type(latest["healthy"]) is bool)


def _exit_ok(value) -> bool:
    return (isinstance(value, dict) and set(value) == _EXIT_KEYS
            and isinstance(value["run_id"], str) and bool(_RUN_ID.fullmatch(value["run_id"]))
            and type(value["collector_exit_status"]) is int)


def validate(obj) -> Optional[dict]:
    """The facts object when it is exactly well formed, else None. Never raises."""
    try:
        if not (isinstance(obj, dict) and set(obj) == _KEYS and obj["schema"] == SCHEMA
                and isinstance(obj["family"], str) and obj["family"]
                and isinstance(obj["custody_commit"], str)
                and _COMMIT.fullmatch(obj["custody_commit"])
                and type(obj["attested"]) is bool
                and (obj["reason"] is None
                     or (isinstance(obj["reason"], str) and _CODE.fullmatch(obj["reason"])))
                and (obj["latest"] is None or _latest_ok(obj["latest"]))
                and (obj["latest_healthy_target_date"] is None
                     or _date(obj["latest_healthy_target_date"]) is not None)
                and (obj["unledgered_exit"] is None or _exit_ok(obj["unledgered_exit"]))):
            return None
        return obj
    except (KeyError, TypeError, ValueError):
        return None


def _code(value) -> str:
    return value if isinstance(value, str) and _CODE.fullmatch(value) else "unclassified"


def verdict(facts, *, now: datetime, cron_utc: Optional[str], grace_hours: int,
            require_attestation: bool) -> Optional[Tuple[str, str]]:
    """(status, fixed detail) when the facts show a failed or stale collection.

    None means no objection: either the facts are healthy and current, or none
    were supplied and attestation is not yet required. Precedence: missing
    facts, explicit non-attestation, a failed latest attempt, an exit with no
    ledger, then staleness of the latest healthy target date.
    """
    if facts is None:
        if require_attestation and cron_utc is not None:
            return collection_status.FETCH_FAILURE, "collection_not_attested"
        return None
    if not isinstance(facts, dict):
        return collection_status.FETCH_FAILURE, "collection_not_attested"
    if facts.get("attested") is not True:
        return (collection_status.FETCH_FAILURE,
                "collection_not_attested: %s" % _code(facts.get("reason")))
    latest = facts.get("latest")
    if isinstance(latest, dict):
        result, health = latest.get("result"), latest.get("health")
        if result in collection_status.FAILURE_STATUSES or health == "fail":
            status = (result if result in collection_status.FAILURE_STATUSES
                      else collection_status.FETCH_FAILURE)
            # A failed health with a non-failure result is named as such, so
            # the public detail never reads "collection ok" for a failure.
            what = (_code(result) if result in collection_status.FAILURE_STATUSES
                    else "health_fail (result %s)" % _code(result))
            return status, "collection %s (run %s, target %s)" % (
                what, _safe_run(latest.get("run_id")),
                _safe_date(latest.get("target_date")))
    exit_ = facts.get("unledgered_exit")
    if isinstance(exit_, dict):
        code = exit_.get("collector_exit_status")
        return (collection_status.FETCH_FAILURE,
                "collector exited %s without a ledger (run %s)" % (
                    code if type(code) is int else "unknown", _safe_run(exit_.get("run_id"))))
    if cron_utc is not None:
        try:
            expected = scheduled_slot_date(now - timedelta(hours=grace_hours), cron_utc)
        except ScheduleError:
            return None
        healthy = _date(facts.get("latest_healthy_target_date"))
        if healthy is None or healthy < expected:
            return (collection_status.FETCH_FAILURE,
                    "collection stale: last healthy target %s (latest run %s); "
                    "expected slot %s" % (
                        healthy.isoformat() if healthy else "none",
                        _safe_run(latest.get("run_id")) if isinstance(latest, dict) else "none",
                        expected.isoformat()))
    return None


def _safe_run(value) -> str:
    return value if isinstance(value, str) and _RUN_ID.fullmatch(value) else "unidentified"


def _safe_date(value) -> str:
    return value if _date(value) is not None else "unknown"
