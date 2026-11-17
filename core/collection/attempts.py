"""Signed collection-attempt facts and the freshness verdict read from them.

A signed Daily envelope proves the private signer ran. It does not prove the
private collector's latest attempt succeeded: a failed attempt still commits a
ledger, so a fresh envelope can sit on top of a failed collection. The private
signer (a later change) carries a small, closed block of the ledger's own
facts inside the signed envelope; this module validates that block and turns
it into a run-result status.

``verdict`` and ``validate`` are pure. ``read_custody`` (the private signer's
side) reads a private custody checkout through ``git`` only and never raises.
Every string a verdict returns is built from validated
codes, dates and run identifiers only: ``error_detail`` is persisted and
rendered publicly, so no error text, URL or request data may reach it.
"""

import re
import subprocess
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


# --- Signer side: reduce a custody commit's ledgers to the closed facts -------

LEDGER_DIR = "state/ledger"
LEDGER_WINDOW = 20
_LEDGER_FIELDS = ("run_id", "target_date", "target_date_source", "finished_utc",
                  "result", "health")
_RUN_NUMBER = re.compile(r"([0-9]+)(?:-([0-9]+))?")
_GIT_TIMEOUT = 60


def unattested(family, commit, reason) -> dict:
    """A well-formed block that attests nothing, for any failure to read."""
    return {"schema": SCHEMA, "family": family, "custody_commit": commit,
            "attested": False, "reason": reason, "latest": None,
            "latest_healthy_target_date": None, "unledgered_exit": None}


def _git(repo, *args) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, timeout=_GIT_TIMEOUT).stdout


def _list(repo, commit, directory):
    """Sorted file names directly under ``directory`` at the commit; [] if absent."""
    probe = subprocess.run(["git", "-C", str(repo), "ls-tree", "--name-only", "-z",
                            commit, directory + "/"], capture_output=True,
                           timeout=_GIT_TIMEOUT)
    if probe.returncode != 0:
        # An absent directory lists as empty; a bad repo or commit is an error.
        _git(repo, "cat-file", "-e", commit + "^{commit}")
        return []
    names = [n.decode() for n in probe.stdout.split(b"\0") if n]
    return sorted(n.rsplit("/", 1)[-1] for n in names)


def _show_json(repo, commit, path):
    import json
    return json.loads(_git(repo, "show", commit + ":" + path))


def _reduce_ledger(ledger) -> dict:
    """The six allowlisted fields, validated; ValueError for anything else."""
    if not isinstance(ledger, dict):
        raise ValueError("ledger is not an object")
    entry = {k: ledger.get(k) for k in _LEDGER_FIELDS}
    ok = entry["result"] in collection_status.ALL_STATUSES
    entry["healthy"] = bool(ok and entry["result"] in collection_status.SUCCESS_STATUSES
                            and entry["health"] != "fail")
    if not _latest_ok(entry):
        raise ValueError("ledger fields are not well formed")
    return entry


def _run_key(run_id):
    """(run number, attempt) from a '<number>-<attempt>' run id; None otherwise."""
    m = _RUN_NUMBER.fullmatch(run_id) if isinstance(run_id, str) else None
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def _unledgered_exit(repo, commit, receipt_dirs, ledger_ids, latest_run_id):
    floor = _run_key(latest_run_id)
    if floor is None:
        return None
    best = None
    for directory in receipt_dirs:
        for name in _list(repo, commit, directory):
            run_id = name[:-5] if name.endswith(".json") else None
            key = _run_key(run_id)
            if key is None or key <= floor or run_id in ledger_ids:
                continue
            if not _RUN_ID.fullmatch(run_id):
                continue
            code = _show_json(repo, commit, directory + "/" + name).get(
                "collector_exit_status")
            if type(code) is not int:
                raise ValueError("receipt exit status is not an integer")
            if code != 0 and (best is None or key > best[0]):
                best = (key, {"run_id": run_id, "collector_exit_status": code})
    return best[1] if best else None


def read_custody(repo, commit, family, *, receipt_dirs=()) -> dict:
    """Closed collection facts from the newest ledgers at a custody commit.

    Total: always returns a dict that passes ``validate`` (for a well-formed
    ``commit``), attested False with a fixed reason when custody cannot be read.
    Only the six allowlisted ledger fields are copied; a ledger with any other
    value shape makes the whole read unattested rather than being skipped.
    """
    try:
        names = _list(repo, commit, LEDGER_DIR)
        if not names:
            return unattested(family, commit, "no_ledger")
        entries, ledger_ids = [], set()
        for name in names[-LEDGER_WINDOW:]:
            raw = _show_json(repo, commit, LEDGER_DIR + "/" + name)
            if isinstance(raw, dict) and raw.get("rehearsal") is True:
                if isinstance(raw.get("run_id"), str):
                    ledger_ids.add(raw["run_id"])  # still a ledger for its run
                continue
            entry = _reduce_ledger(raw)
            entries.append(entry)
            ledger_ids.add(entry["run_id"])
        if not entries:
            return unattested(family, commit, "no_ledger")
        entries.sort(key=lambda e: (_utc(e["finished_utc"]), e["run_id"]))
        latest = entries[-1]
        healthy_dates = [e["target_date"] for e in entries if e["healthy"]]
        facts = {"schema": SCHEMA, "family": family, "custody_commit": commit,
                 "attested": True, "reason": None, "latest": latest,
                 "latest_healthy_target_date": max(healthy_dates) if healthy_dates else None,
                 "unledgered_exit": _unledgered_exit(
                     repo, commit, receipt_dirs, ledger_ids, latest["run_id"])}
        return validate(facts) or unattested(family, commit, "ledger_unreadable")
    except Exception:
        return unattested(family, commit, "ledger_unreadable")
