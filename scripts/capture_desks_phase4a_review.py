"""Generate actual Desks directory screenshots and DOM receipts, off production.

Run on a PR head after Playwright Chromium is installed. The candidate builder
writes only to a fresh disposable directory, preserving output/ and the DB.

Capture the regional atlas and directory together. Verify that all eight
registry desks are listed with their registry state, that the directory
fits the viewport, and that its content remains available without JavaScript
and in forced colours.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "preview"))

import generate_preview as gp  # noqa: E402
from core.desk_registry import load_registry  # noqa: E402
from tests.test_desks_phase4_browser import PROBE, WIDTHS  # noqa: E402

OUT = ROOT / "phase4a-visual-receipt"
REGISTER = ".deskmap-register"


def main() -> int:
    OUT.mkdir(exist_ok=True)
    registry = {e.slug: e for e in load_registry().public_entries}
    failures = []
    receipts = []
    with tempfile.TemporaryDirectory(prefix="ipr-p4a-visual-") as temp:
        destination = Path(temp) / "build"
        gp.build(
            destination,
            "Indo-Pacific Record",
            ROOT / "pla_watch.db",
            snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
        )
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for width in WIDTHS:
                    page = browser.new_page(
                        viewport={"width": width, "height": 900},
                        reduced_motion="reduce",
                    )
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto((destination / "desks.html").as_uri(), wait_until="load")
                    rows = page.evaluate(PROBE)
                    doc_width = page.evaluate("document.documentElement.scrollWidth")
                    result = {"width": width, "rows": rows, "docWidth": doc_width,
                              "page_errors": errors}
                    receipts.append(result)
                    if len(rows) != len(registry) or {r["slug"] for r in rows} != set(registry):
                        failures.append(f"{width}: incomplete desk register")
                    for row in rows:
                        entry = registry.get(row["slug"])
                        if entry and row["state"] != entry.status_label:
                            failures.append(f"{width}: {row['slug']} state is not the registry label")
                        if row["right"] > width + 1:
                            failures.append(f"{width}: {row['slug']} overflows")
                    if errors:
                        failures.append(f"{width}: page_errors: {errors}")
                    if doc_width > width + 1:
                        failures.append(f"{width}: horizontal overflow {doc_width}")
                    if width in (375, 768, 1280, 1600):
                        page.locator(".desks-head").screenshot(
                            path=str(OUT / f"atlas-{width}.png")
                        )
                        page.locator(REGISTER).screenshot(
                            path=str(OUT / f"desks-{width}.png")
                        )
                    page.close()

                context = browser.new_context(
                    viewport={"width": 375, "height": 812},
                    java_script_enabled=False,
                    reduced_motion="reduce",
                )
                nojs = context.new_page()
                nojs.goto((destination / "desks.html").as_uri(), wait_until="load")
                count = nojs.locator(REGISTER + " section.desk").count()
                receipts.append({"mode": "no-js", "desk_count": count})
                nojs.locator(REGISTER).screenshot(path=str(OUT / "desks-nojs-375.png"))
                if count != len(registry):
                    failures.append("no-JS mode does not list every desk")
                context.close()

                forced = browser.new_page(
                    viewport={"width": 375, "height": 812},
                    forced_colors="active",
                    reduced_motion="reduce",
                )
                forced.goto((destination / "desks.html").as_uri(), wait_until="load")
                # Text is legible in forced colours when the page leaves the
                # system colours in charge (forced-color-adjust is not "none")
                # and the text colour differs from the background it actually
                # sits on: the nearest ancestor with an opaque background, or
                # the Canvas the browser paints behind the page.
                sample = forced.evaluate("""() => {
                    const ground = el => {
                        for (let n = el; n; n = n.parentElement) {
                            const b = getComputedStyle(n).backgroundColor;
                            if (b && b !== 'transparent' && !/,\\s*0\\)$/.test(b)) return b;
                        }
                        return getComputedStyle(document.documentElement).color === 'rgb(255, 255, 255)'
                            ? 'rgb(0, 0, 0)' : 'rgb(255, 255, 255)';
                    };
                    const probe = sel => {
                        const el = document.querySelector(sel), s = getComputedStyle(el);
                        return {text: s.color, ground: ground(el), adjust: s.forcedColorAdjust};
                    };
                    return {state: probe('.desk-state'), link: probe('.deskmap-register h3 a')};
                }""")
                receipts.append({"mode": "forced-colors", "sample": sample})
                for name, probe in sample.items():
                    if probe["adjust"] == "none":
                        failures.append(f"forced colours: desk {name} opts out of system colours")
                    if probe["text"] == probe["ground"]:
                        failures.append(f"forced colours: desk {name} text matches its background")
                forced.locator(REGISTER).screenshot(path=str(OUT / "desks-forced-colors-375.png"))
                forced.close()
            finally:
                browser.close()

    (OUT / "measurements.json").write_text(
        json.dumps(
            {"viewport_receipts": receipts, "failures": failures},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"viewports": len(WIDTHS), "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
