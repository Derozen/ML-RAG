# Complément de revue éditoriale — lot candidat V2

## Choix méthodologique

Compléter les preuves avant de calculer les scores est préférable : des qrels
incomplets peuvent classer à tort une bonne récupération comme une erreur.
Cette étape est une annotation proposée par l'assistant, pas une seconde lecture
humaine indépendante et pas une mesure de performance du système.

## Travail réalisé

- Lecture des pages de Statements encore non jugées, y compris les notes de mise en œuvre.
- Recherche thématique de passages supplémentaires dans les Minutes, puis lecture
  des pages sélectionnées. Cette recherche ciblée n'est pas une lecture exhaustive
  des Minutes et ne démontre pas l'absence d'autres preuves.
- 56 décisions supplémentaires proposées : 55 couples
  nouvellement jugés et 1 révision(s) motivée(s), dont 16
  décisions positives (révisions comprises).
- 18 citations complètes vérifiées directement dans les pages physiques
  des PDF, avec contrôle de l'empreinte des sources.
- 119 jugements proposés au total, dont 69 positifs.
- 175 couples question/page restent non jugés ; ils ne reçoivent pas de zéro.

## Exemples de corrections

- **005, Minutes de juin 2022, p. 8** : inquiétude explicite concernant le désancrage
  des anticipations ; preuve forte de cette facette, indépendamment du vote de 75 points.
- **014, Minutes de mars et septembre 2023, p. 4** : autres passages établissant la
  qualification du PIB par le staff. La p. 8 de septembre explique le choix de
  formulation du communiqué. Ces pages manquaient aux références initiales.
- **009, communiqué de juin 2022, p. 4** : la hausse du crédit primaire est un
  distracteur, elle ne doit pas être confondue avec le vote sur les federal funds.
- **010, communiqué de mars 2025, p. 1 et 3** : soutien partiel sur le changement du
  runoff ; ces pages seules n'établissent pas le raisonnement personnel de Waller.
- **018, communiqué de septembre 2025, p. 1** : révision proposée de 0 à 1 pour
  harmoniser le traitement du contexte collectif. Ce désaccord reste explicite
  et nécessite une adjudication ; le grade initial n'est pas effacé.

## Fichiers et protection contre les fuites

`decisions.jsonl` conserve les motifs et extraits. `coverage.csv` présente tous
les couples et les lacunes. `qrels_PAGES_editorial_proposed.trec` fusionne les
propositions initiales et supplémentaires pour revue, sans les rendre officielles.
Les grilles humaines, les 20 questions, les réponses proposées et les qrels initiaux
restent inchangés ; le pipeline, les 145 questions exploratoires et leurs scores aussi.
Aucun classement de BM25, E5, RRF ou reranker n'a servi à choisir ces ajouts.

Un essai de préannotation avec le modèle local a été arrêté sans produire de
jugement exploitable. **Aucune sortie de ce modèle n'est utilisée ici.**

## Ce qui reste nécessaire

Compléter les 175 couples non jugés et faire confirmer les grades,
les réponses et l'absence d'équivalence sémantique avec les 145 anciennes questions.
Les cas 014, 019 et 020 restent à examiner avec attention. Le fait de changer de
date ou de demander un calcul ne prouve pas à lui seul la nouveauté sémantique.
La construction des questions et leur revue par le même assistant ne constituent
pas deux annotations indépendantes.

Une version approuvée devra ensuite être figée avant une unique mesure du système
sélectionné : **RRF + ColBERT, 20 candidats puis 6 passages**. Les questions seules
seront transmises au système, jamais les réponses ou les extraits de référence.
Les 145 questions restent un jeu exploratoire ; aucun entraînement supervisé local
n'a été réalisé. Ce dossier ne donne pas encore le statut de test final au nouveau lot.
