# Revue du projet à la lumière des cours ECC

Date : 8 novembre 2026. Périmètre : préparation du corpus et comparaison BM25 / Dense E5 / Hybride RRF, avant reranking, génération et déploiement.

## Verdict

Le projet constitue une **base expérimentale cohérente et reproductible** pour la récupération documentaire. Il reprend bien les principes de collecte, nettoyage, représentation, séparation des données d’évaluation, comparaison et restitution du cours. En revanche, il faut parler de **comparaison initiale à paramètres figés**, et non d’optimisation achevée ni de validation scientifique définitive de la meilleure stratégie.

La distinction est importante : les scores historiques sont correctement calculés pour les preuves annotées, mais une preuve correcte absente de ces annotations peut être comptée comme un échec. Un cas concret a été confirmé pendant cette revue. Il faut consolider les annotations avant de généraliser la conclusion « BM25 est le meilleur ».

## Documents effectivement examinés

- `Cours_ML_ECC_1.pdf`, 88 pages : paradigmes d’apprentissage, transfert, qualité, généralisation, explicabilité, processus de développement, déséquilibre, optimisation, régression/classification et validation.
- `Cours_ML_ECC_2.pdf`, 91 pages : prévision temporelle, validation chronologique, comparaison des prévisions, ACP, clustering et détection d’anomalies. La dernière page annonce l’introduction à l’IA générative ; ces deux fichiers ne contiennent pas un protocole détaillé d’évaluation RAG.

Les références ci-dessous sont les **pages physiques des PDF**, numérotées à partir de 1. Les exemples et exercices des supports sont des contenus pédagogiques : ils ne constituent pas une demande de transformer le projet en régression, clustering ou prévision.

## 1. Ce qui correspond déjà aux principes des cours

| Principe des cours | Référence | Vérification dans le projet | Appréciation |
|---|---|---|---|
| Comprendre le problème avant de choisir le modèle | Cours 1, p. 7, 55–56 | Question-réponse documentaire : retrouver des preuves dans des comptes rendus FOMC, et non prévoir une valeur économique. | Cohérent. |
| Privilégier des données de qualité | Cours 1, p. 40–41 ; cours 2, p. 79–80 | Manifeste, empreintes, sources, extraction de 6 080 paragraphes sur 563 pages, audit de conservation et références aux pages. | Bon socle ; l’audit de tokens ne prouve pas à lui seul l’ordre de lecture ni l’exactitude sémantique. |
| Transformer les entrées en représentations exploitables | Cours 1, p. 7, 32–37 | Nettoyage conservateur, 1 454 chunks, index lexical et vecteurs E5 de dimension 384. | Adapté au texte. |
| Séparer sélection et évaluation | Cours 1, p. 44, 84–88 | 50 questions dev et 150 test ; reformulations regroupées ; documents utilisés comme preuves distincts entre lots. | Cohérent pour une baseline sans apprentissage local ; le test a désormais été consulté. |
| Éviter les fuites dans le pipeline | Cours 1, p. 59 ; cours 2, p. 37 | Les réponses et preuves ne servent pas à filtrer les documents au moment de la recherche. Les trois méthodes consultent le même index. | Cohérent pour une collection documentaire fixe. |
| Utiliser des mesures adaptées à l’objectif | Cours 1, p. 59 ; cours 2, p. 9–10, 67–76, 84 | Recall@K, MRR@K, couverture et complétude des groupes de preuves, résultats par type et famille. | Adapté à la récupération, sous réserve de la qualité des annotations. |
| Examiner les erreurs, pas seulement une moyenne | Cours 1, p. 49, 51–54 | Classements par question, sources, cas de divergence et graphiques. | Traçabilité utile ; elle ne constitue pas une explication formelle des mécanismes internes d’E5. |
| Reproduire l’expérience | Cours 1, p. 56, 70, 87 | Version du modèle, configuration, empreintes, graines, versions des dépendances et sorties conservées. | Bon socle ; contrôle de l’empreinte des questions renforcé lors de cette revue. |

## 2. Pourquoi il n’y a pas un jeu d’entraînement FOMC à cette étape

Le cours décrit l’apprentissage d’une fonction à partir de couples `(X, y)` et le réglage de ses paramètres. Ici :

- BM25 calcule des statistiques lexicales sur la collection ; il n’apprend pas des réponses à partir des 200 questions.
- E5 est chargé depuis un modèle déjà entraîné, puis utilisé en inférence. Aucun ajustement de ses poids sur les comptes rendus ou leurs questions n’a été effectué.
- RRF combine des rangs ; il ne s’agit pas d’un modèle de fusion appris.

Les 50 questions dev servent au développement et, lors d’une future recherche d’hyperparamètres, à la sélection. Les 150 questions test décrivent la performance des configurations figées. Il n’est donc pas nécessaire d’inventer un lot d’entraînement inutilisé pour reproduire mécaniquement un découpage en trois parts.

Si un reranker ou un encodeur est **entraîné localement**, un lot d’entraînement séparé, un lot de validation pour les hyperparamètres et un lot test de confirmation deviennent nécessaires. Les questions, reformulations, documents et paires question/passage devront être regroupés selon l’objectif de généralisation. Le préentraînement externe d’E5 n’ayant pas été audité, on ne peut pas certifier l’absence de tout recoupement avec son corpus externe.

## 3. Les corrections et limites importantes

### A. Preuves pertinentes incomplètes : cas confirmé, priorité élevée

Question **Q021**, lot dev : « At the meeting ending 2021-09-22, what federal funds target range did the Committee decide on? »

- Preuve actuellement acceptée : `FOMC_2021-09-22_C0034`.
- Un autre passage, `FOMC_2021-09-22_C0038`, contient explicitement : « The Committee decided to keep the target range for the federal funds rate at 0 to ¼ percent ».
- Ce passage figure à la **position 15 de BM25**, sur la **page physique 12** du PDF. Il répond à la question, mais ne figure pas dans les IDs acceptés. Le score historique reste donc nul pour Q021 alors qu’une preuve suffisante est retrouvée.

Voir [la page source](../data/raw/minutes/fomcminutes20210922.pdf#page=12) et [le constat structuré](../results/methodology_review_2026-11-08/annotation_case_Q021.json).

La vérification de la présence des citations a bien été faite ; elle ne garantissait pas que **tous** les autres passages suffisants étaient annotés. C’est une limite désormais observée, et non simplement théorique. Des jugements incomplets peuvent sous-estimer certains scores et modifier les écarts entre méthodes. Leur effet global n’est pas quantifié ici.

Action nécessaire : revue humaine des preuves alternatives, en mélangeant les candidats des méthodes et en masquant leur origine si possible, plus lecture des passages voisins et des documents sources. Produire une version distincte des jugements de pertinence et recalculer toutes les méthodes avec la même version. Ne pas accepter automatiquement un passage parce qu’il contient la même date ou le même chiffre. Les reformulations doivent conserver les mêmes jugements. Aucun ancien corrigé ni score n’a été modifié par cette revue.

### B. Comparaison initiale, pas recherche d’hyperparamètres achevée

Les valeurs BM25 `(k1=1,5 ; b=0,75)`, le modèle E5, les 400 tokens, les 60 tokens de chevauchement et RRF `(constante=60 ; 20 candidats par branche)` sont des choix fixés pour la première comparaison. Il n’existe pas encore d’expérience de recherche systématique démontrant qu’ils sont optimaux.

Le cours 1 (p. 84–88) distingue précisément réglage sur validation et évaluation finale. Avant une future optimisation : définir le critère principal et le budget de passages ; chercher un ensemble limité de configurations sur dev ; conserver les résultats et justifier la sélection. La profondeur de chaque branche RRF doit être distinguée du nombre final de passages : la configuration actuelle n’explore que 20 candidats par branche. Un changement de découpage impose aussi une nouvelle vérification des preuves.

Le test historique a déjà été consulté et discuté. Il reste un résultat de référence, mais ne peut plus être présenté comme un test final jamais observé pour des modifications conçues après ces résultats. Une nouvelle évaluation de confirmation devra être constituée et tenue à l’écart. Une correction des anciennes annotations peut être réévaluée honnêtement comme analyse révisée de la même baseline, sans la présenter comme une nouvelle confirmation indépendante.

### C. Portée temporelle à préciser

Le cours 2 (p. 4–16) traite de la **prévision** : utiliser le passé pour prédire un futur non disponible. Le projet actuel interroge rétrospectivement une collection documentaire fixe de 2021–2025. Avoir les 40 documents dans l’index n’est pas, en soi, une fuite de labels de questions test.

Le découpage actuel n’établit toutefois pas une capacité de généralisation chronologique. Pour simuler un assistant « tel qu’il existait à une date donnée », il faudrait limiter l’index aux documents effectivement publiés à cette date, organiser validation et confirmation chronologiquement, et contrôler les dates de publication plutôt que les seules dates de réunion. Ce serait une expérience supplémentaire, pas une propriété des résultats actuels. Le test de Diebold–Mariano porte sur des erreurs de prévision temporelles ; il n’est pas à appliquer mécaniquement aux classements actuels.

### D. Dépendance des questions et incertitude

Le bootstrap actuel conserve les reformulations d’une même famille ensemble, ce qui est préférable à les compter comme observations indépendantes. Mais des familles différentes peuvent utiliser la même réunion ; les comparaisons relient même deux réunions. Les intervalles actuels ne couvrent pas cette dépendance ni l’incertitude d’annotation.

Pour une étude plus solide : documenter cette structure et envisager une analyse de sensibilité avec regroupements documentaires ou temporels adaptés aux comparaisons, sans prétendre qu’une seule affectation arbitraire règle le problème. Avec seulement cinq années, un regroupement par année comporte très peu de blocs et doit rester exploratoire. Les trois répétitions contrôlent la stabilité et les durées, elles ne triplent pas le nombre de questions.

### E. Diversité et déséquilibre du jeu

Les 200 questions représentent 160 familles ; certaines sont des reformulations. Les factuelles et comparatives portent surtout sur taux et chômage, les explicatives sont plus variées. Le score global dépend de cette composition. Il faut conserver les résultats par type et par famille, puis élargir progressivement aux thèmes utiles au mémoire.

Les 10 questions sans réponse ne représentent que 5 % du jeu et cinq concernent des dates hors corpus, assez faciles à identifier. Le système retourne toujours des candidats : l’abstention n’est pas encore évaluée. Pour un futur rejet, calibrer la règle sur un lot de développement suffisamment diversifié, puis mesurer sur un lot séparé les rejets corrects et les faux rejets de questions répondables. Les scores BM25, cosinus et RRF ne sont pas des probabilités directement interchangeables.

### F. Temps de réponse

Les lots initiaux ont été lancés en parallèle. Les mesures sont conservées, mais ne permettent pas une conclusion fiable de rapidité comparative. Une mesure isolée, sur la même machine et sous une charge comparable, avec échauffement et répétitions, reste à faire. Ce point était déjà signalé dans le rapport.

## 4. Ce qu’il ne faut pas ajouter simplement parce que cela figure dans le cours

- **StandardScaler ou ACP** : les dimensions d’un embedding E5 ne sont pas des variables tabulaires indépendantes à standardiser automatiquement. La normalisation L2 actuelle est cohérente avec le calcul cosinus. Une réduction de dimension serait une nouvelle variante à valider ; une projection en 2D peut aider l’exploration mais ne prouve pas la pertinence de la récupération.
- **SMOTE/ADASYN** : on ne fabrique pas des questions/preuves artificielles en interpolant leurs embeddings pour équilibrer le test. Pour le futur entraînement supervisé, l’échantillonnage doit être limité au train, avec des exemples et labels appropriés.
- **K-means, silhouette, Davies–Bouldin** : ils évaluent ou construisent des regroupements, pas des listes de passages pertinents pour une question. Leur absence n’est pas une lacune de la récupération actuelle.
- **MSE/RMSE, accuracy, matrice de confusion** : utiles pour leurs tâches respectives ; ils ne remplacent pas Recall@K/MRR et les groupes de preuves. Une matrice de confusion pourra devenir pertinente pour une décision répondable/non répondable.
- **SHAP/LIME** : pas nécessaires pour expliquer les sources d’une réponse documentaire. Les citations assurent une traçabilité ; elles ne sont cependant pas une preuve d’interprétabilité interne d’E5.
- **Courbes de loss ou epochs** : aucun apprentissage local n’a eu lieu ; en produire ici inventerait une phase absente.

## 5. Vérifications et modifications réalisées pendant cette revue

1. Lecture des deux supports, extraction paginée et inspection visuelle des schémas pertinents (séparation, pipeline et fenêtres temporelles).
2. Relecture de la préparation, du découpage, de l’indexation, des trois récupérateurs, de la validation, des métriques et du bootstrap.
3. Contrôle des empreintes et de l’intégrité de l’index ; recomposition des métriques à partir des classements existants, sans relancer E5. Le bilan machine est dans [audit.json](../results/methodology_review_2026-11-08/audit.json).
4. Ajout d’un contrôle manquant dans `evaluation.py` : la commande `compare` exige désormais que l’empreinte des questions corresponde à la version validée dans `annotations.json`, en plus du contrôle des chunks. Une modification des questions ne peut plus passer avec une ancienne validation inchangée. Ce contrôle ne remplace pas une revue sémantique.
5. Ajout de deux tests de non-régression, pour les questions modifiées après validation et l’empreinte absente.
6. Conservation du corpus, des annotations, des index, des classements et des scores historiques. Aucune nouvelle stratégie, aucun fine-tuning et aucune optimisation sur test n’ont été lancés.

Pour reproduire les contrôles locaux :

```powershell
cd C:\Users\LENOVO\Desktop\VS_Codex\RAG_FOMC
.\.venv\Scripts\python.exe scripts/audit_methodology.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Conclusion à employer dans le mémoire

« Dans la configuration initiale et pour les preuves annotées du jeu évalué, BM25 obtient le meilleur rappel et la meilleure complétude à 20 passages ; l’hybride RRF obtient le meilleur MRR. Cette comparaison constitue une baseline reproductible. L’exhaustivité des jugements de pertinence, la diversité des questions, l’optimisation des paramètres et une confirmation indépendante restent à consolider. »

La première étape de **mise en œuvre** est donc terminée. La première étape d’**évaluation rigoureuse** possède une base exploitable, mais demande encore ce travail de consolidation avant une conclusion générale ou définitive.
