"""Original text-only social cards for published Indo-Pacific Record Briefs.

No external images or publisher-derived media are used. Titles, numbers and
week-ending dates come from the approved Brief's existing publication sidecar.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CARD_SIZE = (1200, 630)
MAX_BYTES = 300 * 1024
INK = (12, 33, 42)
PAPER = (239, 244, 239)
MIST = (183, 207, 204)
ACCENT = (125, 195, 179)


def _font(size: int):
    """Use Pillow's bundled font, not an OS-dependent font or remote asset."""
    return ImageFont.load_default(size=size)


def _wrap(draw, value: str, font, width: int):
    rows = []
    line = ""
    for word in value.split():
        candidate = (line + " " + word).strip()
        if line and draw.textlength(candidate, font=font) > width:
            rows.append(line)
            line = word
        else:
            line = candidate
    if line:
        rows.append(line)
    return rows


def render_brief_social_card(path: Path, *, title: str, issue: int,
                             week_ending: str) -> str:
    """Write an IPR-owned 1200x630 PNG and return factual image alt text."""
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
        raise ValueError("a published Brief requires a numbered issue")
    title = " ".join(title.split())
    if not title:
        raise ValueError("a published Brief requires a title")
    day = date.fromisoformat(week_ending)
    img = Image.new("RGB", CARD_SIZE, INK)
    draw = ImageDraw.Draw(img)

    # Editorial ground and small geometric accents: no documentary imagery.
    for y in range(CARD_SIZE[1]):
        t = y / (CARD_SIZE[1] - 1)
        draw.line((0, y, CARD_SIZE[0], y), fill=(
            round(INK[0] + 8 * t), round(INK[1] + 16 * t),
            round(INK[2] + 15 * t)))
    draw.rectangle((0, 0, 12, 630), fill=ACCENT)
    draw.line((80, 112, 1120, 112), fill=(76, 116, 119), width=2)
    draw.text((82, 45), "ipr", font=_font(35), fill=PAPER)
    draw.text((157, 50), "Indo-Pacific Record Briefs", font=_font(25), fill=PAPER)
    date_label = f"{day.strftime('%B')} {day.day}, {day.year}"
    draw.text((84, 140), f"No. {issue}  ·  Week ending {date_label}",
              font=_font(24), fill=MIST)

    chosen = None
    for size in range(68, 35, -2):
        font = _font(size)
        lines = _wrap(draw, title, font, 1030)
        line_height = size + 13
        if len(lines) <= 4 and len(lines) * line_height <= 300:
            chosen = (font, lines, line_height)
            break
    if chosen is None:
        raise ValueError("Brief title exceeds card layout")
    font, lines, line_height = chosen
    y = 208
    for line in lines:
        draw.text((82, y), line, font=font, fill=PAPER)
        y += line_height

    draw.line((82, 547, 1120, 547), fill=(76, 116, 119), width=2)
    draw.text((84, 565), "indopacificrecord.org", font=_font(23), fill=MIST)
    draw.text((911, 565), "RESEARCH  /  BRIEFS", font=_font(21), fill=MIST)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True, compress_level=9)
    if path.stat().st_size > MAX_BYTES:
        path.unlink()
        raise ValueError("Brief social card exceeds 300 KB budget")
    return f"Indo-Pacific Record Briefs No. {issue}: {title}. Editorial link preview."
