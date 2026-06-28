from anthropic import Anthropic

from .client import LLMClient


class AnthropicClient(LLMClient):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self._client = Anthropic(api_key=api_key)

    def complete(self, system: str, user: str, response_schema: dict | None = None) -> str:
        messages: list[dict] = [{"role": "user", "content": user}]
        if response_schema is not None:
            messages.append({"role": "assistant", "content": "{"})

        message = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        text = message.content[0].text
        if response_schema is not None:
            text = "{" + text
        return text
