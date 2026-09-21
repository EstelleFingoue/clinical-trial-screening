from __future__ import annotations

from abc import ABC, abstractmethod

from clinical_screening.domain import LLMExtractionResponse, ProviderStatus


class InferenceProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def extract(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
    ) -> LLMExtractionResponse:
        """Retourne une extraction conforme au schéma demandé."""

    @abstractmethod
    def status(self) -> ProviderStatus:
        """Décrit la disponibilité du fournisseur sans exposer de secret."""
