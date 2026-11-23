"""Run W8 reference cases or replay a previously recorded MiniBiz task."""

import argparse
import csv
import importlib.metadata
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from playwright.sync_api import sync_playwright

from dom_snapshot.run import isolated_app
from w6.freeze import ROOT, digest, write_json
from w8.fixtures import REFERENCE_SCRIPTS
from w8.harness import MUTATIONS, replay_case, run_case

TASK_FILE = ROOT / "tasks/tasks_w8.json"


def load_tasks():
    tasks = json.loads(TASK_FILE.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "tasks/task_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for task in tasks:
        validator.validate(task)
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks) or set(by_id) != set(REFERENCE_SCRIPTS):
        raise ValueError("W8 needs one reference script for each unique task")
    if any(len(REFERENCE_SCRIPTS[task["id"]]) > task["max_steps"] for task in tasks):
        raise ValueError("A reference script exceeds its task's max_steps")
    return by_id


def reference_producer(strategy):
    def produce(session, task):
        for step in REFERENCE_SCRIPTS[task["id"]]:
            action = step["do"]
            if action == "goto":
                request = {"action": "navigate", "url": step["url"]}
            else:
                request = {"action": action, "locator": {"strategy": strategy, "value": step[strategy]},
                           **{key: step[key] for key in ("value", "label") if key in step}}
            session.act(request)
    return produce


def row_from_trace(task, trace):
    return {"task_id": task["id"], "module": task["module"], "agent": trace["agent"],
            "mutation": trace["case"]["mutation"], "mutation_seed": trace["case"]["mutation_seed"],
            "success": trace["success"], "steps_done": sum(step["success"] for step in trace["steps"]),
            "seconds": trace["seconds"], "check": trace["verification"]["message"], "error": trace.get("error", ""),
            "replay_matches": trace.get("replay_matches"), "trace": f"traces/{task['id']}.json"}


def save_report(output, rows, expected):
    passed = sum(row["success"] for row in rows)
    durations = sorted(row["seconds"] for row in rows)
    summary = {"expected": expected, "completed": len(rows), "passed": passed, "failed": len(rows) - passed,
               "median_seconds": statistics.median(durations) if durations else None,
               "p95_seconds": durations[(95 * len(durations) + 99) // 100 - 1] if durations else None}
    write_json(output / "summary.json", summary)
    if rows:
        with (output / "results.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return int(passed != expected or len(rows) != expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="Run handwritten reference scripts")
    record.add_argument("--tasks", nargs="+", help="Default: all 40 W8 tasks")
    record.add_argument("--locator", choices=("css", "xpath"), default="css")
    record.add_argument("--mutation", choices=MUTATIONS, default="M0")
    record.add_argument("--seed", type=int, default=0, help="DOM mutation seed, independent of seed_v1")
    replay = commands.add_parser("replay", help="Replay one successful W8 trace")
    replay.add_argument("--trace", type=Path, required=True)
    for command in (record, replay):
        command.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    tasks = load_tasks()
    original = None
    if args.command == "record":
        selection = args.tasks or list(tasks)
        if not 0 <= args.seed <= 2147483647:
            parser.error("--seed must be between 0 and 2147483647")
        if len(selection) != len(set(selection)) or set(selection) - tasks.keys():
            parser.error("Unknown or repeated task ID")
    else:
        try:
            original = json.loads(args.trace.read_text(encoding="utf-8"))
            selection = [original["case"]["task_id"]]
            if selection[0] not in tasks:
                raise ValueError("Trace task is outside the W8 dataset")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            parser.error(f"Invalid trace: {exc}")
    if args.output.exists():
        parser.error("Output directory already exists")
    args.output.mkdir(parents=True, exist_ok=False)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    metadata = {"command": args.command, "git_commit": git.stdout.strip() if git.returncode == 0 else None,
                "started_at_utc": datetime.now(timezone.utc).isoformat(), "playwright": importlib.metadata.version("playwright"),
                "dataset_sha256_lf": digest(TASK_FILE), "task_ids": selection}
    if original is not None:
        metadata["input_trace_sha256_lf"] = digest(args.trace)
    else:
        metadata.update(mutation=args.mutation, mutation_seed=args.seed, locator=args.locator)
    rows = []
    try:
        with isolated_app(args.output) as base, sync_playwright() as pw, pw.chromium.launch() as browser:
            metadata["browser_version"] = browser.version
            for task_id in selection:
                task = tasks[task_id]
                if original is None:
                    trace = run_case(browser, base, task, args.output, reference_producer(args.locator),
                                     agent=f"b0-{args.locator}", mutation=args.mutation, mutation_seed=args.seed)
                else:
                    trace = replay_case(browser, base, task, args.output, original)
                rows.append(row_from_trace(task, trace))
                print(task_id, "PASS" if trace["success"] else "FAIL", trace.get("error", trace["verification"]["message"]), flush=True)
    except (ValueError, TypeError, KeyError) as exc:
        metadata["error"] = str(exc)
        print(f"W8: {exc}")
    finally:
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(args.output / "metadata.json", metadata)
        status = save_report(args.output, rows, len(selection))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
