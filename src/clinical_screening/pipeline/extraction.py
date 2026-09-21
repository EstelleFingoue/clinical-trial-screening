from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from clinical_screening.config import get_variable_config
from clinical_screening.domain import (
    ExtractionMethod,
    LLMExtractionResponse,
    OCRDocument,
    VariableResult,
)
from clinical_screening.providers.base import InferenceProvider

_EMPTY = {None, "", "Non_mentionne", "Inconnu"}


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def verify_citation(citation: str, source: str) -> bool:
    return bool(citation and _normalize(citation) in _normalize(source))


def _match(text: str, pattern: str, flags: int = re.IGNORECASE) -> re.Match[str] | None:
    return re.search(pattern, text, flags)


class RegexExtractor:
    def __init__(self, config: dict[str, dict]) -> None:
        self.config = config

    def extract(self, document: OCRDocument) -> dict[str, VariableResult]:
        text = document.text
        out: dict[str, VariableResult] = {}

        def add(name: str, match: re.Match[str] | None, value: Any = None) -> None:
            sources = self.config.get(name, {}).get("sources", [])
            if not match or document.document_type.value not in sources:
                return
            extracted = value if value is not None else match.group(1)
            out[name] = VariableResult(
                name=name,
                value=extracted,
                confidence="regex_exact",
                method=ExtractionMethod.REGEX,
                evidence=match.group(0),
                document_type=document.document_type,
            )

        adenocarcinoma = _match(text, r"\bad[ée]nocarcinome(?:\s+prostatique)?\b")
        if adenocarcinoma:
            prefix = text[max(0, adenocarcinoma.start() - 35) : adenocarcinoma.start()]
            negated = bool(
                re.search(
                    r"(?:absence\s+d['e]?|sans|pas\s+d['e]?|aucun)\s*$",
                    prefix,
                    re.IGNORECASE,
                )
            )
            add("adenocarcinome", adenocarcinoma, not negated)
        gleason = _match(
            text,
            r"(?:score\s+de\s+)?Gleason\s*(?:[:=à]\s*)?"
            r"(?:(\d)\s*\+\s*(\d)\s*(?:=\s*(\d{1,2}))?|"
            r"(\d{1,2})(?:\s*\((\d)\s*\+\s*(\d)\))?)",
        )
        if gleason:
            if gleason.group(1) and gleason.group(2):
                total = gleason.group(3) or str(int(gleason.group(1)) + int(gleason.group(2)))
                value = f"{total} ({gleason.group(1)}+{gleason.group(2)})"
            else:
                value = gleason.group(4)
                if gleason.group(5) and gleason.group(6):
                    value += f" ({gleason.group(5)}+{gleason.group(6)})"
            add("gleason", gleason, value)
        isup = _match(text, r"(?:ISUP|grade\s+group)\s*(?:[:=]|\bde\b)?\s*([1-5])\b")
        add("grade_isup", isup, int(isup.group(1)) if isup else None)
        carottes = _match(text, r"(\d{1,2})\s+carottes?\b")
        add("nombre_carottes", carottes, int(carottes.group(1)) if carottes else None)
        volume = _match(
            text,
            r"(?:volume\s+(?:prostatique|de\s+la\s+prostate)|prostate\s+de)\s*[:=à]?\s*(\d+(?:[.,]\d+)?)\s*(?:cc|cm3|cm³|ml)\b",
        )
        add("volume_prostatique", volume, _number(volume.group(1)) if volume else None)
        psa = _match(
            text,
            r"\bPSA(?:\s+(?:initial|diagnostique|au\s+diagnostic))?\s*[:=à]?\s*(\d+(?:[.,]\d+)?)\s*(?:ng/mL)?",
        )
        add("psa_diagnostic", psa, _number(psa.group(1)) if psa else None)
        hb = _match(
            text,
            r"(?:h[ée]moglobine|Hb)\s*[:=à]?\s*(\d+(?:[.,]\d+)?)\s*(g/dL|g/L)?",
        )
        hb_value = _number(hb.group(1)) if hb else None
        if hb and hb_value is not None and hb.group(2) and hb.group(2).casefold() == "g/l":
            hb_value = float(hb_value) / 10
        add("hemoglobine", hb, hb_value)
        creat = _match(
            text,
            r"cr[ée]atinin(?:e|[ée]mie)\s*[:=à]?\s*(\d+(?:[.,]\d+)?)\s*(µ?mol/L|mg/L)?",
        )
        creat_value = _number(creat.group(1)) if creat else None
        if (
            creat
            and creat_value is not None
            and creat.group(2)
            and creat.group(2).casefold() == "mg/l"
        ):
            creat_value = round(float(creat_value) * 8.84, 1)
        add("creatinine", creat, creat_value)
        return out


def _number(value: str) -> int | float:
    number = float(value.replace(",", "."))
    return int(number) if number.is_integer() else number


class HybridExtractor:
    def __init__(self, provider: InferenceProvider) -> None:
        self.provider = provider
        self.config = get_variable_config()["variables"]
        self.regex = RegexExtractor(self.config)

    def extract(self, documents: list[OCRDocument]) -> list[VariableResult]:
        regex_by_doc = [(doc, self.regex.extract(doc)) for doc in documents]
        output = [value for _, results in regex_by_doc for value in results.values()]

        for document, regex_results in regex_by_doc:
            requested = self._variables_for_document(document, set(regex_results))
            if not requested:
                continue
            output.extend(self._extract_llm(document, requested))
        return output

    def _variables_for_document(
        self,
        document: OCRDocument,
        found_regex: set[str],
    ) -> list[str]:
        requested = []
        for name, spec in self.config.items():
            if document.document_type.value not in spec["sources"]:
                continue
            if spec["method"] == "llm" or name not in found_regex:
                requested.append(name)
        return requested

    def _extract_llm(
        self,
        document: OCRDocument,
        variables: list[str],
    ) -> list[VariableResult]:
        schema = _response_schema(variables)
        response = self.provider.extract(
            system_prompt=(
                "Tu extrais des informations d'un document médical entièrement fictif. "
                "Retourne seulement les champs demandés. Toute valeur affirmative doit avoir "
                "une citation exacte présente dans le document. N'invente rien."
            ),
            user_prompt=_user_prompt(document.text, variables, self.config),
            schema=schema,
        )
        return list(self._validated_results(document, variables, response))

    def _validated_results(
        self,
        document: OCRDocument,
        variables: list[str],
        response: LLMExtractionResponse,
    ) -> Iterable[VariableResult]:
        for name in variables:
            answer = response.variables.get(name)
            if answer is None:
                continue
            value = answer.value
            if value in _EMPTY:
                continue
            if not verify_citation(answer.citation, document.text):
                yield VariableResult(
                    name=name,
                    value=None,
                    confidence="llm_rejected_citation",
                    method=ExtractionMethod.LLM,
                    evidence=answer.citation,
                    document_type=document.document_type,
                )
                continue
            coerced = _coerce(value, self.config[name].get("allowed") or [])
            yield VariableResult(
                name=name,
                value=coerced,
                confidence="llm_verified",
                method=ExtractionMethod.LLM,
                evidence=answer.citation,
                document_type=document.document_type,
            )


def _coerce(value: Any, allowed: list[Any]) -> Any:
    if not allowed:
        return value
    normalized = str(value).strip().casefold()
    for item in allowed:
        if str(item).casefold() == normalized:
            return item
    stage_bases = [
        str(item).casefold()
        for item in allowed
        if re.fullmatch(r"[tnm]\d", str(item), re.IGNORECASE)
    ]
    if any(normalized.startswith(base) for base in stage_bases):
        return str(value).strip().upper()
    if normalized in {"true", "vrai", "oui", "1"}:
        candidate: Any = True
    elif normalized in {"false", "faux", "non", "0"}:
        candidate = False
    else:
        candidate = value
    for item in allowed:
        if type(item) is type(candidate) and item == candidate:
            return item
    return "Inconnu"


def _user_prompt(text: str, variables: list[str], config: dict) -> str:
    instructions = []
    for name in variables:
        allowed = config[name].get("allowed") or []
        suffix = f" Valeurs autorisées: {allowed}." if allowed else ""
        instructions.append(f"- {name}.{suffix}")
    return (
        "Pour chaque variable, retourne `value` et `citation`. "
        "Si absente, retourne `Non_mentionne` et une citation vide.\n"
        + "\n".join(instructions)
        + f'\n\nDOCUMENT FICTIF:\n"""\n{text}\n"""'
    )


def _response_schema(variables: list[str]) -> dict:
    answer = {
        "type": "object",
        "properties": {
            "value": {"type": ["string", "number", "boolean", "null"]},
            "citation": {"type": "string"},
        },
        "required": ["value", "citation"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "variables": {
                "type": "object",
                "properties": {name: answer for name in variables},
                "required": variables,
                "additionalProperties": False,
            }
        },
        "required": ["variables"],
        "additionalProperties": False,
    }
