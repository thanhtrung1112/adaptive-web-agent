"""Baseline W2: 20 task, 2 cấu hình, server/database tạm riêng cho mỗi lần chạy."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from app import db
from app.seed import reset_database
from baseline.checker import check_all
from baseline.scripts import SCRIPTS

ROOT = Path(__file__).resolve().parent.parent

# Hash byte LF cho mã nguồn; seed có .gitattributes cố định LF.
def source_hashes():
    files = []
    for folder in ('app', 'baseline', 'tasks', 'data'):
        files += [p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in ('.py','.html','.css','.js','.json') and '__pycache__' not in p.parts]
    files += [ROOT / 'requirements.txt', ROOT / 'requirements-lock.txt']
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in sorted(files) if p.exists()}

# Một hành động Playwright là một bước; chấm API không tính vào steps/latency.
def run_step(page, base, step, mode, path):
    action = step['do']
    if action == 'goto':
        page.goto(base + step['url'])
        return None
    loc = page.locator(step['css'] if mode == 'css' else 'xpath=' + step['xpath'])
    if action == 'fill': loc.fill(step['value'])
    elif action == 'select': loc.select_option(label=step['label'])
    elif action == 'click':
        loc.click()
        page.wait_for_load_state('load')
    elif action == 'download':
        with page.expect_download() as info: loc.click()
        path.parent.mkdir(parents=True, exist_ok=True)
        info.value.save_as(path)
        return path
    else: raise ValueError(f'Unknown action: {action}')
    return None

# Reset từng task; cookie mới; luôn đóng context kể cả task bị lỗi.
def run_task(browser, base, task, mode, out, record_video=False, slow_ms=0):
    reset_database()
    options = {'accept_downloads':True, 'viewport':{'width':1280,'height':800}}
    if record_video: options['record_video_dir'] = str(out / 'videos')
    ctx = browser.new_context(**options)
    page = ctx.new_page()
    page.set_default_timeout(5000)
    steps = SCRIPTS[task['id']]
    done, failed, error, dl, traces = 0, None, '', None, []
    t0 = time.perf_counter()
    try:
        for i, step in enumerate(steps):
            start = time.perf_counter()
            try:
                if i >= task['max_steps']: raise ValueError('Vượt max_steps')
                dl = run_step(page, base, step, mode, out/'downloads'/f"{task['id']}_{mode}.csv") or dl
                done += 1
                traces.append({'index':i, **step, 'success':True, 'seconds':round(time.perf_counter()-start,4)})
                if slow_ms: page.wait_for_timeout(slow_ms)
            except Exception as exc:
                failed, error = i, str(exc).splitlines()[0][:500]
                traces.append({'index':i, **step, 'success':False, 'error':error})
                break
        elapsed = time.perf_counter()-t0
        def get(path):
            response = ctx.request.get(base+path)
            if not response.ok: raise ValueError(f'API {path}: HTTP {response.status}')
            return response.json()
        ok, msg = check_all(get, task, dl) if failed is None else (False, 'Lỗi thực thi trước khi chấm')
        row = {'task_id':task['id'], 'module':task['module'], 'difficulty':task['difficulty'],
               'mode':mode, 'mutation':'M0', 'seed':task['seed'], 'success':ok,
               'steps_total':len(steps), 'steps_done':done, 'retry_count':0,
               'failed_step':failed if failed is not None else '',
               'failed_locator':steps[failed].get(mode,'') if failed is not None else '',
               'error':error, 'check':msg, 'seconds':round(elapsed,4)}
        return row, {'result':row, 'steps':traces, 'download':str(dl.relative_to(out)) if dl else None}
    finally: ctx.close()

# p95 nearest-rank, thống kê trên tất cả task kể cả thất bại.
def summarize(rows):
    result = {}
    for mode in sorted({r['mode'] for r in rows}):
        rs = [r for r in rows if r['mode']==mode]
        durations = sorted(r['seconds'] for r in rs)
        result[mode] = {'tasks':len(rs), 'success':sum(r['success'] for r in rs),
            'success_rate':sum(r['success'] for r in rs)/len(rs),
            'median_seconds':round(statistics.median(durations),4),
            'p95_seconds':durations[math.ceil(.95*len(durations))-1],
            'mean_steps':round(statistics.mean(r['steps_done'] for r in rs),2),
            'retry_count':0, 'token_cost':0,
            'by_module':{m:f"{sum(r['success'] for r in rs if r['module']==m)}/{sum(r['module']==m for r in rs)}" for m in sorted({r['module'] for r in rs})}}
    return result

# Lưu kết quả cả khi có task fail; exit code 1 để CI không báo đạt giả.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['css','xpath','both'], default='both')
    parser.add_argument('--tasks', nargs='+')
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--record-video', action='store_true')
    parser.add_argument('--slow-ms', type=int, default=0, help='Chỉ dùng cho demo, không dùng số liệu timing này làm benchmark')
    args = parser.parse_args()
    tasks = json.loads((ROOT/'tasks/tasks_w2.json').read_text(encoding='utf-8'))
    if args.tasks and set(args.tasks)-{t['id'] for t in tasks}: parser.error('Task ID không tồn tại')
    tasks = [t for t in tasks if not args.tasks or t['id'] in args.tasks]
    if any(t['id'] not in SCRIPTS or len(SCRIPTS[t['id']])>t['max_steps'] for t in tasks): parser.error('Thiếu script hoặc vượt max_steps')
    out = ROOT/'runs'/datetime.now(timezone.utc).strftime('baseline_M0_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True)
    modes = ['css','xpath'] if args.mode=='both' else [args.mode]
    metadata = {'started_at_utc':datetime.now(timezone.utc).isoformat(),
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),
        'source_hashes_lf':source_hashes(), 'seed_sha256':hashlib.sha256((ROOT/'data/seed_v1.json').read_bytes()).hexdigest(),
        'tasks_sha256':hashlib.sha256((ROOT/'tasks/tasks_w2.json').read_bytes()).hexdigest(),
        'python':sys.version, 'platform':platform.platform(),
        'packages':{name:importlib.metadata.version(name) for name in ('playwright','fastapi','starlette','uvicorn')},
        'task_count':len(tasks),'modes':modes,'repetitions':1,'slow_ms':args.slow_ms,
        'protocol':'isolated SQLite + new browser context per task; 5s action timeout; no retries; latency excludes reset/context/API check; includes goto and download; UTC date filters'}
    rows, traces = [], []
    original_db = db.DB_PATH
    try:
        with tempfile.TemporaryDirectory(prefix='minibiz-w2-') as temp:
            db.DB_PATH = Path(temp)/'benchmark.sqlite3'
            reset_database()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
            base = f'http://127.0.0.1:{port}'
            env = {**os.environ,'MINIBIZ_DB_PATH':str(db.DB_PATH)}
            with (out/'server.log').open('w',encoding='utf-8') as log:
                server = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    for _ in range(100):
                        if server.poll() is not None: raise RuntimeError('Server failed; xem server.log')
                        try:
                            with urllib.request.urlopen(base+'/health',timeout=.5) as response:
                                if response.status==200: break
                        except OSError: time.sleep(.1)
                    else: raise RuntimeError('Server startup timeout')
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=not args.headed)
                        metadata['browser_version']=browser.version
                        try:
                            for mode in modes:
                                for task in tasks:
                                    row, trace = run_task(browser,base,task,mode,out,args.record_video,args.slow_ms)
                                    rows.append(row); traces.append(trace)
                                    print(f"{mode} {task['id']} {'PASS' if row['success'] else 'FAIL'} {row['seconds']}s {row['error'] or row['check']}",flush=True)
                        finally: browser.close()
                finally:
                    server.terminate()
                    try: server.wait(timeout=10)
                    except subprocess.TimeoutExpired: server.kill(); server.wait()
    finally:
        db.DB_PATH=original_db
        metadata['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        metadata['completed_rows']=len(rows)
        for name,data in [('metadata',metadata),('traces',traces),('summary',summarize(rows))]:
            (out/f'{name}.json').write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        if rows:
            with (out/'results.csv').open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        print('OUTPUT:',out,flush=True)
    return 0 if len(rows)==len(tasks)*len(modes) and all(r['success'] for r in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
