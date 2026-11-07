"""Descriptor = đặc trưng của phần tử mà locator B0 trỏ tới ở M0 (lượt ghi), dùng để chữa ở lượt sau."""
from candidates.features import controls
from healing.ordinal import add_ordinals

# Khóa không được đưa vào descriptor: định danh theo trang, và vị trí thao tác.
_DROP = {"element_id", "xpath"}


def controls_with_xpath(snapshot):
    """Control thao tác được của một snapshot, kèm `xpath` để executor thao tác sau khi chữa."""
    xp = {e["element_id"]: e["locator"]["value"] for e in snapshot["elements"] if e.get("locator")}
    return [{**c, "xpath": xp.get(c["element_id"], "")} for c in controls(snapshot)]


def build_descriptor(snapshot, element_id):
    """Rút descriptor (JSON được) của một control, gồm `ord` và `ord_n`. Không chứa element_id hay xpath."""
    for c in add_ordinals(controls(snapshot)):
        if c["element_id"] == element_id:
            return {k: v for k, v in c.items() if k not in _DROP}
    raise KeyError(f"{element_id} không phải control thao tác được trong snapshot")
