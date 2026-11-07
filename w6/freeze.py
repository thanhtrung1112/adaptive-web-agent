"""Freeze development seeds and audit actual DOM variation, excluding transport context."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.mutations import Node, Tree
from app.mutations_w5 import MODES, VERSION, mutate

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/w6-mutation-set-v1.json"
SEEDS = (17, 18)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def source_hashes():
    paths = [p for folder in ("app", "baseline", "dom_snapshot", "candidates", "ranking", "healing", "w6")
             for p in (ROOT / folder).rglob("*")
             if p.suffix in (".py", ".js", ".css", ".html") and "__pycache__" not in p.parts]
    paths += [ROOT / "data/seed_v1.json", ROOT / "tasks/tasks_w4.json"]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def structural_hash(html):
    """Do not mistake seed URL/hidden fields/script config for independent DOM variants."""
    def clean(node):
        if isinstance(node, str):
            return node.strip() or None
        if node.tag == "input" and node.attrs.get("type") == "hidden" and node.attrs.get("name") in ("mutation", "seed"):
            return None
        attrs = dict(node.attrs)
        for key in ("href", "action", "src"):
            if attrs.get(key):
                url = urlsplit(attrs[key])
                query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k not in ("mutation", "seed")]
                attrs[key] = urlunsplit(url._replace(query=urlencode(query)))
        children = [value for child in node.children if (value := clean(child)) is not None]
        return [node.tag, sorted(attrs.items()), children]
    payload = json.dumps(clean(Tree(html).root), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def freeze(dataset, output=MANIFEST):
    pages = sorted((Path(dataset) / "snapshots").glob("M0-s0-*-step*/dom.html"))
    if not pages:
        raise ValueError("No M0 pre-action snapshots for the seed audit")
    audits = {}
    for name, seeds in (("previous_17_23", (17, 23)), ("frozen_17_18", SEEDS)):
        rows = []
        for page in pages:
            html = page.read_text(encoding="utf-8")
            rows.append({"state": page.parent.name, "reference_sha256_lf": digest(page),
                         "variants": {mode: [structural_hash(mutate(html, mode, seed)) for seed in seeds] for mode in MODES}})
        audits[name] = {"seeds": list(seeds), "states": len(rows),
                        "by_mutation": {mode: {"identical": sum(r["variants"][mode][0] == r["variants"][mode][1] for r in rows),
                                               "groups": len(rows),
                                               "unique_variants": sum(len(set(r["variants"][mode])) for r in rows)} for mode in MODES},
                        "rows": rows}
    tasks = json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))
    result = {"mutation_set_version": "w6-v1", "benchmark_version": VERSION,
              "partition": "development", "held_out_accessed": False,
              "mutation_modes": ["M0", *MODES], "development_seeds": list(SEEDS),
              "task_ids": [t["id"] for t in tasks], "expected_heal_rows": len(tasks) * (1 + len(MODES) * len(SEEDS)),
              "source_sha256_lf": source_hashes(),
              "audit_scope": "Pure mutation on M0 pre-action HTML; excludes seed/mutation transport fields. Not online task outcomes.",
              "seed_audit": audits}
    # Freeze before outcome evaluation, and fail instead of claiming seed diversity without evidence.
    if any(v["identical"] for v in audits["frozen_17_18"]["by_mutation"].values()):
        raise ValueError("New seeds still duplicate variants; inspect the audit before freezing")
    write_json(output, result)
    return result


def validate_manifest(path=MANIFEST):
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if result["source_sha256_lf"] != source_hashes():
        raise ValueError("Frozen source differs from checkout; audit and freeze again before measuring")
    if result["development_seeds"] != list(SEEDS) or result["mutation_modes"] != ["M0", *MODES]:
        raise ValueError("Unexpected W6-v1 modes/seeds")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=MANIFEST)
    args = parser.parse_args()
    result = freeze(args.dataset, args.output)
    for name, audit in result["seed_audit"].items():
        print(name, {m: v["identical"] for m, v in audit["by_mutation"].items()})


if __name__ == "__main__":
    main()
