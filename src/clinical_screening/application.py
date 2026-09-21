from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

from clinical_screening.config import get_settings
from clinical_screening.domain import DocumentType, PipelineReport
from clinical_screening.ingestion import PDFSession
from clinical_screening.ocr import DocTROCREngine, EmbeddedTextOCREngine, OCRError
from clinical_screening.pipeline import PipelineService
from clinical_screening.providers import ProviderError, build_provider
from clinical_screening.synthetic import (
    load_precomputed_report,
    scenario_pdf_paths,
)

ProgressCallback = Callable[[str, float], None]


@lru_cache(maxsize=1)
def build_ocr_engine():
    settings = get_settings()
    if settings.ocr.backend == "embedded":
        return EmbeddedTextOCREngine()
    return DocTROCREngine(settings)


def run_scenario(
    scenario_id: str,
    *,
    provider_name: str | None = None,
    progress: ProgressCallback | None = None,
) -> PipelineReport:
    settings = get_settings()
    selected_provider = (provider_name or settings.inference.provider).casefold()
    if selected_provider == "precomputed":
        return load_precomputed_report(scenario_id)
    try:
        provider = build_provider(selected_provider, settings)
        service = PipelineService(build_ocr_engine(), provider)
        with PDFSession(settings) as session:
            for raw_type, path in scenario_pdf_paths(scenario_id):
                session.add(DocumentType(raw_type), path.read_bytes())
            session.validate_document_mix()
            return service.run_pdf_items(
                session.documents,
                patient_id=scenario_id,
                progress=progress,
            )
    except (OCRError, ProviderError) as exc:
        if settings.inference.fallback_builtin_to_precomputed:
            return load_precomputed_report(
                scenario_id,
                fallback_reason=type(exc).__name__,
            )
        raise


def run_upload(
    files: dict[DocumentType, bytes],
    *,
    provider_name: str | None = None,
    progress: ProgressCallback | None = None,
) -> PipelineReport:
    settings = get_settings()
    selected_provider = (provider_name or settings.inference.provider).casefold()
    if selected_provider == "precomputed":
        raise ProviderError("Le mode precomputed est réservé aux scénarios synthétiques intégrés.")
    provider = build_provider(selected_provider, settings)
    service = PipelineService(build_ocr_engine(), provider)
    with PDFSession(settings) as session:
        for document_type, content in files.items():
            if content:
                session.add(document_type, content)
        session.validate_document_mix()
        return service.run_pdf_items(session.documents, progress=progress)
