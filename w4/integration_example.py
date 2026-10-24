"""Input adapter smoke test using existing W3 ranker; this is NOT an embedding benchmark."""
import argparse
import json
from pathlib import Path
from candidates.generator import rank
from .dataset import ranking_inputs


# Trung replaces rank() with embedding ranking; ground truth stays on evaluator side.
def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('dataset',type=Path)
    args=parser.parse_args()
    pairs=json.loads((args.dataset/'ground_truth/pairs.json').read_text(encoding='utf-8'))
    if not pairs: parser.error('No evaluation pairs')
    pair=pairs[0]
    descriptor,candidates=ranking_inputs(args.dataset,pair)
    ranking=rank(descriptor,candidates,top_k=5)
    print(json.dumps({'scope':'adapter smoke using W3 ranker, NOT embedding',
                      'ranking':ranking,'target_rank':next((i+1 for i,r in enumerate(ranking) if r['element_id']==pair['target_element_id']),None)},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
