from __future__ import annotations

from clinical_screening.config import Settings
from clinical_screening.providers.openai_compatible import (
    OpenAICompatibleProvider,
    ProviderError,
)


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        api_key = settings.groq_api_key
        if not api_key:
            raise ProviderError("GROQ_API_KEY est absente. Configurez la clé ou choisissez Ollama.")
        config = settings.inference
        super().__init__(
            name="groq",
            api_key=api_key,
            base_url=config.groq.base_url,
            model=config.groq.model,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        )
