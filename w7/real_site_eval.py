"""Measure W7 browser recovery on public docs with independently graded targets."""

import argparse
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Error as BrowserError, sync_playwright

from dom_snapshot.capture import capture
from healing.heal import heal
from llm.client import CallScope, Config, LLMError, StructuredClient
from llm.fallback import resolve
from w6.freeze import write_json
from w6.run_heal import POLICY
from w7.context import runtime_candidates
from w7.contracts import make_request, validate_decision
from w7.report import price_usage
from w7.run_agent import source_hashes, validate_replacement
from w7.target_check import DEFAULT_THRESHOLD, check_found, check_link_destination

PYTHON = "https://docs.python.org/3.13/tutorial/index.html"
SQLITE = "https://www.sqlite.org/docs.html"
CASES = (
    ("PY-DATA", PYTHON, "datastructures.html", "5. Data Structures",
     "5. Lists, sets, and dictionaries", "Open the Data Structures tutorial for lists, sets, and dictionaries."),
    ("PY-IO", PYTHON, "inputoutput.html", "7. Input and Output",
     "7. Reading and writing data", "Open the Input and Output tutorial for reading and writing data."),
    ("SQL-LANG", SQLITE, "lang.html", "SQL Syntax",
     "SQL language reference", "Open the SQLite SQL Syntax and language reference."),
    ("SQL-CLI", SQLITE, "cli.html", "The CLI (Command-Line Interface)",
     "Using the SQLite shell", "Open the SQLite command-line interface and shell documentation."),
)
SCENARIOS = ("unchanged", "relabeled", "removed")
MODEL = "gpt-4.1-mini"
RATES = {"date": "2026-11-23", "source": "https://developers.openai.com/api/docs/models/gpt-4.1-mini",
         "input_per_million": 0.40, "cached_input_per_million": 0.10, "output_per_million": 1.60}


def choose(descriptor, candidates, objective, client, record_proposal, trace):
    options = {key: POLICY[key] for key in ("mode", "min_score", "min_margin", "use_order")}
    semantic = heal(descriptor, candidates, **options)
    trace["semantic"] = semantic
    by_xpath = {candidate["xpath"]: candidate for candidate in candidates}
    xpath = semantic["xpath"]
    if xpath and record_proposal("heuristic", by_xpath[xpath]):
        return xpath
    if client is None:
        return None

    trigger = "heuristic_target_rejected" if xpath else semantic["reason"]
    packet, bindings = make_request(descriptor, candidates, "click", {**semantic, "reason": trigger}, objective)
    if not bindings:
        return None
    trace["fallback_trigger"] = trigger
    decision = resolve(packet, CallScope(client))
    trace["fallback_decision"] = decision
    xpath = validate_decision(decision, bindings)
    if xpath and record_proposal("llm", by_xpath[xpath]):
        return xpath
    return None


def run_case(page, case, scenario, agent, client, link_guard):
    case_id, url, href, label, updated_label, objective = case
    expected = urljoin(url, href)
    row = {"case_id": case_id, "site": url, "scenario": scenario, "agent": agent,
           "expected_url": expected, "target_present": scenario != "removed", "proposals": [],
           "attempted_recovery": False, "recovery_seconds": None, "outcome": "environment_error"}
    started = time.perf_counter()
    recovery_started = None
    first_call = len(client.calls) if client else 0
    try:
        response = page.goto(url, wait_until="domcontentloaded")
        if response is None or not response.ok or page.url != url:
            raise ValueError("source_page_unavailable")

        # Ground truth comes from the registered user-visible link and destination.
        # Keep its node identity outside the heuristic and model packets.
        target = page.get_by_role("link", name=label, exact=True)
        baseline = page.locator(f'a[href="{href}"]:visible')
        if (target.count() != 1 or baseline.count() != 1
                or target.evaluate("el => el.href") != expected
                or not baseline.evaluate("(el, target) => el === target", target.element_handle())):
            raise ValueError("live_case_definition_changed")
        oracle = target.element_handle()
        run_id = f"{case_id}-{scenario}-{agent}"
        _, initial_snapshot = capture(page, run_id, case_id, "original", {})
        initial = next(c for c in runtime_candidates(initial_snapshot)
                       if c["tag"] == "a" and c["href"] == href
                       and c["text"] == label)
        descriptor = {key: value for key, value in initial.items() if key not in ("element_id", "xpath")}
        if scenario == "relabeled":
            oracle.evaluate("(el, text) => { el.href = el.href; el.textContent = text; }", updated_label)
        elif scenario == "removed":
            oracle.evaluate("el => el.remove()")

        row["baseline_count"] = baseline.count()
        if row["baseline_count"] == 1:
            locator = baseline
        elif agent == "b0":
            row["outcome"] = "locator_failed"
            return row
        else:
            row["attempted_recovery"] = True
            recovery_started = time.perf_counter()
            html, snapshot = capture(page, run_id, case_id, scenario, {})
            candidates = [c for c in runtime_candidates(snapshot) if c["tag"] == "a" and c["href"]]

            def record_proposal(method, candidate):
                selected = page.locator("xpath=" + candidate["xpath"])
                correct = selected.count() == 1 and selected.evaluate("(el, target) => el === target", oracle)
                if link_guard == "destination":
                    diagnostic = check_link_destination(page.url, descriptor["href"], candidate["href"])
                else:
                    diagnostic = check_found(descriptor, candidate, objective, DEFAULT_THRESHOLD)
                row["proposals"].append({"method": method, "text": candidate["text"], "href": candidate["href"],
                                         "correct": correct, "guard": diagnostic})
                return not diagnostic["likely_wrong"]

            try:
                xpath = choose(descriptor, candidates, objective, client, record_proposal, row)
                if xpath is None:
                    row["outcome"] = "no_recovery" if row["target_present"] else "correct_abstention"
                    return row
                locator = validate_replacement(page, xpath, "click", html)
                if not row["proposals"][-1]["correct"]:
                    # Count the accepted wrong choice, then stop before a wrong navigation.
                    row["outcome"] = "wrong_recovery"
                    return row
            finally:
                row["recovery_seconds"] = round(time.perf_counter() - recovery_started, 4)

        row["outcome"] = "destination_failed"
        with page.expect_navigation(wait_until="domcontentloaded") as navigation:
            locator.click()
        arrival = navigation.value
        row["final_url"] = page.url
        arrived = bool(arrival and arrival.ok and page.url == expected
                       and page.get_by_role("heading", level=1).count() > 0)
        if arrived:
            row["outcome"] = "correct_recovery" if row["attempted_recovery"] else "baseline_success"
    except LLMError as exc:
        row.update(outcome="llm_error", error=str(exc))
    except (BrowserError, StopIteration, ValueError) as exc:
        row["error"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if row["attempted_recovery"] and row["outcome"] == "environment_error":
            row["outcome"] = "recovery_error"
    finally:
        row["task_seconds"] = round(time.perf_counter() - started, 4)
        row["llm_call_ids"] = [call["index"] for call in client.calls[first_call:]] if client else []
    return row


def timing(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "median": None, "p95": None}
    return {"n": len(values), "median": statistics.median(values), "p95": values[math.ceil(0.95 * len(values)) - 1]}


def summarize(rows, calls):
    attempts = sum(r["attempted_recovery"] for r in rows)
    wrong = sum(r["outcome"] == "wrong_recovery" for r in rows)
    proposals = [p for row in rows for p in row["proposals"]]
    usages = [call.get("usage") or {} for call in calls]

    def tokens(key):
        values = [usage.get(key) for usage in usages]
        return sum(values) if all(type(value) is int and value >= 0 for value in values) else None

    return {"cases": len(rows), "outcomes": {name: sum(r["outcome"] == name for r in rows)
                                              for name in sorted({r["outcome"] for r in rows})},
            "recovery_attempts": attempts, "wrong_recoveries": wrong,
            "wrong_recovery_rate": wrong / attempts if attempts else None,
            "wrong_proposals": sum(not p["correct"] for p in proposals),
            "wrong_proposals_rejected": sum(not p["correct"] and p["guard"]["likely_wrong"] for p in proposals),
            "task_seconds": timing(r["task_seconds"] for r in rows),
            "recovery_seconds": timing(r["recovery_seconds"] for r in rows),
            "provider_seconds": timing(c["seconds"] for c in calls), "llm_calls": len(calls),
            "llm_errors": sum(c["status"] != "completed" for c in calls),
            "input_tokens": tokens("input_tokens"), "output_tokens": tokens("output_tokens"),
            "estimated_cost_usd": price_usage(calls, RATES)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--channel", choices=("chrome", "msedge"), help="Use an installed browser")
    parser.add_argument("--live", action="store_true", help="Include A2 using at most eight paid API requests")
    parser.add_argument("--link-guard", choices=("destination", "context"), default="destination",
                        help="Use the recorded link destination or the earlier W7 context guard")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    agents = ("b0", "a1", "a2") if args.live else ("b0", "a1")
    client = None
    rows = []
    metadata = {"date_utc": datetime.now(timezone.utc).isoformat(), "agents": agents, "link_guard": args.link_guard,
                "expected_rows": len(agents) * len(SCENARIOS) * len(CASES),
                "rates": RATES, "source_sha256_lf": source_hashes(), "guard_threshold": DEFAULT_THRESHOLD}
    try:
        if args.live:
            config = Config(model=MODEL, timeout_seconds=20, max_requests=8,
                            max_output_tokens=256, max_reserved_output_tokens=2048)
            client = StructuredClient(config, audit_path=args.output / "llm-calls.jsonl")
            metadata["llm"] = client.metadata()
        with sync_playwright() as pw, pw.chromium.launch(channel=args.channel) as browser:
            metadata["browser"] = {"channel": args.channel or "chromium", "version": browser.version}
            for case in CASES:
                for scenario in SCENARIOS:
                    for agent in agents:
                        with browser.new_context(viewport={"width": 1280, "height": 800}) as context:
                            page = context.new_page()
                            page.set_default_timeout(12000)
                            row = run_case(page, case, scenario, agent, client if agent == "a2" else None,
                                           args.link_guard)
                        rows.append(row)
                        write_json(args.output / "results.json", rows)
                        print(case[0], scenario, agent, row["outcome"], flush=True)
    finally:
        calls = client.calls if client else []
        if client:
            client.close()
        write_json(args.output / "summary.json", {"metadata": metadata, "completed_rows": len(rows),
                                                  "by_agent": {agent: summarize(
                                                      [r for r in rows if r["agent"] == agent],
                                                      calls if agent == "a2" else []) for agent in agents}})
    errors = {"environment_error", "recovery_error", "llm_error", "destination_failed"}
    return int(any(row["outcome"] in errors for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
