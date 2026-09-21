from __future__ import annotations

import pymupdf
import pytest

from clinical_screening.config import get_settings
from clinical_screening.domain import DocumentType
from clinical_screening.ingestion import PDFInput
from clinical_screening.ocr import DocTROCREngine, EmbeddedTextOCREngine, OCRError


def test_embedded_text_ocr(tmp_path):
    path = tmp_path / "text.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "DOCUMENT SYNTHETIQUE")
    document.save(path)
    document.close()
    item = PDFInput(DocumentType.RCP, path, 1, "test")
    result = EmbeddedTextOCREngine().extract(item)
    assert "DOCUMENT SYNTHETIQUE" in result.text


def test_embedded_text_ocr_rejects_image_only_pdf(tmp_path):
    path = tmp_path / "empty.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()
    item = PDFInput(DocumentType.RCP, path, 1, "test")
    with pytest.raises(OCRError, match="docTR"):
        EmbeddedTextOCREngine().extract(item)


def test_doctr_reports_missing_optional_dependency(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "doctr.models":
            raise ImportError("simulated missing optional dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    engine = DocTROCREngine(get_settings())
    with pytest.raises(OCRError, match="extra `ocr`"):
        engine.warmup()
