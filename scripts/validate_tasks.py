"""Kiểm tra tasks/*.json theo schema và các ràng buộc nhất quán."""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SELECTOR_HINTS = ("#", "css", "xpath", "//", "[@", "class=")


def main(tasks_file: str = "tasks/pilot_tasks.json") -> int:
    schema = json.loads((ROOT / "tasks/task_schema.json").read_text(encoding="utf-8"))
    tasks = json.loads((ROOT / tasks_file).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []

    ids = [t.get("id") for t in tasks]
    if len(ids) != len(set(ids)):
        errors.append("ID bị trùng")

    for t in tasks:
        tid = t.get("id", "?")
        for e in validator.iter_errors(t):
            errors.append(f"{tid}: {e.message}")
        goal = t.get("goal", "").lower()
        if any(h in goal for h in SELECTOR_HINTS):
            errors.append(f"{tid}: goal không được chứa chỉ dẫn selector")
        if t.get("difficulty") == "chain" and t.get("module") != "chain":
            errors.append(f"{tid}: difficulty=chain phải có module=chain")

    if errors:
        print("LỖI:")
        for e in errors:
            print(" -", e)
        return 1

    by_module = {}
    for t in tasks:
        by_module[t["module"]] = by_module.get(t["module"], 0) + 1
    print(f"OK: {len(tasks)} task hợp lệ; theo module: {by_module}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
