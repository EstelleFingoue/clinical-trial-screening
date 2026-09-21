from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from clinical_screening.config import resource_path
from clinical_screening.domain import PipelineReport, ScenarioSummary

DEMO_ROOT = resource_path("demo_data")


@lru_cache(maxsize=1)
def scenario_catalog() -> dict[str, dict]:
    path = DEMO_ROOT / "scenarios.json"
    if not path.exists():
        raise RuntimeError("Le catalogue de scénarios synthétiques est absent.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows}


def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary.model_validate(
            {key: value for key, value in row.items() if key in ScenarioSummary.model_fields}
        )
        for row in scenario_catalog().values()
    ]


def scenario_pdf_paths(scenario_id: str) -> list[tuple[str, Path]]:
    row = scenario_catalog().get(scenario_id)
    if row is None:
        raise KeyError(f"Scénario inconnu: {scenario_id}")
    root = DEMO_ROOT / "patients" / scenario_id / "pdf"
    return [(doc_type, root / filename) for doc_type, filename in row["pdf_files"].items()]


def load_precomputed_report(
    scenario_id: str,
    *,
    fallback_reason: str | None = None,
) -> PipelineReport:
    path = DEMO_ROOT / "patients" / scenario_id / "expected_report.json"
    if not path.exists():
        raise KeyError(f"Rapport pré-calculé absent pour {scenario_id}.")
    report = PipelineReport.model_validate_json(path.read_text(encoding="utf-8"))
    report.provider = "precomputed"
    report.provider_mode = "precomputed"
    if fallback_reason:
        report.warnings.append(f"Résultat pré-calculé après indisponibilité: {fallback_reason}.")
    return report
