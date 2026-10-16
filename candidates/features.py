"""Đọc snapshot (schema v0.1) và rút đặc trưng của các phần tử có thể thao tác."""
import json
from collections import defaultdict
from pathlib import Path

SNAP_DIR = Path("results/w3/dom_samples_expanded_v0.1")
CONTROL_TAGS = {"a", "button", "input", "select", "textarea"}


def list_states():
    return sorted(d.name for d in SNAP_DIR.iterdir() if d.is_dir())


def load_state(state):
    return json.loads((SNAP_DIR / state / "features.json").read_text(encoding="utf-8"))


def controls(snap):
    """Các control người dùng thao tác được: đúng thẻ, đang hiện, không bị vô hiệu, không phải hidden."""
    by_id = {e["element_id"]: e for e in snap["elements"]}
    kids = defaultdict(list)
    for e in snap["elements"]:
        kids[e["parent_id"]].append(e)

    def path(e):  # ví dụ body > main > form > p[2] > input
        segs, cur = [], e
        while cur:
            same = [s for s in kids[cur["parent_id"]] if s["tag"] == cur["tag"]]
            segs.append(cur["tag"] if len(same) == 1 else f"{cur['tag']}[{same.index(cur) + 1}]")
            cur = by_id.get(cur["parent_id"])
        return " > ".join(reversed(segs))

    def form(e):
        cur = e
        while cur:
            if cur["tag"] == "form":
                return cur["attributes"].get("action", "")
            cur = by_id.get(cur["parent_id"])
        return ""

    out = []
    for e in snap["elements"]:
        a = e["attributes"]
        if e["tag"] not in CONTROL_TAGS or not e["visible"] or not e["enabled"] or a.get("type") == "hidden":
            continue
        out.append({
            "element_id": e["element_id"], "tag": e["tag"], "id": a.get("id", ""), "name": a.get("name", ""),
            "type": a.get("type", ""), "text": e["text"] if e["tag"] in ("a", "button") else "",
            "label": e["label"] or "", "placeholder": a.get("placeholder", ""), "href": a.get("href", ""),
            "form": form(e), "path": path(e),
            "options": [k["text"] for k in kids[e["element_id"]] if k["tag"] == "option"] if e["tag"] == "select" else [],
        })
    return out
