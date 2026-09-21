from __future__ import annotations

from pathlib import Path

import pytest

from clinical_screening.application import run_scenario, run_upload
from clinical_screening.domain import (
    DecisionLabel,
    DocumentType,
    ExtractionMethod,
    OCRDocument,
    PatientProfile,
    VariableResult,
)
from clinical_screening.pipeline.consolidation import consolidate
from clinical_screening.pipeline.eligibility import screen_all
from clinical_screening.pipeline.extraction import (
    RegexExtractor,
    _response_schema,
    verify_citation,
)
from clinical_screening.providers import ProviderError
from clinical_screening.synthetic import load_precomputed_report


def _variable(name: str, value, alternatives=None) -> VariableResult:
    return VariableResult(
        name=name,
        value=value,
        confidence="test",
        method=ExtractionMethod.PRECOMPUTED,
        alternatives=alternatives or [],
    )


def _profile(**updates) -> PatientProfile:
    values = {
        "statut_metastatique": "M0",
        "ecog": 0,
        "volume_prostatique": 50,
        "gleason": "8 (4+4)",
        "stade_t": "T3a",
        "psa_diagnostic": 30,
        "atteinte_ganglionnaire": "N0",
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
    values.update(updates)
    return PatientProfile(
        patient_id="TEST",
        variables={name: _variable(name, value) for name, value in values.items()},
    )


@pytest.mark.parametrize(
    ("updates", "peace7", "obsapa"),
    [
        ({}, DecisionLabel.ELIGIBLE, DecisionLabel.NON_ELIGIBLE),
        (
            {"statut_metastatique": "M1b"},
            DecisionLabel.NON_ELIGIBLE,
            DecisionLabel.ELIGIBLE,
        ),
        (
            {"statut_metastatique": "Mx"},
            DecisionLabel.INDETERMINABLE,
            DecisionLabel.INDETERMINABLE,
        ),
        (
            {"chimiotherapie_anterieure": True},
            DecisionLabel.NON_ELIGIBLE,
            DecisionLabel.NON_ELIGIBLE,
        ),
        (
            {"ecog": 2},
            DecisionLabel.NON_ELIGIBLE,
            DecisionLabel.NON_ELIGIBLE,
        ),
        (
            {"volume_prostatique": "Non_mentionne"},
            DecisionLabel.INDETERMINABLE,
            DecisionLabel.NON_ELIGIBLE,
        ),
    ],
)
def test_eligibility_matrix(updates, peace7, obsapa):
    decisions = screen_all(_profile(**updates))
    assert decisions["peace7"].decision is peace7
    assert decisions["obsapa"].decision is obsapa


def test_unknown_exclusion_is_indeterminable():
    profile = _profile(chimiotherapie_anterieure="Non_mentionne")
    decisions = screen_all(profile)
    assert decisions["peace7"].decision is DecisionLabel.INDETERMINABLE
    assert decisions["obsapa"].decision is DecisionLabel.NON_ELIGIBLE

    metastatic = _profile(
        statut_metastatique="M1",
        chimiotherapie_anterieure="Non_mentionne",
    )
    assert screen_all(metastatic)["obsapa"].decision is DecisionLabel.INDETERMINABLE


def test_conflicting_decision_variable_is_indeterminable():
    profile = _profile()
    profile.variables["statut_metastatique"].alternatives = ["M1"]
    decisions = screen_all(profile)
    assert decisions["peace7"].decision is DecisionLabel.INDETERMINABLE
    assert decisions["obsapa"].decision is DecisionLabel.INDETERMINABLE


def test_gleason_components_are_summed():
    profile = _profile(gleason="4+4=8")
    assert screen_all(profile)["peace7"].criteria["Gleason>=8"] is True


def test_citation_verification_normalizes_spacing_and_case():
    assert verify_citation("PSA : 20", "Résultat\nPSA :   20 ng/mL")
    assert not verify_citation("PSA : 21", "PSA : 20")


def test_groq_schema_does_not_mix_integer_and_number():
    schema = _response_schema(["ecog"])
    value_types = schema["properties"]["variables"]["properties"]["ecog"]["properties"]["value"][
        "type"
    ]
    assert "number" in value_types
    assert "integer" not in value_types


def test_regex_respects_sources_and_normalizes_units():
    extractor = RegexExtractor(
        {
            "hemoglobine": {"sources": ["bilan"]},
            "creatinine": {"sources": ["bilan"]},
            "adenocarcinome": {"sources": ["anapath"]},
        }
    )
    bilan = OCRDocument(
        document_type=DocumentType.BILAN,
        text="Hb : 140 g/L. Créatininémie : 10 mg/L. Absence d'adénocarcinome.",
        page_count=1,
        source_id="test",
    )
    results = extractor.extract(bilan)
    assert results["hemoglobine"].value == 14
    assert results["creatinine"].value == 88.4
    assert "adenocarcinome" not in results


def test_regex_handles_negation_and_gleason_notation():
    extractor = RegexExtractor(
        {
            "adenocarcinome": {"sources": ["anapath"]},
            "gleason": {"sources": ["anapath"]},
        }
    )
    document = OCRDocument(
        document_type=DocumentType.ANAPATH,
        text="Absence d'adénocarcinome. Gleason 4+4=8.",
        page_count=1,
        source_id="test",
    )
    results = extractor.extract(document)
    assert results["adenocarcinome"].value is False
    assert results["gleason"].value == "8 (4+4)"


def test_consolidation_prioritizes_source_and_records_conflict():
    candidates = [
        VariableResult(
            name="psa_diagnostic",
            value=20,
            confidence="llm_verified",
            method=ExtractionMethod.LLM,
            document_type=DocumentType.COURRIER,
        ),
        VariableResult(
            name="psa_diagnostic",
            value=25,
            confidence="regex_exact",
            method=ExtractionMethod.REGEX,
            document_type=DocumentType.ANAPATH,
        ),
    ]
    profile = consolidate("TEST", candidates)
    assert profile.variables["psa_diagnostic"].value == 25
    assert profile.variables["psa_diagnostic"].alternatives == [20]
    assert profile.conflicts


def test_consolidation_preserves_rejected_citation():
    candidate = VariableResult(
        name="ecog",
        value=None,
        confidence="llm_rejected_citation",
        method=ExtractionMethod.LLM,
        evidence="citation inventée",
        document_type=DocumentType.RCP,
    )
    result = consolidate("TEST", [candidate]).variables["ecog"]
    assert result.confidence == "llm_rejected_citation"
    assert result.evidence == "citation inventée"


def test_precomputed_scenario_short_circuits_ocr():
    report = run_scenario("peace7-01", provider_name="precomputed")
    assert report.provider_mode == "precomputed"
    assert report.decisions["peace7"].decision is DecisionLabel.ELIGIBLE


def test_precomputed_is_refused_for_upload():
    with pytest.raises(ProviderError, match="réservé"):
        run_upload({}, provider_name="precomputed")


def test_all_expected_reports_validate():
    for scenario_id in (
        "peace7-01",
        "peace7-02",
        "obsapa-01",
        "obsapa-02",
        "indeterminate-01",
        "indeterminate-02",
        "noneligible-01",
        "noneligible-02",
    ):
        assert load_precomputed_report(scenario_id).patient_id == scenario_id


def test_generated_reports_do_not_reference_real_paths():
    report = load_precomputed_report("peace7-01")
    payload = report.model_dump_json()
    assert "/Users/" not in payload
    assert str(Path.home()) not in payload
