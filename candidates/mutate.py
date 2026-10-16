"""Mô phỏng thay đổi giao diện trên snapshot để thử generator ."""
import copy
import random
import re

SYNONYMS = {
    "Thêm khách hàng": "Khách hàng mới", "Xác nhận tạo đơn": "Hoàn tất đơn", "Thêm dòng": "Thêm sản phẩm",
    "Xuất CSV": "Tải CSV", "Đóng ticket": "Hoàn tất ticket", "Tạo ticket": "Mở yêu cầu", "Tạo đơn": "Đơn mới",
    "Cập nhật": "Áp dụng thay đổi", "Lưu": "Xác nhận", "Tìm": "Tìm kiếm", "Lọc": "Áp dụng", "Gửi": "Tạo mới",
    "Gán": "Phân công", "Sửa": "Chỉnh sửa", "Số điện thoại": "SĐT", "Tên khách hàng": "Họ và tên",
    "Tiêu đề": "Chủ đề", "Ghi chú": "Nội dung ghi chú", "Người xử lý": "Nhân viên phụ trách",
    "Trạng thái đơn hàng": "Tình trạng đơn", "Từ ngày (UTC)": "Bắt đầu", "Đến ngày (UTC)": "Kết thúc",
    "Email": "Thư điện tử", "Sản phẩm": "Mặt hàng", "Số lượng": "SL",
}
PATTERN = re.compile("|".join(r"(?<!\w)" + re.escape(k) + r"(?!\w)" for k in sorted(SYNONYMS, key=len, reverse=True)))


def _swap(text):
    return PATTERN.sub(lambda m: SYNONYMS[m.group(0)], text) if text else text


def mutate(snap, kind, seed=0):
    """kind: none | ids | labels | wrap | decoy | combined. element_id của phần tử gốc được giữ nguyên."""
    rng = random.Random(seed)
    s = copy.deepcopy(snap)
    kinds = {"combined": ("ids", "labels", "wrap")}.get(kind, (kind,))
    if "ids" in kinds:  # đổi id, name, class thành chuỗi ngẫu nhiên không liên quan
        for e in s["elements"]:
            for attr in ("id", "name", "class"):
                if attr in e["attributes"]:
                    e["attributes"][attr] = "x" + "".join(rng.choice("0123456789abcdef") for _ in range(6))
    if "labels" in kinds:  # đổi nhãn nút, nhãn ô nhập, placeholder bằng từ đồng nghĩa
        for e in s["elements"]:
            for key in ("text", "label", "name_hint"):
                e[key] = _swap(e[key])
            if "placeholder" in e["attributes"]:
                e["attributes"]["placeholder"] = _swap(e["attributes"]["placeholder"])
    if "wrap" in kinds or "decoy" in kinds:
        out, n = [], 0
        for e in s["elements"]:
            if e["tag"] in ("a", "button", "input", "select", "textarea") and e["parent_id"]:
                n += 1
                if "wrap" in kinds:  # thêm một lớp div bọc quanh control
                    wid = f"w{n}"
                    out.append({**copy.deepcopy(e), "element_id": wid, "tag": "div", "attributes": {}, "label": None,
                                "name_hint": None, "value": None, "checked": None, "selected": None})
                    e["parent_id"] = wid
                if "decoy" in kinds and e["tag"] == "button":  # thêm nút "mồi" cùng cha, khác chữ
                    d = copy.deepcopy(e)
                    d.update(element_id=f"d{n}", text="Hủy bỏ", name_hint=None)
                    d["attributes"] = {**d["attributes"], "id": f"decoy{n}"}
                    out.append(e)
                    out.append(d)
                    continue
            out.append(e)
        s["elements"] = out
    return s
