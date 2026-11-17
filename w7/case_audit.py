"""Build a separate development challenge set, audit triggers, never call a model.

These are DOM fixtures, not additional MiniBiz task-success measurements.
Expected selectors below are used ONLY by this evaluator and never in packets.
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

from dom_snapshot.capture import capture, save_snapshot
from healing.descriptor import build_descriptor
from healing.heal import heal
from w6.freeze import digest, write_json
from w6.run_heal import POLICY
from w7.context import runtime_candidates
from w7.contracts import make_request
from w7.target_check import check_found

CASES = [
    {"id": "C01", "objective": "Lưu thông tin khách hàng, không lưu nhân viên.", "action": "click",
     "before": '<form action="/save"><section><h2>Khách hàng</h2><button>Lưu</button></section></form>',
     "after": '<form action="/save"><section><h2>Nhân viên</h2><button>Lưu</button></section><section><h2>Khách hàng</h2><button>Lưu</button></section></form>',
     "expected_selector": "section:nth-child(2) button", "expected_decision": "select"},
    {"id": "C02", "objective": "Lưu thông tin khách hàng.", "action": "click",
     "before": '<form action="/save"><section><button>Lưu</button></section></form>',
     "after": '<form action="/save"><section><button>Lưu</button></section><section><button>Lưu</button></section></form>',
     "expected_selector": None, "expected_decision": "abstain"},
    {"id": "C03", "objective": "Nhập số lượng cho sản phẩm SKU-100.", "action": "fill",
     "before": '<form action="/order"><section><h2>SKU-100</h2><label>Số lượng<input type="number"></label></section></form>',
     "after": '<form action="/order"><section><h2>SKU-200</h2><label>Số lượng<input type="number"></label></section><section><h2>SKU-100</h2><label>Số lượng<input type="number"></label></section></form>',
     "expected_selector": "section:nth-child(2) input", "expected_decision": "select"},
    {"id": "C04", "objective": "Lưu thông tin khách hàng.", "action": "click",
     "before": '<form action="/save"><button>Lưu</button></form>',
     "after": '<main>Chức năng hiện không khả dụng.</main>',
     "expected_selector": None, "expected_decision": "abstain"},
]


def audit(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    calibration = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            with browser.new_page() as page:
                for case in CASES:
                    folder = out / case["id"]
                    page.set_content(case["before"])
                    html, before = capture(page, case["id"] + "-before", case["id"], "before", {})
                    save_snapshot(folder / "before", html, before)
                    loc = page.locator("button" if case["action"] == "click" else "input")
                    eid = loc.evaluate("el => 'e' + (Array.from(document.querySelectorAll('*')).indexOf(el) + 1)")
                    descriptor = build_descriptor(before, eid)
                    page.set_content(case["after"])
                    html, after = capture(page, case["id"] + "-after", case["id"], "after", {})
                    save_snapshot(folder / "after", html, after)
                    candidates = runtime_candidates(after)
                    result = heal(descriptor, candidates, mode=POLICY["mode"], min_margin=POLICY["min_margin"],
                                  min_score=POLICY["min_score"], use_order=POLICY["use_order"])
                    packet, bindings = make_request(descriptor, candidates, case["action"], result, case["objective"])
                    write_json(folder / "request.json", packet)
                    # Ground truth stays in an evaluator-only sidecar.
                    expected = None
                    target_xpath = None
                    if case["expected_selector"]:
                        locator = page.locator(case["expected_selector"])
                        target_eid = locator.evaluate("el => 'e' + (Array.from(document.querySelectorAll('*')).indexOf(el) + 1)")
                        target_xpath = next(c["xpath"] for c in candidates if c["element_id"] == target_eid)
                        expected = next(cid for cid, xpath in bindings.items() if xpath == target_xpath)

                    for candidate in candidates:
                        diagnostic = check_found(
                            descriptor,
                            candidate,
                            case["objective"],
                            threshold=0.0,
                        )
                        label_found = bool(
                            target_xpath and candidate["xpath"] == target_xpath
                        )

                        calibration.append({
                            "case_id": case["id"],
                            "score": diagnostic["score"],
                            "label_found": label_found,
                        })

                        print(
                            f"[CALIBRATION] {case['id']} "
                            f"score={diagnostic['score']} "
                            f"label_found={label_found} "
                            f"text={candidate.get('text', '')!r} "
                            f"context={candidate.get('context_text', '')!r}"
                        )

                    write_json(folder / "evaluation-only.json", {"expected_decision": case["expected_decision"], "expected_candidate_id": expected})
                    rows.append({"case_id": case["id"], "semantic_status": result["status"], "reason": result["reason"],
                                 "candidates": len(bindings), "natural_fallback": result["status"] == "abstain" and bool(bindings)})
        finally:
            browser.close()
    # Select a dev threshold by balanced accuracy on labelled candidate-vs-wrong-target pairs.
    labelled = [r for r in calibration if r["score"] is not None]
    observed_scores = sorted({r["score"] for r in labelled})
    thresholds = [0.0, 1.0] + [(a + b) / 2 for a, b in zip(observed_scores, observed_scores[1:])]
    best = None
    for threshold in thresholds:
        tp = sum(r["label_found"] and r["score"] >= threshold for r in labelled)
        tn = sum((not r["label_found"]) and r["score"] < threshold for r in labelled)
        positives = sum(r["label_found"] for r in labelled)
        negatives = len(labelled) - positives
        sensitivity = tp / positives if positives else 0.0
        specificity = tn / negatives if negatives else 0.0
        metric = (sensitivity + specificity) / 2
        candidate = (metric, -abs(threshold - 0.5), -threshold, threshold, sensitivity, specificity)
        if best is None or candidate > best:
            best = candidate
    threshold_record = {"scope": "development DOM fixtures only", "threshold": best[3] if best else 0.2,
                        "balanced_accuracy": best[0] if best else None,
                        "sensitivity": best[4] if best else None, "specificity": best[5] if best else None,
                        "candidate_count": len(labelled), "not_held_out": True}
    write_json(out / "target-threshold.json", threshold_record)
    write_json(out / "audit.json", {"scope": "Development DOM fixtures; no model calls or MiniBiz task-success claim",
                                    "cases": rows, "llm_requests": 0,
                                    "target_threshold": threshold_record})
    write_json(out / "checksums.json", {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob("*")) if p.is_file()})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for row in audit(args.output):
        print(row["case_id"], row["semantic_status"], row["reason"], "fallback=" + str(row["natural_fallback"]))


if __name__ == "__main__":
    main()
