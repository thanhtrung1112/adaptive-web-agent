"""Bounded OpenAI Responses transport with auditable usage and no hidden retries."""
import hashlib
import importlib.metadata
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_configuration():
    """Read only this repo's .env; explicit process variables take precedence.

    utf-8-sig accepts Windows-created files with a BOM. Never walk parent folders
    or log parsed values. override=False also preserves an explicitly blank key.
    """
    load_dotenv(dotenv_path=DOTENV_PATH, override=False, encoding="utf-8-sig", interpolate=False)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class LLMError(RuntimeError):
    """Only safe, fixed error codes are exposed to traces and command output."""


@dataclass(frozen=True)
class Config:
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 60
    max_output_tokens: int = 512
    max_requests: int = 20
    max_reserved_output_tokens: int = 10240
    max_input_chars: int = 24000

    def __post_init__(self):
        if not self.model or not self.model.strip():
            raise ValueError("model must not be empty")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        for name in ("max_output_tokens", "max_requests", "max_reserved_output_tokens", "max_input_chars"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(name + " must be a positive integer")

    @classmethod
    def from_env(cls, **overrides):
        load_configuration()
        return cls(model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"), **overrides)


class StructuredClient:
    """One SDK request per call. Failed requests also consume the run budget.

    The injected sdk argument is for offline tests; production always uses OpenAI's
    official endpoint. Call logs contain no SDK exception body or credentials.
    """

    def __init__(self, config=None, *, sdk=None, audit_path=None):
        if sdk is None:
            load_configuration()
        self.config = config or Config.from_env()
        self.calls = []
        self.reserved_output_tokens = 0
        self.audit_path = Path(audit_path) if audit_path else None
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            self.audit_path.touch(exist_ok=False)
        if sdk is None:
            key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not key:
                raise LLMError("missing_api_key: set OPENAI_API_KEY locally; never paste it into a trace")
            try:
                from openai import OpenAI
            except ImportError:
                raise LLMError("missing_sdk: install requirements-w7.txt") from None
            sdk = OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                         max_retries=0, timeout=self.config.timeout_seconds)
        self.sdk = sdk

    def close(self):
        close = getattr(self.sdk, "close", None)
        if close:
            close()

    def metadata(self):
        try:
            version = importlib.metadata.version("openai")
        except importlib.metadata.PackageNotFoundError:
            version = None
        return {"provider": "openai", "sdk_version": version,
                "config": asdict(self.config), "sdk_max_retries": 0,
                "api_base": "https://api.openai.com/v1", "store": False}

    def generate_json(self, *, instructions, payload, schema, schema_name="fallback_decision"):
        Draft202012Validator.check_schema(schema)
        body = canonical(payload)
        if len(body) + len(instructions) + len(canonical(schema)) > self.config.max_input_chars:
            raise LLMError("input_budget_exceeded")
        if len(self.calls) >= self.config.max_requests:
            raise LLMError("request_budget_exceeded")
        if self.reserved_output_tokens + self.config.max_output_tokens > self.config.max_reserved_output_tokens:
            raise LLMError("output_reservation_budget_exceeded")
        self.reserved_output_tokens += self.config.max_output_tokens
        event = {"index": len(self.calls), "requested_model": self.config.model,
                 "prompt_sha256": sha256({"instructions": instructions, "payload": payload}),
                 "schema_sha256": sha256(schema), "schema_name": schema_name,
                 "status": "error", "usage": None, "output_text": None,
                 "request_id": None, "response_id": None, "returned_model": None}
        self.calls.append(event)
        started = time.perf_counter()
        try:
            response = self.sdk.responses.create(
                model=self.config.model, instructions=instructions, input=body,
                text={"format": {"type": "json_schema", "name": schema_name,
                                  "schema": schema, "strict": True}},
                max_output_tokens=self.config.max_output_tokens, temperature=0, store=False)
            raw = response.model_dump(mode="json")
            event.update(response_id=raw.get("id"), returned_model=raw.get("model"),
                         request_id=getattr(response, "_request_id", None), usage=raw.get("usage"))
            if any(c.get("type") == "refusal" for o in raw.get("output", []) for c in o.get("content", [])):
                raise LLMError("model_refusal")
            if raw.get("status") != "completed":
                raise LLMError("response_incomplete")
            event["output_text"] = response.output_text
            try:
                value = json.loads(response.output_text)
                Draft202012Validator(schema).validate(value)
            except Exception:
                raise LLMError("invalid_structured_output") from None
            event["status"] = "completed"
            return value
        except LLMError as exc:
            event["error_code"] = str(exc)
            raise
        except Exception as exc:
            # Never copy an HTTP error body or headers, which can include secrets.
            code = type(exc).__name__
            allowed = {"AuthenticationError", "PermissionDeniedError", "RateLimitError", "APITimeoutError",
                       "APIConnectionError", "InternalServerError", "BadRequestError", "NotFoundError"}
            event["error_code"] = code if code in allowed else "provider_error"
            event["request_id"] = getattr(exc, "request_id", None)
            raise LLMError(event["error_code"]) from None
        finally:
            event["seconds"] = round(time.perf_counter() - started, 4)
            if self.audit_path:
                with self.audit_path.open("a", encoding="utf-8") as stream:
                    stream.write(canonical(event) + "\n")


class CallScope:
    """Resolver-facing transport: at most one decision plus one contract repair."""

    def __init__(self, client, max_requests=2):
        self._client = client
        self._remaining = max_requests

    def generate_json(self, **kwargs):
        if self._remaining <= 0:
            raise LLMError("step_request_budget_exceeded")
        self._remaining -= 1
        return self._client.generate_json(**kwargs)
