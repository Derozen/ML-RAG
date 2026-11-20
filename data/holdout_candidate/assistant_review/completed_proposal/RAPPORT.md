# Préannotation des 20 questions — dossier consolidé

**Statut : préannotation proposée complète, validation indépendante à effectuer.**

Les **294/294 couples question/page** ont maintenant un grade
proposé. Il ne reste aucun grade proposé vide dans ce dossier :
**78 pages positives** et
**216 pages proposées non pertinentes**.
Les 20 questions et les 38 facettes attendues conservent leurs références positives.
Il s'agit d'une couverture des documents explicitement demandés par les questions,
pas d'une affirmation d'exhaustivité des réponses possibles dans tout le corpus.

## Méthode et limites

Le dernier passage couvre les 175 couples encore ouverts après la deuxième passe.
Un examen structuré des débuts de paragraphes et des phrases thématiques a servi
à proposer les grades négatifs. Les pages susceptibles d'ajouter un soutien
positif ont fait l'objet d'une lecture ciblée de leur texte complet ;
15 citations supplémentaires ont été contrôlées dans les PDF physiques.
**Les grades 0 de cette passe ne certifient donc pas une absence de réponse après
lecture humaine exhaustive.** Ils doivent être confirmés sur la page complète.
La présence d'un nom, d'un chiffre ou d'un thème ne suffit pas : date, période,
auteur et résolution doivent correspondre à ce qui est demandé.

Grade 2 : preuve explicite d'au moins une facette nécessaire. Grade 1 : preuve
partielle ou contexte directement utile, sans lui attribuer les éléments manquants.
Grade 0 : proposition de non-pertinence pour la question précise, avec raison.
La frontière entre contexte utile et simple proximité thématique doit être
harmonisée par adjudication, notamment pour la révision 0 → 1 de la question 018.

## Fichiers à utiliser pour la validation

Les [20 dossiers de lecture](../../review_packets/INDEX.md) donnent accès aux pages
et aux anciennes questions proches. Leurs mentions de grades décrivent la première
proposition ; utiliser les grades du présent CSV consolidé pour cette revue.

- **human_review.csv** : grille consolidée de 294 propositions ; renseigner
  `human_grade`, `reviewer`, et `notes` en cas de désaccord. Les colonnes de
  l'assistant ne constituent jamais des jugements humains.
- **evidence_proposed.jsonl** : motifs et citations réunis en un seul fichier.
- **qrels_PAGES_proposed.trec** : qrels proposés pour revue, pas qrels finaux approuvés.
- **decisions_last_pass.jsonl** : trace des 175 décisions de cette passe.
- **report.json** : statut, limites et empreintes permettant de reproduire le dossier.

Le contrôle de la grille consolidée s'exécute depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe annotation_tools/check_review.py --page-review data/holdout_candidate/assistant_review/completed_proposal/human_review.csv
```

Le code de sortie 2 indique que les jugements humains restent à compléter ; il
ne signale pas un échec du pipeline. Les décisions sur la nouveauté et les réponses
se renseignent dans `data/holdout_candidate/question_adjudication.csv`.

Les fichiers initiaux et les propositions intermédiaires sont conservés comme
historique. Le `validation_report.json` à la racine concerne la proposition initiale ;
le présent `report.json` décrit cette consolidation. Les grilles humaines initiales
ne sont pas remplies automatiquement et ne sont pas écrasées.

## Indépendance et utilisation des résultats

Les 145 anciennes questions restent exploratoires. Les 85 questions de développement
servent aux diagnostics ; les autres questions déjà consultées ne sont pas un test neuf.
Le pipeline est toujours figé : **RRF + ColBERT, 20 candidats puis 6 passages**.
Cette annotation n'utilise aucun résultat de récupération/reranking des 20 questions.
Le modèle local essayé auparavant n'a fourni aucun jugement exploitable utilisé ici.

La revue de nouveauté sémantique reste à confirmer, particulièrement pour 014, 019
et 020. La création des questions et leur revue par le même assistant ne constituent
pas deux annotations indépendantes. Les questions 017/018 restent dans le même lot.
Il ne faut pas annoncer un test final indépendant simplement parce que les grades
proposés sont complets. Aucun entraînement supervisé local n'était nécessaire avec
les modèles préentraînés utilisés ; absence d'entraînement ne signifie pas absence
de risque de fuite lors des choix de paramètres ou de l'évaluation.

Après confirmation des grades, des réponses et de la nouveauté, résoudre les
désaccords et figer une version approuvée. Puis mesurer une seule fois le système
figé en lui transmettant **seulement les questions**, jamais les réponses attendues
ni les extraits. Aucune comparaison finale n'a été lancée sur ce lot.
