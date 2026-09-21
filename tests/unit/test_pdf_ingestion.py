from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from clinical_screening.config import get_settings
from clinical_screening.domain import DocumentType
from clinical_screening.ingestion import PDFSession, PDFValidationError


def _pdf_bytes(*, pages: int = 1, encrypted: bool = False) -> bytes:
    document = pymupdf.open()
    for _ in range(pages):
        document.new_page()
    if encrypted:
        return document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,  # pyright: ignore[reportAttributeAccessIssue]
            owner_pw="owner",
            user_pw="secret",
        )
    return document.tobytes()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "vide"),
        (b"not a pdf", "signature"),
        (_pdf_bytes(pages=6), "dépasse 5 pages"),
        (_pdf_bytes(encrypted=True), "chiffrés"),
    ],
)
def test_invalid_pdf_is_rejected(content: bytes, message: str):
    with (
        PDFSession(get_settings()) as session,
        pytest.raises(PDFValidationError, match=message),
    ):
        session.add(DocumentType.ANAPATH, content)


def test_document_mix_requires_three_types():
    content = _pdf_bytes()
    with PDFSession(get_settings()) as session:
        session.add(DocumentType.ANAPATH, content)
        session.add(DocumentType.BILAN, content)
        with pytest.raises(PDFValidationError, match="Au moins 3"):
            session.validate_document_mix()


def test_temporary_directory_is_removed_after_success():
    content = _pdf_bytes()
    with PDFSession(get_settings()) as session:
        root = session.root
        session.add(DocumentType.ANAPATH, content)
        assert root.exists()
    assert not root.exists()


def test_temporary_directory_is_removed_after_error():
    root: Path | None = None
    with pytest.raises(RuntimeError), PDFSession(get_settings()) as session:
        root = session.root
        raise RuntimeError("boom")
    assert root is not None
    assert not root.exists()
