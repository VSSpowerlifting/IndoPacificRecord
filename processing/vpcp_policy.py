"""Source-specific gates and durable worst-case reservations on the shared client."""
import json
import math
from pathlib import Path
from core.collection.vietnam_sources import VPCP
PATH=Path(__file__).resolve().parents[1]/'config/vietnam_vpcp_text_policy.json'


def policy():
    p=json.loads(PATH.read_text())
    if (set(p)!={'source_family','owner_approval','collect_preserve','external_model_transmission',
            'public_ipr_analysis','max_documents_per_run','max_input_bytes','max_cost_usd_per_run',
            'max_cost_usd_per_day','max_cost_usd_per_month'} or p['source_family']!=VPCP
        or any(type(p[k]) is not bool for k in ('collect_preserve','external_model_transmission','public_ipr_analysis'))
        or type(p['max_documents_per_run']) is not int or not 1<=p['max_documents_per_run']<=2
        or type(p['max_input_bytes']) is not int or not 100<=p['max_input_bytes']<=32000
        or any(type(p[k]) not in (int,float) or not math.isfinite(p[k]) or p[k]<=0 for k in
            ('max_cost_usd_per_run','max_cost_usd_per_day','max_cost_usd_per_month'))
        or p['max_cost_usd_per_run']>0.50 or p['max_cost_usd_per_day']>1 or p['max_cost_usd_per_month']>10):
        raise ValueError('vpcp_policy_invalid')
    if any(p[k] for k in ('collect_preserve','external_model_transmission','public_ipr_analysis')) and not (
            isinstance(p['owner_approval'],str) and p['owner_approval'].startswith('DECISION_LOG.md#')):
        raise ValueError('vpcp_owner_approval_missing')
    return p


def require_permission(name):
    p=policy()
    if not p.get(name):raise ValueError('vpcp_'+name+'_held')
    return p


def reserve_cost(run_id,cost,p):
    """Durable CAS reservation in the EXISTING private source archive branch.

    Reserve before dispatch, never refund failed/aborted calls. No retry on a
    CAS conflict. Queue/handoff state stays on its existing daily branch.
    """
    import os,base64,requests
    from datetime import datetime,timezone
    from core.vietnam_document_custody import PRIVATE_REPO,REF
    from core.vietnam_corpus_bridge import BridgeError
    if (os.environ.get('GITHUB_REPOSITORY')!=PRIVATE_REPO
        or run_id!=os.environ.get('GITHUB_RUN_ID','')+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','')):
        raise BridgeError('vpcp_private_spend_context_required')
    token=os.environ.get('VIETNAM_VPCP_SPEND_TOKEN','')
    if not token:raise BridgeError('vpcp_spend_checkpoint_token_required')
    endpoint='https://api.github.com/repos/'+PRIVATE_REPO+'/contents/state/vpcp-spend.json'
    session=requests.Session();session.trust_env=False
    session.headers.update({'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
        'User-Agent':'IndoPacificRecord-private-Daily-spend/1'})
    response=session.get(endpoint,params={'ref':REF},timeout=20,allow_redirects=False)
    if response.status_code==404:
        sha=None;state={'schema':'ipr-vpcp-spend/1','days':{},'runs':{}}
    elif response.status_code==200:
        obj=response.json();sha=obj['sha'];state=json.loads(base64.b64decode(obj['content']))
    else:raise BridgeError('vpcp_spend_checkpoint_unavailable')
    if (set(state)!={'schema','days','runs'} or state['schema']!='ipr-vpcp-spend/1'
        or any(not isinstance(v,dict) or any(type(n) not in (int,float) or not math.isfinite(n) or n<0 for n in v.values()) for v in (state['days'],state['runs']))):
        raise BridgeError('vpcp_spend_checkpoint_invalid')
    day=datetime.now(timezone.utc).date().isoformat()
    today=state['days'].get(day,0);month=sum(v for k,v in state['days'].items() if k.startswith(day[:7]));run=state['runs'].get(run_id,0)
    if cost+run>p['max_cost_usd_per_run'] or cost+today>p['max_cost_usd_per_day'] or cost+month>p['max_cost_usd_per_month']:
        raise BridgeError('vpcp_spend_cap')
    state['days'][day]=today+cost;state['runs'][run_id]=run+cost
    payload={'message':'Daily: reserve bounded VPCP processing cost','branch':REF,
        'content':base64.b64encode(json.dumps(state,sort_keys=True).encode()).decode()}
    if sha:payload['sha']=sha
    result=session.put(endpoint,json=payload,timeout=20,allow_redirects=False)
    if result.status_code not in (200,201):raise BridgeError('vpcp_spend_checkpoint_conflict')


def guard(analyzer,run_id):
    from core.vietnam_corpus_bridge import BridgeError
    from analysis.pricing import estimate_usage_cost_usd
    from config import RELEVANCE_MODEL,ANALYSIS_MODEL,RELEVANCE_TOOL_OUTPUT_ENABLED
    p=require_permission('external_model_transmission')
    require_permission('public_ipr_analysis')
    if RELEVANCE_TOOL_OUTPUT_ENABLED:raise BridgeError('vpcp_tool_route_not_authorized')
    call=analyzer._call;calls=0
    def bounded(messages,*,model=None,max_tokens=1000,task=None,**kwargs):
        nonlocal calls
        actual=model or ANALYSIS_MODEL
        if (task,actual,max_tokens) not in (('relevance',RELEVANCE_MODEL,500),('summary',ANALYSIS_MODEL,1000),('summary',ANALYSIS_MODEL,300)) or calls>=6:
            raise BridgeError('vpcp_model_route_bound')
        size=len(json.dumps([messages,kwargs],ensure_ascii=False).encode())+2048
        cost=estimate_usage_cost_usd(actual,0,max_tokens,size,0)
        if cost is None:raise BridgeError('vpcp_model_price_unknown')
        reserve_cost(run_id,cost,p)
        calls+=1
        return call(messages,model=model,max_tokens=max_tokens,task=task,**kwargs)
    analyzer._call=bounded
    analyzer._client=analyzer._client.with_options(max_retries=0)
    return call
