"""Actual OpenAI SDK through an in-memory HTTP transport; no network or API key."""
import json
import os
from unittest.mock import patch

import httpx2
import pytest
from openai import OpenAI

from llm.client import CallScope, Config, LLMError, StructuredClient
from w7.contracts import DECISION_SCHEMA


@pytest.fixture(autouse=True)
def isolate_local_credentials(monkeypatch, tmp_path):
    # Unit tests must not read a developer's real .env or inherit real keys.
    monkeypatch.setattr("llm.client.DOTENV_PATH", tmp_path / ".env")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


def test_loads_repo_env_from_any_working_directory_with_windows_bom(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('OPENAI_API_KEY="offline-placeholder"\nOPENAI_MODEL=gpt-4.1-mini\n', encoding="utf-8-sig")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    from llm.client import load_configuration
    load_configuration()
    assert os.environ["OPENAI_API_KEY"] == "offline-placeholder"
    assert Config.from_env().model == "gpt-4.1-mini"


def test_explicit_environment_wins_and_parent_env_is_not_loaded(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('OPENAI_API_KEY=from-file\nOPENAI_MODEL=from-file\n', encoding="utf-8")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert Config.from_env().model == "gpt-4.1-mini"
    assert os.environ["OPENAI_API_KEY"] == ""
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setattr("llm.client.DOTENV_PATH", child / ".env")
    Config.from_env()
    assert "OPENAI_API_KEY" not in os.environ


def response_body(text='{"decision":"abstain","candidate_id":null,"reason":"uncertain"}', status="completed"):
    return {"id": "resp_test", "object": "response", "created_at": 1, "status": status,
            "model": "gpt-4.1-mini-2025-04-14", "output": [{"id": "msg_test", "type": "message",
            "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": text, "annotations": []}]}],
            "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28,
                      "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}


def make_client(handler, **kwargs):
    sdk = OpenAI(api_key="offline-test-key", max_retries=0,
                 http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    return StructuredClient(sdk=sdk, **kwargs)


def test_repeated_smoke_uses_new_directory_without_touching_previous_result(tmp_path, monkeypatch, capsys):
    import llm.smoke as smoke
    original = tmp_path / "smoke-01"
    original.mkdir()
    previous = original / "result.json"
    previous.write_text('original evidence', encoding="utf-8")
    # Also exercise skipping an existing suffixed result, including a file.
    (tmp_path / "smoke-01-02").write_text("keep", encoding="utf-8")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx2.Response(200, json=response_body('{"ok":true}'))
    def factory(config, audit_path):
        return make_client(handler, config=config, audit_path=audit_path)
    monkeypatch.setattr(smoke, "StructuredClient", factory)
    monkeypatch.setattr("sys.argv", ["smoke", "--live", "--output", str(original)])
    assert smoke.main() == 0
    assert previous.read_text(encoding="utf-8") == "original evidence"
    target = tmp_path / "smoke-01-03"
    assert json.loads((target / "result.json").read_text())["success"] is True
    assert (target / "calls.jsonl").is_file()
    assert len(requests) == 1
    assert "API smoke: passed" in capsys.readouterr().out


def call(client):
    return client.generate_json(instructions="Test contract", payload={"candidates": []}, schema=DECISION_SCHEMA)


def test_actual_sdk_payload_usage_and_credential_free_audit(tmp_path):
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(200, json=response_body(), headers={"x-request-id": "req_test"})
    client = make_client(handler, audit_path=tmp_path / "calls.jsonl")
    try:
        assert call(client)["decision"] == "abstain"
        assert requests[0]["model"] == "gpt-4.1-mini"
        assert requests[0]["text"]["format"]["strict"] is True
        assert requests[0]["store"] is False
        assert "seed" not in requests[0] and "think" not in requests[0]
        event = client.calls[0]
        assert event["usage"]["input_tokens"] == 20
        assert event["request_id"] == "req_test"
        assert event["returned_model"] == "gpt-4.1-mini-2025-04-14"
        assert "offline-test-key" not in (tmp_path / "calls.jsonl").read_text()
    finally:
        client.close()


@pytest.mark.parametrize("body,code", [
    (response_body(status="incomplete"), "response_incomplete"),
    (response_body("not JSON"), "invalid_structured_output"),
    (response_body('{"decision":"select","candidate_id":"c1","reason":"x","extra":true}'), "invalid_structured_output"),
    ({**response_body(), "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]}, "model_refusal")])
def test_response_failures_preserve_usage(body, code):
    client = make_client(lambda req: httpx2.Response(200, json=body))
    try:
        with pytest.raises(LLMError, match=code):
            call(client)
        assert client.calls[0]["usage"]["output_tokens"] == 8
        assert client.calls[0]["status"] == "error"
    finally:
        client.close()


@pytest.mark.parametrize("status,code", [(401, "AuthenticationError"), (429, "RateLimitError"), (500, "InternalServerError")])
def test_provider_errors_never_copy_exception_body_and_never_retry(status, code, tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx2.Response(status, json={"error": {"message": "secret-error-body", "type": "test"}})
    client = make_client(handler, audit_path=tmp_path / "calls.jsonl")
    try:
        with pytest.raises(LLMError, match=code):
            call(client)
        assert len(requests) == 1
        assert client.calls[0]["usage"] is None
        assert "secret-error-body" not in (tmp_path / "calls.jsonl").read_text()
    finally:
        client.close()


def test_timeout_consumes_request_budget_and_retains_unknown_usage():
    requests = []
    def handler(request):
        requests.append(request)
        raise httpx2.ReadTimeout("sensitive-message", request=request)
    client = make_client(handler, config=Config(max_requests=1))
    try:
        with pytest.raises(LLMError, match="APITimeoutError"):
            call(client)
        with pytest.raises(LLMError, match="request_budget_exceeded"):
            call(client)
        assert len(requests) == 1
        assert client.calls[0]["usage"] is None
    finally:
        client.close()


def test_reservation_and_input_limit_prevent_http_calls():
    def unexpected(request):
        raise AssertionError("No HTTP call expected")
    client = make_client(unexpected, config=Config(max_output_tokens=64, max_reserved_output_tokens=32))
    try:
        with pytest.raises(LLMError, match="reservation_budget"):
            call(client)
        assert client.calls == []
    finally:
        client.close()
    client = make_client(unexpected, config=Config(max_input_chars=1))
    try:
        with pytest.raises(LLMError, match="input_budget"):
            call(client)
    finally:
        client.close()


def test_missing_key_fails_before_creating_sdk():
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
        with pytest.raises(LLMError, match="missing_api_key"):
            StructuredClient()


def test_step_scope_limits_repairs_even_when_run_budget_remains():
    client = make_client(lambda req: httpx2.Response(200, json=response_body()))
    try:
        scope = CallScope(client)
        call(scope)
        call(scope)
        with pytest.raises(LLMError, match="step_request_budget_exceeded"):
            call(scope)
        assert len(client.calls) == 2
    finally:
        client.close()


@pytest.mark.parametrize("settings", [{"timeout_seconds": float("nan")}, {"max_requests": 0}, {"model": " "}])
def test_invalid_configuration(settings):
    with pytest.raises(ValueError):
        Config(**settings)


def test_openai_planner_adapter_preserves_missing_data_status():
    from planner.core import make_request
    from w7.plan import plan_with_client
    intent = {"operations": [{"kind": "update_phone", "slots": [], "items": []}]}
    client = make_client(lambda req: httpx2.Response(200, json=response_body(json.dumps(intent))))
    try:
        result = plan_with_client(make_request("Đổi số điện thoại khách hàng", max_steps=30), client)
        assert result["plan"]["status"] == "needs_clarification"
        assert result["semantic_steps"] == []
        assert len(result["plan"]["questions"]) == 2
    finally:
        client.close()


def test_openai_planner_adapter_compiles_evidenced_intent():
    from planner.core import make_request
    from w7.plan import plan_with_client
    intent = {"operations": [{"kind": "update_phone", "items": [], "slots": [
        {"key": "customer_email", "value": "hoa@example.com", "source": "hoa@example.com"},
        {"key": "phone", "value": "0909998888", "source": "0909998888"}]}]}
    client = make_client(lambda req: httpx2.Response(200, json=response_body(json.dumps(intent))))
    try:
        result = plan_with_client(make_request("Đổi số của hoa@example.com thành 0909998888", max_steps=30), client)
        assert result["plan"]["status"] == "ready"
        assert any(s["value"] == "0909998888" for s in result["semantic_steps"])
        assert all("xpath" not in s for s in result["semantic_steps"])
    finally:
        client.close()
