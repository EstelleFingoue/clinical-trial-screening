from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from clinical_screening.domain import (
    DecisionLabel,
    PatientProfile,
    TrialDecision,
)


def _value(profile: PatientProfile, name: str) -> Any:
    result = profile.variables.get(name)
    if result and result.alternatives:
        return None
    return result.value if result else None


def _bool(value: Any) -> bool | None:
    normalized = str(value).strip().casefold()
    if normalized in {"true", "vrai", "oui", "1"}:
        return True
    if normalized in {"false", "faux", "non", "0"}:
        return False
    return None


def _equals(value: Any, yes: set[str], no: set[str]) -> bool | None:
    normalized = str(value).strip().casefold()
    if normalized in yes:
        return True
    if normalized in no:
        return False
    return None


def _stage(
    value: Any,
    *,
    yes_prefixes: tuple[str, ...],
    no_prefixes: tuple[str, ...],
) -> bool | None:
    normalized = str(value or "").strip().casefold()
    if any(normalized.startswith(prefix) for prefix in yes_prefixes):
        return True
    if any(normalized.startswith(prefix) for prefix in no_prefixes):
        return False
    return None


def _number_compare(value: Any, predicate: Callable[[float], bool]) -> bool | None:
    try:
        return predicate(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _gleason_high(value: Any) -> bool | None:
    text = str(value or "")
    components = re.search(r"(\d)\s*\+\s*(\d)", text)
    if components:
        return int(components.group(1)) + int(components.group(2)) >= 8
    total = re.search(r"(?:=\s*)?(\d{1,2})", text)
    if total:
        return int(total.group(1)) >= 8
    return None


def screen_peace7(profile: PatientProfile) -> TrialDecision:
    criteria: dict[str, bool | None] = {
        "M0": _stage(
            _value(profile, "statut_metastatique"),
            yes_prefixes=("m0",),
            no_prefixes=("m1",),
        ),
        "ECOG_0_1": _number_compare(_value(profile, "ecog"), lambda value: value in {0, 1}),
        "volume<100": _number_compare(
            _value(profile, "volume_prostatique"), lambda value: value < 100
        ),
        "Gleason>=8": _gleason_high(_value(profile, "gleason")),
        "T3_T4": _stage(
            _value(profile, "stade_t"),
            yes_prefixes=("t3", "t4"),
            no_prefixes=("t1", "t2"),
        ),
        "PSA>=20": _number_compare(_value(profile, "psa_diagnostic"), lambda value: value >= 20),
        "excl:N1": _stage(
            _value(profile, "atteinte_ganglionnaire"),
            yes_prefixes=("n1",),
            no_prefixes=("n0",),
        ),
    }
    exclusion_variables = [
        "traitement_hormonal_anterieur",
        "chimiotherapie_anterieure",
        "prostatectomie_anterieure",
        "radiotherapie_anterieure",
        "diabete",
        "comorbidite_cardiaque",
        "comorbidite_infectieuse",
        "fonction_pulmonaire",
        "autre_cancer_recent",
    ]
    for name in exclusion_variables:
        criteria[f"excl:{name}"] = _bool(_value(profile, name))

    exclusions = [value for key, value in criteria.items() if key.startswith("excl:")]
    if any(value is True for value in exclusions):
        return _decision("peace7", DecisionLabel.NON_ELIGIBLE, "Exclusion explicite", criteria)
    for key in ("M0", "ECOG_0_1", "volume<100"):
        if criteria[key] is False:
            return _decision(
                "peace7",
                DecisionLabel.NON_ELIGIBLE,
                f"Critère obligatoire non respecté: {key}",
                criteria,
            )
    mandatory = ["M0", "ECOG_0_1", "volume<100"]
    if any(criteria[key] is None for key in mandatory) or any(
        value is None for value in exclusions
    ):
        return _decision(
            "peace7",
            DecisionLabel.INDETERMINABLE,
            "Critère obligatoire ou exclusion non documenté",
            criteria,
        )

    high_risk = [criteria["Gleason>=8"], criteria["T3_T4"], criteria["PSA>=20"]]
    positives = sum(value is True for value in high_risk)
    unknown = sum(value is None for value in high_risk)
    if positives >= 2:
        label = DecisionLabel.ELIGIBLE
        reason = "Cœur clinique compatible: au moins 2 facteurs de haut risque"
    elif positives + unknown < 2:
        label = DecisionLabel.NON_ELIGIBLE
        reason = "Moins de 2 facteurs de haut risque possibles"
    else:
        label = DecisionLabel.INDETERMINABLE
        reason = "Facteurs de haut risque incomplets"
    return _decision("peace7", label, reason, criteria)


def screen_obsapa(profile: PatientProfile) -> TrialDecision:
    criteria = {
        "metastatique_M1": _stage(
            _value(profile, "statut_metastatique"),
            yes_prefixes=("m1",),
            no_prefixes=("m0",),
        ),
        "PSA_disponible": _number_compare(_value(profile, "psa_diagnostic"), lambda _value: True),
        "excl:chimiotherapie_anterieure": _bool(_value(profile, "chimiotherapie_anterieure")),
    }
    if criteria["excl:chimiotherapie_anterieure"] is True:
        label = DecisionLabel.NON_ELIGIBLE
        reason = "Chimiothérapie antérieure documentée"
    elif criteria["metastatique_M1"] is False:
        label = DecisionLabel.NON_ELIGIBLE
        reason = "Maladie non métastatique M0"
    elif (
        criteria["metastatique_M1"] is True
        and criteria["PSA_disponible"] is True
        and criteria["excl:chimiotherapie_anterieure"] is False
    ):
        label = DecisionLabel.ELIGIBLE
        reason = "Cœur clinique compatible: M1 et PSA disponible"
    else:
        label = DecisionLabel.INDETERMINABLE
        reason = "Statut M ou PSA manquant"
    return _decision("obsapa", label, reason, criteria)


def screen_all(profile: PatientProfile) -> dict[str, TrialDecision]:
    return {
        "peace7": screen_peace7(profile),
        "obsapa": screen_obsapa(profile),
    }


def _decision(
    trial: str,
    label: DecisionLabel,
    reason: str,
    criteria: dict[str, bool | None],
) -> TrialDecision:
    return TrialDecision(
        trial=trial,
        decision=label,
        reason=reason,
        criteria=criteria,
        human_review=[
            "Validation médicale du dossier complet",
            "Consentement et critères administratifs",
        ],
    )
