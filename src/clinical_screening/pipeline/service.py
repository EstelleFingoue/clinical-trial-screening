from __future__ import annotations

import hashlib
from collections.abc import Callable

from clinical_screening.domain import OCRDocument, PipelineReport
from clinical_screening.ingestion import PDFInput
from clinical_screening.ocr import OCREngine
from clinical_screening.pipeline.consolidation import consolidate
from clinical_screening.pipeline.eligibility import screen_all
from clinical_screening.pipeline.extraction import HybridExtractor
from clinical_screening.providers.base import InferenceProvider

ProgressCallback = Callable[[str, float], None]


class PipelineService:
    def __init__(self, ocr: OCREngine, provider: InferenceProvider) -> None:
        self.ocr = ocr
        self.provider = provider

    def run_pdf_items(
        self,
        items: list[PDFInput],
        *,
        patient_id: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> PipelineReport:
        callback = progress or (lambda _message, _fraction: None)
        documents: list[OCRDocument] = []
        for index, item in enumerate(items, start=1):
            prefix = "Chargement de docTR et OCR" if index == 1 else "OCR"
            if index == 1:
                minimum = 25 + max(0, item.page_count - 1) * 5
                maximum = 45 + max(0, item.page_count - 1) * 20
            else:
                minimum = item.page_count * 5
                maximum = item.page_count * 20
            callback(
                (f"{prefix} du document {index}/{len(items)} (environ {minimum} à {maximum} s)"),
                0.05 + 0.35 * index / len(items),
            )
            documents.append(self.ocr.extract(item))
        return self.run_documents(
            documents,
            patient_id=patient_id,
            progress=progress,
        )

    def run_documents(
        self,
        documents: list[OCRDocument],
        *,
        patient_id: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> PipelineReport:
        callback = progress or (lambda _message, _fraction: None)
        resolved_id = patient_id or _patient_id(documents)
        provider_name = self.provider.status().name
        llm_estimate = "3 à 15 s/document" if provider_name == "groq" else "10 à 60 s/document"
        callback(
            f"Extraction regex et LLM avec {provider_name} (environ {llm_estimate})",
            0.55,
        )
        extracted = HybridExtractor(self.provider).extract(documents)
        callback("Consolidation du profil (moins de 3 s)", 0.8)
        profile = consolidate(resolved_id, extracted)
        callback("Application des règles (moins de 1 s)", 0.92)
        decisions = screen_all(profile)
        provider_status = self.provider.status()
        callback("Analyse terminée", 1.0)
        return PipelineReport(
            patient_id=resolved_id,
            provider=provider_status.name,
            provider_mode="live" if provider_status.live else "precomputed",
            documents=documents,
            profile=profile,
            decisions=decisions,
            warnings=["Prototype de recherche: toute décision nécessite une validation humaine."],
        )


def _patient_id(documents: list[OCRDocument]) -> str:
    digest = hashlib.sha256(
        "|".join(sorted(document.source_id for document in documents)).encode()
    ).hexdigest()[:10]
    return f"DEMO-{digest.upper()}"
