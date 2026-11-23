"""Expose validated W3 steps and semantic control hints without fixed locators."""
from candidates.generator import WEIGHTS
from planner.workflows import validate_workflow


CONTROL_HINTS = {
    "search_email": ("input", "label", "Tìm khách hàng theo email"),
    "search_submit": ("button", "text", "Tìm"),
    "customer_open": ("a", "text", ""),
    "customer_edit": ("a", "text", "Sửa"),
    "edit_phone": ("input", "label", "Số điện thoại"),
    "save_phone": ("button", "text", "Lưu"),
    "new_name": ("input", "label", "Tên khách hàng"),
    "new_email": ("input", "label", "Email"),
    "new_phone": ("input", "label", "Số điện thoại"),
    "save_customer": ("button", "text", "Lưu"),
    "order_customer": ("select", "label", "Khách hàng"),
    "add_line": ("button", "text", "Thêm dòng"),
    "line_sku": ("select", "label", "Sản phẩm"),
    "line_qty": ("input", "label", "Số lượng"),
    "save_order": ("button", "text", "Xác nhận tạo đơn"),
    "ticket_order": ("select", "label", "Đơn hàng"),
    "ticket_subject": ("input", "label", "Tiêu đề"),
    "save_ticket": ("button", "text", "Gửi"),
    "ticket_open": ("a", "text", "{argument}"),
    "close_note": ("textarea", "label", "Ghi chú"),
    "close_ticket": ("button", "text", "Đóng ticket"),
}


def step_descriptor(step):
    """Translate a planner target to the feature schema expected by the ranker."""
    context = step.get("context", {})
    descriptor = {**dict.fromkeys(WEIGHTS, ""), "options": []}
    hint = CONTROL_HINTS.get(context.get("control"))
    if hint:
        tag, feature, name = hint
        descriptor.update(tag=tag)
        descriptor[feature] = name.format(argument=context.get("argument", ""))
    else:
        descriptor.update(text=step["target"], label=step["target"])
    return descriptor


def semantic_steps(plan, workflow, request, intent):
    validate_workflow(plan, workflow, request, intent)
    if plan["status"] != "ready":
        return []
    return [{"index": i, "action": step["action"], "target": step["target"],
             "value": step["value"], "url": step["url"],
             "context": {"control": meta["control"], "row": meta.get("row", 0), "argument": meta.get("argument", ""),
                         "operation_index": meta["operation_index"]},
             "requires_binding": [ref for ref in ("$last_customer", "$last_order")
                                  if ref in step["target"] or ref in step["value"]]}
            for i, (step, meta) in enumerate(zip(plan["steps"], workflow["steps"]))]


def bind_step(step, bindings):
    """Only the executor can supply observed runtime values; never infer IDs."""
    result = {**step, "context": dict(step["context"])}
    for ref in step["requires_binding"]:
        value = bindings.get(ref)
        if not isinstance(value, str) or not value.strip() or value.startswith("$"):
            raise ValueError("Missing observed runtime binding: " + ref)
        for field in ("target", "value"):
            result[field] = result[field].replace(ref, value)
        if "argument" in result["context"]:
            result["context"]["argument"] = result["context"]["argument"].replace(ref, value)
    result["requires_binding"] = []
    return result
