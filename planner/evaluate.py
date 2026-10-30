"""Run fixed development goals; status/schema checks do not imply task success."""
import argparse
import csv
import json
from pathlib import Path
from .core import make_request
from .run import run


# Reviewer rubrics remain evaluator-side, never in the model request.
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True)
    parser.add_argument('--think',choices=['default','true','false'],default='default')
    parser.add_argument('--mode',choices=['direct','hybrid'],default='direct')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',nargs='+')
    args=parser.parse_args()
    runner=run
    if args.mode=='hybrid':
        from .hybrid import run as runner
    cases=json.loads(Path(__file__).with_name('cases.json').read_text(encoding='utf-8'))
    if args.cases:
        if set(args.cases)-{c['id'] for c in cases}: parser.error('Unknown case')
        cases=[c for c in cases if c['id'] in args.cases]
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for case in cases:
        result=runner(make_request(case['goal'],case['start_url'],30),args.model,
                   'http://127.0.0.1:11434',args.output/case['id'],
                   think={'default':None,'true':True,'false':False}[args.think])
        status=result.get('plan',{}).get('status')
        rows.append({'case':case['id'],'schema_valid':result['schema_valid'],
                     'status':status,'expected_status':case['expected_status'],
                     'status_matches':status==case['expected_status'],
                     'latency_seconds':result['latency_seconds'],
                     'semantic_review':'pending','browser_executed':False})
        print(rows[-1],flush=True)
        # Preserve completed cases if a later model request is interrupted.
        (args.output/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (args.output/'progress.json').write_text(json.dumps({
            'requested_cases':[c['id'] for c in cases],
            'completed_cases':[r['case'] for r in rows],
            'complete':len(rows)==len(cases)},indent=2)+'\n',encoding='utf-8')
        with (args.output/'summary.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return 0 if all(r['schema_valid'] and r['status_matches'] for r in rows) else 1


if __name__=='__main__': raise SystemExit(main())
