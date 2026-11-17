"""
The regional atlas: one real coastline, used on the Desks page and the desk pages.

Geometry. Natural Earth 1:50m land and de facto boundary lines (public domain,
via world-atlas 2.0.2, ISC), as `scripts/desk_map.py` projected and generalized
them for the retired Desks map (Miller cylindrical, 10 units per degree of
longitude, Douglas-Peucker 0.06 degrees). The raw TopoJSON was never committed,
so this module does not rebuild from it: `--extract` reads that committed
generated SVG out of git history (blob pinned below by its SHA-256), clips it to
the atlas frame and writes `site/assets/geo/atlas-50m.json`. That JSON is the
source of truth from then on.

Drawing. `python scripts/build_atlas.py` turns the JSON into
`site/assets/geo/atlas.svg` and `atlas.receipt.json`, deterministically (same
input, same bytes; the receipt holds hashes, never a time). The sea is drawn
with *waterlines*: the real coastline's outline repeated at fixed offsets, an
engraved-chart convention. They show distance from the drawn coast and nothing
else: no depth, relief, terrain or coverage.

Placement. `atlas_view()` and `locator_view()` project a desk's seat
(`desks/geography.json`) into the same frame at render time, so a seat always
lands on the coastline the asset drew. A seat marks where a desk's publishing
institutions are based, never an area of coverage.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GEOGRAPHY = REPO_ROOT / "desks" / "geography.json"
GEO_DIR = REPO_ROOT / "site" / "assets" / "geo"
SOURCE_JSON = GEO_DIR / "atlas-50m.json"
ATLAS_SVG = GEO_DIR / "atlas.svg"
RECEIPT = GEO_DIR / "atlas.receipt.json"

# The retired generated geometry this atlas is cut from.
RETIRED_COMMIT = "46f7431982f355b2612f135fee517f7a83f6549e"
RETIRED_PATH = "site/preview/templates/_desk_map_geo.svg"
RETIRED_SHA256 = "6358018ee3827f43e09543baef1d5578cd981e768ac502c36e7a95e9099ce012"
# The retired frame (desk_map.py): origin at 60E, 54N.
OLD_LON_W, OLD_LAT_N = 60.0, 54.0

K = 10.0                       # units per degree of longitude
# The asset frame: wide enough that every view cut from it (the Desks atlas
# and each desk's locator) sits well inside, so no clipped edge or its
# waterlines ever shows.
LON_W, LON_E = 84.0, 160.0
LAT_N, LAT_S = 52.0, -18.0
# The Desks-page view: tight to the seats, the Bay of Bengal to the Philippine Sea.
VIEW = {"lon": (94.0, 148.0), "lat": (45.5, -10.5)}
# A desk page's locator: a regional window, never a city-scale zoom (at
# 1:50m a close crop would draw Singapore as five points).
LOCATOR_SPAN = (26.0, 26.0)   # degrees of longitude, degrees of Miller height
# Where an outside desk's edge pointer meets the east edge: open ocean, and
# deliberately not the latitude of any former seat.
OUTSIDE_EDGE_LAT = 2.5

# Waterline offsets from the coast, in units, nearest first, with the share of
# the line colour mixed into the sea for each.
WATERLINES = ((2.4, .50), (5.2, .38), (8.6, .28), (12.8, .2), (18.0, .13))
LINE_W = .62
SEA = (0xE1, 0xEE, 0xEA)      # --accent-tint
LINE = (0x17, 0x6C, 0x6C)     # --accent
LAND = "#F8F6EF"
COAST = "#2E4C56"
BORDER = "#8C9C9A"
GRATICULE = "#CDDBD7"


def _miller(lat: float) -> float:
    phi = math.radians(lat)
    return math.degrees(1.25 * math.log(math.tan(math.pi / 4 + 0.4 * phi)))


Y_TOP = _miller(LAT_N)
WIDTH = round((LON_E - LON_W) * K)
HEIGHT = round((Y_TOP - _miller(LAT_S)) * K)


def project(lon: float, lat: float) -> tuple:
    return ((lon - LON_W) * K, (Y_TOP - _miller(lat)) * K)


# ── extraction (run once; reads git history) ─────────────────────────────────

_NUM = r"-?\d+(?:\.\d+)?"


def _subpaths(d: str):
    for chunk in re.findall(r"M[^M]*", d):
        pts = [(float(x), float(y)) for x, y in re.findall(r"(%s)[ ,](%s)" % (_NUM, _NUM), chunk)]
        yield pts, chunk.rstrip().endswith("Z")


def _clip_ring(pts, x0, y0, x1, y1):
    """Sutherland-Hodgman against the rectangle; each ring alone, which keeps
    the even-odd fill of the whole set intact."""
    def clip(points, inside, cross):
        out = []
        for i, cur in enumerate(points):
            prev = points[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
        return out

    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))

    def at_y(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y)

    for inside, cross in ((lambda p: p[0] >= x0, at_x(x0)), (lambda p: p[0] <= x1, at_x(x1)),
                          (lambda p: p[1] >= y0, at_y(y0)), (lambda p: p[1] <= y1, at_y(y1))):
        if not pts:
            break
        pts = clip(pts, inside, cross)
    return pts


def _clip_line(pts, x0, y0, x1, y1):
    """Keep the runs of a polyline inside the rectangle (vertices only; a
    segment leaving the frame ends the run, which is invisible at the pad)."""
    runs, run = [], []
    for x, y in pts:
        if x0 <= x <= x1 and y0 <= y <= y1:
            run.append((x, y))
        else:
            if len(run) > 1:
                runs.append(run)
            run = []
    if len(run) > 1:
        runs.append(run)
    return runs


def extract() -> dict:
    blob = subprocess.run(["git", "show", "%s:%s" % (RETIRED_COMMIT, RETIRED_PATH)],
                          cwd=REPO_ROOT, check=True, capture_output=True).stdout
    if hashlib.sha256(blob).hexdigest() != RETIRED_SHA256:
        raise SystemExit("retired geometry does not match its pinned SHA-256")
    svg = blob.decode("utf-8")
    land_d = re.search(r'class="dm-land"[^>]*\sd="([^"]+)"', svg).group(1)
    border_d = re.search(r'class="dm-borders"[^>]*\sd="([^"]+)"', svg).group(1)
    dx = (LON_W - OLD_LON_W) * K
    dy = (_miller(OLD_LAT_N) - Y_TOP) * K
    pad = 24.0   # beyond the widest waterline, so a clipped edge never draws one in view
    box = (-pad, -pad, WIDTH + pad, HEIGHT + pad)

    def shift(pts):
        return [(round(x - dx, 1), round(y - dy, 1)) for x, y in pts]

    land = []
    for pts, closed in _subpaths(land_d):
        ring = _clip_ring(shift(pts), *box)
        if len(ring) >= 3:
            land.append([[round(x, 1), round(y, 1)] for x, y in ring])
    # Singapore island fell under the retired map's smallest-ring cut; that
    # map kept it only as the desk's own emphasis polygon. It is restored to
    # the land here so the Singapore seat stands on it. It does not touch any
    # other ring, so the even-odd fill is unchanged elsewhere.
    sg_d = re.search(r'id="dm-geo-singapore"[^>]*\sd="([^"]+)"', svg).group(1)
    for pts, _ in _subpaths(sg_d):
        land.append([[x, y] for x, y in shift(pts)])
    borders = []
    for pts, _ in _subpaths(border_d):
        for run in _clip_line(shift(pts), *box):
            borders.append([[x, y] for x, y in run])
    return {
        "_comment": [
            "Natural Earth 1:50m land rings and de facto boundary lines (public domain, via",
            "world-atlas 2.0.2, ISC), as projected and generalized by scripts/desk_map.py",
            "(Miller, 10 units per degree of longitude, Douglas-Peucker 0.06 degrees), cut",
            "from the retired generated SVG pinned below and clipped to this frame. No",
            "boundary claim is made. Rebuild the drawing with python scripts/build_atlas.py.",
        ],
        "source": {"commit": RETIRED_COMMIT, "path": RETIRED_PATH, "sha256": RETIRED_SHA256,
                   "natural_earth_inputs": {
                       "countries-50m.json": "04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394"}},
        "frame": {"lon": [LON_W, LON_E], "lat": [LAT_N, LAT_S], "units_per_degree": K,
                  "width": WIDTH, "height": HEIGHT, "projection": "Miller cylindrical"},
        "land": land,
        "borders": borders,
    }


# ── drawing ──────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _path(lines, closed) -> str:
    out = []
    for pts in lines:
        out.append("M" + "L".join("%s %s" % (_fmt(x), _fmt(y)) for x, y in pts) + ("Z" if closed else ""))
    return "".join(out)


def _mix(share: float) -> str:
    return "#%02X%02X%02X" % tuple(round(s + (l - s) * share) for s, l in zip(SEA, LINE))


def draw(src: dict) -> str:
    sea = "#%02X%02X%02X" % SEA
    grat = []
    for lon in range(90, 161, 10):
        x = project(lon, 0)[0]
        grat.append("M%s 0V%s" % (_fmt(x), HEIGHT))
    for lat in (-10, 0, 10, 20, 30, 40, 50):
        y = project(LON_W, lat)[1]
        grat.append("M0 %sH%s" % (_fmt(y), WIDTH))
    rings = []
    for off, share in reversed(WATERLINES):
        rings.append('<use href="#l" stroke="%s" stroke-width="%s"/>' % (_mix(share), _fmt(2 * off + LINE_W)))
        rings.append('<use href="#l" stroke="%s" stroke-width="%s"/>' % (sea, _fmt(2 * off - LINE_W)))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 %d %d" width="%d" height="%d">\n' % (WIDTH, HEIGHT, WIDTH, HEIGHT)
        + "<!-- Indo-Pacific Record regional atlas. Natural Earth 1:50m (public domain; "
          "world-atlas 2.0.2, ISC), Miller projection, generalized; de facto lines, no "
          "boundary claim. Waterlines repeat the coastline at fixed offsets: distance "
          "from the drawn coast, not depth. Generated by scripts/build_atlas.py; do not "
          "edit by hand. -->\n"
        + '<defs><path id="l" fill-rule="evenodd" d="%s"/></defs>\n' % _path(src["land"], True)
        + '<rect width="%d" height="%d" fill="%s"/>\n' % (WIDTH, HEIGHT, sea)
        + '<path d="%s" fill="none" stroke="%s" stroke-width=".6"/>\n' % ("".join(grat), GRATICULE)
        + '<g fill="none" stroke-linejoin="round">%s</g>\n' % "".join(rings)
        + '<use href="#l" fill="%s" stroke="%s" stroke-width=".7" stroke-linejoin="round"/>\n' % (LAND, COAST)
        + '<path d="%s" fill="none" stroke="%s" stroke-width=".55" stroke-dasharray="2.4 1.4" '
          'stroke-linejoin="round"/>\n' % (_path(src["borders"], False), BORDER)
        + "</svg>\n"
    )


def build() -> dict:
    src = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    svg = draw(src).encode("utf-8")
    ATLAS_SVG.write_bytes(svg)
    receipt = {
        "generator": "scripts/build_atlas.py",
        "source": {"file": SOURCE_JSON.name,
                   "sha256": hashlib.sha256(SOURCE_JSON.read_bytes()).hexdigest(),
                   "cut_from": src["source"]},
        "licence": "Natural Earth: public domain. world-atlas: ISC.",
        "outputs": {ATLAS_SVG.name: {"bytes": len(svg), "sha256": hashlib.sha256(svg).hexdigest()}},
        "meaning": "Waterlines are offsets of the drawn coastline: distance from the coast, "
                   "not depth, terrain or coverage.",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


# ── render time ──────────────────────────────────────────────────────────────

def _places() -> dict:
    return json.loads(GEOGRAPHY.read_text(encoding="utf-8"))["desks"]


def _pct(v: float) -> str:
    return ("%.2f" % v).rstrip("0").rstrip(".") + "%"


def _window(x0, y0, w, h) -> dict:
    """CSS for showing the rectangle (x0, y0, w, h) of the asset as a
    background: its size and position in percentages of the box."""
    return {
        "size": "%s auto" % _pct(WIDTH / w * 100),
        "position": "%s %s" % (_pct(x0 / (WIDTH - w) * 100), _pct(y0 / (HEIGHT - h) * 100)),
        "ratio": "%s / %s" % (_fmt(w), _fmt(h)),
    }


def atlas_view(desks) -> dict:
    """The Desks-page atlas: the view rectangle and, for each registry desk in
    `desks` with a placed seat, its position as percentages of that view."""
    (lw, le), (ln, ls) = VIEW["lon"], VIEW["lat"]
    x0, y0 = project(lw, ln)
    x1, y1 = project(le, ls)
    w, h = x1 - x0, y1 - y0
    places = _places()
    seats, outside = [], []
    for d in desks:
        p = places.get(d.slug)
        if not p:
            continue
        if p.get("outside"):
            outside.append({"desk": d, "place": p["outside"], "short": p.get("short", d.name),
                            "y": _pct((project(le, OUTSIDE_EDGE_LAT)[1] - project(lw, ln)[1])
                                      / (project(le, ls)[1] - project(lw, ln)[1]) * 100)})
            continue
        x, y = project(*p["anchor"])
        if not (x0 < x < x1 and y0 < y < y1):
            raise ValueError("%s's seat is outside the atlas view" % d.slug)
        seats.append({"desk": d, "seat": p["seat"], "label": p.get("label", "right"),
                      "label_narrow": p.get("label_narrow", p.get("label", "right")),
                      "short": p.get("short", d.name),
                      "x": _pct((x - x0) / w * 100), "y": _pct((y - y0) / h * 100)})
    return {"window": _window(x0, y0, w, h), "seats": seats, "outside": outside,
            "graticule": _graticule_labels(x0, y0, w, h)}


def _graticule_labels(x0, y0, w, h) -> dict:
    lons = [(lon, _pct((project(lon, 0)[0] - x0) / w * 100)) for lon in range(100, 150, 10)
            if x0 < project(lon, 0)[0] < x0 + w]
    lats = [(lat, _pct((project(LON_W, lat)[1] - y0) / h * 100)) for lat in (40, 30, 20, 10, 0, -10)
            if y0 < project(LON_W, lat)[1] < y0 + h]
    return {
        "lon": [{"text": "%d°E" % lon, "at": at} for lon, at in lons],
        "lat": [{"text": ("%d°%s" % (abs(lat), "N" if lat > 0 else "S")) if lat else "0°", "at": at}
                for lat, at in lats],
    }


def locator_view(slug: str):
    """A desk page's locator: a regional window on the same asset with the
    seat inside it, or None for a desk with no seat in the frame."""
    p = _places().get(slug)
    if not p or p.get("outside"):
        return None
    sx, sy = project(*p["anchor"])
    w, h = LOCATOR_SPAN[0] * K, LOCATOR_SPAN[1] * K
    x0 = min(max(sx - w / 2, 0), WIDTH - w)
    y0 = min(max(sy - h * .55, 0), HEIGHT - h)
    return {"window": _window(x0, y0, w, h), "seat": p["seat"],
            "x": _pct((sx - x0) / w * 100), "y": _pct((sy - y0) / h * 100)}


if __name__ == "__main__":
    if sys.argv[1:] == ["--extract"]:
        data = extract()
        SOURCE_JSON.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
        print("wrote %s: %d rings, %d border runs" % (SOURCE_JSON, len(data["land"]), len(data["borders"])))
    elif not sys.argv[1:]:
        print(json.dumps(build(), indent=1))
    else:
        raise SystemExit("usage: build_atlas.py [--extract]")
