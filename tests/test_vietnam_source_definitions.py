"""Vietnam Daily reads family behaviour from its source definitions. Offline only."""
import unittest

from core import vietnam_corpus_bridge as bridge
from core import vietnam_document_custody as custody
from core import vietnam_official_link_admission as vn
from core import vietnam_source_use as source_use
from core.collection.vietnam_sources import PROCESSING_SOURCES, SOURCES
from processing.screening import private_document_profile, profile_for_source
from scripts import run_vietnam_daily_bridge as runner

MPS, VPCP = source_use.MPS, source_use.VPCP


class VietnamSourceDefinitions(unittest.TestCase):
    def test_declared_behaviour_matches_the_families_that_had_it(self):
        self.assertEqual({f for f, s in PROCESSING_SOURCES.items() if s.private_document},
                         {VPCP})
        self.assertEqual({f for f, s in PROCESSING_SOURCES.items() if s.analysis_headline},
                         {MPS, VPCP})
        # The ministry HTML collector never enrolls a private-document family.
        self.assertFalse(any(s.private_document for s in SOURCES.values()))

    def test_private_document_ref_is_the_custody_ref(self):
        self.assertEqual(vn.private_ref(VPCP), custody.REF)
        self.assertEqual(vn.private_ref(VPCP), "archive/vietnam-vpcp")

    def test_profiles_never_fall_back_to_another_desk(self):
        self.assertEqual(bridge._profile(VPCP).analysis_prompt_version,
                         private_document_profile().analysis_prompt_version)
        for family in SOURCES:
            self.assertIs(bridge._profile(family), profile_for_source(family))
            self.assertEqual(bridge._profile(family).desk_id, "vietnam")
        with self.assertRaises(KeyError):
            bridge._profile("unknown-source")

    def test_analysis_headline_drops_only_the_title_dependency(self):
        for family in PROCESSING_SOURCES:
            deps = source_use.standing(family)._dependencies("public_ipr_analysis")
            if PROCESSING_SOURCES[family].analysis_headline:
                self.assertEqual(deps, ("external_model_transmission",))
            else:
                self.assertEqual(deps, source_use.REQUIRES.get("public_ipr_analysis", ()))

    def test_only_a_private_document_failure_is_isolated(self):
        self.assertTrue(runner._isolated(VPCP))
        for family in SOURCES:
            self.assertFalse(runner._isolated(family))
        self.assertFalse(runner._isolated("unknown-source"))


if __name__ == "__main__":
    unittest.main()
