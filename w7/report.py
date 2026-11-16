"""Compare compatible replay runs; optionally price actual usage using a dated rate card."""
import argparse
import json
import math
from pathlib import Path

from w6.freeze import write_json


def price_usage(calls, rates):
    """Rates are USD per million tokens; unknown usage never becomes zero cost."""
    required = ("input_per_million", "cached_input_per_million", "output_per_million")
    if not rates:
        return None
    if not rates.get("date") or not rates.get("source") or any(type(rates.get(k)) not in (int, float) or not math.isfinite(rates[k]) or rates[k] < 0 for k in required):
        raise ValueError("Rate card requires date, source and non-negative input/cached/output rates")
    total = 0
    for call in calls:
        usage = call.get("usage")
        if not usage:
            return None
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens")
        if any(type(v) is not int or v < 0 for v in (input_tokens, output_tokens, cached)) or cached > input_tokens:
            return None
        total += ((input_tokens - cached) * rates["input_per_million"] + cached * rates["cached_input_per_million"]
                  + output_tokens * rates["output_per_million"]) / 1_000_000
    return round(total, 8)


def compare(paths, rates=None):
    runs, reference, seen = [], None, set()
    keys = ("manifest_sha256_lf", "w7_source_sha256_lf", "task_ids", "mutations", "development_seeds", "locator")
    reference_rows = None
    for path in map(Path, paths):
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
        if metadata["agent"] in seen:
            raise ValueError("One run per agent per comparison; repetitions must be reported separately")
        seen.add(metadata["agent"])
        current = {key: metadata[key] for key in keys}
        current["semantic_policy"] = {k: v for k, v in metadata["policy"].items() if k not in ("llm", "fallback_trigger")}
        if reference is not None and current != reference:
            raise ValueError("Runs differ in manifest/source/task/mutation/seed/locator")
        reference = current
        if not summary["complete"]:
            raise ValueError("Cannot compare incomplete runs")
        traces = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((path / "traces").glob("*.json"))]
        identities = [(t["result"]["task_id"], t["result"]["mutation"], t["result"]["mutation_seed"]) for t in traces]
        if len(set(identities)) != summary["expected_rows"] or len(traces) != summary["expected_rows"]:
            raise ValueError("Trace coverage does not match declared matrix")
        if reference_rows is not None and set(identities) != reference_rows:
            raise ValueError("Different task/mutation/seed rows")
        reference_rows = set(identities)
        calls_path = path / "llm-calls.jsonl"
        calls = [json.loads(line) for line in calls_path.read_text(encoding="utf-8").splitlines() if line] if calls_path.exists() else []
        runs.append({"agent": metadata["agent"], "path": str(path), **summary,
                     "estimated_cost_usd": price_usage(calls, rates) if metadata["agent"] == "a2" else 0})
    by_agent = {r["agent"]: r for r in runs}
    return {"scope": "Development replay only; no independent target labels or final LLM quality claims",
            "runs": runs, "rates": rates,
            "a1_minus_b0_percentage_points": 100 * (by_agent["a1"]["task_success_rate"] - by_agent["b0"]["task_success_rate"]) if {"b0", "a1"} <= by_agent.keys() else None,
            "a2_minus_a1_percentage_points": 100 * (by_agent["a2"]["task_success_rate"] - by_agent["a1"]["task_success_rate"]) if {"a1", "a2"} <= by_agent.keys() else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--rates", type=Path, help="JSON: date, source, input_per_million, cached_input_per_million, output_per_million")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists")
    rates = json.loads(args.rates.read_text(encoding="utf-8")) if args.rates else None
    write_json(args.output, compare(args.runs, rates))
    print("Report written:", args.output)


if __name__ == "__main__":
    main()
