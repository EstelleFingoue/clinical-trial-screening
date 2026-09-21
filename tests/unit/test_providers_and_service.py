from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from clinical_screening.config import get_settings
from clinical_screening.domain import (
    DocumentType,
    LLMExtractionResponse,
    OCRDocument,
    ProviderStatus,
)
from clinical_screening.pipeline import HybridExtractor, PipelineService
from clinical_screening.providers import ProviderError, build_provider
from clinical_screening.providers.base import InferenceProvider
from clinical_screening.providers.openai_compatible import OpenAICompatibleProvider
from clinical_screening.providers.precomputed import PrecomputedProvider, response_key


class StubProvider(InferenceProvider):
    name = "stub"
    model = "stub-v1"

    def __init__(self, variables: dict | None = None) -> None:
        self.variables = variables or {}

    def extract(self, *, system_prompt: str, user_prompt: str, schema: dict):
        assert "document médical entièrement fictif" in system_prompt
        assert "DOCUMENT FICTIF" in user_prompt
        assert schema["additionalProperties"] is False
        return LLMExtractionResponse.model_validate({"variables": self.variables})

    def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, model=self.model, configured=True, live=False)


def _document(text: str = "ECOG 1.") -> OCRDocument:
    return OCRDocument(
        document_type=DocumentType.RCP,
        text=text,
        page_count=1,
        source_id="stub",
    )


def test_hybrid_extractor_accepts_exact_citation_and_rejects_invented_one():
    provider = StubProvider(
        {
            "ecog": {"value": 1, "citation": "ECOG 1."},
            "stade_t": {"value": "T3", "citation": "citation inventée"},
        }
    )
    results = HybridExtractor(provider).extract([_document()])
    by_name = {result.name: result for result in results}
    assert by_name["ecog"].value == 1
    assert by_name["ecog"].confidence == "llm_verified"
    assert by_name["stade_t"].value is None
    assert by_name["stade_t"].confidence == "llm_rejected_citation"


def test_pipeline_service_returns_explainable_report():
    service = PipelineService(ocr=None, provider=StubProvider())  # type: ignore[arg-type]
    report = service.run_documents([_document()], patient_id="TEST")
    assert report.patient_id == "TEST"
    assert report.provider_mode == "precomputed"
    assert report.warnings
    assert set(report.decisions) == {"peace7", "obsapa"}


def test_provider_factory_branches(monkeypatch):
    settings = get_settings()
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    get_settings.cache_clear()
    try:
        assert build_provider("groq").name == "groq"
        assert build_provider("ollama", settings).name == "ollama"
        assert build_provider("precomputed", settings).name == "precomputed"
        with pytest.raises(ProviderError, match="inconnu"):
            build_provider("unknown", settings)
    finally:
        get_settings.cache_clear()


def test_groq_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ProviderError, match="GROQ_API_KEY"):
            build_provider("groq")
    finally:
        get_settings.cache_clear()


def test_precomputed_provider_success_and_failures(tmp_path: Path):
    text = "Statut métastatique M0."
    registry = tmp_path / "registry.json"
    registry.write_text(
        '{"' + response_key(text) + '":{"variables":{"statut_metastatique":'
        '{"value":"M0","citation":"Statut métastatique M0."}}}}',
        encoding="utf-8",
    )
    provider = PrecomputedProvider(registry)
    result = provider.extract(
        system_prompt="ignored",
        user_prompt=f'DOCUMENT FICTIF:\n"""\n{text}\n"""',
        schema={},
    )
    assert result.variables["statut_metastatique"].value == "M0"
    assert provider.status().configured is True
    with pytest.raises(ProviderError, match="absent"):
        provider.extract(system_prompt="", user_prompt="sans document", schema={})
    with pytest.raises(ProviderError, match="Aucun résultat"):
        provider.extract(
            system_prompt="",
            user_prompt='DOCUMENT FICTIF:\n"""\nautre\n"""',
            schema={},
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "Réponse vide"),
        ("not json", "non conforme"),
        ('{"variables": {"x": {"value": [], "citation": ""}}}', "non conforme"),
    ],
)
def test_openai_compatible_provider_validates_responses(payload, message):
    provider = OpenAICompatibleProvider(
        name="test",
        api_key="test",
        base_url="http://localhost:1/v1",
        model="test",
        timeout=1,
        max_retries=0,
        temperature=0,
        max_output_tokens=100,
    )
    choices = [] if payload is None else [SimpleNamespace(message=SimpleNamespace(content=payload))]
    provider.client = cast(
        Any,
        SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **_kwargs: SimpleNamespace(choices=choices)
                )
            )
        ),
    )
    with pytest.raises(ProviderError, match=message):
        provider.extract(system_prompt="system", user_prompt="user", schema={})


def test_openai_compatible_provider_wraps_transport_errors():
    provider = OpenAICompatibleProvider(
        name="test",
        api_key="test",
        base_url="http://localhost:1/v1",
        model="test",
        timeout=1,
        max_retries=0,
        temperature=0,
        max_output_tokens=100,
    )

    def fail(**_kwargs):
        raise RuntimeError("network")

    provider.client = cast(
        Any,
        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail))),
    )
    with pytest.raises(ProviderError, match="Échec"):
        provider.extract(system_prompt="system", user_prompt="user", schema={})
