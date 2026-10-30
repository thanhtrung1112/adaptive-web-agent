"""Replay real app variants using an evaluation oracle, with isolated DB and W3 snapshots."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from app.mutations import MODES, context_url
from app.seed import reset_database
from baseline.checker import check_all
from baseline.run_baseline import run_step, SCRIPTS
from dom_snapshot.capture import capture, save_snapshot
from dom_snapshot.run import isolated_app
from .oracle import oracle_css, element_id

ROOT = Path(__file__).resolve().parents[1]


# Include dirty-source LF hashes, not just HEAD; reports may be produced before committing.
def provenance():
    files = sorted(p for folder in ('app','baseline','dom_snapshot','w4','tasks','tests','data')
                   for p in (ROOT/folder).rglob('*')
                   if p.is_file() and p.suffix in ('.py','.js','.html','.css','.json') and '__pycache__' not in p.parts)
    files += [ROOT/'requirements.txt',ROOT/'requirements-lock.txt',ROOT/'scripts/validate_tasks.py',ROOT/'scripts/seed_manifest.py']
    return {'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),
            'source_hashes_lf':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files},
            'data_seed':'seed_v1','seed_sha256':hashlib.sha256((ROOT/'data/seed_v1.json').read_bytes()).hexdigest()}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


# Each task runs on reset DB + fresh cookie context. Oracle success is not B0/A1 success.
def replay(browser, base, task, mutation, seed, out, metadata, snapshots, translate=oracle_css):
    reset_database()
    refs, trace, failure, downloaded, pre_ok = [], [], '', None, None
    with browser.new_context(viewport={'width':1280,'height':800},accept_downloads=True) as ctx:
        page = ctx.new_page()
        page.set_default_timeout(5000)
        ctx.add_cookies([{'name':'minibiz_mutation','value':f'{mutation}:{seed}','url':base}])
        def get(path):
            response = ctx.request.get(base+path)
            if not response.ok: raise ValueError(f'{path}: HTTP {response.status}')
            return response.json()
        try:
            pre_ok = check_all(get,task)[0]
            if pre_ok: raise AssertionError('Task already satisfies success criteria on seed')
            for i, original in enumerate(SCRIPTS[task['id']]):
                if i >= task['max_steps']: raise AssertionError('max_steps exceeded')
                step = dict(original)
                if step['do'] == 'goto':
                    step['url'] = context_url(step['url'],mutation,seed)
                else:
                    loc = page.locator(translate(step['css'],mutation,seed))
                    loc.wait_for(state='visible')
                    if snapshots:
                        sid = f'{mutation}-s{seed}-{task["id"]}-step{i:02d}'
                        html, snapshot = capture(page,sid,task['id'],f'{task["id"]}-step{i:02d}',
                            {'mutation':mutation,'mutation_seed':seed,'data_seed':task['seed'],
                             'git_commit':metadata['git_commit'],'seed_sha256':metadata['seed_sha256'],'capture_kind':'pre-action runtime'})
                        eid = element_id(loc)
                        if eid not in {e['element_id'] for e in snapshot['elements']}: raise AssertionError('Target absent from snapshot')
                        save_snapshot(out/'snapshots'/sid,html,snapshot)
                        refs.append({'task_id':task['id'],'step_index':i,'action':step['do'],
                                     'mutation':mutation,'mutation_seed':seed,
                                     'snapshot':f'snapshots/{sid}/features.json','target_element_id':eid})
                    step['css'] = translate(step['css'],mutation,seed)
                downloaded = run_step(page,base,step,'css',out/'downloads'/f'{mutation}-s{seed}-{task["id"]}.csv') or downloaded
                if page.url.startswith(base) and not page.url.startswith(base+'/api/'):
                    cookie = next(c['value'] for c in ctx.cookies() if c['name']=='minibiz_mutation')
                    if cookie != f'{mutation}:{seed}': raise AssertionError('Lost mutation context')
                trace.append({'index':i,'action':step['do'],'passed':True})
            ok, message = check_all(get,task,downloaded)
            if not ok: raise AssertionError(message)
            if snapshots:
                sid = f'{mutation}-s{seed}-{task["id"]}-final'
                html, snapshot = capture(page,sid,task['id'],f'{task["id"]}-final',
                    {'mutation':mutation,'mutation_seed':seed,'data_seed':task['seed'],
                     'git_commit':metadata['git_commit'],'seed_sha256':metadata['seed_sha256'],'capture_kind':'post-task runtime'})
                save_snapshot(out/'snapshots'/sid,html,snapshot)
        except Exception as exc:
            failure = f'{type(exc).__name__}: {exc}'[:1500]
        row = {'task_id':task['id'],'module':task['module'],'mutation':mutation,'mutation_seed':seed,
               'runner':'functionality_oracle_NOT_embedding','success':not failure,
               'precondition_success':pre_ok,'steps_done':len(trace),'error':failure}
        return row, {'result':row,'steps':trace}, refs


# Match the same task/pre-action state across independent M0 and mutated replays.
def make_pairs(refs):
    base = {(r['task_id'],r['step_index']):r for r in refs if r['mutation']=='M0'}
    pairs = []
    for row in refs:
        if row['mutation']=='M0': continue
        original = base.get((row['task_id'],row['step_index']))
        if original is None: continue
        pairs.append({'task_id':row['task_id'],'step_index':row['step_index'],'action':row['action'],
                      'mutation':row['mutation'],'mutation_seed':row['mutation_seed'],
                      'reference_snapshot':original['snapshot'],'reference_element_id':original['target_element_id'],
                      'candidate_snapshot':row['snapshot'],'target_element_id':row['target_element_id']})
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',nargs='+')
    parser.add_argument('--mutations',nargs='+',choices=MODES,default=list(MODES))
    parser.add_argument('--seeds',nargs='+',type=int,default=[7])
    parser.add_argument('--output',type=Path)
    parser.add_argument('--no-snapshots',action='store_true')
    args = parser.parse_args()
    tasks = json.loads((ROOT/'tasks/tasks_w4.json').read_text(encoding='utf-8'))
    if args.tasks and set(args.tasks)-{t['id'] for t in tasks}: parser.error('Unknown task IDs')
    if any(not 0 <= seed <= 2147483647 for seed in args.seeds): parser.error('Seed out of range')
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.mutations)) != len(args.mutations): parser.error('Duplicate modes/seeds')
    tasks = [t for t in tasks if not args.tasks or t['id'] in args.tasks]
    if any(t['id'] not in SCRIPTS for t in tasks): parser.error('Missing M0 feasibility script')
    if 'M0' not in args.mutations and not args.no_snapshots: parser.error('M0 required for paired snapshot dataset')
    out = (args.output or ROOT/'runs'/datetime.now(timezone.utc).strftime('w4_%Y%m%dT%H%M%S_%fZ')).resolve()
    out.mkdir(parents=True,exist_ok=False)
    metadata = provenance()
    metadata.update(started_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),
                    playwright=importlib.metadata.version('playwright'),mutations=args.mutations,development_seeds=args.seeds,
                    task_ids=[t['id'] for t in tasks],task_file='tasks/tasks_w4.json',
                    task_sha256=hashlib.sha256((ROOT/'tasks/tasks_w4.json').read_bytes()).hexdigest(),
                    protocol='one replay/task/variant; reset isolated DB; fresh browser context; evaluator oracle, not ranking; held-out not accessed')
    rows, traces, refs = [], [], []
    try:
        with isolated_app(out) as base, sync_playwright() as pw:
            browser = pw.chromium.launch()
            metadata['browser_version'] = browser.version
            try:
                modes = sorted(args.mutations)
                for mutation in modes:
                    for seed in ([0] if mutation=='M0' else args.seeds):
                        for task in tasks:
                            row, trace, captured = replay(browser,base,task,mutation,seed,out,metadata,not args.no_snapshots)
                            rows.append(row); traces.append(trace); refs.extend(captured)
                            print(f'{mutation} seed={seed} {task["id"]} {"PASS" if row["success"] else "FAIL"} {row["error"]}',flush=True)
            finally: browser.close()
    finally:
        expected = len(tasks)*sum(1 if mode=='M0' else len(args.seeds) for mode in args.mutations)
        summary = {'scope':'full task replays using evaluator oracle; NOT embedding/B0 success',
                   'expected_rows':expected,'completed_rows':len(rows),'passed':sum(r['success'] for r in rows),
                   'all_passed':len(rows)==expected and all(r['success'] for r in rows),
                   'by_mutation':{m:{'total':sum(r['mutation']==m for r in rows),'passed':sum(r['success'] for r in rows if r['mutation']==m)} for m in args.mutations},
                   'snapshot_count':len(list((out/'snapshots').glob('*/features.json'))),
                   'pair_count':len(make_pairs(refs)),'embedding_evaluated':False}
        metadata['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(out/'metadata.json',metadata)
        write_json(out/'summary.json',summary)
        write_json(out/'traces.json',traces)
        write_json(out/'ground_truth/pairs.json',make_pairs(refs))
        write_json(out/'coverage.json',{'scope':'pre-action and final states from full replays; see success rows',
                   'rows':rows,'pre_action_snapshots':refs})
        if rows:
            with (out/'results.csv').open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
        print('OUTPUT:',out,flush=True)
    return 0 if summary['all_passed'] else 1


if __name__=='__main__': raise SystemExit(main())
