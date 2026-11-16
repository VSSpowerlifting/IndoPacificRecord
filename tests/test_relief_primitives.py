"""
The relief primitives stay what the Phase 1 rulings allow.

DECISION_LOG 2026-10-10: three editorial lifts on six named surfaces and
nowhere else (B1=A); full-colour flags vendored with their MIT licence (B9=A);
geography built deterministically from Natural Earth and recorded in a receipt;
every illustration decorative; motion only behind reduced-motion, scripting
and scroll-timeline support. These checks hold those lines. Phase 2 links the
primitives into the homepage; Phase 2b adds the Archive, which takes only
`relief.css` and the finder lift (B1 names "the finder"). Phase 4A brings the Desks page into the same named-surface allowlist and
publishes its eight local flag SVGs with the MIT notice, but no glyph sprite.

2026-11-14, the parallel-text identity: no production page draws relief art or
links `relief.css` any longer. The primitives, their builder and the gallery
are still checked below; the production checks now hold that the home page,
the Records page, the Briefs catalogue and the Desks page stay clear of them.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import xml.dom.minidom
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts import build_geo_assets as geo  # noqa: E402

PREVIEW = REPO_ROOT / "site" / "preview"
TEMPLATES = PREVIEW / "templates"
RELIEF_CSS = PREVIEW / "relief.css"
ASSETS = REPO_ROOT / "site" / "assets"
TRACKED_DB = REPO_ROOT / "pla_watch.db"

SURFACES = ("rl-finder", "rl-card", "rl-analysis", "rl-brief", "rl-plate", "rl-scope")
LIFTS = ("none", "var(--lift-1)", "var(--lift-2)", "var(--lift-3)")
# flag-icons 7.3.2 (MIT), byte-identical to the release files.
FLAGS = ("cn", "id", "jp", "kr", "ph", "sg", "us", "vn")
GLYPHS = ("newspaper", "ministry", "agency", "journal", "portal", "feed")


def _square(x0, y0, x1, y1):
    """One closed ring as a quantized TopoJSON arc (hundredths of a degree)."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    q = [(round(x * 100), round(y * 100)) for x, y in pts]
    return [list(q[0])] + [[b[0] - a[0], b[1] - a[1]] for a, b in zip(q, q[1:])]


def synthetic_topology() -> dict:
    """Six countries as rectangles placed where the builder looks for them.
    It is not geography; it only exercises the builder's whole path."""
    shapes = {
        "156": [(100, 25, 120, 40)],
        "392": [(135, 33, 140, 38)],
        "704": [(105, 10, 108, 20)],
        "702": [(103.65, 1.25, 104.0, 1.45)],
        "458": [(103.4, 1.5, 104.2, 2.5)],
        "360": [(103.8, 0.8, 104.6, 1.15)],
        # Hawaii survives the keep filter; the continental ring must not.
        "840": [(-158, 19, -155, 22), (-120, 30, -80, 45)],
    }
    arcs, geometries = [], []
    for cid, rects in shapes.items():
        polys = []
        for rect in rects:
            polys.append([[len(arcs)]])
            arcs.append(_square(*rect))
        geometries.append({"type": "MultiPolygon", "id": cid, "arcs": polys})
    return {"type": "Topology",
            "transform": {"scale": [0.01, 0.01], "translate": [0, 0]},
            "objects": {"countries": {"type": "GeometryCollection",
                                      "geometries": geometries}},
            "arcs": arcs}


def _css_rules(css: str):
    """(selector, body) pairs for every innermost rule, at-rules unwrapped."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.findall(r"([^{};]+)\{([^{}]*)\}", css)


class GeoBuilderTests(unittest.TestCase):
    """The builder is deterministic and its receipt matches what is committed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="relief-geo-"))
        topo = cls.tmp / "topo.json"
        topo.write_text(json.dumps(synthetic_topology()), encoding="utf-8")
        cls.first = cls.tmp / "a"
        cls.second = cls.tmp / "b"
        cls.result = geo.build(topo, topo, cls.first)
        geo.build(topo, topo, cls.second)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_same_inputs_give_the_same_bytes(self):
        names = sorted(p.name for p in self.first.iterdir())
        self.assertEqual(names, sorted(geo.SPRITES + (geo.RECEIPT,)))
        for name in names:
            self.assertEqual((self.first / name).read_bytes(),
                             (self.second / name).read_bytes(), name)

    def test_every_symbol_is_built_and_parses(self):
        ids = set()
        for name in geo.SPRITES:
            doc = xml.dom.minidom.parse(str(self.first / name))
            ids |= {s.getAttribute("id") for s in doc.getElementsByTagName("symbol")}
        for slug in geo.EMBLEMS:
            self.assertIn(slug, ids)
            self.assertIn(slug + "-seat", ids)
        self.assertTrue({"strait", "region", "region-china", "region-singapore"} <= ids)

    def test_hawaii_keeps_only_the_islands(self):
        d = self.result["geometry"]["hawaii"]["d"]
        self.assertEqual(d.count("M"), 1, "the continental ring was drawn")

    def test_receipt_records_hashes_and_no_time(self):
        rec = json.loads((self.first / geo.RECEIPT).read_text(encoding="utf-8"))
        for name in geo.SPRITES:
            data = (self.first / name).read_bytes()
            self.assertEqual(rec["outputs"][name],
                             {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        text = json.dumps(rec)
        self.assertNotRegex(text, r"\d{4}-\d\d-\d\dT|generated_at|timestamp")


class CommittedAssetTests(unittest.TestCase):
    """What is committed under site/assets is what its receipts describe."""

    def test_geo_outputs_match_the_committed_receipt(self):
        rec = json.loads((ASSETS / "geo" / geo.RECEIPT).read_text(encoding="utf-8"))
        self.assertEqual(sorted(rec["outputs"]), sorted(geo.SPRITES))
        for name, out in rec["outputs"].items():
            data = (ASSETS / "geo" / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), out["sha256"], name)
            self.assertEqual(len(data), out["bytes"], name)
        self.assertEqual(sorted(rec["inputs"]), ["10m", "50m"])
        for name in ("emblems.svg", "strait.svg", "region.svg"):
            self.assertIn(name, rec["outputs"])

    def test_every_svg_parses(self):
        # An XML comment may not contain "--"; one did, and the browser
        # silently drew nothing from the whole sprite.
        for path in sorted(ASSETS.glob("*/*.svg")):
            if path.parent.name in ("geo", "flags", "glyphs"):
                xml.dom.minidom.parse(str(path))

    def test_flags_are_vendored_with_their_licence(self):
        licence = (ASSETS / "flags" / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", licence)
        self.assertIn("Permission is hereby granted", licence)
        self.assertEqual(sorted(p.stem for p in (ASSETS / "flags").glob("*.svg")),
                         list(FLAGS))

    def test_glyphs_are_the_six_families(self):
        doc = xml.dom.minidom.parse(str(ASSETS / "glyphs" / "sources.svg"))
        ids = [s.getAttribute("id") for s in doc.getElementsByTagName("symbol")]
        self.assertEqual(sorted(ids), sorted(GLYPHS))
        # Line drawings only: no raster, text or embedded reference.
        raw = (ASSETS / "glyphs" / "sources.svg").read_text(encoding="utf-8")
        self.assertNotRegex(raw, r"<(image|text|use|foreignObject)\b|href=")


class ShadowAuditTests(unittest.TestCase):
    """B1=A lifts stay scoped; the owner also permits timeline node illumination."""

    def test_no_other_preview_stylesheet_or_template_casts_a_shadow(self):
        for path in sorted(PREVIEW.rglob("*")):
            if path.suffix not in (".css", ".html") or path == RELIEF_CSS:
                continue
            text = path.read_text(encoding="utf-8")
            if path == PREVIEW / "timelines.css":
                # Ben's Flowing Chronology exception is decorative node glow,
                # not card elevation. Remove only this exact rule's approved
                # declaration, then audit everything else in the file as usual.
                text = re.sub(
                    r"(?m)^(\s*\.tl-entry::before\s*\{[^{}]*?)"
                    r"box-shadow\s*:\s*0 0 16px color-mix\(in srgb,var\(--focus-band\) 25%,transparent\)"
                    r"(?=\s*[;}])", r"\1", text)
            self.assertNotRegex(text, r"box-shadow\s*:(?!\s*none)",
                                "%s casts a shadow" % path.relative_to(REPO_ROOT))

    def test_timeline_node_exception_does_not_admit_other_shadows(self):
        glow = "0 0 16px color-mix(in srgb,var(--focus-band) 25%,transparent)"
        node = ".tl-entry::before{box-shadow:%s}" % glow
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            root = Path(tmp)
            with mock.patch(__name__ + ".PREVIEW", root):
                path = root / "timelines.css"
                path.write_text(node, encoding="utf-8")
                self.test_no_other_preview_stylesheet_or_template_casts_a_shadow()
                for css in (node + "\n.tl-entry-body{box-shadow:0 2px 4px black}",
                            node.replace("::before", "-body"),
                            node.replace("::before{", "::before,.other{"),
                            node.replace(glow, glow + ",0 2px 4px black")):
                    with self.subTest(css=css), self.assertRaises(AssertionError):
                        path.write_text(css, encoding="utf-8")
                        self.test_no_other_preview_stylesheet_or_template_casts_a_shadow()
                path.unlink()
                for name in ("other.css", "timeline.html"):
                    other = root / name
                    other.write_text(node, encoding="utf-8")
                    with self.subTest(file=name), self.assertRaises(AssertionError):
                        self.test_no_other_preview_stylesheet_or_template_casts_a_shadow()
                    other.unlink()

    def test_relief_css_uses_only_the_three_lifts_on_the_six_surfaces(self):
        css = RELIEF_CSS.read_text(encoding="utf-8")
        tokens = dict(re.findall(r"(--lift-[123]):([^;}]+)", css))
        self.assertEqual(sorted(tokens), ["--lift-1", "--lift-2", "--lift-3"])
        # Pressed controls darken; nothing casts an inner shadow.
        self.assertFalse(any("inset" in v for v in tokens.values()))
        seen = set()
        for selector, body in _css_rules(css):
            for value in re.findall(r"box-shadow\s*:\s*([^;]+)", body):
                value = value.strip()
                self.assertIn(value, LIFTS, selector)
                seen.add(value)
                classes = set(re.findall(r"\.(rl-[a-z]+)", selector))
                self.assertTrue(classes and classes <= set(SURFACES),
                                "shadow on %r" % selector.strip())
        self.assertTrue({"var(--lift-1)", "var(--lift-2)", "var(--lift-3)"} <= seen)

    def test_the_stylesheet_stays_inside_its_budget(self):
        self.assertLessEqual(RELIEF_CSS.stat().st_size, 4096)


class MotionAndModeTests(unittest.TestCase):
    """Motion is opt-in; forced colours and print lose every lift."""

    css = RELIEF_CSS.read_text(encoding="utf-8")

    def test_scroll_motion_is_gated_three_ways(self):
        gate = ("@media(prefers-reduced-motion:no-preference) and (scripting:enabled)"
                "{@supports(animation-timeline:view()){")
        self.assertIn(gate, self.css)
        start = self.css.index(gate)
        for match in re.finditer(r"animation(-name)?\s*:", self.css):
            self.assertGreater(match.start(), start, "ungated animation")
        gated = self.css[start:]
        self.assertIn("html:not(.no-anim)", gated)

    def test_transforms_wait_for_no_motion_preference(self):
        rm = self.css.index("@media(prefers-reduced-motion:no-preference)")
        for match in re.finditer(r"transform\s*:\s*(?!none)", self.css):
            self.assertGreater(match.start(), rm, "transform outside the motion query")

    def test_forced_colours_and_print_drop_lifts(self):
        for query in ("@media(forced-colors:active)", "@media print"):
            block = self.css[self.css.index(query):]
            block = block[:block.index("}}") + 2]
            self.assertIn("box-shadow:none", block, query)
            self.assertIn("::after", block, query)


class MacroTests(unittest.TestCase):
    """Every illustration is decoration beside text that names it."""

    src = (TEMPLATES / "_relief.html").read_text(encoding="utf-8")

    def test_every_svg_and_flag_is_hidden_from_assistive_technology(self):
        svgs = re.findall(r"<svg\b[^>]*>", self.src)
        self.assertGreaterEqual(len(svgs), 4)
        for tag in svgs:
            self.assertIn('aria-hidden="true"', tag)
            self.assertIn('focusable="false"', tag)
        for tag in re.findall(r"<img\b[^>]*>", self.src):
            self.assertIn('alt=""', tag)

    def test_art_is_referenced_not_inlined(self):
        self.assertNotRegex(self.src, r"<path\b|<polygon\b|<rect\b")
        for href in re.findall(r'(?:href|src)="([^"]+)"', self.src):
            self.assertRegex(href, r"assets/(geo|flags|glyphs)/")


class ProductionIsolationTests(unittest.TestCase):
    """No production template reaches the relief primitives (2026-11-14).

    The home page drew emblems and the Singapore Strait, and four page families
    linked relief.css, until the parallel-text identity retired drawn scenery.
    What is left is two class names kept as unstyled hooks: `rl-finder` on the
    Records page's search form and `rl-brief` on the Briefs catalogue's rows.
    Everything else matching the pattern belongs to the gallery alone.
    """

    PATTERN = re.compile(r"relief\.css|_relief\.html|assets/(geo|flags|glyphs)/[\w.-]*|\brl-[a-z]+")
    ALLOWED = {"archive.html": {"rl-finder"}, "analysis.html": {"rl-brief"}}

    def test_no_production_template_reaches_the_relief_primitives(self):
        for path in sorted(TEMPLATES.glob("*.html")):
            if path.name in ("gallery-relief.html", "_relief.html"):
                continue
            found = {m.group(0) for m in self.PATTERN.finditer(path.read_text(encoding="utf-8"))}
            self.assertEqual(found - self.ALLOWED.get(path.name, set()), set(), path.name)
        home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        self.assertIsNone(self.PATTERN.search(home))
        self.assertEqual(re.findall(r"relief\.(\w+)\(", home), [])

    def test_stylesheets_and_base_templates_stay_out(self):
        for path in sorted(PREVIEW.glob("*.css")):
            if path != RELIEF_CSS:
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"relief\.css|--lift-")
        for path in (REPO_ROOT / "site/templates/base.html",
                     REPO_ROOT / "site/templates/pla-watch-base.html",
                     TEMPLATES / "base.html"):
            if path.exists():
                self.assertNotIn("relief.css", path.read_text(encoding="utf-8"))


def _production_build(out, **options):
    # This helper exercises synthetic Brief/Timeline collections.
    options.setdefault("dossiers_dir", out.parent / "no-dossiers")
    sys.path.insert(0, str(PREVIEW))
    import generate_preview as gp
    gp.build(out, gp.PUBLIC_TITLE, TRACKED_DB,
             snapshot=gp.snapshot_from_corpus(TRACKED_DB), legacy_routes=True, **options)
    return gp


class ProductionAssetTests(unittest.TestCase):
    """A production build admits named relief and public Desks flag assets only.

    Built with an approved copy of the timeline pilot and the existing
    test-only China/Singapore Brief fixture. The positive Strait branch must
    not depend on which real Brief happens to lead the published collection.
    """

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        from tests.test_timelines import approve_fixture, pilot_without_mindef_evidence
        from tests.brief_fixtures import FIXTURE_SLUG, stage
        # The real pilot cites withheld MINDEF records and is held by the rights
        # boundary (tests.test_timelines.PilotIsHeldByRightsBoundary). This
        # layout test runs under an explicit synthetic rights authority on a
        # fixture derived from the pilot minus those citations.
        rights = mock.patch("core.mindef_public_boundary.editorial_hold", return_value=False)
        rights.start()
        cls.addClassCleanup(rights.stop)
        cls.tmp = Path(tempfile.mkdtemp(prefix="relief-production-"))
        briefs = stage(cls.tmp)
        sources = cls.tmp / "timelines"
        sources.mkdir()
        sc = pilot_without_mindef_evidence()
        sc["editor_name"] = "Fixture editor"
        sc["related_briefs"] = [FIXTURE_SLUG]
        approve_fixture(sc)
        (sources / (sc["slug"] + ".json")).write_text(json.dumps(sc), encoding="utf-8")
        cls.out = cls.tmp / "build"
        cls.gp = _production_build(cls.out, timelines_dir=sources,
                                  briefs_dir=briefs, allow_synthetic_briefs=True)
        cls.index = (cls.out / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_approved_relief_and_country_flag_assets_are_byte_identical(self):
        self.assertEqual(self.gp.RELIEF_PRODUCTION_ASSETS,
                         ("assets/geo/emblems.svg", "assets/geo/strait.svg"))
        self.assertEqual((self.out / "relief.css").read_bytes(), RELIEF_CSS.read_bytes())
        for route in self.gp.RELIEF_PRODUCTION_ASSETS:
            self.assertEqual((self.out / route).read_bytes(),
                             (REPO_ROOT / "site" / route).read_bytes(), route)
        # The Briefs catalogue adds the region art its Editorial plates draw.
        self.assertEqual(self.gp.CATALOGUE_STATIC_ASSETS, ("assets/geo/region.svg",))
        self.assertEqual((self.out / "assets/geo/region.svg").read_bytes(),
                         (REPO_ROOT / "site/assets/geo/region.svg").read_bytes())
        self.assertEqual(sorted(p.name for p in (self.out / "assets/geo").iterdir()),
                         ["emblems.svg", "region.svg", "strait.svg"])
        # A public Desk flag is an explicitly referenced asset and the MIT
        # notice travels with it; gallery-only glyphs must still stay private.
        expected = {"%s.svg" % iso for iso in FLAGS} | {"LICENSE"}
        self.assertEqual({p.name for p in (self.out / "assets/flags").iterdir()}, expected)
        self.assertEqual(set(self.gp.DESKS_PUBLIC_FLAG_ASSETS),
                         {"assets/flags/" + name for name in expected})
        for route in self.gp.DESKS_PUBLIC_FLAG_ASSETS:
            self.assertEqual((self.out / route).read_bytes(),
                             (REPO_ROOT / "site" / route).read_bytes(), route)
        for absent in ("assets/glyphs", "gallery-relief.html"):
            self.assertFalse((self.out / absent).exists(), absent)
        self.assertFalse(any(self.out.glob("assets/**/*.receipt.json")))

    def test_the_homepage_draws_no_relief_art(self):
        # The pinned fixture Brief lists Singapore: the case that used to draw
        # the strait and both desks' emblems beside it.
        self.assertEqual(re.findall(r'<use href="assets/[^"]+"', self.index), [])
        self.assertNotRegex(self.index, r'\brl-[a-z]+')
        for retired in ("emblems.svg", "strait.svg", "Singapore Strait",
                        "not a navigation or boundary chart"):
            self.assertNotIn(retired, self.index)

    def test_no_built_page_links_the_relief_stylesheet(self):
        for page in self.out.rglob("*.html"):
            self.assertNotIn("relief.css", page.read_text(encoding="utf-8"),
                             page.relative_to(self.out))

    def test_relief_art_is_decorative(self):
        for tag in re.findall(r"<svg\b[^>]*>", self.index):
            if "rl-" in tag:
                self.assertIn('aria-hidden="true"', tag)

    def test_timeline_branch_survives_without_the_strait(self):
        from bs4 import BeautifulSoup
        more = BeautifulSoup(self.index, "html.parser").select_one(
            "#analysis .home-briefs-more article")
        self.assertEqual(more.select_one(".home-label").get_text(strip=True),
                         "Evidence timeline")
        self.assertEqual(more.h3.a["href"], "timeline/maritime-cooperation-2026.html")
        self.assertTrue(more.h3.a.get_text(strip=True))
        self.assertIn("Read this Brief", self.index)


class GalleryBuildTests(unittest.TestCase):
    """The relief gallery's every reference resolves in the tree it is built into."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")
        sys.path.insert(0, str(PREVIEW))
        import generate_preview as gp
        cls.tmp = Path(tempfile.mkdtemp(prefix="relief-gallery-"))
        cls.out = cls.tmp / "build"
        gp.build(cls.out, gp.PUBLIC_TITLE, TRACKED_DB,
                 snapshot=gp.snapshot_from_corpus(TRACKED_DB),
                 legacy_routes=True, gallery=True)
        cls.html = (cls.out / "gallery-relief.html").read_text(encoding="utf-8")
        cls.gallery = (cls.out / "gallery.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_relief_stylesheet_is_linked_and_copied(self):
        self.assertIn('href="relief.css"', self.html)
        self.assertEqual((self.out / "relief.css").read_bytes(), RELIEF_CSS.read_bytes())

    def test_component_gallery_only_points_to_it(self):
        # Kept apart so the component gallery stays inside its delivery budget.
        self.assertNotIn("relief.css", self.gallery)
        self.assertNotRegex(self.gallery, r"assets/(geo|flags|glyphs)/|\brl-")
        self.assertIn('href="gallery-relief.html"', self.gallery)

    def test_every_use_and_flag_resolves(self):
        ids = {}
        uses = re.findall(r'<use href="(assets/[^"#]+)#([^"]+)"', self.html)
        self.assertTrue(uses)
        for path, symbol in uses:
            if path not in ids:
                doc = xml.dom.minidom.parse(str(self.out / path))
                ids[path] = {s.getAttribute("id") for s in doc.getElementsByTagName("symbol")}
            self.assertIn(symbol, ids[path], "%s#%s" % (path, symbol))
        flags = re.findall(r'<img class="rl-flag" src="([^"]+)"', self.html)
        self.assertTrue(flags)
        for src in flags:
            self.assertTrue((self.out / src).is_file(), src)
        self.assertFalse(any(self.out.glob("assets/*/*.receipt.json")))


if __name__ == "__main__":
    unittest.main()
