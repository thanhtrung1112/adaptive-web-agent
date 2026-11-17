"""Natural-language planner -> semantic matcher/LLM fallback -> Playwright executor demo."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.seed import reset_database
from dom_snapshot.capture import capture
from healing.heal import heal
from llm.client import CallScope, Config, LLMError, StructuredClient
from w6.run_heal import POLICY
from w7.context import runtime_candidates
from w7.plan import plan_with_client
from w7.run_agent import validate_replacement
from w7.target_check import check_found, DEFAULT_THRESHOLD
from w7.contracts import make_request, validate_decision
from dom_snapshot.run import isolated_app
from w6.freeze import write_json


def execute_step(page, base, step, resolver_client, trace, target_threshold=DEFAULT_THRESHOLD):
    if step["action"] == "navigate":
        page.goto(base + step["url"], wait_until="domcontentloaded")
        trace.append({"action": "navigate", "url": step["url"], "success": True})
        return
    action = step["action"]
    snapshot_id = f"demo-step-{len(trace):02d}"
    html, snapshot = capture(page, snapshot_id, "natural-demo", snapshot_id, {})
    candidates = runtime_candidates(snapshot)
    descriptor = {"text": step["target"], "label": step["target"],
                  "tag": {"fill": "input", "click": "button", "select": "select"}.get(action, "")}
    semantic = heal(descriptor, candidates, mode=POLICY["mode"], min_margin=POLICY["min_margin"],
                    min_score=POLICY["min_score"], use_order=False)
    xpath = semantic["xpath"] if semantic["status"] == "healed" else None
    diagnostic = None
    if xpath:
        chosen = next((c for c in candidates if c.get("xpath") == xpath), {})
        diagnostic = check_found(descriptor, chosen, step["target"], target_threshold)
        if diagnostic["likely_wrong"]:
            xpath = None
    decision = None
    if xpath is None and candidates:
        packet, bindings = make_request(descriptor, candidates, action,
                                        {**semantic, "reason": semantic["reason"]},
                                        objective=step["target"])
        from llm.fallback import resolve
        decision = resolve(packet, CallScope(resolver_client))
        xpath = validate_decision(decision, bindings)
        if xpath:
            chosen = next((c for c in candidates if c.get("xpath") == xpath), {})
            diagnostic = check_found(descriptor, chosen, step["target"], target_threshold)
            if diagnostic["likely_wrong"]:
                xpath = None
    if not xpath:
        raise ValueError("Matcher/fallback abstained: " + semantic["reason"])
    locator = validate_replacement(page, xpath, action, html)
    if action == "fill":
        locator.fill(step["value"])
    elif action == "click":
        locator.click()
    elif action == "select":
        locator.select_option(label=step["value"])
    else:
        raise ValueError("Unsupported browser action: " + action)
    trace.append({"action": action, "target": step["target"], "success": True,
                  "semantic": semantic, "fallback": decision, "target_check": diagnostic,
                  "url": page.url})


def run(goal, output, target_threshold=DEFAULT_THRESHOLD):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    record = {"scope": "interactive natural-language demo; not benchmark evidence",
              "goal": goal, "success": False, "steps": []}
    client = None
    try:
        client = StructuredClient(Config.from_env(max_requests=20, max_output_tokens=1024,
                                                   max_reserved_output_tokens=10240),
                                  audit_path=output / "llm-calls.jsonl")
        from planner.core import make_request as make_plan_request
        request = make_plan_request(goal, "/customers", 30)
        planned = plan_with_client(request, client)
        record["plan"] = planned
        if planned["plan"]["status"] != "ready":
            raise ValueError("Planner needs clarification or cannot support this request")
        reset_database()
        with isolated_app(output) as base, sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                page.set_default_timeout(7000)
                for step in planned["semantic_steps"]:
                    execute_step(page, base, step, client, record["steps"], target_threshold)
                record["final_url"] = page.url
                record["success"] = True
                context.close()
            finally:
                browser.close()
    except LLMError as exc:
        record["error_code"] = str(exc)
    except Exception as exc:
        record["error"] = type(exc).__name__
    finally:
        if client:
            record["llm"] = client.metadata()
            record["llm_requests"] = len(client.calls)
            client.close()
        write_json(output / "demo.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True, help="Natural-language MiniBiz request")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    if not 0 <= args.target_threshold <= 1:
        parser.error("--target-threshold must be between 0 and 1")
    result = run(args.goal, args.output, args.target_threshold)
    print(json.dumps({"success": result["success"], "error": result.get("error", result.get("error_code")),
                      "steps": len(result["steps"]), "llm_requests": result.get("llm_requests")}, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
