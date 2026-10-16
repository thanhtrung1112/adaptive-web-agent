"""Candidate generator: chấm điểm giống nhau giữa phần tử gốc và các phần tử trên trang mới."""
import difflib

# Trọng số mỗi đặc trưng. Đặc trưng nào phần tử gốc không có thì bỏ qua (không phạt, không thưởng).
WEIGHTS = {"tag": 3, "type": 1, "text": 3, "label": 3, "placeholder": 1.5, "id": 2, "name": 2,
           "href": 2, "form": 1, "path": 1, "options": 1}


def text_sim(a, b):
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() if a and b else 0.0


def path_sim(a, b):
    pa, pb = a.split(" > "), b.split(" > ")
    common = 0
    for x, y in zip(pa, pb):
        if x != y:
            break
        common += 1
    return common / max(len(pa), len(pb))


def options_sim(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa | sb else 0.0


def score(desc, cand):
    """Trả về (điểm 0..1, điểm từng đặc trưng) để giải thích được vì sao ứng viên được xếp hạng đó."""
    total = used = 0.0
    parts = {}
    for key, weight in WEIGHTS.items():
        if not desc[key]:
            continue
        if key in ("tag", "type", "form"):
            s = 1.0 if desc[key] == cand[key] else 0.0
        elif key == "path":
            s = path_sim(desc[key], cand[key])
        elif key == "options":
            s = options_sim(desc[key], cand[key])
        else:
            s = text_sim(desc[key], cand[key])
        parts[key] = round(s, 2)
        total += weight * s
        used += weight
    return (total / used if used else 0.0), parts


def rank(desc, candidates, top_k=5):
    """Danh sách ứng viên xếp theo điểm giảm dần (hòa điểm thì giữ thứ tự trong DOM)."""
    scored = [(*score(desc, c), c) for c in candidates]
    scored.sort(key=lambda t: -t[0])
    return [{"element_id": c["element_id"], "score": round(s, 3), "parts": p} for s, p, c in scored[:top_k]]
