# RAG FOMC ? r?cup?ration, reranking et ?valuation

Un seul projet actif : **93 PDF, 838 pages et 1 692 chunks**. Les 145 questions
constituent la comparaison exploratoire. Les 20 questions suppl?mentaires sont
une ?valuation compl?mentaire ? scores provisoires ; leurs 294 grades ont ?t?
accept?s globalement par l?utilisateur apr?s le calcul. Leur ind?pendance
s?mantique n?est pas ?tablie. Les ?tudes 200/110 sont archiv?es dans `_archive/`.

## Lire les r?sultats actuels

- [Rapport du projet](docs/RAPPORT_PROJET.md).
- [?tat des cinq actions de finalisation](docs/FINALISATION.md).
- [D?cision sur le lot de 20 questions](docs/STATUT_HOLDOUT.md).
- [Cinq figures de comparaison exploratoire PNG/SVG](results/figures/INDEX.md).
- [Scores des 145 questions, six chunks](results/context_top6/comparison.csv).
- [Scores suppl?mentaires des 20 questions et graphique](results/candidate_provisional/INDEX.md).
- [Analyse d?erreurs consolid?e et r?sultats par type sur dev](results/finalization/ANALYSE_ERREURS.md).
- [Trois cas avec citations v?rifi?es](results/audit_project/ANALYSE_QUALITATIVE_DEV.md).
- [Analyse exploratoire du corpus](results/audit_project/RAPPORT.md).
- [Concordance avec les consignes ECC](docs/CONFORMITE_ECC.md).
- [M?thodes](docs/METHODOLOGIE.md) et [r?f?rences scientifiques](docs/REFERENCES.md).

Les **20 candidats** sont reclass?s avant de s?lectionner **5 ou 6 chunks**.
Les qrels portent sur des pages PDF ; la couverture de toutes les pages du contexte
et les m?triques limit?es aux premi?res pages uniques n?ont pas le m?me p?rim?tre.
Le rapport `results/RAPPORT.md` d?crit le pool complet ; la comparaison principale
est dans `results/context_top6/`.

## Installation et application

Python 3.12.7 est utilis? sur le poste de r?f?rence. Depuis ce dossier :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/build_indexes.py --download-models
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

Les r?visions sont fix?es dans `src/common.py` et le [verrou](protocol/frozen_pipeline_20261120.json).
Les poids ne sont pas inclus dans le paquet de remise. L?installation et leur
acquisition exigent un acc?s r?seau. Voir [REPRODUCTION.md](docs/REPRODUCTION.md)
pour les succ?s r?ellement observ?s et l??chec de l?installation vierge.

Pour la g?n?ration, installer/d?marrer Ollama puis `ollama pull qwen2.5:3b`.
Sans Ollama, d?sactiver la g?n?ration dans l?interface. Cette fonctionnalit? est
exp?rimentale : une r?ponse r?elle ?tait partielle et citait d?autres r?unions.
Voir les [traces techniques](docs/VERIFICATION_TECHNIQUE.md).

Pr?chargement optionnel du mod?le d?j? install? avant une d?monstration :

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/generate' -Method Post -ContentType 'application/json' -Body '{"model":"qwen2.5:3b","prompt":"","stream":false,"keep_alive":"15m"}' -TimeoutSec 600
```

## Corpus et reproduction

Le [manifeste du corpus](data/corpus_manifest.json) contient noms, types, URL et
SHA-256. Les PDF exacts et les index sont inclus dans le paquet local de remise.
Pour importer depuis un dossier `raw/`, ou tenter les URL officielles :

```powershell
.\.venv\Scripts\python.exe scripts/acquire_corpus.py --from-dir 'D:\corpus\raw'
# Sans --from-dir : t?l?chargement, avec refus de tout SHA-256 diff?rent.
.\.venv\Scripts\python.exe scripts/acquire_corpus.py
```

Reconstruction de l?extraction, de l?alignement et des index dans un dossier neuf,
puis recalcul des m?triques des classements fig?s, tests et Streamlit r?el :

```powershell
.\.venv\Scripts\python.exe scripts/reproduce_project.py --workdir tmp/reproduction_nouvelle
```

Cette commande r?utilise les d?pendances de l?interpr?teur et les poids locaux ;
elle n?est pas une installation vierge. `--python` permet de choisir un autre
interpr?teur d?j? pr?par?. Pour refaire aussi la recherche/reranking, lancer
`python run.py --from-step retrieve` dans la **copie de travail**. Le pipeline
complet `python run.py` ?crit ses sorties : pr?server les r?sultats de r?f?rence.

## Contr?les et exports

```powershell
.\.venv\Scripts\python.exe src/protocol.py verify
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/verify_metrics.py
.\.venv\Scripts\python.exe scripts/verify_delivery.py
# Optionnel, lent : un vrai appel Ollama sur une ancienne question dev.
.\.venv\Scripts\python.exe scripts/verify_delivery.py --generation
```

AppTest et HTTP ne remplacent pas une inspection graphique dans tous les navigateurs.
Les dur?es CPU apr?s ?chauffement ne repr?sentent pas une requ?te interactive froide.
Pour recalculer explicitement les scores provisoires et v?rifier leurs m?triques :

```powershell
.\.venv\Scripts\python.exe scripts/score_candidate.py --provisional
.\.venv\Scripts\python.exe scripts/verify_candidate_scores.py results/candidate_provisional/20261120T151147Z
```

Chaque mesure cr?e un dossier s?par?. Les r?ponses et qrels ne sont pas transmis
aux r?cup?rateurs/rerankers. La validation globale est dans
[user_approval.json](data/holdout_candidate/assistant_review/completed_proposal/user_approval.json) ;
la [grille actuelle](data/holdout_candidate/assistant_review/completed_proposal/human_review.csv)
est dans `assistant_review/completed_proposal/`. La grille de niveau sup?rieur est historique.

Reconstruction des figures, du rapport et du ZIP local :

```powershell
.\.venv\Scripts\python.exe scripts/plot_comparisons.py
.\.venv\Scripts\python.exe scripts/build_project_review.py
.\.venv\Scripts\python.exe scripts/finalize_delivery.py
```

Le paquet est `output/delivery/RAG_FOMC_remise.zip` ; son
[inventaire](results/finalization/delivery_manifest.json) indique les empreintes.
L?environnement Python et les poids sont exclus. Les preuves sont autoris?es
par `.gitignore`, sans publication/pouss?e effectu?e vers un d?p?t distant.

## Emplacement des codes

| ?tape | Fichier |
|---|---|
| Extraction PDF et d?coupage | `src/pdf_layout.py`, `src/chunk.py` |
| Alignement des pages et r?f?rences | `src/align_references.py` |
| Index BM25 et vectorisation E5 | `src/build_indexes.py` |
| R?cup?ration BM25/E5/RRF | `src/retrieve.py` |
| Reranking BM25/ColBERT/cross-encoder | `src/rerank.py` |
| M?triques et contextes | `src/evaluate.py` |
| Questions libres et g?n?ration | `src/rag_pipeline.py`, `src/generate.py` |
| Interface | `app/streamlit_app.py` |
| Figures, rapports et contr?les de remise | `scripts/` |
| Annotations et tra?abilit? | `annotation_tools/` |

Toute modification du syst?me fig? doit ?tre d?clar?e dans une nouvelle version ;
le verrou historique ne doit pas ?tre r??crit pour masquer une modification.
