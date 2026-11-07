"""B2: đánh giá offline healing trên dataset W4/W5 (cặp trước/sau có ground truth).

Với mỗi cặp: descriptor lấy từ snapshot M0 (có ord, ord_n), ứng viên lấy từ snapshot đã mutate. Ground truth
(`target_element_id`) chỉ dùng để chấm. Kết quả mỗi lượt: correct | WRONG (chữa nhầm) | abstain (bỏ cuộc).
    python -m healing.evaluate --dataset <thư mục dataset> --out results/w6/offline/evaluation.json [--encoder hash]
Chia dev/test theo task như W4 (ranking.evaluate_w4.split_of). Chưa chọn ngưỡng ở đây (việc B3, chỉ trên dev).
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from candidates.features import controls
from healing.heal import heal
from healing.ordinal import add_ordinals
from ranking.evaluate_w4 import load_pairs, split_of
from w4.dataset import read_snapshot

CONFIGS = {
    "A_features_dom_guess": dict(mode="features", min_margin=0.0),
    "B_features_abstain": dict(mode="features", min_margin=0.02),
    "C_features_ordinal": dict(mode="features", min_margin=0.02, use_order=True),
}
HYBRID = {"D_hybrid_hash_ordinal": dict(mode="hybrid", alpha=0.25, min_margin=0.02, use_order=True)}


def verdict(r, target):
    return "abstain" if r["status"] == "abstain" else ("correct" if r["eid"] == target else "WRONG")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--encoder", choices=["none", "hash"], default="none", help="hash: thêm cấu hình hybrid (offline)")
    a = ap.parse_args()
    root, pairs = Path(a.dataset), load_pairs(a.dataset)
    cfgs = dict(CONFIGS)
    encoder = None
    if a.encoder == "hash":
        from ranking.encoders import HashingEncoder
        encoder = HashingEncoder()
        cfgs.update(HYBRID)
    tally = defaultdict(Counter)   # (mutation, seed, split, config) -> verdict
    by_mut = defaultdict(Counter)  # (mutation, config) -> verdict, mọi seed
    uniq = defaultdict(Counter)    # như trên nhưng mỗi biến thể HTML duy nhất chỉ đếm một lần (loại seed trùng)
    uniq_seen = set()
    variants = defaultdict(set)    # (task, step, mutation) -> tập html_sha256 của các seed
    misses = []
    for p in pairs:
        ref = add_ordinals(controls(read_snapshot(root, p["reference_snapshot"])))
        desc = next(c for c in ref if c["element_id"] == p["reference_element_id"])
        desc = {k: v for k, v in desc.items() if k != "element_id"}
        cand_snap = read_snapshot(root, p["candidate_snapshot"])
        cands = controls(cand_snap)
        variants[(p["task_id"], p["step_index"], p["mutation"])].add(cand_snap.get("html_sha256", ""))
        sp = split_of(p["task_id"])
        ukey = (p["task_id"], p["step_index"], p["mutation"], cand_snap.get("html_sha256", ""))
        is_new = ukey not in uniq_seen
        uniq_seen.add(ukey)
        for name, cfg in cfgs.items():
            r = heal(desc, cands, encoder=encoder, **cfg)
            v = verdict(r, p["target_element_id"])
            tally[(p["mutation"], p.get("mutation_seed", 0), sp, name)][v] += 1
            by_mut[(p["mutation"], name)][v] += 1
            if is_new:
                uniq[(p["mutation"], name)][v] += 1
            if v == "WRONG":
                misses.append({"config": name, "task_id": p["task_id"], "step_index": p["step_index"],
                               "mutation": p["mutation"], "seed": p.get("mutation_seed", 0), "target": p["target_element_id"],
                               "chosen": r["eid"], "score": r["score"], "margin": r["margin"], "via": r["via"]})
    # Số biến thể thật sự khác nhau giữa các seed (seed trùng biến thể thì không thêm đa dạng)
    dup = defaultdict(lambda: [0, 0])
    for (task, step, mut), shas in variants.items():
        dup[mut][0] += 1
        dup[mut][1] += 1 if len(shas) == 1 else 0
    seeds_per = defaultdict(set)
    for p in pairs:
        seeds_per[p["mutation"]].add(p.get("mutation_seed", 0))

    muts = sorted({k[0] for k in tally})
    print(f"{len(pairs)} cặp | cấu hình: {', '.join(cfgs)}")
    rows = []
    for name in cfgs:
        print(f"\n== {name}")
        print(f"{'mutation':13}{'seed':>5}{'split':>6}{'đúng':>7}{'NHẦM':>6}{'bỏ':>5}")
        for mut in muts:
            for seed in sorted({k[1] for k in tally if k[0] == mut}):
                for sp in ("dev", "test"):
                    c = tally.get((mut, seed, sp, name))
                    if not c:
                        continue
                    rows.append({"config": name, "mutation": mut, "seed": seed, "split": sp,
                                 "correct": c["correct"], "wrong": c["WRONG"], "abstain": c["abstain"]})
                    print(f"{mut:13}{seed:>5}{sp:>6}{c['correct']:>7}{c['WRONG']:>6}{c['abstain']:>5}")
    print("\nBiến thể trùng giữa các seed (cùng task, bước, mutation):")
    for mut, (n, d) in sorted(dup.items()):
        if len(seeds_per[mut]) > 1:
            print(f"  {mut:13} {d}/{n} nhóm có HTML giống hệt ở mọi seed")
    summary = []
    print("\nTỔNG THEO MODE: đúng/NHẦM/bỏ cuộc | tất cả lượt (mọi seed) | biến thể HTML duy nhất")
    for name in cfgs:
        print(f"== {name}")
        for mut in muts:
            a_, u_ = by_mut[(mut, name)], uniq[(mut, name)]
            summary.append({"config": name, "mutation": mut,
                            "all": {"correct": a_["correct"], "wrong": a_["WRONG"], "abstain": a_["abstain"]},
                            "unique": {"correct": u_["correct"], "wrong": u_["WRONG"], "abstain": u_["abstain"]}})
            print(f"  {mut:13} {a_['correct']:>5}/{a_['WRONG']:>3}/{a_['abstain']:>3}  |  {u_['correct']:>5}/{u_['WRONG']:>3}/{u_['abstain']:>3}")
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"dataset": str(root), "pairs": len(pairs), "configs": cfgs, "rows": rows, "by_mutation": summary,
                                   "identical_across_seeds": {m: {"groups": n, "identical": d} for m, (n, d) in dup.items()},
                                   "wrong": misses}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Đã ghi", out)


if __name__ == "__main__":
    main()
