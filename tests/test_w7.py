"""W7 integration checks. Injected resolver decisions are NOT real-model evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from playwright.sync_api import sync_playwright

from dom_snapshot.run import isolated_app
from planner.core import make_request
from planner.workflows import compile_intent
from w6.freeze import ROOT, validate_manifest
from w6.run_heal import replay as record_replay
from w7.contracts import make_request as fallback_request, validate_decision
from w7.planner_adapter import bind_step, semantic_steps
from w7.run_agent import replay, summarize
from w7.report import compare, price_usage


def test_handoff_packet_projects_runtime_data_and_aliases():
    desc = {"tag": "input", "label": "Email", "xpath": "secret", "target_element_id": "answer"}
    cands = [{"element_id": "e7", "xpath": "/html/input", "tag": "input", "type": "text",
              "form": "/customers?mutation=W5_ID&seed=17", "target_element_id": "answer"},
             {"element_id": "e8", "xpath": "/html/button", "tag": "button"}]
    packet, bindings = fallback_request(desc, cands, "fill", {"reason": "low_margin", "topk": [{"eid": "e7", "score": .8}]})
    payload = json.dumps(packet)
    assert "xpath" not in payload and "target_element_id" not in payload and "e7" not in payload
    assert "mutation=" not in payload and "seed=" not in payload
    assert len(packet["candidates"]) == 1
    assert packet["semantic_topk"] == [{"candidate_id": "c1", "score": .8}]
    assert validate_decision({"decision": "select", "candidate_id": "c1", "reason": "ok"}, bindings) == "/html/input"
    with pytest.raises(ValueError):
        validate_decision({"decision": "select", "candidate_id": "c9", "reason": "bad"}, bindings)
    with pytest.raises(ValueError):
        validate_decision({"decision": "abstain", "candidate_id": "c1", "reason": "bad"}, bindings)


def test_summary_keeps_unknown_tokens_unknown():
    result = summarize([], 2, [{"usage": None}])
    assert result["input_tokens"] is None and result["usage_complete"] is False
    assert result["complete"] is False and result["wrong_heal_count"] is None


def test_cost_separates_cached_tokens_and_does_not_price_timeouts_as_zero():
    rates = {"date": "test", "source": "fixture", "input_per_million": 2,
             "cached_input_per_million": 1, "output_per_million": 4}
    calls = [{"usage": {"input_tokens": 1000, "output_tokens": 100,
                        "input_tokens_details": {"cached_tokens": 200}}}]
    assert price_usage(calls, rates) == .0022
    assert price_usage(calls + [{"usage": None}], rates) is None
    with pytest.raises(ValueError):
        price_usage(calls, {**rates, "input_per_million": float("nan")})


def test_report_rejects_different_experimental_conditions(tmp_path):
    metadata = {"agent": "b0", "manifest_sha256_lf": "a", "w7_source_sha256_lf": {},
                "task_ids": ["T001"], "mutations": ["M0"], "development_seeds": [17, 18],
                "locator": "css", "policy": {"llm": False, "min_margin": .02}}
    summary = {"complete": True, "expected_rows": 1, "task_success_rate": 1}
    paths = [tmp_path / "b0", tmp_path / "a1"]
    for index, path in enumerate(paths):
        (path / "traces").mkdir(parents=True)
        meta = {**metadata, "agent": "a1" if index else "b0", "locator": "xpath" if index else "css"}
        (path / "metadata.json").write_text(json.dumps(meta))
        (path / "summary.json").write_text(json.dumps(summary))
        (path / "traces/one.json").write_text(json.dumps({"result": {"task_id": "T001", "mutation": "M0", "mutation_seed": 0}}))
    with pytest.raises(ValueError, match="Runs differ"):
        compare(paths)


def test_adapter_preserves_targets_and_refuses_invented_runtime_ids():
    request = make_request("Đổi số của hoa@example.com thành 0909998888", max_steps=30)
    intent = {"operations": [{"kind": "update_phone", "items": [], "slots": [
        {"key": "customer_email", "value": "hoa@example.com", "source": "hoa@example.com"},
        {"key": "phone", "value": "0909998888", "source": "0909998888"}]}]}
    compiled = compile_intent(intent, request)
    steps = semantic_steps(compiled["plan"], compiled["workflow"], request, intent)
    assert any(s["context"]["control"] == "edit_phone" for s in steps)
    step = {"target": "Đơn $last_order", "value": "$last_order", "context": {}, "requires_binding": ["$last_order"]}
    with pytest.raises(ValueError):
        bind_step(step, {})
    assert bind_step(step, {"$last_order": "ORD-1007"})["value"] == "ORD-1007"


class BrowserInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="w7-tests-")
        cls.out = Path(cls.temp.name)
        cls.app_cm = isolated_app(cls.out)
        cls.base = cls.app_cm.__enter__()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.task = json.loads((ROOT / "tasks/tasks_w4.json").read_text(encoding="utf-8"))[0]
        record = cls.out / "record"
        record.mkdir()
        cls.descriptors = {}
        result = record_replay(cls.browser, cls.base, cls.task, "M0", 0, "record", "css", record, cls.descriptors, {})
        assert result["success"]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.app_cm.__exit__(None, None, None)
        cls.temp.cleanup()

    def run_agent(self, agent, *, mutation="W5_ID", resolver=None, client=None):
        out = self.out / self._testMethodName
        out.mkdir()
        row = replay(self.browser, self.base, self.task, mutation, 0 if mutation == "M0" else 17,
                     agent, "css", out, self.descriptors, {}, resolver=resolver, client=client)
        trace = json.loads(next((out / "traces").glob("*.json")).read_text())
        return row, trace

    def test_b0_on_m0_does_not_invoke_healer(self):
        with patch("w7.run_agent.heal", side_effect=AssertionError("B0 must not heal")):
            row, _ = self.run_agent("b0", mutation="M0")
        self.assertTrue(row["success"])

    def test_b0_on_id_fails_and_retains_snapshot(self):
        row, trace = self.run_agent("b0")
        self.assertFalse(row["success"])
        self.assertIn("snapshot", trace["steps"][-1])

    def test_a1_recovers_without_any_model(self):
        row, _ = self.run_agent("a1")
        self.assertTrue(row["success"], row)
        self.assertEqual(row["llm_requests"], 0)

    def test_a2_requires_trungs_policy(self):
        with self.assertRaisesRegex(ValueError, "requires a resolver"):
            self.run_agent("a2")

    def test_a2_accepts_valid_injected_decision(self):
        from healing.heal import heal as actual_heal
        selections = []
        def force_abstain(*args, **kwargs):
            result = actual_heal(*args, **kwargs)
            selections.append(result["xpath"])
            return {**result, "status": "abstain", "reason": "test_fixture", "xpath": ""}
        def resolver(packet, client):
            # Oracle allowed ONLY inside this software test, never in production.
            from w7.contracts import safe_features
            expected = selections[-1]
            candidates = captured[-1]
            wanted = next(c for c in candidates if c["xpath"] == expected)
            offered = next(c for c in packet["candidates"] if {k: v for k, v in c.items() if k != "candidate_id"} == safe_features(wanted))
            return {"decision": "select", "candidate_id": offered["candidate_id"], "reason": "offline fixture"}
        from w7.contracts import make_request as real_request
        captured = []
        def remember(desc, candidates, *args, **kwargs):
            captured.append(candidates)
            return real_request(desc, candidates, *args, **kwargs)
        with patch("w7.run_agent.heal", side_effect=force_abstain), patch("w7.run_agent.make_request", side_effect=remember):
            row, _ = self.run_agent("a2", resolver=resolver, client=SimpleNamespace(calls=[]))
        self.assertTrue(row["success"], row)
        self.assertGreater(row["fallback_attempts"], 0)
        self.assertEqual(row["llm_requests"], 0)  # Never misreport a fixture as a real call.

    def test_a2_rejects_invented_candidate_and_stops(self):
        def resolver(packet, client):
            return {"decision": "select", "candidate_id": "made-up", "reason": "bad"}
        with patch("w7.run_agent.heal", return_value={"status": "abstain", "reason": "low_margin", "topk": []}):
            row, trace = self.run_agent("a2", resolver=resolver, client=SimpleNamespace(calls=[]))
        self.assertFalse(row["success"])
        self.assertFalse(trace["steps"][-1]["success"])

    def test_a2_rejects_dom_changed_during_resolution(self):
        from w7.run_agent import validate_replacement
        with self.browser.new_page() as page:
            page.set_content('<input id="x">')
            html = page.evaluate("() => '<!DOCTYPE html>\\n' + document.documentElement.outerHTML")
            page.locator("body").evaluate("el => el.prepend(document.createElement('input'))")
            with self.assertRaisesRegex(ValueError, "DOM changed"):
                validate_replacement(page, "//*[@id='x']", "fill", html)

    def test_readonly_replacement_is_rejected_before_fill(self):
        from w7.run_agent import validate_replacement
        with self.browser.new_page() as page:
            page.set_content('<input id="x" readonly>')
            html = page.evaluate("() => '<!DOCTYPE html>\\n' + document.documentElement.outerHTML")
            with self.assertRaisesRegex(ValueError, "not editable"):
                validate_replacement(page, "//*[@id='x']", "fill", html)


def test_w6_frozen_source_still_valid():
    assert validate_manifest()["mutation_set_version"] == "w6-v1"
