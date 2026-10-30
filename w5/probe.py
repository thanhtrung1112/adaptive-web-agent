"""Freeze five M0 locators and detect missing or silently wrong targets after mutation."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.mutations_w5 import MODES
from dom_snapshot.run import isolated_app
from w4.run import write_json

SPECS = (
    ('id','/customers/new','#customer-email'),
    ('class','/customers/new','main.container'),
    ('text','/customers/new','text="Lưu"'),
    ('order','/customers','table thead tr th:nth-child(1)'),
    ('structure','/customers/new','xpath=/html/body/main/form/p[2]/input'),
)


def identity(loc, axis):
    if axis == 'class': return loc.evaluate('el=>el.tagName.toLowerCase()')
    if axis == 'order': return loc.inner_text().strip()
    if axis == 'text': return loc.get_attribute('type')
    return loc.get_attribute('name')


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
    rows=[]; expected={}
    with isolated_app(a.output) as base, sync_playwright() as pw:
        browser=pw.chromium.launch()
        try:
            for mode in ('M0',*MODES):
                for seed in ([0] if mode=='M0' else [17,23]):
                    with browser.new_context() as ctx:
                        page=ctx.new_page()
                        for axis,path,selector in SPECS:
                            page.goto(f'{base}{path}?mutation={mode}&seed={seed}')
                            loc=page.locator(selector); count=loc.count()
                            actual=identity(loc,axis) if count==1 else None
                            if mode=='M0':
                                if count!=1: raise AssertionError(f'M0 locator not unique: {axis}')
                                expected[axis]=actual
                            rows.append({'axis':axis,'mutation':mode,'seed':seed,'frozen_m0_locator':selector,
                                         'count':count,'expected_identity':expected[axis],'actual_identity':actual,
                                         'correct_target':count==1 and actual==expected[axis],
                                         'failure_kind':'missing' if count==0 else 'ambiguous' if count>1 else 'wrong_target' if actual!=expected[axis] else None})
        finally: browser.close()
    must_break={'W5_ID':'id','W5_CLASS':'class','W5_TEXT':'text','W5_ORDER':'order','W5_STRUCTURE':'structure'}
    for mode,axis in must_break.items():
        if any(r['correct_target'] for r in rows if r['mutation']==mode and r['axis']==axis):
            raise AssertionError(f'Axis did not break frozen M0 locator: {mode}')
    if any(r['correct_target'] for r in rows if r['mutation']=='W5_COMBINED'):
        raise AssertionError('Combined must break all five selected probes')
    write_json(a.output/'locator-probe.json',{'scope':'65 frozen-locator probes; not whole-task B0 success or recovery',
        'rows':rows,'targeted_axes_verified':list(must_break.values()),'all_targeted_axes_broken':True})
    print('PASS: 65 probes, five axes broken, wrong-target column detected')


if __name__=='__main__': main()
