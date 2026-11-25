import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from w8 import agent


class _FakeLocator:
    def evaluate(self, _script, target):
        return f"label::{target}"


class _FakePage:
    def __init__(self):
        self.url = "http://127.0.0.1:8000/about:blank"

    def locator(self, _selector):
        return _FakeLocator()


class _FakeSession:
    def __init__(self, output):
        self.output = Path(output)
        self.base = "http://127.0.0.1:8000"
        self.page = _FakePage()
        self.actions = []

    def act(self, request, *, decision=None):
        self.actions.append((request, decision))
        if request["action"] == "click" and request["locator"]["value"] == "//save_order":
            self.page.url = self.base + "/orders/ORD-1006"


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.closed = False

    def close(self):
        self.closed = True


def _step(action, control, value="", url="", requires_binding=None):
    step = {
        "action": action,
        "url": url,
        "value": value,
        "target": control,
        "context": {"control": control, "row": 1, "argument": value},
        "requires_binding": requires_binding or [],
    }
    return step


class W8AgentAdapterTests(unittest.TestCase):
    def test_capture_order_binding_uses_observed_detail_url(self):
        page = SimpleNamespace(url="http://127.0.0.1:8000/orders/ORD-1006")
        self.assertEqual(agent._capture_order_binding(page), "ORD-1006")

    def test_capture_order_binding_rejects_unobserved_id(self):
        page = SimpleNamespace(url="http://127.0.0.1:8000/orders")
        with self.assertRaises(ValueError):
            agent._capture_order_binding(page)

    def test_producer_binds_new_order_before_creating_ticket(self):
        steps = [
            _step("navigate", "navigate", url="/orders/new"),
            _step("select", "order_customer", "pham.ha@example.com"),
            _step("select", "line_sku", "SKU-100"),
            _step("fill", "line_qty", "2"),
            _step("click", "save_order"),
            _step("navigate", "navigate", url="/tickets/new"),
            _step("select", "ticket_order", "$last_order", requires_binding=["$last_order"]),
            _step("fill", "ticket_subject", "Hỏi thời gian giao"),
            _step("click", "save_ticket"),
        ]
        planned = {"plan": {"status": "ready"}, "semantic_steps": steps}
        with tempfile.TemporaryDirectory() as tmp:
            session = _FakeSession(tmp)
            with patch.object(agent, "StructuredClient", _FakeClient), \
                 patch.object(agent, "plan_with_client", return_value=planned), \
                 patch.object(agent, "_resolve_target",
                              side_effect=lambda page, base, step, client, index:
                              (f"//{step['context']['control']}", {"source": "semantic"})):
                agent.producer(session, {
                    "id": "T010", "goal": "create order then ticket",
                    "start_url": "/customers", "max_steps": 30,
                })

        ticket_select = next(
            request for request, _ in session.actions
            if request["action"] == "select"
            and request["locator"]["value"] == "//ticket_order"
        )
        self.assertEqual(ticket_select["label"], "label::ORD-1006")
        self.assertEqual(session.actions[-1][0]["locator"]["value"], "//save_ticket")


    def test_w7_workflows_compile_for_the_four_handoff_milestones(self):
        from planner.workflows import compile_intent
        from planner.intent import validate as validate_intent
        from w7.planner_adapter import semantic_steps

        task_map = {
            task["id"]: task for task in __import__("json").loads(
                (Path(__file__).resolve().parents[1] / "tasks/tasks_w8.json").read_text(encoding="utf-8")
            )
        }

        def slot(key, value, source):
            return {"key": key, "value": value, "source": source}

        def item(sku, quantity, source):
            return {"sku": sku, "quantity": quantity, "source": source}

        email = "nguyen.dung@example.com"
        goals = {
            "T003": {"operations": [{"kind": "update_phone", "slots": [
                slot("customer_email", email, email),
                slot("phone", "0987654321", "0987654321")], "items": []}]},
            "T004": {"operations": [{"kind": "create_order", "slots": [
                slot("customer_email", "pham.ha@example.com", "pham.ha@example.com")],
                "items": [item("SKU-100", 1, "SKU-100 số lượng 1"),
                          item("SKU-205", 3, "SKU-205 số lượng 3")]}]},
            "T007": {"operations": [{"kind": "create_ticket", "slots": [
                slot("order_id", "ORD-1002", "ORD-1002"),
                slot("subject", "Giao hàng chậm", "Giao hàng chậm")], "items": []}]},
            "T010": {"operations": [
                {"kind": "find_customer", "slots": [
                    slot("customer_email", "vo.tam@example.com", "vo.tam@example.com")], "items": []},
                {"kind": "create_order", "slots": [
                    slot("customer_email", "vo.tam@example.com", "vo.tam@example.com")],
                    "items": [item("SKU-100", 2, "SKU-100 số lượng 2")]},
                {"kind": "create_ticket", "slots": [
                    slot("order_id", "$last_order", "đơn hàng vừa tạo"),
                    slot("subject", "Hỏi thời gian giao", "Hỏi thời gian giao")], "items": []},
            ]},
        }

        for task_id, intent in goals.items():
            task = task_map[task_id]
            validate_intent(intent, task["goal"])
            request = {
                "goal": task["goal"],
                "start_url": task["start_url"],
                "max_steps": task["max_steps"],
            }
            compiled = compile_intent(intent, request)
            steps = semantic_steps(compiled["plan"], compiled["workflow"], request, intent)
            self.assertEqual(compiled["plan"]["status"], "ready", task_id)
            self.assertLessEqual(len(steps), task["max_steps"], task_id)
            if task_id == "T010":
                self.assertIn("$last_order", steps[-3]["requires_binding"] + steps[-2]["requires_binding"]
                              + steps[-1]["requires_binding"] + steps[-4]["requires_binding"]
                              + steps[-5]["requires_binding"])


if __name__ == "__main__":
    unittest.main()
