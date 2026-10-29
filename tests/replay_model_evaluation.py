"""Replay preserved Anthropic responses; never dispatch or write evidence.

Run: python -m tests.replay_model_evaluation --evidence-dir PRIVATE_DIRECTORY
Old responses test new rejection/recovery code, not revised-prompt generation.
Only counts, rejection reasons and usage-priced costs are emitted.
"""
import argparse
import contextlib
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import analysis.analyzer as engine
from analysis.usage import build_run_record
from processing.screening import profile_for_desk

MANIFEST_SHA = 'bda59247ed4f264181ea482d1a1556599c620e7dffa2e26761391c8797daca35'
FROZEN_FILES = {
    'results.json': '424c72cab04f59b9d0a94452aabe082eb89e9a0083f0824b7fed18189752d720',
    'budget.sqlite': 'a77657e09fff9c58b39d9df374d595b31d2c8df21c2ab14fc35e57e94de6089f',
}


class Replay:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = self
        self.calls = 0

    def create(self, **request):
        raw = next(self.responses)
        if raw['model'] != request['model']:
            raise ValueError('replay model mismatch')
        self.calls += 1
        return SimpleNamespace(
            stop_reason=raw['stop_reason'],
            usage=SimpleNamespace(**raw['usage']),
            content=[SimpleNamespace(**b) for b in raw['content']])

    @contextlib.contextmanager
    def stream(self, **request):
        response = self.create(**request)
        yield SimpleNamespace(get_final_message=lambda: response)


def replay(directory):
    for name, expected in FROZEN_FILES.items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected:
            raise ValueError('frozen response evidence mismatch: ' + name)
    manifest_bytes = (directory/'manifest.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA:
        raise ValueError('frozen manifest mismatch')
    manifest = json.loads(manifest_bytes)
    records = {}
    for entry in manifest['records']:
        content = (directory/entry['input_file']).read_bytes()
        if hashlib.sha256(content).hexdigest() != entry['input_file_sha256']:
            raise ValueError('frozen input mismatch')
        records[entry['record_id']] = json.loads(content)
    baseline = json.loads((directory/'results.json').read_text())
    with sqlite3.connect((directory/'budget.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True) as conn:
        conn.row_factory=sqlite3.Row
        calls=[dict(r) for r in conn.execute('select * from calls order by rowid')]
    report={}
    for model in manifest['models']:
        a=engine.Analyzer.__new__(engine.Analyzer)
        a.task_model=lambda task: model
        outcomes=Counter(); rejected=[]
        for rid,record in records.items():
            original=(record['title_original'],record['text_original'])
            for task in ['relevance','translation','summary','categorization']:
                rows=[r for r in calls if r['model']==model and r['record_id']==rid and r['task']==task]
                if not rows:continue
                a._client=Replay([json.loads(r['raw']) for r in rows])
                controlled=(['own','common'] if model=='claude-haiku-5-5' and task in ('summary','categorization') and record['slug']!='sg_mindef_releases' else ['own'])
                for condition in controlled:
                    label=task+':'+condition
                    try:
                        if task=='relevance':a.score_relevance(*original,profile=profile_for_desk('singapore') if record['slug']=='sg_mindef_releases' else None)
                        elif task=='translation':a.translate(*original)
                        elif record['slug']=='sg_mindef_releases':a._desk_summary_and_flag(*original,profile_for_desk('singapore'))
                        else:
                            input_model='claude-sonnet-4-6' if condition=='common' else model
                            english=baseline['records'][str(rid)][input_model]['translation']['result']
                            if task=='summary':a.summarize(*english)
                            else:a.categorize(*english)
                        outcomes[label+':accepted_by_code']+=1
                    except engine.AnalysisError as exc:
                        outcomes[label+':held_by_code']+=1
                        rejected.append({'record':rid,'task':label,'reason':str(exc)})
                # A missing/unconsumed stored response is a replay defect. No
                # new model call or invented response may fill a hole.
                if a._client.calls != len(rows):raise ValueError('unconsumed stored response')
        usage=build_run_record(a.usage,run_date='2026-10-29',recorded_at='frozen-replay',run_status='offline',analysis_model=model,relevance_model=model,articles_queued=len(records),articles_fully_analyzed=0)
        report[model]={'outcomes':dict(outcomes),'held':rejected,'usage':usage}
    return {'manifest_sha256':MANIFEST_SHA,'provider_dispatches':0,
            'generation_prompts':'preserved old prompts; revised prompts NOT live-qualified',
            'factual_acceptance':'No candidate qualified; code acceptance is not factual acceptance',
            'models':report}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args()
    # Explicitly isolate replay from operator overrides. No key/client/network.
    with patch.multiple(engine,TRANSLATION_MODEL='',SUMMARY_MODEL='',CATEGORIZATION_MODEL='',FALLBACK_MODEL='',RELEVANCE_TOOL_OUTPUT_ENABLED=False):
        print(json.dumps(replay(args.evidence_dir),indent=2))


if __name__=='__main__':main()
