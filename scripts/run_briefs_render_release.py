"""Run the governed render for Phase 3C and No. 17 without publishing it.

The release renders historical PLA Watch pages from their existing sidecars,
then renders the current IPR tree. It never collects, changes canonical
sidecars, writes the database, or deploys. Publication is a separate, manual
workflow input after the strict output-scope check passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://indopacificrecord.org"
HISTORICAL_DATES = (
    "2026-05-09", "2026-05-16", "2026-05-23", "2026-05-30",
    "2026-06-06", "2026-06-13", "2026-06-20", "2026-06-27",
    "2026-07-04", "2026-07-11", "2026-07-18", "2026-08-01",
    "2026-08-08", "2026-08-15",
)


def _run(*args: str) -> None:
    print("$ " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_rendered_contract() -> None:
    out = ROOT / "output"
    analysis = (out / "analysis.html").read_text(encoding="utf-8")
    article_path = out / "briefs" / "trident-resolve-regional-scale-specific-chinese-tasks.html"
    from core.mindef_public_boundary import editorial_hold
    no17_sidecar = json.loads((ROOT / "briefs" / (article_path.stem + ".json")).read_text(encoding="utf-8"))
    no17_held = editorial_hold(no17_sidecar)
    if no17_held:
        assert not article_path.exists() and article_path.stem not in analysis, "held No. 17 appeared in public output"
    else:
        article = article_path.read_text(encoding="utf-8")
    historical = (out / "the-pla-watch" / "posts" / "2026-08-15.html").read_text(
        encoding="utf-8")
    no12 = (out / "the-pla-watch" / "posts" / "2026-08-01.html").read_text(
        encoding="utf-8")
    brief23_slug = "china-western-pacific-deployment-coordination-2026"
    brief23 = (out / "briefs" / (brief23_slug + ".html")).read_text(encoding="utf-8")
    assert brief23_slug in analysis and brief23_slug in (out / "index.html").read_text(encoding="utf-8")
    assert brief23_slug in (out / "briefs" / "feed.xml").read_text(encoding="utf-8")
    assert brief23_slug in (out / "sitemap.xml").read_text(encoding="utf-8")
    for required in ("Benjamin Yang", "Edited by Dylan Tanzi", "Research and analysis by Peter",
                     "Archival image; does not depict the November 2026 deployment.",
                     "liaoning-j15-20220506-cover-800.webp"):
        assert required in brief23, f"No. 23 article is missing {required!r}"
    for route in ("record/cited-b9a27aaa35d15b52.html", "record/cited-984b3bff98a5a213.html"):
        assert (out / route).is_file(), f"No. 23 cited record is missing: {route}"
    for route in ("assets/editorial/derivatives/liaoning-j15-20220506-cover-1600.jpg",
                  "assets/editorial/derivatives/liaoning-j15-20220506-cover-800.webp",
                  "assets/editorial/derivatives/liaoning-j15-20220506-cover-1600.webp",
                  "assets/catalogue/media/no-23-liaoning-j15-20220506-cover.jpg"):
        assert _sha256(ROOT / "site" / route) == _sha256(out / route), f"No. 23 asset mismatch: {route}"
    brief24_slug = "singapore-indonesia-first-joint-fighter-patrol"
    brief24 = (out / "briefs" / (brief24_slug + ".html")).read_text(encoding="utf-8")
    assert brief24_slug in analysis and brief24_slug in (out / "index.html").read_text(encoding="utf-8")
    assert brief24_slug in (out / "briefs" / "feed.xml").read_text(encoding="utf-8")
    assert brief24_slug in (out / "sitemap.xml").read_text(encoding="utf-8")
    assert brief24_slug + ".html" in brief23, "No. 23 must link forward to No. 24"
    for required in ("Benjamin Yang", "Dylan Tanzi", "Lead Research Analyst",
                     "Context image; does not depict the November 2026 joint patrol.",
                     "does not imply or constitute DoW endorsement",
                     "patkor-indopura-context-2025-800.webp"):
        assert required in brief24, f"No. 24 article is missing {required!r}"
    assert "no-24-patkor-indopura-context-2025.jpg" in analysis, "No. 24 catalogue card is missing its admitted photograph"
    for route in ("assets/editorial/derivatives/patkor-indopura-context-2025-1600.jpg",
                  "assets/editorial/derivatives/patkor-indopura-context-2025-800.webp",
                  "assets/editorial/derivatives/patkor-indopura-context-2025-1600.webp",
                  "assets/catalogue/media/no-24-patkor-indopura-context-2025.jpg"):
        assert _sha256(ROOT / "site" / route) == _sha256(out / route), f"No. 24 asset mismatch: {route}"

    if not no17_held:
        assert "no-17-trident-resolve-basarnas-drone.jpg" in analysis, (
            "No. 17 catalogue card is missing its admitted photograph")
    assert "no-08-liaoning-j15-recovery.jpg" in analysis, (
        "No. 8's existing catalogue photograph disappeared")
    assert "no-09-scarborough-shoal-iss.jpg" in analysis, (
        "No. 9's existing catalogue photograph disappeared")
    if not no17_held:
        for required in (
            "trident-resolve-basarnas-drone-800.webp",
            "9957254",
            "Sgt. 1st Class Timothy Hughes",
            "does not imply or constitute DoW endorsement",
        ):
            assert required in article, f"No. 17 article is missing {required!r}"
    assert "Adjacent historical issues" in historical, (
        "historical Brief navigation is absent from the rerendered article")
    assert "Downloaded from PLA Daily / 81.cn" not in no12, (
        "the prohibited No. 12 collector note has appeared")
    assert (ROOT / "site" / "assets" / "editorial" / "trident-resolve-basarnas-drone.jpg").is_file(), (
        "verified source photograph is missing from the editorial source tree")
    if not no17_held:
        for rel in (
            "assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg",
            "assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp",
            "assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp",
            "assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg",
        ):
            assert (out / rel).is_file(), f"required No. 17 asset is missing: {rel}"
        for source_rel, output_rel in (
            ("site/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg",
             "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg"),
            ("site/assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp",
             "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp"),
            ("site/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp",
             "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp"),
            ("site/assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg",
             "output/assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg"),
        ):
            assert _sha256(ROOT / source_rel) == _sha256(ROOT / output_rel), (
                "public output asset hash mismatch: " + output_rel)
    for date in HISTORICAL_DATES:
        assert (out / "the-pla-watch" / "posts" / f"{date}.html").is_file(), (
            f"historical Brief page missing after render: {date}")
    _assert_approved_brief_records_delivered(out)


def _assert_approved_brief_records_delivered(out: Path) -> None:
    """A fresh render carries every approved Brief and each cited Record.

    The committed snapshot may predate a newly approved Brief; the release
    render may not. Each route must exist and meet the delivery budgets.
    """
    from core.brief_collection import load_collection
    from core.cited_source_records import resolve
    from core.desk_registry import load_registry
    from scripts.verify_frontend_delivery import verify
    collection = load_collection([], load_registry(), briefs_dir=ROOT / "briefs")
    routes = {b["url"] for b in collection.briefs}
    routes |= {r["record_path"] for r in resolve(collection)[0]}
    missing = sorted(route for route in routes if not (out / route).is_file())
    assert not missing, "approved Brief routes missing from the render: " + "; ".join(missing)
    result = verify(out, only=routes)
    assert result["routes_checked"] == len(routes)
    assert not result["failures"], "approved Brief routes over delivery budget: " + "; ".join(
        f["route"] for f in result["failures"])


def _check_db_and_worktree(db_hash: str) -> None:
    db = ROOT / "pla_watch.db"
    if _sha256(db) != db_hash:
        raise RuntimeError("pla_watch.db changed during render")
    for suffix in ("-wal", "-shm"):
        if (ROOT / ("pla_watch.db" + suffix)).exists():
            raise RuntimeError("database sidecar appeared: pla_watch.db" + suffix)
    subprocess.run(
        ["git", "diff", "--exit-code", "--", "pla_watch.db"],
        cwd=ROOT, check=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    outside_output = [
        line for line in status
        if line[3:].strip() and not line[3:].startswith("output/")
    ]
    if outside_output:
        raise RuntimeError(
            "render changed files outside output/; refusing release: "
            + "; ".join(outside_output[:20]))


def _check_replay_delta(changed, *, verify_current=False):
    """Review replays must match HEAD; publication still requires a delta."""
    if verify_current:
        if changed:
            raise SystemExit("BLOCKED: committed Brief output differs from its render")
    elif not changed:
        raise SystemExit("BLOCKED: no changes to release")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope", choices=("report-only", "strict"), default="report-only",
        help="report-only produces a preview; strict refuses any unreviewed output path",
    )
    parser.add_argument(
        "--verify-current", action="store_true",
        help="CI-only replay check: require committed Brief output to be current; never publish",
    )
    args = parser.parse_args(argv)
    if args.verify_current and args.scope != "strict":
        parser.error("--verify-current requires --scope strict")
    db = ROOT / "pla_watch.db"
    if not db.is_file():
        raise SystemExit("BLOCKED: tracked pla_watch.db is missing")
    if any((ROOT / ("pla_watch.db" + suffix)).exists() for suffix in ("-wal", "-shm")):
        raise SystemExit("BLOCKED: pre-existing database sidecar; stop before rendering")
    initial_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if initial_status:
        raise SystemExit("BLOCKED: worktree must be clean before rendering")

    from scripts.guard_briefs_render_scope import classify_output_changes
    preexisting, _ = classify_output_changes(ROOT)
    if preexisting:
        raise SystemExit(
            "BLOCKED: pre-existing tracked, untracked, or ignored output drift: "
            + "; ".join(sorted(preexisting)[:20]))

    db_hash = _sha256(db)
    _run(sys.executable, "scripts/build_brief_cover.py", "--check")
    _run(sys.executable, "scripts/build_catalogue_media.py", "--check")
    _run(sys.executable, "scripts/rerender_pla_watch.py", "--no-covers")
    _run(sys.executable, "site/render.py", "--out", "output",
         "--site-origin", SITE_ORIGIN)
    _run(sys.executable, "scripts/validate_output.py")
    _assert_rendered_contract()
    _check_db_and_worktree(db_hash)

    from scripts.guard_briefs_render_scope import (
        classify_output_changes, restore_unreviewed_output,
    )
    changed, unexpected = classify_output_changes(ROOT)
    print(f"Briefs release output deltas before scope reconciliation: {len(changed)}")
    for path in sorted(changed):
        print(("OUT OF SCOPE: " if path in unexpected else "REVIEWED: ") + path)
    if unexpected and args.scope == "strict":
        print("Returning unreviewed generated routes to the committed HEAD baseline.")
        restore_unreviewed_output(ROOT, unexpected)
        _run(sys.executable, "scripts/validate_output.py")
        _assert_rendered_contract()
        _check_db_and_worktree(db_hash)
        changed, unexpected = classify_output_changes(ROOT)
        print(f"Briefs release output deltas after reconciliation: {len(changed)}")
        for path in sorted(changed):
            print(("BLOCKED: " if path in unexpected else "REVIEWED: ") + path)
    elif unexpected:
        print("PREVIEW ONLY: unexpected output paths are reported, not published.")
    if unexpected:
        print("Unreviewed output drift remains after reconciliation:")
        for path in sorted(unexpected):
            print("  " + path)
        if args.scope == "strict":
            raise SystemExit("BLOCKED: strict release scope failed; do not commit or deploy")
    elif args.verify_current:
        _check_replay_delta(changed, verify_current=True)
        print("Committed Brief output matches the governed render; verification only.")
    elif not changed:
        print("No generated output changes.")
        if args.scope == "strict":
            _check_replay_delta(changed)
    else:
        print("Final output scope is within the explicit Briefs release allow-list.")
    if args.scope == "strict" and (
        ROOT / "output" / "assets" / "editorial" / "trident-resolve-basarnas-drone.jpg"
    ).exists():
        raise SystemExit(
            "BLOCKED: unmodified source JPEG must not be present in public output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
