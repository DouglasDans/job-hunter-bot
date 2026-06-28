import pytest

from src.llm.client import LLMClient
from src.llm.fallback import FallbackClient


class _SuccessClient(LLMClient):
    def __init__(self, response: str):
        self._response = response

    def complete(self, system: str, user: str) -> str:
        return self._response


class _FailingClient(LLMClient):
    def complete(self, system: str, user: str) -> str:
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
