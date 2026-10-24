"""Đánh giá ranking trên dữ liệu mutation thật của W4 (cặp snapshot trước/sau do `w4.run` sinh).

  python -m w4.run --seeds 7 --output runs/w4-trung-full
  python -m ranking.evaluate_w4 --dataset runs/w4-trung-full --encoder hash

Quy tắc: ranker chỉ nhận (descriptor, candidates) từ `w4.dataset.ranking_inputs`.
`target_element_id` chỉ được đọc SAU khi ranker trả kết quả, để chấm điểm.
"""
import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from ranking.encoders import DEFAULT_MODEL, make_encoder
from ranking.rank import rank
from w4.dataset import ranking_inputs

ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]
MODES = ("features", "embedding", "hybrid")
META_KEYS = ("git_commit", "git_status", "task_sha256", "development_seeds", "data_seed", "mutations")


def load_pairs(root):
    data = json.loads((Path(root) / "ground_truth" / "pairs.json").read_text(encoding="utf-8"))
    return data["pairs"] if isinstance(data, dict) else data


def split_of(task_id):
    """Chia theo task (M1, M2, M3 của cùng task nằm cùng phía) để dev và test không chung task."""
    return "test" if int(hashlib.md5(task_id.encode()).hexdigest(), 16) % 3 == 0 else "dev"


def _metrics(ranks):
    n = len(ranks)
    if n == 0:
        return {"pairs": 0}
    return {"pairs": n, "top1": round(sum(r == 1 for r in ranks) / n, 3),
            "top3": round(sum(r is not None and r <= 3 for r in ranks) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 3)}


def _run(root, pairs, encoder, mode, alpha, record_time=False):
    ranks, times, misses = [], [], []
    for p in pairs:
        descriptor, candidates = ranking_inputs(root, p)  # chỉ hai thứ này đi vào ranker
        t0 = time.perf_counter()
        order = [r["element_id"] for r in rank(descriptor, candidates, encoder, mode, alpha, top_k=10)]
        times.append((time.perf_counter() - t0) * 1000)
        target = p["target_element_id"]  # chỉ đọc sau khi ranker đã trả kết quả
        r = order.index(target) + 1 if target in order else None
        ranks.append(r)
        if r != 1:
            misses.append({"task_id": p["task_id"], "step_index": p["step_index"], "mutation": p["mutation"],
                           "mode": mode, "target": target, "top1": order[0], "rank_of_target": r})
    return (ranks, times, misses) if record_time else ranks


def evaluate(root, encoder, alphas=ALPHAS):
    pairs = load_pairs(root)
    part = {s: [p for p in pairs if split_of(p["task_id"]) == s] for s in ("dev", "test")}
    # chọn alpha trên dev (MRR cao nhất; hòa thì chọn alpha nhỏ hơn), không nhìn test
    dev_mrr = {a: _metrics(_run(root, part["dev"], encoder, "hybrid", a))["mrr"] for a in alphas}
    alpha = max(alphas, key=lambda a: (dev_mrr[a], -a))
    config = {"features": 1.0, "embedding": 0.0, "hybrid": alpha}

    ranks = {}  # (mode) -> list rank theo từng cặp, giữ thứ tự `pairs`
    latency, misses = {}, []
    for mode in MODES:
        ranks[mode], times, miss = _run(root, pairs, encoder, mode, config[mode], record_time=True)
        latency[mode] = {"median_ms": round(statistics.median(times), 2),
                         "p95_ms": round(sorted(times)[int(0.95 * (len(times) - 1))], 2)}
        misses += miss

    def group(select):
        idx = [i for i, p in enumerate(pairs) if select(p)]
        return {m: _metrics([ranks[m][i] for i in idx]) for m in MODES}

    by_mutation = {mu: {"all": group(lambda p, mu=mu: p["mutation"] == mu),
                        "test": group(lambda p, mu=mu: p["mutation"] == mu and split_of(p["task_id"]) == "test")}
                   for mu in sorted({p["mutation"] for p in pairs})}
    return {"pairs": len(pairs), "split_pairs": {s: len(v) for s, v in part.items()},
            "alpha_chosen_on_dev": alpha, "dev_mrr_by_alpha": dev_mrr,
            "overall": {"all": group(lambda p: True), "test": group(lambda p: split_of(p["task_id"]) == "test")},
            "by_mutation": by_mutation, "latency_ms_per_pair": latency, "misses": misses}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="thư mục chứa ground_truth/pairs.json và snapshots/")
    ap.add_argument("--encoder", choices=["hash", "sbert"], default="hash")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out")
    a = ap.parse_args()
    t0 = time.perf_counter()
    encoder = make_encoder(a.encoder, a.model)
    load_s = round(time.perf_counter() - t0, 2)
    res = evaluate(a.dataset, encoder)
    meta_file = Path(a.dataset) / "metadata.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    res.update(encoder=a.encoder, model=a.model if a.encoder == "sbert" else "hashing char n-gram (offline)",
               encoder_load_s=load_s, dataset=str(a.dataset), dataset_metadata={k: meta.get(k) for k in META_KEYS},
               note="Dữ liệu mutation phát triển (seed phát triển); không dùng held-out W11.")
    out = Path(a.out or f"results/w4/ranking_w4_{a.encoder}_v0.1/evaluation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"encoder={a.encoder} | {res['pairs']} cặp (dev {res['split_pairs']['dev']}, test {res['split_pairs']['test']}) | alpha chọn trên dev = {res['alpha_chosen_on_dev']}")
    print(f"{'mutation':9} | top-1 (tất cả cặp): features embedding hybrid | mrr: features embedding hybrid")
    for mu, g in res["by_mutation"].items():
        t = g["all"]
        print(f"{mu:9} | {'':>19}{t['features']['top1']:>8} {t['embedding']['top1']:>9} {t['hybrid']['top1']:>7} | "
              f"{'':>5}{t['features']['mrr']:>8} {t['embedding']['mrr']:>9} {t['hybrid']['mrr']:>7}")
    print("Độ trễ mỗi cặp (ms):", {m: v["median_ms"] for m, v in res["latency_ms_per_pair"].items()}, "| số ca chưa hạng 1:", len(res["misses"]))
    print("Đã ghi", out)


if __name__ == "__main__":
    main()
