"""python -m dom_snapshot.run: thu bộ mẫu W3, không đụng database đang dùng."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from app import db
from app.seed import reset_database
from .capture import capture, save_snapshot

ROOT = Path(__file__).resolve().parents[1]


# Server riêng, database riêng; khôi phục biến module ngay cả khi thu mẫu lỗi.
@contextmanager
def isolated_app(out):
    original = db.DB_PATH
    with tempfile.TemporaryDirectory(prefix='w3-dom-', dir=out) as temp:
        try:
            db.DB_PATH = Path(temp)/'snapshot.sqlite3'
            reset_database()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            base = f'http://127.0.0.1:{port}'
            with (out/'server.log').open('w', encoding='utf-8') as log:
                server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT,
                    env={**os.environ, 'MINIBIZ_DB_PATH': str(db.DB_PATH)}, stdout=log, stderr=log,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    for _ in range(100):
                        if server.poll() is not None:
                            raise RuntimeError('Server failed; see server.log')
                        try:
                            with urllib.request.urlopen(base+'/health', timeout=.5) as response:
                                if response.status == 200:
                                    break
                        except OSError:
                            time.sleep(.1)
                    else:
                        raise RuntimeError('Server startup timeout')
                    yield base
                finally:
                    # Windows venv python may spawn a child owning the log/SQLite handles.
                    # Stop only this server's process tree before temporary-directory cleanup.
                    if os.name == 'nt' and server.poll() is None:
                        subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    if server.poll() is None:
                        server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
        finally:
            db.DB_PATH = original


from .cases import CASES, check_features


# Chỉ ghi vào thư mục mới để bảo toàn bằng chứng lần chạy trước.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    out = args.output or ROOT/'runs'/datetime.now(timezone.utc).strftime('dom_W3_%Y%m%dT%H%M%S_%fZ')
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    files = sorted(p for folder in ('app', 'dom_snapshot') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.js','.html','.css','.json'))
    provenance = {
        'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'git_status': subprocess.check_output(['git','status','--porcelain'], cwd=ROOT, text=True),
        'source_hashes_lf': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files},
        'seed_sha256': hashlib.sha256((ROOT/'data/seed_v1.json').read_bytes()).hexdigest(),
        'mutation': 'M0', 'schema_status': 'proposal awaiting candidate-generator integration',
    }
    summary = []
    with isolated_app(out) as base, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            provenance['browser_version'] = browser.version
            for spec in CASES:
                reset_database()
                state, task, route, ready = spec['state'], spec['tasks'][0], spec['route'], spec['ready']
                with browser.new_context(viewport={'width':1280,'height':800}) as context:
                    page = context.new_page()
                    page.set_default_timeout(5000)
                    response = page.goto(base+route)
                    if not response.ok:
                        raise RuntimeError(f'{route}: HTTP {response.status}')
                    page.locator(ready).wait_for(state='visible')
                    for action, selector, value in spec['steps']:
                        locator = page.locator(selector)
                        if action == 'fill': locator.fill(value)
                        elif action == 'select': locator.select_option(value=value)
                        elif action == 'click':
                            locator.click()
                            page.wait_for_load_state('load')
                        else: raise ValueError(action)
                    html, features = capture(page, state, task, state, provenance)
                    check_features(features, spec)
                    # Kiểm tra mọi tham chiếu ánh xạ duy nhất vào DOM đang chụp.
                    for element in features['elements']:
                        locator = page.locator('xpath='+element['locator']['value'])
                        if locator.count() != 1:
                            raise ValueError(f'Non-unique reference: {element["element_id"]}')
                    save_snapshot(out/state, html, features)
                    row = {'state':state, 'task_id':task, 'related_tasks':spec['tasks'], 'elements':len(features['elements']),
                           'visible':sum(e['visible'] for e in features['elements']),
                           'controls':sum(e['tag'] in ('input','select','textarea','button','a') for e in features['elements'])}
                    summary.append(row)
                    print(row, flush=True)
        finally:
            browser.close()
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    coverage = {task: [s['state'] for s in summary if task in s['related_tasks']] for task in sorted({t for s in summary for t in s['related_tasks']})}
    (out/'coverage.json').write_text(json.dumps({'scope':'representative UI states, not full task replay', 'tasks':coverage}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('OUTPUT:', out)


if __name__ == '__main__':
    main()
