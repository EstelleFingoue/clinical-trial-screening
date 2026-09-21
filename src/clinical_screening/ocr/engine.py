from __future__ import annotations

import threading
from abc import ABC, abstractmethod

from clinical_screening.config import Settings
from clinical_screening.domain import OCRDocument
from clinical_screening.ingestion import PDFInput


class OCRError(RuntimeError):
    pass


class OCREngine(ABC):
    @abstractmethod
    def extract(self, item: PDFInput) -> OCRDocument:
        """Extrait le texte d'un PDF validé."""


class DocTROCREngine(OCREngine):
    """Moteur docTR chargé paresseusement et partagé par le processus."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._predictor = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.BoundedSemaphore(value=settings.ocr.max_concurrency)

    def warmup(self) -> None:
        self._get_predictor()

    def _get_predictor(self):
        if self._predictor is not None:
            return self._predictor
        with self._load_lock:
            if self._predictor is not None:
                return self._predictor
            try:
                from doctr.models import ocr_predictor  # pyright: ignore[reportMissingImports]
            except ImportError as exc:
                raise OCRError("docTR n'est pas installé. Installez l'extra `ocr`.") from exc
            self._predictor = ocr_predictor(
                det_arch=self.settings.ocr.detection_arch,
                reco_arch=self.settings.ocr.recognition_arch,
                pretrained=self.settings.ocr.pretrained,
                assume_straight_pages=True,
            )
            return self._predictor

    def extract(self, item: PDFInput) -> OCRDocument:
        try:
            from doctr.io import DocumentFile  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise OCRError("docTR n'est pas installé.") from exc

        predictor = self._get_predictor()
        try:
            pages = DocumentFile.from_pdf(str(item.path))
            with self._inference_lock:
                result = predictor(pages)
            rendered = result.render()
            if isinstance(rendered, str):
                text = rendered.strip()
            else:
                text = "\n\n".join(str(page).strip() for page in rendered if str(page).strip())
        except Exception as exc:
            raise OCRError("Échec de l'OCR sur un PDF validé.") from exc
        if not text.strip():
            raise OCRError("L'OCR n'a produit aucun texte.")
        return OCRDocument(
            document_type=item.document_type,
            text=text,
            page_count=item.page_count,
            source_id=item.source_id,
        )


class EmbeddedTextOCREngine(OCREngine):
    """Backend léger de développement; la production utilise docTR."""

    def extract(self, item: PDFInput) -> OCRDocument:
        import pymupdf

        pdf = pymupdf.open(item.path)
        try:
            text = "\n\n".join(str(page.get_text("text")) for page in pdf)
        finally:
            pdf.close()
        if not text.strip():
            raise OCRError("Ce PDF image nécessite docTR.")
        return OCRDocument(
            document_type=item.document_type,
            text=text,
            page_count=item.page_count,
            source_id=item.source_id,
        )
