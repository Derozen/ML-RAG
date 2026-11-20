# Scores provisoires des 20 questions candidates

**Mise à jour :** les 294 grades ont été acceptés globalement par l’utilisateur
dans la conversation, sans modification. [Trace de l’accord](../../data/holdout_candidate/assistant_review/completed_proposal/user_approval.json).
Les scores sont inchangés. La revue sémantique et l’adjudication des réponses
restent distinctes ; cet accord ne prouve pas l’indépendance du lot.
Le rapport de run ci-dessous conserve le statut historique au moment du calcul.

Exécution du 20 novembre 2026 :

- [Rapport, tableau des 12 configurations et graphique](20261120T151147Z/RAPPORT.md).
- [Comparaison CSV, budgets 5 et 6](20261120T151147Z/comparison.csv).
- [Scores par question](20261120T151147Z/metrics_per_question.csv).
- [Recalcul séparé : 480 contextes et 24 synthèses contrôlés](20261120T151147Z/independent_recalculation.json).
- [Provenance et empreintes du run](20261120T151147Z/run.json).

Les qrels sont des propositions de l’assistant, pas des annotations humaines
approuvées. Ces scores ne constituent pas un test final indépendant validé.
Le lot est désormais exposé aux performances ; aucun réglage n’a été effectué
à partir de ce calcul. Les scores de génération ne sont pas évalués ici.

À six chunks, le meilleur nDCG pages@6 observé est Dense + cross-encoder (0,521),
suivi de RRF + cross-encoder (0,520). Le système RRF + ColBERT choisi avant cette
mesure obtient 0,506. Ces écarts ne démontrent pas une supériorité statistique.
