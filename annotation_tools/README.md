# Préparation du lot candidat V2 — hors pipeline figé

## Dossier consolidé à utiliser désormais

La **préannotation proposée des 294 couples est complète**. Le point d'entrée est
[ce rapport](../data/holdout_candidate/assistant_review/completed_proposal/RAPPORT.md).
Le dossier `assistant_review/completed_proposal/` rassemble une seule grille à
relire, les preuves et les qrels proposés. Les versions initiale et intermédiaire
sont conservées pour la traçabilité ; ce ne sont pas des systèmes RAG différents.

**La complétude des grades proposés ne signifie pas validation humaine ni
exhaustivité des qrels.** Les grades négatifs de la dernière passe proviennent
d'un examen des débuts de paragraphes et des phrases thématiques, non d'une
lecture humaine exhaustive. Leur confirmation sur les pages complètes reste
requise. Les réponses et l'indépendance sémantique restent aussi à adjuger.

```powershell
.\.venv\Scripts\python.exe annotation_tools/complete_editorial_proposal.py
.\.venv\Scripts\python.exe annotation_tools/check_review.py --page-review data/holdout_candidate/assistant_review/completed_proposal/human_review.csv
```

Le premier script contrôle les citations nouvelles dans les PDF, le gel et la
couverture exacte des 294 couples. Il refuse d'écraser des annotations humaines
déjà saisies dans sa grille. Le second vérifie cette grille consolidée et les
décisions par question dans `data/holdout_candidate/question_adjudication.csv`.
Le code de sortie 2 est attendu tant que la revue humaine n'est pas complétée.
Les qrels proposés ne doivent pas être traités comme des qrels finaux approuvés.

`remaining_minutes_decisions.json` conserve les 175 décisions de la dernière
passe, avec leurs motifs. `inspect_remaining_pages.py` reproduit l'inspection
structurée utilisée pour repérer les pages à approfondir ; ce n'est ni un modèle
de récupération évalué, ni une preuve automatique de non-pertinence.

## Complément éditorial : preuves supplémentaires

[Rapport du complément](../data/holdout_candidate/assistant_review/round_2/RAPPORT.md).
Les décisions explicites sont dans `supplemental_editorial_decisions.json`.
`publish_editorial_supplement.py` vérifie leurs citations dans les PDF physiques
et produit une fusion **proposée**, séparée des annotations humaines et des qrels
initiaux. Les pages restantes restent non jugées ; leur grade n'est jamais déduit
de l'absence de mots-clés. Une révision de grade déclare obligatoirement son
ancien grade. Les fichiers de référence et les grilles restent inchangés.

```powershell
.\.venv\Scripts\python.exe annotation_tools/publish_editorial_supplement.py
```

Ce complément n'est ni un test final approuvé, ni une certification de nouveauté
sémantique. La préannotation par modèle local a été abandonnée avant toute sortie
exploitable ; ses scripts expérimentaux sont archivés hors du code actif.

## Suite de la revue : dossiers de lecture et contrôle

Ouvrir d’abord [l’index des 20 dossiers](../data/holdout_candidate/review_packets/INDEX.md).
Chaque dossier contient le texte de **toutes** les pages des documents demandés,
les propositions de preuves et les anciennes questions proches. Les 145 anciennes
questions sont également regroupées dans un fichier de lecture. Les dossiers
contiennent les réponses : ils sont réservés aux annotateurs.

```powershell
.\.venv\Scripts\python.exe annotation_tools/prepare_review.py
.\.venv\Scripts\python.exe annotation_tools/check_review.py
```

La préparation préserve les grilles existantes. Renseigner `human_review.csv`
(294 couples, y compris les 64 propositions à confirmer), puis
`question_adjudication.csv` (20 décisions sur la nouveauté, les réponses et les
facettes). Consigner les recouvrements identifiés dans `semantic_pairs_145.csv` ;
le verdict `distinct` désigne une paire jugée différente. Les autres verdicts
non vides bloquent le contrôle jusqu’à résolution documentée. La déclaration de
lecture des 145 anciennes questions ne peut pas être déduite d’un score lexical.

Le contrôle produit `review_readiness.json`. Le code de sortie **2 est attendu**
tant que la revue est incomplète. Il vérifie aussi le gel et la présence de toutes
les pages attendues. Même une grille complète donne seulement le statut
`ready_for_release_review` : elle doit ensuite être versionnée et ses désaccords
résolus avant la mesure finale. Ce contrôle ne certifie ni l’identité du relecteur,
ni la vérité de ses jugements, ni une indépendance statistique absolue.

Les grilles humaines ne sont jamais remplies automatiquement. Aucune exécution de
ces deux outils ne calcule de métriques ou n’interroge les modèles.

Ces outils préparent des annotations. Ils ne calculent aucun score de performance des modèles et ne modifient aucun fichier de `src/`, `app/`, des index ou des 145 questions exploratoires. Les empreintes du protocole sont vérifiées avant la préparation et pendant la validation.

- `holdout_v2_plan.json` : questions, périmètres de sources, facettes attendues et revue éditoriale des anciennes questions liées.
- `editorial_page_review.json` : 28 décisions motivées sur des pages complémentaires ou des distracteurs, proposées par l’assistant ; ce n’est pas une seconde annotation humaine indépendante.
- `rejected_questions.json` : proposition retirée par prudence et raison de son remplacement.
- `rebuild_holdout.py` : construit les questions, qrels proposés, extraits, grilles de revue et dossiers de contrôle.
- `validate_holdout.py` : vérifie les identifiants, grades, provenance, fragments directement dans les PDF, séparation questions/réponses et cohérence des fichiers.

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe annotation_tools/validate_holdout.py
```

La validation technique ne donne pas le statut « test final ». La V2 comprend 20 questions, 53 jugements positifs proposés et 11 jugements de non-pertinence motivés. Parmi les 294 couples question/page des documents explicitement demandés, 230 restent non jugés. Un écran a parcouru toutes les 838 pages pour chaque question ; cette recherche par fragments ne remplace pas la lecture sémantique exhaustive et peut manquer des paraphrases pertinentes. Les pages hors périmètre ne sont pas automatiquement déclarées non pertinentes dans l’absolu.

La revue sémantique compare les informations demandées et réponses attendues, avec des cas liés explicités. Les 2 900 paires nouvelles/anciennes sont disponibles pour la seconde lecture. Ni la similarité de chaînes, ni une date différente, ni une absence de mots-clés ne prouvent l’indépendance sémantique. Les sources communes rendent certains exemples corrélés.

La grille `data/holdout_candidate/human_review.csv` attend un grade humain 0/1/2 et un relecteur, notamment pour les pages non jugées. `semantic_pairs_145.csv` permet d’inscrire un verdict humain d’équivalence. Les questions 014, 019 et 020 méritent une attention accrue ; les questions 017 et 018 partagent une famille documentaire mais portent sur des résolutions ou informations différentes et doivent rester dans le même lot.

Après relecture, résoudre les désaccords, compléter les qrels, retirer/remplacer tout doublon substantiel, archiver une version approuvée et ses empreintes. Seulement alors, évaluer une fois les fonctions figées, en leur donnant exclusivement le texte de la question. Les réponses de `question_gold.jsonl` et les extraits ne doivent jamais être transmis au récupérateur ou au générateur pour cette mesure. Toute modification du système fondée sur les nouveaux résultats exige un autre jeu de confirmation.

`rebuild_holdout.py` refuse d’écraser une grille où un grade ou un relecteur humain a déjà été renseigné. Une régénération doit passer par une version archivée, sans effacer la trace des décisions.
