"""B0/A1 and pluggable A2 replay. Requires Trung's resolver for A2.

W6 files and its manifest are never modified. The record CLI remains w6.run_heal.
"""
import argparse
import csv
import json
import inspect
import math
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.mutations import context_url
from app.seed import reset_database
from baseline.checker import check_all
from dom_snapshot.capture import capture, save_snapshot
from dom_snapshot.run import isolated_app
from healing.heal import heal
from llm.client import CallScope, Config, LLMError, StructuredClient
from w6.freeze import MANIFEST, ROOT, digest, validate_manifest, write_json
from w6.run_heal import POLICY, SCRIPTS, action, load_record, locate, relative_url
from w7.contracts import load_resolver, make_request, validate_decision
from w7.context import runtime_candidates
from w7.target_check import check_found, DEFAULT_THRESHOLD


def source_hashes():
    paths = [p for folder in ("llm", "w7", "planner") for p in (ROOT / folder).rglob("*")
             if p.suffix in (".py", ".json") and "__pycache__" not in p.parts]
    paths += [ROOT / "requirements-w7.txt"]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def validate_replacement(page, xpath, action_name, original_html):
    # Reject stale absolute XPaths after model latency; no automatic write retry.
    current_html = page.evaluate("() => '<!DOCTYPE html>\\n' + document.documentElement.outerHTML")
    if current_html != original_html:
        raise ValueError("DOM changed while resolving; stale decision rejected")
    locator = page.locator("xpath=" + xpath)
    if locator.count() != 1 or not locator.is_visible() or not locator.is_enabled():
        raise ValueError("Replacement must be unique, visible and enabled")
    if action_name == "fill" and not locator.is_editable():
        raise ValueError("Replacement is not editable")
    return locator


def replay(browser, base, task, mutation, seed, agent, locator, out, descriptors,
           provenance, *, resolver=None, client=None, target_threshold=DEFAULT_THRESHOLD):
    if agent not in ("b0", "a1", "a2"):
        raise ValueError("Unknown agent")
    if agent == "a2" and (resolver is None or client is None):
        raise ValueError("A2 requires a resolver and a client; no scripted default")
    reset_database()
    run_id = f"{mutation}-s{seed}-{task['id']}"
    trace, error, download, check_message = [], "", None, "not reached"
    started = time.perf_counter()
    with browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True) as ctx:
        ctx.add_cookies([{"name": "minibiz_mutation", "value": f"{mutation}:{seed}", "url": base}])
        page = ctx.new_page()
        page.set_default_timeout(5000)

        def get(path):
            response = ctx.request.get(base + path)
            if not response.ok:
                raise ValueError(f"API read returned {response.status}")
            return response.json()

        try:
            if check_all(get, task)[0]:
                raise ValueError("Task already satisfied on seed")
            for i, original in enumerate(SCRIPTS[task["id"]]):
                entry = {"index": i, "action": original["do"], "success": False,
                         "b0_count": None, "semantic": None, "fallback": None,
                         "llm_calls": [], "url_before": relative_url(page.url)}
                trace.append(entry)
                step, execute_locator = dict(original), locator
                step_started = time.perf_counter()
                try:
                    if i >= task["max_steps"]:
                        raise ValueError("max_steps exceeded")
                    if step["do"] == "goto":
                        step["url"] = context_url(step["url"], mutation, seed)
                    else:
                        count = locate(page, step, locator).count()
                        entry["b0_count"] = count
                        if count != 1:
                            entry["trigger"] = "missing" if count == 0 else "multiple"
                            sid = f"{run_id}-step{i:02d}"
                            html, snapshot = capture(page, sid, task["id"], sid, provenance)
                            save_snapshot(out / "snapshots" / sid, html, snapshot)
                            entry["snapshot"] = f"snapshots/{sid}/features.json"
                            if agent == "b0":
                                raise ValueError("B0 locator did not match exactly once")
                            descriptor = descriptors[f"{task['id']}:{i}"]["descriptor"]
                            candidates = runtime_candidates(snapshot)
                            result = heal(descriptor, candidates, mode=POLICY["mode"],
                                          min_margin=POLICY["min_margin"], min_score=POLICY["min_score"],
                                          use_order=POLICY["use_order"])
                            entry["semantic"] = result
                            xpath = result["xpath"] if result["status"] == "healed" else None
                            if xpath is not None:
                                chosen = next((c for c in candidates if c.get("xpath") == xpath), None)
                                entry["target_check"] = check_found(descriptor, chosen or {}, task["goal"], target_threshold)
                                if entry["target_check"]["likely_wrong"]:
                                    xpath = None
                                    entry["target_check"]["reason"] = "semantic_candidate_rejected"
                            if xpath is None and agent == "a2" and candidates:
                                packet, bindings = make_request(descriptor, candidates, step["do"], result,
                                                                objective=task["goal"])
                                if bindings:
                                    entry["fallback_request"] = packet
                                    before = len(client.calls)
                                    try:
                                        decision = resolver(packet, CallScope(client))
                                        entry["fallback"] = decision
                                        xpath = validate_decision(decision, bindings)
                                        if xpath:
                                            chosen = next((c for c in candidates if c.get("xpath") == xpath), None)
                                            entry["target_check"] = check_found(descriptor, chosen or {}, task["goal"], target_threshold)
                                            if entry["target_check"]["likely_wrong"]:
                                                xpath = None
                                                entry["target_check"]["reason"] = "llm_candidate_rejected"
                                    finally:
                                        entry["llm_calls"] = client.calls[before:]
                            if not xpath:
                                raise ValueError("No accepted replacement")
                            validate_replacement(page, xpath, step["do"], html)
                            step["xpath"], execute_locator = xpath, "xpath"
                        entry["executed_locator"] = step.get(execute_locator)
                    download = action(page, base, step, execute_locator, out / "downloads" / f"{run_id}.csv") or download
                    if not page.url.startswith(base + "/"):
                        raise ValueError("Navigation outside owned MiniBiz")
                    cookie = next((c["value"] for c in ctx.cookies() if c["name"] == "minibiz_mutation"), "")
                    if cookie != f"{mutation}:{seed}":
                        raise ValueError("Mutation context lost")
                    entry["success"] = True
                    entry["url_after"] = relative_url(page.url)
                except LLMError as exc:
                    entry["error"] = str(exc)
                    raise
                except Exception as exc:
                    # Resolver exceptions may contain HTTP headers or input: keep type only.
                    entry["error"] = type(exc).__name__
                    raise
                finally:
                    entry["seconds"] = round(time.perf_counter() - step_started, 4)
            ok, check_message = check_all(get, task, download)
            if not ok:
                raise ValueError("Final API/CSV check failed")
        except Exception as exc:
            error = entry.get("error", type(exc).__name__) if trace else type(exc).__name__
            try:
                _, check_message = check_all(get, task, download)
            except Exception:
                check_message = "API check unavailable"
    calls = [c for s in trace for c in s["llm_calls"]]
    row = {"agent": agent, "task_id": task["id"], "module": task["module"],
           "mutation": mutation, "mutation_seed": seed, "success": not error,
           "steps_done": sum(s["success"] for s in trace), "steps_total": len(SCRIPTS[task["id"]]),
           "healing_attempts": sum(s["semantic"] is not None for s in trace),
           "fallback_attempts": sum("fallback_request" in s for s in trace),
           "wrong_target_rejections": sum(bool(s.get("target_check", {}).get("likely_wrong")) for s in trace),
           "llm_requests": len(calls), "llm_errors": sum(c["status"] != "completed" for c in calls),
           "seconds": round(time.perf_counter() - started, 4), "error": error, "check": check_message}
    write_json(out / "traces" / f"{run_id}.json", {"result": row, "steps": trace})
    return row


def summarize(rows, expected, calls=()):
    durations = sorted(r["seconds"] for r in rows)
    usages = [c.get("usage") for c in calls]
    def total(key):
        return sum(u[key] for u in usages) if all(u is not None and isinstance(u.get(key), int) for u in usages) else None
    return {"scope": "W7 infrastructure replay; count trigger only; resolver policy pending Trung",
            "expected_rows": expected, "completed_rows": len(rows), "complete": len(rows) == expected,
            "passed": sum(r["success"] for r in rows),
            "task_success_rate": sum(r["success"] for r in rows) / len(rows) if rows else None,
            "median_seconds": statistics.median(durations) if durations else None,
            "p95_seconds": durations[math.ceil(.95 * len(durations)) - 1] if durations else None,
            "llm_requests": len(calls), "usage_complete": all(u is not None for u in usages),
            "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
            "estimated_cost_usd": None, "cost_note": "Apply a dated official rate card; no invented price.",
            "wrong_heal_count": sum(r.get("wrong_target_rejections", 0) for r in rows) if rows else None,
            "target_accuracy_note": "Guard rejections are counted; this is not an independent target-accuracy estimate.",
            "by_mutation": {m: {"total": len(rs := [r for r in rows if r["mutation"] == m]),
                                 "passed": sum(r["success"] for r in rs)} for m in sorted({r["mutation"] for r in rows})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("b0", "a1", "a2"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--mutations", nargs="+")
    parser.add_argument("--locator", choices=("css", "xpath"), default="css")
    parser.add_argument("--resolver", help="Trung's module:function, called as resolve(packet, client)")
    parser.add_argument("--max-requests", type=int, default=20)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--max-reserved-output-tokens", type=int, default=10240)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--target-threshold", type=float, default=DEFAULT_THRESHOLD,
                        help="threshold selected on the separate development challenge set")
    args = parser.parse_args()
    if args.agent != "b0" and not args.record:
        parser.error("A1/A2 require --record from w6.run_heal --mode record")
    if args.agent == "a2" and not args.resolver:
        parser.error("A2 requires --resolver; Trung's policy is deliberately not fabricated")
    if args.agent != "a2" and args.resolver:
        parser.error("--resolver is only allowed for A2")
    if not 0 <= args.target_threshold <= 1:
        parser.error("--target-threshold must be between 0 and 1")
    manifest = validate_manifest()
    tasks = json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))
    if args.tasks and (len(set(args.tasks)) != len(args.tasks) or set(args.tasks) - {t["id"] for t in tasks}):
        parser.error("Unknown/duplicate tasks")
    tasks = [t for t in tasks if not args.tasks or t["id"] in args.tasks]
    modes = args.mutations or manifest["mutation_modes"]
    if len(set(modes)) != len(modes) or set(modes) - set(manifest["mutation_modes"]):
        parser.error("Unknown/duplicate mutation modes")
    record = load_record(args.record, [t["id"] for t in tasks], manifest, args.locator) if args.record else None
    resolver = load_resolver(args.resolver) if args.resolver else None
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    client = None
    rows = []
    expected = len(tasks) * sum(1 if m == "M0" else len(manifest["development_seeds"]) for m in modes)
    metadata = {"agent": args.agent, "resolver": args.resolver,
                "policy": {**POLICY, "llm": args.agent == "a2", "fallback_trigger": "semantic_abstention_or_wrong_target_with_candidates",
                           "wrong_target_threshold": args.target_threshold},
                "started_at_utc": datetime.now(timezone.utc).isoformat(), "held_out_accessed": False,
                "manifest_sha256_lf": digest(MANIFEST), "w7_source_sha256_lf": source_hashes(),
                "record_sha256_lf": digest(args.record / "descriptors.json") if record else None,
                "task_ids": [t["id"] for t in tasks], "mutations": modes,
                "development_seeds": manifest["development_seeds"], "locator": args.locator,
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "git_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)}
    if resolver:
        resolver_path = inspect.getsourcefile(resolver)
        if not resolver_path:
            raise ValueError("Resolver must have inspectable source for provenance")
        metadata["resolver_source_sha256_lf"] = digest(resolver_path)
    try:
        if args.agent == "a2":
            client = StructuredClient(Config.from_env(timeout_seconds=args.timeout, max_requests=args.max_requests,
                                      max_output_tokens=args.max_output_tokens,
                                      max_reserved_output_tokens=args.max_reserved_output_tokens),
                                      audit_path=out / "llm-calls.jsonl")
            metadata["llm"] = client.metadata()
        write_json(out / "metadata.json", metadata)
        with isolated_app(out) as base, sync_playwright() as pw:
            browser = pw.chromium.launch()
            metadata["browser_version"] = browser.version
            try:
                for mode in modes:
                    for seed in ([0] if mode == "M0" else manifest["development_seeds"]):
                        for task in tasks:
                            row = replay(browser, base, task, mode, seed, args.agent, args.locator, out,
                                         record["descriptors"] if record else {}, metadata,
                                         resolver=resolver, client=client, target_threshold=args.target_threshold)
                            rows.append(row)
                            print(f"{args.agent} {mode} s{seed} {task['id']}: {row['success']}", flush=True)
                            write_json(out / "summary.json", summarize(rows, expected, client.calls if client else []))
            finally:
                browser.close()
    except LLMError as exc:
        metadata["setup_error"] = str(exc)
        print(str(exc))
    finally:
        if client:
            client.close()
        metadata["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(out / "metadata.json", metadata)
        write_json(out / "summary.json", summarize(rows, expected, client.calls if client else []))
        if rows:
            with (out / "results.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    return 0 if len(rows) == expected and all(r["success"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
