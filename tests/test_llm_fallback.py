import pytest

from src.llm.client import LLMClient
from src.llm.fallback import FallbackClient


class _SuccessClient(LLMClient):
    def __init__(self, response: str):
        self._response = response

    def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
        return self._response


class _FailingClient(LLMClient):
    def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
        raise RuntimeError("connection refused")


def test_fallback_uses_primary_when_succeeds():
    client = FallbackClient(
        primary=_SuccessClient("from primary"),
        fallback=_SuccessClient("from fallback"),
    )
    assert client.complete("sys", "user") == "from primary"


def test_fallback_uses_fallback_when_primary_fails():
    client = FallbackClient(
        primary=_FailingClient(),
        fallback=_SuccessClient("from fallback"),
    )
    assert client.complete("sys", "user") == "from fallback"


def test_fallback_raises_when_both_fail():
    client = FallbackClient(
        primary=_FailingClient(),
        fallback=_FailingClient(),
    )
    with pytest.raises(RuntimeError):
        client.complete("sys", "user")


def test_fallback_passes_schema_to_primary():
    schema = {"type": "object"}
    received: dict = {}

    class _RecordingClient(LLMClient):
        def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
            received["schema"] = response_schema
            return "ok"

    client = FallbackClient(primary=_RecordingClient(), fallback=_SuccessClient("fallback"))
    client.complete("sys", "user", response_schema=schema)
    assert received["schema"] is schema


def test_fallback_passes_schema_to_fallback_on_primary_failure():
    schema = {"type": "object"}
    received: dict = {}

    class _RecordingFallback(LLMClient):
        def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
            received["schema"] = response_schema
            return "ok"

    client = FallbackClient(primary=_FailingClient(), fallback=_RecordingFallback())
    client.complete("sys", "user", response_schema=schema)
    assert received["schema"] is schema
