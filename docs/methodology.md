# Méthodologie

Les variables structurées sont extraites par regex lorsqu'une expression
déterministe et une unité claire sont disponibles. Les autres variables sont
demandées en sortie JSON structurée au fournisseur LLM. Chaque valeur LLM doit
être accompagnée d'une citation exacte; une citation absente ou inventée est
rejetée et reste visible dans le rapport.

La consolidation applique l'ordre de priorité documentaire défini dans
`config/variables.yaml`. Des valeurs distinctes deviennent des alternatives et
un conflit sur une variable décisionnelle rend le critère indéterminé.

Les règles de démonstration sont volontairement conservatrices : un critère
obligatoire ou une exclusion non documentée empêche une conclusion
`eligible`. Les critères non automatisables restent dans `human_review`.

Les rapports attendus des scénarios sont générés à partir de définitions
canoniques, puis comparés à des décisions déclarées indépendamment afin
d'éviter un oracle circulaire.
