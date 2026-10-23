"""Publish compact evidence + representative snapshots; full replay data stays under runs/."""
import argparse
import json
import shutil
from pathlib import Path
from .run import write_json
from .validate_dataset import validate

SAMPLE_TASKS = ('T001','T004','T006','T009','T024','T030')


# Keep the last pre-action state for each selected task/variant, including the two-line form.
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); summary=json.loads((args.run/'summary.json').read_text(encoding='utf-8'))
    if not summary['all_passed']: parser.error('Refuse to publish incomplete/failed functionality run')
    args.output.mkdir(parents=True,exist_ok=False)
    pairs=json.loads((args.run/'ground_truth/pairs.json').read_text(encoding='utf-8'))
    picked={}
    for pair in pairs:
        if pair['task_id'] not in SAMPLE_TASKS: continue
        key=(pair['task_id'],pair['mutation'],pair['mutation_seed'])
        if key not in picked or pair['step_index']>picked[key]['step_index']: picked[key]=pair
    pairs=list(picked.values())
    for path in sorted({p[key] for p in pairs for key in ('reference_snapshot','candidate_snapshot')}):
        directory=Path(path).parent
        shutil.copytree(args.run/directory,args.output/directory)
    for name in ('metadata.json','summary.json','results.csv','traces.json'):
        shutil.copyfile(args.run/name,args.output/name)
    write_json(args.output/'ground_truth/pairs.json',pairs)
    write_json(args.output/'coverage.json',{'scope':'representative last pre-action snapshot per selected task, NOT full replay snapshots',
        'sample_tasks':SAMPLE_TASKS,'sample_pairs':len(pairs),
        'full_replay_expected_rows':summary['expected_rows'],'full_replay_completed_rows':summary['completed_rows'],
        'full_replay_snapshot_count':summary['snapshot_count'],'regenerate_full_dataset':'python -m w4.run --seeds 7'})
    result=validate(args.output)
    write_json(args.output/'manifest.json',{'dataset_version':'w4-real-app-v1','partition':'development',
        'held_out':'not accessed; reserved for W11','representative_snapshots':result['snapshot_count'],
        'representative_pairs':result['pair_count'],'full_replay_summary_file':'summary.json',
        'scope_note':'summary.json counts full run; validation.json counts published subset'})
    print(args.output.resolve())


if __name__=='__main__': main()
