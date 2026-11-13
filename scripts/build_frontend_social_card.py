#!/usr/bin/env python3
"""Rebuild IPR's 1200x630 publication social card from its approved cover.

The HTML is self-contained and embeds the public-domain U.S. Navy photograph.
Only local assets are used. Run with Playwright/Chromium and Pillow installed.
"""
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "site" / "assets"
SOURCE = ROOT / "scripts" / "templates" / "ipr-featured-social-card.html"
TARGET = ASSETS / "frontend" / "ipr-social-card-1200x630.png"
RECEIPT = ASSETS / "frontend" / "SOCIAL_CARD.json"


def build():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    with tempfile.TemporaryDirectory(prefix="ipr-social-card-") as tmp:
        raw = Path(tmp) / "source.png"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1248, "height": 690},
                                        device_scale_factor=1)
                page.goto(SOURCE.as_uri(), wait_until="load")
                page.wait_for_function(
                    "() => {const i=document.querySelector('img.real');"
                    "return i && i.complete && i.naturalWidth > 0;}")
                page.locator(".card").screenshot(path=str(raw), animations="disabled")
            finally:
                browser.close()
        image = Image.open(raw).convert("RGB")
        if image.size != (1200, 630):
            raise ValueError("Unexpected social card dimensions: %r" % (image.size,))
        # Palette optimization preserves the designed layout and meets the
        # 300 KB social-card budget checked by tests/test_identity_assets.py.
        image.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                       dither=Image.Dither.NONE).save(TARGET, optimize=True)
    if TARGET.stat().st_size >= 300 * 1024:
        raise ValueError("Social card exceeds the 300 KB budget")
    payload = {
        "builder": "scripts/build_frontend_social_card.py",
        "template": "scripts/templates/ipr-featured-social-card.html",
        "file": TARGET.name,
        "width": 1200,
        "height": 630,
        "bytes": TARGET.stat().st_size,
        "sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "source": "U.S. Navy / Nathan Burke, 23 November 2015; public domain",
    }
    RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
