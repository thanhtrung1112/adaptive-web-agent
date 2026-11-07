"""Record B0 descriptors on M0; replay frozen B0 + conditional healing without an oracle.

python -m w6.run_heal --mode record --output runs/w6-record
python -m w6.run_heal --mode heal --record runs/w6-record --output runs/w6-online
"""
import argparse
import csv
import importlib.metadata
import json
import math
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright
from app.mutations import context_url
from app.seed import reset_database
from baseline.checker import check_all
from baseline.run_baseline import SCRIPTS, run_step
from dom_snapshot.capture import capture, save_snapshot
from dom_snapshot.run import isolated_app
from healing.descriptor import build_descriptor, controls_with_xpath
from healing.heal import heal
from w6.freeze import MANIFEST, ROOT, digest, structural_hash, validate_manifest, write_json

POLICY = {"trigger": "B0_count_not_one", "mode": "features", "min_margin": 0.02,
          "min_score": 0.0, "use_order": True, "max_heal_attempts_per_step": 1,
          "wrong_target_check": False, "llm": False}


def relative_url(url):
    from urllib.parse import urlsplit
    value = urlsplit(url)
    return value.path + ("?" + value.query if value.query else "")


def locate(page, step, locator):
    return page.locator(step["css"] if locator == "css" else "xpath=" + step["xpath"])


def action(page, base, step, locator, out):
    return run_step(page, base, step, locator, out)


def load_record(path, task_ids, manifest, locator):
    path = Path(path)
    record = json.loads((path / "descriptors.json").read_text(encoding="utf-8"))
    if record["manifest_sha256_lf"] != digest(MANIFEST) or record["locator"] != locator:
        raise ValueError("Record manifest/locator differs from this run")
    if record["scripts_sha256_lf"] != {p: manifest["source_sha256_lf"][p] for p in ("baseline/scripts.py", "baseline/w4_scripts.py")}:
        raise ValueError("B0 scripts changed since record")
    if not all(record["task_success"].get(t) for t in task_ids):
        raise ValueError("Record is missing successful M0 tasks")
    for task_id in task_ids:
        for i, step in enumerate(SCRIPTS[task_id]):
            if step["do"] != "goto":
                entry = record["descriptors"].get(f"{task_id}:{i}")
                if not entry or entry["step"] != step:
                    raise ValueError(f"Missing or changed recorded step {task_id}:{i}")
                if any(k in entry["descriptor"] for k in ("element_id", "xpath", "target_element_id", "ref_eid")):
                    raise ValueError("Answer/location identifier in descriptor")
    return record


def replay(browser, base, task, mutation, seed, mode, locator, out, descriptors, provenance, demo=False):
    """Only B0, recorded descriptor and current DOM participate in target selection."""
    reset_database()
    run_id = f"{mutation}-s{seed}-{task['id']}"
    trace, error, download, pre_ok = [], "", None, None
    options = {"viewport": {"width": 1280, "height": 800}, "accept_downloads": True}
    if demo:
        options["record_video_dir"] = str(out / "videos")
    started = time.perf_counter()
    snapshots = []
    with browser.new_context(**options) as ctx:
        ctx.add_cookies([{"name": "minibiz_mutation", "value": f"{mutation}:{seed}", "url": base}])
        page = ctx.new_page()
        page.set_default_timeout(5000)

        def get(path):
            response = ctx.request.get(base + path)
            if not response.ok:
                raise ValueError(f"API {path}: HTTP {response.status}")
            return response.json()

        check_message = "not reached"
        try:
            pre_ok = check_all(get, task)[0]
            if pre_ok:
                raise ValueError("Task already satisfied on seed; invalid benchmark precondition")
            for i, original in enumerate(SCRIPTS[task["id"]]):
                entry = {"index": i, "action": original["do"], "b0_locator": original.get(locator),
                         "success": False, "heal": None, "url_before": relative_url(page.url)}
                trace.append(entry)  # Failed steps are retained too.
                step = dict(original)
                step_start = time.perf_counter()
                try:
                    if i >= task["max_steps"]:
                        raise ValueError("max_steps exceeded")
                    execute_locator = locator
                    if step["do"] == "goto":
                        step["url"] = context_url(step["url"], mutation, seed)
                    else:
                        b0 = locate(page, step, locator)
                        count = b0.count()
                        entry["b0_count"] = count
                        if mode == "record" or count != 1:
                            sid = f"{run_id}-step{i:02d}"
                            html, snap = capture(page, sid, task["id"], sid, provenance)
                            save_snapshot(out / "snapshots" / sid, html, snap)
                            entry["snapshot"] = f"snapshots/{sid}/features.json"
                            if mode == "record":
                                if count != 1:
                                    raise ValueError(f"M0 B0 must match once; got {count}")
                                # Identify the B0 element only in the recording page, never on mutation pages.
                                eid = b0.evaluate("el => 'e' + (Array.from(document.querySelectorAll('*')).indexOf(el) + 1)")
                                descriptors[f"{task['id']}:{i}"] = {"step": original, "descriptor": build_descriptor(snap, eid),
                                                                     "snapshot": entry["snapshot"]}
                                snapshots.append({"task_id": task["id"], "step_index": i,
                                                  "structural_hash": structural_hash(html)})
                            else:
                                entry["trigger"] = "missing" if count == 0 else "multiple"
                                descriptor = descriptors[f"{task['id']}:{i}"]["descriptor"]
                                result = heal(descriptor, controls_with_xpath(snap), mode=POLICY["mode"],
                                              min_margin=POLICY["min_margin"], min_score=POLICY["min_score"], use_order=POLICY["use_order"])
                                entry["heal"] = result
                                if result["status"] != "healed":
                                    raise ValueError("Healing abstained: " + result["reason"])
                                replacement = page.locator("xpath=" + result["xpath"])
                                if not result["xpath"] or replacement.count() != 1:
                                    raise ValueError("Replacement XPath is missing/non-unique")
                                step["xpath"], execute_locator = result["xpath"], "xpath"
                        entry["executed_locator"] = step.get(execute_locator)
                    download = action(page, base, step, execute_locator, out / "downloads" / f"{run_id}.csv") or download
                    if not page.url.startswith(base):
                        raise ValueError("Navigation outside owned MiniBiz")
                    context = next((c["value"] for c in ctx.cookies() if c["name"] == "minibiz_mutation"), "")
                    if context != f"{mutation}:{seed}":
                        raise ValueError("Mutation context was lost")
                    entry["success"] = True
                    entry["url_after"] = relative_url(page.url)
                    if demo and entry["heal"]:
                        page.screenshot(path=str(out / f"{run_id}-step{i:02d}-after.png"), full_page=True)
                except Exception as exc:
                    entry["error"] = f"{type(exc).__name__}: {exc}"[:1500]
                    raise
                finally:
                    entry["seconds"] = round(time.perf_counter() - step_start, 4)
            ok, check_message = check_all(get, task, download)
            if not ok:
                raise ValueError(check_message)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:1500]
            # API is the final outcome authority even if execution failed; success still requires all steps.
            _, check_message = check_all(get, task, download)
        healed = [s for s in trace if s.get("heal")]
        row = {"task_id": task["id"], "module": task["module"], "mutation": mutation, "mutation_seed": seed,
               "success": not error, "precondition_success": pre_ok, "steps_done": sum(s["success"] for s in trace),
               "steps_total": len(SCRIPTS[task["id"]]), "heal_attempts": len(healed),
               "heal_actions_succeeded": sum(s["success"] for s in healed),
               "abstentions": sum(s["heal"]["status"] == "abstain" for s in healed),
               "seconds": round(time.perf_counter() - started, 4), "check": check_message, "error": error}
        if demo:
            page.screenshot(path=str(out / f"{run_id}-final.png"), full_page=True)
            video = page.video
            page.close()
            if video:
                video.save_as(str(out / f"{run_id}.webm"))
    detail = {"result": row, "steps": trace, "record_states": snapshots,
              "recovery_definition": "Task-level recovery requires a healing trigger, all actions, and final API success. Action success alone does not prove correct target."}
    write_json(out / "traces" / f"{run_id}.json", detail)
    return row


def summarize(rows, expected):
    triggered = [r for r in rows if r["heal_attempts"]]
    durations = sorted(r["seconds"] for r in rows)
    return {"scope": "Online frozen B0 with conditional DOM healing; development MiniBiz; no LLM/oracle target mapping",
            "expected_rows": expected, "completed_rows": len(rows), "complete": len(rows) == expected,
            "passed": sum(r["success"] for r in rows), "failed": sum(not r["success"] for r in rows),
            "task_success_rate": sum(r["success"] for r in rows) / len(rows) if rows else None,
            "tasks_with_healing": len(triggered), "recovered_tasks": sum(r["success"] for r in triggered),
            "task_recovery_rate": sum(r["success"] for r in triggered) / len(triggered) if triggered else None,
            "healing_attempts": sum(r["heal_attempts"] for r in rows),
            "heal_actions_succeeded": sum(r["heal_actions_succeeded"] for r in rows),
            "abstentions": sum(r["abstentions"] for r in rows),
            "wrong_heal_count": None, "wrong_heal_note": "Not independently target-labelled online; do not infer zero from API task pass.",
            "median_seconds": statistics.median(durations) if durations else None,
            "p95_seconds": durations[math.ceil(.95 * len(durations)) - 1] if durations else None,
            "by_mutation": {m: {"total": len(rs := [r for r in rows if r["mutation"] == m]),
                                 "passed": sum(r["success"] for r in rs), "tasks_with_healing": sum(bool(r["heal_attempts"]) for r in rs)}
                            for m in sorted({r["mutation"] for r in rows})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("record", "heal"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--mutations", nargs="+")
    parser.add_argument("--locator", choices=("css", "xpath"), default="css")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    manifest = validate_manifest()
    tasks = json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))
    if args.tasks:
        if len(set(args.tasks)) != len(args.tasks) or set(args.tasks) - {t["id"] for t in tasks}:
            parser.error("Unknown/duplicate task IDs")
        tasks = [t for t in tasks if t["id"] in args.tasks]
    modes = ["M0"] if args.mode == "record" else (args.mutations or manifest["mutation_modes"])
    if len(set(modes)) != len(modes) or set(modes) - set(manifest["mutation_modes"]):
        parser.error("Unknown/duplicate modes")
    if args.mode == "record" and args.mutations and args.mutations != ["M0"]:
        parser.error("record supports M0 only")
    if args.mode == "heal" and not args.record:
        parser.error("heal requires --record")
    record = load_record(args.record, [t["id"] for t in tasks], manifest, args.locator) if args.mode == "heal" else None
    descriptors = record["descriptors"] if record else {}
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    expected = len(tasks) * sum(1 if m == "M0" else len(manifest["development_seeds"]) for m in modes)
    metadata = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "git_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True),
                "source_sha256_lf": manifest["source_sha256_lf"], "manifest_sha256_lf": digest(MANIFEST),
                "record_sha256_lf": digest(args.record / "descriptors.json") if record else None,
                "mutation_set_version": manifest["mutation_set_version"], "mode": args.mode, "locator": args.locator,
                "mutations": modes, "development_seeds": manifest["development_seeds"], "task_ids": [t["id"] for t in tasks],
                "policy": POLICY, "held_out_accessed": False, "demo": args.demo,
                "started_at_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                "playwright": importlib.metadata.version("playwright"), "numpy": importlib.metadata.version("numpy")}
    rows = []
    write_json(out / "metadata.json", metadata)
    try:
        with isolated_app(out) as base, sync_playwright() as pw:
            browser = pw.chromium.launch()
            metadata["browser_version"] = browser.version
            try:
                for mode in modes:
                    for seed in ([0] if mode == "M0" else manifest["development_seeds"]):
                        for task in tasks:
                            row = replay(browser, base, task, mode, seed, args.mode, args.locator, out, descriptors, metadata, args.demo)
                            rows.append(row)
                            print(f"{mode} s{seed} {task['id']}: {row['success']} heal={row['heal_attempts']} {row['error']}", flush=True)
                            write_json(out / "summary.json", summarize(rows, expected))
            finally:
                browser.close()
    finally:
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "metadata.json", metadata)
        write_json(out / "summary.json", summarize(rows, expected))
        if rows:
            with (out / "results.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
        if args.mode == "record":
            write_json(out / "descriptors.json", {"manifest_sha256_lf": digest(MANIFEST), "locator": args.locator,
                       "scripts_sha256_lf": {p: manifest["source_sha256_lf"][p] for p in ("baseline/scripts.py", "baseline/w4_scripts.py")},
                       "task_success": {r["task_id"]: r["success"] for r in rows}, "descriptors": descriptors})
    return 0 if len(rows) == expected and all(r["success"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
