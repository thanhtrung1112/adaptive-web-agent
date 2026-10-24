"""Đo ranking: features vs embedding vs hybrid, trên tập dev (chọn alpha) và tập test (báo cáo)."""
import argparse
import hashlib
import json
from pathlib import Path

from candidates.features import controls, load_state
from candidates.targets import build_targets
from ranking.encoders import DEFAULT_MODEL, make_encoder
from ranking.rank import rank
from ranking.stress import stress_mutate

KINDS = ["none", "ids", "labels", "combined", "flatten", "hard"]
ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]


def split_of(state):
    """Chia theo trạng thái (không theo phần tử) để dev và test không chung trang. Xác định, không phụ thuộc máy."""
    return "test" if int(hashlib.md5(state.encode()).hexdigest(), 16) % 3 == 0 else "dev"


def _ranks(targets, encoder, kind, mode, alpha, seed):
    out = []
    for st, eid, _css in targets:
        snap0 = load_state(st)
        desc = next(c for c in controls(snap0) if c["element_id"] == eid)
        cands = controls(stress_mutate(snap0, kind, seed))
        order = [r["element_id"] for r in rank(desc, cands, encoder, mode, alpha, top_k=10)]
        out.append(order.index(eid) + 1 if eid in order else None)
    return out


def _metrics(ranks):
    n = len(ranks)
    return {"targets": n, "top1": round(sum(r == 1 for r in ranks) / n, 3),
            "top3": round(sum(r is not None and r <= 3 for r in ranks) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 3)}


def evaluate(encoder, kinds=KINDS, alphas=ALPHAS, seed=0):
    targets, _ = build_targets()
    split = {s: [t for t in targets if split_of(t[0]) == s] for s in ("dev", "test")}
    res = {"split_sizes": {s: len(v) for s, v in split.items()}, "kinds": {}}
    for kind in kinds:
        # chọn alpha trên dev (MRR cao nhất; hòa thì chọn alpha nhỏ hơn), rồi báo cáo trên test
        dev = {a: _metrics(_ranks(split["dev"], encoder, kind, "hybrid", a, seed))["mrr"] for a in alphas}
        best = max(alphas, key=lambda a: (dev[a], -a))
        res["kinds"][kind] = {
            "alpha_chosen_on_dev": best,
            "test": {"features": _metrics(_ranks(split["test"], encoder, kind, "features", 1.0, seed)),
                     "embedding": _metrics(_ranks(split["test"], encoder, kind, "embedding", 0.0, seed)),
                     "hybrid": _metrics(_ranks(split["test"], encoder, kind, "hybrid", best, seed))}}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--encoder", choices=["hash", "sbert"], default="hash")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    res = evaluate(make_encoder(a.encoder, a.model))
    res.update(encoder=a.encoder, model=a.model if a.encoder == "sbert" else "hashing char n-gram (offline)",
               note="Mô phỏng trên snapshot; chưa phải mutation thật.")
    out = Path(f"results/w4/ranking_{a.encoder}_v0.1/evaluation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"encoder={a.encoder} | dev={res['split_sizes']['dev']} test={res['split_sizes']['test']} phần tử đích")
    print(f"{'kiểu đổi':10} {'alpha':>5} | top-1 test: {'features':>8} {'embedding':>9} {'hybrid':>7} | mrr: {'features':>8} {'embedding':>9} {'hybrid':>7}")
    for kind, r in res["kinds"].items():
        t = r["test"]
        print(f"{kind:10} {r['alpha_chosen_on_dev']:>5} | {'':>15}{t['features']['top1']:>8} {t['embedding']['top1']:>9} {t['hybrid']['top1']:>7} | "
              f"{'':>5}{t['features']['mrr']:>8} {t['embedding']['mrr']:>9} {t['hybrid']['mrr']:>7}")
    print("Đã ghi", out)


if __name__ == "__main__":
    main()
