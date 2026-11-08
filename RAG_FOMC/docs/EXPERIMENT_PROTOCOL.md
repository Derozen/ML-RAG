# Protocole de comparaison de la récupération

**Mise à jour du 8 novembre 2026 :** voir la [revue méthodologique à partir des cours ECC](REVUE_METHODOLOGIQUE_COURS_ECC.md). La baseline a été exécutée à paramètres fixés, sans recherche systématique d’hyperparamètres. Le test historique a déjà été observé et ne peut servir de confirmation indépendante de nouvelles modifications. Un cas de preuve alternative non annotée a été confirmé ; consolider les jugements de pertinence avant une conclusion générale. La commande `compare` exige aussi `questions_sha256` dans `evaluation/annotations.json` pour vérifier la version validée des questions.

## Objectif et hypothèses

Mesurer la capacité de BM25, du dense E5 et de leur fusion RRF à retrouver des preuves pertinentes sur une collection commune de passages. Une hypothèse de départ est que BM25 bénéficie des formulations et chiffres explicites, le dense des reformulations et RRF de leur complémentarité. Ce sont des hypothèses à tester, pas des conclusions.

Le cadre compare des candidats. Il ne mesure ni la qualité d’une réponse générée, ni l’apport d’un reranker.

## Pilote puis expérience principale

1. Contrôler trois comptes rendus de réunions différentes et l’inventaire officiel.
2. Relire pour chaque document le début, le milieu, la fin, un chiffre et une négation ; contrôler les tableaux et colonnes PDF.
3. Contrôler les passages voisins, leurs sources et les statistiques de tailles.
4. Préparer dix questions anglaises avec preuves, dont une comparative et une sans réponse si le corpus le permet.
5. Faire une revue croisée : une personne annote, l’autre cherche les preuves sans consulter le corrigé.
6. Exécuter les trois méthodes et vérifier manuellement où apparaissent les preuves.
7. Étendre ensuite au corpus complet. Réconcilier le nombre annoncé de 56 rapports avec les comptes par année et les documents communs.

Une cible de 200 questions, 50 développement et 150 test, reste conditionnée à la capacité de validation humaine. Répartir les années et types ; garder une même famille de reformulations dans un seul lot. Le code vérifie les familles mais ne remplace pas la revue de la répartition. Il ne génère aucune question artificiellement étiquetée comme validée.

## Conditions constantes

Même corpus, même découpage, mêmes métadonnées, mêmes questions et même K pour toutes les stratégies. Aucune date tirée du corrigé ne filtre les documents. Les scores égaux sont départagés par ID canonique. Les paramètres sont choisis sur dev puis figés avant test. Archiver la configuration, les annotations, leurs empreintes et les résultats dans un nouveau dossier.

Si le découpage change, les IDs peuvent référencer un autre texte. Réannoter ou vérifier les liens puis actualiser l’empreinte des annotations ; ne pas réutiliser aveuglément les anciens qrels.

## Mesures

Pour une question répondable, soit `R` l’union des IDs acceptables et `L_K` les K premiers candidats uniques :

- **Recall@K** = `|R ∩ L_K| / |R|`.
- **MRR@K** : inverse du rang du premier ID pertinent ; zéro s’il est absent.
- **Couverture des preuves** : proportion des groupes requis ayant au moins un ID acceptable dans `L_K`.
- **Complétude** (`all_evidence`) : un si tous les groupes requis sont couverts, zéro sinon.

Le rappel par IDs pénalise l’absence d’une variante acceptable même si une autre variante apporte la même preuve. La couverture par groupes complète donc son interprétation. Deux passages qui se chevauchent pour la réunion A ne compensent pas une preuve manquante de la réunion B.

Exemple fictif : deux preuves attendues, une retrouvée au rang 3. Avec un passage pertinent par groupe, Recall = 0,5 ; MRR = 1/3 ; couverture = 0,5 ; complétude = 0.

Les scores sont calculés par question puis macro-moyennés, sans multiplier artificiellement l’effectif par le nombre de répétitions. `summary.csv` fournit aussi chaque type ; utiliser la ligne `comparative` pour discuter spécifiquement les comparaisons entre réunions.

Les questions sans réponse sont exclues de ces métriques. Leurs candidats sont conservés pour revue ; le moteur de récupération ne possède pas ici de mécanisme de rejet. Un éventuel seuil devra être réglé par méthode sur dev et évalué ensuite séparément sur test, avec faux rejets des questions répondables.

## Latences

Charger les index et le modèle, puis effectuer un échauffement par stratégie. Mesurer avec `perf_counter()` le temps jusqu’à la liste finale, encodage de question inclus. RRF inclut ses deux recherches et la fusion. Répéter sur la même machine et dans les mêmes conditions d’alimentation et de charge ; conserver toutes les mesures, la médiane et le percentile 95. Trois répétitions conviennent au pilote ; davantage et un jeu de questions suffisant stabilisent le p95.

Le temps de construction d’index, incluant ici le chargement du modèle, est consigné séparément dans les métadonnées. Les temps de première exploration ne sont pas ceux du benchmark.

## Comparaisons appariées

`paired_comparisons.csv` donne la moyenne des différences B−A sur les mêmes questions répondables. Le bootstrap rééchantillonne les familles de questions pour conserver ensemble leurs reformulations. Les intervalles à 95 % proviennent de 1000 tirages à graine fixe.

Ces intervalles sont exploratoires : ils ne corrigent pas les comparaisons multiples, sont fragiles sur un petit pilote et ne couvrent pas l’incertitude d’annotation ou le choix du corpus. Un intervalle étroit avec une seule famille n’est pas une preuve solide. Rapporter le nombre de questions et de familles, l’ampleur du gain et les limites plutôt qu’une seule affirmation de significativité.

## Analyse des erreurs et restitution

`review_cases.jsonl` sélectionne de manière déterministe un exemple disponible de succès, d’incomplétude et de divergence. Chaque cas contient la question, la réponse de référence, les citations attendues, leurs rangs et les premiers candidats. La cause n’est pas inférée automatiquement.

Après lecture des originaux, commenter notamment : mauvaise réunion, chiffre similaire, reformulation, défaut d’extraction ou preuve répartie entre passages. Distinguer le constat mesuré de l’explication plausible. Documenter toute correction d’annotation et recalculer les trois méthodes sur la même version.

La restitution comprend l’inventaire, les paramètres figés, les résultats par question et par type, les différences appariées, les latences et les cas d’erreurs. Les classements sourcés forment le livrable destiné au futur composant de reranking.
