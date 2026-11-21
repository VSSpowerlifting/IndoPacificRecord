"""Offline synthetic contract tests: authenticated MOD PDF -> shared license gate.

No real publisher text is supplied to tests, actions logs or public fixtures.
"""
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core.japan_mod_original_replay import (
    JapanOriginalHold, qualify_private_pdf_text,
)
from core.standing_source_rights import StandingLicenseHold


COMMIT = "a" * 40
IDENTITY = "jp_mod_news_ja:/j/press/news/2026/10/23a.pdf"
URL = "https://www.mod.go.jp/j/press/news/2026/10/23a.pdf"
TEXT = "SYNTHETIC FICTIONAL test source body. No original ministry words."
TEXT_SHA = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
CAPTURE_SHA = "b" * 64
NOW = "2026-11-06T23:00:00Z"


def authentic_fake_receipt():
    return {
        "status": "PDF_TEXT_LAYER_REPLAYED",
        "source_family": "jp_mod_news_ja",
        "source_identity": IDENTITY,
        "official_url": URL,
        "source_git_commit": COMMIT,
        "pdf_capture_sha256": CAPTURE_SHA,
        "text_sha256": TEXT_SHA,
        "rss_pubdate": "2026-10-23",
        "page_count": 5,
        "pages_with_text": 5,
        "pages_failed": 0,
        "publisher_license_qualified": False,
        "external_model_input_authorized": False,
        "public_original_authorized": False,
        "machine_explanation_authorized": False,
        "publication_authorized": False,
    }


def synthetic_policy(policy):
    return {
        "policy_id": policy["policy_id"],
        "official_policy_url": policy["policy_url"],
        "observed_at_utc": NOW,
        "publisher_policy_sha256": "c" * 64,
        "text_reproduction_permitted": True,
        "derivatives_permitted": True,
        "third_party_exclusions_preserved": True,
        "policy_changed_or_withdrawn": False,
    }


def synthetic_clean_item(source, policy):
    return {
        "first_party_official_text": True,
        "third_party_text_present": False,
        "separate_terms_apply": False,
        "privacy_or_secrecy_exception": False,
        "released_artifact_embeds_media": False,
        "entire_source_text_version_sha256": TEXT_SHA,
    }


class JapanOriginalTextRightsBridgeTests(unittest.TestCase):
    def setUp(self):
        self.receipt = authentic_fake_receipt()

    def qualify(self, *, policy=synthetic_policy, item=synthetic_clean_item,
                identity=IDENTITY, text=TEXT):
        with patch("core.japan_mod_original_replay.replay_private_pdf",
                   return_value=(self.receipt, text)) as verified:
            result = qualify_private_pdf_text(
                Path("/isolated/source-mirror"), COMMIT, identity,
                Path("/isolated/private/original.pdf"),
                fetch_run=lambda *_: None, now_utc=NOW,
                policy_replay=policy, exception_replay=item)
        verified.assert_called_once()
        return result

    def test_missing_independent_policy_or_exception_evidence_holds(self):
        for policy, item in ((None, synthetic_clean_item),
                             (synthetic_policy, None),
                             (None, None)):
            with self.subTest(policy=policy is not None,
                              item=item is not None):
                with self.assertRaisesRegex(
                        StandingLicenseHold,
                        "trusted_source_policy_and_exception_verifiers_required"):
                    self.qualify(policy=policy, item=item)

    def test_eligible_synthetic_text_creates_safe_conditional_receipt_only(self):
        result = self.qualify()
        self.assertEqual(result["status"],
                         "STANDING_TEXT_LICENSE_CONDITIONALLY_QUALIFIED")
        self.assertEqual(result["text_sha256"], TEXT_SHA)
        self.assertEqual(result["pdf_capture_sha256"], CAPTURE_SHA)
        self.assertEqual(result["standing_qualification"]["scope"],
                         "original_text")
        self.assertTrue(result["standing_qualification"][
            "original_text_matches_authenticated_capture"])
        for field in ("external_model_input_authorized",
                      "automated_text_processing_authorized",
                      "publication_authorized", "source_body_returned"):
            self.assertIs(result[field], False)
        public_safe = json.dumps(result)
        self.assertNotIn(TEXT, public_safe)
        self.assertNotIn("/isolated/private", public_safe)

    def test_changed_text_after_authentic_replay_holds(self):
        with self.assertRaisesRegex(
                JapanOriginalHold, "japan_qualifier_text_hash_disagreement"):
            self.qualify(text=TEXT + " adulterated")

    def test_incomplete_capture_or_changed_identity_holds(self):
        self.receipt["pages_with_text"] = 4
        with self.assertRaisesRegex(
                JapanOriginalHold,
                "japan_qualifier_requires_authenticated_complete_original"):
            self.qualify()
        self.receipt["pages_with_text"] = 5
        with self.assertRaisesRegex(
                JapanOriginalHold,
                "japan_qualifier_requires_authenticated_complete_original"):
            self.qualify(identity="jp_mod_news_ja:/j/press/news/2026/10/22a.pdf")

    def test_no_permission_boolean_can_be_inherited_from_custody(self):
        self.receipt["external_model_input_authorized"] = True
        with self.assertRaisesRegex(
                JapanOriginalHold, "japan_qualifier_must_not_inherit"):
            self.qualify()

    def test_third_party_text_or_media_must_hold(self):
        def media(source, policy):
            item = synthetic_clean_item(source, policy)
            item["released_artifact_embeds_media"] = True
            return item
        def third_party(source, policy):
            item = synthetic_clean_item(source, policy)
            item["third_party_text_present"] = True
            return item
        for checker in (media, third_party):
            with self.subTest(checker=checker.__name__):
                with self.assertRaisesRegex(
                        StandingLicenseHold,
                        "source_item_excluded_by_rights_or_scope"):
                    self.qualify(item=checker)

    def test_changed_or_stale_publisher_policy_holds(self):
        def changed(policy):
            data = synthetic_policy(policy)
            data["policy_changed_or_withdrawn"] = True
            return data
        def stale(policy):
            data = synthetic_policy(policy)
            data["observed_at_utc"] = "2026-10-15T23:00:00Z"
            return data
        for checker in (changed, stale):
            with self.subTest(checker=checker.__name__):
                with self.assertRaisesRegex(
                        StandingLicenseHold,
                        "standing_license_missing_changed_or_stale"):
                    self.qualify(policy=checker)

    def test_unverified_item_text_version_holds(self):
        def mismatch(source, policy):
            data = synthetic_clean_item(source, policy)
            data["entire_source_text_version_sha256"] = "d" * 64
            return data
        with self.assertRaisesRegex(
                StandingLicenseHold,
                "source_item_excluded_by_rights_or_scope"):
            self.qualify(item=mismatch)


if __name__ == "__main__":
    unittest.main()
