# Dossiers de lecture — revue indépendante

Ces dossiers contiennent les réponses proposées : ils sont réservés aux annotateurs.
Ils ne sont jamais des entrées du système évalué. Aucune inférence n’est lancée.

Lire chaque page, puis renseigner `human_review.csv` : `human_grade` (0/1/2), `reviewer`, et `notes` (obligatoire en cas de désaccord avec la proposition).
0 = hors réponse ; 1 = élément partiel ou contexte utile ; 2 = preuve explicite d’au moins une facette demandée. Une page peut ne couvrir qu’une partie d’une question à plusieurs preuves.

Lire les 145 anciennes questions avant de conclure sur la nouveauté. Une similarité lexicale faible ne suffit pas. Comparer aussi les informations demandées et les réponses, consulter les preuves si nécessaire. Consigner les paires problématiques dans `semantic_pairs_145.csv`.

Renseigner ensuite `question_adjudication.csv` : verdict `distinct`, `overlap` ou `uncertain`, `old_questions_reviewed` = 145 après lecture, `answer_verified` et `facets_verified` = yes après vérification, nom du relecteur et justification. Ne pas cocher ces champs par anticipation.

Un désaccord ou une preuve supplémentaire exige une adjudication documentée ; ne pas modifier silencieusement les propositions initiales. L’exhaustivité concerne les documents explicitement demandés, pas toutes les paraphrases possibles dans le corpus. Les 20 questions restent ensemble.

- [HOLDOUT_V2_001](HOLDOUT_V2_001.md) — factual, minutes : 15 pages, dont 14 sans jugement proposé.
- [HOLDOUT_V2_002](HOLDOUT_V2_002.md) — factual, minutes : 11 pages, dont 10 sans jugement proposé.
- [HOLDOUT_V2_003](HOLDOUT_V2_003.md) — factual, statements : 4 pages, dont 3 sans jugement proposé.
- [HOLDOUT_V2_004](HOLDOUT_V2_004.md) — factual, statements : 4 pages, dont 2 sans jugement proposé.
- [HOLDOUT_V2_005](HOLDOUT_V2_005.md) — explanatory, minutes : 12 pages, dont 11 sans jugement proposé.
- [HOLDOUT_V2_006](HOLDOUT_V2_006.md) — explanatory, minutes : 21 pages, dont 20 sans jugement proposé.
- [HOLDOUT_V2_007](HOLDOUT_V2_007.md) — explanatory, statements : 4 pages, dont 3 sans jugement proposé.
- [HOLDOUT_V2_008](HOLDOUT_V2_008.md) — explanatory, statements : 4 pages, dont 3 sans jugement proposé.
- [HOLDOUT_V2_009](HOLDOUT_V2_009.md) — explanatory, mixed : 16 pages, dont 12 sans jugement proposé.
- [HOLDOUT_V2_010](HOLDOUT_V2_010.md) — explanatory, mixed : 22 pages, dont 17 sans jugement proposé.
- [HOLDOUT_V2_011](HOLDOUT_V2_011.md) — comparative, minutes : 24 pages, dont 22 sans jugement proposé.
- [HOLDOUT_V2_012](HOLDOUT_V2_012.md) — comparative, statements : 8 pages, dont 4 sans jugement proposé.
- [HOLDOUT_V2_013](HOLDOUT_V2_013.md) — comparative, statements : 8 pages, dont 5 sans jugement proposé.
- [HOLDOUT_V2_014](HOLDOUT_V2_014.md) — comparative, mixed : 29 pages, dont 21 sans jugement proposé.
- [HOLDOUT_V2_015](HOLDOUT_V2_015.md) — comparative, mixed : 21 pages, dont 15 sans jugement proposé.
- [HOLDOUT_V2_016](HOLDOUT_V2_016.md) — multi_evidence, minutes : 12 pages, dont 10 sans jugement proposé.
- [HOLDOUT_V2_017](HOLDOUT_V2_017.md) — multi_evidence, mixed : 20 pages, dont 16 sans jugement proposé.
- [HOLDOUT_V2_018](HOLDOUT_V2_018.md) — multi_evidence, mixed : 24 pages, dont 15 sans jugement proposé.
- [HOLDOUT_V2_019](HOLDOUT_V2_019.md) — multi_evidence, mixed : 20 pages, dont 18 sans jugement proposé.
- [HOLDOUT_V2_020](HOLDOUT_V2_020.md) — multi_evidence, mixed : 15 pages, dont 9 sans jugement proposé.
