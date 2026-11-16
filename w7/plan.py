"""OpenAI intent extraction using existing W3 validation; no browser writes."""
import argparse
import copy
import json
from pathlib import Path

from llm.client import Config, LLMError, StructuredClient
from planner.core import make_request
from planner.intent import SCHEMA, SYSTEM, validate
from planner.workflows import compile_intent
from w6.freeze import write_json
from w7.planner_adapter import semantic_steps
from w7.run_agent import source_hashes


def strict_intent_schema():
    # W3 enum fields omit explicit type, which strict provider schemas require.
    schema = copy.deepcopy(SCHEMA)
    schema["properties"]["operations"]["items"]["properties"]["kind"]["type"] = "string"
    schema["properties"]["operations"]["items"]["properties"]["slots"]["items"]["properties"]["key"]["type"] = "string"
    return schema


def plan_with_client(request, client):
    intent = client.generate_json(instructions=SYSTEM, payload={"goal": request["goal"]},
                                  schema=strict_intent_schema(), schema_name="minibiz_intent")
    validate(intent, request["goal"])
    compiled = compile_intent(intent, request)
    return {"intent": intent, **compiled,
            "semantic_steps": semantic_steps(compiled["plan"], compiled["workflow"], request, intent)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--start-url", default="/customers")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = make_request(args.goal, args.start_url, args.max_steps)
    args.output.mkdir(parents=True, exist_ok=False)
    record = {"scope": "OpenAI intent/plan generation only; browser execution not claimed",
              "request": request, "w7_source_sha256_lf": source_hashes(), "success": False}
    client = None
    try:
        client = StructuredClient(Config.from_env(max_requests=1, max_output_tokens=2048,
                                                   max_reserved_output_tokens=2048),
                                  audit_path=args.output / "llm-calls.jsonl")
        record["llm"] = client.metadata()
        record.update(plan_with_client(request, client), success=True)
    except LLMError as exc:
        record["error_code"] = str(exc)
    except Exception as exc:
        record["error_code"] = type(exc).__name__
    finally:
        if client:
            client.close()
        write_json(args.output / "plan.json", record)
    print("Plan:", record.get("plan", {}).get("status", record.get("error_code", "failed")))
    return 0 if record["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
