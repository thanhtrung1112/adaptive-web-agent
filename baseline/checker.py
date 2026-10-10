"""Chấm success criteria của task bằng JSON API của MiniBiz (không dựa vào giao diện).

`get(path)` trả về JSON của API. Runner truyền hàm gọi qua chính browser context của task,
vì /api/session/last_viewed_customer phụ thuộc cookie phiên của trình duyệt đó.
"""
import csv
import urllib.parse
from collections import Counter


def _api_check(get, c):
    data, exp = get(c["endpoint"]), c.get("expect", {})
    target = data
    if "count" in data:  # phản hồi dạng danh sách: {"count": n, "<khóa>": [...]}
        rows = next((v for v in data.values() if isinstance(v, list)), [])
        if "count" in exp and data["count"] != exp["count"]:
            return False, f"{c['endpoint']}: count={data['count']} (cần {exp['count']})"
        if len(rows) != data["count"]:
            return False, "count không khớp số bản ghi API"
        if not rows and exp.get("count") == 0:
            return (not exp.get("fields") and "items" not in exp), "kiểm tra tập rỗng"
        target = rows[0] if rows else None
    if target is None:
        return False, f"{c['endpoint']}: không có dữ liệu"
    for k, v in exp.get("fields", {}).items():
        if target.get(k) != v:
            return False, f"{c['endpoint']}: {k}={target.get(k)!r} (cần {v!r})"
    if "items" in exp:
        got = Counter((i["sku"], i["qty"]) for i in target.get("items", []))
        want = Counter((i["sku"], i["qty"]) for i in exp["items"])
        if got != want:
            return False, f"{c['endpoint']}: items={sorted(got)} (cần {sorted(want)})"
    if exp.get("linked_to_new_order"):
        email = urllib.parse.parse_qs(urllib.parse.urlparse(c["endpoint"]).query)["customer_email"][0]
        orders = get(f"/api/orders?customer_email={email}")["orders"]
        if len(orders) != 1 or target["order_id"] != orders[0]["id"]:
            return False, "ticket không gắn với đơn hàng vừa tạo"
    return True, "ok"


def _download_check(get, c, path):
    if not path:
        return False, "không có file tải về"
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not ({"id", "order_id"} & set(reader.fieldnames)):
            return False, "CSV thiếu cột mã đơn"
        rows = list(reader)
    got = Counter(r.get("id") or r.get("order_id") for r in rows)
    api = get(c["expect"]["order_ids_equal_to_api"])
    want = Counter(o["id"] for o in next(v for v in api.values() if isinstance(v, list)))
    return (got == want), ("ok" if got == want else f"csv orders={sorted(got)} (cần {sorted(want)})")


def check_all(get, task, download_path=None):
    msgs, ok = [], True
    for c in task["success_criteria"]:
        try:
            r, m = _api_check(get, c) if c["type"] == "api_check" else _download_check(get, c, download_path)
        except Exception as e:  # noqa: BLE001
            r, m = False, f"lỗi khi chấm: {e}"
        ok &= r
        msgs.append(m)
    return ok, "; ".join(msgs)
