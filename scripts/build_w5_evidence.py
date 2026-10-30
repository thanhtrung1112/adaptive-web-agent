"""Build/check W5 evidence from actual benchmark outputs, never invent test results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FULL=ROOT/'results/w5/benchmark_v0.5.0'
OUT=ROOT/'Evidence/W05'
PUB=ROOT/'results/w5/published_v0.5.0'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
    if a.check:
        manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
        bad=[p for p,h in manifest['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
        if bad: raise ValueError(f'Artifact checksum mismatch: {bad}')
        from w4.validate_dataset import validate
        from app.mutations_w5 import MODES
        val=validate(PUB,write_report=False,mutation_modes=('M0',*MODES))
        print(f'PASS: {len(manifest["files"])} checksums; {val["snapshot_count"]} sample snapshots, {val["pair_count"]} pairs')
        return
    summary=json.loads((FULL/'summary.json').read_text(encoding='utf-8'))
    if not summary['all_passed'] or summary['completed_rows']!=390: raise ValueError('Incomplete or failing full benchmark')
    for log in ('test-results.txt','release-test-results.txt'):
        path=OUT/log
        if path.exists(): path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
    test=(OUT/'test-results.txt').read_text(encoding='utf-8-sig')
    if 'Ran 85 tests' not in test or not test.rstrip().endswith('OK'): raise ValueError('Missing successful test log')
    OUT.mkdir(parents=True,exist_ok=True)
    for name in ('summary.json','metadata.json','results.csv','validation.json'):
        shutil.copy2(FULL/name,OUT/name)
    shutil.copy2(ROOT/'results/w5/probe_v0.5.0/locator-probe.json',OUT/'locator-probe.json')
    shutil.copytree(FULL/'figures',OUT/'figures',dirs_exist_ok=True)
    # Complete JSON/HTML pair examples, balanced by module/axis, seed 17 only.
    pairs=json.loads((FULL/'ground_truth/pairs.json').read_text(encoding='utf-8'))
    chosen=[]
    for task in ('T001','T004','T007'):
        for mode in ('W5_ID','W5_CLASS','W5_TEXT','W5_ORDER','W5_STRUCTURE','W5_COMBINED'):
            ps=[p for p in pairs if p['task_id']==task and p['mutation']==mode and p['mutation_seed']==17]
            chosen.extend(ps[:2])
    for p in chosen:
        for key in ('reference_snapshot','candidate_snapshot'):
            folder=Path(p[key]).parent
            shutil.copytree(FULL/folder,PUB/folder,dirs_exist_ok=True)
    write(PUB/'ground_truth/pairs.json',chosen)
    from w4.validate_dataset import validate
    from app.mutations_w5 import MODES
    val=validate(PUB,mutation_modes=('M0',*MODES))
    write(PUB/'metadata.json',{'benchmark_version':'0.5.0','scope':'published loader sample; not full matrix',
        'source':'results/w5/benchmark_v0.5.0','task_ids':['T001','T004','T007'],'seed':17,
        'snapshot_count':val['snapshot_count'],'pair_count':val['pair_count']})
    rubric=Path(r'C:\Users\admin\Downloads\TheoDoi_TienDo_11_Nhom_DonGian_2026updated.xlsm')
    write(OUT/'rubric.json',{'source_file':rubric.name,'source_sha256':sha(rubric),'sheet':'Theo dõi 11 nhóm',
        'group_cell':'H3','group':'KH1-N5','members_cell':'H4','members':['Vũ Văn Bình','Nguyễn Thành Trung'],
        'week_cell':'A45','week':'W5 25/10 – 31/10','requirement_cell':'H45',
        'requirement':'Tạo bộ mutation: đổi id/class/text/order/structure; version benchmark.',
        'criteria':[{'cell':f'B{r}','criterion':c,'maximum_points':v} for r,c,v in [(46,'Submit đúng hạn',1),(47,'Đủ nội dung + evidence',2),(48,'Bám sát deadline / deliverable',2),(49,'GitHub + phân chia công việc',2),(50,'Chất lượng chuyên môn / báo cáo',1),(51,'Tiêu chí chuyên môn riêng',2)]],
        'grading':'Không tự điền điểm hoặc xác nhận nộp thay GVHD.'})
    with (OUT/'metrics.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['metric','value','unit','scope','source'])
        for mode,v in summary['by_mutation'].items():
            w.writerow(['functionality_pass',v['passed'],'runs',mode,'Evidence/W05/results.csv'])
            w.writerow(['functionality_total',v['total'],'runs',mode,'Evidence/W05/results.csv'])
        for metric,value,unit,scope,src in [('software_tests_passed',85,'tests','full regression','test-results.txt'),('runtime_snapshots',summary['snapshot_count'],'snapshots','full dataset','summary.json'),('evaluation_pairs',summary['pair_count'],'pairs','full dataset','summary.json'),('locator_probes',65,'probes','five selected frozen locators','locator-probe.json')]:
            w.writerow([metric,value,unit,scope,'Evidence/W05/'+src])
        if (OUT/'release-test-results.txt').exists():
            release=(OUT/'release-test-results.txt').read_text(encoding='utf-8-sig')
            if 'Ran 63 tests' not in release or not release.rstrip().endswith('OK'): raise ValueError('Release regression failed')
            w.writerow(['release_software_tests_passed',63,'tests','independent W5 on main','Evidence/W05/release-test-results.txt'])
    version={'benchmark_version':'0.5.0','partition':'development','week':'W5','teacher_requirement':'Evidence/W05/rubric.json',
        'task_file':'tasks/tasks_w4.json','task_count':30,'task_sha256':sha(ROOT/'tasks/tasks_w4.json'),
        'data_seed':'seed_v1','data_seed_sha256':sha(ROOT/'data/seed_v1.json'),
        'mutation_modes':['M0',*MODES],'development_seeds':[17,23],
        'source_contract':'LF SHA-256 per file, separate from Git HEAD because working tree may be dirty',
        'source_sha256_lf':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for folder in ('app','w4','w5','baseline','dom_snapshot','tasks') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and p.suffix in ('.py','.js','.html','.css','.json') and '__pycache__' not in p.parts},
        'held_out':{'reserved_for':'W11','accessed':False,'seeds':None},
        'version_policy':'Change transformation, seed set, tasks, or checker => new version; do not overwrite 0.5.0 evidence.',
        'run_command':'python -m w5.run --output runs/w5-reproduction --seeds 17 23',
        'probe_command':'python -m w5.probe --output runs/w5-probe-reproduction',
        'scope':'Oracle verifies business preservation; not A1/A2 success or self-healing.'}
    write(ROOT/'data/benchmark_v0.5.0.json',version)
    previous=json.loads((OUT/'manifest.json').read_text(encoding='utf-8')) if (OUT/'manifest.json').exists() else {}
    files=[p for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json']
    files.extend(p for p in PUB.rglob('*') if p.is_file())
    files.append(ROOT/'data/benchmark_v0.5.0.json')
    write(OUT/'manifest.json',{'version':'0.5.0','scope':'W5 five mutation axes plus combined; development data',
        'github':previous.get('github',{'status':'prepared_local_pending_peer_review','milestone':None,'issues':[],'pull_request':None,'tag':None}),
        'git_head_at_packaging':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'files':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}})
    print('Built Evidence/W05, published sample and benchmark version manifest')


if __name__=='__main__': main()
