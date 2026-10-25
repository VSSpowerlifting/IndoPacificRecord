"""Offline synthetic PDF faults + actual public bibliographic acceptance fields.

No official PDF copies, body fixtures, online requests or model calls in CI.
Actual hash-pinned private PDF acceptance is a separate local receipt.
"""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pypdf import PageObject
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject, ArrayObject, FloatObject
from processing import vpcp_document as doc
from processing import vpcp_policy
from processing.pdf_text import PdfExtraction
from core.collection.vietnam_sources import VPCP
from core import vietnam_source_use as su
from core import vietnam_corpus_bridge as bridge
from tests.test_vietnam_government_documents import metadata
from tests.test_vietnam_daily_pipeline import clone_schema,PROMOTED,grant
from migrations.versions import m0019_vpcp_article_provenance as migration
NOW='2026-10-23T23:00:00Z'


def widget(text,x=147,y=729,flags=0):
    stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 0 0 Td ('+text+') Tj ET').encode())
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    stream[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    from pypdf.generic import NumberObject
    return DictionaryObject({NameObject('/Subtype'):NameObject('/Widget'),NameObject('/F'):NumberObject(flags),NameObject('/Rect'):ArrayObject([FloatObject(n) for n in [x,y,x+25,y+14]]),NameObject('/AP'):DictionaryObject({NameObject('/N'):stream})})


class HeaderPage(dict):
    mediabox=SimpleNamespace(width=595,height=842)
    def __init__(self,m,split=False):
        super().__init__();self.m=m;self.split=split;self['/Resources']=DictionaryObject()
        self['/Annots']=ArrayObject([widget('545'),widget('22',401),widget('10',456),widget('2026',504)]) if split else []
    def extract_text(self):
        number='/TB -VPCP' if self.split else self.m['document_number']
        stamp='ngày tháng năm' if self.split else 'ngày 22 tháng 10 năm 2026'
        return 'VĂN PHÒNG CHÍNH PHỦ\nSố: '+number+'\nHà Nội, '+stamp+'\nSynthetic test document. '+self.m['signatory']


class Header(unittest.TestCase):
    def test_both_acceptance_headers(self):
        for ident,split in [('220077',False),('220078',True)]:
            m=metadata(ident);r=SimpleNamespace(pages=[HeaderPage(m,split)])
            result=doc.identity_header(r,m)
            self.assertEqual(result['number'],'match')
            self.assertEqual('widget' in result['basis'],split)
    def test_number_conflict_is_held(self):
        m=metadata('220078');page=HeaderPage(m,True);page['/Annots'][0]=widget('546')
        with self.assertRaisesRegex(ValueError,'number_conflict'):doc.identity_header(SimpleNamespace(pages=[page]),m)
    def test_missing_number_is_never_filled_from_portal(self):
        m=metadata('220078');p=HeaderPage(m,True);p['/Annots']=p['/Annots'][1:]
        with self.assertRaisesRegex(ValueError,'number_missing'):doc.identity_header(SimpleNamespace(pages=[p]),m)
    def test_ambiguous_or_hidden_appearances_hold(self):
        m=metadata('220078')
        for annotations in [[widget('545'),widget('545')],[widget('545',flags=2)]]:
            p=HeaderPage(m,True);p['/Annots']=annotations
            with self.assertRaises(ValueError):doc.identity_header(SimpleNamespace(pages=[p]),m)
    def test_normalization_does_not_change_digits(self):
        self.assertEqual(doc.normalized('545 / TB – VPCP'),doc.normalized('545/TB-VPCP'))
        self.assertNotEqual(doc.normalized('546/TB-VPCP'),doc.normalized('545/TB-VPCP'))


class Fidelity(unittest.TestCase):
    def reader(self,m):return SimpleNamespace(pages=[HeaderPage(m)],is_encrypted=False,attachments={})
    def extraction(self,m,**kw):
        text=('Synthetic test document with sufficient text. '*8)+m['signatory']
        args=dict(status='ok',text=text,page_count=1,pages_with_text=1,pages_failed=0,pages=((1,text),));args.update(kw);return PdfExtraction(**args)
    def test_hash_and_version_reprocessing(self):
        m=metadata();r=self.reader(m)
        with patch.object(doc,'PdfReader',return_value=r),patch.object(doc,'extract_pdf_text',return_value=self.extraction(m)):
            a=doc.inspect_pdf(b'%PDF- synthetic 1',m)
            self.assertEqual(a,doc.inspect_pdf(b'%PDF- synthetic 1',m))
            self.assertNotEqual(a['content_sha256'],doc.inspect_pdf(b'%PDF- synthetic 2',m)['content_sha256'])
            with self.assertRaisesRegex(ValueError,'hash_conflict'):doc.inspect_pdf(b'%PDF- synthetic 1',m,expected_sha256='0'*64)
    def test_metadata_revision_changes_version(self):
        m=metadata();new=copy.deepcopy(m);new['subject']+=' '  # exact metadata identity, no invented source claim
        with patch.object(doc,'PdfReader',return_value=self.reader(m)),patch.object(doc,'extract_pdf_text',return_value=self.extraction(m)):
            self.assertNotEqual(doc.inspect_pdf(b'%PDF- fixture',m)['content_sha256'],doc.inspect_pdf(b'%PDF- fixture',new)['content_sha256'])
    def test_missing_failed_or_lost_pages_hold(self):
        m=metadata()
        for extraction in [self.extraction(m,page_count=2),self.extraction(m,pages_failed=1),self.extraction(m,pages=((2,'Synthetic text'),))]:
            with patch.object(doc,'PdfReader',return_value=self.reader(m)),patch.object(doc,'extract_pdf_text',return_value=extraction):
                with self.assertRaises(ValueError):doc.inspect_pdf(b'%PDF- fixture',m)
    def test_malformed_and_encrypted(self):
        with self.assertRaises(ValueError):doc.inspect_pdf(b'HTML challenge',metadata())
        r=self.reader(metadata());r.is_encrypted=True
        with patch.object(doc,'PdfReader',return_value=r):
            with self.assertRaisesRegex(ValueError,'encrypted'):doc.inspect_pdf(b'%PDF- fixture',metadata())


class Policies(unittest.TestCase):
    def test_owner_policy_and_missing_decision_remain_distinct(self):
        p=vpcp_policy.policy()
        self.assertTrue(p['owner_approval'].startswith('DECISION_LOG.md#2026-10-24'))
        self.assertEqual((p['max_documents_per_run'],p['max_input_bytes'],p['max_cost_usd_per_run'],p['max_cost_usd_per_day'],p['max_cost_usd_per_month']),(2,32000,0.5,1,10))
        p.update(owner_approval=None,collect_preserve=False,external_model_transmission=False,public_ipr_analysis=False)
        for k in ['collect_preserve','external_model_transmission','public_ipr_analysis']:
            self.assertFalse(p[k])
            with patch.object(vpcp_policy,'policy',return_value=p):
                with self.assertRaises(ValueError):vpcp_policy.require_permission(k)
        self.assertFalse(su.standing(VPCP).allows('external_model_transmission'))
    def test_collector_policy_precedes_network(self):
        from scripts.collect_vpcp_private_documents import collect
        with patch('scripts.collect_vpcp_private_documents.OriginalsAdapter') as adapter:
            with self.assertRaises(ValueError):collect('absent.db','absent','absent')
            adapter.assert_not_called()
    def test_mps_grant_does_not_authorize_vpcp(self):
        self.assertNotEqual(grant().source_family,VPCP)
        self.assertFalse(su.standing(VPCP).allows('public_ipr_analysis'))
    def test_shared_profile_no_public_queue_or_full_translation(self):
        from processing.screening import private_document_profile
        p=private_document_profile();self.assertFalse(p.daily_queue);self.assertIsNone(p.build_translation_messages)
        message=p.build_analysis_messages('Fixture','[Page 1] Fixture')[0]['content']
        for term in ['responsible','conditional','deadlines','evidence','90 words']:self.assertIn(term,message)
    def test_unauthorized_guard_never_constructs_client(self):
        a=SimpleNamespace()
        with patch.object(vpcp_policy,'require_permission',side_effect=ValueError('policy held')):
            with self.assertRaises(ValueError):vpcp_policy.guard(a,'fixture')
        self.assertFalse(hasattr(a,'_client'))


class Projection(unittest.TestCase):
    def test_page_evidence_and_modalities(self):
        source='Synthetic evidence about a conditional instruction with 2030 stated.'
        sentence='The Government Office said a test action would follow if approved.'
        v={'pages':[(1,source)],'text_original':source}
        second='The Government Office said approval would be conditional.'
        r={'summary_english':sentence+' '+second,'is_significant':False,'document_facts':[{'sentence':sentence,'page':1,'evidence':source,'status':'conditional'},{'sentence':second,'page':1,'evidence':source,'status':'conditional'}]}
        self.assertEqual(doc.output_failures(v,r),[])
        r['document_facts'][0]=dict(r['document_facts'][0],page=2)
        self.assertTrue(doc.output_failures(v,r))
    def test_existing_mps_rows_survive_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=clone_schema(Path(tmp)/'scratch.db');migration.up(c);self.assertTrue(migration.is_already_applied(c));migration.up(c)
            self.assertEqual(c.execute('pragma foreign_key_check').fetchall(),[]);c.close()


if __name__=='__main__':unittest.main()

class SharedBridge(unittest.TestCase):
    def test_private_to_ordinary_corpus_is_gated_and_idempotent(self):
        from core.collection.vietnam_sources import content_sha256
        from processing.government_document_intake import admit
        from core.collection.vietnam_government_documents import digest
        from core import vietnam_daily_handoff as handoff
        from core import vietnam_daily_qa as qa
        from core.vietnam_corpus_bridge import PrivateCustody
        body='The Government Office said a synthetic test instruction applies. The Government Office asked a fictional test agency to report.'
        sentences=['The Government Office instructed the test action.','The Government Office asked the test agency to report.']
        m=metadata();capture='a'*64
        blocks=[['page-1',body]];lead=digest(m)+':'+capture
        sha=content_sha256(doc.HASH_RULE,m['subject'],lead,blocks)
        version={'title_original':m['subject'],'text_original':body,'lead_original':lead,
            'blocks_json':json.dumps(blocks),'content_hash_rule':doc.HASH_RULE,'content_sha256':sha,
            'body_status':'text','pages':[(1,body)],'content_labels':['Energy security'],
            'pdf_sha256':capture,'metadata_sha256':digest(m),
            'bibliographic':{k:m[k] for k in ('document_number','document_type','issuer','signatory','issue_date','official_url')},
            'identity_checks':{'number':'match','date':'match','issuer':'match','basis':'page_text'}}
        record={'source_family':VPCP,'source_identity':'vpcp-vi:220077','canonical_official_url':m['official_url'],
            'publisher_posted_date':m['issue_date'],'content_sha256':sha,'capture_sha256':capture,
            'source_git_commit':'b'*40,'collector_commit':'c'*40}
        reading={'passed_relevance':True,'relevance_score':0.9,'relevance_reasoning':'Synthetic test explanation.',
            'requires_translation':False,'title_english':'Synthetic Government Office instruction',
            'text_english':None,'summary_english':' '.join(sentences),'categories':['policy_document'],
            'is_significant':False,'significance_reasoning':None,'model_id':'synthetic-test-model',
            'prompt_version':'vn-vpcp-document-analysis-v1','document_facts':[
                {'sentence':sentence,'evidence':body,'page':1,'status':'instructed'} for sentence in sentences]}
        p=vpcp_policy.policy();p.update(owner_approval='DECISION_LOG.md#fictional-test',external_model_transmission=True,public_ipr_analysis=True)
        model=SimpleNamespace(analyze_record=lambda title,text,profile:copy.deepcopy(reading))
        permissions={k:k in ('collect_preserve','external_model_transmission','public_ipr_analysis') for k in su.PERMISSIONS}
        approved=grant(VPCP,permissions=permissions)
        with tempfile.TemporaryDirectory() as tmp:
            conn=clone_schema(Path(tmp)/'scratch.db');migration.up(conn)
            admit(conn,[(m,capture)],source_sha='c'*40,run_id='synthetic',observed_utc=NOW);conn.commit()
            args=dict(api=None,as_of_utc=NOW,analyzer=model,ledger_path=Path(tmp)/'ledger.json',
                run_id='synthetic',second_pass=lambda *a:{'ok':True,'reason':'Synthetic test check.'},desk=PROMOTED,custody=PrivateCustody('0'*40,None),now=lambda:NOW)
            packet={'records':[record],'logical_date':'2026-10-23','source_hold':None}
            with patch('core.vietnam_document_custody.prepare',return_value=(packet,{(record['source_identity'],sha):version})),patch('processing.vpcp_policy.policy',return_value=p),patch('processing.vpcp_policy.guard') as guard:
                held=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=su.standing(VPCP),**args)
                self.assertEqual(held['counts'],{qa.HELD_RIGHTS:1});guard.assert_not_called()
                # A rejected model response is retained only in private custody,
                # with a precise reason; it never enters a handoff or paid retry.
                original_facts=copy.deepcopy(reading['document_facts'])
                reading['document_facts'][0]['evidence']='Synthetic missing private evidence span'
                bad_args=dict(args,ledger_path=Path(tmp)/'bad-ledger.json')
                bad=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=approved,**bad_args)
                self.assertEqual(bad['counts'],{qa.HELD_REVIEW:1})
                private=json.loads((Path(tmp)/'bad-ledger.json').read_text())['items'][record['source_identity']]['private_document_review']
                self.assertEqual(private['failures'],['document_page_evidence_invalid'])
                self.assertIn('Synthetic missing private evidence span',json.dumps(private))
                self.assertNotIn('Synthetic missing private evidence span',json.dumps(bad))
                held_envelope=handoff.sign([bad],{VPCP:json.loads((Path(tmp)/'bad-ledger.json').read_text())},key=b'fictional-bridge-key-0000000000000000',run_id='synthetic',generated_utc=NOW)
                self.assertNotIn('Synthetic missing private evidence span',json.dumps(held_envelope))
                settled=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=approved,**bad_args)
                self.assertEqual(settled['counts'],{bridge.SETTLED:1})
                self.assertEqual(guard.call_count,1)
                guard.reset_mock();reading['document_facts']=original_facts
                # Complete a never-run factual review from a retained format draft.
                # Relevance and explanation are not dispatched again.
                from config import ANALYSIS_MODEL
                resume_conn=clone_schema(Path(tmp)/'resume.db');migration.up(resume_conn)
                admit(resume_conn,[(m,capture)],source_sha='c'*40,run_id='synthetic',observed_utc=NOW);resume_conn.commit()
                saved=copy.deepcopy(reading);saved['model_id']=ANALYSIS_MODEL
                resume_path=Path(tmp)/'resume-ledger.json'
                resume_ledger=bridge.load_ledger(resume_path,VPCP)
                resume_ledger['items'][record['source_identity']]={'content_sha256':sha,'outcome':qa.HELD_REVIEW,'failures':['E_ANALYSIS_INCOMPLETE'],'attempts':0,'private_document_review':{'failures':['document_summary_coverage'],'reading':saved}}
                bridge.save_ledger(resume_path,resume_ledger)
                no_regeneration=SimpleNamespace(analyze_record=unittest.mock.Mock(side_effect=AssertionError('paid draft must not be regenerated')))
                first_review=unittest.mock.Mock(return_value={'ok':True,'reason':'Synthetic first factual review.'})
                recovered=bridge.run_family(resume_conn,'unused','b'*40,VPCP,source_use=approved,**dict(args,analyzer=no_regeneration,second_pass=first_review,ledger_path=resume_path))
                self.assertEqual(recovered['counts'],{qa.PUBLISHED:1})
                no_regeneration.analyze_record.assert_not_called();first_review.assert_called_once()
                self.assertTrue(no_regeneration._vpcp_first_qa_continuation)
                resume_conn.close();guard.reset_mock()
                first=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=approved,**args)
                self.assertEqual(first['counts'],{qa.PUBLISHED:1})
                second=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=approved,**args)
                self.assertEqual(second['counts'],{bridge.DUPLICATE:1});self.assertEqual(guard.call_count,1)
                row=conn.execute('select title_original,text_original,text_english from articles').fetchone()
                self.assertEqual(row,(None,None,None))
                ledger=json.loads((Path(tmp)/'ledger.json').read_text())
                # Published projection survives duplicate retry and carries page hashes, no original spans.
                article=ledger['items'][record['source_identity']]['article'];self.assertNotIn('document_facts',article['row'])
                envelope=handoff.sign([first],{VPCP:ledger},key=b'fictional-bridge-key-0000000000000000',run_id='synthetic',generated_utc=NOW)
                self.assertEqual(envelope['families'][0]['source_ref'],'archive/vietnam-vpcp')
                # The ordinary source citation accepts withheld titles without substituting the machine headline.
                import sys
                sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'site/preview'))
                import generate_preview as gp
                citation_record={'id':1,'title_original':None,'source_slug':VPCP,'vietnam':dict(article['provenance'],permissions=approved.snapshot(),qa=json.loads(article['provenance']['qa_json'])),
                    'institution':'Government Office of Vietnam','source_name':'Government Office','published_date':m['issue_date'],'url':m['official_url'],'state':'analyzed'}
                citation=gp.record_citation(citation_record,'Synthetic IPR fixture',{'date':'2026-10-23','expected_records':1})
                self.assertIn('10790/VPCP-CN',citation['source_text'])
                self.assertNotIn('Synthetic Government Office instruction',citation['source_text'])
                import shutil,sqlite3
                rendered_db=Path(tmp)/'render.db'
                shutil.copyfile(Path(__file__).resolve().parents[1]/'pla_watch.db',rendered_db)
                public=sqlite3.connect(rendered_db,isolation_level=None);migration.up(public)
                # Replay the same fixture metadata into this scratch copy only.
                admit(public,[(m,capture)],source_sha='c'*40,run_id='synthetic',observed_utc=NOW)
                outcome,article_id,error=bridge._insert(public,VPCP,record,article['row'],article['provenance'])
                self.assertEqual(outcome,qa.PUBLISHED)
                public.close()
                gp.build(Path(tmp)/'rendered','Synthetic test preview',rendered_db,snapshot=gp.snapshot_from_corpus(rendered_db))
                html=(Path(tmp)/'rendered/record'/('%s.html'%article_id)).read_text()
                self.assertIn('10790/VPCP-CN',html)
                self.assertIn('not an official translation',html)
                self.assertNotIn('id="record-translation"',html)
                self.assertNotIn(version['text_original'],html)

                # Changed immutable bytes hold without overwriting the existing article.
                changed=copy.deepcopy(record);changed['content_sha256']='f'*64
                packet['records']=[changed]
                third=bridge.run_family(conn,'unused','b'*40,VPCP,source_use=approved,**args)
                self.assertEqual(third['counts'],{qa.HELD_SOURCE:1})
            conn.close()

class SpendReservations(unittest.TestCase):
    def test_reservation_precedes_dispatch_and_every_call_stays_bounded(self):
        from config import ANALYSIS_MODEL
        events=[]
        class Client:
            base_url='https://api.anthropic.com'
            def with_options(self,**kw):self.options=kw;return self
        a=SimpleNamespace(_vpcp_document_sha='a'*64,_client=Client(),_call=lambda *a,**kw:events.append('dispatch'))
        self.addCleanup(patch.stopall);patch.object(vpcp_policy,'verify_pricing').start()
        p=vpcp_policy.policy();p.update(owner_approval='DECISION_LOG.md#fixture',external_model_transmission=True,public_ipr_analysis=True)
        with patch.object(vpcp_policy,'policy',return_value=p),patch.object(vpcp_policy,'reserve_cost',side_effect=lambda *a,**kw:events.append('reserve')):
            vpcp_policy.guard(a,'123-1')
            a._call([{'role':'user','content':'Synthetic test'}],model=ANALYSIS_MODEL,max_tokens=1000,task='summary')
            self.assertEqual(events,['reserve','dispatch']);self.assertEqual(a._client.options,{'max_retries':0})
            with self.assertRaises(bridge.BridgeError):a._call([],model='unapproved',max_tokens=1000,task='summary')
        self.assertEqual(events,['reserve','dispatch'])
    def test_checkpoint_failure_prevents_model_call(self):
        from config import ANALYSIS_MODEL
        a=SimpleNamespace(_vpcp_document_sha='a'*64,_client=SimpleNamespace(base_url='https://api.anthropic.com',with_options=lambda **kw:None),_call=unittest.mock.Mock())
        self.addCleanup(patch.stopall);patch.object(vpcp_policy,'verify_pricing').start()
        p=vpcp_policy.policy();p.update(external_model_transmission=True,public_ipr_analysis=True)
        call=a._call
        with patch.object(vpcp_policy,'policy',return_value=p),patch.object(vpcp_policy,'reserve_cost',side_effect=bridge.BridgeError('fixture CAS failure')):
            vpcp_policy.guard(a,'123-1')
            with self.assertRaises(bridge.BridgeError):a._call([],model=ANALYSIS_MODEL,max_tokens=1000,task='summary')
            call.assert_not_called()
    def test_daily_monthly_and_run_limits_are_checked_before_put(self):
        import base64,requests
        from datetime import datetime,timezone
        day=datetime.now(timezone.utc).date().isoformat();p=vpcp_policy.policy()
        for state in [dict(days={day:1},runs={'122-1':1}),dict(days={day[:8]+'01':10},runs={'122-1':10}),dict(days={day:0.5},runs={'123-1':0.5})]:
            body={'schema':'ipr-vpcp-spend/1','documents':{},**state};response=SimpleNamespace(status_code=200,json=lambda:{'sha':'fixture','content':base64.b64encode(json.dumps(body).encode()).decode()})
            session=SimpleNamespace(headers={},get=lambda *a,**kw:response,put=unittest.mock.Mock())
            env={'GITHUB_REPOSITORY':'VSSpowerlifting/ipr-source-evidence-private','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','VIETNAM_VPCP_SPEND_TOKEN':'fictional'}
            with patch.dict('os.environ',env),patch.object(requests,'Session',return_value=session):
                with self.assertRaisesRegex(bridge.BridgeError,'spend_cap'):vpcp_policy.reserve_cost('123-1',0.01,p,document_sha='a'*64,route='relevance:500')
                session.put.assert_not_called()


class ImmutableCustody(unittest.TestCase):
    def test_unseen_permitted_documents_are_not_starved_by_refreshes_or_holds(self):
        import sqlite3
        from scripts import collect_vpcp_private_documents as collector
        from core.collection.vietnam_government_documents import digest,identity
        known=metadata('220078');held=copy.deepcopy(metadata())
        held.update(document_id='909902',subject='Synthetic topical held test document')
        fresh=[]
        for ident in ('909900','909901'):
            m=copy.deepcopy(metadata());m.update(document_id=ident,subject='Synthetic topic-free test document')
            fresh.append(m)
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'private';(repo/'state/documents').mkdir(parents=True)
            old='a'*64
            (repo/'state/documents'/(old+'.json')).write_text(json.dumps({'capture':{'metadata_sha256':digest(known)}}))
            (repo/'state/vpcp-index.json').write_text(json.dumps({'records':{identity(known):old},'checked':{},'holds':{identity(held):'source hold'}}))
            db=Path(tmp)/'metadata.db';c=sqlite3.connect(db)
            c.execute('CREATE TABLE official_document_versions(source_family,metadata_json,first_observed_utc)')
            c.executemany('INSERT INTO official_document_versions VALUES (?,?,?)',[(VPCP,json.dumps(m),NOW) for m in [known,held]+fresh]);c.commit();c.close()
            adapter=unittest.mock.Mock();adapter.fetch.return_value={'body':b'%PDF- synthetic'}
            with patch.dict('os.environ',{'VIETNAM_VPCP_TEXT_ENABLED':'true','VIETNAM_PRIVATE_BRIDGE_KEY':'fictional-fixture-key-0000000000000000','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'b'*40}),patch.object(collector,'private_repo',return_value=repo),patch.object(collector,'OriginalsAdapter',return_value=adapter),patch.object(collector,'preserve',return_value='new') as preserve,patch('processing.government_document_intake.topics',side_effect=lambda m: ['energy'] if m['document_id'] in ('220078','909902') else []):
                result=collector.collect(db,repo,Path(tmp)/'gate')
            self.assertEqual(result['outcomes'],['new','new'])
            self.assertEqual([call.args[1]['document_id'] for call in preserve.call_args_list],['909901','909900'])
            self.assertEqual(adapter.fetch.call_count,2)
    def test_changed_bytes_are_preserved_and_same_version_is_not_reprocessed(self):
        import subprocess,os
        from core import vietnam_document_custody as custody
        m=metadata();key='fictional-test-key-000000000000000000'
        def version(data,meta,**kw):
            sha=hashlib.sha256(data).hexdigest()
            if kw.get('expected_sha256') not in (None,sha):raise ValueError('hash conflict')
            return {'pdf_sha256':sha,'content_sha256':hashlib.sha256(data+json.dumps(meta,sort_keys=True).encode()).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/'private';repo.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init','-b',custody.REF);git('config','user.name','Synthetic test');git('config','user.email','fixture@example.invalid');git('remote','add','origin','https://github.com/'+custody.PRIVATE_REPO+'.git')
            kw=dict(collector_commit='a'*40,source_run='123-1',workflow_sha='b'*40,observed_utc=NOW)
            with patch.dict(os.environ,{'VIETNAM_PRIVATE_BRIDGE_KEY':key}),patch.object(custody,'inspect_pdf',side_effect=version):
                self.assertEqual(custody.preserve(repo,m,b'%PDF- fixture A',**kw),'new')
                self.assertEqual(custody.preserve(repo,m,b'%PDF- fixture A',**kw),'unchanged')
                index_before=json.loads((repo/custody.INDEX).read_text())
                self.assertEqual(custody.preserve(repo,m,b'%PDF- fixture B',**kw),'revised')
                self.assertEqual(len(list((repo/'state/captures').glob('*.bin'))),2)
                index_after=json.loads((repo/custody.INDEX).read_text());self.assertNotEqual(index_before['records'],index_after['records'])
                git('add','state');git('commit','-m','Synthetic private capture')
                commit=git('rev-parse','HEAD')
                receipt={'status':'completed','conclusion':'success','path':'.github/workflows/vietnam_private_first_collector.yml','event':'schedule','repository':{'full_name':custody.PRIVATE_REPO},'head_sha':'b'*40}
                api=SimpleNamespace(get=lambda path:receipt)
                original=custody._git_bytes
                def read(args,root):
                    if args[:2]==['merge-base','--is-ancestor']:return b''
                    return original(args,root)
                with patch.object(custody,'_git_bytes',side_effect=read):
                    packet,versions=custody.prepare(repo,commit,api=api);self.assertEqual(len(packet['records']),1)
                    custody.hold(repo,'vpcp-vi:220077',observed_utc=NOW)
                    self.assertEqual(json.loads((repo/custody.INDEX).read_text())['checked']['vpcp-vi:220077'],NOW)
                    git('add','state');git('commit','-m','Synthetic current-source hold')
                    held_commit=git('rev-parse','HEAD')
                    held_packet,_=custody.prepare(repo,held_commit,api=api)
                    self.assertEqual(held_packet['records'],[])
                    self.assertEqual(len(list((repo/'state/captures').glob('*.bin'))),2)
                    self.assertEqual(custody.preserve(repo,m,b'%PDF- fixture B',**kw),'unchanged')
                    self.assertEqual(json.loads((repo/custody.INDEX).read_text())['holds'],{})

                    receipt['conclusion']='failure'
                    with self.assertRaisesRegex(ValueError,'not_successful'):custody.prepare(repo,commit,api=api)
                    receipt['conclusion']='success'
                    with patch.dict(os.environ,{'VIETNAM_PRIVATE_BRIDGE_KEY':'wrong-fixture-key-000000000000000000'}):
                        with self.assertRaisesRegex(ValueError,'mac_invalid'):custody.prepare(repo,commit,api=api)


class DecisionIsolation(unittest.TestCase):
    def test_malformed_vpcp_decision_holds_only_this_family(self):
        from scripts.run_vietnam_daily_bridge import _policies
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'malformed.json';path.write_text('{invalid')
            result=_policies({VPCP:path},[VPCP],NOW[:10])
            self.assertFalse(result[VPCP].allows('external_model_transmission'))


class OwnerReleaseGuards(unittest.TestCase):
    def test_administrative_decision_needs_individual_confirmation(self):
        m=metadata();m['document_type']='Quyết định'
        with self.assertRaisesRegex(ValueError,'individual_review'):
            doc.inspect_pdf(b'%PDF- synthetic',m)
    def test_missing_checkpoint_or_version_retry_never_dispatches(self):
        import base64,requests
        from datetime import datetime,timezone
        day=datetime.now(timezone.utc).date().isoformat()
        states=[None,{'schema':'ipr-vpcp-spend/1','days':{day:0.01},'runs':{'122-1':0.01},
            'documents':{'a'*64:{'run_id':'122-1','routes':['relevance:500']}}}]
        for state in states:
            response=SimpleNamespace(status_code=404 if state is None else 200,json=lambda:{'sha':'fixture','content':base64.b64encode(json.dumps(state).encode()).decode()})
            session=SimpleNamespace(headers={},get=lambda *a,**kw:response,put=unittest.mock.Mock())
            env={'GITHUB_REPOSITORY':'VSSpowerlifting/ipr-source-evidence-private','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','VIETNAM_VPCP_SPEND_TOKEN':'fictional'}
            with patch.dict('os.environ',env),patch.object(requests,'Session',return_value=session):
                with self.assertRaises(bridge.BridgeError):
                    vpcp_policy.reserve_cost('123-1',0.01,vpcp_policy.policy(),document_sha='a'*64,route='relevance:500')
                session.put.assert_not_called()
    def test_pricing_refusal_fails_before_client_or_reservation(self):
        a=SimpleNamespace()
        with patch.object(vpcp_policy,'verify_pricing',side_effect=bridge.BridgeError('price unavailable')),patch.object(vpcp_policy,'reserve_cost') as reserve:
            with self.assertRaises(bridge.BridgeError):vpcp_policy.guard(a,'123-1')
            reserve.assert_not_called()

    def test_shared_telemetry_counts_only_this_family(self):
        from analysis.usage import UsageLedger
        usage=UsageLedger()
        usage.record_response('summary','claude-sonnet-4-6',SimpleNamespace(input_tokens=10,output_tokens=10,cache_creation_input_tokens=0,cache_read_input_tokens=0))
        analyzer=SimpleNamespace(usage=usage)
        def run(*a,**kw):
            usage.record_response('summary','claude-sonnet-4-6',SimpleNamespace(input_tokens=100,output_tokens=20,cache_creation_input_tokens=0,cache_read_input_tokens=0))
            return {'source_family':VPCP}
        with patch.object(bridge,'_run_family',side_effect=run):
            report=bridge.run_family(analyzer=analyzer)
        self.assertAlmostEqual(report['model_usage']['cost_usd'],0.0006)
        self.assertEqual(report['model_usage']['tasks'][0]['input_tokens'],100)


class EvidenceSupportAndFirstReview(unittest.TestCase):
    def test_administrative_attribution_is_source_specific(self):
        from core import vietnam_daily_qa as qa
        permissions={'public_ipr_analysis':True}
        projection={'title_english':'Government Office administrative instructions'}
        for verb in ('issued','instructs','requests'):
            summary='The Government Office '+verb+' an administrative instruction.'
            result={'summary_english':summary,'categories':['policy_document'],'is_significant':False}
            def check(family):
                return qa.output_failures({'source_family':family},'Synthetic','Synthetic',result,
                    translation_required=False,permissions=permissions,projection=projection)
            self.assertNotIn('E_UNATTRIBUTED',check(VPCP))
            self.assertIn('E_UNATTRIBUTED',check('vn_mps_foreign_affairs_vi'))
        result['summary_english']='The instruction requires administrative action.'
        self.assertIn('E_UNATTRIBUTED',check(VPCP))
    def test_private_notes_may_be_longer_than_the_bounded_public_summary(self):
        from config import ANALYSIS_MODEL
        evidence='Synthetic conditional source material about a fictional test and approval.'
        summary='The Government Office said action would follow if approved.'
        facts=[{'sentence':'The Government Office said the proposed fictional action would remain conditional until a test authority had reviewed the supporting paperwork.','page':1,'evidence':evidence,'status':'conditional'},
               {'sentence':'The Government Office said approval would depend on a separate test review, with no claim that any action had already taken place.','page':1,'evidence':evidence,'status':'conditional'}]
        reading={'summary_english':summary,'document_facts':facts,'is_significant':False,'title_english':'Synthetic conditional Government Office notice','model_id':ANALYSIS_MODEL,'prompt_version':'fixture','relevance_score':0.85}
        version={'pages':[(1,evidence)],'text_original':evidence,'bibliographic':{'document_type':'Công văn'}}
        self.assertEqual(doc.output_failures(version,reading),[])
        facts[0]['sentence']+=' The Government Office referred to 2026.'
        version['pages']=[(1,evidence+' 2026')]
        self.assertEqual(doc.output_failures(version,reading),[])
        facts[0]['sentence']+=' The Government Office referred to 9999.'
        self.assertEqual(doc.output_failures(version,reading),['document_numeric_evidence_mismatch'])
        facts[0]['sentence']=facts[0]['sentence'].split(' The Government Office referred to 9999.')[0]
        item={'outcome':'held_review','private_document_review':{'failures':['document_summary_coverage'],'reading':reading}}
        draft=doc.retained_format_draft(item,version)
        self.assertEqual(draft['summary_english'],summary)
        reading['summary_english']='word '*91
        self.assertIsNone(doc.retained_format_draft(item,version))
        reading['summary_english']=summary;item['private_document_review']['failures']=['document_page_evidence_invalid']
        self.assertIsNone(doc.retained_format_draft(item,version))
    def test_only_a_never_executed_factual_review_can_continue(self):
        import base64,requests
        from datetime import datetime,timezone
        day=datetime.now(timezone.utc).date().isoformat()
        state={'schema':'ipr-vpcp-spend/1','days':{day:0.01},'runs':{'122-1':0.01},'documents':{'a'*64:{'run_id':'122-1','routes':['relevance:500','summary:1000']}}}
        puts=[]
        def get(*a,**kw):return SimpleNamespace(status_code=200,json=lambda:{'sha':'fixture','content':base64.b64encode(json.dumps(state).encode()).decode()})
        def put(*a,**kw):
            puts.append(kw['json']);state.clear();state.update(json.loads(base64.b64decode(kw['json']['content'])))
            return SimpleNamespace(status_code=200)
        session=SimpleNamespace(headers={},get=get,put=put)
        env={'GITHUB_REPOSITORY':'VSSpowerlifting/ipr-source-evidence-private','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','VIETNAM_VPCP_SPEND_TOKEN':'fictional'}
        with patch.dict('os.environ',env),patch.object(requests,'Session',return_value=session):
            p=vpcp_policy.policy()
            with self.assertRaises(bridge.BridgeError):vpcp_policy.reserve_cost('123-1',0.01,p,document_sha='a'*64,route='summary:1000',allow_first_qa=True)
            vpcp_policy.reserve_cost('123-1',0.01,p,document_sha='a'*64,route='summary:300',allow_first_qa=True,generation_run_id='122-1')
            self.assertEqual(state['documents']['a'*64]['qa_run_id'],'123-1')
            with self.assertRaises(bridge.BridgeError):vpcp_policy.reserve_cost('123-1',0.01,p,document_sha='a'*64,route='summary:300',allow_first_qa=True,generation_run_id='122-1')
            self.assertEqual(len(puts),1)
            self.assertAlmostEqual(state['runs']['123-1'],0.01)
    def test_oversize_complete_request_is_held_before_reservation(self):
        from config import ANALYSIS_MODEL
        client=SimpleNamespace(base_url='https://api.anthropic.com',with_options=lambda **kw:None)
        a=SimpleNamespace(_client=client,_call=unittest.mock.Mock(),_vpcp_document_sha='a'*64)
        original=a._call
        with patch.object(vpcp_policy,'verify_pricing'),patch.object(vpcp_policy,'reserve_cost') as reserve:
            vpcp_policy.guard(a,'123-1')
            with self.assertRaisesRegex(bridge.BridgeError,'complete_model_input_limit'):
                a._call([{'role':'user','content':'x'*32001}],model=ANALYSIS_MODEL,max_tokens=1000,task='summary')
            reserve.assert_not_called();original.assert_not_called()
