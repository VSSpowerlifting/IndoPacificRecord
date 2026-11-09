"""Offline synthetic Indonesian regressions. No live/paid model response."""
import copy
import hashlib
import json
import sqlite3
import unittest
from unittest.mock import Mock, patch

from analysis.analyzer import Analyzer
from analysis.indonesia_prompts import VERSION
from core.indonesia_kemhan_release_validator import HELD_IDENTITY
from processing import daily_intake as d
from processing.screening import INDONESIA_PROFILE, PHILIPPINES_PROFILE, profile_for_source
from tests.test_philippines_shared_daily import record as ph_record, fake_analyzer as ph_analyzer

FAMILY = 'id_kemhan_news'
KEY = 'offline-Indonesia-test-key-' * 2


def policy():
    p = d.load_policy()
    p['sources'][FAMILY].update(private_model_processing=True,
        public_machine_explanation=True, unattended_release=True,
        owner_decision='SYNTHETIC TEST ONLY; no owner authorization')
    return p


def denied_policy():
    p = policy()
    p['sources'][FAMILY].update(private_model_processing=False,
        public_machine_explanation=False, unattended_release=False,
        owner_decision='SYNTHETIC DENIED TEST POLICY')
    return p


def record():
    # Explicitly synthetic Indonesian text, never represented as publisher text.
    body = 'Latihan direncanakan akan berlangsung pada 23 Oktober.\n\nPertemuan membahas rencana latihan bersama.'
    return dict(ph_record(), source_family=FAMILY,
        source_identity='kemhan:/2026/10/19/synthetic-fixture.html',
        canonical_official_url='https://www.kemhan.go.id/2026/10/19/synthetic-fixture.html',
        title='SYNTHETIC Indonesian fixture', body=body,
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
        official_issuer=None, official_publisher='id_kemhan', official_republisher=None)


def reading():
    sentences = ['Kemhan reports plans for an exercise on 23 Oktober.',
                 'Kemhan describes discussions about a planned joint exercise.']
    return dict(passed_relevance=True, requires_translation=False,
        summary_english=' '.join(sentences), facts=[
            dict(sentence=sentences[0], evidence='Latihan direncanakan akan berlangsung pada 23 Oktober.',
                 evidence_translation='An exercise is planned for 23 Oktober.'),
            dict(sentence=sentences[1], evidence='Pertemuan membahas rencana latihan bersama.',
                 evidence_translation='The meeting discusses plans for a joint exercise.')],
        categories=['exercises'], is_significant=False, significance_reasoning=None,
        model_id='offline-mock-model', prompt_version=VERSION)


def analyzer(reply=None):
    a = Mock()
    a.analyze_record.return_value = reading() if reply is None else reply
    a.usage.rows.return_value = []
    return a


class IndonesiaSharedDaily(unittest.TestCase):
    def process(self, records=None, state=None, a=None, p=None):
        return d.process(records or [record()], state or {}, family=FAMILY,
            policy=p or policy(), analyzer_factory=lambda: a or analyzer())[0]

    def test_profile_explicit_and_kept_out_of_public_original_queue(self):
        self.assertIs(profile_for_source(FAMILY), INDONESIA_PROFILE)
        self.assertEqual(INDONESIA_PROFILE.source_language, 'id')
        self.assertFalse(INDONESIA_PROFILE.translates)
        self.assertFalse(INDONESIA_PROFILE.daily_queue)
        self.assertIs(profile_for_source('ph_afp_articles'), PHILIPPINES_PROFILE)
        self.assertEqual(profile_for_source('vn_mps_foreign_affairs_vi').desk_id, 'vietnam')
        self.assertEqual(profile_for_source('unknown').desk_id, 'unsupported')

    def test_actual_analyzer_two_calls_resolve_private_translations(self):
        r, reply = record(), reading()
        out = dict(flag=False, flag_reason=None,
            flag_evidence_id=None, categories=['exercises'], facts=[
                dict(sentence=f['sentence'], evidence_id='P'+str(i+1),
                     evidence_translation=f['evidence_translation'])
                for i,f in enumerate(reply['facts'])])
        a = Analyzer.__new__(Analyzer)
        with patch.object(a, '_call', side_effect=[json.dumps(dict(score=.9, reasoning='Offline.')),json.dumps(out)]) as call, \
             patch.object(a, 'translate', side_effect=AssertionError('China route')), \
             patch.object(a, 'categorize', side_effect=AssertionError('China categories')):
            result = a.analyze_record(r['title'], r['body'], INDONESIA_PROFILE)
        self.assertEqual(call.call_count, 2)
        self.assertIn('Indonesian', call.call_args_list[0].kwargs['system'][0]['text'])
        self.assertIsNone(result['text_english'])
        self.assertIsNone(result['title_english'])
        self.assertEqual(len(d.quality_check(r,result)), 64)

    def test_fact_only_contract_derives_summary_without_an_extra_call(self):
        r, reply = record(), reading()
        payload = dict(flag=False, flag_reason=None, flag_evidence_id=None,
            categories=reply['categories'], facts=[
                dict(sentence=f['sentence'], evidence_id='P'+str(i+1),
                     evidence_translation=f['evidence_translation'])
                for i,f in enumerate(reply['facts'])])
        a = Analyzer.__new__(Analyzer)
        with patch.object(a, '_call', return_value=json.dumps(payload)) as call:
            result = a._desk_summary_and_flag(r['title'],r['body'],INDONESIA_PROFILE)
        self.assertEqual(result[0],reply['summary_english'])
        call.assert_called_once()
        # Unexpected duplicate text must not be silently dropped to gain a pass.
        for change in ({'summary':'Unsupported additional claim.'},
                       {'flag_reason':'Unsupported additional claim.'},
                       {'facts':[dict(payload['facts'][0],evidence_id='P999'),payload['facts'][1]]},
                       {'facts':[dict(payload['facts'][0],evidence_id='P2'),payload['facts'][1]]}):
            with self.subTest(change=list(change)):
                changed=dict(payload,**change)
                with patch.object(a,'_call',return_value=json.dumps(changed)):
                    if ('summary' in change or 'flag_reason' in change
                            or changed['facts'][0]['evidence_id']=='P999'):
                        from analysis.analyzer import AnalysisError
                        with self.assertRaises(AnalysisError):
                            a._desk_summary_and_flag(r['title'],r['body'],INDONESIA_PROFILE)
                    else:
                        summary,flag,reason,cats,facts,_=a._desk_summary_and_flag(r['title'],r['body'],INDONESIA_PROFILE)
                        bad=dict(reply,summary_english=summary,facts=facts)
                        with self.assertRaises(d.IntakeHold):d.quality_check(r,bad)

    def test_complete_passages_do_not_cut_or_complete_long_sentences(self):
        from analysis.indonesia_prompts import evidence_passages
        first='SYNTHETIC '+('latihan ' * 48).strip()+'.'
        second='SYNTHETIC '+('peserta ' * 32).strip()+'.'
        body=first+' '+second
        self.assertGreater(len(body),500)
        self.assertEqual([t for _,t in evidence_passages(body)],[first,second])
        body=first+'   \n'+second
        self.assertTrue(all(t in body for _,t in evidence_passages(body)))
        self.assertEqual(evidence_passages('SYNTHETIC '+('kata '*130)+'.'),[])
        body='SYNTHETIC '+('latihan ' * 55)+'dr. Contoh memimpin latihan. '+second
        self.assertTrue(any('dr. Contoh' in t for _,t in evidence_passages(body)))
        self.assertTrue(all(t in body and len(t)<=500 for _,t in evidence_passages(body)))

    def dated_reading(self):
        r=record();reply=reading()
        r['body']='Latihan dilaksanakan pada 21/10/2026.\n\nPertemuan membahas rencana latihan bersama.'
        # Publication is later than the actual event.
        r['publisher_posted_date']='2026-10-23'
        reply['facts'][0]=dict(sentence='Kemhan reports an exercise on 21 Oktober 2026.',
            evidence=r['body'].split('\n\n')[0],evidence_translation='An exercise was held on 21 October 2026.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_equivalent_date_formats_are_not_changed_events(self):
        r,reply=self.dated_reading()
        for date_text in ('21 Oktober 2026','21 October 2026','21 OCTOBER 2026','21 OKTOBER 2026','21/10/2026','2026-10-21','21-10-2026'):
            with self.subTest(date=date_text):
                reply['facts'][0]['sentence']='Kemhan reports an exercise on '+date_text+'.'
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_wrong_dates_and_private_translation_still_fail(self):
        for field,value in (('sentence','Kemhan reports an exercise on 23 October 2026.'),
                            ('evidence_translation','An exercise was held on 22 October 2026.'),
                            ('evidence_translation','An exercise was held on 21 November 2026.')):
            r,reply=self.dated_reading();reply['facts'][0][field]=value
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(field=field,value=value),self.assertRaisesRegex(d.IntakeHold,'daily_quantity_or_date_unsupported'):
                d.quality_check(r,reply)
        r,reply=self.dated_reading();reply['facts'][0]['sentence']='Kemhan reports an exercise on 31/02/2026.'
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaisesRegex(d.IntakeHold,'daily_date_invalid'):d.quality_check(r,reply)

    def test_private_translation_cannot_add_cross_passage_names_or_completions(self):
        r,reply=self.dated_reading();r['body']+='\n\nSYNTHETIC Contoh menghadiri kegiatan terpisah.'
        for translation,reason in (
            ('An exercise was held on 21 October 2026 with Contoh.','daily_private_translation_name_unsupported'),
            ('An exercise was held on 21 October 2026 with [Contoh].','daily_private_translation_completion_held')):
            reply['facts'][0]['evidence_translation']=translation
            with self.subTest(reason=reason),self.assertRaisesRegex(d.IntakeHold,reason):d.quality_check(r,reply)

    def test_private_translation_must_preserve_negation_and_action_status(self):
        r,reply=self.dated_reading()
        reply['facts'][0]['evidence_translation']='An exercise was completed on 21 October 2026.'
        with self.assertRaisesRegex(d.IntakeHold,'daily_completed_action_unsupported'):d.quality_check(r,reply)
        r=record();reply=reading();r['body']=r['body'].replace('direncanakan akan','tidak akan')
        reply['facts'][0]['evidence']=r['body'].split('\n\n')[0]
        reply['facts'][0]['sentence']='Kemhan reports an exercise will not be held on 23 Oktober.'
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        # Public negation cannot excuse its loss in the private translation.
        with self.assertRaisesRegex(d.IntakeHold,'daily_negation_lost'):d.quality_check(r,reply)

    def test_private_translation_cannot_invent_negation_or_change_unit_suffix(self):
        r,reply=self.dated_reading()
        reply['facts'][0]['evidence_translation']='An exercise was not held on 21 October 2026.'
        with self.assertRaisesRegex(d.IntakeHold,'daily_negation_unsupported'):d.quality_check(r,reply)
        r,reply=self.dated_reading()
        r['body']=r['body'].replace('dilaksanakan','dilaksanakan menggunakan SYN-120B')
        reply['facts'][0]['evidence']=r['body'].split('\n\n')[0]
        reply['facts'][0]['evidence_translation']='An exercise used SYN-120C on 21 October 2026.'
        with self.assertRaisesRegex(d.IntakeHold,'daily_quantity_or_date_unsupported'):d.quality_check(r,reply)

    def numbered_reading(self, abbreviation='No. 17', negative=False):
        r,reply=record(),reading()
        first='Dokumen '+abbreviation+(' tidak mengubah' if negative else ' menjelaskan')+' rencana latihan.'
        r['body']=first+'\n\n'+r['body'].split('\n\n')[1]
        reply['facts'][0]=dict(evidence=first,
            sentence='Kemhan reports '+('no change to plans' if negative else 'exercise plans')+' in document '+abbreviation+'.',
            evidence_translation='Document '+abbreviation+(' does not change exercise plans.' if negative else ' describes exercise plans.'))
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_document_number_abbreviation_is_not_negation(self):
        for abbreviation in ('No. 17','No.17','NO. 17','no. 17'):
            r,reply=self.numbered_reading(abbreviation)
            with self.subTest(abbreviation=abbreviation):
                self.assertEqual(len(d.quality_check(r,reply)),64)
        # Ignoring the abbreviation for negation never ignores the number.
        reply['facts'][0]['sentence']=reply['facts'][0]['sentence'].replace('17','18')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaisesRegex(d.IntakeHold,'daily_quantity_or_date_unsupported'):d.quality_check(r,reply)

    def test_document_number_does_not_hide_invented_negation(self):
        r,reply=self.numbered_reading()
        for field,text in (
            ('sentence','Kemhan reports no exercise plans in document No. 17.'),
            ('evidence_translation','Document No. 17 contains no exercise plans.')):
            bad=copy.deepcopy(reply);bad['facts'][0][field]=text
            bad['summary_english']=' '.join(f['sentence'] for f in bad['facts'])
            with self.subTest(field=field),self.assertRaisesRegex(d.IntakeHold,'daily_negation_unsupported'):
                d.quality_check(r,bad)

    def test_document_number_cannot_replace_actual_source_negation(self):
        r,reply=self.numbered_reading(negative=True)
        self.assertEqual(len(d.quality_check(r,reply)),64)
        for field,text in (
            ('sentence','Kemhan reports exercise plans in document No. 17.'),
            ('evidence_translation','Document No. 17 describes exercise plans.')):
            bad=copy.deepcopy(reply);bad['facts'][0][field]=text
            bad['summary_english']=' '.join(f['sentence'] for f in bad['facts'])
            with self.subTest(field=field),self.assertRaisesRegex(d.IntakeHold,'daily_negation_lost'):
                d.quality_check(r,bad)

    def test_cross_passage_industry_claim_is_not_supported_by_the_article(self):
        r,reply=self.dated_reading()
        r['body']+='\n\nSYNTHETIC program pengembangan sumber daya manusia.'
        for field in ('sentence','evidence_translation'):
            bad=copy.deepcopy(reply)
            bad['facts'][0][field]+=' The exercise supports human-resource development.'
            bad['summary_english']=' '.join(f['sentence'] for f in bad['facts'])
            with self.subTest(field=field),self.assertRaisesRegex(d.IntakeHold,'daily_cross_passage_claim_unsupported'):d.quality_check(r,bad)

    def development_reading(self, passage, sentence, translation, other=None):
        # Synthetic passages; only the "development" phrase and its support vary.
        r,reply=record(),reading()
        r['body']=passage+'\n\n'+(other+'\n\n' if other else '')+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=passage,sentence='Kemhan reports that '+sentence+'.',
            evidence_translation=translation+'.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_development_rendering_a_local_phrase_is_not_an_industry_claim(self):
        passage='Latihan bersama mendukung pembinaan satuan dan pembangunan daerah.'
        for phrase in ('unit-development and regional development','unit development and regional development'):
            r,reply=self.development_reading(passage,'the joint exercise supports '+phrase,
                'The joint exercise supports '+phrase)
            with self.subTest(phrase=phrase):
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_development_needs_its_own_phrase_in_the_cited_passage(self):
        both='Latihan bersama mendukung pembinaan satuan dan pembangunan daerah.'
        cases=(  # (cited passage, other passage, unsupported phrase)
            ('Latihan bersama membahas rencana satuan.','Program pembinaan satuan dan pembangunan daerah berlanjut.','unit-development'),
            ('Latihan bersama membahas rencana satuan.','Program pembinaan satuan dan pembangunan daerah berlanjut.','regional development'),
            ('Latihan bersama mendukung pembinaan satuan.',None,'regional development'),
            ('Latihan bersama mendukung pembangunan daerah.',None,'unit development'),
            # A unit name containing "Pembangunan" is not regional development.
            ('Batalyon Contoh Pembangunan (Yonif CP) membahas latihan.',None,'regional development'),
            (both,None,'development'),(both,None,'weapons development'),
            (both,None,'research and development'),(both,None,'defense-industry development'))
        for passage,other,phrase in cases:
            for field in ('sentence','evidence_translation'):
                r,reply=self.development_reading(passage,'the joint exercise is discussed',
                    'The joint exercise is discussed',other)
                reply['facts'][0][field]=reply['facts'][0][field][:-1]+' for '+phrase+'.'
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                with self.subTest(passage=passage,phrase=phrase,field=field),\
                        self.assertRaisesRegex(d.IntakeHold,'daily_cross_passage_claim_unsupported'):
                    d.quality_check(r,reply)

    def test_derived_summary_cannot_shorten_an_over_budget_fact(self):
        r,reply=self.dated_reading();reply['facts'][0]['sentence']+=' reported'*90
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaisesRegex(d.IntakeHold,'daily_summary_invalid'):d.quality_check(r,reply)

    def test_prompt_revision_keeps_source_version_attempts_and_exhaustion(self):
        for previous_failures in (1,2,3,4):
            state=self.process(a=analyzer({}));key=next(iter(state))
            state[key]['attempts']=previous_failures
            a=analyzer({})
            for _ in range(5):state=self.process(state=state,a=a)
            self.assertEqual(a.analyze_record.call_count,5-previous_failures)
            self.assertEqual((state[key]['attempts'],state[key]['status']),(5,'paused'))
        for status in ('paused','terminal','held'):
            state[key].update(status=status,attempts=5,reason='existing_exception')
            a=analyzer();out=self.process(state=state,a=a);a.analyze_record.assert_not_called()
            self.assertEqual(out[key],state[key])

    def office_reading(self):
        # Entirely synthetic names, institution and credential suffixes.
        r,reply=record(),reading()
        first=('Kepala RS Contoh, Brigjen TNI dr. Nama Uji, M.Kes., '
               'Sp. SYN., Subsp.A.B.(C), menyampaikan kesiapan rumah sakit.')
        r['body']=first+'\n\n'+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=first,
            sentence='Kemhan reports that Head of RS Contoh, Nama Uji, described hospital readiness.',
            evidence_translation=('The Head of RS Contoh, Brigjen TNI dr. Nama Uji, M.Kes., '
                'Sp. SYN., Subsp.A.B.(C), described hospital readiness.'))
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def first_fact(self, evidence, sentence, translation, rest=''):
        # Synthetic Indonesian text and invented units; never publisher text.
        r,reply=record(),reading()
        r['body']=evidence+'\n\n'+reply['facts'][1]['evidence']+rest
        reply['facts'][0]=dict(evidence=evidence,sentence=sentence,evidence_translation=translation)
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_suffix_defined_by_exact_initials_in_cited_passage_is_same_identifier(self):
        long,both,short='123/Garuda Satu','123/Garuda Satu (GS)','123/GS'
        for sentence_unit,translation_unit in ((short,both),(long,both),(both,both),(short,long),(short,short)):
            r,reply=self.first_fact('Batalyon Uji '+both+' menggelar latihan.',
                'Kemhan reports that Batalyon Uji '+sentence_unit+' holds an exercise.',
                'Batalyon Uji '+translation_unit+' holds an exercise.')
            with self.subTest(sentence=sentence_unit,translation=translation_unit):
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_suffix_abbreviation_without_exact_local_definition_holds(self):
        cases=[  # wrong number; mismatched initials; definition only elsewhere in body
            ('Batalyon Uji 123/Garuda Satu (GS) menggelar latihan.','124/GS','Batalyon Uji 123/Garuda Satu (GS)',''),
            ('Batalyon Uji 123/Garuda Satu (GX) menggelar latihan.','123/GX','Batalyon Uji 123/Garuda Satu (GX)',''),
            ('Batalyon Uji 123/Garuda Satu menggelar latihan.','123/GS','Batalyon Uji 123/Garuda Satu',
             '\n\nBatalyon Uji 123/Garuda Satu (GS) dibentuk.')]
        for evidence,unit,translated,rest in cases:
            r,reply=self.first_fact(evidence,'Kemhan reports that Batalyon Uji '+unit+' holds an exercise.',
                translated+' holds an exercise.',rest)
            with self.subTest(unit=unit,rest=bool(rest)),self.assertRaisesRegex(d.IntakeHold,'daily_quantity_or_date_unsupported'):
                d.quality_check(r,reply)

    def test_weekday_requires_its_indonesian_name_in_cited_passage(self):
        evidence='Latihan direncanakan akan berlangsung pada Selasa, 23 Oktober.'
        def run(day,source=evidence):
            return self.first_fact(source,'Kemhan reports plans for an exercise on '+day+', 23 Oktober.',
                'An exercise is planned for '+day+', 23 Oktober.')
        self.assertEqual(len(d.quality_check(*run('Tuesday'))),64)
        r,reply=run('Sunday','Latihan direncanakan akan berlangsung pada Minggu, 23 Oktober.')
        self.assertEqual(len(d.quality_check(r,reply)),64)
        for day,source in (('Wednesday',evidence),
                           ('Tuesday','Latihan direncanakan akan berlangsung pada 23 Oktober.'),
                           ('Sunday','Latihan satu minggu direncanakan pada 23 Oktober.')):
            r,reply=run(day,source)
            with self.subTest(day=day,source=source),self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
                d.quality_check(r,reply)

    def institution_reading(self, form='Kementerian Contoh'):
        # Synthetic institutions and text; no publisher article or real response.
        r,reply=record(),reading()
        first=form+' membahas rencana latihan bersama.'
        r['body']=first+'\n\n'+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=first,
            sentence='Kemhan reports that '+form+' discusses joint exercise plans.',
            evidence_translation=form+' discusses plans for a joint exercise.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_exact_local_institution_forms_pass_in_both_fields(self):
        for form in ('Kementerian Contoh','Kemencontoh','Ministry of Contoh'):
            r,reply=self.institution_reading(form)
            with self.subTest(form=form):
                self.assertEqual(len(d.quality_check(r,reply)),64)
        # Either literal form is usable when the cited passage supplies both;
        # this does not create an alias mapping for any other passage.
        for form in ('Kementerian Contoh','Kemencontoh'):
            r,reply=self.institution_reading('Kementerian Contoh (Kemencontoh)')
            reply['facts'][0]['sentence']='Kemhan reports that '+form+' discusses exercise plans.'
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(parenthesized=form):
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def holder_reading(self, passage, sentence_form, translation_form, other=None):
        # Synthetic title, abbreviation and people; never publisher text.
        r,reply=record(),reading()
        r['body']=passage+'\n\n'+(other+'\n\n' if other else '')+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=passage,
            sentence='Kemhan reports that '+sentence_form+' discusses joint exercise plans.',
            evidence_translation=translation_form+' discusses plans for a joint exercise.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_abbreviation_and_holder_defined_in_the_cited_passage_pass(self):
        for passage,form in (
                ('Menteri Contoh Negara (MCN) Budi Contoh membahas rencana latihan bersama.','MCN Budi Contoh'),
                ('Menteri Contoh Republik Negara (Mencon RN) Budi Contoh membahas rencana latihan.','Mencon RN Budi Contoh')):
            r,reply=self.holder_reading(passage,form,form)
            with self.subTest(form=form):
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_abbreviation_holder_form_is_not_inferred_or_borrowed(self):
        defined='Menteri Contoh Negara (MCN) Budi Contoh hadir dalam pertemuan.'
        cases=(  # (cited passage, other passage, abbreviation-holder form)
            # Mismatched person: both people are local; only one is defined.
            ('Menteri Contoh Negara (MCN) Budi Contoh membahas latihan bersama Ani Lain.',None,'MCN Ani Lain'),
            ('Menteri Contoh Negara (MCN) Budi Contoh membahas rencana latihan.',None,'MCN Budi'),
            # Undefined abbreviation: no multiword title, lowercase title or parentheses.
            ('Pejabat (MCN) Budi Contoh membahas rencana latihan bersama.',None,'MCN Budi Contoh'),
            ('menteri contoh negara (MCN) Budi Contoh membahas rencana latihan.',None,'MCN Budi Contoh'),
            ('Menteri Contoh Negara MCN, Budi Contoh, membahas rencana latihan.',None,'MCN Budi Contoh'),
            # Definition found only in another passage of the same article.
            ('MCN membahas rencana latihan bersama Budi Contoh.',defined,'MCN Budi Contoh'))
        for passage,other,form in cases:
            for field in ('sentence','evidence_translation'):
                forms=dict(sentence='MCN',evidence_translation='MCN');forms[field]=form
                r,reply=self.holder_reading(passage,forms['sentence'],forms['evidence_translation'],other)
                with self.subTest(passage=passage,form=form,field=field),\
                        self.assertRaisesRegex(d.IntakeHold,'daily_institution_form_not_local'):
                    d.quality_check(r,reply)
        # A holder named only by the other passage's definition stays a name hold.
        r,reply=self.holder_reading('MCN membahas rencana latihan bersama.','MCN Budi','MCN',defined)
        with self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
            d.quality_check(r,reply)

    def possessive_reading(self, sentence_name):
        # Synthetic passage; only the possessive spelling and base name vary.
        r,reply=record(),reading()
        first='Delegasi Indonesia membahas rencana latihan bersama.'
        r['body']=first+'\n\n'+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=first,
            sentence='Kemhan reports that '+sentence_name+' delegation discusses joint exercise plans.',
            evidence_translation='The delegation of Indonesia discusses plans for a joint exercise.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        return r,reply

    def test_possessive_of_a_local_name_is_judged_like_its_name(self):
        # The straight and typographic apostrophes must not be judged differently.
        for name in ('Indonesia','Indonesia\'s','Indonesia’s'):
            r,reply=self.possessive_reading(name)
            with self.subTest(name=name):
                self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_possessive_does_not_make_a_nonlocal_name_or_form_local(self):
        for name in ('Singapore','Singapore\'s','Singapore’s','Indonesian\'s','Indonesians\'',
                     'Indonesia\'s Singapore\'s'):
            r,reply=self.possessive_reading(name)
            with self.subTest(name=name),self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
                d.quality_check(r,reply)

    def test_possessive_of_a_local_institution_is_judged_like_its_form(self):
        # Same glyph rule for the institution-form gate, in both fields.
        for form in ('Kementerian Contoh','Ministry of Contoh'):
            for mark in ("'",'\u2019'):
                for field in ('sentence','evidence_translation'):
                    r,reply=self.institution_reading(form)
                    reply['facts'][0][field]=reply['facts'][0][field].replace(form,form+mark+'s plans for',1)
                    reply['facts'][0][field]=reply['facts'][0][field].replace(' plans for discusses',' discusses')
                    reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                    with self.subTest(form=form,mark=mark,field=field):
                        self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_possessive_does_not_make_a_nonlocal_institution_local(self):
        for mark in ("'",'\u2019'):
            for field in ('sentence','evidence_translation'):
                r,reply=self.institution_reading()
                reply['facts'][0][field]=reply['facts'][0][field].replace('Kementerian Contoh','Kementerian Lain'+mark+'s')
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                with self.subTest(mark=mark,field=field),self.assertRaises(d.IntakeHold):
                    d.quality_check(r,reply)

    def test_institution_acronyms_expansions_and_translations_are_not_inferred(self):
        for source,alias in (('Kementerian Contoh','Kemencontoh'),
                             ('Kementerian Contoh','kemencontoh'),
                             ('Kemencontoh','Kementerian Contoh'),
                             ('Kemencontoh','kementerian contoh'),
                             ('Kementerian Contoh','Ministry of Contoh'),
                             ('Kementerian Contoh','ministry of contoh')):
            for field in ('sentence','evidence_translation'):
                r,reply=self.institution_reading(source)
                reply['facts'][0][field]=reply['facts'][0][field].replace(source,alias)
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                with self.subTest(source=source,alias=alias,field=field),self.assertRaises(d.IntakeHold):
                    d.quality_check(r,reply)

    def test_wrong_institutions_and_cross_passage_borrowing_fail_both_fields(self):
        for field in ('sentence','evidence_translation'):
            for other_passage in (False,True):
                r,reply=self.institution_reading()
                if other_passage:r['body']+='\n\nKementerian Lain membahas rencana latihan.'
                reply['facts'][0][field]=reply['facts'][0][field].replace('Kementerian Contoh','Kementerian Lain')
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                with self.subTest(field=field,other_passage=other_passage),self.assertRaises(d.IntakeHold):
                    d.quality_check(r,reply)
            # Merely finding all component words in the same passage cannot
            # authorize a newly assembled institution name.
            r,reply=self.institution_reading()
            old=reply['facts'][0]['evidence'];new=old.replace(' membahas',' dan Lembaga Lain membahas')
            r['body']=r['body'].replace(old,new);reply['facts'][0]['evidence']=new
            reply['facts'][0]['evidence_translation']='Kementerian Contoh and Lembaga Lain discuss exercise plans.'
            reply['facts'][0][field]=reply['facts'][0][field].replace('Kementerian Contoh','Kementerian Lain')
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(field=field,assembled=True),self.assertRaisesRegex(d.IntakeHold,'daily_institution_form_not_local'):
                d.quality_check(r,reply)

    def test_passage_ids_supply_literal_local_institutions_without_title_aliases(self):
        from analysis.indonesia_prompts import analysis_messages
        body='Kementerian Contoh membahas rencana latihan.\n\nKemencontoh menghadiri kegiatan.'
        message=analysis_messages('SYNTHETIC title alias',body)[0]['content']
        payload=json.loads(message.split('\n',1)[1])
        self.assertNotIn('title',payload)
        self.assertEqual([(p['id'],p['institutional_forms']) for p in payload['passages']],
                         [('P1',['Kementerian Contoh']),('P2',['Kemencontoh'])])

    def test_passages_opening_with_a_back_reference_are_marked_context_dependent(self):
        from analysis.indonesia_prompts import analysis_messages, context_dependent
        for text in ('Selain itu, Kemhan membahas rencana latihan.','Ia menyampaikan rencana latihan.',
                     'Dalam kesempatan tersebut dibahas rencana latihan.','Menurutnya, latihan akan dimulai.',
                     'Menurut dia, latihan akan dimulai.','Menurut beliau, latihan akan dimulai.',
                     'Kegiatan tersebut diikuti dua puluh peserta.','Latihan itu diikuti dua puluh peserta.','Mereka membahas rencana latihan.'):
            with self.subTest(text=text): self.assertTrue(context_dependent(text))
        for text in ('Kementerian Contoh membahas rencana latihan.','Iaido adalah olahraga bela diri.',
                     'Diah menghadiri kegiatan latihan.','Latihan bersama diikuti dua puluh peserta.',
                     'Menurut Kementerian Contoh, latihan akan dimulai.','Menurut Menteri Contoh, latihan akan dimulai.',
                     'Menurut Kemhan, latihan akan dimulai.'):
            with self.subTest(text=text): self.assertFalse(context_dependent(text))
        body='Kementerian Contoh membahas rencana latihan.\n\nSelain itu, rencana pengadaan juga dibahas.'
        message=analysis_messages('SYNTHETIC title alias',body)[0]['content']
        payload=json.loads(message.split('\n',1)[1])
        self.assertEqual([(p['id'],p['context_dependent']) for p in payload['passages']],[('P1',False),('P2',True)])
        self.assertEqual([p['institutional_forms'] for p in payload['passages']],[['Kementerian Contoh'],[]])
        self.assertNotIn('title',payload)

    def test_prompt_forbids_borrowing_an_actor_for_a_context_dependent_passage(self):
        from analysis.indonesia_prompts import analysis_messages
        text=analysis_messages('SYNTHETIC title','Kementerian Contoh membahas rencana latihan.')[0]['content']
        self.assertIn('context_dependent true',text)
        self.assertIn('cite a different passage or omit the detail',text)
        self.assertIn('never a reason to borrow',text)
        self.assertNotIn('Retain the actual actor',text)

    def test_context_dependent_marker_does_not_relax_local_support_checks(self):
        # The marker is a prompt aid only: a fact that borrows an actor from
        # another passage fails the same source-local gate as before.
        r,reply=self.institution_reading()
        r['body']+='\n\nSelain itu, rencana pengadaan Kementerian Contoh juga dibahas.'
        fact=reply['facts'][1]
        fact['evidence']='Selain itu, rencana pengadaan juga dibahas.'
        r['body']=r['body'].replace('Selain itu, rencana pengadaan Kementerian Contoh juga dibahas.',fact['evidence'])
        fact['sentence']='Kemhan reports that Kementerian Contoh discussed procurement plans.'
        fact['evidence_translation']='Procurement plans were also discussed.'
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaises(d.IntakeHold):
            d.quality_check(r,reply)

    def test_context_dependent_marker_never_excludes_a_passage_that_names_its_actor(self):
        # Advisory only: the passage still reaches the model, and a fact whose
        # every name, number and date is in that passage passes the unchanged gate.
        from analysis.indonesia_prompts import analysis_messages, context_dependent, evidence_passages
        named='Selain itu, Kementerian Contoh membahas rencana pengadaan bersama.'
        self.assertTrue(context_dependent(named))
        r,reply=self.institution_reading()
        r['body']=r['body'].split('\n\n')[0]+'\n\n'+named
        reply['facts'][1]=dict(evidence=named,
            sentence='Kemhan reports that Kementerian Contoh discussed joint procurement plans.',
            evidence_translation='Additionally, Kementerian Contoh discussed joint procurement plans.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        self.assertEqual(len(d.quality_check(r,reply)),64)
        payload=json.loads(analysis_messages('SYNTHETIC title',r['body'])[0]['content'].split('\n',1)[1])
        self.assertEqual([(p['id'],p['text']) for p in payload['passages']],evidence_passages(r['body']))
        self.assertEqual([p['context_dependent'] for p in payload['passages']],[False,True])
        # "Menurut <named actor>" is not a back reference; it names its actor.
        self.assertFalse(context_dependent('Menurut Kementerian Contoh, rencana pengadaan dibahas.'))

    def test_generic_translated_nouns_are_not_institution_names(self):
        r,reply=self.institution_reading()
        old=reply['facts'][0]['evidence']
        evidence='Layanan rumah sakit membahas rencana latihan bersama.'
        r['body']=r['body'].replace(old,evidence)
        reply['facts'][0]=dict(evidence=evidence,
            sentence='Kemhan reports discussions about hospital care plans.',
            evidence_translation='Hospital care discussions concern joint exercise plans.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        self.assertEqual(len(d.quality_check(r,reply)),64)

    def test_sentence_prefixes_do_not_hide_institutions(self):
        for form in ('Kementerian Contoh','Ministry of Contoh','MHC'):
            r,reply=self.institution_reading(form)
            old=reply['facts'][0]['evidence']
            evidence='Menurut '+old
            r['body']=r['body'].replace(old,evidence)
            reply['facts'][0]['evidence']=evidence
            reply['facts'][0]['evidence_translation']='Meanwhile '+form+' discusses exercise plans.'
            with self.subTest(form=form):
                self.assertEqual(len(d.quality_check(r,reply)),64)
        for alias in ('Kemencontoh','Ministry of Contoh','MHC'):
            r,reply=self.institution_reading()
            reply['facts'][0]['evidence_translation']='Meanwhile '+alias+' discusses exercise plans.'
            with self.subTest(alias=alias),self.assertRaisesRegex(d.IntakeHold,'daily_institution_form_not_local'):
                d.quality_check(r,reply)
        r,reply=self.institution_reading('National Ministry of Contoh')
        reply['facts'][0]['evidence_translation']='Municipal Ministry of Contoh discusses exercise plans.'
        with self.assertRaisesRegex(d.IntakeHold,'daily_institution_form_not_local'):
            d.quality_check(r,reply)

    def test_head_translation_binds_institution_and_full_named_holder(self):
        r,reply=self.office_reading()
        for head in ('Head','head'):
            supported=copy.deepcopy(reply)
            supported['facts'][0]['sentence']=supported['facts'][0]['sentence'].replace('Head',head)
            supported['summary_english']=' '.join(f['sentence'] for f in supported['facts'])
            self.assertEqual(len(d.quality_check(r,supported)),64)
            for old,new in (('RS Contoh','RS Lain'),('Nama Uji','Tokoh Lain'),
                            ('Nama Uji','Uji'),('Head','Director'),('Head','deputy Head')):
                bad=copy.deepcopy(reply)
                bad['facts'][0]['sentence']=bad['facts'][0]['sentence'].replace(old,new).replace('Head',head)
                # All these names and offices occur in the same passage, but
                # belonging to a different holder cannot support this role.
                extra=' Kepala RS Lain, Tokoh Lain, menyampaikan kesiapan.'
                rr=dict(r,body=r['body'].replace(reply['facts'][0]['evidence'],reply['facts'][0]['evidence']+extra))
                bad['facts'][0]['evidence']+=extra
                bad['facts'][0]['evidence_translation']+=' Head of RS Lain, Tokoh Lain, described readiness.'
                bad['summary_english']=' '.join(f['sentence'] for f in bad['facts'])
                with self.subTest(head=head,change=new),self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
                    d.quality_check(rr,bad)

    def test_head_not_whitelisted_or_supported_by_another_passage(self):
        r,reply=self.office_reading();first=reply['facts'][0]['evidence']
        for evidence in ('SYNTHETIC kegiatan rumah sakit bersama Nama Uji dan RS Contoh.',
                         first.replace('Kepala','Direktur'),first.replace('Kepala','Plt. Kepala')):
            bad=copy.deepcopy(reply);rr=dict(r,body=evidence+'\n\n'+r['body'])
            bad['facts'][0]['evidence']=evidence
            bad['facts'][0]['evidence_translation']='A hospital activity involves Nama Uji and RS Contoh.'
            for head in ('Head','head'):
                bad['facts'][0]['sentence']=reply['facts'][0]['sentence'].replace('Head',head)
                bad['summary_english']=' '.join(f['sentence'] for f in bad['facts'])
                with self.subTest(evidence=evidence,head=head),self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
                    d.quality_check(rr,bad)

    def test_head_injury_is_a_passage_supported_medical_term_not_an_office(self):
        r,reply=record(),reading()
        evidence='Simulasi evakuasi menangani pasien dengan cedera kepala.'
        r['body']=evidence+'\n\n'+reply['facts'][1]['evidence']
        reply['facts'][0]=dict(evidence=evidence,
            sentence='Kemhan reports that an evacuation scenario involved a head injury.',
            evidence_translation='The evacuation simulation treated a patient with a head injury.')
        for term in ('head injury','head injuries','Head injury','Head injuries'):
            reply['facts'][0]['sentence']='Kemhan reports that an evacuation scenario involved '+term+'.'
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(term=term):
                self.assertEqual(len(d.quality_check(r,reply)),64)
        # Clinical support elsewhere in the article cannot support this fact.
        unsupported='Simulasi evakuasi menangani pasien dengan luka tangan.'
        r['body']=unsupported+'\n\n'+r['body']
        reply['facts'][0]['evidence']=unsupported
        with self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
            d.quality_check(r,reply)

    def test_medical_head_use_does_not_bypass_an_office_in_the_same_fact(self):
        r,reply=self.office_reading()
        clinical=' Simulasi evakuasi menangani pasien dengan cedera kepala.'
        r['body']=r['body'].replace(reply['facts'][0]['evidence'],reply['facts'][0]['evidence']+clinical)
        reply['facts'][0]['evidence']+=clinical
        reply['facts'][0]['evidence_translation']+=' The scenario treated a head injury.'
        for head in ('Head','head'):
            for holder in ('Nama Uji','Tokoh Lain'):
                reply['facts'][0]['sentence']=(
                    'Kemhan reports that '+head+' of RS Contoh, '+holder+', described a head injury scenario.')
                reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
                with self.subTest(head=head,holder=holder):
                    if holder=='Nama Uji':
                        self.assertEqual(len(d.quality_check(r,reply)),64)
                    else:
                        with self.assertRaisesRegex(d.IntakeHold,'daily_name_or_office_unsupported'):
                            d.quality_check(r,reply)

    def test_copied_credentials_still_fail_after_office_translation_passes(self):
        r,reply=self.office_reading()
        reply['facts'][0]['sentence']=(
            'Kemhan reports that Head of RS Contoh, Brigjen TNI dr. Nama Uji, '
            'M.Kes., Sp. SYN., Subsp.A.B.(C), described hospital readiness.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaisesRegex(d.IntakeHold,'daily_original_excerpt_prohibited'):
            d.quality_check(r,reply)
        # Private translation retains the full credential chain; public output
        # omits it while retaining the complete holder, institution and role.
        _,concise=self.office_reading()
        self.assertEqual(len(d.quality_check(r,concise)),64)

    def test_private_office_abbreviation_cannot_borrow_an_expansion(self):
        r,reply=self.office_reading()
        first=reply['facts'][0]['evidence'].replace('Kepala RS Contoh','Kapuscontoh Kemhan')
        r['body']=first+'\n\n'+r['body']
        reply['facts'][0].update(evidence=first,
            sentence='Kemhan reports that Kapuscontoh Kemhan, Nama Uji, described hospital readiness.',
            evidence_translation='The Head of RS Contoh, Nama Uji, described hospital readiness.')
        reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
        with self.assertRaisesRegex(d.IntakeHold,'daily_private_translation_name_unsupported'):
            d.quality_check(r,reply)

    def test_unapproved_rights_never_construct_model(self):
        factory = Mock(side_effect=AssertionError('unauthorized model'))
        state,_=d.process([record()],{},family=FAMILY,policy=denied_policy(),analyzer_factory=factory)
        self.assertEqual(next(iter(state.values()))['reason'],'model_rights_held')
        factory.assert_not_called()
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_rights_held'):
            d.sign_outputs(state,family=FAMILY,policy=denied_policy(),key=KEY)

    def test_existing_semantic_hold_cannot_be_removed_by_policy(self):
        r=record(); r['source_identity']=HELD_IDENTITY
        p=policy();p['sources'][FAMILY]['excluded_source_identities']=[]
        a=analyzer(); state=self.process([r],a=a,p=p)
        self.assertEqual(next(iter(state.values()))['reason'],'source_semantic_anomaly')
        a.analyze_record.assert_not_called()
        r=record();r['semantic_exception_hold']='disputed_version'
        a=analyzer();self.process([r],a=a);a.analyze_record.assert_not_called()

    def test_per_sentence_attribution_and_evidence_are_required(self):
        for update, reason in [({'sentence':'A planned exercise is reported.'},'daily_attribution_missing'),
                               ({'evidence':'Invented source evidence longer than twenty characters.'},'daily_evidence_not_in_original')]:
            reply=reading();reply['facts'][0].update(update)
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(reason=reason),self.assertRaisesRegex(d.IntakeHold,reason):
                d.quality_check(record(),reply)

    def test_numbers_names_translation_and_modality_hold(self):
        for sentence, reason in [('Kemhan reports plans for an exercise on 24 Oktober.','daily_quantity_or_date_unsupported'),
                                 ('Kemhan reports plans for an exercise involving Beijing.','daily_name_or_office_unsupported'),
                                 ('Kemhan reports a completed exercise.','daily_modality_or_contradiction_hold')]:
            reply=reading();reply['facts'][0]['sentence']=sentence
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(reason=reason),self.assertRaisesRegex(d.IntakeHold,reason):
                d.quality_check(record(),reply)
        reply=reading();reply['facts'][0]['evidence_translation']='An exercise was held on 23 Oktober.'
        with self.assertRaisesRegex(d.IntakeHold,'daily_modality_or_contradiction_hold'):
            d.quality_check(record(),reply)

    def test_lost_negation_and_planned_event_as_completed_are_held(self):
        r=record();r['body']=r['body'].replace('direncanakan akan','tidak akan')
        reply=reading();reply['facts'][0]['evidence']=r['body'].split('\n\n')[0]
        with self.assertRaisesRegex(d.IntakeHold,'daily_negation_lost'):
            d.quality_check(r,reply)
        for past in ('took place', 'was held', 'was conducted', 'has been completed'):
            reply=reading()
            reply['facts'][0]['sentence']='Kemhan reports the planned exercise '+past+' on 23 Oktober.'
            reply['summary_english']=' '.join(f['sentence'] for f in reply['facts'])
            with self.subTest(past=past),self.assertRaisesRegex(d.IntakeHold,'daily_completed_action_unsupported'):
                d.quality_check(record(),reply)

    def test_geography_and_significance_require_source_rubric(self):
        for changes,reason in [({'categories':['south_china_sea']},'daily_topic_unsupported'),
                              ({'is_significant':True,'significance_reasoning':'Strategic.'},'daily_indonesia_flag_held')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(d.IntakeHold,reason):
                d.quality_check(record(),dict(reading(),**changes))

    def test_cached_rejected_terminal_and_revised_versions_never_reprocess(self):
        a=analyzer();state=self.process(a=a);self.process(state=state,a=a)
        self.assertEqual(a.analyze_record.call_count,1)
        revised=dict(record(),content_sha256='d'*64)
        state=self.process([revised],state=state,a=a)
        self.assertEqual(next(iter(state.values()))['reason'],'source_version_changed')
        self.assertEqual(a.analyze_record.call_count,1)
        a=analyzer(dict(reading(),passed_relevance=False));state=self.process(a=a)
        self.process(state=state,a=a);self.assertEqual(a.analyze_record.call_count,1)

    def test_terminal_disposition_is_never_automatically_reset(self):
        state=self.process()
        entry=next(iter(state.values()));entry.update(status='terminal',reason='no_usable_prose')
        a=analyzer();out=self.process(state=state,a=a)
        a.analyze_record.assert_not_called()
        self.assertEqual(next(iter(out.values()))['status'],'terminal')

    def test_failures_pause_after_existing_retry_budget(self):
        a=analyzer({}); state={}
        for _ in range(7):state=self.process(state=state,a=a)
        self.assertEqual(a.analyze_record.call_count,5)
        self.assertEqual(next(iter(state.values()))['status'],'paused')

    def test_one_record_per_run_and_no_other_desk_changes(self):
        other={'ph_afp_articles:afp:1':{'status':'held','reason':'owner_exception'}}
        rows=[record(),dict(record(),source_identity='kemhan:/2026/10/19/second.html')]
        state=self.process(rows,state=other)
        self.assertEqual(state['ph_afp_articles:afp:1'],other['ph_afp_articles:afp:1'])
        self.assertEqual([v['status'] for k,v in state.items() if k.startswith(FAMILY)],['complete','pending'])
        ph,_=d.process([ph_record()],{},family='ph_afp_articles',policy=policy(),analyzer_factory=ph_analyzer)
        self.assertEqual(ph['ph_afp_articles:afp:1']['status'],'complete')

    def test_signed_admission_replay_revisions_and_retained_holds(self):
        from migrations.versions.m0015_daily_machine_records import up
        from core.regional_official_link_release import SCHEMA_SQL
        import tempfile
        from pathlib import Path
        import core.daily_machine_records as machine
        p=policy();r=record();state=self.process()
        env=d.sign_outputs(state,family=FAMILY,policy=p,key=KEY)
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'scratch.db'
            with sqlite3.connect(db) as conn:
                conn.executescript(SCHEMA_SQL);up(conn)
                conn.execute('INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                    FAMILY,r['source_identity'],'indonesia',r['canonical_official_url'],
                    r['publisher_posted_date'],None,'id_kemhan',None,'c'*40,'a'*64,
                    '123-1','official_link_only','d'*64,'2026-10-19T00:00:00Z'))
                conn.commit()
                with self.assertRaises(d.IntakeHold):
                    d.admit(conn,env,family=FAMILY,policy=p,key='wrong-key-'*4)
                with self.assertRaisesRegex(d.IntakeHold,'daily_output_rights_held'):
                    d.admit(conn,env,family=FAMILY,policy=denied_policy(),key=KEY)
                self.assertEqual(d.admit(conn,env,family=FAMILY,policy=p,key=KEY)['admitted'],1)
                self.assertEqual(d.admit(conn,env,family=FAMILY,policy=p,key=KEY)['admitted'],0)
                changed=copy.deepcopy(state)
                next(iter(changed.values()))['output']['content_sha256']='e'*64
                revision=d.sign_outputs(changed,family=FAMILY,policy=p,key=KEY)
                self.assertIn('daily_released_version_changed',d.admit(conn,revision,family=FAMILY,policy=p,key=KEY)['holds'])
                with patch.object(machine,'load_policy',return_value=p):
                    rows=machine.load(db)
                self.assertEqual(rows[0]['desk_id'],'indonesia')
                archived=list(machine.archive_rows(rows))[0]
                self.assertEqual(archived['desks'],['indonesia'])
                self.assertEqual(archived['record_type'],'machine_explanation')
                held,_=d.process([],state,family=FAMILY,policy=p)
                d.admit(conn,d.sign_outputs(held,family=FAMILY,policy=p,key=KEY),family=FAMILY,policy=p,key=KEY)
                d.admit(conn,env,family=FAMILY,policy=p,key=KEY)
                self.assertEqual(conn.execute('SELECT publication_state FROM daily_machine_records').fetchone()[0],'held')
            with patch.object(machine,'load_policy',return_value=p):
                self.assertEqual(machine.load(db),[])

    def test_source_rights_hold_before_call_for_republished_material(self):
        for change in ({'official_publisher':'other'}, {'official_republisher':'other'},
                       {'body':record()['body']+'\nSumber: external publisher'}):
            a=analyzer();state=self.process([dict(record(),**change)],a=a)
            a.analyze_record.assert_not_called()
            self.assertEqual(next(iter(state.values()))['reason'],'source_rights_not_first_party')

    def test_private_cost_reservation_and_call_count(self):
        from config import RELEVANCE_MODEL
        a=Mock();call=a._call
        d.bound_private_calls(a,policy()['sources'][FAMILY])
        a._call([{'role':'user','content':'x'*16000}],max_tokens=500,task='relevance',model=RELEVANCE_MODEL)
        a._call([{'role':'user','content':'x'*16000}],max_tokens=2200,task='summary')
        with self.assertRaisesRegex(d.IntakeHold,'daily_private_call_bound'):
            a._call([],max_tokens=2200,task='summary')
        self.assertEqual(call.call_count,2)
        a=Mock();call=a._call
        d.bound_private_calls(a,dict(policy()['sources'][FAMILY],max_estimated_cost_usd_per_run=.00001))
        with self.assertRaisesRegex(d.IntakeHold,'daily_private_spend_bound'):
            a._call([],max_tokens=500,task='relevance',model=RELEVANCE_MODEL)
        call.assert_not_called()

    def test_machine_record_discloses_indonesian_processing(self):
        from jinja2 import Environment,FileSystemLoader,select_autoescape
        env=Environment(loader=FileSystemLoader(d.ROOT/'site/preview/templates'),autoescape=select_autoescape(['html']))
        html=env.get_template('_machine_explanation.html').render(record=dict(
            source_label='Kemhan',desk_id='indonesia',summary=reading()['summary_english'],
            model_flagged=False,publisher='id_kemhan',published_date='2026-10-19',
            url=record()['canonical_official_url']))
        self.assertIn('../indonesia.html',html)
        self.assertIn('cited passages translated privately',html)
        self.assertNotIn('No translation was needed',html)
        self.assertNotIn('Philippines Desk',html)

    def test_signed_public_projection_contains_no_original_or_translation(self):
        state=self.process(); env=d.sign_outputs(state,family=FAMILY,policy=policy(),key=KEY)
        text=json.dumps(env)
        for private in ('evidence_translation','evidence_id',record()['body'],record()['title']):
            self.assertNotIn(private,text)
        out=env['packet']['records'][0]
        d.validate_output(out,FAMILY,policy()['sources'][FAMILY])
        self.assertEqual(d.allowed_prompt_versions(FAMILY),(VERSION,))
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='id-relevance-v1+id-analysis-v1'),FAMILY,policy()['sources'][FAMILY])
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='id-relevance-v1+id-analysis-v2'),FAMILY,policy()['sources'][FAMILY])
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='id-relevance-v1+id-analysis-v3'),FAMILY,policy()['sources'][FAMILY])
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='id-relevance-v1+id-analysis-v4'),FAMILY,policy()['sources'][FAMILY])
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='ph-relevance-v1+ph-analysis-v13'),FAMILY,policy()['sources'][FAMILY])

    HISTORICAL='id-relevance-v1+id-analysis-v4'

    def _db_with_link(self, tmp):
        from migrations.versions.m0015_daily_machine_records import up
        from core.regional_official_link_release import SCHEMA_SQL
        from pathlib import Path
        r=record();db=Path(tmp)/'scratch.db'
        with sqlite3.connect(db) as conn:
            conn.executescript(SCHEMA_SQL);up(conn)
            conn.execute('INSERT INTO regional_official_source_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                FAMILY,r['source_identity'],'indonesia',r['canonical_official_url'],
                r['publisher_posted_date'],None,'id_kemhan',None,'c'*40,'a'*64,
                '123-1','official_link_only','d'*64,'2026-10-19T00:00:00Z'))
        return db

    def test_new_output_admission_requires_v5_but_released_v4_remains_valid(self):
        p=policy()[ 'sources'][FAMILY]
        out=d.sign_outputs(self.process(),family=FAMILY,policy=policy(),key=KEY)['packet']['records'][0]
        self.assertEqual(out['prompt_version'],VERSION)
        d.validate_output(out,FAMILY,p)                                  # valid v5 admission
        d.validate_output(out,FAMILY,p,released=True)
        old=dict(out,prompt_version=self.HISTORICAL)
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(old,FAMILY,p)                              # new v4 is refused
        d.validate_output(old,FAMILY,p,released=True)                    # released v4 is readable
        self.assertEqual(d.allowed_prompt_versions(FAMILY),(VERSION,))
        self.assertEqual(d.allowed_prompt_versions(FAMILY,released=True),(VERSION,self.HISTORICAL))
        # The historical allowance is exactly one pair: nothing else widens.
        for version in ('id-relevance-v1+id-analysis-v1','id-relevance-v1+id-analysis-v2',
                        'id-relevance-v1+id-analysis-v3','id-relevance-v1+id-analysis-v6',
                        'ph-relevance-v1+ph-analysis-v12'):
            with self.subTest(version=version), self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
                d.validate_output(dict(out,prompt_version=version),FAMILY,p,released=True)
        # Released validation relaxes nothing else: schema, policy, provenance and
        # output holds still apply to a historical record.
        for change,message in ((dict(policy_sha256='f'*64),'daily_output_schema_or_policy_invalid'),
                               (dict(content_sha256='not-a-hash'),'daily_output_provenance_invalid'),
                               (dict(summary='Too short.'),'daily_output_incomplete'),
                               (dict(model_flagged=True,flag_reason=None),'daily_output_incomplete'),
                               (dict(summary=out['summary'].replace('Kemhan','The ministry')),
                                'daily_indonesia_flag_or_attribution_held')):
            with self.subTest(change=change), self.assertRaisesRegex(d.IntakeHold,message):
                d.validate_output(dict(old,**change),FAMILY,p,released=True)
        excluded=dict(p,excluded_source_identities=[old['source_identity']])
        with self.assertRaisesRegex(d.IntakeHold,'daily_owner_excluded_source_identity'):
            d.validate_output(dict(old,policy_sha256=d.digest(excluded)),FAMILY,excluded,released=True)
        # Source-local QA is untouched: a v4-stamped reading never passes it.
        with self.assertRaisesRegex(d.IntakeHold,'daily_model_provenance_incomplete'):
            d.quality_check(record(),dict(reading(),prompt_version=self.HISTORICAL))

    def test_signed_v4_output_is_held_at_admission_and_never_stored(self):
        import tempfile
        p=policy();state=self.process()
        next(iter(state.values()))['output']['prompt_version']=self.HISTORICAL
        env=d.sign_outputs(state,family=FAMILY,policy=p,key=KEY)
        with tempfile.TemporaryDirectory() as tmp:
            db=self._db_with_link(tmp)
            with sqlite3.connect(db) as conn:
                result=d.admit(conn,env,family=FAMILY,policy=p,key=KEY)
                self.assertEqual(result['admitted'],0)
                self.assertIn('daily_output_incomplete',result['holds'])
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM daily_machine_records').fetchone()[0],0)

    def test_released_historical_record_renders_with_provenance_and_binding_intact(self):
        import tempfile
        import core.daily_machine_records as machine
        p=policy();state=self.process()
        env=d.sign_outputs(state,family=FAMILY,policy=p,key=KEY)
        with tempfile.TemporaryDirectory() as tmp:
            db=self._db_with_link(tmp)
            with sqlite3.connect(db) as conn:
                self.assertEqual(d.admit(conn,env,family=FAMILY,policy=p,key=KEY)['admitted'],1)
                before=dict(zip([c[1] for c in conn.execute('PRAGMA table_info(daily_machine_records)')],
                                conn.execute('SELECT * FROM daily_machine_records').fetchone()))
                # Re-stamp as the already-released record it models, bypassing admission.
                conn.execute('UPDATE daily_machine_records SET prompt_version=?',(self.HISTORICAL,))
            with patch.object(machine,'load_policy',return_value=p):
                rows=machine.load(db)
                self.assertEqual(len(rows),1)
                row=rows[0]
                self.assertEqual(row['prompt_version'],self.HISTORICAL)
                for key in ('summary','content_sha256','capture_sha256','metadata_version_sha256',
                            'quality_sha256','policy_sha256','source_git_commit','source_identity'):
                    self.assertEqual(row[key],before[key],key)
                self.assertEqual((row['desk_id'],row['source_label'],row['machine_only']),('indonesia','Kemhan',True))
                self.assertEqual(len(list(machine.archive_rows(rows))),1)
                # Source binding is still enforced: a changed metadata version withholds it.
                with sqlite3.connect(db) as conn:
                    conn.execute('UPDATE regional_official_source_links SET metadata_version_sha256=?',('9'*64,))
                self.assertEqual(machine.load(db),[])
                with sqlite3.connect(db) as conn:
                    conn.execute('UPDATE regional_official_source_links SET metadata_version_sha256=?',(before['metadata_version_sha256'],))
                self.assertEqual(len(machine.load(db)),1)
                # An unlisted prompt version, or a policy change, is still rejected on read.
                with sqlite3.connect(db) as conn:
                    conn.execute('UPDATE daily_machine_records SET prompt_version=?',('id-relevance-v1+id-analysis-v3',))
                with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
                    machine.load(db)
                with sqlite3.connect(db) as conn:
                    conn.execute('UPDATE daily_machine_records SET prompt_version=?',(self.HISTORICAL,))
                changed=copy.deepcopy(p);changed['sources'][FAMILY]['owner_decision']='changed'
                with patch.object(machine,'load_policy',return_value=changed):
                    with self.assertRaisesRegex(d.IntakeHold,'daily_output_schema_or_policy_invalid'):
                        machine.load(db)


if __name__=='__main__':unittest.main()
