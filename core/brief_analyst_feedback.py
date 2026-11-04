"""Private owner-reviewed analytical feedback; never self-modifying learning.

Like analyze_editor_return, observations remain proposals. An operator supplies
an independently made source-check decision; the code validates its provenance
and exact text binding, not the factual truth of that human assessment.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import re

from core.brief_analyst_packet import HEX, digest, line, require, validate_manifest, web_url
from scripts.sunday_editor_readable import editable_sections
from scripts.validate_editorial_return import _split

SCHEMA = "ipr-analytical-feedback/1"
DISPOSITIONS = {"accepted", "rejected", "unresolved"}


def reconcile_feedback(manifest, returned, revised_worksheet, *, decisions, owner_review):
    """Record explicit decisions; do not rewrite a manuscript or infer approval.

    New analyst URLs remain unverified until the independent owner supplies
    exact official-source identity/version and a real source-check reference.
    Owner input must be supplied separately from the untrusted returned file.
    """
    validate_manifest(manifest)
    require(isinstance(returned, dict) and returned.get("schema") == "ipr-research-analyst-return/1"
            and returned.get("assignment_id") == manifest["assignment_id"]
            and returned.get("manifest_sha256") == manifest["manifest_sha256"]
            and returned.get("worksheet_sha256") == manifest["worksheet_sha256"], "return does not belong to the trusted assignment")
    require(returned.get("return_receipt_sha256") == digest({k: v for k, v in returned.items() if k != "return_receipt_sha256"}), "return receipt altered")
    revised_sections = editable_sections(revised_worksheet)
    header, _, appendix = _split(revised_worksheet)
    require(digest(header) == manifest["worksheet_header_sha256"]
            and digest(appendix) == manifest["worksheet_appendix_sha256"],
            "revised worksheet changed assignment identity or protected source appendix")
    revised_sha = digest(revised_worksheet)
    require(isinstance(owner_review, dict) and set(owner_review) == {
        "owner_confirmed", "reviewed_by", "review_reference", "reviewed_on", "return_receipt_sha256", "revised_worksheet_sha256"},
        "separate exact-version owner reconciliation required")
    require(owner_review["owner_confirmed"] is True and line(owner_review["reviewed_by"], 3)
            and line(owner_review["review_reference"], 12), "named owner reconciliation and actual reference required")
    require(date.fromisoformat(owner_review["reviewed_on"]).isoformat() == owner_review["reviewed_on"], "review date must be canonical")
    require(owner_review["return_receipt_sha256"] == returned["return_receipt_sha256"]
            and owner_review["revised_worksheet_sha256"] == revised_sha,
            "owner review does not bind exact return and revised manuscript")
    require(isinstance(decisions, list), "reconciliation decisions required")
    assertions = {f["finding_id"]: f for f in returned["findings"]}
    require(len(assertions) == len(returned["findings"]), "duplicate return findings")
    require(len(decisions) == len(assertions) and {d.get("finding_id") for d in decisions} == set(assertions),
            "every extracted assertion needs one explicit disposition")
    old_text = "\n\n".join(v for _, v in manifest["sections"])
    new_text = "\n\n".join(v for _, v in revised_sections)
    results = []
    sources = {s["id"]: s for s in manifest["sources"]}
    for decision in decisions:
        require(isinstance(decision, dict) and set(decision) == {
            "finding_id", "disposition", "reason", "source_checks", "change", "candidate_lesson", "error_type", "serious"},
            "feedback decision has invalid fields")
        finding = assertions[decision["finding_id"]]
        disposition = decision["disposition"]
        require(disposition in DISPOSITIONS and line(decision["reason"], 12)
                and type(decision["serious"]) is bool, "disposition/reason/serious flag invalid")
        require(isinstance(decision["source_checks"], list) and len(decision["source_checks"]) <= 12,
                "bounded independent source checks required")
        verified = []
        for check in decision["source_checks"]:
            require(isinstance(check, dict) and set(check) == {
                "source_id", "url", "version_sha256", "reviewed_by", "review_reference", "assessment"},
                "source check must identify exact source/version and independent reviewer")
            require(line(check["source_id"], maximum=100) and web_url(check["url"])
                    and isinstance(check["version_sha256"], str) and HEX.fullmatch(check["version_sha256"])
                    and line(check["reviewed_by"], 3) and line(check["review_reference"], 12)
                    and check["assessment"] in {"supports_correction", "contradicts_suggestion", "inconclusive"},
                    "source check lacks actual original-review provenance")
            old = sources.get(check["source_id"])
            if old is not None:
                require(old["evidence_basis"] in ("preserved_original", "reviewed_original")
                        and check["url"] == old["url"] and check["version_sha256"] == old["version_sha256"],
                        "source version/access drift requires a new assignment, not inherited verification")
            else:
                require(check["url"] in [r["url"] for r in finding["references"]],
                        "new source was not identified by this analyst finding")
            verified.append(dict(check))
        if disposition == "accepted":
            require(any(c["assessment"] == "supports_correction" for c in verified),
                    "accepted correction requires an independently checked original")
            change = decision["change"]
            require(isinstance(change, dict) and set(change) == {"before", "after"}
                    and isinstance(change["before"], str) and isinstance(change["after"], str)
                    and bool(change["before"]) and bool(change["after"])
                    and change["before"] != change["after"] and change["before"] in old_text
                    and change["after"] in new_text and revised_sha != manifest["worksheet_sha256"]
                    and old_text.count(change["before"]) > new_text.count(change["before"])
                    and new_text.count(change["after"]) > old_text.count(change["after"]),
                    "accepted correction must name a real change in the exact revised manuscript")
        else:
            require(decision["change"] is None, "rejected/unresolved assertions cannot claim an accepted change")
        lesson = decision["candidate_lesson"]
        code = decision["error_type"]
        require((lesson is None and code is None) or (line(lesson, 20, 1200)
                and isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{2,60}", code)),
                "lesson and human-assessed error type must be supplied together")
        eligible = bool(lesson and verified and ((disposition == "accepted" and any(
            c["assessment"] == "supports_correction" for c in verified)) or (disposition == "rejected" and any(
            c["assessment"] == "contradicts_suggestion" for c in verified))))
        results.append({**decision, "analyst_assertion": finding["assertion"],
            "assertion_origin": finding["origin"], "independent_source_checks": verified,
            "lesson_eligible_for_owner_consideration": eligible,
            "system_model_suggestion": None, "assertion_authorship_verified": False, "lesson_adopted": False})
    report = {"schema": SCHEMA, "assignment_id": manifest["assignment_id"],
        "worksheet_sha256": manifest["worksheet_sha256"], "return_receipt_sha256": returned["return_receipt_sha256"],
        "revised_worksheet_sha256": revised_sha, "owner_review": dict(owner_review), "findings": results,
        "state": "HELD" if any(r["disposition"] == "unresolved" for r in results) else "ANALYSIS_RECONCILED",
        "credit_proposal": "Owner adjudication required; no automatic byline or acknowledgement",
        "governance": {"code_verified_facts": False, "publication_authorized": False,
            "prompt_changed": False, "model_called": False, "lesson_adopted": False,
            "statement": "Named human source-check attestations, not software factual verification. Candidate lessons require a separate owner decision before any prompt, rubric or policy change."}}
    report["feedback_sha256"] = digest(report)
    return report


def aggregate_feedback(reports):
    """Aggregate owner-reviewed verified error types, deduplicated by assignment.

    One serious supported error is surfaced immediately. Frequency is not a
    factual review, source permission, automatic rule, or credit decision.
    """
    seen, groups = {}, defaultdict(list)
    for report in reports:
        require(isinstance(report, dict) and report.get("schema") == SCHEMA
                and report.get("feedback_sha256") == digest({k: v for k, v in report.items() if k != "feedback_sha256"}),
                "invalid or altered analytical feedback receipt")
        assignment = report["assignment_id"]
        if assignment in seen:
            require(seen[assignment] == report["feedback_sha256"], "conflicting feedback receipts for one assignment")
            continue
        seen[assignment] = report["feedback_sha256"]
        review = report["owner_review"]
        require(review["owner_confirmed"] is True and line(review["reviewed_by"], 3)
                and line(review["review_reference"], 12)
                and review["revised_worksheet_sha256"] == report["revised_worksheet_sha256"]
                and review["return_receipt_sha256"] == report["return_receipt_sha256"], "feedback lacks exact owner review")
        by_code = {}
        for finding in report["findings"]:
            checks = finding["independent_source_checks"]
            verified = bool(checks) and all(isinstance(c.get("version_sha256"), str)
                and HEX.fullmatch(c["version_sha256"]) and web_url(c.get("url"))
                and line(c.get("reviewed_by"), 3) and line(c.get("review_reference"), 12) for c in checks)
            supporting = any(c.get("assessment") == "supports_correction" for c in checks)
            contrary = any(c.get("assessment") == "contradicts_suggestion" for c in checks)
            eligible = (finding["disposition"] in {"accepted", "rejected"} and verified
                and ((finding["disposition"] == "accepted" and supporting and isinstance(finding.get("change"), dict))
                     or (finding["disposition"] == "rejected" and contrary))
                and line(finding.get("candidate_lesson"), 20, 1200)
                and isinstance(finding.get("error_type"), str)
                and re.fullmatch(r"[a-z][a-z0-9_]{2,60}", finding["error_type"]))
            if eligible:
                by_code.setdefault(finding["error_type"], []).append(finding)
        for code, findings in by_code.items():
            groups[code].append({"assignment_id": assignment,
                "serious": any(f["serious"] for f in findings),
                "candidate_lessons": list(dict.fromkeys(f["candidate_lesson"] for f in findings))})
    return [{"error_type": code, "assignments_observed": len(items),
             "attention": "immediate owner review" if any(i["serious"] for i in items) else
             ("recurring verified pattern for owner review" if len(items) >= 3 else "isolated verified observation"),
             "observations": items, "lesson_adopted": False, "prompt_changed": False}
            for code, items in sorted(groups.items())]
