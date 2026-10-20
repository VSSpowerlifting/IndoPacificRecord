"""Fictional private Git/API/MAC contracts. No live approval or network."""
import base64
import copy
import hashlib
import hmac
import json
import unittest
from datetime import date
from pathlib import Path

from core import vietnam_official_link_admission as vn
from scripts import vietnam_ministry_remote as remote
from scripts.attest_vietnam_run_state import sha_blob
from tests import test_vietnam_ministry_remote_review as fixture
from tests.test_vietnam_official_link_admission import KEY, NOW, db, sealed, seal_review

BRIDGE = b'fictional-private-bridge-key-independent-00000'
WORKFLOW_SHA = 'b' * 40


class API:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        return copy.deepcopy(self.routes[path])


class PrivateCustody(unittest.TestCase):
    def setUp(self):
        self.f = fixture.RemoteReview(); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repos / fixture.MPS
        self.collect('100-1', one=True)
        self.legacy = self.f.commit_state()
        self.collect('101-1')
        self.receipt = {'schema': vn.ATTEMPT_SCHEMA, 'source_family': fixture.MPS,
            'run_attempt': '101-1', 'workflow_commit': WORKFLOW_SHA,
            'collector_commit': fixture.COMMIT, 'public_frozen_tip': self.legacy,
            'event': 'workflow_dispatch', 'health': 'ok',
            'state_sha256': hashlib.sha256((self.repo/'state/shadow.db').read_bytes()).hexdigest(),
            'public_release_authorized': False}
        (self.repo/'private_attempts').mkdir()
        (self.repo/'private_attempts/101-1.json').write_text(json.dumps(self.receipt))
        fixture.git(self.repo, 'add', 'state', 'private_attempts')
        fixture.git(self.repo, 'commit', '-m', 'private-vietnam: preserve '+fixture.MPS+' attempt 101-1')
        self.tip = fixture.git(self.repo, 'rev-parse', 'HEAD')
        fixture.git(self.repo, 'branch', vn.PRIVATE_REF)
        self.packet = vn.prepare(self.repo, self.tip, fixture.MPS, private=True)
        latest=next((self.repo/'state/ledger').glob('*-101-1.json'))
        latest=json.loads(latest.read_text())
        self.decision = sealed(self.packet)
        self.public_api = API({
            vn.PREFIX+'/git/ref/heads/'+vn.SOURCES[fixture.MPS].state_branch:
                {'ref':'refs/heads/'+vn.SOURCES[fixture.MPS].state_branch,'object':{'sha':self.legacy}},
            vn.PREFIX+'/actions/runs/100/attempts/1':
                {'id':100,'run_attempt':1,'path':'.github/workflows/vietnam_ministry_shadow.yml',
                 'head_sha':fixture.COMMIT,'event':'workflow_dispatch','status':'completed','conclusion':'success'}})
        raw=json.dumps(self.receipt).encode()
        self.receipt_path=vn.PRIVATE_PREFIX+'/contents/private_attempts/101-1.json?ref='+self.tip
        self.run_path=vn.PRIVATE_PREFIX+'/actions/runs/101/attempts/1'
        self.api=API({self.receipt_path:{'encoding':'base64','content':base64.b64encode(raw).decode(),'sha':sha_blob(raw)},
            self.run_path:{'id':101,'run_attempt':1,'repository':{'full_name':vn.PRIVATE_REPO},
                'head_branch':'main','path':vn.PRIVATE_WORKFLOW,'head_sha':WORKFLOW_SHA,
                'event':'workflow_dispatch','status':'completed','conclusion':'success'},
            self.run_path+'/jobs?per_page=100':{'total_count':1,'jobs':[{'steps':[
                {'name':'Persist and independently verify private state','conclusion':'success'}]}]},
            vn.PRIVATE_PREFIX+'/git/ref/heads/'+vn.PRIVATE_REF:
                {'ref':'refs/heads/'+vn.PRIVATE_REF,'object':{'sha':self.tip}}})
        self.api.routes[self.run_path].update(run_started_at=latest['started_utc'],updated_at=latest['finished_utc'])
        self.cx=db();self.addCleanup(self.cx.close)

    def collect(self,rid,one=False):
        if not one:
            return self.f.collector(self.repo/'state',fixture.MPS,date(2026,10,5),0,2,rid,fixture.COMMIT)
        # Derived fictional feed: one existing original arrives only in the
        # private attempt. No invented original-language source text.
        import xml.etree.ElementTree as ET
        from tests.test_vn_ministry_adapters import adapter,response,URLS,FakeResponse,FIX
        rss=ET.fromstring((FIX/'mps-rss-34.bin').read_bytes())
        channel=rss.find('channel')
        for item in list(channel.findall('item')):
            if item.findtext('link') == URLS[fixture.BODIES[fixture.MPS][1]]:
                channel.remove(item)
        listing=FakeResponse(200,ET.tostring(rss),{'Content-Type':'application/xml'})
        return fixture.collect(self.repo/'state',fixture.MPS,date(2026,10,5),0,2,rid,fixture.COMMIT,
            adapter=adapter(fixture.MPS,[response(fixture.BODIES[fixture.MPS][0])],listing=listing))

    def sign(self):
        return vn.sign_private_projection(self.repo,self.tip,self.legacy,self.decision,
            api=self.api,public_api=self.public_api,bridge_key=BRIDGE,review_key=KEY,
            as_of_utc=NOW,validator_commit=fixture.git(remote.REPO,'rev-parse','HEAD'))

    def admit(self, signed):
        return vn.admit_private_projection(self.cx,signed,self.decision,
            bridge_key=BRIDGE,secret=KEY,api=self.public_api,private_api=self.api,
            as_of_utc=NOW,public_checkout=remote.REPO)

    def resign(self,signed):
        signed['hmac_sha256']=hmac.new(BRIDGE,vn.PRIVATE_DOMAIN+vn._canonical(signed['projection']),hashlib.sha256).hexdigest()

    def test_real_git_replay_and_distinct_private_workflow_identity(self):
        self.assertEqual({r['version_first_seen_run'] for r in self.packet['records']},{'100-1','101-1'})
        signed=self.sign()
        self.assertEqual(signed['projection']['proof']['private_attempts_verified'],1)
        self.assertNotIn('title_original',json.dumps(signed))
        self.api.calls.clear();self.public_api.calls.clear()
        self.admit(signed);self.admit(signed)
        self.assertEqual(self.cx.execute('select count(*) from regional_official_source_links').fetchone()[0],2)
        self.assertTrue(all('/contents/' not in p for p in self.api.calls))
        self.assertFalse(any('captures' in p or 'shadow.db' in p for p in self.api.calls))

    def test_only_human_selected_metadata_is_exported(self):
        decision=self.decision['review'];decision['approved_source_identities']=decision['approved_source_identities'][:1]
        self.decision=seal_review(decision)
        signed=self.sign()
        self.assertEqual(len(signed['projection']['packet']['records']),1)
        self.admit(signed)
        self.assertEqual(self.cx.execute('select count(*) from regional_official_source_links').fetchone()[0],1)

    def test_private_attempt_layout_is_opt_in_and_source_bound_before_collection(self):
        with self.assertRaisesRegex(ValueError,'unrelated'):
            remote.prepare(self.f.repos,self.f.gate)
        remote.prepare(self.f.repos,self.f.gate,private=True)
        path=self.repo/'private_attempts/101-1.json'
        item=json.loads(path.read_text());item['source_family']=fixture.ENERGY
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(ValueError,'source mismatch'):
            remote.prepare(self.f.repos,self.f.gate,private=True)

    def test_private_archive_reuses_the_unsigned_editorial_queue_and_feeder(self):
        from scripts import prepare_vietnam_mps_review_queue as queue
        from scripts.prepare_vietnam_briefs_evidence import verified_queue
        out=self.f.root/'private-editorial-queue'
        queue.prepare(self.repo,self.tip,out,private=True)
        packet=json.loads((out/'review_queue.json').read_text())
        self.assertEqual(packet['state_branch'],vn.PRIVATE_REF)
        self.assertEqual(len(verified_queue(packet)),2)
        self.assertEqual(packet['human_approvals'],0)
        self.assertEqual(packet['rights_approvals'],0)

    def test_private_attempt_repository_workflow_code_event_and_persistence_are_independent(self):
        original=copy.deepcopy(self.api.routes)
        for field,value in [('repository',{'full_name':'VSSpowerlifting/IndoPacificRecord'}),
                ('head_sha',fixture.COMMIT),('path','.github/workflows/vietnam_ministry_shadow.yml'),
                ('event','schedule'),('run_attempt',2),('status','in_progress'),
                ('run_started_at','2999-01-01T00:00:00Z')]:
            with self.subTest(field=field):
                self.api.routes=copy.deepcopy(original);self.api.routes[self.run_path][field]=value
                with self.assertRaises(ValueError):self.sign()
        self.api.routes=copy.deepcopy(original)
        self.api.routes[self.run_path+'/jobs?per_page=100']['jobs'][0]['steps'][0]['conclusion']='failure'
        with self.assertRaisesRegex(ValueError,'persisted'):self.sign()

    def test_failure_before_ledger_cannot_make_an_old_healthy_attempt_current(self):
        receipt={**self.receipt,'run_attempt':'102-1','health':'fail_before_ledger'}
        (self.repo/'private_attempts/102-1.json').write_text(json.dumps(receipt))
        fixture.git(self.repo,'add','private_attempts')
        fixture.git(self.repo,'commit','-m','private-vietnam: preserve '+fixture.MPS+' attempt 102-1')
        tip=fixture.git(self.repo,'rev-parse','HEAD')
        fixture.git(self.repo,'update-ref','refs/heads/'+vn.PRIVATE_REF,tip)
        packet=vn.prepare(self.repo,tip,fixture.MPS,private=True)
        with self.assertRaisesRegex(ValueError,'no_healthy_ledger'):
            vn.authenticate_private(packet,self.repo,self.legacy,api=self.api,public_api=self.public_api)

    def test_private_ref_drift_and_legacy_ref_drift_hold_without_public_fallback(self):
        signed=self.sign()
        self.api.routes[vn.PRIVATE_PREFIX+'/git/ref/heads/'+vn.PRIVATE_REF]['object']['sha']='f'*40
        with self.assertRaisesRegex(ValueError,'concurrently'):self.admit(signed)
        self.api.routes[vn.PRIVATE_PREFIX+'/git/ref/heads/'+vn.PRIVATE_REF]['object']['sha']=self.tip
        self.public_api.routes[vn.PREFIX+'/git/ref/heads/'+vn.SOURCES[fixture.MPS].state_branch]['object']['sha']='f'*40
        with self.assertRaisesRegex(ValueError,'writer_changed'):self.admit(signed)
        self.assertEqual(self.cx.execute('select count(*) from regional_official_source_links').fetchone()[0],0)

    def test_original_fields_even_with_valid_bridge_mac_are_refused(self):
        for field in ('title_original','text_original','captured_html','model_text'):
            with self.subTest(field=field):
                signed=self.sign();signed['projection']['packet']['records'][0][field]='fictional forbidden bytes'
                self.resign(signed)
                with self.assertRaisesRegex(ValueError,'fields'):self.admit(signed)

    def test_bridge_mac_cannot_replace_independent_human_review_or_custody(self):
        signed=self.sign();signed['hmac_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'mac'):self.admit(signed)
        signed=self.sign()
        for field in ('protected_custody_verified','original_language_and_source_version_checked','production_release_authorized'):
            with self.subTest(field=field):
                changed=copy.deepcopy(self.decision['review']);changed[field]=False
                old=self.decision;self.decision=seal_review(changed)
                with self.assertRaises(ValueError):self.admit(signed)
                self.decision=old
        with self.assertRaisesRegex(ValueError,'independent'):
            vn.sign_private_projection(self.repo,self.tip,self.legacy,self.decision,
                api=self.api,public_api=self.public_api,bridge_key=KEY,review_key=KEY,
                as_of_utc=NOW,validator_commit='a'*40)

    def test_private_projection_uses_existing_atomic_publisher_and_failure_cleanup(self):
        import shutil
        from unittest.mock import patch
        from scripts import admit_vietnam_official_links as publisher
        signed=self.sign(); target=self.f.root/'disposable-production.db'
        shutil.copyfile(publisher.ROOT/'pla_watch.db',target)
        before=target.read_bytes()
        options=dict(api=self.public_api,secret=KEY,as_of_utc=NOW,
            expected_db_sha256=publisher.sha(target),private_projection=signed,
            bridge_key=BRIDGE,private_api=self.api)
        with patch.object(publisher,'read_live_links',side_effect=ValueError('independent readback failed')):
            with self.assertRaises(ValueError):publisher.admit_atomic(target,None,None,self.decision,**options)
        self.assertEqual(target.read_bytes(),before)
        self.assertEqual(list(target.parent.glob('.vietnam-admission-*')),[])
        publisher.admit_atomic(target,None,None,self.decision,**options)


class PrivateWorkflowBoundary(unittest.TestCase):
    def test_public_release_receives_only_reviewed_metadata_and_keeps_all_release_gates(self):
        text=(Path(remote.REPO)/'.github/workflows/vietnam_ministry_shadow.yml').read_text()
        self.assertIn('  shadow:\n    if: false',text)
        self.assertNotIn('  schedule:',text)
        release=text.split('  reviewed-release:',1)[1]
        self.assertNotIn('git clone',release)
        self.assertNotIn('vn-release-source',release)
        for required in ('vars.VIETNAM_MPS_RELEASE_ENABLED', 'VIETNAM_LINK_REVIEW_KEY',
            'VIETNAM_PRIVATE_BRIDGE_KEY','VIETNAM_PRIVATE_PROVENANCE_TOKEN','--private-projection',
            'verify_private_projection_head','group: daily-update','scripts/validate_output.py',
            'refs/heads/main','refs/heads/gh-pages','--vietnam-https'):
            self.assertIn(required,release)
