from .client import LLMClient


class FallbackClient(LLMClient):
    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback

    def complete(self, system: str, user: str) -> str:
        try:
            return self._primary.complete(system, user)
        except Exception as e:
            print(f"[WARN] Primary LLM failed ({e}), trying fallback.")
            return self._fallback.complete(system, user)
