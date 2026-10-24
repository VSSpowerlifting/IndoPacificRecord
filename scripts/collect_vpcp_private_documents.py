"""Inactive-by-default private collection step; reuses the metadata source.

Runs inside the existing private Vietnam collector, never the public Daily.
The surrounding workflow commits the existing source archive branch and the
subsequent shared Vietnam bridge authenticates the successful Action receipt.
No model, signing, publication, Git push or scheduler here.
"""
import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime,timezone
from core.collection.vietnam_government_documents import FAMILY
from core.collection.vietnam_vpcp_originals import OriginalsAdapter
from core.collection.host_gate import HostGate
from core.vietnam_document_custody import private_repo,preserve,hold
from processing.vpcp_policy import require_permission
from scraper.sources.vn_shadow_http import Refusal


def collect(database,repo,gate_dir):
    rules=require_permission('collect_preserve')
    if os.environ.get('VIETNAM_VPCP_TEXT_ENABLED')!='true':raise ValueError('vpcp_collection_inactive')
    if len(os.environ.get('VIETNAM_PRIVATE_BRIDGE_KEY',''))<32:raise ValueError('vpcp_capture_key_required')
    repo=private_repo(repo)
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    now=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    # All current metadata versions, including subject-filtered candidates.
    with sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as c:
        rows=c.execute('SELECT metadata_json FROM official_document_versions WHERE source_family=? ORDER BY first_observed_utc DESC',(FAMILY,)).fetchall()
    candidates={}
    for (raw,) in rows:
        m=json.loads(raw);candidates.setdefault(m['document_id'],m)
    from core.collection.vietnam_government_documents import digest,identity
    index_path=repo/'state/vpcp-index.json'
    index=json.loads(index_path.read_text()) if index_path.exists() else {'records':{},'checked':{}}
    from processing.government_document_intake import topics
    def priority(m):
        old=index['records'].get(identity(m))
        previous=json.loads((repo/'state/documents'/(old+'.json')).read_text())['capture'] if old else None
        unseen=previous is None or previous['metadata_sha256']!=digest(m)
        return (not bool(topics(m)),not unseen,index.get('checked',{}).get(identity(m),''),-int(m['document_id']))
    adapter=OriginalsAdapter(rules['max_documents_per_run'],gate=HostGate(gate_dir));adapter.open()
    outcomes=[]
    for m in sorted(candidates.values(),key=priority)[:rules['max_documents_per_run']]:
        if len(m['attachments'])!=1 or m['document_type'] not in ('Công văn','Thông báo'):
            hold(repo,identity(m));outcomes.append('attachment_review');continue
        try:
            got=adapter.fetch(m['attachments'][0])
            outcomes.append(preserve(repo,m,got['body'],collector_commit=source_commit,
                source_run=os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT'],
                workflow_sha=os.environ['GITHUB_SHA'],observed_utc=now))
        except Refusal:
            hold(repo,identity(m));outcomes.append('held_access');break
        except (ValueError,KeyError):
            hold(repo,identity(m));outcomes.append('held_document')
    return {'source_family':FAMILY,'outcomes':outcomes,'model_calls':0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--database',required=True);p.add_argument('--private-repo',required=True);p.add_argument('--gate-dir',required=True)
    a=p.parse_args()
    try:print(json.dumps(collect(a.database,a.private_repo,a.gate_dir),sort_keys=True))
    except (ValueError,OSError,sqlite3.Error):
        print(json.dumps({'source_family':FAMILY,'status':'held','model_calls':0}));return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
