"""Ranking input adapter: no oracle import, task goals or target answers passed to rank()."""
import json
from pathlib import Path
from candidates.features import controls


# Reject paths outside the supplied dataset; data must be local schema v0.1 snapshots.
def read_snapshot(root, relative):
    root = Path(root).resolve()
    path = (root/relative).resolve()
    if root not in path.parents: raise ValueError('Snapshot path escapes dataset')
    return json.loads(path.read_text(encoding='utf-8'))


# Only source descriptor + candidate features cross the ranking interface.
def ranking_inputs(root, pair):
    reference = controls(read_snapshot(root,pair['reference_snapshot']))
    descriptor = next(c for c in reference if c['element_id']==pair['reference_element_id'])
    return descriptor, controls(read_snapshot(root,pair['candidate_snapshot']))
