"""The shared Daily lane reads each family from one definition. Offline only."""
import unittest
from unittest.mock import patch

from core import daily_sources
from core.daily_sources import SOURCES, source_for
from processing import daily_intake as d
from processing.screening import (
    INDONESIA_PROFILE, PHILIPPINES_PROFILE, profile_for_desk, profile_for_source,
)
from tests.test_philippines_shared_daily import record as ph_record

AFP, NSC, KEMHAN = "ph_afp_articles", "ph_nsc_official_statements", "id_kemhan_news"


class SourceDefinitions(unittest.TestCase):
    def test_registry_matches_policy_and_private_signer_exports(self):
        self.assertEqual(list(SOURCES), [AFP, NSC, KEMHAN])
        self.assertEqual(set(d.load_policy()["sources"]), set(SOURCES))
        # The private signer reads these module-level names from this module.
        self.assertEqual(d.REFS, {AFP: "archive/ph-afp", NSC: "archive/ph-nsc",
                                  KEMHAN: "archive/indonesia-kemhan"})
        self.assertEqual([s.key_env for s in SOURCES.values()],
                         ["DAILY_PH_AFP_ARTICLES_KEY", "DAILY_PH_NSC_OFFICIAL_STATEMENTS_KEY",
                          "DAILY_ID_KEMHAN_NEWS_KEY"])
        self.assertEqual(d.PUBLIC_FIELDS[:3],
                         ("source_family", "source_identity", "metadata_version_sha256"))

    def test_every_adapter_reference_resolves(self):
        for s in SOURCES.values():
            for ref in (s.links, s.quality, s.release_gate, s.known_hold, s.output_check):
                if ref:
                    self.assertTrue(callable(daily_sources._call(ref)), (s.family, ref))

    def test_profiles_are_the_desks_own_and_current_prompts_stay_accepted(self):
        self.assertIs(profile_for_source(AFP), PHILIPPINES_PROFILE)
        self.assertIs(profile_for_source(NSC), PHILIPPINES_PROFILE)
        self.assertIs(profile_for_source(KEMHAN), INDONESIA_PROFILE)
        for s in SOURCES.values():
            profile = profile_for_desk(s.desk_id)
            self.assertIn(profile.prompt_version + "+" + profile.analysis_prompt_version,
                          s.prompt_versions)
            self.assertEqual(d.allowed_prompt_versions(s.family), s.prompt_versions)
        # Historical accepted outputs must stay valid; Indonesia is not widened.
        self.assertEqual(len(SOURCES[AFP].prompt_versions), 4)
        self.assertEqual(SOURCES[KEMHAN].prompt_versions, ("id-relevance-v1+id-analysis-v4",))

    def test_unknown_source_fails_closed_everywhere(self):
        self.assertIsNone(source_for("unknown-source"))
        self.assertEqual(profile_for_source("unknown-source").desk_id, "unsupported")
        with self.assertRaises(d.IntakeHold):
            d.allowed_prompt_versions("unknown-source")
        with self.assertRaises(d.IntakeHold):
            d.quality_check(dict(ph_record(), source_family="unknown-source"), {})
        with self.assertRaises(d.IntakeHold):
            d.process([], {}, family="unknown-source", policy=d.load_policy())
        with self.assertRaises(d.IntakeHold):
            d.verified_source("/nonexistent", "0" * 40, "unknown-source")

    def test_first_party_binding_comes_from_the_link_family_table(self):
        afp = dict(ph_record(), body="Plain body.")
        self.assertIsNone(SOURCES[AFP].rights_hold(afp))
        for change in (dict(official_republisher="other"), dict(official_issuer=None),
                       dict(official_publisher="other")):
            self.assertEqual(SOURCES[AFP].rights_hold({**afp, **change}),
                             "source_rights_not_first_party")
        kemhan = dict(afp, source_family=KEMHAN, official_publisher="id_kemhan",
                      official_issuer=None, official_republisher=None)
        self.assertIsNone(SOURCES[KEMHAN].rights_hold(kemhan))
        self.assertEqual(SOURCES[KEMHAN].rights_hold({**kemhan, "body": "Isi.\nSumber: lain"}),
                         "source_rights_not_first_party")
        self.assertIsNone(SOURCES[NSC].rights_hold({"body": "x"}))  # NSC has no link family

    def test_release_gate_follows_the_current_nsc_policy(self):
        self.assertIsNone(SOURCES[AFP].release_hold())
        for resolved, expected in ((True, None), (False, "nsc_category_anomaly")):
            with patch("core.ph_nsc_official_link_admission.load_policy",
                       return_value={"category_anomaly_resolved": resolved}):
                self.assertEqual(SOURCES[NSC].release_hold(), expected)


if __name__ == "__main__":
    unittest.main()
