"""Small frozen-locator failure probe on T004; not the full 30-task B0 matrix."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
from baseline.run_baseline import run_task
from dom_snapshot.run import isolated_app
from .run import ROOT, provenance, write_json


# Same task, database seed and original scripts under all four real app versions.
def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    out=args.output or ROOT/'runs'/datetime.now(timezone.utc).strftime('w4-b0-probe_%Y%m%dT%H%M%S_%fZ')
    out.mkdir(parents=True,exist_ok=False)
    task=next(t for t in json.loads((ROOT/'tasks/tasks_w4.json').read_text(encoding='utf-8')) if t['id']=='T004')
    metadata=provenance(); rows=[]
    with isolated_app(out) as base, sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:
            metadata['browser_version']=browser.version
            for mutation in ('M0','M1','M2','M3'):
                for mode in ('css','xpath'):
                    row,trace=run_task(browser,base,task,mode,out,mutation=mutation,mutation_seed=0 if mutation=='M0' else 7)
                    rows.append(trace)
                    print(mutation,mode,'PASS' if row['success'] else 'FAIL',row['failed_locator'],flush=True)
        finally: browser.close()
    write_json(out/'probe.json',{'scope':'frozen B0 T004 only; compare with full functionality oracle run',
               'metadata':metadata,'traces':rows})
    print('OUTPUT:',out)


if __name__=='__main__': main()
