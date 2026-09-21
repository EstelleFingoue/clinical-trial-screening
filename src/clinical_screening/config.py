from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Resolve resources both from a checkout and from an installed wheel."""
    checkout_path = PROJECT_ROOT.joinpath(*parts)
    if checkout_path.exists():
        return checkout_path
    return PACKAGE_ROOT.joinpath("resources", *parts)


class AppSection(BaseModel):
    title: str
    host: str = "0.0.0.0"
    port: int = 7860
    public_mode: bool = True
    allow_custom_text: bool = False


class UploadSection(BaseModel):
    allowed_content_types: list[str] = Field(default_factory=lambda: ["application/pdf"])
    max_files: int = 5
    min_document_types: int = 3
    max_pages_per_file: int = 5
    max_bytes_per_file: int = 10 * 1024 * 1024
    temp_root: str | None = None


class OCRSection(BaseModel):
    backend: str = "doctr"
    detection_arch: str = "db_resnet50"
    recognition_arch: str = "crnn_vgg16_bn"
    pretrained: bool = True
    max_concurrency: int = 1


class ProviderSection(BaseModel):
    base_url: str
    model: str


class InferenceSection(BaseModel):
    provider: str = "groq"
    timeout_seconds: float = 45
    max_retries: int = 2
    temperature: float = 0
    max_output_tokens: int = 3000
    cache_builtin_scenarios: bool = True
    cache_uploaded_documents: bool = False
    fallback_builtin_to_precomputed: bool = True
    groq: ProviderSection
    ollama: ProviderSection


class LoggingSection(BaseModel):
    level: str = "INFO"
    log_content: bool = False
    log_filenames: bool = False


class Settings(BaseModel):
    app: AppSection
    uploads: UploadSection
    ocr: OCRSection
    inference: InferenceSection
    logging: LoggingSection

    @property
    def groq_api_key(self) -> str | None:
        return os.getenv("GROQ_API_KEY") or None


def _apply_environment(data: dict) -> dict:
    inference = data.setdefault("inference", {})
    app = data.setdefault("app", {})
    uploads = data.setdefault("uploads", {})
    provider = os.getenv("SCREENING_PROVIDER")
    if provider:
        inference["provider"] = provider
    custom = os.getenv("SCREENING_ALLOW_CUSTOM_TEXT")
    if custom is not None:
        app["allow_custom_text"] = custom.lower() in {"1", "true", "yes"}
    temp_root = os.getenv("SCREENING_TEMP_ROOT")
    if temp_root:
        uploads["temp_root"] = temp_root
    for name, section, key in (
        ("GROQ_MODEL", "groq", "model"),
        ("GROQ_BASE_URL", "groq", "base_url"),
        ("OLLAMA_MODEL", "ollama", "model"),
        ("OLLAMA_BASE_URL", "ollama", "base_url"),
    ):
        value = os.getenv(name)
        if value:
            inference.setdefault(section, {})[key] = value
    return data


@lru_cache(maxsize=1)
def get_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path) if config_path else resource_path("config", "app.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings.model_validate(_apply_environment(data))


@lru_cache(maxsize=1)
def get_variable_config() -> dict:
    path = resource_path("config", "variables.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))
