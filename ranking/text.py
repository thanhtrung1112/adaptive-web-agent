"""Chuyển một control (kết quả của candidates.features.controls) thành câu ngắn để đưa vào mô hình embedding."""

KIND = {"a": "liên kết", "button": "nút", "select": "ô chọn", "textarea": "ô nhập văn bản"}


def element_text(c):
    name = c["text"] or c["label"] or c["placeholder"] or ""
    parts = [f"{KIND.get(c['tag'], 'ô nhập')} {name}".strip()]
    if c["options"]:
        parts.append("lựa chọn: " + ", ".join(c["options"][:5]))
    if c["form"]:
        parts.append("trong biểu mẫu " + c["form"])
    return "; ".join(parts)
