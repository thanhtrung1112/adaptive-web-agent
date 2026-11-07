"""Đo tác dụng của tie-break theo thứ tự dòng (ordinal) trên biến đổi mô phỏng của snapshot M0.

Mỗi control thao tác được của mỗi trang M0 (loại trùng theo html_sha256) lần lượt là phần tử đích; trang được biến đổi bằng
candidates.mutate rồi heal() tìm lại. element_id giữ nguyên qua mutate, chỉ dùng để chấm. Kết quả: chữa đúng, chữa nhầm, bỏ cuộc.
    python -m healing.eval_order --dataset runs/w4-trung-full --out results/w6/offline/order_tiebreak/evaluation.json
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from candidates.mutate import mutate
from healing.descriptor import build_descriptor, controls_with_xpath
from healing.heal import heal

KINDS = ("ids", "labels", "wrap", "decoy", "combined")
SEEDS = (0, 1, 2)
CONFIGS = {
    "A_dom_order_guess": dict(min_margin=0.0),
    "B_abstain_on_tie": dict(min_margin=0.02),
    "C_ordinal_tiebreak": dict(min_margin=0.02, use_order=True),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="runs/w4-trung-full")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    root = Path(a.dataset)
    pages, seen = [], set()
    for d in sorted((root / "snapshots").glob("M0-s0-*")):
        snap = json.loads((d / "features.json").read_text(encoding="utf-8"))
        if snap["html_sha256"] not in seen:
            seen.add(snap["html_sha256"])
            pages.append((d.name, snap))
    tally = defaultdict(Counter)
    bad = defaultdict(set)
    for name, snap in pages:
        ctrls = controls_with_xpath(snap)
        descs = {c["element_id"]: build_descriptor(snap, c["element_id"]) for c in ctrls}
        for kind in KINDS:
            for seed in SEEDS:
                cands = controls_with_xpath(mutate(snap, kind, seed))
                present = {c["element_id"] for c in cands}
                for eid, desc in descs.items():
                    if eid not in present:
                        continue
                    for cname, cfg in CONFIGS.items():
                        r = heal(desc, cands, mode="features", **cfg)
                        k = "abstain" if r["status"] == "abstain" else ("correct" if r["eid"] == eid else "WRONG")
                        tally[(kind, cname)][k] += 1
                        if k != "correct":
                            bad[(kind, cname, k)].add(name)
    rows = []
    print(f"{len(pages)} trang M0 duy nhất, {len(SEEDS)} seed mỗi kiểu")
    print(f"{'kiểu':9} {'cấu hình':20} {'đúng':>6} {'nhầm':>5} {'bỏ cuộc':>8}")
    for (kind, cname), c in sorted(tally.items()):
        rows.append({"kind": kind, "config": cname, **{k: c[k] for k in ("correct", "WRONG", "abstain")}})
        print(f"{kind:9} {cname:20} {c['correct']:>6} {c['WRONG']:>5} {c['abstain']:>8}")
    print("trang có lỗi (A/B/C):", {f"{k[0]}/{k[1][:1]}/{k[2]}": sorted(v)[:4] for k, v in bad.items()})
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"dataset": str(root), "pages": len(pages), "seeds": SEEDS, "configs": CONFIGS,
                                 "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Đã ghi", p)


if __name__ == "__main__":
    main()
