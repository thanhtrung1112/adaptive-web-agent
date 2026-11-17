"""Expose validated W3 steps to a future semantic executor, without fixed locators."""
from planner.workflows import validate_workflow


def semantic_steps(plan, workflow, request, intent):
    validate_workflow(plan, workflow, request, intent)
    if plan["status"] != "ready":
        return []
    return [{"index": i, "action": step["action"], "target": step["target"],
             "value": step["value"], "url": step["url"],
             "context": {"control": meta["control"], "row": meta.get("row", 0),
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
    result["requires_binding"] = []
    return result
