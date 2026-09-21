# Model card

Le dépôt n'entraîne aucun modèle. Il orchestre :

- docTR pour l'OCR image;
- un endpoint OpenAI-compatible Groq ou Ollama pour l'extraction structurée;
- des regex et règles Python déterministes.

Les noms et versions de modèles sont configurables dans `config/app.yaml`. Une
réponse LLM n'est conservée que si sa citation est vérifiable dans le document.
Le mode `precomputed` rejoue uniquement les scénarios synthétiques intégrés.

Les sorties ne sont pas calibrées comme probabilités et le champ de confiance
décrit la méthode de validation, pas une certitude clinique.

Avant toute utilisation autre qu'une démonstration, il faut valider séparément
l'OCR, l'extraction, les règles, les biais, la sécurité et la conformité
réglementaire.
