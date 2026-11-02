"""Offline Track C routing between the Saturday packet, one analyst and Dylan.

Nothing here is scheduled or wired to a workflow (2026-11-01 workflow freeze).
The analyst transport must be injected: there is no default SMTP, so no live
analyst send is possible from this module. The editor send stays Track A
``deliver(..., analyst_routing=True)`` with its owner exact-SHA approval and
once-only editor reservation; Dylan receives only the provisional manuscript or
the owner-reconciled exact revision, never an analyst's returned file.

The private directory must be durable host storage that survives runners and
restarts. Code can only refuse locations known to be ephemeral; choosing real
durable storage is an activation prerequisite, not something verified here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from config import DB_PATH
from core.brief_analyst_packet import HEX, digest, validate_manifest
from scripts.saturday_sunday_briefs import (MARKER, NY, collection_window, compare,
                                            digest as cycle_digest, inventory,
                                            private_directory, write_private)

UPSTREAM_NAME = "Daily PLA Watch Update"
UPSTREAM_PATH = ".github/workflows/daily_update.yml"
REQUIRED_STEPS = ("Run pipeline", "Validate rendered output",
                  "Deploy to GitHub Pages", "Record successful run")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
ROSTER_SCHEMA = "ipr-analyst-roster/1"
SCOPE = "analyst-review-manuscript-and-links-only"
EDITOR_DEADLINE = time(21, 0)  # Dylan's packet is due by Saturday 9 p.m. New York


class DailyCompletionRefused(ValueError):
    pass


class NoNewCollection(DailyCompletionRefused):
    """Expected silent no-op: wrong day, or a green run that skipped collection."""


def daily_completion(event, jobs, *, phase, repo, marker, now):
    """Reconfirm the original successful scheduled Daily run for this phase.

    Ported from #807 ``verify`` and generalized to Saturday and Sunday. Pure:
    the caller supplies the workflow_run event, its jobs JSON and the marker.
    """
    if phase not in ("saturday", "sunday"):
        raise DailyCompletionRefused("unknown cycle phase")
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise DailyCompletionRefused("invalid repository")
    if now.tzinfo is None or now.utcoffset() is None:
        raise DailyCompletionRefused("timezone-aware clock required")
    today = now.astimezone(NY).date()
    if today.weekday() != (5 if phase == "saturday" else 6):
        raise NoNewCollection("not " + phase + " in New York")
    if not isinstance(event, dict) or not isinstance(event.get("workflow_run"), dict):
        raise DailyCompletionRefused("missing upstream workflow event")
    run = event["workflow_run"]
    if (run.get("name") != UPSTREAM_NAME or run.get("path") != UPSTREAM_PATH
            or run.get("event") != "schedule" or run.get("head_branch") != "main"
            or run.get("conclusion") != "success" or run.get("status") != "completed"
            or type(run.get("run_attempt")) is not int or run["run_attempt"] != 1
            or not isinstance(run.get("head_repository"), dict)
            or run["head_repository"].get("full_name") != repo
            or not isinstance(event.get("repository"), dict)
            or event["repository"].get("full_name") != repo):
        raise DailyCompletionRefused("not the original successful main scheduled collection")
    if type(run.get("id")) is not int or run["id"] <= 0:
        raise DailyCompletionRefused("missing upstream run id")
    if not isinstance(jobs, dict) or not isinstance(jobs.get("jobs"), list):
        raise DailyCompletionRefused("upstream job evidence unavailable")
    if jobs.get("total_count") != len(jobs["jobs"]) or len(jobs["jobs"]) != 1:
        raise DailyCompletionRefused("ambiguous upstream jobs")
    job = jobs["jobs"][0]
    if (not isinstance(job, dict) or job.get("name") != "update"
            or job.get("conclusion") != "success" or not isinstance(job.get("steps"), list)):
        raise DailyCompletionRefused("upstream daily job not successful")
    steps = {s["name"]: s.get("conclusion") for s in job["steps"]
             if isinstance(s, dict) and isinstance(s.get("name"), str)}
    if steps.get("Run pipeline") == "skipped" and steps.get("Record successful run") == "skipped":
        raise NoNewCollection("green retry skipped production collection")
    if any(steps.get(step) != "success" for step in REQUIRED_STEPS):
        raise DailyCompletionRefused("upstream full collection/deployment was skipped or failed")
    if marker != today.isoformat():
        raise DailyCompletionRefused(phase.capitalize() + " marker not fresh and complete")
    week = today if phase == "saturday" else today - timedelta(days=1)
    return {"phase": phase, "week_ending": week.isoformat(),
            "collection_day": today.isoformat(), "upstream_id": run["id"]}


def durable_directory(directory):
    """Private 0700 store owned by this user and outside known ephemeral roots."""
    resolved = Path(directory).resolve()
    for name in ("RUNNER_TEMP", "GITHUB_WORKSPACE", "RUNNER_TOOL_CACHE"):
        root = os.environ.get(name)
        if root:
            root = Path(root).resolve()
            if resolved == root or root in resolved.parents:
                raise ValueError("private routing store must not live in ephemeral runner storage")
    directory = private_directory(directory)
    if directory.stat().st_uid != os.getuid():
        raise ValueError("private routing store must be owned by the operator")
    return directory


def eligible_analyst(roster, week_ending, *, editor, owner):
    """Return the first consenting, available, in-scope analyst, else None.

    The roster is a private owner file. Consent references are owner records,
    not verified here; revocation or unavailability means the no-analyst path.
    """
    if not isinstance(roster, dict) or roster.get("schema") != ROSTER_SCHEMA \
            or not isinstance(roster.get("analysts"), list):
        raise ValueError("private analyst roster schema required")
    from scripts.sunday_editorial_handoff import single_address
    for entry in roster["analysts"]:
        if not isinstance(entry, dict):
            raise ValueError("invalid analyst roster entry")
        email = single_address(entry.get("email", ""), "analyst email")
        consent = entry.get("consent_reference")
        if (isinstance(consent, str) and len(consent.strip()) >= 12
                and entry.get("scope") == SCOPE and entry.get("revoked") is False
                and week_ending in (entry.get("available_weeks") or [])
                and email.casefold() not in (editor.casefold(), owner.casefold())):
            return {"id": entry.get("id"), "email": email, "consent_reference": consent}
    return None


def _paths(directory, week):
    return {name: directory / ("analyst-" + name + "-" + week + ".json")
            for name in ("week", "return", "feedback")}


def _revised(directory, week):
    return directory / ("revised-IPR-Briefs-Editorial-" + week + ".txt")


def _load(path):
    if path.is_symlink():
        raise ValueError("private routing receipt must not be a symlink")
    return json.loads(path.read_text(encoding="utf-8"))


def _deadline(manifest):
    when = datetime.fromisoformat(manifest["deadline"])
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("analyst deadline must include a timezone offset")
    latest = datetime.combine(date.fromisoformat(manifest["week_ending"]), EDITOR_DEADLINE, NY)
    if when > latest:
        raise ValueError("analyst deadline must leave Dylan's Saturday 9 p.m. delivery intact")
    return when


def _bind(state, manifest):
    validate_manifest(manifest)
    # Slug identities (#946) are refused: one analyst item per reporting Saturday.
    if manifest["packet"] != state["identity"] or state["identity"] != "IPR-" + manifest["week_ending"]:
        raise ValueError("analyst assignment must bind the exact weekly packet identity")
    if manifest["worksheet_sha256"] != state["packet_sha256"]:
        raise ValueError("analyst assignment does not bind the accepted provisional manuscript")


def dispatch_analyst(state, directory, *, manifest, docx, brief, roster, transport,
                     owner_confirmed=False, approved_manifest_sha256="",
                     marker_path=MARKER, now=None, database=DB_PATH):
    """Send one owner-approved assignment to one eligible analyst, at most once.

    Returns NO_ANALYST without writing anything when nobody is eligible; the
    Track A provisional delivery then proceeds unchanged. The weekly cap and the
    reservation are written before the transport and stay consumed on failure.
    """
    week = state["window"]["week_ending"]
    collection_window(week, "saturday", now=now, marker_path=marker_path)
    directory = durable_directory(directory)
    clock = (now or datetime.now(NY)).astimezone(NY)
    if state.get("status") != "SATURDAY_PROVISIONAL":
        raise ValueError("analyst assignment requires an accepted provisional manuscript")
    _bind(state, manifest)
    packet = directory / state["packet_file"]
    if packet.is_symlink() or hashlib.sha256(packet.read_bytes()).hexdigest() != state["packet_sha256"]:
        raise ValueError("accepted provisional manuscript fingerprint changed")
    if _deadline(manifest) <= clock:
        raise ValueError("analyst deadline has already passed")
    if any(compare(state["inventory"], inventory(week, database=database)).values()):
        raise ValueError("source evidence or permissions changed after drafting; hold analyst assignment")
    if not owner_confirmed or approved_manifest_sha256 != manifest["manifest_sha256"]:
        raise ValueError("analyst send requires owner review of the exact assignment manifest")
    from scripts.sunday_editorial_handoff import single_address
    editor = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    owner = single_address(os.environ.get("IPR_PREVIEW_TO", ""), "IPR_PREVIEW_TO")
    analyst = eligible_analyst(roster, week, editor=editor, owner=owner)
    if analyst is None:
        return {"status": "NO_ANALYST", "email_sent": False, "publication_authorized": False}
    if not callable(transport):
        raise ValueError("analyst transport must be injected explicitly")
    if not isinstance(docx, bytes) or not docx or not isinstance(brief, str) or not brief:
        raise ValueError("analyst assignment files required")
    paths = _paths(directory, week)
    # One analyst item per reporting Saturday, whichever analyst or slug.
    write_private(paths["week"], {"status": "ANALYST_ASSIGNMENT_RESERVED",
        "identity": state["identity"], "assignment_id": manifest["assignment_id"],
        "analyst_id": analyst["id"], "consent_reference": analyst["consent_reference"],
        "docx_sha256": hashlib.sha256(docx).hexdigest(), "brief_sha256": digest(brief),
        "manifest": manifest})
    key = cycle_digest({"identity": state["identity"], "phase": "analyst",
                        "recipient": analyst["email"].casefold()})
    write_private(directory / ("dispatch-" + key + ".json"),
                  {"status": "DELIVERY_ATTEMPT_RESERVED", "assignment_id": manifest["assignment_id"],
                   "manifest_sha256": manifest["manifest_sha256"], "recipient": analyst["email"],
                   "identity": state["identity"]})
    transport(recipient=analyst["email"], docx=docx, brief=brief,
              assignment_id=manifest["assignment_id"])
    write_private(directory / ("delivered-" + key + ".json"),
                  {"status": "ANALYST_SENT", "manifest_sha256": manifest["manifest_sha256"]})
    return {"status": "ANALYST_SENT", "assignment_id": manifest["assignment_id"],
            "email_sent": True, "publication_authorized": False}


def record_return(directory, week, returned):
    """Store the extracted analyst return once, bound to the stored assignment."""
    directory = durable_directory(directory)
    paths = _paths(directory, week)
    manifest = _load(paths["week"])["manifest"]
    validate_manifest(manifest)
    if (not isinstance(returned, dict) or returned.get("assignment_id") != manifest["assignment_id"]
            or returned.get("manifest_sha256") != manifest["manifest_sha256"]
            or returned.get("worksheet_sha256") != manifest["worksheet_sha256"]
            or returned.get("return_receipt_sha256") != digest(
                {k: v for k, v in returned.items() if k != "return_receipt_sha256"})):
        raise ValueError("analyst return does not belong to the stored assignment")
    write_private(paths["return"], returned)
    return returned["return_receipt_sha256"]


def record_feedback(directory, week, feedback, revised_worksheet):
    """Store the owner's reconciliation report and the exact revised manuscript once."""
    directory = durable_directory(directory)
    paths = _paths(directory, week)
    manifest = _load(paths["week"])["manifest"]
    returned = _load(paths["return"])
    _check_feedback(manifest, returned, feedback)
    if not isinstance(revised_worksheet, str) or digest(revised_worksheet) != feedback["revised_worksheet_sha256"]:
        raise ValueError("revised manuscript is not the one the owner reconciled")
    write_private(_revised(directory, week), revised_worksheet)
    write_private(paths["feedback"], feedback)
    return feedback["state"]


def _check_feedback(manifest, returned, feedback):
    if (not isinstance(feedback, dict) or feedback.get("schema") != "ipr-analytical-feedback/1"
            or feedback.get("feedback_sha256") != digest(
                {k: v for k, v in feedback.items() if k != "feedback_sha256"})
            or feedback.get("assignment_id") != manifest["assignment_id"]
            or feedback.get("worksheet_sha256") != manifest["worksheet_sha256"]
            or feedback.get("return_receipt_sha256") != returned["return_receipt_sha256"]
            or feedback.get("state") not in ("HELD", "ANALYSIS_RECONCILED")
            or not HEX.fullmatch(str(feedback.get("revised_worksheet_sha256")))):
        raise ValueError("owner feedback receipt does not bind the stored return")


def route(state, directory, *, now=None):
    """Decide Dylan's manuscript from durable receipts; never sends anything.

    A received return beats the deadline. A return without owner feedback, or
    feedback that is HELD, blocks Dylan's packet. A missing return after the
    deadline falls back to the accepted provisional manuscript.
    """
    week = state["window"]["week_ending"]
    directory = durable_directory(directory)
    paths = _paths(directory, week)
    if not paths["week"].exists() and not paths["week"].is_symlink():
        return {"route": "NO_ANALYST", "packet_sha256": state["packet_sha256"]}
    manifest = _load(paths["week"])["manifest"]
    _bind(state, manifest)
    clock = (now or datetime.now(NY))
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise ValueError("routing clock requires timezone")
    if paths["return"].exists() or paths["return"].is_symlink():
        returned = _load(paths["return"])
        if returned.get("assignment_id") != manifest["assignment_id"] or returned.get(
                "return_receipt_sha256") != digest({k: v for k, v in returned.items()
                                                    if k != "return_receipt_sha256"}):
            raise ValueError("stored analyst return changed")
        if not (paths["feedback"].exists() or paths["feedback"].is_symlink()):
            return {"route": "HELD", "reason": "analyst return awaits owner reconciliation"}
        feedback = _load(paths["feedback"])
        _check_feedback(manifest, returned, feedback)
        if feedback["state"] != "ANALYSIS_RECONCILED":
            return {"route": "HELD", "reason": "owner reconciliation left unresolved findings"}
        revised = _revised(directory, week)
        if revised.is_symlink() or hashlib.sha256(revised.read_bytes()).hexdigest() \
                != feedback["revised_worksheet_sha256"]:
            raise ValueError("stored revised manuscript changed")
        return {"route": "DELIVER_REVISED", "packet_file": revised.name,
                "packet_sha256": feedback["revised_worksheet_sha256"],
                "feedback_sha256": feedback["feedback_sha256"]}
    if clock < _deadline(manifest):
        return {"route": "AWAIT_ANALYST", "deadline": manifest["deadline"]}
    return {"route": "DELIVER_PROVISIONAL", "packet_sha256": state["packet_sha256"],
            "reason": "analyst deadline passed without a return"}
