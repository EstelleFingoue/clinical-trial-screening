from __future__ import annotations

import base64
from pathlib import Path

import gradio as gr
import pymupdf

from clinical_screening.application import run_scenario, run_upload
from clinical_screening.config import get_settings
from clinical_screening.domain import DocumentType, PipelineReport
from clinical_screening.synthetic import list_scenarios


def build_ui() -> gr.Blocks:
    scenarios = list_scenarios()
    choices = [(f"{item.title} — {item.category}", item.id) for item in scenarios]

    with gr.Blocks(title="Pré-screening clinique — Données synthétiques") as demo:
        gr.Markdown(
            """
# Pré-screening d'essais cliniques
Cette application illustre un pipeline de pré-screening qui transforme des documents
cliniques PDF en un profil structuré, puis évalue de façon explicable les principaux
critères des essais **PEACE-7** et **OBSAPA**. Elle combine OCR, règles d'extraction et
modèle de langage pour restituer les variables détectées, leurs preuves et les points
qui nécessitent une vérification humaine.

**Projet réalisé par Estelle Danielle Fingoue dans le cadre de son alternance au sein
de l'ICB.**

Ce prototype ne constitue pas un dispositif médical. Toute décision exige une validation
humaine et aucun document réel ou sensible ne doit être importé dans cette démonstration.
"""
        )
        with gr.Tabs():
            with gr.Tab("Importer des PDF"):
                gr.Markdown(
                    """
Le pipeline attend au moins trois types de documents complémentaires afin de croiser les
informations cliniques :

- **Anatomopathologie** : confirme le diagnostic et renseigne notamment Gleason et ISUP.
- **Bilan biologique** : apporte les valeurs biologiques utiles, comme l'hémoglobine et
  la créatinine.
- **RCP** : synthétise le stade de la maladie et la stratégie thérapeutique discutée.
- **Consultation** et **courrier** : documentent l'état général, les antécédents,
  les comorbidités et les traitements déjà reçus.

Vous pouvez importer jusqu'à cinq PDF, limités à cinq pages et 10 Mo chacun. Groq
transfère le texte OCR vers un service externe.
"""
                )
                upload_provider = gr.Dropdown(
                    choices=["groq", "ollama"],
                    value="groq",
                    label="Fournisseur d'inférence",
                )
                upload_estimate = gr.Markdown(
                    value=_estimate_upload_duration("groq", None, None, None, None, None),
                    elem_id="upload-time-estimate",
                )
                with gr.Row():
                    anapath = gr.File(label="Anatomopathologie", file_types=[".pdf"])
                    bilan = gr.File(label="Bilan biologique", file_types=[".pdf"])
                    rcp = gr.File(label="RCP", file_types=[".pdf"])
                with gr.Row():
                    consultation = gr.File(label="Consultation", file_types=[".pdf"])
                    courrier = gr.File(label="Courrier", file_types=[".pdf"])
                attestation = gr.Checkbox(
                    label="J'atteste que ces documents sont fictifs et non sensibles."
                )
                run_upload_button = gr.Button("Analyser les PDF", variant="primary")
                upload_status = gr.Markdown(
                    value="",
                    visible=False,
                    elem_id="upload-processing-status",
                )
            with gr.Tab("Patient synthétique intégré"):
                gr.Markdown(
                    """
Cet espace permet de tester le pipeline de bout en bout avec des patients et des
documents entièrement synthétiques générés pour la démonstration. Aucune donnée réelle
n'est utilisée.
"""
                )
                scenario_provider = gr.Dropdown(
                    choices=["precomputed", "groq", "ollama"],
                    value="precomputed",
                    label="Mode d'inférence",
                    info="Precomputed est instantané; Groq et Ollama exécutent le pipeline live.",
                )
                scenario = gr.Dropdown(
                    choices=choices,
                    value=choices[0][1] if choices else None,
                    label="Scénario",
                )
                run_demo = gr.Button("Lancer le pipeline complet", variant="primary")

        with gr.Tabs():
            with gr.Tab("Décisions"):
                summary = gr.Markdown()
                warnings = gr.Markdown()
            with gr.Tab("Profil clinique"):
                variables = gr.Dataframe(
                    headers=[
                        "Variable",
                        "Valeur",
                        "Confiance",
                        "Méthode",
                        "Document",
                        "Preuve",
                        "Alternatives",
                    ],
                    interactive=False,
                    wrap=True,
                )
            with gr.Tab("Critères PEACE-7"):
                peace = gr.Dataframe(
                    headers=["Critère", "Résultat"],
                    interactive=False,
                )
            with gr.Tab("Critères OBSAPA"):
                obsapa = gr.Dataframe(
                    headers=["Critère", "Résultat"],
                    interactive=False,
                )
            with gr.Tab("Texte OCR"):
                ocr_text = gr.Textbox(lines=24, interactive=False)
            with gr.Tab("Rapport JSON"):
                report_json = gr.JSON(label="Rapport copiable")
                report_download = gr.HTML()

        outputs = [
            summary,
            warnings,
            variables,
            peace,
            obsapa,
            ocr_text,
            report_json,
            report_download,
        ]
        run_demo.click(
            fn=_run_scenario_ui,
            inputs=[scenario, scenario_provider],
            outputs=outputs,
        )
        estimate_inputs = [
            upload_provider,
            anapath,
            bilan,
            rcp,
            consultation,
            courrier,
        ]
        for estimate_trigger in estimate_inputs:
            estimate_trigger.change(
                fn=_estimate_upload_duration,
                inputs=estimate_inputs,
                outputs=upload_estimate,
                queue=False,
                show_progress="hidden",
            )
        upload_start = run_upload_button.click(
            fn=_processing_started,
            outputs=[upload_status, run_upload_button],
            queue=False,
            show_progress="hidden",
        )
        upload_analysis = upload_start.then(
            fn=_run_upload_ui,
            inputs=[
                attestation,
                upload_provider,
                anapath,
                bilan,
                rcp,
                consultation,
                courrier,
            ],
            outputs=outputs,
            show_progress="full",
            show_progress_on=upload_status,
        )
        upload_analysis.success(
            fn=_processing_succeeded,
            outputs=[upload_status, run_upload_button],
            queue=False,
            show_progress="hidden",
        )
        upload_analysis.failure(
            fn=_processing_failed,
            outputs=[upload_status, run_upload_button],
            queue=False,
            show_progress="hidden",
        )
    return demo


def _run_scenario_ui(
    scenario_id: str,
    provider: str,
    progress=gr.Progress(),  # noqa: B008 - Gradio injects this dependency.
):
    progress(0, desc="Préparation du scénario")
    try:
        report = run_scenario(
            scenario_id,
            provider_name=provider,
            progress=_progress_callback(progress),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    return _render(report)


def _run_upload_ui(
    attestation: bool,
    provider: str,
    anapath,
    bilan,
    rcp,
    consultation,
    courrier,
    progress=gr.Progress(),  # noqa: B008 - Gradio injects this dependency.
):
    progress(0, desc="Validation des PDF")
    if not attestation:
        raise gr.Error("L'attestation de documents fictifs est obligatoire.")
    raw = {
        DocumentType.ANAPATH: anapath,
        DocumentType.BILAN: bilan,
        DocumentType.RCP: rcp,
        DocumentType.CONSULTATION: consultation,
        DocumentType.COURRIER: courrier,
    }
    files = {
        document_type: _bounded_path_read(value) for document_type, value in raw.items() if value
    }
    try:
        report = run_upload(
            files,
            provider_name=provider,
            progress=_progress_callback(progress),
        )
    except Exception as exc:
        raise gr.Error(str(exc)) from exc
    return _render(report)


def _processing_started():
    return (
        gr.Markdown(
            value=(
                "### Traitement en cours\n"
                "Préparation de l'analyse. Les étapes de validation, OCR, extraction "
                "clinique et consolidation s'afficheront ici."
            ),
            visible=True,
        ),
        gr.Button(value="Analyse en cours…", interactive=False),
    )


def _processing_succeeded():
    return (
        gr.Markdown(
            value="### Analyse terminée\nLes résultats sont disponibles ci-dessous.",
            visible=True,
        ),
        gr.Button(value="Analyser les PDF", interactive=True),
    )


def _processing_failed():
    return (
        gr.Markdown(
            value=(
                "### Analyse interrompue\n"
                "Consultez le message d'erreur puis corrigez les fichiers ou la configuration."
            ),
            visible=True,
        ),
        gr.Button(value="Analyser les PDF", interactive=True),
    )


def _estimate_upload_duration(provider: str, *uploads) -> str:
    document_count, page_count = _selected_pdf_stats(uploads)
    llm_minimum, llm_maximum = (3, 15) if provider == "groq" else (10, 60)
    llm_label = "Groq" if provider == "groq" else "Ollama"
    lines = [
        "### Temps indicatifs",
        "- Validation des PDF : **1 à 5 s**",
        (
            "- Chargement de docTR et OCR : **25 à 45 s pour la première page**, "
            "puis **5 à 20 s par page supplémentaire**"
        ),
        (f"- Extraction avec {llm_label} : **{llm_minimum} à {llm_maximum} s par document**"),
        "- Consolidation et règles d'éligibilité : **1 à 3 s**",
    ]
    if document_count:
        ocr_minimum = 25 + max(0, page_count - 1) * 5
        ocr_maximum = 45 + max(0, page_count - 1) * 20
        total_minimum = 2 + ocr_minimum + document_count * llm_minimum
        total_maximum = 8 + ocr_maximum + document_count * llm_maximum
        lines.extend(
            [
                "",
                (
                    f"**Total estimé pour {document_count} PDF "
                    f"({page_count} page{'s' if page_count > 1 else ''}) : "
                    f"{_format_duration(total_minimum)} à "
                    f"{_format_duration(total_maximum)}.**"
                ),
            ]
        )
    else:
        lines.extend(["", "_Ajoutez des PDF pour calculer une estimation totale._"])
    lines.extend(
        [
            "",
            (
                "_Ces durées varient selon le nombre et la qualité des pages, "
                "le matériel et la disponibilité du fournisseur._"
            ),
        ]
    )
    return "\n".join(lines)


def _selected_pdf_stats(uploads) -> tuple[int, int]:
    document_count = 0
    page_count = 0
    for upload in uploads:
        if not upload:
            continue
        document_count += 1
        try:
            with pymupdf.open(_path(upload)) as document:
                page_count += document.page_count
        except Exception:
            page_count += 1
    return document_count, page_count


def _format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} s"
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes} min {remainder:02d} s" if remainder else f"{minutes} min"


def _path(value) -> str:
    return value if isinstance(value, str) else value.name


def _bounded_path_read(value) -> bytes:
    path = Path(_path(value))
    maximum = get_settings().uploads.max_bytes_per_file
    with path.open("rb") as handle:
        content = handle.read(maximum + 1)
    if len(content) > maximum:
        raise gr.Error("Le PDF dépasse la taille maximale de 10 Mo.")
    return content


def _progress_callback(progress):
    def callback(message: str, value: float) -> None:
        progress(value, desc=message)

    return callback


def _render(report: PipelineReport):
    decisions = report.decisions
    summary = (
        f"## Patient {report.patient_id}\n"
        f"**PEACE-7 :** `{decisions['peace7'].decision.value}` — "
        f"{decisions['peace7'].reason}\n\n"
        f"**OBSAPA :** `{decisions['obsapa'].decision.value}` — "
        f"{decisions['obsapa'].reason}\n\n"
        f"Fournisseur : `{report.provider}` ({report.provider_mode})"
    )
    warning_text = "\n".join(f"- {warning}" for warning in report.warnings)
    rows = [
        [
            name,
            result.value,
            result.confidence,
            result.method.value,
            result.document_type.value if result.document_type else "",
            result.evidence,
            ", ".join(map(str, result.alternatives)),
        ]
        for name, result in report.profile.variables.items()
    ]
    peace = [[key, _criterion(value)] for key, value in decisions["peace7"].criteria.items()]
    obsapa = [[key, _criterion(value)] for key, value in decisions["obsapa"].criteria.items()]
    ocr = "\n\n".join(
        f"===== {document.document_type.value.upper()} =====\n{document.text}"
        for document in report.documents
    )
    payload = report.model_dump_json(indent=2)
    encoded = base64.b64encode(payload.encode()).decode()
    download = (
        '<a download="rapport-screening.json" '
        f'href="data:application/json;base64,{encoded}">Télécharger le rapport JSON</a>'
    )
    return (
        summary,
        warning_text,
        rows,
        peace,
        obsapa,
        ocr,
        report.model_dump(mode="json"),
        download,
    )


def _criterion(value: bool | None) -> str:
    if value is True:
        return "satisfait / présent"
    if value is False:
        return "non satisfait / absent"
    return "indéterminé"
