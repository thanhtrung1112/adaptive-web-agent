"""Validate schema, HTML bytes and evaluation-only pair references for real-app snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
from candidates.features import controls
from dom_snapshot.parser import validate_snapshot
from .run import write_json


# Reject bool (a Python int subclass), missing seeds and out-of-range metadata.
def validate_seed(value):
    if type(value) is not int or not 0 <= value <= 2147483647:
        raise ValueError('Invalid mutation_seed: expected integer in 0..2147483647')


# Validate all files, including snapshots without a ranking pair (e.g. final states).
def validate(root, *, write_report=True, mutation_modes=('M0','M1','M2','M3')):
    root = Path(root).resolve()
    hashes, snapshots = {}, {}
    paths = sorted((root/'snapshots').glob('*/features.json'))
    if not paths: raise ValueError('Dataset has no snapshots')
    for path in paths:
        snap = validate_snapshot(json.loads(path.read_text(encoding='utf-8')))
        html = path.with_name('dom.html')
        if hashlib.sha256(html.read_bytes()).hexdigest()!=snap['html_sha256']: raise ValueError(f'HTML checksum mismatch: {html}')
        for file in (path,html): hashes[file.relative_to(root).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
        key = path.relative_to(root).as_posix()
        snapshots[key]=snap
        validate_seed(snap['provenance'].get('mutation_seed'))
        if snap['provenance'].get('data_seed')!='seed_v1': raise ValueError('Missing data seed')
        if snap['provenance'].get('mutation') not in mutation_modes: raise ValueError('Invalid mutation metadata')
    pairs = json.loads((root/'ground_truth/pairs.json').read_text(encoding='utf-8'))
    seen = set()
    for pair in pairs:
        validate_seed(pair.get('mutation_seed'))
        if pair.get('mutation') not in set(mutation_modes) - {'M0'}:
            raise ValueError('Pair mutation must be M1/M2/M3')
        if type(pair.get('step_index')) is not int or pair['step_index'] < 0:
            raise ValueError('Invalid pair step_index')
        if any(pair.get(k) not in snapshots for k in ('reference_snapshot','candidate_snapshot')):
            raise ValueError('Pair references unknown snapshot')
        key=(pair['task_id'],pair['step_index'],pair['mutation'],pair['mutation_seed'])
        if key in seen: raise ValueError('Duplicate evaluation pair')
        seen.add(key)
        original = snapshots[pair['reference_snapshot']]
        candidate = snapshots[pair['candidate_snapshot']]
        if original['task_id'] != pair['task_id'] or candidate['task_id'] != pair['task_id']:
            raise ValueError('Pair task_id mismatch')
        if original['state'] != candidate['state']:
            raise ValueError('Pair state mismatch')
        if original['provenance']['mutation']!='M0': raise ValueError('Reference must be M0')
        if candidate['provenance']['mutation']!=pair['mutation'] or candidate['provenance']['mutation_seed']!=pair['mutation_seed']: raise ValueError('Pair provenance mismatch')
        a = next(c for c in controls(original) if c['element_id']==pair['reference_element_id'])
        b = next(c for c in controls(candidate) if c['element_id']==pair['target_element_id'])
        if (a['tag'],a['type'],a['name'])!=(b['tag'],b['type'],b['name']): raise ValueError('Target semantic identity mismatch')
    result = {'snapshot_count':len(paths),'pair_count':len(pairs),'schema_version':'0.1',
              'schema_html_hash_pair_checks':'passed','file_sha256':hashes}
    # Read-only verification preserves already-published evidence and its manifest hashes.
    if write_report:
        write_json(root/'validation.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('dataset',type=Path)
    parser.add_argument('--check-only', action='store_true', help='Validate without overwriting validation.json')
    args = parser.parse_args()
    result=validate(args.dataset, write_report=not args.check_only)
    print(f'PASS: {result["snapshot_count"]} snapshots, {result["pair_count"]} evaluation pairs')


if __name__=='__main__': main()
