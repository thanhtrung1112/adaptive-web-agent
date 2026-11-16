"""Dry-run by default. --live makes at most one real, billed OpenAI request."""
import argparse
import json
from dataclasses import asdict
from itertools import count
from pathlib import Path

from llm.client import Config, LLMError, StructuredClient

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


def reserve_output(requested):
    """Allocate atomically; repeated smoke commands never overwrite evidence."""
    for index in count(1):
        path = requested if index == 1 else requested.with_name(f"{requested.name}-{index:02d}")
        try:
            path.mkdir(parents=True, exist_ok=False)
            return path
        except FileExistsError:
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = Config.from_env(max_requests=1, max_output_tokens=64, max_reserved_output_tokens=64)
    if not args.live:
        print(json.dumps({"mode": "dry-run", "network_requests": 0, "config": asdict(config)}, indent=2))
        return 0
    if args.output is None:
        parser.error("--live requires --output")
    if args.output.name in ("", ".", ".."):
        parser.error("--output must name a result directory")
    args.output = reserve_output(args.output)
    print("Output directory:", args.output)
    client = None
    result = {"scope": "API connectivity only; not model quality or browser task success"}
    try:
        client = StructuredClient(config, audit_path=args.output / "calls.jsonl")
        result["metadata"] = client.metadata()
        result["response"] = client.generate_json(instructions="Return ok=true in the required JSON schema.",
                                                   payload={"check": "connectivity"}, schema=SCHEMA,
                                                   schema_name="connectivity_check")
        result["success"] = result["response"] == {"ok": True}
    except LLMError as exc:
        result.update(success=False, error_code=str(exc))
    finally:
        if client:
            client.close()
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("API smoke:", "passed" if result["success"] else result["error_code"] if "error_code" in result else "failed")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
