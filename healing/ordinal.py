"""Thứ tự trong nhóm control cùng loại: để phân biệt các dòng lặp (ví dụ dòng sản phẩm 1 và 2 của form đơn hàng)."""
from collections import Counter


def signature(c):
    """Chữ ký ổn định qua mutation id/nhãn/bọc: thẻ, type, form đích."""
    return (c["tag"], c["type"], c["form"])


def add_ordinals(cands):
    """Thêm `ord` (vị trí trong nhóm cùng chữ ký, theo thứ tự DOM) và `ord_n` (kích thước nhóm)."""
    total = Counter(signature(c) for c in cands)
    seen, out = Counter(), []
    for c in cands:
        s = signature(c)
        out.append({**c, "ord": seen[s], "ord_n": total[s]})
        seen[s] += 1
    return out
