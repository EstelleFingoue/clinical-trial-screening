# Data card

## Nature

Le jeu contient exactement huit profils entièrement synthétiques, quatre types
de documents image-only par profil et aucune donnée issue d'un patient réel.
Les identifiants et textes sont générés par `scripts/generate_demo_data.py`
avec une graine versionnée.

## Distribution

- 2 profils éligibles PEACE-7 et non éligibles OBSAPA;
- 2 profils éligibles OBSAPA et non éligibles PEACE-7;
- 2 profils indéterminables pour les deux essais;
- 2 profils non éligibles pour les deux essais.

`demo_data/manifest.json` porte `synthetic_only: true`, les hashes, tailles,
nombres de pages et l'indicateur image-only.

## Usages

Le jeu sert aux démonstrations, tests fonctionnels et contrôles de régression.
Il ne mesure ni performance clinique, ni généralisation, ni biais sur une
population réelle.

## Limites

La langue, la mise en page et les formulations sont volontairement bornées.
Les PDF ne reproduisent pas toute la variabilité documentaire hospitalière.
