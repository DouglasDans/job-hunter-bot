from anthropic import Anthropic

from .client import LLMClient


class AnthropicClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self._client = Anthropic(api_key=api_key)

    def complete(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text
