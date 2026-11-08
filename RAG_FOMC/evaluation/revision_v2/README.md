# Version 2 des preuves : mode d'emploi

Cette version consolide les annotations des 200 questions. Elle ne remplace pas `evaluation/questions.jsonl`, dont la validation humaine initiale et les résultats v1 sont conservés. Les nouveaux objets portent `validated: false` : les ajouts ont été relus par l'assistant, sans prétendre à une nouvelle validation humaine.

## Ce qui a été fait

- Recherche dans tous les paragraphes et chunks des documents sources, en complément de l'union des candidats BM25, Dense et RRF.
- Lecture de 186 extraits candidats factuels. Les citations de décision adoptée et de directive d'exécution sont distinguées des avis des participants ; 20 extraits contextuels ne sont pas ajoutés comme preuves autonomes, et un fragment reste à vérifier.
- Ajouts pour 89 questions ; 222 liens supplémentaires question/groupe/chunk. Les 221 variantes de source (initiales et alternatives) ont été contrôlées dans les paragraphes et chunks, puis sur 166 pages physiques PDF. Les nombres de variantes, de liens et de pages ne désignent pas le même objet.
- Réutilisation des mêmes groupes pour les reformulations et pour les comparaisons qui utilisent ces faits ; aucun groupe supplémentaire n'est créé pour une simple variante.
- Conservation des questions, réponses initiales, familles, lots et preuves initiales. Les 40 explicatives sont recherchées par correspondance littérale/normalisée de leur preuve ; aucune équivalence causale approximative n'est ajoutée automatiquement.
- Recalcul des métriques sur les classements historiques, inchangés. Il ne s'agit ni d'un nouveau moteur ni d'un nouveau test indépendant.

## Où relire

1. Ouvrir [RELECTURE.md](RELECTURE.md) : les 200 questions, groupes, citations, chunks ajoutés et liens PDF sont présentés ensemble.
2. Vérifier les ajouts en lisant le contexte complet. Une bonne date ou une valeur identique ne suffit pas. Pour les chiffres économiques, contrôler aussi le mois de l'observation et la population concernée ; pour les taux, distinguer décision, proposition et projection.
3. Consulter `candidate_decisions.jsonl` pour les motifs, et `source_provenance.jsonl` pour la source de chaque variante.
4. Examiner les candidats restants dans `pool_blind.jsonl`. Ce fichier masque méthode et rang ; `pool_method_key.jsonl` conserve la correspondance pour l'analyse ultérieure. Les passages ne sont pas automatiquement rejetés parce qu'ils sont absents de la liste acceptée ou issus d'un autre document.
5. Les 10 questions sans réponse nécessitent une recherche d'absence à l'échelle du corpus ; les résultats des moteurs ne constituent pas une preuve d'absence.

Le pool contient 7 108 couples question/passage : 319 acceptés par les preuves consolidées, 1 255 candidats du même document à examiner, 5 167 candidats d'autres documents non jugés et 367 candidats liés aux questions sans réponse. Ces états décrivent l'avancement de la revue, pas des étiquettes de non-pertinence certifiées.

## Résultats recalculés

Ouvrir [le rapport avant/après](../../results/comparison_200_v2_rescored/RAPPORT.md), puis `test/summary.csv` et les images dans `test/plots/`.

Sur les 145 questions répondables du test, toutes les preuves annotées sont retrouvées pour 128 questions avec BM25, 115 avec RRF et 86 avec E5. Ce sont des résultats exploratoires avec un corrigé révisé, en attente de confirmation indépendante.

Le Recall par chunks peut baisser après une extension du corrigé : le nombre total de chunks acceptés augmente. La complétude par groupes évite d'exiger toutes les copies de la même preuve. Ne pas interpréter une différence v1/v2 comme un gain ou une dégradation de l'algorithme.

## Reproduire les étapes

Depuis la racine du projet :

```powershell
# Reconstruire la version annotée par l'assistant à partir du catalogue relu
.\.venv\Scripts\python.exe scripts/consolidate_evidence.py build

# Recalculer les scores si le dossier de sortie n'existe pas encore
.\.venv\Scripts\python.exe scripts/rescore_evidence_revision.py

# Régénérer les figures, sans recharger E5
.\.venv\Scripts\python.exe scripts/plot_comparison.py --results results/comparison_200_v2_rescored/test --questions evaluation/revision_v2/questions_consolidated.jsonl

# Vérifier la cohérence et la préservation de v1
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Le script de recalcul refuse un dossier existant. Les décisions s'appliquent à une empreinte précise du catalogue : si les textes sources changent, il faut refaire leur revue et non réutiliser les mêmes décisions par numéro.

La commande de benchmark `compare` garde son contrôle de validation humaine et n'est pas assouplie pour ces brouillons révisés. Une promotion ultérieure doit enregistrer la revue, sa date, sa portée et les nouvelles empreintes. Toute optimisation future doit utiliser le développement et une confirmation distincte du test historique déjà observé.
