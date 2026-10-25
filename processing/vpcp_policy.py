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


def reserve_cost(run_id,cost,p,*,document_sha,route,allow_first_qa=False,generation_run_id=None,manual_correction=False):
    """Durable CAS reservation in the EXISTING private source archive branch.

    Reserve before dispatch, never refund failed/aborted calls. No retry on a
    CAS conflict. Queue/handoff state stays on its existing daily branch.
    """
    import os,base64,requests
    from datetime import datetime,timezone
    from core.vietnam_document_custody import PRIVATE_REPO,REF
    from core.vietnam_corpus_bridge import BridgeError
    from processing import vpcp_correction as correction
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
    if response.status_code==200:
        obj=response.json();sha=obj['sha'];state=json.loads(base64.b64decode(obj['content']))
    else:raise BridgeError('vpcp_spend_checkpoint_unavailable')
    if (set(state)!={'schema','days','runs','documents'} or state['schema']!='ipr-vpcp-spend/1'
        or any(not isinstance(v,dict) or any(type(n) not in (int,float) or not math.isfinite(n) or n<0 for n in v.values()) for v in (state['days'],state['runs']))):
        raise BridgeError('vpcp_spend_checkpoint_invalid')
    import re
    if (not re.fullmatch('[a-f0-9]{64}',document_sha or '') or route not in ('relevance:500','summary:1000','summary:300')
        or not isinstance(state['documents'],dict) or any(not re.fullmatch('[a-f0-9]{64}',k) or not isinstance(v,dict)
            or set(v) not in ({'run_id','routes'},{'run_id','routes','qa_run_id'},{'run_id','routes','qa_run_id','manual_correction'}) or v['run_id'] not in state['runs'] or ('qa_run_id' in v and v['qa_run_id'] not in state['runs']) or not isinstance(v['routes'],list)
            or not v['routes'] or len(v['routes'])!=len(set(v['routes'])) or set(v['routes'])-{'relevance:500','summary:1000','summary:300'}
            for k,v in state['documents'].items())
        or abs(sum(state['days'].values())-sum(state['runs'].values()))>1e-8):
        raise BridgeError('vpcp_spend_checkpoint_invalid')
    for key,entry in state['documents'].items():
        if 'manual_correction' not in entry:continue
        c=entry['manual_correction']
        if (key!=correction.CONTENT or not isinstance(c,dict)
            or set(c)!={'decision','run_id','routes','reserved_cost_usd'}
            or c['decision']!=correction.DECISION or c['run_id'] not in state['runs']
            or c['routes'] not in (['summary:1000'],['summary:1000','summary:300'])
            or type(c['reserved_cost_usd']) not in (int,float) or not math.isfinite(c['reserved_cost_usd'])
            or not 0<c['reserved_cost_usd']<=correction.MAX_RESERVED
            or c['reserved_cost_usd']>state['runs'][c['run_id']]
            or entry['run_id']!=correction.GENERATION_RUN or entry['qa_run_id']!=correction.REJECTED_RUN
            or entry['routes']!=['relevance:500','summary:1000','summary:300']):
            raise BridgeError('vpcp_spend_checkpoint_invalid')
    prior=state['documents'].get(document_sha)
    if type(cost) not in (int,float) or not math.isfinite(cost) or cost<=0:
        raise BridgeError('vpcp_spend_cost_invalid')
    corrected=(prior or {}).get('manual_correction')
    if manual_correction:
        if (manual_correction is not True or not correction.manual_context()
            or document_sha!=correction.CONTENT or not prior
            or prior['run_id']!=correction.GENERATION_RUN or prior.get('qa_run_id')!=correction.REJECTED_RUN
            or prior['routes']!=['relevance:500','summary:1000','summary:300']
            or (not corrected and route!='summary:1000')
            or (corrected and (corrected['run_id']!=run_id or corrected['routes']!=['summary:1000'] or route!='summary:300'))):
            raise BridgeError('vpcp_document_retry_not_authorized')
        if cost+(corrected or {}).get('reserved_cost_usd',0)>correction.MAX_RESERVED:
            raise BridgeError('vpcp_correction_spend_cap')
    continuation=bool(allow_first_qa is True and prior and prior['run_id']==generation_run_id and prior['run_id']!=run_id
        and route=='summary:300' and prior['routes']==['relevance:500','summary:1000'])
    if not manual_correction and prior and (route in prior['routes'] or (prior['run_id']!=run_id and not continuation)):
        raise BridgeError('vpcp_document_retry_not_authorized')
    used=sum(v['run_id']==run_id or v.get('qa_run_id')==run_id or (v.get('manual_correction') or {}).get('run_id')==run_id for v in state['documents'].values())
    if ((prior is None and route!='relevance:500') or ((prior is None or continuation or (manual_correction and not corrected)) and used>=p['max_documents_per_run'])):
        raise BridgeError('vpcp_document_run_limit')
    day=datetime.now(timezone.utc).date().isoformat()
    today=state['days'].get(day,0);month=sum(v for k,v in state['days'].items() if k.startswith(day[:7]));run=state['runs'].get(run_id,0)
    if cost+run>p['max_cost_usd_per_run'] or cost+today>p['max_cost_usd_per_day'] or cost+month>p['max_cost_usd_per_month']:
        raise BridgeError('vpcp_spend_cap')
    state['days'][day]=today+cost;state['runs'][run_id]=run+cost
    entry=dict(prior) if prior else {'run_id':run_id,'routes':[]}
    if manual_correction:
        entry['manual_correction']={'decision':correction.DECISION,'run_id':run_id,
            'routes':(corrected or {}).get('routes',[])+[route],
            'reserved_cost_usd':(corrected or {}).get('reserved_cost_usd',0)+cost}
    else:entry['routes']=entry['routes']+[route]
    if continuation:entry['qa_run_id']=run_id
    state['documents'][document_sha]=entry
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
    verify_pricing()
    require_permission('public_ipr_analysis')
    if RELEVANCE_MODEL!='claude-haiku-4-5-20251001' or ANALYSIS_MODEL!='claude-sonnet-4-6':raise BridgeError('vpcp_model_not_authorized')
    if str(analyzer._client.base_url).rstrip('/')!='https://api.anthropic.com':raise BridgeError('vpcp_provider_not_authorized')
    if RELEVANCE_TOOL_OUTPUT_ENABLED:raise BridgeError('vpcp_tool_route_not_authorized')
    call=analyzer._call;calls=0
    def bounded(messages,*,model=None,max_tokens=1000,task=None,**kwargs):
        nonlocal calls
        actual=model or ANALYSIS_MODEL
        if (task,actual,max_tokens) not in (('relevance',RELEVANCE_MODEL,500),('summary',ANALYSIS_MODEL,1000),('summary',ANALYSIS_MODEL,300)) or calls>=6:
            raise BridgeError('vpcp_model_route_bound')
        system=kwargs.get('system',getattr(analyzer,'_SYSTEM_WITH_CACHE',[]))
        payload=dict(messages=messages,system=system,model=actual,max_tokens=max_tokens,**{k:v for k,v in kwargs.items() if k!='system'})
        input_bytes=len(json.dumps(payload,ensure_ascii=False).encode())
        if input_bytes>p['max_input_bytes']:raise BridgeError('vpcp_complete_model_input_limit')
        size=input_bytes+2048
        cost=estimate_usage_cost_usd(actual,0,max_tokens,size,0)
        if cost is None:raise BridgeError('vpcp_model_price_unknown')
        reserve_cost(run_id,cost,p,document_sha=getattr(analyzer,'_vpcp_document_sha',None),route=task+':'+str(max_tokens),allow_first_qa=getattr(analyzer,'_vpcp_first_qa_continuation',False),generation_run_id=getattr(analyzer,'_vpcp_generation_run_id',None),manual_correction=getattr(analyzer,'_vpcp_manual_correction',False))
        calls+=1
        return call(messages,model=model,max_tokens=max_tokens,task=task,**kwargs)
    analyzer._call=bounded
    analyzer._client=analyzer._client.with_options(max_retries=0)
    return call


def verify_pricing():
    """Revalidate only the provider's public prices, never send source text."""
    import requests,re
    from bs4 import BeautifulSoup
    from core.vietnam_corpus_bridge import BridgeError
    from analysis.pricing import PRICING_USD_PER_MTOK,CACHE_WRITE_5M_MULTIPLIER,CACHE_READ_MULTIPLIER
    expected={'Claude Sonnet 4.6':('claude-sonnet-4-6',[3,15,3.75,6,0.30]),
              'Claude Haiku 4.5':('claude-haiku-4-5-20251001',[1,5,1.25,2,0.10])}
    try:
        session=requests.Session();session.trust_env=False
        with session.get('https://platform.claude.com/docs/en/about-claude/pricing',
                headers={'User-Agent':'IndoPacificRecord-VPCP-price-verification/1'},
                timeout=20,allow_redirects=False,stream=True) as response:
            if response.status_code!=200:raise ValueError('price access')
            body=bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body)>2_000_000:raise ValueError('price size')
        rows=BeautifulSoup(bytes(body),'html.parser').select('tr')
        for label,(model,rates) in expected.items():
            matches=[row for row in rows if row.find(['td','th']) and row.find(['td','th']).get_text(' ',strip=True)==label]
            if not matches:raise ValueError('price row')
            cells=matches[0].find_all(['td','th'])[1:]
            actual=[float(re.search(r'\$([0-9.]+)',cell.get_text(' ',strip=True)).group(1)) for cell in cells[:5]]
            pinned=PRICING_USD_PER_MTOK[model]
            if actual!=rates or pinned!={'input':rates[0],'output':rates[1]} or CACHE_WRITE_5M_MULTIPLIER!=1.25 or CACHE_READ_MULTIPLIER!=0.1:
                raise ValueError('price changed')
    except Exception as exc:
        raise BridgeError('vpcp_model_pricing_unverified') from exc
