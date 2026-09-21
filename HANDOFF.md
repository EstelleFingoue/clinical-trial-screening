# Passation — Clinical Trial Screening Demo

Dernière mise à jour : 20 septembre 2026.

Ce document permet de reprendre le développement directement depuis le dépôt
`clinical-trial-screening-demo` dans un nouveau chat Cursor.

## 1. Objectif du dépôt

Construire un portfolio public, entièrement réimplémenté, démontrant un pipeline de
pré-identification de patients potentiellement éligibles aux essais PEACE-7 et OBSAPA :

```text
PDF fictifs
→ validation et stockage temporaire
→ OCR docTR
→ extraction regex
→ extraction LLM
→ vérification des citations
→ consolidation du profil clinique
→ règles PEACE-7 et OBSAPA
→ résultat explicable variable par variable
```

Le dépôt doit fournir :

- une application Gradio accessible aux recruteurs ;
- une API FastAPI versionnée ;
- Groq comme fournisseur LLM par défaut ;
- Ollama comme fournisseur local sélectionnable par configuration ;
- un démarrage local avec Docker et Docker Compose ;
- un déploiement Hugging Face conditionnel, sans coût ;
- huit patients synthétiques intégrés ;
- la possibilité d'importer au moins trois types de PDF fictifs.

## 2. Contraintes non négociables

### Indépendance vis-à-vis du projet ICB

- Ne copier aucun code du dépôt `/Users/cartelgouabou/Downloads/projet_estelle`.
- Ne copier aucune donnée, sortie, image, notebook, métrique individuelle, liste de noms ou
  artefact dérivé de patients réels.
- La nouvelle implémentation est une réécriture autonome autorisée pour le portfolio.
- Les éventuels résultats réels ne pourront apparaître que sous forme agrégée et autorisée,
  dans une page documentaire séparée.

### Politique des imports publics

- N'accepter que des PDF fictifs/non sensibles.
- Exiger une attestation explicite avant traitement.
- Maximum cinq PDF par analyse.
- Maximum cinq pages et 10 Mo par PDF.
- Exiger au moins trois types documentaires distincts.
- Types : `anapath`, `bilan`, `rcp`, `consultation`, `courrier`.
- Le type est choisi manuellement via cinq zones d'import distinctes.
- Supprimer les PDF et textes OCR à la fin de la requête.
- Ne journaliser ni noms de fichiers, ni textes OCR, ni valeurs cliniques.
- Ne pas utiliser de cache disque pour les documents importés.

### Positionnement médical

- L'application est un prototype de recherche et non un dispositif médical.
- Toute décision doit afficher qu'une validation humaine est obligatoire.
- Une décision est ternaire : `eligible`, `non_eligible` ou `indeterminable`.
- Les preuves, conflits et critères non automatisables doivent rester visibles.

## 3. État du dépôt

- Dépôt Git initialisé sur la branche `main`.
- Aucun commit n'a encore été créé.
- Tous les fichiers applicatifs sont encore non suivis.
- Aucun remote GitHub ou Hugging Face n'est configuré.
- Aucun fichier du dépôt historique n'a été copié.
- Le plan Cursor d'origine reste dans l'ancien workspace et ne doit pas être nécessaire à la
  reprise : ce document en contient les exigences utiles.

## 4. Ce qui a déjà été implémenté

### Squelette Python et dépendances

Fichier : `pyproject.toml`

- Python ciblé : 3.12.
- FastAPI, Gradio, OpenAI SDK, Pydantic, PyYAML, Pillow et PyMuPDF déclarés.
- docTR est actuellement dans l'extra optionnel `ocr`.
- Extras de développement : pytest, coverage, Ruff, Pyright et pip-audit.
- Package installable `src/clinical_screening`.

Attention : aucun `uv.lock` n'existe encore et les dépendances n'ont pas été installées.

### Configuration

Fichiers :

- `config/app.yaml`
- `config/variables.yaml`
- `config/trials/peace7.yaml`
- `config/trials/obsapa.yaml`
- `.env.example`

La configuration prévoit :

- Groq par défaut ;
- Ollama via `SCREENING_PROVIDER=ollama` ;
- modèles et URL configurables ;
- limites des PDF ;
- paramètres docTR ;
- timeouts, retries et fallback pré-calculé ;
- surcharge par variables d'environnement.

### Modèles de domaine

Fichiers :

- `src/clinical_screening/domain/models.py`
- `src/clinical_screening/domain/__init__.py`

Schémas Pydantic présents :

- `DocumentType`
- `OCRDocument`
- `VariableResult`
- `PatientProfile`
- `TrialDecision`
- `PipelineReport`
- `ScenarioSummary`
- `ProviderStatus`
- schémas de sortie LLM

### Ingestion PDF

Fichier : `src/clinical_screening/ingestion/pdf.py`

Implémenté :

- vérification de la signature PDF ;
- limite de taille ;
- rejet des PDF chiffrés ;
- limite de pages ;
- identifiant SHA-256 non nominatif ;
- répertoire temporaire par analyse ;
- suppression via `TemporaryDirectory` ;
- validation du nombre de types distincts.

### OCR

Fichier : `src/clinical_screening/ocr/engine.py`

Implémenté :

- interface `OCREngine` ;
- backend docTR chargé paresseusement ;
- verrou de chargement ;
- concurrence bornée ;
- backend léger `EmbeddedTextOCREngine` pour le développement.

Non vérifié :

- installation réelle de docTR ;
- téléchargement des modèles ;
- consommation mémoire et latence CPU ;
- qualité sur les futurs PDF image-only.

### Extraction et consolidation

Fichiers :

- `src/clinical_screening/pipeline/extraction.py`
- `src/clinical_screening/pipeline/consolidation.py`

Implémenté :

- regex pour adénocarcinome, Gleason, ISUP, carottes, volume, PSA, hémoglobine et créatinine ;
- routage par type de document ;
- appel LLM groupé pour les autres variables et le rattrapage regex ;
- JSON Schema dynamique ;
- vérification que chaque citation affirmative existe dans le texte ;
- rejet des citations invalides ;
- consolidation par priorité de source ;
- signalement des conflits et alternatives ;
- valeurs absentes explicites.

### Règles de pré-éligibilité

Fichier : `src/clinical_screening/pipeline/eligibility.py`

Implémenté :

- règle PEACE-7 ternaire ;
- règle OBSAPA ternaire ;
- trace critère par critère ;
- raisons synthétiques ;
- éléments à vérifier humainement.

Ces règles sont une réécriture de démonstration et doivent encore être validées par les tests.

### Orchestration

Fichiers :

- `src/clinical_screening/pipeline/service.py`
- `src/clinical_screening/application.py`

Implémenté :

- exécution OCR sur plusieurs PDF ;
- extraction hybride ;
- consolidation ;
- application des deux règles ;
- callback de progression ;
- exécution d'un scénario intégré ou d'un import.

### Fournisseurs LLM

Fichiers :

- `src/clinical_screening/providers/base.py`
- `src/clinical_screening/providers/openai_compatible.py`
- `src/clinical_screening/providers/groq.py`
- `src/clinical_screening/providers/ollama.py`
- `src/clinical_screening/providers/precomputed.py`
- `src/clinical_screening/providers/factory.py`

Implémenté :

- interface commune `InferenceProvider` ;
- client OpenAI-compatible ;
- structured output strict par JSON Schema ;
- séparation `system` / `user` ;
- timeout et retries ;
- Groq avec `GROQ_API_KEY` ;
- Ollama avec endpoint local ;
- provider pré-calculé fondé sur un registre de réponses ;
- sélection via configuration.

Le registre `demo_data/precomputed_llm.json` n'existe pas encore.

### API FastAPI

Fichier : `src/clinical_screening/api/app.py`

Routes esquissées :

- `GET /api/v1/health`
- `GET /api/v1/providers`
- `GET /api/v1/scenarios`
- `POST /api/v1/ocr`
- `POST /api/v1/extract`
- `POST /api/v1/screen`
- `POST /api/v1/pipeline/scenario`
- `POST /api/v1/pipeline/upload`
- documentation prévue sous `/api/docs`

Les routes d'import utilisent cinq champs PDF distincts et une attestation.

Attention : l'import de l'application n'a pas encore été testé. Les signatures FastAPI
`Annotated`/`UploadFile` peuvent nécessiter une correction.

### Interface Gradio

Fichier : `src/clinical_screening/ui/gradio_app.py`

Deux parcours sont esquissés :

1. sélectionner un patient synthétique ;
2. importer trois à cinq types de PDF.

Sorties prévues :

- décisions PEACE-7 et OBSAPA ;
- fournisseur réellement utilisé ;
- tableau des variables ;
- confiance, méthode, document et citation ;
- alternatives et conflits ;
- critères par essai ;
- texte OCR ;
- rapport JSON.

L'interface n'a pas encore été lancée ni vérifiée avec la version réelle de Gradio.

### Référentiel des scénarios

Fichier : `src/clinical_screening/synthetic/repository.py`

Le chargeur attend :

```text
demo_data/
├── manifest.json
├── scenarios.json
├── precomputed_llm.json
└── patients/<scenario_id>/
    ├── pdf/
    └── expected_report.json
```

Ces fichiers n'existent pas encore.

## 5. Travail interrompu

La création de `scripts/generate_demo_data.py` a été interrompue avant l'écriture du fichier.
Le fichier n'existe donc pas et doit être recréé.

Le script prévu devait :

- définir exactement huit scénarios fictifs ;
- produire leurs documents texte ;
- rendre chaque document en PDF image-only ;
- produire la vérité terrain ;
- produire `expected_report.json` ;
- produire `precomputed_llm.json` ;
- produire `manifest.json` et `scenarios.json`.

Répartition exigée :

- 2 patients éligibles PEACE-7 ;
- 2 patients éligibles OBSAPA ;
- 2 patients indéterminables pour les deux essais ;
- 2 patients non éligibles pour les deux essais.

Chaque patient doit contenir entre trois et cinq types de documents.

## 6. Points techniques connus à vérifier/corriger

1. Installer Python 3.12 avec `uv` et générer `uv.lock`.
2. Lancer Ruff et Pyright : aucun lint ni type-check n'a encore été exécuté.
3. Corriger les erreurs révélées par l'import de `clinical_screening.api.app`.
4. Vérifier les annotations `UploadFile` de FastAPI.
5. Vérifier la compatibilité de `gr.Dataframe`, `gr.JSON`, `gr.Progress` et
   `gr.mount_gradio_app` avec la version verrouillée.
6. Ne pas laisser `run_scenario()` intercepter toutes les exceptions : le fallback doit couvrir
   les indisponibilités OCR/provider prévues, pas masquer les bugs de programmation.
7. Si `provider=precomputed` est choisi pour un scénario intégré, charger directement
   `expected_report.json`.
8. Refuser `provider=precomputed` pour un import utilisateur inédit.
9. Ajouter un cache uniquement pour les scénarios intégrés ; aucun cache disque pour les uploads.
10. Vérifier que les répertoires temporaires sont supprimés même après une erreur OCR ou LLM.
11. Mesurer docTR sur CPU avant de confirmer la viabilité d'un Space gratuit.
12. Vérifier que le Docker final utilise un seul worker afin de ne charger docTR qu'une fois.

## 7. Reste à implémenter

### Priorité 1 — Jeu synthétique

- Recréer `scripts/generate_demo_data.py`.
- Générer huit dossiers cohérents.
- Utiliser exclusivement des identités manifestement fictives.
- Générer des PDF image-only lisibles par docTR.
- Ajouter du bruit OCR léger et déterministe.
- Vérifier automatiquement la distribution attendue des décisions.
- Ajouter une data card et un manifeste `synthetic_only`.

### Priorité 2 — Stabilisation API et interface

- Installer les dépendances.
- Importer et lancer l'application.
- Corriger les incompatibilités FastAPI/Gradio.
- Tester chaque route.
- Vérifier les deux parcours Gradio.
- Afficher clairement le mode `live` ou `precomputed`.
- Ajouter le téléchargement du rapport JSON sans persistance durable.

### Priorité 3 — Docker

Créer :

- `Dockerfile` multi-stage ;
- `compose.yaml` ;
- service `app` ;
- profil `ollama` ;
- service d'initialisation/pull du modèle Ollama ;
- volume réservé aux modèles Ollama ;
- healthchecks ;
- répertoire temporaire non persistant ;
- limites CPU/mémoire raisonnables ;
- `Makefile`.

Commandes attendues :

```bash
docker compose up --build
docker compose --profile ollama up --build
make test
make compose-groq
make compose-ollama
```

### Priorité 4 — Tests

Créer au minimum :

- tests unitaires des regex ;
- tests des citations ;
- tests de consolidation ;
- tests PEACE-7 et OBSAPA ;
- tests de configuration des providers ;
- providers HTTP simulés ;
- tests des limites PDF ;
- tests des PDF chiffrés/illisibles ;
- tests de suppression des temporaires ;
- tests des huit scénarios ;
- tests des endpoints FastAPI ;
- smoke test Gradio ;
- smoke test Docker ;
- tests OCR complets marqués `ocr` ;
- tests live Groq marqués `live` et jamais lancés automatiquement sur une PR.

### Priorité 5 — CI/CD

Créer :

- `.github/workflows/ci.yml` ;
- `.github/workflows/privacy.yml` ;
- `.github/workflows/deploy-hf.yml` ;
- configuration pre-commit ;
- scan Gitleaks ;
- `pip-audit` ;
- Ruff ;
- Pyright ;
- pytest avec couverture ;
- build et smoke test Docker.

Le déploiement Hugging Face doit rester conditionnel tant qu'un Space Docker/Gradio gratuit
n'est pas confirmé pour le compte.

### Priorité 6 — Documentation

Créer :

- `README.md` orienté recruteur ;
- `docs/architecture.md` ;
- `docs/methodology.md` ;
- `docs/data-card.md` ;
- `docs/model-card.md` ;
- `docs/real-results.md` ;
- `docs/limitations.md` ;
- licence Apache-2.0.

## 8. État logique des tâches

- `bootstrap-repo` : terminé.
- `implement-pipeline` : implémentation initiale terminée, validation restante.
- `add-providers` : implémentation initiale terminée, validation restante.
- `build-api-ui` : en cours, non testé.
- `create-synthetic-data` : non commencé ; le patch du générateur a été interrompu.
- `containerize-local` : non commencé.
- `setup-quality-cicd` : non commencé.
- `document-portfolio` : non commencé, hors ce document de passation.

## 9. Première séquence recommandée dans le nouveau chat

```bash
cd /Users/cartelgouabou/Downloads/clinical-trial-screening-demo
git status --short
uv python install 3.12
uv lock
uv sync --extra dev
uv run ruff check .
uv run pyright
```

Ensuite :

1. corriger les erreurs statiques ;
2. recréer le générateur synthétique ;
3. générer les huit dossiers ;
4. lancer les tests du pipeline sans docTR ;
5. installer l'extra OCR et tester un seul PDF ;
6. stabiliser l'API et Gradio ;
7. ajouter Docker ;
8. ajouter CI/CD et documentation ;
9. créer le premier commit seulement quand les scans de confidentialité sont verts.

## 10. Prompt conseillé pour le nouveau chat

```text
Travaille dans le dépôt clinical-trial-screening-demo.
Commence par lire HANDOFF.md en entier et inspecter l'état Git.
Reprends l'implémentation à partir de la section « Première séquence recommandée ».
Respecte strictement les contraintes de confidentialité : aucune donnée ni code du dépôt ICB.
Poursuis jusqu'à avoir généré les huit scénarios synthétiques, stabilisé FastAPI/Gradio,
ajouté Docker Compose Groq/Ollama, les tests, la CI/CD et la documentation.
Vérifie chaque étape et mets à jour HANDOFF.md si une nouvelle passation devient nécessaire.
```

## 11. Mise à jour après reprise — 20 septembre 2026

Le plan de reprise a été implémenté :

- environnement Python 3.12 verrouillé dans `uv.lock`;
- import FastAPI et construction Gradio validés avec les versions verrouillées;
- règles ternaires rendues conservatrices pour les critères/exclusions inconnus;
- sous-stades T/N/M, notation Gleason, négations et unités principales corrigés;
- docTR partagé par processus et rendu texte corrigé;
- fallback limité aux erreurs OCR/provider, avec mode precomputed direct;
- precomputed refusé pour les uploads inédits et texte libre désactivé en mode public;
- huit scénarios synthétiques, 32 PDF image-only, rapports attendus et registre générés;
- API et interface testées, dont un parcours Gradio dans le navigateur;
- Dockerfile, Compose Groq/Ollama, Makefile, CI, confidentialité et déploiement HF conditionnel;
- documentation portfolio et licence Apache-2.0.

Validation locale obtenue :

- Ruff : vert;
- Pyright : vert;
- build sdist et wheel : vert;
- pytest hors `ocr`/`live` : 51 tests, couverture 79,90 %;
- test docTR réel sur un PDF image-only : vert;
- mesure docTR à froid : 36,97 s et environ 1,73 Gio de RSS maximale sur macOS ARM64;
- `pip-audit` : aucune vulnérabilité connue après mise à jour de pytest vers 9.0.3+.

Point externe restant : le build Docker local n'a pas atteint la compilation, le daemon
étant resté bloqué sur la récupération des métadonnées Docker Hub/GHCR. La configuration
Compose est valide; relancer le build lorsque l'accès aux registres est disponible.

Gitleaks est configuré dans pre-commit et dans le workflow `privacy.yml`. Le binaire local
n'était pas installé; le scan effectif sera exécuté par la CI ou localement après installation.
