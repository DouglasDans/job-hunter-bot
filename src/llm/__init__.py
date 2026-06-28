import os

from .client import LLMClient


def create_llm_client() -> LLMClient:
    from .ollama import OllamaClient

    ollama = OllamaClient(
        model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        from .anthropic import AnthropicClient
        from .fallback import FallbackClient

        anthropic = AnthropicClient(
            model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            api_key=anthropic_key,
        )
        return FallbackClient(primary=anthropic, fallback=ollama)

    return ollama
