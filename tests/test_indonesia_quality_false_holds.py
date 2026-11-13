"""Kemhan QA: faithful renderings pass, real substitutions still hold.

Every passage, name, office and institution here is synthetic. Nothing is
publisher text or a real model response.
"""
import unittest

from processing import daily_intake as d
from tests.test_indonesia_shared_daily import record, reading

FORM, NAME = 'daily_institution_form_not_local', 'daily_name_or_office_unsupported'
TRANSLATION = 'daily_private_translation_name_unsupported'
STAGE, MODALITY = 'daily_completed_action_unsupported', 'daily_modality_or_contradiction_hold'
CONCEPT = 'daily_cross_passage_claim_unsupported'


def case(passage, sentence, translation, other=None):
    r, reply = record(), reading()
    r['body'] = passage + '\n\n' + (other + '\n\n' if other else '') + reply['facts'][1]['evidence']
    reply['facts'][0] = dict(evidence=passage, sentence='Kemhan reports that ' + sentence,
                             evidence_translation=translation)
    reply['summary_english'] = ' '.join(f['sentence'] for f in reply['facts'])
    return r, reply


class LeadingFormOfALocalEnglishName(unittest.TestCase):
    PASSAGE = ('Delegasi menghadiri Resepsi Pasukan Contoh (Contoh Defense Forces Day Reception) '
               'dan membahas rencana latihan bersama.')

    def run_form(self, form, passage=None):
        r, reply = case(passage or self.PASSAGE,
                        'a delegation attended an event for the ' + form + ' and discusses joint exercise plans.',
                        'The delegation attended the ' + form + ' and discusses plans for a joint exercise.')
        return d.quality_check(r, reply)

    def test_words_after_the_head_noun_may_be_dropped(self):
        for form in ('Contoh Defense Forces Day Reception', 'Contoh Defense Forces Day',
                     'Contoh Defense Forces'):
            with self.subTest(form=form):
                self.assertEqual(len(self.run_form(form)), 64)

    def test_a_qualifier_or_the_head_noun_is_never_dropped(self):
        for form in ('Defense Forces', 'Contoh Forces', 'Negara Defense Forces',
                     'Contoh Defense Force'):
            with self.subTest(form=form), self.assertRaises(d.IntakeHold) as held:
                self.run_form(form)
            self.assertIn(str(held.exception), (FORM, NAME))

    def test_head_first_names_and_of_phrases_yield_no_shorter_form(self):
        for local, shorter in (('Ministry of Contoh Negara', 'Ministry of Contoh'),
                               ('Contoh Council of Negara Elders', 'Contoh Council'),
                               ('Kementerian Contoh Negara', 'Kementerian Contoh')):
            passage = 'Delegasi menghadiri acara ' + local + ' dan membahas rencana latihan bersama.'
            with self.subTest(local=local), self.assertRaisesRegex(d.IntakeHold, FORM):
                self.run_form(shorter, passage)
            self.assertEqual(len(self.run_form(local, passage)), 64)


class PortfolioAppositiveHolder(unittest.TestCase):
    TITLE = 'Wakil Menteri Contoh Negara (Wamencon RN) Bidang '
    LIST = TITLE + 'Logistik, Industri Contoh, dan Teknologi, Marsekal Budi Contoh, membahas rencana latihan bersama.'
    SINGLE = TITLE + 'Logistik, Marsekal Budi Contoh, membahas rencana latihan bersama.'

    def run_form(self, passage, form):
        r, reply = case(passage, form + ' discusses joint exercise plans.',
                        form + ' discusses plans for a joint exercise.')
        return d.quality_check(r, reply)

    def test_holder_after_the_portfolio_is_defined_by_the_passage(self):
        for passage in (self.LIST, self.SINGLE):
            with self.subTest(passage=passage):
                self.assertEqual(len(self.run_form(passage, 'Wamencon RN Marsekal Budi Contoh')), 64)
                self.assertEqual(len(self.run_form(passage, 'Wamencon RN')), 64)

    def test_portfolio_items_and_other_people_are_not_the_holder(self):
        cases = (
            (self.LIST, 'Wamencon RN Industri Contoh'),
            (self.LIST, 'Wamencon RN Budi Contoh'),
            # A second comma-delimited person is not the holder.
            (self.TITLE + 'Logistik, Marsekal Budi Contoh, Kolonel Adi Contoh, membahas rencana latihan.',
             'Wamencon RN Kolonel Adi Contoh'),
            # A verb between office and person is a meeting, not an apposition.
            ('Wakil Menteri Contoh Negara (Wamencon RN) menerima Marsekal Budi Contoh, membahas rencana latihan.',
             'Wamencon RN Marsekal Budi Contoh'),
            # No portfolio marker and no direct adjacency.
            ('Wakil Menteri Contoh Negara (Wamencon RN) bersama delegasi, Marsekal Budi Contoh, membahas rencana latihan.',
             'Wamencon RN Marsekal Budi Contoh'),
            # An open list (no closing "dan") does not say where the portfolio ends.
            (self.TITLE + 'Logistik, Industri Contoh, Teknologi, Marsekal Budi Contoh, membahas rencana latihan.',
             'Wamencon RN Marsekal Budi Contoh'),
        )
        for passage, form in cases:
            with self.subTest(passage=passage, form=form), self.assertRaisesRegex(d.IntakeHold, FORM):
                self.run_form(passage, form)

    def test_definition_in_another_passage_stays_nonlocal(self):
        r, reply = case('Wamencon RN membahas rencana latihan bersama Marsekal Budi Contoh.',
                        'Wamencon RN Marsekal Budi Contoh discusses joint exercise plans.',
                        'Wamencon RN discusses plans for a joint exercise.', other=self.LIST)
        with self.assertRaisesRegex(d.IntakeHold, FORM):
            d.quality_check(r, reply)


class TranslatedCountryNames(unittest.TestCase):
    def run_names(self, passage, sentence, translation, other=None):
        r, reply = case(passage, sentence, translation, other)
        return d.quality_check(r, reply)

    def test_english_name_of_a_local_country_passes_in_both_fields(self):
        other = 'Acara Japan Day membahas rencana latihan bersama lain.'
        for passage, public, private in (
                ('Delegasi Jepang membahas rencana latihan bersama.', "a Japanese", 'Japan'),
                ('Delegasi Jepang membahas rencana latihan bersama.', "Japan's", 'Japan'),
                ('Delegasi Filipina membahas rencana latihan bersama.', 'a Philippine', 'the Philippines'),
                ('Delegasi Amerika Serikat membahas rencana latihan bersama.', 'a United States', 'the United States'),
                ('Delegasi Korea Selatan membahas rencana latihan bersama.', 'a South Korean', 'South Korea')):
            with self.subTest(passage=passage, public=public):
                # "other" puts the English name elsewhere in the article, which
                # is what made the private translation hold.
                self.assertEqual(len(self.run_names(
                    passage, public + ' delegation discusses joint exercise plans.',
                    'The delegation of ' + private + ' discusses plans for a joint exercise.', other)), 64)

    def test_a_country_the_passage_does_not_name_still_holds(self):
        passage = 'Delegasi Filipina membahas rencana latihan bersama.'
        with self.assertRaisesRegex(d.IntakeHold, NAME):
            self.run_names(passage, 'a Japanese delegation discusses joint exercise plans.',
                           'The delegation discusses plans for a joint exercise.')
        with self.assertRaisesRegex(d.IntakeHold, TRANSLATION):
            self.run_names(passage, 'a delegation discusses joint exercise plans.',
                           'The delegation of Japan discusses plans for a joint exercise.',
                           'Delegasi Japan Day membahas rencana latihan bersama lain.')
        # The country elsewhere in the article is not evidence for this passage.
        with self.assertRaisesRegex(d.IntakeHold, NAME):
            self.run_names('Delegasi membahas rencana latihan bersama.',
                           'a Japanese delegation discusses joint exercise plans.',
                           'The delegation discusses plans for a joint exercise.',
                           'Delegasi Jepang membahas rencana latihan bersama lain.')

    def test_a_country_name_does_not_license_an_institution_alias(self):
        passage = 'Kementerian Pertahanan Jepang membahas rencana latihan bersama.'
        for alias in ('Japan Ministry of Defense', 'Japanese Defense Ministry'):
            with self.subTest(alias=alias), self.assertRaises(d.IntakeHold) as held:
                self.run_names(passage, 'the ' + alias + ' discusses joint exercise plans.',
                               'Kementerian Pertahanan Jepang discusses plans for a joint exercise.')
            self.assertIn(str(held.exception), (FORM, NAME))
        self.assertEqual(len(self.run_names(
            passage, 'in Japan, Kementerian Pertahanan Jepang discusses joint exercise plans.',
            'Kementerian Pertahanan Jepang discusses plans for a joint exercise.')), 64)


class OrganisedEventVerb(unittest.TestCase):
    """"diselenggarakan" states a held/conducted event, as "digelar" does."""
    HELD = 'Resepsi Contoh diselenggarakan di Hotel Contoh.'

    def run_verb(self, passage, sentence, translation, other=None):
        r, reply = case(passage, sentence, translation, other)
        return d.quality_check(r, reply)

    def test_held_and_conducted_render_the_organised_event_verb(self):
        for passage, sentence, translation in (
                (self.HELD, 'Resepsi Contoh was held at Hotel Contoh.',
                 'Resepsi Contoh was held at Hotel Contoh.'),
                ('Latihan Contoh merupakan puncak rangkaian latihan yang diselenggarakan secara bertahap.',
                 'Latihan Contoh was the culmination of a series of exercises conducted in phases.',
                 'Latihan Contoh is the culmination of a series of exercises conducted in phases.'),
                ('Kemhan menyelenggarakan Latihan Contoh di Lapangan Contoh.',
                 'Kemhan conducted Latihan Contoh at Lapangan Contoh.',
                 'Kemhan conducted Latihan Contoh at Lapangan Contoh.')):
            with self.subTest(passage=passage):
                self.assertEqual(len(self.run_verb(passage, sentence, translation)), 64)

    def test_a_planned_event_is_still_not_a_held_one(self):
        with self.assertRaises(d.IntakeHold) as held:
            self.run_verb('Resepsi Contoh akan diselenggarakan di Hotel Contoh.',
                          'Resepsi Contoh was held at Hotel Contoh.',
                          'Resepsi Contoh was held at Hotel Contoh.')
        self.assertIn(str(held.exception), (STAGE, MODALITY))

    def test_held_without_a_local_event_verb_still_holds(self):
        cases = (
            ('Resepsi Contoh di Hotel Contoh dihadiri delegasi.', None),
            # The verb in another passage of the article is not this passage's.
            ('Resepsi Contoh di Hotel Contoh dihadiri delegasi.', 'Resepsi Lain diselenggarakan di Hotel Lain.'),
        )
        for passage, other in cases:
            with self.subTest(other=other), self.assertRaisesRegex(d.IntakeHold, STAGE):
                self.run_verb(passage, 'Resepsi Contoh was held at Hotel Contoh.',
                              'Resepsi Contoh at Hotel Contoh was attended by a delegation.', other)

    def test_the_organised_event_verb_supports_no_other_outcome(self):
        for word in ('signed', 'completed', 'delivered', 'agreed', 'acquired', 'deployed'):
            with self.subTest(word=word), self.assertRaisesRegex(d.IntakeHold, STAGE):
                self.run_verb(self.HELD, 'Resepsi Contoh was held and ' + word + ' at Hotel Contoh.',
                              'Resepsi Contoh was held at Hotel Contoh.')

    def test_a_generic_do_verb_is_not_support_for_conducted(self):
        with self.assertRaisesRegex(d.IntakeHold, STAGE):
            self.run_verb('Menteri Contoh melakukan peninjauan di Lapangan Contoh.',
                          'Menteri Contoh visited Lapangan Contoh.',
                          'Menteri Contoh conducted an inspection at Lapangan Contoh.')


class ExerciseDevelopmentPhrase(unittest.TestCase):
    PASSAGE = 'Latihan Contoh merupakan puncak dari rangkaian pembinaan latihan.'

    def run_phrase(self, translation, passage=None, other=None):
        r, reply = case(passage or self.PASSAGE, 'Latihan Contoh was the culmination of a training series.',
                        translation, other)
        return d.quality_check(r, reply)

    def test_exercise_development_renders_the_local_phrase(self):
        for phrase in ('exercise development', 'training development', 'exercise-development'):
            with self.subTest(phrase=phrase):
                self.assertEqual(len(self.run_phrase(
                    'Latihan Contoh is the culmination of a series of ' + phrase + ' activities.')), 64)

    def test_other_development_claims_still_need_pengembangan(self):
        cases = (
            # The phrase elsewhere in the article does not support this passage.
            ('Latihan Contoh is the culmination of a series of exercise development activities.',
             'Latihan Contoh merupakan puncak dari rangkaian latihan.', 'Pembinaan latihan berlanjut.'),
            # The local phrase clears only its own words, not a second claim.
            ('Latihan Contoh is the culmination of exercise development and weapons development.',
             None, None),
            ('Latihan Contoh is the culmination of a series of development activities.', None, None),
        )
        for translation, passage, other in cases:
            with self.subTest(translation=translation), self.assertRaisesRegex(d.IntakeHold, CONCEPT):
                self.run_phrase(translation, passage, other)


if __name__ == '__main__':
    unittest.main()
