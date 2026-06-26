import os

from .client import LLMClient


def create_llm_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", "ollama")
    model = os.getenv("LLM_MODEL", "qwen2.5:7b")
    if provider == "ollama":
        from .ollama import OllamaClient

        return OllamaClient(
            model=model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    if provider == "anthropic":
        from .anthropic import AnthropicClient

        return AnthropicClient(model=model, api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
