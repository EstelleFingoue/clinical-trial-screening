---
title: Clinical Trial Screening Demo
emoji: 🩺
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
license: apache-2.0
---

# Clinical Trial Screening Demo

Ce projet est un **portfolio issu des travaux et problématiques que j'ai
explorés durant mon alternance au sein de l'ICB**. Il présente une démonstration
complète et explicable de pré-screening pour les essais cliniques PEACE-7 et
OBSAPA.

Afin de pouvoir être présenté publiquement, le projet a été entièrement
réimplémenté et utilise exclusivement des patients et documents synthétiques.
Aucune donnée réelle ni aucun code confidentiel de l'ICB n'est inclus.

**Estelle Danielle Fingoue**

```text
PDF fictifs → validation → OCR docTR → regex + LLM
             → consolidation → règles ternaires → rapport explicable
```

## Objectif

L'application transforme plusieurs documents cliniques PDF en un profil patient
structuré. Elle combine OCR, expressions régulières et modèle de langage pour
extraire les variables pertinentes, vérifier leurs citations et appliquer des
règles de pré-éligibilité.

Le résultat conserve les preuves, les conflits et les informations manquantes
afin que chaque décision puisse être comprise et vérifiée par un humain.

## Avertissement

Ce prototype de recherche n'est pas un dispositif médical. Ses sorties
`eligible`, `non_eligible` et `indeterminable` ne remplacent jamais une revue
médicale. Toute décision exige une validation humaine.

N'importez jamais de document réel, personnel ou sensible. Les imports publics
sont limités à cinq PDF fictifs de cinq pages et 10 Mo chacun, avec au moins
trois types documentaires et une attestation explicite.

## Fonctionnalités

- application Gradio et API FastAPI versionnée sous `/api/v1`;
- Groq par défaut, Ollama local et rapports pré-calculés pour la démo intégrée;
- OCR docTR chargé paresseusement une fois par processus;
- citations LLM vérifiées contre le texte source;
- conflits, alternatives et critères indéterminés visibles;
- huit scénarios reproductibles et PDF image-only;
- Docker Compose avec profils Groq et Ollama;
- contrôles Ruff, Pyright, pytest, pip-audit et Gitleaks.

## Démarrage rapide

Prérequis : `uv`, Python 3.12 et, pour l'OCR complet, les ressources nécessaires
à docTR.

```bash
uv python install 3.12
uv sync --extra dev
uv run python scripts/generate_demo_data.py
SCREENING_PROVIDER=precomputed uv run clinical-screening
```

Ouvrir <http://localhost:7860>. La documentation OpenAPI est disponible sur
<http://localhost:7860/api/docs>.

Pour Groq :

```bash
export GROQ_API_KEY="..."
make compose-groq
```

Pour Ollama :

```bash
make compose-ollama
```

## Qualité

```bash
make lint
make typecheck
make test
make build
```

Les tests `ocr` chargent docTR sur demande. Les tests `live` nécessitent une clé
Groq et ne sont jamais lancés automatiquement sur une pull request.

## Documentation

- [Architecture](docs/architecture.md)
- [Méthodologie](docs/methodology.md)
- [Data card](docs/data-card.md)
- [Model card](docs/model-card.md)
- [Mesure OCR CPU](docs/ocr-benchmark.md)
- [Limitations](docs/limitations.md)

Licence Apache-2.0.
