"""Offline English synthetic evidence; no official originals or model evaluation."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from processing import daily_intake as daily
from tests.test_philippines_shared_daily import record, reading


def candidate(body, sentences, family="ph_afp_articles"):
    item = record()
    item.update(body=body, title="Synthetic explanation fixture", source_family=family)
    result = reading()
    result.update(summary_english=" ".join(sentences),
                  facts=[dict(sentence=s, evidence=body) for s in sentences],
                  prompt_version="ph-relevance-v1+ph-analysis-v13")
    return item, result


class PhilippinesExplanationQuality(unittest.TestCase):
    def test_longer_sentences_retain_actor_activity_and_scope(self):
        body = ("The commander reviewed the exercise plan for 23 October. "
                "The planned activity involves 125 specialists working on maritime search.")
        sentences = (
            "According to AFP, the commander examined plans for an exercise scheduled for 23 October.",
            "AFP describes maritime search as the focus of the planned exercise involving 125 specialists.",
        )
        self.assertTrue(all(len(s.split()) > 11 for s in sentences))
        self.assertTrue(daily.quality_check(*candidate(body, sentences)))

    def test_nsc_host_can_attribute_to_actual_office_without_fixed_opening(self):
        body = ("The National Security Adviser requested a review of maritime safety procedures. "
                "The statement proposed talks on incident reporting.")
        sentences = (
            "According to the NSC website, the National Security Adviser called for maritime safety procedures to be reviewed.",
            "The NSC website describes proposed discussions about reporting incidents.",
        )
        self.assertTrue(daily.quality_check(*candidate(body, sentences, "ph_nsc_official_statements")))

    def test_longer_output_still_holds_copied_twelve_word_sequence(self):
        body = ("The commander explained that personnel will conduct maritime search exercises "
                "along the coast during the planned activity in October.")
        sentences = (
            "AFP reports that personnel will conduct maritime search exercises along the coast during the planned activity.",
            "According to AFP, the commander described exercises planned for October.",
        )
        with self.assertRaisesRegex(daily.IntakeHold, "daily_original_excerpt_prohibited"):
            daily.quality_check(*candidate(body, sentences))

    def test_longer_output_still_holds_unsupported_completion(self):
        body = ("The commander said that equipment will be delivered for the planned exercise. "
                "The exercise will focus on maritime search.")
        sentences = (
            "AFP reports that equipment was delivered to support the exercise focused on maritime search.",
            "According to AFP, the commander described a planned exercise involving maritime search.",
        )
        with self.assertRaisesRegex(daily.IntakeHold, "daily_modality_or_contradiction_hold"):
            daily.quality_check(*candidate(body, sentences))


class VietnamInstitutionalAttribution(unittest.TestCase):
    def test_existing_reviewer_covers_roles_and_preserves_accepted_case(self):
        # Scripted verdicts test routing and preservation, not semantic ability.
        from core import vietnam_corpus_bridge as bridge, vietnam_daily_qa as qa
        from core.collection.vietnam_sources import VPCP
        from processing import vpcp_document as document

        page = ("Synthetic English evidence: the Government Office transmitted the Prime Minister's "
                "instructions. The Prime Minister asked the test ministry to review supplies. "
                "Provincial chairs were instructed to report violations.")
        facts = [
            dict(sentence="The Prime Minister asked the test ministry to review supplies.",
                 page=1, evidence=page, status="instructed"),
            dict(sentence="Provincial chairs were instructed to report violations.",
                 page=1, evidence=page, status="instructed"),
        ]
        cases = (
            ("The Government Office conveyed the Prime Minister's instructions. "
             "The test ministry must review supplies; provincial chairs must report violations.", True),
            ("The Government Office asked for a supply review by the test ministry. "
             "Provincial chairs must report violations.", False),
            ("The Government Office conveyed the Prime Minister's instructions. "
             "Provincial chairs must review supplies and report violations.", False),
        )
        for summary, accepted in cases:
            with self.subTest(summary=summary):
                result = dict(summary_english=summary, title_english="Synthetic supply review instruction",
                              is_significant=False, categories=["policy_document"], document_facts=facts)
                # All three pass mechanical evidence checks: the existing independent
                # review is essential for deciding who instructed whom to do what.
                self.assertEqual(document.output_failures(
                    dict(pages=[(1, page)], text_original=page), result), [])
                self.assertNotIn("E_UNATTRIBUTED", qa.output_failures(
                    dict(source_family=VPCP), "Synthetic", page, result,
                    translation_required=False, permissions={"public_ipr_analysis": True},
                    projection={"title_english": result["title_english"]}))
                analyzer = SimpleNamespace(_call=Mock(return_value="scripted reply"),
                    _parse_task_json=Mock(return_value=dict(ok=accepted, reason="Synthetic verdict")))
                verdict = bridge.model_second_pass(analyzer, VPCP)({}, "Synthetic", page, result)
                self.assertIs(verdict["ok"], accepted)
                prompt = analyzer._call.call_args.args[0][0]["content"]
                self.assertIn("Prime Minister's instructions", prompt)
                self.assertIn("ministry's responsibility to provincial", prompt)
                self.assertIn(summary, prompt)
                for fact in facts:
                    self.assertIn(fact["sentence"], prompt)
                analyzer._call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
