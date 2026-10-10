"""Chạy baseline B0 (CSS / XPath) trên MiniBiz v1 và ghi kết quả.

  python -m baseline.run_baseline --mode both
Yêu cầu: MiniBiz đang chạy (python -m uvicorn app.main:app --port 8000) trên cùng thư mục repo,
vì runner reset database trực tiếp qua app.seed.reset_database() giữa các task.
"""
import argparse
import csv
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.seed import reset_database
from baseline.checker import check_all
from baseline.scripts import SCRIPTS

ROOT = Path(__file__).resolve().parent.parent
ACTION_TIMEOUT_MS = 3000


def load_tasks():
    return json.loads((ROOT / "tasks" / "pilot_tasks.json").read_text(encoding="utf-8"))


def run_step(page, base, step, mode, dl_path):
    if step["do"] == "goto":
        page.goto(base + step["url"])
        return None
    loc = page.locator(step["css"] if mode == "css" else "xpath=" + step["xpath"])
    if step["do"] == "fill":
        loc.fill(step["value"])
    elif step["do"] == "select":
        loc.select_option(label=step["label"])
    elif step["do"] == "click":
        loc.click()
        page.wait_for_load_state("load")
    elif step["do"] == "download":
        with page.expect_download() as info:
            loc.click()
        dl_path.parent.mkdir(parents=True, exist_ok=True)
        info.value.save_as(dl_path)
        return dl_path
    return None


def run_task(browser, base, task, mode, out):
    reset_database()
    ctx = browser.new_context(accept_downloads=True)  # context mới cho mỗi task: không dính phiên cũ
    page = ctx.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    steps, done, failed, error, dl = SCRIPTS[task["id"]], 0, None, "", None
    t0 = time.perf_counter()
    for i, step in enumerate(steps):
        try:
            dl = run_step(page, base, step, mode, out / "downloads" / f"{task['id']}_{mode}.csv") or dl
            done += 1
        except Exception as e:  # noqa: BLE001
            failed, error = i, str(e).strip().splitlines()[0][:200]
            break
    page.wait_for_timeout(100)
    elapsed = time.perf_counter() - t0
    if failed is None:
        ok, msg = check_all(lambda p: ctx.request.get(base + p).json(), task, dl)
    else:
        ok, msg = False, "bước thất bại trước khi chấm"
    ctx.close()
    return {"task_id": task["id"], "module": task["module"], "difficulty": task["difficulty"], "mode": mode,
            "mutation": "M0", "success": ok, "steps_total": len(steps), "steps_done": done,
            "failed_step": failed if failed is not None else "",
            "failed_locator": ((steps[failed].get("css") if mode == "css" else steps[failed].get("xpath"))
                               if failed is not None else ""),
            "error": error, "check": msg, "seconds": round(elapsed, 2)}


def summarize(rows):
    out = {}
    for mode in sorted({r["mode"] for r in rows}):
        rs = [r for r in rows if r["mode"] == mode]
        out[mode] = {"tasks": len(rs), "success": sum(r["success"] for r in rs),
                     "success_rate": round(sum(r["success"] for r in rs) / len(rs), 3),
                     "median_seconds": round(statistics.median(r["seconds"] for r in rs), 2),
                     "by_module": {m: f"{sum(r['success'] for r in rs if r['module'] == m)}/{sum(1 for r in rs if r['module'] == m)}"
                                   for m in sorted({r["module"] for r in rs})}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["css", "xpath", "both"], default="both")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--tasks", nargs="*", help="Lọc theo ID, ví dụ T001 T006")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()

    tasks = [t for t in load_tasks() if not a.tasks or t["id"] in a.tasks]
    modes = ["css", "xpath"] if a.mode == "both" else [a.mode]
    out = ROOT / "runs" / f"baseline_M0_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not a.headed)
        for mode in modes:
            for t in tasks:
                r = run_task(browser, a.base_url, t, mode, out)
                rows.append(r)
                note = "" if r["success"] else (r["error"] or r["check"])
                print(f"[{mode:5}] {t['id']} {'PASS' if r['success'] else 'FAIL'} {r['seconds']:>5}s {note}")
        browser.close()

    with open(out / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "traces.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = summarize(rows)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Kết quả:", out)


if __name__ == "__main__":
    main()
