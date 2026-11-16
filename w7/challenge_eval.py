"""Evaluate Trung's resolver on isolated challenge packets, never expose answer files."""
import argparse
import json
from pathlib import Path

from llm.client import CallScope, Config, LLMError, StructuredClient
from w6.freeze import digest, write_json
from w7.contracts import load_resolver, validate_decision
from w7.run_agent import source_hashes


def grade(decision, expected):
    return decision["decision"] == expected["expected_decision"] and decision["candidate_id"] == expected["expected_candidate_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--resolver", required=True, help="module:function supplied by Trung")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=8)
    args = parser.parse_args()
    resolver = load_resolver(args.resolver)
    audit = json.loads((args.dataset / "audit.json").read_text(encoding="utf-8"))
    checksums = json.loads((args.dataset / "checksums.json").read_text(encoding="utf-8"))
    for name, expected_hash in checksums.items():
        path = (args.dataset / name).resolve()
        if not path.is_relative_to(args.dataset.resolve()) or digest(path) != expected_hash:
            raise ValueError("Challenge checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    client, rows = None, []
    metadata = {"scope": "DOM fixture resolver evaluation; not online MiniBiz task success",
                "resolver": args.resolver, "w7_source_sha256_lf": source_hashes(),
                "dataset_checksums_sha256_lf": digest(args.dataset / "checksums.json")}
    try:
        client = StructuredClient(Config.from_env(max_requests=args.max_requests), audit_path=args.output / "llm-calls.jsonl")
        metadata["llm"] = client.metadata()
        for case in audit["cases"]:
            packet = json.loads((args.dataset / case["case_id"] / "request.json").read_text(encoding="utf-8"))
            row = {"case_id": case["case_id"], "success": False, "decision": None,
                   "natural_fallback": case["natural_fallback"]}
            before = len(client.calls)
            try:
                if case["natural_fallback"]:
                    decision = resolver(packet, CallScope(client))  # No expected label or evaluator path passed.
                    validate_decision(decision, {c["candidate_id"]: c["candidate_id"] for c in packet["candidates"]})
                else:
                    decision = {"decision": "abstain", "candidate_id": None, "reason": "no_candidates"}
                row["decision"] = decision
                expected = json.loads((args.dataset / case["case_id"] / "evaluation-only.json").read_text(encoding="utf-8"))
                row["success"] = grade(decision, expected)
            except LLMError as exc:
                row["error_code"] = str(exc)
            except Exception as exc:
                row["error_code"] = type(exc).__name__
            row["llm_requests"] = len(client.calls) - before
            rows.append(row)
            write_json(args.output / "results.json", rows)
    except LLMError as exc:
        metadata["setup_error"] = str(exc)
    finally:
        if client:
            client.close()
        write_json(args.output / "metadata.json", metadata)
        write_json(args.output / "summary.json", {"expected_cases": len(audit["cases"]), "completed_cases": len(rows),
                                                   "passed": sum(r["success"] for r in rows),
                                                   "llm_requests": len(client.calls) if client else 0})
    return 0 if len(rows) == len(audit["cases"]) and all(r["success"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
