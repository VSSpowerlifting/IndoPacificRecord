"""VPCP evidence in the existing private Git vault; no second corpus database."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from core.collection.vietnam_government_documents import FAMILY, digest, identity
from processing.vpcp_document import inspect_pdf
from scripts.review_shadow_state import _git_bytes, verify_state_commit

REF='archive/vietnam-vpcp'
PRIVATE_REPO='VSSpowerlifting/ipr-source-evidence-private'
INDEX='state/vpcp-index.json'
ROOT=Path(__file__).resolve().parents[1]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def private_repo(repo):
    repo=Path(repo).resolve()
    require(repo!=ROOT and ROOT not in repo.parents,'vpcp_originals_public_checkout_refused')
    remote=_git_bytes(['remote','get-url','origin'],repo).decode().strip().removesuffix('.git')
    require(remote in ('https://github.com/'+PRIVATE_REPO,'git@github.com:'+PRIVATE_REPO),
            'vpcp_private_custody_mismatch')
    return repo


def _immutable(path,data):
    require(not any(p.is_symlink() for p in path.parents),'vpcp_custody_symlink')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    require(not path.is_symlink(),'vpcp_custody_symlink')
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:
        require(path.read_bytes()==data,'vpcp_immutable_version_conflict')
    else:
        with os.fdopen(fd,'wb') as out:out.write(data)


def preserve(repo,metadata,data,*,collector_commit,source_run,workflow_sha,observed_utc):
    """Private collector only; policy checked by its CLI before any network."""
    repo=private_repo(repo)
    require(_git_bytes(['branch','--show-current'],repo).decode().strip()==REF,
            'vpcp_private_archive_branch_required')
    require(re.fullmatch('[a-f0-9]{40}',collector_commit) and
            re.fullmatch('[a-f0-9]{40}',workflow_sha) and
            re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*',source_run),'vpcp_capture_provenance_invalid')
    v=inspect_pdf(data,metadata)
    capture={'schema':'ipr-vpcp-private-capture/1','metadata':metadata,
        'pdf_sha256':v['pdf_sha256'],'content_sha256':v['content_sha256'],
        'metadata_sha256':digest(metadata),'collector_commit':collector_commit,
        'source_run':source_run,'workflow_sha':workflow_sha,'observed_utc':observed_utc}
    key=os.environ.get('VIETNAM_PRIVATE_BRIDGE_KEY','').encode()
    require(len(key)>=32,'vpcp_capture_key_required')
    payload=json.dumps(capture,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    sealed={'capture':capture,'mac':hmac.new(key,b'IPR-VPCP-CAPTURE-v1\n'+payload,hashlib.sha256).hexdigest()}
    raw=json.dumps(sealed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    sha=hashlib.sha256(raw).hexdigest()
    _immutable(repo/'state/captures'/(v['pdf_sha256']+'.bin'),data)
    _immutable(repo/'state/documents'/(sha+'.json'),raw)
    path=repo/INDEX
    require(not path.is_symlink(),'vpcp_custody_symlink')
    index=json.loads(path.read_text()) if path.exists() else {'schema':'ipr-vpcp-private-index/1','records':{},'checked':{}}
    index.setdefault('checked',{})[identity(metadata)]=observed_utc
    previous=index['records'].get(identity(metadata))
    # Identical source versions reuse the capture/run pin, avoiding needless work.
    if previous:
        prior=json.loads((repo/'state/documents'/(previous+'.json')).read_text())['capture']
        if prior['metadata_sha256']==capture['metadata_sha256'] and prior['pdf_sha256']==capture['pdf_sha256']:
            # Refresh authentication after a failed prior Action without changing content identity.
            index['records'][identity(metadata)]=sha
            tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(index,sort_keys=True));os.chmod(tmp,0o600);tmp.replace(path)
            return 'unchanged'
    index['records'][identity(metadata)]=sha
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(index,sort_keys=True));os.chmod(tmp,0o600);tmp.replace(path)
    return 'new' if previous is None else 'revised'


def prepare(repo,commit,*,api):
    """Replay pinned bytes, metadata, all pages and successful private Action."""
    repo=private_repo(repo)
    verify_state_commit(repo,commit,REF)
    index=json.loads(_git_bytes(['show',commit+':'+INDEX],repo))
    require(set(index)=={'schema','records','checked'} and index['schema']=='ipr-vpcp-private-index/1'
            and isinstance(index['records'],dict) and len(index['records'])<=1000,'vpcp_index_invalid')
    records=[];versions={};runs={}
    for ident,capture_sha in sorted(index['records'].items()):
        require(re.fullmatch('[a-f0-9]{64}',str(capture_sha)),'vpcp_capture_pin_invalid')
        raw=_git_bytes(['show',commit+':state/documents/'+capture_sha+'.json'],repo)
        require(len(raw)<=32000 and hashlib.sha256(raw).hexdigest()==capture_sha,'vpcp_capture_hash_invalid')
        sealed=json.loads(raw);key=os.environ.get('VIETNAM_PRIVATE_BRIDGE_KEY','').encode()
        require(set(sealed)=={'capture','mac'} and len(key)>=32,'vpcp_capture_key_required')
        cap=sealed['capture'];payload=json.dumps(cap,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        require(hmac.compare_digest(sealed['mac'],hmac.new(key,b'IPR-VPCP-CAPTURE-v1\n'+payload,hashlib.sha256).hexdigest()),'vpcp_capture_mac_invalid')
        m=cap['metadata'];sha=cap['pdf_sha256']
        require(re.fullmatch('[a-f0-9]{64}',str(sha)) and identity(m)==ident
                and cap['schema']=='ipr-vpcp-private-capture/1' and cap['metadata_sha256']==digest(m),
                'vpcp_capture_identity_invalid')
        require(m['issue_date']<=cap['observed_utc'][:10],'vpcp_future_document')
        data=_git_bytes(['show',commit+':state/captures/'+sha+'.bin'],repo)
        v=inspect_pdf(data,m,expected_sha256=sha)
        require(v['content_sha256']==cap['content_sha256'],'vpcp_extraction_version_changed')
        run,attempt=cap['source_run'].split('-')
        if (run,attempt) not in runs:
            receipt=api.get('/repos/'+PRIVATE_REPO+'/actions/runs/'+run+'/attempts/'+attempt)
            require(receipt.get('status')=='completed' and receipt.get('conclusion')=='success'
                and receipt.get('path')=='.github/workflows/vietnam_private_first_collector.yml'
                and receipt.get('event') in ('schedule','workflow_dispatch')
                and (receipt.get('repository') or {}).get('full_name')==PRIVATE_REPO,
                'vpcp_private_action_not_successful')
            runs[(run,attempt)]=receipt
        require(runs[(run,attempt)].get('head_sha')==cap['workflow_sha'],'vpcp_private_action_pin_mismatch')
        collector=cap['collector_commit']
        require(re.fullmatch('[a-f0-9]{40}',str(collector)),'vpcp_collector_pin_invalid')
        # The processor may replay only reviewed collector code in its history.
        _git_bytes(['merge-base','--is-ancestor',collector,'HEAD'],ROOT)
        r={'source_family':FAMILY,'source_identity':ident,'canonical_official_url':m['official_url'],
            'publisher_posted_date':m['issue_date'],'content_sha256':v['content_sha256'],
            'capture_sha256':sha,'source_git_commit':commit,'collector_commit':collector}
        records.append(r);versions[(ident,v['content_sha256'])]=v
    return ({'records':records,'logical_date':max((json.loads(_git_bytes(['show',commit+':state/documents/'+h+'.json'],repo))["capture"]['observed_utc'][:10] for h in index['records'].values()),default='1970-01-01'),
             'source_hold':None},versions)
