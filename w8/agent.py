"""W7 semantic Agent adapter for the W8 trace/replay harness.

The planner and resolver choose targets; TraceSession remains the only browser
write interface so every browser action is recorded and replayable.
"""
import re
from urllib.parse import urlsplit

from dom_snapshot.capture import capture
from healing.heal import heal
from llm.client import CallScope, Config, StructuredClient
from llm.fallback import resolve as resolve_fallback
from planner.core import make_request
from w6.run_heal import POLICY
from w7.context import runtime_candidates
from w7.contracts import compatible, make_request as make_fallback_request, validate_decision, without_mutation_context
from w7.plan import plan_with_client
from w7.planner_adapter import bind_step, step_descriptor
from w7.run_agent import validate_replacement
from w7.target_check import check_found, check_link_destination, DEFAULT_THRESHOLD


def _resolve_target(page, base, step, client, trace_index):
    """Resolve one semantic step to a unique, live XPath without executing it."""
    if step.get("requires_binding"):
        raise ValueError("Unresolved runtime binding")

    action = step["action"]
    context = step.get("context", {})
    control = context.get("control")
    snapshot_id = f"w8-{trace_index:03d}"
    html, snapshot = capture(page, snapshot_id, "w8-agent", snapshot_id, {})
    descriptor = step_descriptor(step)
    candidates = [
        candidate for candidate in runtime_candidates(snapshot)
        if compatible(action, candidate)
        and (not descriptor["tag"] or candidate["tag"] == descriptor["tag"])
    ]

    if control in ("search_submit", "save_phone"):
        path = urlsplit(page.url).path
        pattern = r"/customers" if control == "search_submit" else r"/customers/\d+/edit"
        if not re.fullmatch(pattern, path):
            raise ValueError(f"Unexpected customer form page for {control}")
        descriptor.update(type="submit", form=path, ord_n=1)
        candidates = [
            candidate for candidate in candidates
            if candidate["type"] == "submit"
            and not check_link_destination(
                page.url, path, without_mutation_context(candidate["form"]),
            )["likely_wrong"]
        ]
        if len(candidates) != 1:
            raise ValueError(f"Expected one submit button for customer form {path}")
    elif control == "customer_open":
        email = context["argument"].casefold()
        candidates = [
            candidate for candidate in candidates
            if email in candidate["context_text"].casefold().split()
            and re.fullmatch(r"/customers/\d+", urlsplit(candidate.get("href", "")).path)
        ]
        if len(candidates) != 1:
            raise ValueError("Customer search must identify exactly one detail link")
        descriptor["href"] = candidates[0]["href"]
    elif control == "customer_edit":
        path = urlsplit(page.url).path
        if not re.fullmatch(r"/customers/\d+", path):
            raise ValueError("Expected a customer detail page")
        descriptor["href"] = path + "/edit"
    elif control in ("line_qty", "line_sku"):
        legend = f"Sản phẩm {context['row']} "
        candidates = [
            candidate for candidate in candidates
            if (candidate["context_text"] + " ").startswith(legend)
        ]

    by_xpath = {candidate["xpath"]: candidate for candidate in candidates}
    exact = {
        candidate["xpath"] for candidate in candidates
        if any(descriptor[key] and descriptor[key] == candidate[key]
               for key in ("text", "label"))
    }

    def assess(xpath):
        candidate = by_xpath[xpath]

        # Customer edit links must match the exact customer URL observed
        # from the currently opened detail page.
        if control == "customer_edit":
            expected_path = urlsplit(descriptor["href"]).path
            actual_path = urlsplit(candidate.get("href", "")).path
            matches = bool(expected_path) and actual_path == expected_path

            return {
                "found": matches,
                "score": 1.0 if matches else 0.0,
                "threshold": 1.0,
                "likely_wrong": not matches,
                "reason": (
                    "bound_customer_edit_href"
                    if matches else "customer_edit_href_mismatch"
                ),
            }

        if exact and not (descriptor["href"] or descriptor["form"]):
            matches = exact == {xpath}
            return {
                "likely_wrong": not matches,
                "reason": "unique_control_name" if matches else "control_name_mismatch",
            }

        return check_found(
            descriptor, candidate, step["target"], DEFAULT_THRESHOLD, page_url=page.url,
        )

    semantic = heal(
        descriptor, candidates, mode=POLICY["mode"],
        min_margin=POLICY["min_margin"], min_score=POLICY["min_score"],
        use_order=False,
    )
    xpath = semantic["xpath"] if semantic["status"] == "healed" else None
    diagnostic = None
    decision = None

    if xpath:
        diagnostic = assess(xpath)
        if diagnostic["likely_wrong"]:
            xpath = None

    if xpath is None and candidates:
        reason = diagnostic["reason"] if diagnostic else semantic["reason"]
        packet, bindings = make_fallback_request(
            descriptor, candidates, action,
            {**semantic, "reason": reason},
            objective=step["target"],
        )
        decision = resolve_fallback(packet, CallScope(client))
        xpath = validate_decision(decision, bindings)
        if xpath:
            diagnostic = assess(xpath)
            if diagnostic["likely_wrong"]:
                xpath = None

    if not xpath:
        reason = diagnostic["reason"] if diagnostic else semantic["reason"]
        raise ValueError("Matcher/fallback abstained: " + str(reason))

    validate_replacement(page, xpath, action, html)
    decision_record = {
        "source": "llm_fallback" if decision is not None else "semantic",
        "semantic_status": semantic.get("status"),
        "semantic_reason": semantic.get("reason"),
        "target_check": diagnostic,
    }
    if decision is not None:
        decision_record["fallback"] = decision
    return xpath, decision_record


def _capture_order_binding(page):
    """Read the order ID from the actual post-save URL, never predict an ID."""
    match = re.fullmatch(r"/orders/(ORD-\d+)", urlsplit(page.url).path)
    if not match:
        raise ValueError("Could not observe the newly created order ID")
    return match.group(1)


def producer(session, task):
    """W8 callback: producer(session, task), compatible with w8.harness.run_case."""
    client = None
    audit_path = session.output / "llm-calls" / f"{task['id']}.jsonl"
    try:
        client = StructuredClient(
            Config.from_env(
                max_requests=100,
                max_output_tokens=1024,
                max_reserved_output_tokens=102400,
            ),
            audit_path=audit_path,
        )
        request = make_request(task["goal"], task["start_url"], task["max_steps"])
        planned = plan_with_client(request, client)
        if planned["plan"]["status"] != "ready":
            raise ValueError("W7 planner needs clarification or does not support this task")

        bindings = {}
        for index, raw_step in enumerate(planned["semantic_steps"]):
            step = bind_step(raw_step, bindings) if raw_step.get("requires_binding") else raw_step
            if step["action"] == "navigate":
                session.act(
                    {"action": "navigate", "url": step["url"]},
                    decision={"source": "planner", "control": "navigate"},
                )
                continue

            xpath, decision = _resolve_target(
                session.page, session.base, step, client, index,
            )
            action = step["action"]
            request = {
                "action": action,
                "locator": {"strategy": "xpath", "value": xpath},
            }
            if action == "fill":
                request["value"] = str(step["value"])
            elif action == "select":
                # Resolve the planner's observed token to one visible option label.
                # W8's harness executes the label, while the DOM may expose a
                # longer label such as "ORD-1006 — customer@example.com".
                option = session.page.locator("xpath=" + xpath).evaluate(
                    """(control, target) => {
                        const matches = [...control.options].filter(option =>
                            !option.matches(':disabled') &&
                            (option.value === target || option.label === target ||
                             option.label.split(' — ').includes(target)));
                        return matches.length === 1 ? matches[0].label : null;
                    }""",
                    str(step["value"]),
                )
                if not option:
                    raise ValueError("The requested select option must be unique")
                request["label"] = option
            elif action not in ("click", "download"):
                raise ValueError("Unsupported W7 action: " + str(action))

            decision.update(control=step.get("context", {}).get("control"))
            session.act(request, decision=decision)

            if step.get("context", {}).get("control") == "save_order":
                bindings["$last_order"] = _capture_order_binding(session.page)
    finally:
        if client is not None:
            client.close()
