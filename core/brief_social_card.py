"""Photographic link previews for IPR Briefs, using individually verified covers.

The caller must supply a cover already admitted by core.brief_photography.
No synthetic/AI photographs, web downloads or alternate image lookups are
permitted. A cover's social-sharing rights must also be reviewed before release.
"""

from __future__ import annotations

from datetime import date
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

CARD_SIZE = (1200, 630)
MAX_BYTES = 350 * 1024
GROUND = (8, 34, 44)
PAPER = (245, 243, 235)
MIST = (188, 209, 211)
ACCENT = (103, 193, 187)


def _font(size: int, *, serif: bool = False):
    """Prefer ordinary platform faces, with an always-available Pillow fallback."""
    for name in (("DejaVuSerif.ttf", "LiberationSerif-Regular.ttf")
                 if serif else ("DejaVuSans.ttf", "LiberationSans-Regular.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def _wrap(draw, value: str, font, width: int):
    result, line = [], ""
    for word in value.split():
        candidate = (line + " " + word).strip()
        if line and draw.textlength(candidate, font=font) > width:
            result.append(line)
            line = word
        else:
            line = candidate
    if line:
        result.append(line)
    return result


def _photo_crop(path: Path) -> Image.Image:
    with Image.open(path) as opened:
        if opened.format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError("social photo must be a real approved raster")
        return ImageOps.fit(opened.convert("RGB"), (735, CARD_SIZE[1]),
                            method=Image.Resampling.LANCZOS,
                            centering=(0.5, 0.48))


def render_brief_social_card(path: Path, *, title: str, issue: int,
                             week_ending: str, photo_file: Path,
                             photo: dict, byline: str = "") -> str:
    """Compose a genuine approved photograph, no simulations or substitutes."""
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
        raise ValueError("a published Brief requires a numbered issue")
    title = " ".join(title.split())
    if not title or not str(photo.get("credit") or "").strip():
        raise ValueError("a published photo preview requires title and credit")
    if photo.get("depicts") not in ("event", "context"):
        raise ValueError("photographic provenance must identify event or context")
    if photo.get("license") not in ("CC BY 4.0", "Public domain"):
        raise ValueError("photographic source licence not verified")
    if not str(photo.get("source_page") or "").startswith("https://"):
        raise ValueError("photographic source page missing")
    day = date.fromisoformat(week_ending)
    image = Image.new("RGB", CARD_SIZE, GROUND)
    photograph = _photo_crop(Path(photo_file))
    image.paste(photograph, (465, 0))

    # Semi-transparent dark tint helps the image sit behind a steep editorial
    # diagonal; the photograph remains the actual source photo.
    ink = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    g = ImageDraw.Draw(ink)
    g.polygon([(0, 0), (830, 0), (585, 630), (0, 630)], fill=(5, 35, 43, 249))
    g.polygon([(815, 0), (847, 0), (600, 630), (569, 630)], fill=(11, 118, 120, 136))
    g.rectangle((0, 0, 11, 630), fill=(108, 190, 181, 255))
    # Dark photograph footrail for factual attribution.
    g.rectangle((0, 566, 1200, 630), fill=(3, 23, 30, 245))
    image = Image.alpha_composite(image.convert("RGBA"), ink)
    d = ImageDraw.Draw(image)

    d.text((63, 53), "ipr", font=_font(43, serif=True), fill=PAPER)
    d.rectangle((158, 60, 161, 98), fill=ACCENT)
    d.text((182, 63), "INDO-PACIFIC RECORD", font=_font(22), fill=PAPER)
    d.text((64, 138), f"BRIEFS    /    NO. {issue}", font=_font(19), fill=ACCENT)
    readable = f"{day.day} {day.strftime('%B')} {day.year}"
    d.text((64, 169), f"Week ending {readable}", font=_font(18), fill=MIST)

    chosen = None
    for size in range(59, 33, -2):
        face = _font(size, serif=True)
        lines = _wrap(d, title, face, 610)
        if len(lines) <= 5 and len(lines) * (size + 10) <= 304:
            chosen = (face, lines, size + 10)
            break
    if chosen is None:
        raise ValueError("Brief title cannot fit photographic preview")
    face, lines, lh = chosen
    y = 217
    for line in lines:
        d.text((62, y), line, font=face, fill=PAPER)
        y += lh

    if byline:
        d.rectangle((64, 552, 97, 555), fill=ACCENT)
        d.text((108, 540), "By " + byline, font=_font(19), fill=PAPER)

    # Essential: keep the archival year and actual creator on the artwork.
    year = re.search(r"\\b(?:19|20)\\d{2}\\b", str(photo.get("date_note") or ""))
    if photo["depicts"] == "context":
        archive = "ARCHIVAL PHOTO" + ((" · " + year.group(0)) if year else "")
    else:
        archive = "SOURCE PHOTOGRAPH"
    d.text((730, 539), archive, font=_font(16), fill=PAPER)

    # Attribution is inside the shared image because the social platform
    # normally does not display page captions or licensing metadata.
    credit = str(photo["credit"])
    if photo["license"] == "CC BY 4.0":
        credit += " · Cropped / color-treated by IPR"
    for label, y in ((credit, 572), ((photo.get("notice") or "").strip(), 600)):
        if not label:
            continue
        for size in range(14, 9, -1):
            face = _font(size)
            if d.textlength(label, font=face) <= 1135:
                d.text((30, y), label, font=face, fill=PAPER)
                break
        else:
            raise ValueError("source credit or required notice too long to display")

    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=86, optimize=True, subsampling=1)
    if path.stat().st_size > MAX_BYTES:
        path.unlink(missing_ok=True)
        raise ValueError("photographic JPEG preview exceeds image budget")
    return (f"Indo-Pacific Record Brief No. {issue}: {title}. "
            f"Photographic context: {photo.get('alt', '')}. "
            f"Credit: {credit}.")
