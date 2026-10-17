"""Đo: phần tử đúng nằm ở hạng mấy trong danh sách ứng viên sau khi giao diện bị đổi (mô phỏng trên snapshot)."""
import json
import statistics
from pathlib import Path

from candidates.features import controls, load_state
from candidates.generator import WEIGHTS, rank
from candidates.mutate import mutate
from candidates.targets import build_targets

KINDS = ["none", "ids", "labels", "wrap", "decoy", "combined"]
OUT = Path("results/w3/candidate_generator_v0.1/evaluation.json")


def evaluate(kinds=KINDS, seed=0, top_k=10):
    """Trả về (bảng số liệu theo kiểu đổi, danh sách ca sai)."""
    targets, _ = build_targets()
    table, misses = {}, []
    for kind in kinds:
        ranks, sizes = [], []
        for st, eid, css in targets:
            snap0 = load_state(st)
            desc = next(c for c in controls(snap0) if c["element_id"] == eid)
            cands = controls(mutate(snap0, kind, seed))
            order = [r["element_id"] for r in rank(desc, cands, top_k)]
            r = order.index(eid) + 1 if eid in order else None
            ranks.append(r)
            sizes.append(len(cands))
            if r != 1:
                misses.append({"mutation": kind, "state": st, "selector": css, "target": eid,
                               "top1": order[0], "rank_of_target": r})
        n = len(ranks)
        table[kind] = {"targets": n,
                       "top1": round(sum(r == 1 for r in ranks) / n, 3),
                       "top3": round(sum(r is not None and r <= 3 for r in ranks) / n, 3),
                       "top5": round(sum(r is not None and r <= 5 for r in ranks) / n, 3),
                       "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
                       "mean_controls": round(statistics.mean(sizes), 1)}
    return table, misses


def main(seed=0):
    table, misses = evaluate(seed=seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"snapshot_set": "dom_samples_expanded_v0.1", "seed": seed, "weights": WEIGHTS,
               "note": "Mô phỏng trên snapshot; chưa phải mutation thật của app (W4).",
               "results": table, "misses": misses}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{'mutation':9} {'targets':>7} {'top1':>6} {'top3':>6} {'top5':>6} {'mrr':>6}")
    for kind, row in table.items():
        print(f"{kind:9} {row['targets']:>7} {row['top1']:>6} {row['top3']:>6} {row['top5']:>6} {row['mrr']:>6}")
    print(f"Ca sai: {len(misses)}. Đã ghi {OUT}")


if __name__ == "__main__":
    main()
