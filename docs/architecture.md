# Architecture

L'application suit un pipeline sans persistance documentaire :

1. `PDFSession` valide et copie les PDF dans un répertoire temporaire par requête.
2. un moteur OCR produit des `OCRDocument`;
3. `HybridExtractor` combine regex et fournisseur LLM;
4. les citations LLM sont acceptées uniquement si elles figurent dans le texte;
5. `consolidate` choisit la source prioritaire et expose les conflits;
6. les règles PEACE-7 et OBSAPA produisent une décision ternaire;
7. FastAPI et Gradio rendent le même `PipelineReport`.

Les scénarios intégrés peuvent charger directement un rapport pré-calculé. Un
upload inédit ne peut jamais utiliser ce mode. Groq effectue une inférence
externe; Ollama utilise l'endpoint configuré.

Le conteneur exécute un seul worker afin de ne charger docTR qu'une fois. Les
documents utilisent un `tmpfs`; seul le volume des modèles Ollama est persistant.
