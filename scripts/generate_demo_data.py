"""Generate the deterministic, synthetic-only portfolio dataset."""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from clinical_screening.config import PROJECT_ROOT, get_variable_config
from clinical_screening.domain import (
    DocumentType,
    OCRDocument,
    PipelineReport,
)
from clinical_screening.pipeline import HybridExtractor, consolidate, screen_all
from clinical_screening.providers.precomputed import PrecomputedProvider, response_key

ROOT = PROJECT_ROOT / "demo_data"
PATIENTS = ROOT / "patients"
SEED = 20260920


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    category: str
    description: str
    values: dict[str, Any]
    expected: dict[str, str]


def _base_values() -> dict[str, Any]:
    return {
        "adenocarcinome": True,
        "gleason": "8 (4+4)",
        "grade_isup": 4,
        "nombre_carottes": 12,
        "volume_prostatique": 55,
        "psa_diagnostic": 28,
        "hemoglobine": 14.2,
        "creatinine": 82,
        "stade_t": "T3a",
        "statut_metastatique": "M0",
        "atteinte_ganglionnaire": "N0",
        "ecog": 0,
        "toucher_rectal": "suspect",
        "traitement_hormonal_anterieur": False,
        "chimiotherapie_anterieure": False,
        "prostatectomie_anterieure": False,
        "radiotherapie_anterieure": False,
        "diabete": False,
        "comorbidite_cardiaque": False,
        "comorbidite_infectieuse": False,
        "fonction_pulmonaire": False,
        "autre_cancer_recent": False,
    }


def _scenario(
    scenario_id: str,
    title: str,
    category: str,
    description: str,
    expected: dict[str, str],
    **updates: Any,
) -> Scenario:
    values = _base_values()
    values.update(updates)
    return Scenario(scenario_id, title, category, description, values, expected)


SCENARIOS = [
    _scenario(
        "peace7-01",
        "Profil Synthétique Alpha",
        "eligible_peace7",
        "M0, faible volume et trois facteurs de haut risque.",
        {"peace7": "eligible", "obsapa": "non_eligible"},
    ),
    _scenario(
        "peace7-02",
        "Profil Synthétique Bêta",
        "eligible_peace7",
        "M0, ECOG 1 et deux facteurs de haut risque.",
        {"peace7": "eligible", "obsapa": "non_eligible"},
        gleason="7 (4+3)",
        ecog=1,
        psa_diagnostic=31,
        volume_prostatique=72,
    ),
    _scenario(
        "obsapa-01",
        "Profil Synthétique Gamma",
        "eligible_obsapa",
        "Maladie M1 avec PSA disponible et sans chimiothérapie antérieure.",
        {"peace7": "non_eligible", "obsapa": "eligible"},
        statut_metastatique="M1b",
        atteinte_ganglionnaire="N1",
    ),
    _scenario(
        "obsapa-02",
        "Profil Synthétique Delta",
        "eligible_obsapa",
        "Maladie M1, PSA disponible et ECOG 1.",
        {"peace7": "non_eligible", "obsapa": "eligible"},
        statut_metastatique="M1a",
        ecog=1,
        psa_diagnostic=12,
    ),
    _scenario(
        "indeterminate-01",
        "Profil Synthétique Epsilon",
        "indeterminable",
        "Statut métastatique Mx non résolu.",
        {"peace7": "indeterminable", "obsapa": "indeterminable"},
        statut_metastatique="Mx",
    ),
    _scenario(
        "indeterminate-02",
        "Profil Synthétique Zêta",
        "indeterminable",
        "Statut métastatique non mentionné.",
        {"peace7": "indeterminable", "obsapa": "indeterminable"},
        statut_metastatique="Non_mentionne",
    ),
    _scenario(
        "noneligible-01",
        "Profil Synthétique Êta",
        "non_eligible",
        "M0 avec chimiothérapie antérieure documentée.",
        {"peace7": "non_eligible", "obsapa": "non_eligible"},
        chimiotherapie_anterieure=True,
    ),
    _scenario(
        "noneligible-02",
        "Profil Synthétique Thêta",
        "non_eligible",
        "M0 avec ECOG 2, incompatible avec PEACE-7.",
        {"peace7": "non_eligible", "obsapa": "non_eligible"},
        ecog=2,
    ),
]


def _clinical_documents(
    scenario: Scenario,
) -> tuple[dict[DocumentType, str], dict[str, tuple[Any, str, DocumentType]]]:
    value = scenario.values
    evidence: dict[str, tuple[Any, str, DocumentType]] = {}

    def line(name: str, text: str, document_type: DocumentType) -> str:
        evidence[name] = (value[name], text, document_type)
        return text

    anapath = [
        "DOCUMENT ENTIÈREMENT SYNTHÉTIQUE — AUCUNE DONNÉE RÉELLE",
        f"Identifiant fictif : {scenario.id.upper()}",
        line(
            "adenocarcinome",
            "Adénocarcinome prostatique identifié.",
            DocumentType.ANAPATH,
        ),
        line("gleason", f"Score de Gleason : {value['gleason']}.", DocumentType.ANAPATH),
        line("grade_isup", f"Grade ISUP : {value['grade_isup']}.", DocumentType.ANAPATH),
        line(
            "nombre_carottes",
            f"{value['nombre_carottes']} carottes analysées.",
            DocumentType.ANAPATH,
        ),
    ]
    bilan = [
        "DOCUMENT ENTIÈREMENT SYNTHÉTIQUE — BILAN",
        line(
            "hemoglobine",
            f"Hémoglobine : {value['hemoglobine']} g/dL.",
            DocumentType.BILAN,
        ),
        line(
            "creatinine",
            f"Créatininémie : {value['creatinine']} µmol/L.",
            DocumentType.BILAN,
        ),
    ]
    rcp = [
        "DOCUMENT ENTIÈREMENT SYNTHÉTIQUE — RCP",
        line(
            "volume_prostatique",
            f"Volume prostatique : {value['volume_prostatique']} cc.",
            DocumentType.RCP,
        ),
        line(
            "psa_diagnostic",
            f"PSA diagnostique : {value['psa_diagnostic']} ng/mL.",
            DocumentType.RCP,
        ),
        line("stade_t", f"Stade clinique {value['stade_t']}.", DocumentType.RCP),
    ]
    if value["statut_metastatique"] != "Non_mentionne":
        rcp.append(
            line(
                "statut_metastatique",
                f"Statut métastatique {value['statut_metastatique']}.",
                DocumentType.RCP,
            )
        )
    rcp.extend(
        [
            line(
                "atteinte_ganglionnaire",
                f"Atteinte ganglionnaire {value['atteinte_ganglionnaire']}.",
                DocumentType.RCP,
            ),
            line("ecog", f"ECOG {value['ecog']}.", DocumentType.RCP),
        ]
    )

    labels = {
        "toucher_rectal": "Toucher rectal",
        "traitement_hormonal_anterieur": "Traitement hormonal antérieur",
        "chimiotherapie_anterieure": "Chimiothérapie antérieure",
        "prostatectomie_anterieure": "Prostatectomie antérieure",
        "radiotherapie_anterieure": "Radiothérapie antérieure",
        "diabete": "Diabète",
        "comorbidite_cardiaque": "Comorbidité cardiaque majeure",
        "comorbidite_infectieuse": "Comorbidité infectieuse majeure",
        "fonction_pulmonaire": "Insuffisance pulmonaire majeure",
        "autre_cancer_recent": "Autre cancer récent",
    }
    consultation = ["DOCUMENT ENTIÈREMENT SYNTHÉTIQUE — CONSULTATION"]
    for name, label in labels.items():
        raw = value[name]
        rendered = "oui" if raw is True else "non" if raw is False else str(raw)
        consultation.append(line(name, f"{label} : {rendered}.", DocumentType.CONSULTATION))

    documents = {
        DocumentType.ANAPATH: "\n".join(anapath),
        DocumentType.BILAN: "\n".join(bilan),
        DocumentType.RCP: "\n".join(rcp),
        DocumentType.CONSULTATION: "\n".join(consultation),
    }
    return documents, evidence


def _provider_payload(
    document_type: DocumentType,
    evidence: dict[str, tuple[Any, str, DocumentType]],
) -> dict[str, Any]:
    variables = {}
    for name in get_variable_config()["variables"]:
        item = evidence.get(name)
        if item and item[2] == document_type:
            variables[name] = {"value": item[0], "citation": item[1]}
        else:
            variables[name] = {"value": "Non_mentionne", "citation": ""}
    return {"variables": variables}


def _render_image_pdf(text: str, target: Path, seed: int) -> None:
    rng = random.Random(seed)
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=22)
    y = 90
    for paragraph in text.splitlines():
        for wrapped in textwrap.wrap(paragraph, width=78) or [""]:
            draw.text((90, y), wrapped, fill=(20, 20, 20), font=font)
            y += 36
        y += 12
    for _ in range(45):
        x = rng.randrange(image.width)
        y_noise = rng.randrange(image.height)
        shade = rng.randrange(215, 246)
        draw.point((x, y_noise), fill=(shade, shade, shade))
    pixmap = pymupdf.Pixmap(Image_to_png(image))
    pdf = pymupdf.open()
    try:
        page = pdf.new_page(width=595, height=842)
        page.insert_image(page.rect, pixmap=pixmap)
        pdf.save(target, garbage=4, deflate=True)
    finally:
        pdf.close()


def _validate_pdf(path: Path) -> tuple[int, int]:
    size = path.stat().st_size
    if size > 10 * 1024 * 1024:
        raise RuntimeError(f"PDF synthétique trop volumineux: {path}")
    with pymupdf.open(path) as document:
        if not 1 <= document.page_count <= 5:
            raise RuntimeError(f"Nombre de pages invalide: {path}")
        if any(page.get_text().strip() for page in document):
            raise RuntimeError(f"Le PDF n'est pas image-only: {path}")
        return size, document.page_count


def Image_to_png(image: Image.Image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate() -> None:
    if PATIENTS.exists():
        shutil.rmtree(PATIENTS)
    PATIENTS.mkdir(parents=True)
    registry: dict[str, Any] = {}
    catalog = []
    manifest_files = []
    scenario_inputs: list[tuple[Scenario, dict[DocumentType, str]]] = []

    for scenario_index, scenario in enumerate(SCENARIOS):
        documents, evidence = _clinical_documents(scenario)
        scenario_inputs.append((scenario, documents))
        pdf_root = PATIENTS / scenario.id / "pdf"
        pdf_root.mkdir(parents=True)
        pdf_files = {}
        for document_index, (document_type, text) in enumerate(documents.items()):
            filename = f"{document_type.value}.pdf"
            target = pdf_root / filename
            _render_image_pdf(
                text,
                target,
                SEED + scenario_index * 10 + document_index,
            )
            registry[response_key(text)] = _provider_payload(document_type, evidence)
            pdf_files[document_type.value] = filename
            content = target.read_bytes()
            size, page_count = _validate_pdf(target)
            manifest_files.append(
                {
                    "path": str(target.relative_to(ROOT)),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": size,
                    "pages": page_count,
                    "image_only": True,
                }
            )
        catalog.append(
            {
                "id": scenario.id,
                "title": scenario.title,
                "category": scenario.category,
                "description": scenario.description,
                "document_types": [item.value for item in documents],
                "expected": scenario.expected,
                "pdf_files": pdf_files,
            }
        )
        _write_json(PATIENTS / scenario.id / "truth.json", scenario.values)

    _write_json(ROOT / "precomputed_llm.json", registry)
    provider = PrecomputedProvider(ROOT / "precomputed_llm.json")
    distribution: dict[tuple[str, str], int] = {}
    for scenario, documents in scenario_inputs:
        ocr_documents = [
            OCRDocument(
                document_type=document_type,
                text=text,
                page_count=1,
                source_id=f"synthetic:{scenario.id}:{document_type.value}",
            )
            for document_type, text in documents.items()
        ]
        candidates = HybridExtractor(provider).extract(ocr_documents)
        profile = consolidate(scenario.id, candidates)
        decisions = screen_all(profile)
        actual = {key: item.decision.value for key, item in decisions.items()}
        if actual != scenario.expected:
            raise RuntimeError(
                f"Décisions incohérentes pour {scenario.id}: {actual} != {scenario.expected}"
            )
        key = (actual["peace7"], actual["obsapa"])
        distribution[key] = distribution.get(key, 0) + 1
        report = PipelineReport(
            patient_id=scenario.id,
            provider="precomputed",
            provider_mode="precomputed",
            documents=ocr_documents,
            profile=profile,
            decisions=decisions,
            warnings=[
                "Données entièrement synthétiques.",
                "Prototype de recherche: toute décision nécessite une validation humaine.",
            ],
        )
        _write_json(
            PATIENTS / scenario.id / "expected_report.json",
            report.model_dump(mode="json"),
        )

    expected_distribution = {
        ("eligible", "non_eligible"): 2,
        ("non_eligible", "eligible"): 2,
        ("indeterminable", "indeterminable"): 2,
        ("non_eligible", "non_eligible"): 2,
    }
    if distribution != expected_distribution:
        raise RuntimeError(f"Distribution inattendue: {distribution}")
    _write_json(ROOT / "scenarios.json", catalog)
    _write_json(
        ROOT / "manifest.json",
        {
            "synthetic_only": True,
            "generator_seed": SEED,
            "scenario_count": len(SCENARIOS),
            "files": manifest_files,
        },
    )
    print(f"{len(SCENARIOS)} scénarios synthétiques générés et validés.")


if __name__ == "__main__":
    generate()
