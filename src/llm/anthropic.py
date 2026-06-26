from .client import LLMClient


class AnthropicClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
        raise NotImplementedError(
            "AnthropicClient not yet implemented. "
            "Install 'anthropic' and implement this client, or use LLM_PROVIDER=ollama."
        )
