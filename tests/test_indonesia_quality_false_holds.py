"""Kemhan QA: faithful renderings pass, real substitutions still hold.

Every passage, name, office and institution here is synthetic. Nothing is
publisher text or a real model response.
"""
import unittest

from processing import daily_intake as d
from tests.test_indonesia_shared_daily import record, reading

FORM, NAME = 'daily_institution_form_not_local', 'daily_name_or_office_unsupported'
TRANSLATION = 'daily_private_translation_name_unsupported'


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


if __name__ == '__main__':
    unittest.main()
