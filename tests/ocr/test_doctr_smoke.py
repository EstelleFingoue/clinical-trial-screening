from __future__ import annotations

import pytest

from clinical_screening.config import PROJECT_ROOT, get_settings
from clinical_screening.domain import DocumentType
from clinical_screening.ingestion import PDFInput
from clinical_screening.ocr import DocTROCREngine


@pytest.mark.ocr
def test_doctr_reads_one_synthetic_image_pdf():
    pytest.importorskip("doctr")
    path = PROJECT_ROOT / "demo_data/patients/peace7-01/pdf/anapath.pdf"
    result = DocTROCREngine(get_settings()).extract(
        PDFInput(DocumentType.ANAPATH, path, 1, "ocr-smoke")
    )
    assert len(result.text) >= 40
    assert result.page_count == 1
