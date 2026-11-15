# RAG FOMC — 145 questions et références silver de pages

Le jeu actif est désormais **`queries_145.jsonl`**, accompagné de **`silver_qrels_PAGES.trec`**. Les deux fichiers fournis sont copiés sans modification dans `data/evaluation/`. Les 110 anciennes questions et leurs résultats sont conservés dans `_archive/phase_110_20261114/`.

Les **145 questions sont évaluées ensemble**, sans entraînement local ni découpage train/test. Le fichier fourni contient des étiquettes `dev`, `test` et `validation` ; elles restent disponibles comme métadonnées, mais ne commandent aucun partage des calculs. Les récupérateurs et rerankers reçoivent uniquement l’identifiant et le texte de la question.

## Organisation

```text
RAG_FOMC/
├── README.md
├── requirements.txt
├── run.py
├── data/
│   ├── raw/                     # 46 minutes + 47 statements, PDF 2021–2026
│   ├── processed/
│   │   ├── manifest.json        # Sources, pages et empreintes des 93 PDF
│   │   ├── paragraphs.jsonl
│   │   ├── chunks.jsonl         # 1 774 passages avec provenance
│   │   └── chunk_report.json
│   └── evaluation/
│       ├── queries_145.jsonl            # Questions et métadonnées originales
│       ├── silver_qrels_PAGES.trec      # Qrels originaux : question, 0, PDF#page, grade
│       ├── page_qrels.tsv               # Mêmes 279 jugements, au format tabulaire
│       ├── chunk_pages.jsonl            # Provenance des chunks vers les pages
│       └── alignment_report.json       # Validation et empreintes
├── indexes/
│   ├── bm25/
│   └── dense/
├── src/
│   ├── chunk.py                 # 1. Extraction et découpage des PDF
│   ├── align_references.py      # 2. Validation des pages et de leur provenance
│   ├── build_indexes.py         # 3. Index BM25/E5 et préparation des modèles
│   ├── retrieve.py              # 4. BM25, E5, hybride RRF
│   ├── rerank.py                # 5. BM25, ColBERT, cross-encoder
│   ├── evaluate.py              # 6. Métriques de pages, rapport, graphiques
│   ├── common.py                # Paramètres et fonctions communes
│   └── pdf_layout.py            # Lecture des colonnes et lignes PDF
├── tests/
│   └── test_pipeline.py
├── results/
│   ├── retrieval/               # Classements des 20 chunks par méthode/question
│   ├── reranking/               # Reclassements et temps
│   ├── plots/                   # Trois graphiques PNG
│   ├── comparison.csv           # Moyennes des 12 configurations
│   ├── metrics_per_question.csv # 145 × 12 = 1 740 évaluations
│   ├── page_rankings.jsonl       # Pages uniques et chunks pour chaque classement
│   ├── paired_changes.csv       # Gains et pertes face au classement initial
│   ├── cases.jsonl              # Exemples de gains et pertes
│   ├── verification.json
│   └── RAPPORT.md
└── _archive/                    # Anciennes études 200 puis 110 questions, inactives
```

Il existe un seul projet actif. Les anciens ZIP sont dans l’archive de la phase 200. Les dossiers `.venv` et `.cache` contiennent l’environnement Python et les checkpoints locaux.

## Utiliser les résultats

Ouvrir d’abord **`results/RAPPORT.md`**, puis **`results/comparison.csv`**. Les métriques de ce jeu concernent les **pages PDF uniques**. Les graphiques sont dans `results/plots/` :

1. `01_retrieval.png` : comparaison BM25, E5 et RRF.
2. `02_reranking_ndcg.png` : classement initial et trois rerankers.
3. `03_latency.png` : temps CPU exploratoires.

Pour suivre une question, filtrer `metrics_per_question.csv` par `question_id`, consulter les pages ordonnées dans `page_rankings.jsonl`, puis ouvrir les PDF de `data/raw/` à leurs pages physiques. `cases.jsonl` et le rapport présentent des exemples avant/après.

## Exécuter dans PowerShell

```powershell
cd C:\Users\LENOVO\Desktop\VS_Codex\RAG_FOMC
$env:HF_HUB_OFFLINE = "1"

# Recalculer uniquement les métriques, graphiques et rapport avec les rangs existants
.\.venv\Scripts\python.exe src/evaluate.py

# Refaire la recherche puis le reranking et les métriques
.\.venv\Scripts\python.exe run.py --from-step retrieve

# Refaire les six étapes, y compris découpage et indexation
.\.venv\Scripts\python.exe run.py

# Tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les index documentaires existants sont réutilisables : ils ne dépendent pas des questions. Le contrôle des index vérifie les empreintes du corpus et les paramètres, sans exiger la même taille de jeu de questions. Les métadonnées de construction du corpus/index peuvent conserver la taille du jeu historique ; le jeu actif est défini par `queries_145.jsonl` et vérifié dans chaque nouveau run.

Le reranking réutilise un calcul terminé seulement si les empreintes des candidats et la configuration correspondent. Pour refaire ses mesures depuis zéro, archiver les fichiers de `results/reranking/` avant de relancer. Un cache incompatible est refusé. Le calcul sur CPU peut prendre plusieurs minutes, particulièrement pour le cross-encoder.

Si les checkpoints sont absents, les télécharger avant l’exécution hors ligne :

```powershell
Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe src/build_indexes.py --download-models
```

Cette commande télécharge les checkpoints publics à révision fixée et vérifie les poids par SHA-256. Les questions et les rapports restent sur le poste pendant les calculs.

## Méthodes

Les PDF sont lus en tenant compte des colonnes et des lignes à plusieurs polices. Les chiffres et les négations sont conservés. Les chunks comportent au plus 400 tokens E5 de corps, avec chevauchement de 60 tokens ; l’entrée complète reste sous 512 tokens. Les identifiants distinguent minutes et statements d’une même date.

- **BM25** : statistiques du corpus complet, k1=1,5 et b=0,75.
- **Dense E5** : `intfloat/e5-small-v2`, vecteurs normalisés de 384 dimensions, cosinus exact, préfixes `query:` et `passage:`.
- **Hybride RRF** : fusion des deux listes top-20, constante 60, puis sélection de 20 chunks.

Chaque liste de 20 chunks est reclassée par :

- **BM25**, avec les statistiques du corpus complet. BM25 sur sa propre liste est un contrôle d’identité.
- **ColBERT**, checkpoint `answerdotai/answerai-colbert-small-v1` : poids BERT et projection apprise à 96 dimensions, marqueurs de rôle, normalisation des vecteurs de tokens, masquage de la ponctuation documentaire et somme MaxSim. Limites fixées à 64 tokens par question et 512 par document, sans expansion de requête.
- **Cross-encoder**, `cross-encoder/ms-marco-MiniLM-L6-v2` : score de chaque paire question/passage ; limite 512 tokens, troncature du document uniquement si nécessaire.

Les révisions exactes sont dans `common.py` et les fichiers `*_run.json`. Les mêmes 20 identifiants sont contrôlés avant et après chaque reranking.

## Pourquoi évaluer des pages ?

Les **279 jugements silver** fournis concernent **169 pages distinctes dans les 93 documents** : 188 grades 2 et 91 grades 1. Les grades sont conservés exactement. Le programme vérifie les questions, doublons, fichiers, numéros physiques de pages et présence des pages dans le texte indexé. Il ne prétend pas avoir réannoté leur pertinence sémantique.

Un chunk peut couvrir plusieurs pages et plusieurs chunks peuvent provenir d’une même page. La projection utilisée est :

1. Parcourir les chunks dans leur ordre de classement.
2. Pour chaque chunk, prendre les pages de ses paragraphes, par ordre physique.
3. Garder chaque page à sa première apparition seulement.

Cette convention est indépendante des qrels. Elle impose un ordre physique aux pages d’un même chunk et peut donc influencer les métriques aux coupures. Aucun jugement de pertinence de chunk n’est inventé à partir d’une page pertinente.

**Recall@5/10/20** mesure la proportion des pages pertinentes annotées retrouvées dans les premières pages uniques. **nDCG@10** utilise le gain `2^grade - 1`, la décote `log2(rang + 1)` et un idéal calculé sur tous les qrels de la question. **MRR@10** mesure l’inverse du rang de la première page pertinente, ou zéro si aucune n’apparaît dans les dix premières.

**`pool_page_recall`** mesure la couverture de l’ensemble des pages présentes dans les 20 chunks candidats. Cette couverture reste identique après reranking. En revanche, Recall@20 peut changer si les 20 chunks couvrent plus de 20 pages uniques : ces deux coupures ne désignent pas la même chose.

Une page pertinente peut contenir un chunk qui ne répond pas à la question. Les métriques de pages sont donc plus grossières que des métriques reposant sur des preuves localisées dans les passages. Les pages non annotées valent zéro pour le calcul, sans être prouvées non pertinentes. Le caractère silver et la couverture potentiellement incomplète des annotations limitent les conclusions.

Les 145 questions forment un jeu unique de comparaison descriptive à paramètres fixés. Les scores ne constituent pas une évaluation indépendante après optimisation et ne sont pas directement comparables aux anciens scores de chunks.

## Temps et reproductibilité

Les durées correspondent à un passage CPU après échauffement, sans chargement des modèles. ColBERT préencode les passages candidats : ce coût est enregistré séparément dans `colbert_run.json`, puis exclu du temps en ligne. L’encodage de la question et MaxSim sont inclus dans le reranking. Le cross-encoder calcule les paires de chaque configuration sans cache partagé de scores. Les mesures restent exploratoires.

Les fichiers de run et `verification.json` conservent les paramètres, versions, empreintes des entrées et contrôles de candidats.
