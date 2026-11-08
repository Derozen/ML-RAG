# RAG FOMC — préparation et comparaison de la récupération

Première étape du projet **« Optimisation et déploiement d’un système RAG pour la question-réponse : étude comparative des stratégies de récupération et de reranking et proposition d’un cadre d’évaluation rigoureux »**.

Ce dépôt implémente le circuit allant des fichiers locaux aux classements de passages sourcés et à leur comparaison. Il s’arrête à la récupération : le reranking appris, la génération de réponses et le déploiement appartiennent aux étapes suivantes. La fusion RRF est ici une stratégie de récupération hybride.

**Données intégrées depuis `ML-RAG-master.zip` : 40 Minutes de 2021 à 2025, 563 pages et 6 080 paragraphes.** Le manifeste est rempli et les originaux sont conservés. Les 47 communiqués et 6 Minutes de 2026 restent disponibles dans `data/raw/` et sont exclus du corpus principal selon le périmètre du guide. Aucun rapport de 2020 n’est fourni. Les questions validées restent à constituer : `evaluation/questions.jsonl` demeure réservé à cette version relue.

Le détail des choix repris du dépôt fourni et des corrections est dans [docs/INTEGRATION_ML_RAG.md](docs/INTEGRATION_ML_RAG.md). Les scripts originaux sont conservés sous `references/ML-RAG-master/`.

**Exécution réelle effectuée :** 1 454 passages, matrice E5 normalisée de **1 454 × 384**, puis **600 candidats sourcés** produits par BM25, dense et RRF sur les dix questions brouillon. Les sorties sont dans `results/pilot_retrieval_v1/` ; `preview.md` permet une première lecture et `verification.json` consigne les contrôles techniques. La pertinence scientifique attend la revue des annotations.

## 1. Choix expérimentaux

| Élément | Configuration initiale |
|---|---|
| Documents | Minutes fournies dont la date de fin de réunion est entre 2020 et 2025 ; 2021–2025 effectivement présents |
| Corpus | Un document canonique par compte rendu ; HTML préféré, PDF conservé pour contrôle |
| Prétraitement | Unicode NFC, espaces normalisés ; chiffres, fractions, dates et négations conservés |
| Découpage | Environ 400 tokens E5, chevauchement de 60 tokens, frontières de phrases préférées |
| Frontières | Aucun passage ne mélange deux documents ou sections |
| Texte de recherche | Date en anglais + date ISO + section + passage original |
| Lexical | BM25Okapi, `k1=1.5`, `b=0.75`, sans suppression des stopwords |
| Dense | `intfloat/e5-small-v2`, vecteurs normalisés float32, cosinus exact NumPy |
| Hybride | Union des top 20 BM25/dense, RRF avec constante 60, top 20 uniques |
| Égalités | Ordre canonique croissant des identifiants |
| Recherches | Corpus entier, aucun filtrage déduit des réponses de référence |

E5 utilise les préfixes `passage: ` et `query: `. Sa [fiche officielle](https://huggingface.co/intfloat/e5-small-v2) décrit son usage pour l’anglais et sa limite de 512 tokens. Le code contrôle la longueur complète, métadonnées et tokens spéciaux inclus, avant l’encodage. Il refuse les entrées trop longues plutôt que d’accepter une troncature silencieuse.

Le preset principal fixe E5 à la révision **`ffb93f3bd4047442299a41ebb6fa998a38507c52`**, établie depuis le dépôt du modèle lors de cette intégration. Une configuration utilisant `main` est résolue en SHA au découpage. La vectorisation et les questions chargent ensuite cette même révision enregistrée. L’API utilisée est documentée dans [Sentence Transformers](https://sbert.net/docs/package_reference/sentence_transformer/model.html).

## 2. Organisation

```text
RAG_FOMC/
  configs/default.json          Paramètres de départ
  data/manifest.csv             Inventaire fourni et contrôlé
  data/raw/                     Originaux à recevoir
  data/processed/               Paragraphes, passages et rapports de contrôle
  evaluation/
    questions.jsonl             Questions et preuves annotées
    question.template.json      Gabarit à remplir, pas une question validée
    annotations.json            Lien entre annotations et version des passages
  indexes/                      Matrice, IDs, tokens BM25 et métadonnées
  results/                      Un sous-dossier par expérience
  src/rag_fomc/
    common.py                   Configuration, empreintes, écritures et formats
    preprocessing.py            Normalisation et tokenisation lexicale
    ingestion.py                Inventaire, extraction HTML/PDF/TXT
    archive_import.py           Import sûr du ZIP et sélection du corpus
    pdf_layout.py               Ordre des colonnes, paragraphes et titres PDF
    quality.py                  Audit de conservation et extraits à relire
    chunking.py                 Découpage par offsets et provenance
    encoding.py                 Chargement E5 et contrôles d’encodage
    indexing.py                 Construction et vérification des index
    retrieval.py                BM25, dense et RRF
    evaluation.py               Validation, mesures, benchmark et exports
    comparison.py               Différences appariées et cas à relire
    pilot.py                    Liaison des questions brouillon aux passages
    cli.py                      Commandes du projet
  tests/test_pipeline.py        Tests sur données synthétiques
  docs/                        Contrats de données et protocole expérimental
  run.py                        Lanceur sans installation du paquet
  pyproject.toml               Dépendances et commande installable
```

## 3. Installation dans PowerShell

Depuis ce dossier dans VS Code, avec Python 3.10 ou plus récent :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip freeze > requirements-local.txt
.\.venv\Scripts\python.exe run.py --help
```

Les dépendances applicatives sont définies dans `pyproject.toml`. `requirements-local.txt` permet de conserver les versions effectivement installées pour l’expérience. Le premier chargement du tokenizer/modèle nécessite Internet et de l’espace pour les poids. Les documents et les questions ne sont envoyés à aucun service de génération ; les embeddings sont calculés localement. Pour une exécution hors ligne, précharger le modèle et utiliser sa révision SHA.

`requirements-tested.txt` fixe les versions critiques de l’environnement vérifié. Il peut servir de contraintes avant `pip install -e .` pour reproduire ces versions.

Le lanceur place par défaut le cache du modèle dans `.cache/huggingface/`. Sous Windows, il utilise le transport HTTP et un délai de lecture de 120 secondes, adaptés aux blocages et délais de téléchargement constatés sur ce poste. Des valeurs d’environnement déjà définies par l’utilisateur sont respectées. Le cache et l’environnement Python sont exclus des archives de livraison.

Un script de secours existe pour les connexions interrompant les gros fichiers : `.\.venv\Scripts\python.exe scripts/download_e5_model.py --workers 4`. Il télécharge le modèle E5 épinglé par blocs reprenables, contrôle les plages et vérifie le SHA256 officiel de l’ensemble avant de placer les poids dans le cache local. La concurrence est limitée à huit connexions. Le pipeline `index` reste identique après ce préchargement.

## 4. Importer ou reproduire les données fournies

L’import et l’extraction ont déjà été exécutés. Pour les reproduire depuis le ZIP :

```powershell
.\.venv\Scripts\python.exe run.py import-archive --archive "C:\Users\LENOVO\Downloads\ML-RAG-master.zip"
.\.venv\Scripts\python.exe run.py inventory
.\.venv\Scripts\python.exe run.py extract
.\.venv\Scripts\python.exe run.py audit
```

`data/archive_inventory.csv` recense les 93 PDF, leur empreinte, leur type et la raison d’inclusion/exclusion. `data/import_report.json` consigne l’empreinte du ZIP, les comptes et la provenance des sources. Les dates de début/fin des réunions sont établies à partir du titre PDF ou de la première page, puis confrontées au nom du fichier. La date de publication reste vide lorsqu’elle n’est pas établie. Les fichiers `.env`, réglages VS Code et bytecodes du ZIP ne sont pas importés. Les scripts de référence ne sont jamais exécutés par l’import.

Pour ajouter d’autres documents ultérieurement :

Toute extension du corpus doit recevoir une nouvelle `corpus_version` dans la configuration, puis un nouveau découpage, une réindexation et une vérification des preuves.

1. Déposer les originaux dans `data/raw/`, sans modifier leur contenu.
2. Remplir une ligne du manifeste par document canonique avec les dates et l’URL officielle. Indiquer toutes les réunions liées pour un fichier commun, notamment les cas particuliers de 2020.
3. Utiliser `obtained`, `missing`, `review` ou `duplicate` pour le statut. Seuls les documents `obtained` sont indexés. La colonne `sha256` peut être vide lors du premier inventaire ; si renseignée, elle est vérifiée. Les empreintes calculées sont également conservées avec les paragraphes.
4. Vérifier sur les originaux le type **Minutes**, les dates et l’unicité HTML/PDF : une empreinte seule ne détecte pas deux formats d’un même document.
5. Commencer avec trois rapports de réunions différentes et dix questions relues, puis étendre le corpus.

Le guide annonce 56 rapports : ce nombre reste une attente à rapprocher de l’inventaire. Le code produit les comptes par année et l’écart sans inventer de documents ni bloquer un pilote de trois rapports.

Le contrat exact du manifeste et des annotations est dans [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md).

## 5. Exécuter la préparation

Les commandes suivantes sont à lancer depuis la racine de `RAG_FOMC` :

```powershell
.\.venv\Scripts\python.exe run.py inventory
.\.venv\Scripts\python.exe run.py extract
.\.venv\Scripts\python.exe run.py audit
# Relire les paragraphes avant de poursuivre.
.\.venv\Scripts\python.exe run.py chunk
# Contrôler tailles, sources et continuité de deux passages voisins.
.\.venv\Scripts\python.exe run.py index
```

Pour un autre dossier ou une variante de configuration, placer les options globales **avant** la sous-commande :

```powershell
.\.venv\Scripts\python.exe run.py --root . --config configs/default.json chunk
```

| Commande | Artefacts principaux | Contrôle attendu |
|---|---|---|
| `inventory` | `inventory_report.json` | Comptes, doublons, fichiers et URLs |
| `extract` | `paragraphs.jsonl`, `extraction_report.json` | Début/milieu/fin, chiffres, négation, tableaux |
| `audit` | `quality_report.json`, `review_samples.md` | Conservation des tokens par page et extraits pour revue |
| `chunk` | `chunks.jsonl`, `chunking.json` | Passages par document, min/médiane/max, provenance |
| `index` | `vectors.npy`, `chunk_ids.json`, `bm25_tokens.jsonl`, `metadata.json` | Dimensions, normalisation, empreintes et ordre des IDs |

Les rapports de préparation sont écrits dans `data/processed/`. Le sélecteur HTML initial est `#article` ; une absence provoque une erreur explicite. Le PDF est extrait par lignes géométriques : détection d’une/deux colonnes, lecture gauche puis droite, reconstruction des paragraphes et identification des titres usuels. Les titres restent présents dans le contenu pour éviter toute perte. Les en-têtes connus sont retirés uniquement dans la marge supérieure. Des contrôles visuels ont porté sur les formats anciens et récents et sur des pages de décisions du pilote. L’ordre complexe et les tableaux demandent toujours une revue. Une page vide bloque l’extraction. Les lignes additionnelles de `pdf_drop_lines` sont réservées à des suppressions vérifiées.

Les mots coupés en fin de ligne ne sont pas réunis automatiquement : cela exige un contrôle de l’original. Les TXT doivent être des exports UTF-8 déjà vérifiés, avec paragraphes séparés par une ligne vide.

## 6. Rechercher sans annotations

```powershell
.\.venv\Scripts\python.exe run.py retrieve --question "How did participants describe inflation?" --output results/exploration_01
```

Ou passer un JSONL contenant au minimum `qid` et `question` :

```powershell
.\.venv\Scripts\python.exe run.py retrieve --questions evaluation/questions.jsonl --output results/exploration_02
```

Les trois méthodes produisent des résultats sur les mêmes passages. `rankings.csv` contient les identifiants, rangs, scores, dates et URLs. `rankings.jsonl` inclut aussi le texte original et la provenance. `diagnostics.json` signale notamment une absence de correspondance lexicale et des scores lexicaux tous égaux. Un top 20 existe même pour une question hors corpus ; il ne constitue pas une réponse garantie.

Ces temps exploratoires ne remplacent pas le benchmark avec échauffement.

Un jeu de dix questions de développement sur les réunions de janvier 2021, septembre et novembre 2024 peut être préparé après le découpage :

```powershell
.\.venv\Scripts\python.exe run.py prepare-pilot
.\.venv\Scripts\python.exe run.py retrieve --questions evaluation/pilot_draft.jsonl --output results/pilot_retrieval_v1
```

Les citations, numéros de pages et réponses de référence de ces brouillons sont issus des PDF fournis. Les IDs sont retrouvés automatiquement dans les passages. Toutes les questions portent `validated: false` : une revue indépendante est nécessaire avant de les transférer vers `questions.jsonl` et de calculer une comparaison finale. `pilot_draft.metadata.json` enregistre le découpage concerné.

## 7. Préparer l’évaluation

Créer les annotations à partir des originaux avec le gabarit `evaluation/question.template.json`. Chaque ligne de `questions.jsonl` est un objet JSON complet. Pour une question comparative, créer **un groupe de preuve par élément nécessaire** ; plusieurs `chunk_ids` dans un groupe représentent des passages acceptables pour le même élément.

Le validateur exige une citation présente dans chaque passage déclaré acceptable. Si les passages équivalents emploient des formulations différentes, renseigner le dictionnaire optionnel `quotes_by_chunk`, qui associe chaque ID concerné à sa citation exacte. Les autres IDs utilisent `quote`. La pertinence de chaque variante pour le même élément doit être validée humainement.

Après revue croisée des questions et des preuves :

```powershell
Get-FileHash data/processed/chunks.jsonl -Algorithm SHA256
```

Copier l’empreinte en minuscules dans `evaluation/annotations.json`, renseigner les relecteurs et mettre `validated: true` uniquement pour les questions réellement validées. Après un nouveau découpage, refaire le lien avec les preuves et cette revue. Le code refuse une empreinte périmée et empêche qu’une même `family_id` de reformulations soit répartie entre développement et test.

## 8. Comparer les stratégies

```powershell
.\.venv\Scripts\python.exe run.py compare --split dev --output results/pilot_dev_v1 --repetitions 3
# Après réglage sur dev, figer configuration et annotations.
.\.venv\Scripts\python.exe run.py compare --split test --output results/test_v1 --repetitions 5
```

Un nouveau dossier de résultats est requis pour préserver les expériences existantes. Les commandes de recherche utilisent la configuration **enregistrée dans l’index**. Après modification de `configs/default.json`, relancer le découpage puis l’indexation ; modifier le JSON ne transforme pas un ancien index.

| Fichier | Usage |
|---|---|
| `summary.csv` | Macro-moyennes et latences, globales et par type |
| `metrics_per_question.csv` | Recall@K, MRR@K, couverture et complétude des preuves |
| `paired_comparisons.csv` | Différences B−A et intervalles bootstrap à 95 % par famille |
| `rankings.csv` | Candidats sourcés pour les comparaisons et le futur reranker |
| `rankings.jsonl` | Mêmes candidats avec textes et provenance complète |
| `latencies.csv` | Temps de chaque question/méthode/répétition et diagnostics lexicaux |
| `unanswerable_review.jsonl` | Questions sans réponse examinées séparément |
| `review_cases.jsonl` | Cas sélectionnés de succès, incomplétude et divergence à commenter |
| `run.json` | Empreintes, configuration, révision, machine et définition du chronométrage |

Les métriques sont calculées une fois par question, puis moyennées sur les mêmes questions répondables. Les répétitions servent aux temps. Les modèles et index sont chargés avant chronométrage ; chaque méthode reçoit une requête d’échauffement. Le dense inclut l’encodage de la question. RRF exécute à nouveau ses deux branches : il ne réutilise pas gratuitement les résultats déjà mesurés des autres méthodes. L’ordre des appels est mélangé avec une graine fixe pour limiter le biais de séquence.

Le protocole, les formules, les limites et la revue des erreurs sont dans [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md).

## 9. Vérification technique

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Les tests couvrent le nettoyage financier, la progression et la provenance du découpage, les égalités, RRF, les métriques, les index périmés/corrompus, les annotations et les fuites dev/test. Un test de bout en bout utilise BM25 réel et un encodeur **synthétique** pour vérifier les exports et le benchmark sans poids téléchargés. Ce test ne valide pas la pertinence sémantique d’E5. Les tests HTML et BM25 sont signalés comme ignorés si leurs bibliothèques ne sont pas installées.

L’état des exécutions et leurs limites sont consignés dans [docs/VALIDATION.md](docs/VALIDATION.md). Avant toute conclusion scientifique, faire relire les questions/preuves et exécuter le protocole dev/test. Le code s’arrête aux classements et à la comparaison de récupération, conformément au périmètre demandé.
