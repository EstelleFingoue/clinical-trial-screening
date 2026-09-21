# Mesure OCR CPU

Mesure locale du 20 septembre 2026 sur macOS ARM64, Python 3.12.13,
python-doctr 1.1.0, avec un PDF synthétique image-only d'une page :

- test : `pytest -m ocr tests/ocr/test_doctr_smoke.py`;
- temps total à froid : 36,97 s;
- mémoire résidente maximale rapportée par `/usr/bin/time -l` : environ 1,73 Gio;
- résultat : texte OCR non vide, test réussi.

Cette mesure inclut le chargement des modèles et ne constitue pas un benchmark
de débit. Elle indique néanmoins qu'un hébergement CPU gratuit à faible mémoire
peut être lent ou insuffisant. Le déploiement Hugging Face reste donc
conditionnel et le conteneur conserve un seul worker.
