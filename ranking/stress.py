"""Kịch bản khó hơn W3, dựng trên candidates.mutate (vẫn là mô phỏng trên snapshot, chưa phải mutation thật)."""
import copy

from candidates.mutate import mutate

CONTROL_TAGS = {"a", "button", "input", "select", "textarea"}


def flatten(snap):
    """Đưa mọi control về cùng một thẻ cha dưới body: mất thông tin form và vị trí trong cây (giống đổi layout)."""
    s = copy.deepcopy(snap)
    body = next(e for e in s["elements"] if e["tag"] == "body")
    box = {**copy.deepcopy(body), "element_id": "flat0", "tag": "div", "attributes": {}, "label": None,
           "name_hint": None, "text": "", "parent_id": body["element_id"]}
    out = []
    for e in s["elements"]:
        if e["tag"] in CONTROL_TAGS:
            e["parent_id"] = "flat0"
        out.append(e)
        if e is body:
            out.append(box)
    s["elements"] = out
    return s


def stress_mutate(snap, kind, seed=0):
    """kind: các kiểu của candidates.mutate, hoặc flatten, hoặc hard (id + nhãn đồng nghĩa + nút mồi + flatten)."""
    if kind == "flatten":
        return flatten(snap)
    if kind == "hard":
        s = mutate(snap, "ids", seed)
        s = mutate(s, "labels", seed)
        s = mutate(s, "decoy", seed)
        return flatten(s)
    return mutate(snap, kind, seed)
