from __future__ import annotations

import asyncio
from typing import Annotated

import gradio as gr
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from clinical_screening.application import build_ocr_engine, run_scenario, run_upload
from clinical_screening.config import get_settings, resource_path
from clinical_screening.domain import (
    DocumentType,
    OCRDocument,
    PatientProfile,
    PipelineReport,
    ProviderStatus,
    ScenarioSummary,
)
from clinical_screening.ingestion import PDFSession, PDFValidationError
from clinical_screening.ocr import OCRError
from clinical_screening.pipeline import HybridExtractor, consolidate, screen_all
from clinical_screening.providers import ProviderError, build_provider
from clinical_screening.synthetic import list_scenarios
from clinical_screening.ui.gradio_app import build_ui


class ScenarioRequest(BaseModel):
    scenario_id: str
    provider: str | None = None


class ExtractRequest(BaseModel):
    patient_id: str = "DEMO-API"
    provider: str | None = None
    documents: list[OCRDocument] = Field(min_length=1, max_length=5)


class ScreenRequest(BaseModel):
    profile: PatientProfile


app = FastAPI(
    title="Clinical Trial Screening Demo API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)


@app.get("/api", include_in_schema=False)
def api_root() -> RedirectResponse:
    return RedirectResponse("/api/docs")


@app.get("/api/v1/health")
def health() -> dict:
    settings = get_settings()
    scenario_count = len(list_scenarios())
    return {
        "status": "ok" if scenario_count == 8 else "degraded",
        "version": app.version,
        "provider": settings.inference.provider,
        "synthetic_only": True,
        "scenario_count": scenario_count,
    }


@app.get("/api/v1/providers", response_model=list[ProviderStatus])
def providers() -> list[ProviderStatus]:
    settings = get_settings()
    return [
        ProviderStatus(
            name="groq",
            model=settings.inference.groq.model,
            configured=bool(settings.groq_api_key),
            live=True,
        ),
        ProviderStatus(
            name="ollama",
            model=settings.inference.ollama.model,
            configured=bool(settings.inference.ollama.base_url),
            live=True,
        ),
        ProviderStatus(
            name="precomputed",
            model="curated-synthetic-results-v1",
            configured=resource_path("demo_data", "precomputed_llm.json").exists(),
            live=False,
        ),
    ]


@app.get("/api/v1/scenarios", response_model=list[ScenarioSummary])
def scenarios() -> list[ScenarioSummary]:
    return list_scenarios()


@app.post("/api/v1/pipeline/scenario", response_model=PipelineReport)
async def pipeline_scenario(request: ScenarioRequest) -> PipelineReport:
    try:
        return await asyncio.to_thread(
            run_scenario,
            request.scenario_id,
            provider_name=request.provider,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ProviderError, PDFValidationError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/extract", response_model=PatientProfile)
async def extract(request: ExtractRequest) -> PatientProfile:
    if get_settings().app.public_mode and not get_settings().app.allow_custom_text:
        raise HTTPException(
            status_code=403,
            detail="L'extraction de texte libre est désactivée en mode public.",
        )
    try:
        provider = build_provider(request.provider)
        candidates = await asyncio.to_thread(
            HybridExtractor(provider).extract,
            request.documents,
        )
        return consolidate(request.patient_id, candidates)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/screen")
def screen(request: ScreenRequest) -> dict:
    return screen_all(request.profile)


Upload = Annotated[UploadFile | None, File()]


@app.post("/api/v1/ocr", response_model=list[OCRDocument])
async def ocr_endpoint(
    attestation: Annotated[bool, Form()],
    anapath: Upload = None,
    bilan: Upload = None,
    rcp: Upload = None,
    consultation: Upload = None,
    courrier: Upload = None,
) -> list[OCRDocument]:
    files = _uploads(anapath, bilan, rcp, consultation, courrier)
    if not attestation:
        raise HTTPException(status_code=400, detail="L'attestation est obligatoire.")
    try:
        settings = get_settings()
        engine = build_ocr_engine()
        with PDFSession(settings) as session:
            for document_type, upload in files.items():
                session.add(document_type, await _bounded_read(upload))
            session.validate_document_mix()
            return [await asyncio.to_thread(engine.extract, item) for item in session.documents]
    except PDFValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await _close_uploads(files.values())


@app.post("/api/v1/pipeline/upload", response_model=PipelineReport)
async def pipeline_upload(
    attestation: Annotated[bool, Form()],
    provider: Annotated[str | None, Form()] = None,
    anapath: Upload = None,
    bilan: Upload = None,
    rcp: Upload = None,
    consultation: Upload = None,
    courrier: Upload = None,
) -> PipelineReport:
    if not attestation:
        raise HTTPException(status_code=400, detail="L'attestation est obligatoire.")
    uploads = _uploads(anapath, bilan, rcp, consultation, courrier)
    try:
        contents = {
            document_type: await _bounded_read(upload) for document_type, upload in uploads.items()
        }
        return await asyncio.to_thread(
            run_upload,
            contents,
            provider_name=provider,
        )
    except PDFValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OCRError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await _close_uploads(uploads.values())


def _uploads(*files: UploadFile | None) -> dict[DocumentType, UploadFile]:
    return {
        document_type: upload
        for document_type, upload in zip(DocumentType, files, strict=True)
        if upload is not None
    }


async def _bounded_read(upload: UploadFile) -> bytes:
    maximum = get_settings().uploads.max_bytes_per_file
    content = await upload.read(maximum + 1)
    if len(content) > maximum:
        raise PDFValidationError("Le PDF dépasse la taille maximale de 10 Mo.")
    return content


async def _close_uploads(uploads) -> None:
    for upload in uploads:
        await upload.close()


app = gr.mount_gradio_app(app, build_ui(), path="/")


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "clinical_screening.api.app:app",
        host=settings.app.host,
        port=settings.app.port,
        workers=1,
    )


if __name__ == "__main__":
    main()
