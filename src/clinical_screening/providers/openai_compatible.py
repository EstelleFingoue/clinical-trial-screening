from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from clinical_screening.domain import LLMExtractionResponse, ProviderStatus
from clinical_screening.providers.base import InferenceProvider


class ProviderError(RuntimeError):
    pass


class OpenAICompatibleProvider(InferenceProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        temperature: float,
        max_output_tokens: int,
        configured: bool = True,
    ) -> None:
        self.name = name
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._configured = configured
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    def extract(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
    ) -> LLMExtractionResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "clinical_extraction",
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
        except Exception as exc:
            raise ProviderError(f"Échec du fournisseur {self.name}.") from exc
        if not response.choices or not response.choices[0].message.content:
            raise ProviderError(f"Réponse vide du fournisseur {self.name}.")
        try:
            payload: Any = json.loads(response.choices[0].message.content)
            return LLMExtractionResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError("Réponse LLM non conforme au schéma.") from exc

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            model=self.model,
            configured=self._configured,
            live=True,
        )
