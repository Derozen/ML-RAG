# RAG FOMC — récupération, reranking et évaluation

Un seul projet : le pipeline original dans `src/`, avec ses scores conserves.
Le corpus comprend 93 PDF, 838 pages et 1 692 chunks. Les 145 questions sont
exploratoires ; les 20 questions supplémentaires restent une évaluation
complémentaire provisoire, avec 294 grades acceptés globalement par l’utilisateur.

## Lancer Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port 8603
```

L'interface utilise le pipeline original dans `src/`.

## Résultats et rapport V1

- [Rapport principal](docs/RAPPORT_PROJET.md).
- [Bilan de finalisation](docs/FINALISATION.md).
- [Statut des 20 questions](docs/STATUT_HOLDOUT.md).
- [Cinq graphiques de comparaison](results/figures/INDEX.md).
- [Scores des 145 questions, six chunks](results/context_top6/comparison.csv).
- [Scores supplémentaires et graphique des 20 questions](results/candidate_provisional/INDEX.md).
- [Analyse d’erreurs consolidée et résultats par type](results/finalization/ANALYSE_ERREURS.md).
- [Trois cas avec citations vérifiées](results/audit_project/ANALYSE_QUALITATIVE_DEV.md).
- [Analyse exploratoire du corpus](results/audit_project/RAPPORT.md).
- [Conformité ECC](docs/CONFORMITE_ECC.md), [méthodes](docs/METHODOLOGIE.md) et [références](docs/REFERENCES.md).

En V1, 20 candidats sont reclassés avant de retenir 5 ou 6 chunks. Les qrels
portent sur des pages PDF. La couverture des pages de six chunks et les métriques
tronquées à six pages uniques n’ont pas le même périmètre. Les études 200/110
sont archivées, sans constituer d’autres projets actifs.

## Installation et données

Python 3.12.7 est utilisé sur le poste de référence. Les dépendances et les poids
exigent un accès aux distributions nécessaires :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/build_indexes.py --download-models
```

Le [manifeste](data/corpus_manifest.json) contient les URL et empreintes des PDF.
Pour importer le corpus depuis un dossier local ou tenter les URL officielles :

```powershell
.\.venv\Scripts\python.exe scripts/acquire_corpus.py --from-dir 'D:\corpus\raw'
# Sans --from-dir : téléchargement avec contrôle SHA-256.
.\.venv\Scripts\python.exe scripts/acquire_corpus.py
```

Pour générer, installer/démarrer Ollama et préparer `ollama pull qwen2.5:3b`.
Sans Ollama, désactiver la génération dans l’interface. Le premier chargement
peut être lent sur CPU. La V1 originale reste accessible avec
`.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py`.

## Tests et reproduction

```powershell
.\.venv\Scripts\python.exe src/protocol.py verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/verify_metrics.py
.\.venv\Scripts\python.exe scripts/verify_delivery.py
```

[Les preuves de reproduction V1](docs/REPRODUCTION.md) distinguent la reconstruction
isolée réussie avec dépendances réutilisées de l’installation vierge non confirmée.

```powershell
.\.venv\Scripts\python.exe scripts/reproduce_project.py --workdir tmp/reproduction_nouvelle
```

Le dossier doit être nouveau. `--python` permet de choisir un interpréteur
déjà préparé. Pour recalculer aussi recherche et reranking, exécuter
`python run.py --from-step retrieve` dans la copie de travail. Les commandes
écrivent leurs sorties : préserver les références V1.

Les scores supplémentaires sont déjà disponibles. Leur reproduction explicite
et le recalcul séparé des métriques utilisent :

```powershell
.\.venv\Scripts\python.exe scripts/score_candidate.py --provisional
.\.venv\Scripts\python.exe scripts/verify_candidate_scores.py results/candidate_provisional/20261120T151147Z
```

La validation globale est tracée dans
[user_approval.json](data/holdout_candidate/assistant_review/completed_proposal/user_approval.json).
La [grille actuelle](data/holdout_candidate/assistant_review/completed_proposal/human_review.csv)
est dans `assistant_review/completed_proposal/` ; la grille supérieure est historique.

## Exports de remise

```powershell
.\.venv\Scripts\python.exe scripts/plot_comparisons.py
.\.venv\Scripts\python.exe scripts/build_project_review.py
.\.venv\Scripts\python.exe scripts/finalize_delivery.py
```

Le paquet local est `output/delivery/RAG_FOMC_remise.zip` ; il contient les PDF,
index, code et preuves, avec [inventaire SHA-256](results/finalization/delivery_manifest.json).
Il exclut les poids et l’environnement Python. Un paquet déjà créé représente
l’état au moment de sa création ; il ne se met pas à jour automatiquement .
Aucune publication distante n’est effectuée par ces commandes.

## Emplacement des codes

| Étape | Fichiers |
|---|---|
| Extraction et découpage | `src/pdf_layout.py`, `src/chunk.py` |
| Références et index | `src/align_references.py`, `src/build_indexes.py` |
| Récupération et reranking V1 | `src/retrieve.py`, `src/rerank.py` |
| Métriques V1 | `src/evaluate.py` |
| Pipeline et génération V1 | `src/rag_pipeline.py`, `src/generate.py` |
| Interface | `app/streamlit_app.py` |
| Rapports et contrôles | `scripts/` |
| Annotations | `annotation_tools/` |

Le verrou du pipeline original reste intact.
