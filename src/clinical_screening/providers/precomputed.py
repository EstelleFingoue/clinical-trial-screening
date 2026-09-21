from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from clinical_screening.domain import LLMExtractionResponse, ProviderStatus
from clinical_screening.providers.base import InferenceProvider
from clinical_screening.providers.openai_compatible import ProviderError


class PrecomputedProvider(InferenceProvider):
    """Réponses versionnées pour les seuls scénarios synthétiques intégrés."""

    name = "precomputed"
    model = "curated-synthetic-results-v1"

    def __init__(self, registry_path: Path) -> None:
        self.registry_path = registry_path
        self.responses = (
            json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
        )

    def extract(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
    ) -> LLMExtractionResponse:
        del system_prompt, schema
        match = re.search(r'DOCUMENT FICTIF:\s*"""\s*(.*?)\s*"""', user_prompt, re.DOTALL)
        if not match:
            raise ProviderError("Document synthétique absent du prompt.")
        key = hashlib.sha256(_normalized(match.group(1)).encode()).hexdigest()
        payload = self.responses.get(key)
        if payload is None:
            raise ProviderError(
                "Aucun résultat pré-calculé pour ce document. Le fallback est réservé "
                "aux scénarios intégrés."
            )
        return LLMExtractionResponse.model_validate(payload)

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            model=self.model,
            configured=bool(self.responses),
            live=False,
        )


def response_key(text: str) -> str:
    return hashlib.sha256(_normalized(text).encode()).hexdigest()


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
