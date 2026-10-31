"""Read-only qualification reuse for Daily; GitHub job evidence, never artifacts.

Trust starts at Daily's reviewed main checkout. Only authenticated main-push
full runs may qualify equivalent inputs when their entire non-mutable Git tree
(including this verifier, scope selector and workflow) equals that checkout. No candidate code
is checked out or executed. API/identity/availability failures require the old
offline suite, and cannot authorize collection or publication themselves.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import urllib.request

from scripts.pr_ci_scope import classify

REPOSITORY = "VSSpowerlifting/IndoPacificRecord"
WORKFLOW = ".github/workflows/pr_offline_checks.yml"
SHA = r"[0-9a-f]{40}"
RECEIPT = re.compile(r"Qualification environment ([0-9a-f]{64})")

# Closed list of routine products. Canonical edition sidecars, all source
# assets/scripts/styles, prompts, policies, fixtures, docs and unknown paths
# remain inputs. Even these mutable paths must be ordinary non-executable blobs.
MUTABLE = {
    "pla_watch.db", ".github/state/last_daily_run_date.txt",
    ".github/state/last_billing_failure_date.txt", ".github/state/llm_usage.jsonl",
    "output/data/articles.json", "output/corpus-index.json",
    "output/archive-research-index.json", "output/sitemap.xml",
}
GENERATED_PAGES = {
    "about", "analysis", "archive", "china", "corpus-guide", "corpus",
    "coverage", "desks", "index", "indonesia", "japan", "korea",
    "methodology", "philippines", "pla-watch", "signals", "singapore",
    "sources", "team", "us-indopacific", "vietnam",
}
GENERATED_RECORD = re.compile(
    r"output/(?:article|record|source|korea-originals|korea-analysis|korea-translations)"
    r"/[a-zA-Z0-9_-]+\.html")
GENERATED_WEEK = re.compile(r"output/week-\d{4}-\d{2}-\d{2}(?:-\d+)?\.html")


class Unqualified(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Unqualified(reason)


def mutable(path, mode="100644"):
    return mode == "100644" and (
        path in MUTABLE or
        path in {"output/" + p + ".html" for p in GENERATED_PAGES} or
        GENERATED_RECORD.fullmatch(path) is not None or
        GENERATED_WEEK.fullmatch(path) is not None)


class Git:
    def __init__(self, root):
        self.root = root

    def run(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root,
                                       stderr=subprocess.DEVNULL)

    def revision(self):
        return self.run("rev-parse", "HEAD").decode().strip()

    def inputs(self, revision):
        # Include names, modes, object types and immutable blob/submodule IDs.
        # A newly introduced unknown file or mutable-path symlink is an input.
        result = {}
        for entry in self.run("ls-tree", "-rz", "--full-tree", revision).split(b"\0"):
            if not entry:
                continue
            meta, path = entry.split(b"\t", 1)
            name = path.decode("utf-8", "surrogateescape")
            mode = meta.split(b" ", 1)[0].decode()
            if not mutable(name, mode):
                result[name] = meta.decode()
        return result

    def obtain(self, revision):
        require(re.fullmatch(SHA, revision), "invalid tested revision")
        # SHA only, hardcoded public origin, no candidate checkout or execution.
        self.run("fetch", "--no-tags",
                 "https://github.com/" + REPOSITORY + ".git", revision)

    def parents(self, revision):
        return self.run("rev-list", "--parents", "-n", "1", revision).decode().split()[1:]

    def ancestor(self, ancestor, current):
        return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, current],
                              cwd=self.root, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0

    def scope(self, base, tested):
        paths = self.run("diff", "--name-only", "-z", "--no-renames", base, tested, "--")
        return classify([p.decode("utf-8", "surrogateescape")
                         for p in paths.split(b"\0") if p])

    def clean_inputs(self):
        paths = self.run("diff", "HEAD", "--name-only", "-z", "--no-renames", "--")
        require(all(mutable(p.decode("utf-8", "surrogateescape"))
                    for p in paths.split(b"\0") if p), "execution inputs modified after checkout")
        # Untracked executable/configuration files could shadow checked-in code.
        require(not self.run("ls-files", "--others", "--exclude-standard", "-z").strip(b"\0"),
                "untracked checkout files")

    def workflow_matches(self, revision, current):
        require(re.fullmatch(SHA, revision or ""), "Daily workflow revision unavailable")
        path = ".github/workflows/daily_update.yml"
        require(self.run("rev-parse", revision + ":" + path) ==
                self.run("rev-parse", current + ":" + path),
                "executing Daily workflow differs from checked-out workflow")


def environment_identity():
    """Conservative resolved environment identity, measured before tests.

    Runner image drift and unpinned dependency resolutions invalidate reuse.
    RECORD metadata includes wheel file hashes, not just requirement ranges.
    No secrets or runtime activation values are read into this identity.
    """
    from playwright.sync_api import sync_playwright

    image = {k: os.environ.get(k, "") for k in
             ("ImageOS", "ImageVersion", "RUNNER_OS", "RUNNER_ARCH")}
    packages = sorted((d.metadata["Name"].lower(), d.version,
                       d.read_text("RECORD"), d.read_text("direct_url.json"))
                      for d in importlib.metadata.distributions())
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        chromium = browser.version
        browser.close()
    require(all(image.values()), "runner image identity unavailable")
    data = {"version": 1, "image": image, "python": sys.version,
            "platform": platform.machine(), "packages": packages, "chromium": chromium,
            # playwright --with-deps can install newer native libraries on the
            # same runner image. Their resolved versions must match as well.
            "system_packages": subprocess.check_output(
                ["dpkg-query", "-W", "-f=${Package}=${Version}\n"], text=True)}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class GitHub:
    def __init__(self, token):
        require(bool(token), "GitHub read token unavailable")
        self.token = token

    def get(self, path):
        request = urllib.request.Request(
            "https://api.github.com/repos/" + REPOSITORY + "/" + path,
            headers={"Authorization": "Bearer " + self.token,
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)


REQUIRED_STEPS = (
    "Check out the pull request", "Set up Python 3.9",
    "Record tracked database baseline", "Classify changed paths against PR base",
    "Verify GPG and restore frozen historical replay objects", "Install dependencies",
    "Install Chromium for the browser-backed tests", "Verify Chromium launches",
    "Measure qualification environment", "Run offline test suite",
    "Render isolated output for validation", "Validate rendered output",
    "Assert the tracked database and output are unchanged",
)


def successful(obj):
    return obj.get("status") == "completed" and obj.get("conclusion") == "success"


def verify_run(api, git, run, workflow_id, current, current_inputs, environment):
    require(run.get("repository", {}).get("full_name") == REPOSITORY,
            "wrong evidence repository")
    require(run.get("head_repository", {}).get("full_name") == REPOSITORY,
            "external head repository")
    require(run.get("workflow_id") == workflow_id and run.get("path") == WORKFLOW,
            "wrong workflow identity")
    # For push, GitHub binds head_sha to the actual checkout/workflow revision.
    # PR head_sha is NOT its executed synthetic merge. A PR-controlled step
    # name claiming a merge SHA cannot authenticate the workflow that ran.
    require(run.get("event") == "push" and run.get("head_branch") == "main" and successful(run),
            "run is not a completed successful trusted main-push qualification")
    run_id, attempt = run["id"], run["run_attempt"]
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0,
            "invalid run/attempt identity")
    jobs = api.get(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    require(jobs["total_count"] == len(jobs["jobs"]) == 1,
            "incomplete or unexpected qualification jobs")
    job = jobs["jobs"][0]
    require(job.get("name") == "offline-checks" and successful(job) and
            job.get("run_id") == run_id and job.get("run_attempt") == attempt and
            job.get("head_sha") == run.get("head_sha") and
            job.get("labels") == ["ubuntu-24.04"], "job identity/environment mismatch")
    steps = job.get("steps", [])
    receipts = [s for s in steps if RECEIPT.fullmatch(s.get("name", ""))]
    require(len(receipts) == 1 and successful(receipts[0]),
            "missing successful versioned qualification step")
    tested = run.get("head_sha", "")
    measured = RECEIPT.fullmatch(receipts[0]["name"]).group(1)
    require(measured == environment, "resolved test environment changed")
    git.obtain(tested)
    parents = git.parents(tested)
    require(parents and git.ancestor(tested, current), "tested revision is not an ancestor of current main")
    inputs = git.inputs(tested)
    differing = sorted(p for p in inputs.keys() | current_inputs.keys()
                       if inputs.get(p) != current_inputs.get(p))
    require(not differing, "execution inputs changed: " + ", ".join(differing[:8]))
    scope = git.scope(parents[0], tested)
    require(scope.mode == "full", "focused-only or docs-only scope")
    required = list(REQUIRED_STEPS)
    if scope.source_replay:
        required.append("Replay all frozen pilot sources and independent review excerpts")
    for name in required:
        matches = [s for s in steps if s.get("name") == name]
        require(len(matches) == 1 and successful(matches[0]),
                "required step did not succeed: " + name)
    return {"run": run_id, "attempt": attempt, "job": job["id"], "tested": tested,
            "environment": environment,
            "inputs_sha256": hashlib.sha256(
                json.dumps(current_inputs, sort_keys=True).encode()).hexdigest(),
            "url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}"}


def decide(api, git, environment, workflow_revision):
    current = git.revision()  # Actual job-start checkout, never triggering SHA.
    result = {"reused": False, "current": current, "reason": "no qualifying full run"}
    try:
        require(re.fullmatch(r"[0-9a-f]{64}", environment or ""),
                "current environment unavailable")
        git.clean_inputs()
        git.workflow_matches(workflow_revision, current)
        inputs = git.inputs(current)
        workflow = api.get("actions/workflows/pr_offline_checks.yml")
        require(workflow.get("path") == WORKFLOW and workflow.get("state") == "active",
                "trusted workflow unavailable")
        runs = api.get(f"actions/workflows/{workflow['id']}/runs?event=push&branch=main&per_page=30")
        # Bounded search: history beyond this window safely takes the fallback.
        reasons = []
        for run in runs["workflow_runs"]:
            try:
                evidence = verify_run(api, git, run, workflow["id"], current, inputs, environment)
                return dict(result, reused=True, reason="trusted full qualification reused",
                            evidence=evidence)
            except (Unqualified, KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
                reasons.append(f"run {run.get('id', '?')}: {exc}")
        if reasons:
            result["reason"] = "; ".join(reasons)
    except Exception as exc:
        # Authentication/rate limits/deleted history/network/shape errors must
        # never skip the suite. Report type only: HTTP errors can contain URLs.
        result["reason"] = str(exc) if isinstance(exc, Unqualified) else type(exc).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("environment", "decide"))
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "environment":
        try:
            digest = environment_identity()
        except Exception as exc:
            # Measurement is eligibility for reuse, never an alternative gate.
            # Unavailable metadata/tools require the unchanged full fallback.
            print("Qualification environment unavailable; full suite required:",
                  type(exc).__name__)
            digest = ""
        with args.github_output.open("a") as out:
            out.write("digest=" + digest + "\n")
        print("Resolved qualification environment:", digest)
        return
    try:
        api = GitHub(os.environ.get("GH_TOKEN"))
        result = decide(api, Git(Path.cwd()), os.environ.get("QUALIFICATION_ENVIRONMENT"),
                        os.environ.get("DAILY_WORKFLOW_SHA"))
    except Unqualified as exc:
        result = {"reused": False, "current": Git(Path.cwd()).revision(), "reason": str(exc)}
    with args.github_output.open("a") as out:
        out.write("reused=" + str(result["reused"]).lower() + "\n")
    print(json.dumps(result, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write("### Code qualification\n\n```json\n" +
                          json.dumps(result, indent=2) + "\n```\n\n")


if __name__ == "__main__":
    main()
