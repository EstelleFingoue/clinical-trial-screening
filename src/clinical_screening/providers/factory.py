from __future__ import annotations

from clinical_screening.config import Settings, get_settings, resource_path
from clinical_screening.providers.base import InferenceProvider
from clinical_screening.providers.groq import GroqProvider
from clinical_screening.providers.ollama import OllamaProvider
from clinical_screening.providers.openai_compatible import ProviderError
from clinical_screening.providers.precomputed import PrecomputedProvider


def build_provider(
    name: str | None = None,
    settings: Settings | None = None,
) -> InferenceProvider:
    config = settings or get_settings()
    selected = (name or config.inference.provider).casefold()
    if selected == "groq":
        return GroqProvider(config)
    if selected == "ollama":
        return OllamaProvider(config)
    if selected == "precomputed":
        return PrecomputedProvider(resource_path("demo_data", "precomputed_llm.json"))
    raise ProviderError(f"Provider inconnu: {selected}. Choix: groq, ollama, precomputed.")
