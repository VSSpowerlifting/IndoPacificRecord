#!/usr/bin/env python3
"""
The one owner activation change for the South Korea Desk Daily.

    python scripts/korea_daily_activation.py plan    # print the change; writes nothing
    python scripts/korea_daily_activation.py apply   # write it into the working tree

`apply` does exactly two things, which the build refuses to see half-done:

  1. moves the staged production manifest
     config/korea_daily_activation/manifest.json -> desks/korea/manifest.json
     (with its staging comment replaced by the active one), and
  2. flips the desks/registry.json Korea entry to status "live", manifest
     "desks/korea/manifest.json", has_production_records true, with scope and
     status explanation that describe the machine-translated lane.

It edits the Korea entry's text in place so the rest of the hand-formatted
registry is untouched. It does not commit, push, set repository variables,
call a model, touch a database or publish anything. The Daily stays off until
the owner also sets KOREA_DAILY_AUTOMATION_ENABLED=true
(docs/engineering/KOREA_DAILY_ACTIVATION_2026-10-20.md).
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGED = Path("config/korea_daily_activation/manifest.json")
ACTIVE = Path("desks/korea/manifest.json")
REGISTRY = Path("desks/registry.json")

ACTIVE_COMMENT = [
    "South Korea Desk - production manifest, activated by the owner through",
    "scripts/korea_daily_activation.py (docs/engineering/KOREA_DAILY_ACTIVATION_2026-10-20.md).",
    "One source: Korea Policy Briefing republications explicitly labeled as",
    "MND (A00005) releases. access_method is manual: the Daily never fetches",
    "the portal. The private collector (ipr-source-evidence-private) keeps",
    "captures, HWPX and photographs; records reach `articles` only through the",
    "source-pinned bridge (core/korea_corpus_bridge.py) for identities in the",
    "public KOGL release index. DAPA stays metadata-only and is not a source",
    "here. Tier B reflects republication; cadence thresholds remain unset.",
]

REGISTRY_FIELDS: Dict[str, object] = {
    "scope": (
        "Source-verified MND and DAPA official-link metadata from Korea Policy "
        "Briefing; separately licensed Korean government original text; "
        "machine-translated MND releases, labeled as unreviewed machine "
        "output; and editor-approved English translation and analysis. "
        "Coverage is selective; government claims remain attributed to their "
        "issuing institutions."),
    "status": "live",
    "status_explanation": (
        "MND releases republished on Korea Policy Briefing whose KOGL Type 1 "
        "Korean text is in the public release index enter the corpus once per "
        "source version through a source-pinned bridge, and the shared Daily "
        "screens, machine-translates and summarizes them. Those records are "
        "machine output that no human has reviewed. Releases in the "
        "editor-reviewed English path, the frozen October baseline and the "
        "research hold are never machine-published. DAPA remains official-link metadata "
        "only. Live describes this lane; it does not certify comprehensive "
        "Korean defense coverage or direct MND.gov.kr collection."),
    "manifest": str(ACTIVE),
    "has_production_records": True,
}


class ActivationError(RuntimeError):
    pass


def _korea_block(text: str) -> Tuple[int, int]:
    start = text.index('"slug": "korea"')
    nxt = text.find('"slug":', start + len('"slug": "korea"'))
    return start, (nxt if nxt != -1 else len(text))


def flip_registry(text: str) -> str:
    """Return the registry text with only the Korea entry's fields replaced."""
    start, end = _korea_block(text)
    block = text[start:end]
    for key, value in REGISTRY_FIELDS.items():
        pattern = re.compile(r'(\n[ \t]*"%s": )(?:"(?:[^"\\]|\\.)*"|null|true|false)' % key)
        if len(pattern.findall(block)) != 1:
            raise ActivationError("registry Korea entry: expected one %r field" % key)
        rendered = json.dumps(value, ensure_ascii=False)
        block = pattern.sub(lambda m: m.group(1) + rendered, block)
    return text[:start] + block + text[end:]


def activated_manifest(staged_text: str) -> str:
    data = json.loads(staged_text)
    data["_comment"] = ACTIVE_COMMENT
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def plan(root: Path = REPO_ROOT) -> Dict[Path, Tuple[str, str]]:
    """{path: (before, after)} for every file `apply` writes. Refuses a
    repository that is already activated or half-activated."""
    staged, active, registry = root / STAGED, root / ACTIVE, root / REGISTRY
    if active.exists():
        raise ActivationError("%s already exists; the desk is already activated" % ACTIVE)
    if not staged.is_file():
        raise ActivationError("staged manifest %s is missing" % STAGED)
    reg_before = registry.read_text(encoding="utf-8")
    entry = next(d for d in json.loads(reg_before)["desks"] if d["slug"] == "korea")
    if entry["status"] != "shadow" or entry["manifest"] is not None \
            or entry["has_production_records"]:
        raise ActivationError("registry Korea entry is not the expected shadow entry")
    reg_after = flip_registry(reg_before)
    after = json.loads(reg_after)
    if [d for d in after["desks"] if d["slug"] != "korea"] != \
            [d for d in json.loads(reg_before)["desks"] if d["slug"] != "korea"]:
        raise ActivationError("registry edit reached beyond the Korea entry")
    return {
        REGISTRY: (reg_before, reg_after),
        ACTIVE: ("", activated_manifest(staged.read_text(encoding="utf-8"))),
        STAGED: (staged.read_text(encoding="utf-8"), ""),
    }


def apply(root: Path = REPO_ROOT) -> Dict[Path, Tuple[str, str]]:
    changes = plan(root)
    (root / ACTIVE).parent.mkdir(parents=True, exist_ok=True)
    (root / ACTIVE).write_text(changes[ACTIVE][1], encoding="utf-8")
    (root / REGISTRY).write_text(changes[REGISTRY][1], encoding="utf-8")
    (root / STAGED).unlink()
    try:
        (root / STAGED).parent.rmdir()
    except OSError:
        pass
    return changes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("action", choices=("plan", "apply"))
    args = parser.parse_args(argv)
    try:
        changes = (apply if args.action == "apply" else plan)()
    except ActivationError as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    for path, (before, after) in changes.items():
        sys.stdout.writelines(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True),
            "a/%s" % path if before else "/dev/null",
            "b/%s" % path if after else "/dev/null"))
    if args.action == "apply":
        print("\nApplied in the working tree. Commit the registry and manifest "
              "together; processing stays off until the owner sets "
              "KOREA_DAILY_AUTOMATION_ENABLED=true.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
