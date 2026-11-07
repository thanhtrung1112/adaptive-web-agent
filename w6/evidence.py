"""Package and verify the complete W6 online evidence without server logs/databases."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path

from baseline.run_baseline import SCRIPTS
from w6.freeze import MANIFEST, ROOT, digest, write_json
from w6.run_heal import POLICY, summarize


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe_file(root, relative):
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("Evidence path escapes bundle")
    return path


def verify(root):
    root = Path(root)
    frozen = read(root / "mutation-set-v1.json")
    meta = read(root / "metadata.json")
    record = read(root / "record/descriptors.json")
    record_meta = read(root / "record/metadata.json")
    frozen_sha = digest(root / "mutation-set-v1.json")
    if any(v != frozen_sha for v in (meta["manifest_sha256_lf"], record["manifest_sha256_lf"], record_meta["manifest_sha256_lf"])):
        raise ValueError("Manifest/record identity mismatch")
    if meta["record_sha256_lf"] != digest(root / "record/descriptors.json"):
        raise ValueError("Record descriptor checksum mismatch")
    if any(m["source_sha256_lf"] != frozen["source_sha256_lf"] for m in (meta, record_meta)):
        raise ValueError("Recorded/evaluated source differs from frozen source")
    if meta["policy"] != POLICY or meta["mode"] != "heal" or meta["held_out_accessed"]:
        raise ValueError("Unexpected evaluation policy/scope")
    expected = {(task, mode, seed) for task in frozen["task_ids"] for mode in frozen["mutation_modes"]
                for seed in ([0] if mode == "M0" else frozen["development_seeds"])}
    traces = [read(p) for p in sorted((root / "traces").glob("*.json"))]
    rows = [t["result"] for t in traces]
    actual = [(r["task_id"], r["mutation"], r["mutation_seed"]) for r in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Missing/duplicate task-mode-seed rows")
    if not all(record["task_success"].get(t) for t in frozen["task_ids"]):
        raise ValueError("M0 recording was not successful for every task")
    expected_descriptors = {f"{t}:{i}" for t in frozen["task_ids"] for i, s in enumerate(SCRIPTS[t]) if s["do"] != "goto"}
    if set(record["descriptors"]) != expected_descriptors:
        raise ValueError("Incomplete descriptor coverage")
    for value in record["descriptors"].values():
        if {"element_id", "xpath", "target_element_id", "ref_eid"} & value["descriptor"].keys():
            raise ValueError("Forbidden answer/location field in recorded descriptor")
    snapshots = 0
    for tree in (root, root / "record"):
        for file in sorted((tree / "traces").glob("*.json")):
            detail = read(file)
            result, steps = detail["result"], detail["steps"]
            if [s["index"] for s in steps] != list(range(len(steps))):
                raise ValueError("Non-contiguous trace")
            if result["success"] and (len(steps) != len(SCRIPTS[result["task_id"]]) or not all(s["success"] for s in steps)):
                raise ValueError("Success reported for incomplete/failed actions")
            if result["steps_done"] != sum(s["success"] for s in steps):
                raise ValueError("Step count mismatch")
            healed = [s for s in steps if s.get("heal")]
            if result["heal_attempts"] != len(healed):
                raise ValueError("Healing attempt count mismatch")
            for step in steps:
                if step.get("heal") and step.get("b0_count") == 1:
                    raise ValueError("Healing triggered outside the frozen policy")
                if step.get("heal") and step["heal"]["status"] == "abstain":
                    if step["success"]:
                        raise ValueError("Action succeeded after abstention")
                if step.get("snapshot"):
                    features_file = safe_file(tree, step["snapshot"])
                    features = read(features_file)
                    html = features_file.with_name("dom.html").read_bytes()
                    if hashlib.sha256(html).hexdigest() != features["html_sha256"]:
                        raise ValueError("Snapshot HTML checksum mismatch")
                    snapshots += 1
    result_summary = summarize(rows, len(expected))
    published = read(root / "summary.json")
    # Medians and counts do not depend on trace ordering.
    if result_summary != published:
        raise ValueError("Summary differs from per-task traces")
    with (root / "results.csv").open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    if len(csv_rows) != len(rows):
        raise ValueError("CSV row count mismatch")
    indexed = {(r["task_id"], r["mutation"], str(r["mutation_seed"])): r for r in rows}
    if len({(r["task_id"], r["mutation"], r["mutation_seed"]) for r in csv_rows}) != len(rows):
        raise ValueError("Duplicate CSV identity")
    for row in csv_rows:
        expected_row = indexed[(row["task_id"], row["mutation"], row["mutation_seed"])]
        if any((str(expected_row[k]) if expected_row[k] is not None else "") != v for k, v in row.items()):
            raise ValueError("CSV differs from trace result")
    return {"verified": True, "task_runs": len(rows), "record_descriptors": len(expected_descriptors),
            "snapshots_verified": snapshots, "source_files_frozen": len(frozen["source_sha256_lf"]),
            "note": "Integrity/coverage verification, not independent target correctness labels."}


def pack(run, record, output, demo=None):
    output.mkdir(parents=True, exist_ok=False)
    for source, target in ((run, output), (record, output / "record")):
        target.mkdir(parents=True, exist_ok=True)
        for name in ("metadata.json", "summary.json", "results.csv", "descriptors.json"):
            if (source / name).exists():
                shutil.copy2(source / name, target / name)
        for name in ("traces", "snapshots"):
            if (source / name).exists():
                shutil.copytree(source / name, target / name)
    shutil.copy2(MANIFEST, output / "mutation-set-v1.json")
    if demo:
        demo_out = output / "demo"
        demo_out.mkdir()
        for name in ("metadata.json", "summary.json", "results.csv", "traces"):
            source = demo / name
            if source.is_dir():
                shutil.copytree(source, demo_out / name)
            elif source.exists():
                shutil.copy2(source, demo_out / name)
        for source in demo.glob("*.png"):
            shutil.copy2(source, demo_out / source.name)
    write_json(output / "validation.json", verify(output))
    hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "checksums.json", {"algorithm": "SHA-256 raw bytes", "files": hashes})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--demo", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "Evidence/W06/online")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        checksums = read(args.verify / "checksums.json")
        for path, sha in checksums["files"].items():
            if hashlib.sha256(safe_file(args.verify, path).read_bytes()).hexdigest() != sha:
                raise ValueError(f"Artifact checksum mismatch: {path}")
        print(json.dumps(verify(args.verify)))
    elif args.run and args.record:
        pack(args.run, args.record, args.output, args.demo)
        print(json.dumps(verify(args.output)))
    else:
        parser.error("Provide --verify, or --run and --record")


if __name__ == "__main__":
    main()
