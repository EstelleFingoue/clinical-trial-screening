from __future__ import annotations

from clinical_screening.config import Settings
from clinical_screening.providers.openai_compatible import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings) -> None:
        config = settings.inference
        super().__init__(
            name="ollama",
            api_key="ollama",
            base_url=config.ollama.base_url,
            model=config.ollama.model,
            timeout=max(config.timeout_seconds, 120),
            max_retries=config.max_retries,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        )
