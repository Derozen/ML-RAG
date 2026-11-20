# Vérifications techniques et statut du test final

## Validation utilisateur enregistrée

L’utilisateur a accepté globalement les **294 grades proposés**, sans changement de grade. Les champs de la grille et la trace de cet accord sont enregistrés dans [user_approval.json](../data/holdout_candidate/assistant_review/completed_proposal/user_approval.json). Les scores calculés restent numériquement valables pour ces annotations acceptées.

Cet accord global ne déclare ni une lecture indépendante page par page, ni la revue sémantique des 145 questions antérieures, ni l’adjudication des réponses et facettes. Ces décisions restent non renseignées. Le statut de test final indépendant n’est donc pas établi. Le [statut retenu pour la remise](STATUT_HOLDOUT.md) est une évaluation complémentaire descriptive, sans conclusion confirmatoire.


Les essais ci-dessous portent sur le code figé et des questions dev déjà explorées. Ils ne constituent pas une nouvelle évaluation indépendante de qualité.

| Contrôle | Observation |
|---|---|
| Tests automatisés | 25 tests de régression réussis pendant cette revue. Ils ne couvrent pas tous les comportements possibles. |
| Recalcul indépendant des métriques | passed : 3480 contextes, budgets 5/6, 24 synthèses ; tolérance 10⁻¹². |
| Syntaxe Python | 29 fichiers examinés lors de l’essai applicatif. |
| Démarrage Streamlit par AppTest | Réussi |
| Question vide | Réussi |
| Recherche réelle RRF + ColBERT, top-6 | Réussi ; identifiants des passages identiques au benchmark existant. |
| Recherche réelle RRF + ColBERT, top-5 | Réussi ; identifiants des passages identiques au benchmark existant. |
| Panneau de scores détaillés | Réussi |
| Repli du mode temporel en l’absence de période | Réussi |
| Serveur HTTP local réel | HTTP 200 sur la page et santé `ok` ; serveur temporaire arrêté après contrôle. |
| Génération Qwen structurée réelle | Réussie sur FOMC_035 (dev), sortie conservée ; justesse sémantique non certifiée. |
| Rendu visuel de Streamlit dans tous les navigateurs | Non vérifié. AppTest et HTTP ne remplacent pas une inspection graphique du navigateur. |
| Autres chemins applicatifs | Les modes temporels valides sur plusieurs dates et toutes les configurations en ligne ne sont pas testés exhaustivement. |
| Test final indépendant des 20 questions | **Non exécuté.** Les propositions de qrels ne sont pas encore validées indépendamment. |

## Chargement de Qwen et démonstration

Un premier essai complet a échoué après le délai de 300 secondes : les journaux Ollama situaient le blocage pendant le chargement du modèle. L’application a affiché cette erreur et préservé le précédent résultat. La trace est conservée dans `results/delivery_verification/attempts/cold_generation_timeout.json`.

Un préchargement sans prompt ni génération a ensuite réussi en **184.0 secondes**. Il utilise le même modèle et ne change ni poids ni paramètres du pipeline. Le démarrage à froid reste une limite opérationnelle : précharger le modèle avant la démonstration.

La chaîne a ensuite été essayée de nouveau avec le modèle chargé. Ce succès valide un cas fonctionnel de génération, pas la fidélité de toutes les réponses. Les identifiants de citations et les sections structurées ne constituent pas une preuve automatique d’implication sémantique.

[Sortie réelle de génération](../results/delivery_verification/real_generation_dev.json)

### Limites observées dans cette réponse

La revue éditoriale de la sortie FOMC_035 constate une réponse **partielle** : elle mentionne l’inflation mais omet le marché du travail solide, pourtant explicitement présent dans la source 1 de janvier 2022. Elle cite aussi les sources 5 et 6, de décembre et juillet 2022. Ces réunions ultérieures ne suffisent pas à justifier ce que pensait le Comité en janvier.

Les contrôles retournent des identifiants de citations valides et une section structurellement complète, mais **cela ne valide pas la pertinence temporelle ni la complétude de la réponse**. Le mode classique ne doit pas être présenté comme ayant résolu ces problèmes. Le pipeline figé n’a pas été modifié pendant cette vérification.

[Revue et réponse manuelle proposée, distincte de la sortie du modèle](../results/delivery_verification/generation_semantic_review.json)

Une correction des règles de génération ou de citations devra être développée sur dev et déclarée comme une nouvelle version. Le verrou existant doit rester l’historique du système réellement comparé.

## Pourquoi le test final attend

Le dernier contrôle de la grille consolidée indique **0 jugements de pages sans grade humain/relecteur** et **0/20 décisions par question complètes**. L’accord global de l’utilisateur accepte les grades, sans attester les décisions sémantiques par question. La recherche par fragments ne prouve ni l’exhaustivité des qrels ni la nouveauté sémantique par rapport aux 145 anciennes questions.

La mesure complémentaire réalisée reste provisoire et ne peut pas être annoncée comme un test final indépendant validé. Le contrôle conserve donc le statut `annotation_pending`. Les données historiques, les modèles, paramètres et index restent figés.

## Graphiques et reproduction

[Les cinq figures de comparaison](../results/figures/INDEX.md) ont été générées en PNG/SVG et inspectées visuellement. Les figures globales portent sur les 145 questions exploratoires ; celle par type porte uniquement sur les 85 dev. Elles ne donnent pas les scores du nouveau lot.

Les commandes pour reproduire les contrôles et précharger Ollama sont dans le [README](../README.md). Les résultats JSON et les identifiants des passages examinés sont conservés dans `results/delivery_verification/`. La vérification du verrou a réussi avant et après les essais terminés.

La conformité complète n’est pas revendiquée : restent la validation indépendante, la relecture et mise en forme académique du rapport, les diapositives, la vidéo et la validation du paquet de reproduction sur le poste de présentation. La consigne générale entraînement/validation/test est adaptée et justifiée pour ce système sans entraînement supervisé local, pas présentée comme suivie littéralement.


## Mesure provisoire supplémentaire des 20 questions

[Scores et graphique](../results/candidate_provisional/20261120T151147Z/RAPPORT.md) : 12 configurations, budgets 5/6. Les grades initialement proposés par l’assistant ont été acceptés globalement par l’utilisateur. L’indépendance du lot et la génération ne sont pas validées par ce calcul. Le lot a désormais été exposé aux scores ; une correction guidée par ceux-ci nécessitera une autre confirmation.


## Reproduction isolée et dossier de remise

[Reproduction : exécutions, journaux et limites](REPRODUCTION.md). Une copie isolée avec poids/dépendances réutilisés ne constitue pas une installation vierge. [Plan de finalisation et preuves](FINALISATION.md).
