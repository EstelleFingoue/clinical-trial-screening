from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from clinical_screening.config import get_variable_config
from clinical_screening.domain import ExtractionMethod, PatientProfile, VariableResult

_EMPTY = {None, "", "Non_mentionne", "Inconnu"}
_CONFIDENCE_RANK = {
    "regex_exact": 0,
    "llm_verified": 1,
    "precomputed": 2,
    "llm_rejected_citation": 99,
}


def consolidate(patient_id: str, candidates: list[VariableResult]) -> PatientProfile:
    config = get_variable_config()["variables"]
    grouped: dict[str, list[VariableResult]] = defaultdict(list)
    rejected: dict[str, list[VariableResult]] = defaultdict(list)
    for candidate in candidates:
        if candidate.value not in _EMPTY:
            grouped[candidate.name].append(candidate)
        elif candidate.confidence == "llm_rejected_citation":
            rejected[candidate.name].append(candidate)

    variables: dict[str, VariableResult] = {}
    conflicts: list[str] = []
    for name, values in grouped.items():
        sources = config.get(name, {}).get("sources", [])

        def rank(
            item: VariableResult,
            source_order: list[str] = sources,
        ) -> tuple[int, int]:
            source = item.document_type.value if item.document_type else ""
            source_rank = (
                source_order.index(source) if source in source_order else len(source_order)
            )
            return source_rank, _CONFIDENCE_RANK.get(item.confidence, 50)

        ordered = sorted(values, key=rank)
        selected = ordered[0].model_copy(deep=True)
        distinct = _distinct_values(value.value for value in ordered)
        if len(distinct) > 1:
            selected.alternatives = distinct[1:]
            conflicts.append(
                f"{name}: valeur retenue={selected.value!r}, alternatives={distinct[1:]!r}"
            )
        variables[name] = selected

    for name in config:
        if name not in variables:
            rejection = rejected.get(name, [])
            variables[name] = VariableResult(
                name=name,
                value="Non_mentionne",
                confidence="llm_rejected_citation" if rejection else "absent",
                method=ExtractionMethod.LLM if rejection else ExtractionMethod.REGEX,
                evidence=rejection[0].evidence if rejection else "",
                document_type=rejection[0].document_type if rejection else None,
            )
    return PatientProfile(patient_id=patient_id, variables=variables, conflicts=conflicts)


def _distinct_values(values) -> list[Any]:
    distinct: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = _comparison_key(value)
        if key not in seen:
            seen.add(key)
            distinct.append(value)
    return distinct


def _comparison_key(value: Any) -> str:
    if isinstance(value, bool):
        return f"bool:{value}"
    try:
        return f"number:{Decimal(str(value).replace(',', '.')).normalize()}"
    except (InvalidOperation, ValueError):
        return f"text:{str(value).strip().casefold()}"
