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


def record():
    # Explicitly synthetic Indonesian text, never represented as publisher text.
    body = 'Latihan direncanakan akan berlangsung pada 23 Oktober. Pertemuan membahas rencana latihan bersama.'
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
        out = dict(summary=reply['summary_english'], flag=False, flag_reason=None,
            flag_evidence_id=None, categories=['exercises'], facts=[
                dict(sentence=f['sentence'], evidence_id='P1',
                     evidence_translation='An exercise is planned for 23 Oktober. The meeting discusses joint exercise plans.')
                for f in reply['facts']])
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

    def test_unapproved_rights_never_construct_model(self):
        factory = Mock(side_effect=AssertionError('unauthorized model'))
        state,_=d.process([record()],{},family=FAMILY,policy=d.load_policy(),analyzer_factory=factory)
        self.assertEqual(next(iter(state.values()))['reason'],'model_rights_held')
        factory.assert_not_called()
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_rights_held'):
            d.sign_outputs(state,family=FAMILY,policy=d.load_policy(),key=KEY)

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
        reply=reading();reply['facts'][0]['evidence']=r['body'].split('. ')[0]+'.'
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
                    d.admit(conn,env,family=FAMILY,policy=d.load_policy(),key=KEY)
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
        with self.assertRaisesRegex(d.IntakeHold,'daily_output_incomplete'):
            d.validate_output(dict(out,prompt_version='ph-relevance-v1+ph-analysis-v13'),FAMILY,policy()['sources'][FAMILY])


if __name__=='__main__':unittest.main()
