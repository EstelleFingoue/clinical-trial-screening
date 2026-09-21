from __future__ import annotations

import json
from typing import Any, cast

import pymupdf
import pytest
from fastapi.testclient import TestClient

from clinical_screening.api.app import app
from clinical_screening.config import PROJECT_ROOT
from clinical_screening.synthetic import list_scenarios, load_precomputed_report
from clinical_screening.ui import build_ui
from clinical_screening.ui.gradio_app import (
    _criterion,
    _estimate_upload_duration,
    _format_duration,
    _processing_failed,
    _processing_started,
    _processing_succeeded,
    _render,
    _run_scenario_ui,
    _run_upload_ui,
)

client = TestClient(app)


def test_health_and_provider_statuses():
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["synthetic_only"] is True
    providers = client.get("/api/v1/providers")
    assert providers.status_code == 200
    assert {row["name"] for row in providers.json()} == {
        "groq",
        "ollama",
        "precomputed",
    }


def test_catalog_contains_exactly_eight_synthetic_scenarios():
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    assert len(response.json()) == 8
    assert len(list_scenarios()) == 8


def test_precomputed_scenario_endpoint():
    response = client.post(
        "/api/v1/pipeline/scenario",
        json={"scenario_id": "peace7-01", "provider": "precomputed"},
    )
    assert response.status_code == 200
    assert response.json()["decisions"]["peace7"]["decision"] == "eligible"


def test_unknown_scenario_returns_404():
    response = client.post(
        "/api/v1/pipeline/scenario",
        json={"scenario_id": "does-not-exist", "provider": "precomputed"},
    )
    assert response.status_code == 404


def test_custom_text_extraction_is_disabled_in_public_mode():
    response = client.post(
        "/api/v1/extract",
        json={
            "patient_id": "TEST",
            "provider": "precomputed",
            "documents": [
                {
                    "document_type": "rcp",
                    "text": "texte arbitraire",
                    "page_count": 1,
                    "source_id": "test",
                }
            ],
        },
    )
    assert response.status_code == 403


def test_upload_requires_attestation():
    response = client.post(
        "/api/v1/pipeline/upload",
        data={"attestation": "false", "provider": "precomputed"},
    )
    assert response.status_code == 400

    ocr_response = client.post("/api/v1/ocr", data={"attestation": "false"})
    assert ocr_response.status_code == 400


def test_screen_endpoint_accepts_a_valid_profile():
    report = load_precomputed_report("peace7-01")
    response = client.post(
        "/api/v1/screen",
        json={"profile": report.profile.model_dump(mode="json")},
    )
    assert response.status_code == 200
    assert response.json()["peace7"]["decision"] == "eligible"


def test_gradio_builds_with_locked_version():
    demo = build_ui()
    assert demo is not None
    assert demo.title == "Pré-screening clinique — Données synthétiques"
    components = demo.config["components"]
    tabs = [
        component["props"]["label"] for component in components if component["type"] == "tabitem"
    ]
    markdown = "\n".join(
        component["props"].get("value", "")
        for component in components
        if component["type"] == "markdown"
    )
    normalized_markdown = " ".join(markdown.split())
    assert tabs[:2] == ["Importer des PDF", "Patient synthétique intégré"]
    assert "Importer des PDF fictifs" not in tabs
    assert "Estelle Danielle Fingoue" in markdown
    assert "alternance au sein de l'ICB" in normalized_markdown
    assert "Anatomopathologie" in markdown
    assert "documents entièrement synthétiques générés" in markdown
    assert "Temps indicatifs" in markdown
    assert "25 à 45 s pour la première page" in markdown
    upload_status = next(
        component
        for component in components
        if component["props"].get("elem_id") == "upload-processing-status"
    )
    assert upload_status["type"] == "markdown"
    assert upload_status["props"]["visible"] is False
    upload_button = next(
        component
        for component in components
        if component["type"] == "button" and component["props"].get("value") == "Analyser les PDF"
    )
    dependencies = demo.config.get("dependencies", [])
    state_events = [
        dependency
        for dependency in dependencies
        if dependency["outputs"] == [upload_status["id"], upload_button["id"]]
    ]
    assert len(state_events) == 3
    assert any(event["trigger_only_on_success"] for event in state_events)
    assert any(event["trigger_only_on_failure"] for event in state_events)


class _Progress:
    def __call__(self, _value, *, desc: str):
        assert desc


def test_gradio_render_and_precomputed_action():
    rendered = _run_scenario_ui(
        "peace7-01",
        "precomputed",
        progress=cast(Any, _Progress()),
    )
    assert len(rendered) == 8
    assert "Télécharger le rapport JSON" in rendered[-1]
    assert _criterion(True) == "satisfait / présent"
    assert _criterion(False) == "non satisfait / absent"
    assert _criterion(None) == "indéterminé"
    assert len(_render(load_precomputed_report("peace7-01"))) == 8


def test_gradio_upload_requires_attestation():
    with pytest.raises(Exception, match="attestation"):
        _run_upload_ui(
            False,
            "groq",
            None,
            None,
            None,
            None,
            None,
            progress=cast(Any, _Progress()),
        )


@pytest.mark.parametrize(
    ("state_factory", "expected_text", "interactive"),
    [
        (_processing_started, "Traitement en cours", False),
        (_processing_succeeded, "Analyse terminée", True),
        (_processing_failed, "Analyse interrompue", True),
    ],
)
def test_gradio_upload_processing_states(state_factory, expected_text, interactive):
    status, button = state_factory()
    assert status.visible is True
    assert expected_text in status.value
    assert button.interactive is interactive
    assert ("cours" in button.value) is (not interactive)


def test_gradio_upload_estimate_uses_provider_and_selected_pdf_pages():
    pdf = PROJECT_ROOT / "demo_data" / "patients" / "peace7-01" / "pdf" / "anapath.pdf"
    estimate = _estimate_upload_duration("groq", str(pdf), str(pdf))
    assert "Extraction avec Groq" in estimate
    assert "2 PDF (2 pages)" in estimate
    assert "Total estimé" in estimate
    assert "Extraction avec Ollama" in _estimate_upload_duration("ollama", None, None, None)
    assert _format_duration(59) == "59 s"
    assert _format_duration(60) == "1 min"
    assert _format_duration(75) == "1 min 15 s"


def test_manifest_and_image_only_pdf_invariants():
    manifest = json.loads(
        (PROJECT_ROOT / "demo_data" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["synthetic_only"] is True
    assert manifest["scenario_count"] == 8
    assert len(manifest["files"]) == 32
    for item in manifest["files"]:
        path = PROJECT_ROOT / "demo_data" / item["path"]
        assert path.stat().st_size <= 10 * 1024 * 1024
        with pymupdf.open(path) as document:
            assert document.page_count <= 5
            assert all(not str(page.get_text()).strip() for page in document)


def test_expected_distribution():
    counts: dict[tuple[str, str], int] = {}
    for scenario in list_scenarios():
        key = (
            scenario.expected["peace7"].value,
            scenario.expected["obsapa"].value,
        )
        counts[key] = counts.get(key, 0) + 1
        assert 3 <= len(scenario.document_types) <= 5
    assert counts == {
        ("eligible", "non_eligible"): 2,
        ("non_eligible", "eligible"): 2,
        ("indeterminable", "indeterminable"): 2,
        ("non_eligible", "non_eligible"): 2,
    }


def test_no_forbidden_historical_project_reference_in_generated_data():
    demo_root = PROJECT_ROOT / "demo_data"
    for path in demo_root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "projet_estelle" not in text
        assert "/Users/" not in text
