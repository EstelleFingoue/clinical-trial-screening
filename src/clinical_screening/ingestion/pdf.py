from __future__ import annotations

import hashlib
import tempfile
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from clinical_screening.config import Settings
from clinical_screening.domain import DocumentType


class PDFValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PDFInput:
    document_type: DocumentType
    path: Path
    page_count: int
    source_id: str


class PDFSession(AbstractContextManager["PDFSession"]):
    """Stockage éphémère d'une requête, supprimé à la sortie du contexte."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._temp = tempfile.TemporaryDirectory(
            prefix="screening-",
            dir=settings.uploads.temp_root,
        )
        self.root = Path(self._temp.name)
        self.documents: list[PDFInput] = []

    def add(self, document_type: DocumentType, content: bytes) -> PDFInput:
        limits = self.settings.uploads
        if len(self.documents) >= limits.max_files:
            raise PDFValidationError(f"Maximum {limits.max_files} PDF par analyse.")
        if not content:
            raise PDFValidationError("Le PDF est vide.")
        if len(content) > limits.max_bytes_per_file:
            raise PDFValidationError("Le PDF dépasse la taille maximale de 10 Mo.")
        if not content.startswith(b"%PDF-"):
            raise PDFValidationError("Le fichier n'a pas une signature PDF valide.")

        try:
            pdf = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise PDFValidationError("Le PDF est illisible.") from exc
        try:
            if pdf.needs_pass:
                raise PDFValidationError("Les PDF chiffrés ne sont pas acceptés.")
            page_count = pdf.page_count
            if page_count < 1:
                raise PDFValidationError("Le PDF ne contient aucune page.")
            if page_count > limits.max_pages_per_file:
                raise PDFValidationError(f"Le PDF dépasse {limits.max_pages_per_file} pages.")
        finally:
            pdf.close()

        digest = hashlib.sha256(content).hexdigest()[:16]
        path = self.root / f"{len(self.documents):02d}-{document_type.value}.pdf"
        path.write_bytes(content)
        item = PDFInput(document_type, path, page_count, f"sha256:{digest}")
        self.documents.append(item)
        return item

    def validate_document_mix(self) -> None:
        unique_types = {item.document_type for item in self.documents}
        minimum = self.settings.uploads.min_document_types
        if len(unique_types) < minimum:
            raise PDFValidationError(
                f"Au moins {minimum} types de documents distincts sont requis."
            )

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._temp.cleanup()
