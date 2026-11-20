# Décision sur le lot de 20 questions

## Statut retenu pour la remise

Le lot est une **évaluation complémentaire à scores provisoires**, avec
**294 grades acceptés globalement par l’utilisateur**, après le calcul des scores.
Il n’est pas présenté comme un test final indépendant et validé. Cette décision
permet de terminer le rapport de comparaison en conservant des conclusions
descriptives et des limites explicites.

- Les 145 questions et leurs résultats restent exploratoires.
- Les 20 questions ont été évaluées avec les mêmes modèles, paramètres et index
  figés ; aucune optimisation n’a été effectuée à partir de cette mesure.
- L’accord global est conservé dans
  [user_approval.json](../data/holdout_candidate/assistant_review/completed_proposal/user_approval.json).
  Les 294 grades ont été acceptés sans changement ; les scores restent identiques.
- La relecture indépendante page par page, la nouveauté par rapport aux 145
  questions et l’adjudication des réponses/facettes n’ont pas été attestées par
  cet accord. Les décisions par question restent vides ; elles ne sont pas
  complétées automatiquement.

## Faut-il un nouveau test indépendant ?

**Oui pour une conclusion confirmatoire**, notamment si une nouvelle version du
système est choisie ou corrigée à partir des résultats des 20 questions.
**Ce n’est pas nécessaire pour présenter honnêtement la comparaison descriptive
actuelle**, avec son statut exploratoire/provisoire et ses limites.

Une validation postérieure des réponses et des références peut renforcer la
qualité des annotations de ce lot. Elle ne transforme pas rétroactivement les
résultats déjà consultés en une épreuve réalisée à l’aveugle. Une future confirmation
devra fixer questions, qrels approuvés, familles de questions et pipeline avant le
calcul, puis conserver les résultats sans réglage fondé sur ce test.

## Interprétation des nouveaux scores

À six chunks, Dense E5 + cross-encoder obtient le meilleur nDCG pages@6 observé
(0,521), devant RRF + cross-encoder (0,520). Le système RRF + ColBERT retenu avant
cette mesure obtient 0,506 et la meilleure couverture moyenne des pages annotées
(55,7 %). Ces critères mesurent des aspects différents ; aucune combinaison
n’est proclamée supérieure statistiquement à partir de ces seuls nombres.

[Résultats, graphique et provenance](../results/candidate_provisional/INDEX.md).
La qualité des réponses du générateur reste une évaluation distincte.
