"""Local Ollama planner CLI. Logs actual responses; never substitutes a scripted plan."""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from jsonschema import ValidationError
from .core import SCHEMA, make_request, messages, validate_plan


# Require explicit localhost inference; no remote transmission of goals by default.
def generate(request, model, endpoint, client, history=None, think=None, schema=None):
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use a local Ollama HTTP endpoint without credentials/query')
    payload = {
        'model':model,'messages':history or messages(request),'format':schema or SCHEMA,'stream':False,
        'options':{'temperature':0,'seed':7,'num_predict':4096,'num_ctx':8192}}
    # Omit the option for older models; explicit False must not be dropped.
    if think is not None:
        payload['think'] = think
    response = client.post(endpoint.rstrip('/')+'/api/chat', json=payload)
    response.raise_for_status()
    return response.json()


# Persist failures as well as successes. Never label a schema-valid plan as task success.
def run(request, model, endpoint, output, think=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    record = {'scope':'LLM planning only; no browser execution', 'request':request,
              'model':model,'endpoint':endpoint,'temperature':0,'seed':7,'think':think,
              'started_at_utc':datetime.now(timezone.utc).isoformat(),
              'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
              'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.iterdir() if p.suffix in ('.py','.json')},
              'schema_valid':False,'task_success':None,'cost':None}
    history = messages(request)
    record['messages'] = history.copy()
    record['attempts'] = []
    record['context_length'] = 8192
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=240, trust_env=False) as client:
            # One bounded contract repair; the model must produce the correction itself.
            for attempt in range(2):
                raw = generate(request,model,endpoint,client,history,think=think)
                record['raw_response'] = raw
                item = {'raw_response':raw}
                record['attempts'].append(item)
                try:
                    if not raw.get('done') or raw.get('done_reason') == 'length':
                        raise ValueError('Incomplete model response')
                    plan = json.loads(raw['message']['content'])
                    validate_plan(plan,request)
                    record.update(schema_valid=True,plan=plan)
                    break
                except (ValueError, KeyError, TypeError, ValidationError) as exc:
                    item['validation_error'] = str(exc)[:2000]
                    if attempt == 1:
                        raise
                    history = history + [
                        {'role':'assistant','content':raw.get('message',{}).get('content','')},
                        {'role':'user','content':'Sửa JSON theo lỗi hợp đồng sau, giữ nguyên goal và dữ liệu: '+str(exc)[:2000]}]
                    item['repair_instruction'] = history[-1]['content']
    except Exception as exc:
        record['error'] = f'{type(exc).__name__}: {exc}'
    record['usage'] = {
        'input_tokens':sum(a['raw_response'].get('prompt_eval_count',0) for a in record['attempts']),
        'output_tokens':sum(a['raw_response'].get('eval_count',0) for a in record['attempts'])}
    record['latency_seconds'] = round(time.perf_counter()-started,3)
    (output/'trace.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--goal',required=True)
    parser.add_argument('--start-url',default='/customers')
    parser.add_argument('--max-steps',type=int,default=15)
    parser.add_argument('--model',required=True)
    parser.add_argument('--think',choices=['default','true','false'],default='default')
    parser.add_argument('--endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    request=make_request(args.goal,args.start_url,args.max_steps)
    output=args.output or Path('runs')/datetime.now(timezone.utc).strftime('planner_%Y%m%dT%H%M%S_%fZ')
    result=run(request,args.model,args.endpoint,output,
               think={'default':None,'true':True,'false':False}[args.think])
    print(json.dumps(result.get('plan',{'error':result.get('error')}),ensure_ascii=False,indent=2))
    print('OUTPUT:',output.resolve())
    return 0 if result['schema_valid'] else 1


if __name__=='__main__': raise SystemExit(main())
