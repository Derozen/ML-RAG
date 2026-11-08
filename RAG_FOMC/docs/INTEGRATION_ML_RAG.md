# Intégration du dépôt et des données fournis

## Origine et sélection du corpus

L’archive `ML-RAG-master.zip`, fournie par l’utilisateur, contient 93 PDF et une première implémentation Python. Son SHA256 figure dans `data/import_report.json`. Chaque fichier conservé est copié à l’identique et reçoit sa propre empreinte.

| Documents de l’archive | Nombre | Utilisation |
|---|---:|---|
| Minutes 2021 | 8 | Corpus principal |
| Minutes 2022 | 8 | Corpus principal |
| Minutes 2023 | 8 | Corpus principal |
| Minutes 2024 | 8 | Corpus principal |
| Minutes 2025 | 8 | Corpus principal |
| Minutes 2026 | 6 | Conservées, hors période du guide |
| Statements 2021–2026 | 47 | Conservés séparément, hors type documentaire principal |
| Minutes 2020 | 0 | Absentes du ZIP |

Le corpus principal contient donc **40 documents**, et non les 56 annoncés comme attente dans le guide. L’écart de −16 est un écart à cette attente, pas une démonstration qu’il manque exactement 16 réunions officielles. Le ZIP ne fournit aucun rapport de 2020 ; une confrontation exhaustive avec le calendrier officiel reste nécessaire pour établir la complétude de 2020–2025.

Les originaux se trouvent dans `data/raw/minutes/` et `data/raw/statements/`. La sélection de 40 rapports est définie dans `data/manifest.csv`, tandis que `data/archive_inventory.csv` conserve tous les PDF avec leur motif de sélection. Les deux formats documentaires ne sont pas mélangés dans la comparaison principale. Une étude élargie aux Statements ou à 2026 peut être menée ultérieurement avec une nouvelle version du corpus.

## Éléments repris de l’implémentation

Les sources originales sont conservées sous `references/ML-RAG-master/`. Elles servent à comprendre et comparer les choix, sans exécution automatique de leur `main.py` ni connexion à leur base de données. Le fichier `.env` de l’archive n’est pas copié ou chargé.

| Élément d’origine | Adaptation dans le projet |
|---|---|
| `preprocess_pdf` dans `Pdf2Txt.py` | Extraction PyMuPDF conservée ; lecture géométrique des colonnes, dates, sections et pages ajoutées |
| Nettoyage spaCy/NLTK | Normalisation conservatrice ; négations, ponctuation financière et fractions préservées |
| `CreateChunks`, taille de départ 128 mots | Fenêtres de tokens du modèle, chevauchement, frontières de documents/sections, gestion des longues phrases et offsets |
| `EmbedChunks`, SentenceTransformer | Chargement local, révision figée, vérification de longueur, normalisation et intégrité des vecteurs |
| `all-MiniLM-L12-v2` | Variante conservée dans `configs/minilm_reference.json` |
| `StockVectors.py`, PostgreSQL/pgvector | Stockage exact NumPy pour cette expérience locale ; interface de candidats sourcés disponible pour une intégration future |
| Parcours des Minutes et Statements dans `main.py` | Import automatique traçable ; sélection explicite du type et de la période dans le manifeste |

Le nettoyage initial supprimait les stopwords anglais, donc potentiellement `not`, et la ponctuation. Cela peut altérer une preuve financière. Le regroupement de plusieurs PDF dans une même chaîne supprimait également leurs frontières et leur provenance. Le pipeline révisé traite chaque document séparément et conserve le texte nécessaire à la vérification des citations.

Le code initial ne comprenait pas les trois moteurs de récupération et leur évaluation appariée. Ils sont assurés ici par `retrieval.py`, `evaluation.py` et `comparison.py`.

## Variante MiniLM de référence

Le modèle [all-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) utilise, dans sa [configuration Sentence Transformers publiée](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2/blob/main/sentence_bert_config.json), une longueur maximale de 128 tokens. Une fenêtre de 128 mots accompagnée de métadonnées peut donc être tronquée.

Le preset `configs/minilm_reference.json` conserve ce modèle, avec des préfixes vides, une limite totale de 128 tokens, une cible de 80 tokens de contenu et un chevauchement de 16. Le budget est encore réduit si les métadonnées l’exigent. Le preset E5 principal conserve les préfixes `passage:`/`query:` et une fenêtre cible de 400 tokens.

Pour tester MiniLM, travailler dans une copie de travail séparée, puis passer `--config configs/minilm_reference.json` aux étapes `extract`, `chunk` et `index`. Les index actifs d’un dossier sont uniques : réindexer dans le même dossier remplace l’expérience précédente. Comparer les modèles avec des fenêtres différentes constitue une expérience secondaire, distincte de la comparaison BM25/dense/RRF à passages communs. Ne pas attribuer un écart au seul modèle si le découpage change aussi.

## Adaptation aux PDF réellement reçus

Les formats anciens ont deux colonnes. Les plus récents ont une colonne et peuvent encoder chaque ligne dans un bloc PDF distinct. Le lecteur détecte les colonnes et réassemble les paragraphes selon la géométrie des lignes, les espacements et les titres. Une régression vérifie aussi les blocs contenant à la fois un titre et le premier paragraphe : le contenu après le titre doit être conservé.

L’extraction produit 6 080 paragraphes sur 563 pages physiques. L’audit compare les multiensembles de tokens extraits à ceux des lignes sources de chaque page, après le même retrait explicite des en-têtes. Il ne relève aucune perte/duplication et aucun caractère de remplacement Unicode. Les césures de fin de ligne restent présentes lorsque leur correction n’est pas établie ; elles peuvent réduire la qualité lexicale et demandent une revue. Les tableaux et les mises en page atypiques nécessitent également un contrôle humain.

`data/processed/review_samples.md` prépare des extraits du début, milieu et de la fin de chaque rapport. `data/processed/quality_report.json` et `extraction_report.json` conservent les contrôles et les indicateurs par document/page.

## Évaluation et périmètre

Les dix questions pilotes et leurs preuves sont des **pré-annotations**, conservées dans `pilot_seed.json`, puis liées aux IDs dans `pilot_draft.jsonl` par `prepare-pilot`. Elles incluent des chiffres, une négation, un motif de désaccord, une comparaison entre réunions et une question hors corpus. Elles demandent une seconde revue ; `validated` reste faux. Elles ne sont pas utilisées comme un test final validé.

Le travail reste limité à la préparation, vectorisation, récupération et code de comparaison. Le reranking appris, la génération et le déploiement ne sont pas exécutés.

L’exécution réelle a produit 1 454 vecteurs E5 de dimension 384 et 600 candidats pour les dix questions brouillon. Les contrôles techniques, les versions et les limites sont consignés dans `VALIDATION.md`. Les métriques scientifiques attendent la revue indépendante des annotations.
