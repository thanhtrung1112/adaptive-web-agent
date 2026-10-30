"""LLM intent + explicit MiniBiz workflows. No hard-coded task-ID plan lookup."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from jsonschema import ValidationError
from .core import make_request
from .intent import SCHEMA, messages, validate
from .run import generate
from .workflows import compile_intent


# Log actual extraction and compilation separately; never replace failed LLM intent with fixtures.
def run(request, model, endpoint, output, think=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    record={'architecture':'LLM intent + deterministic MiniBiz workflows v1',
            'scope':'planning only; no browser execution','intent_schema_version':'1.0','request':request,'model':model,
            'endpoint':endpoint,'think':think,'temperature':0,'seed':7,'context_length':8192,
            'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.json')},
            'schema_valid':False,'task_success':None,'cost':None,'attempts':[]}
    history=messages(request);record['messages']=history.copy()
    started=time.perf_counter()
    try:
        with httpx.Client(timeout=240,trust_env=False) as client:
            for attempt in range(2):
                raw=generate(request,model,endpoint,client,history,think=think,schema=SCHEMA)
                item={'raw_response':raw};record['attempts'].append(item)
                try:
                    if not raw.get('done') or raw.get('done_reason')=='length': raise ValueError('Incomplete intent response')
                    intent=json.loads(raw['message']['content']);validate(intent,request['goal'])
                    record['intent']=intent
                    compiled=compile_intent(intent,request)
                    record.update(compiled,schema_valid=True)
                    break
                except (ValueError,KeyError,TypeError,ValidationError) as exc:
                    item['validation_error']=str(exc)[:1500]
                    if attempt==1: raise
                    history=history+[{'role':'assistant','content':raw.get('message',{}).get('content','')},
                                     {'role':'user','content':'Sửa JSON trích xuất; giữ đúng dữ liệu goal. Lỗi: '+str(exc)[:1500]}]
            # This endpoint was already allowlisted by generate; provenance failure does not erase the plan.
            try:
                models=client.get(endpoint.rstrip('/')+'/api/tags').json()['models']
                record['model_inventory']=next((m for m in models if m['name']==model),None)
                record['ollama_version']=client.get(endpoint.rstrip('/')+'/api/version').json()
            except (httpx.HTTPError,ValueError,KeyError) as exc:
                record['metadata_warning']=str(exc)[:200]
    except Exception as exc:
        record['error']=f'{type(exc).__name__}: {exc}'
    # A timeout can consume unreported tokens; do not report zero as measured usage.
    complete=bool(record['attempts']) and not record.get('error')
    record['usage']={'complete':complete,
                     'reported_input_tokens':sum(a['raw_response'].get('prompt_eval_count',0) for a in record['attempts']),
                     'reported_output_tokens':sum(a['raw_response'].get('eval_count',0) for a in record['attempts'])}
    record['latency_seconds']=round(time.perf_counter()-started,3)
    (output/'trace.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goal',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--think',choices=['default','true','false'],default='false')
    parser.add_argument('--start-url',default='/customers')
    parser.add_argument('--max-steps',type=int,default=30)
    parser.add_argument('--endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    request=make_request(args.goal,args.start_url,args.max_steps)
    output=args.output or Path('runs')/datetime.now(timezone.utc).strftime('hybrid_%Y%m%dT%H%M%S_%fZ')
    result=run(request,args.model,args.endpoint,output,{'default':None,'true':True,'false':False}[args.think])
    print(json.dumps(result.get('plan',{'error':result.get('error')}),ensure_ascii=False,indent=2))
    print('OUTPUT:',output.resolve())
    return 0 if result['schema_valid'] else 1


if __name__=='__main__': raise SystemExit(main())
