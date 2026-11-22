"""Briefs section contrast stays measured now that the navy band is retired.

The section is paper since 2026-11-14; the same glyph-pixel probe measures the
runs that carry its heading, labels and bylines.
"""
from tests import test_homepage_veil_contract as probe


class TestTheBandInTheBrowser(probe.TestTextOverTheVeilIsMeasuredAtItsGlyphs):
    RUNS = {'.home-briefs h2': 3.0, '.home-briefs .meta': 4.5,
            '.home-briefs .home-label': 4.5,
            '.home-briefs .evidence--analysis': 4.5,
            '.home-briefs .home-feature-dek': 4.5}
