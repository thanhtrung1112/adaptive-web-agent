"""python -m w5.run --output results/w5/benchmark_v0.5.0"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from app.mutations import opaque_id
from app.mutations_w5 import MODES, VERSION
from dom_snapshot.run import isolated_app
from w4.run import ROOT, make_pairs, provenance, replay, write_json
from w4.validate_dataset import validate


def oracle(css, mode, seed):
    """Evaluation only, never passed to an agent/ranker."""
    if mode in ('W5_ID', 'W5_COMBINED') and css.startswith('#'):
        return '#' + opaque_id(css[1:], seed)
    return css


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--seeds', nargs='+', type=int, default=[17, 23])
    ap.add_argument('--tasks', nargs='+')
    ap.add_argument('--no-snapshots', action='store_true')
    a = ap.parse_args()
    if len(set(a.seeds)) != len(a.seeds) or any(type(s) is not int or not 0 <= s <= 2147483647 for s in a.seeds):
        ap.error('Invalid/duplicate development seeds')
    tasks = json.loads((ROOT/'tasks/tasks_w4.json').read_text(encoding='utf-8'))
    if a.tasks:
        if set(a.tasks) - {t['id'] for t in tasks}: ap.error('Unknown tasks')
        tasks = [t for t in tasks if t['id'] in a.tasks]
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    meta = provenance()
    meta.update(benchmark_version=VERSION, started_at_utc=datetime.now(timezone.utc).isoformat(),
                development_seeds=a.seeds, mutations=['M0',*MODES], task_ids=[t['id'] for t in tasks],
                protocol='isolated DB reset and fresh context/task/variant; evaluation oracle; not agent success',
                python=sys.version, held_out_accessed=False)
    for folder in ('w5','ranking','candidates'):
        for p in (ROOT/folder).rglob('*.py'):
            meta['source_hashes_lf'][p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    rows, traces, refs = [], [], []
    try:
        with isolated_app(out) as base, sync_playwright() as pw:
            browser = pw.chromium.launch()
            meta['browser_version'] = browser.version
            try:
                for mode in ('M0',*MODES):
                    for seed in ([0] if mode == 'M0' else a.seeds):
                        for task in tasks:
                            row, trace, captured = replay(browser,base,task,mode,seed,out,meta,not a.no_snapshots,translate=oracle)
                            rows.append(row); traces.append(trace); refs.extend(captured)
                            print(f'{mode} s{seed} {task["id"]}: {row["success"]} {row["error"]}',flush=True)
                        # Reproducible screenshots of the actual runtime DOM for each mode/seed.
                        with browser.new_context() as ctx:
                            page=ctx.new_page(); page.goto(f'{base}/customers?mutation={mode}&seed={seed}')
                            (out/'figures').mkdir(exist_ok=True)
                            page.screenshot(path=str(out/'figures'/f'{mode}-s{seed}.png'),full_page=True)
            finally:
                browser.close()
    finally:
        expected = len(tasks)*(1+len(MODES)*len(a.seeds))
        summary = {'benchmark_version':VERSION,'expected_rows':expected,'completed_rows':len(rows),
                   'passed':sum(r['success'] for r in rows),'all_passed':len(rows)==expected and all(r['success'] for r in rows),
                   'scope':'functionality oracle; NOT adaptive agent or recovery rate',
                   'by_mutation':{m:{'total':sum(r['mutation']==m for r in rows),'passed':sum(r['success'] for r in rows if r['mutation']==m)} for m in ('M0',*MODES)},
                   'snapshot_count':len(list((out/'snapshots').glob('*/features.json'))),'pair_count':len(make_pairs(refs))}
        meta['finished_at_utc']=datetime.now(timezone.utc).isoformat()
        for name,data in [('metadata',meta),('summary',summary),('traces',traces),('coverage',{'rows':rows,'pre_action_snapshots':refs})]:
            write_json(out/f'{name}.json',data)
        write_json(out/'ground_truth/pairs.json',make_pairs(refs))
        if rows:
            with (out/'results.csv').open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n'); w.writeheader(); w.writerows(rows)
    if not a.no_snapshots:
        validate(out,mutation_modes=('M0',*MODES))
    print(json.dumps(summary),flush=True)
    return 0 if summary['all_passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
