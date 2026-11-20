# Comparaison FOMC - 145 questions et qrels silver de pages

Ce rapport conserve le classement complet des 20 candidats pour le diagnostic. La sortie finale est limitée à 6 passages (ou 5). Voir [le rapport des contextes top-6](context_top6/RAPPORT.md) pour les performances des passages effectivement retenus.

Les 145 questions et 279 jugements fournis sont utilisés sans changement. Les grades d’origine sont conservés : {'2': 188, '1': 91}. Toutes les pages annotées existent dans les PDF et sont représentées dans les chunks indexés. Ce contrôle vérifie les fichiers et numéros de pages ; il ne constitue pas une validation humaine de leur pertinence sémantique.

Le corpus analysé comprend 93 PDF et 1692 chunks. Les index documentaires ont été reconstruits après nettoyage, puis la récupération et le reranking recalculés. Aucun entraînement local. Les étiquettes dev/test/validation sont conservées comme métadonnées ; toutes les questions sont évaluées ensemble.

## Protocole et unité de mesure

BM25, E5 et RRF récupèrent chacun 20 chunks. BM25, ColBERT et le cross-encoder reclassent exactement ces mêmes candidats. Le contrôle BM25 → BM25 conserve le classement initial.

Les qrels désignent des pages PDF, pas des chunks. Un chunk est relié aux pages physiques de ses paragraphes. Les pages sont parcourues dans l’ordre des chunks ; à l’intérieur d’un chunk multipage, elles suivent l’ordre physique. Chaque page est conservée à sa première apparition uniquement. Cette règle déterministe traite les pages du même chunk comme un groupe ordonné par numéro, sans utiliser les qrels. Elle peut influencer les métriques aux coupures de rang.

Recall@5/10/20 porte sur les premières pages uniques ; nDCG@10 utilise les grades silver et le gain 2^grade−1 ; MRR@10 utilise la première page annotée pertinente. Le classement idéal nDCG utilise tous les qrels de la question. La couverture du pool (pool_page_recall) mesure les pages pertinentes présentes dans l’ensemble des 20 chunks. Cette couverture est invariante après reranking. Recall@20 peut varier si ces 20 chunks couvrent plus de 20 pages uniques.

## Résultats moyens

| Configuration | Recall pages @20 | nDCG pages @10 | MRR pages @10 | Couverture du pool | Temps total médian (ms) |
|---|---:|---:|---:|---:|---:|
| bm25 | 0.550 | 0.286 | 0.281 | 0.588 | 8.5 |
| bm25 + bm25 | 0.550 | 0.286 | 0.281 | 0.588 | 18.5 |
| bm25 + colbert | 0.576 | 0.415 | 0.425 | 0.588 | 33.5 |
| bm25 + cross_encoder | 0.568 | 0.359 | 0.357 | 0.588 | 2119.4 |
| dense | 0.525 | 0.290 | 0.302 | 0.563 | 21.6 |
| dense + bm25 | 0.563 | 0.330 | 0.341 | 0.563 | 31.6 |
| dense + colbert | 0.559 | 0.405 | 0.422 | 0.563 | 47.3 |
| dense + cross_encoder | 0.552 | 0.373 | 0.385 | 0.563 | 2133.0 |
| hybrid_rrf | 0.581 | 0.328 | 0.329 | 0.618 | 30.3 |
| hybrid_rrf + bm25 | 0.574 | 0.287 | 0.281 | 0.618 | 40.4 |
| hybrid_rrf + colbert | 0.611 | 0.429 | 0.441 | 0.618 | 55.3 |
| hybrid_rrf + cross_encoder | 0.602 | 0.383 | 0.377 | 0.618 | 2143.2 |

Le meilleur nDCG@10 observé est **hybrid_rrf + colbert : 0.429**. Cette conclusion concerne ces questions, ces jugements silver, cette projection en pages et ces checkpoints.

## Effet du reranking sur le nDCG@10

| Configuration | Écart moyen | Questions améliorées | Inchangées | Dégradées |
|---|---:|---:|---:|---:|
| bm25 + bm25 | +0.000 | 0 | 145 | 0 |
| bm25 + colbert | +0.129 | 63 | 67 | 15 |
| bm25 + cross_encoder | +0.073 | 56 | 65 | 24 |
| dense + bm25 | +0.040 | 44 | 71 | 30 |
| dense + colbert | +0.115 | 56 | 71 | 18 |
| dense + cross_encoder | +0.083 | 49 | 67 | 29 |
| hybrid_rrf + bm25 | -0.041 | 31 | 68 | 46 |
| hybrid_rrf + colbert | +0.101 | 65 | 64 | 16 |
| hybrid_rrf + cross_encoder | +0.055 | 46 | 68 | 31 |

## Modèles, temps et limites

E5 : intfloat/e5-small-v2 ; ColBERT : answerdotai/answerai-colbert-small-v1, encodeur BERT et projection apprise à 96 dimensions, marqueurs de rôle et somme MaxSim ; cross-encoder : cross-encoder/ms-marco-MiniLM-L6-v2. Les révisions et paramètres sont figés dans src/common.py. BM25 utilise les statistiques du corpus complet, y compris lors du reranking.

Les temps correspondent à un passage CPU après échauffement, sans chargement des modèles. Le préencodage documentaire ColBERT prend 210.5 secondes et est exclu des durées en ligne. Les temps restent exploratoires.

Une page pertinente peut contenir plusieurs passages sans rapport avec la question : retrouver un chunk de cette page ne prouve pas que ce chunk contient la réponse. L’évaluation de pages est donc moins précise qu’une annotation de passages. Aucun grade de chunk n’a été inféré des qrels de pages. Les pages non jugées sont comptées zéro pour les métriques, sans preuve de non-pertinence. Les annotations silver peuvent être incomplètes ou erronées ; une revue humaine ciblée reste possible dans les PDF.

Le jeu unique permet une comparaison descriptive à paramètres fixés, sans confirmation indépendante après optimisation. Les nouveaux scores portent sur une autre unité de mesure et ne doivent pas être comparés directement aux anciens scores de chunks.

## Fichiers utiles

- comparison.csv : les 12 configurations.
- metrics_per_question.csv : scores et métadonnées de toutes les questions.
- page_rankings.jsonl : listes de chunks et pages uniques pour chaque configuration.
- paired_changes.csv : gains, égalités et pertes par question.
- cases.jsonl : exemples avant/après.
- ../data/evaluation/silver_qrels_PAGES.trec : jugements originaux.
- ../data/evaluation/chunk_pages.jsonl : provenance chunk → pages.
- verification.json : vérifications et empreintes des entrées.

## Exemples avant et après

### FOMC_092 - bm25 + colbert (largest_loss)

Why did the September 2026 staff projection put growth above potential through 2028?

nDCG@10 : 1.000 → 0.500.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260916.pdf#p6](../data/raw/minutes/fomcminutes20260916.pdf#page=6) | 2 | 1 | 3 |

### FOMC_086 - bm25 + colbert (largest_gain)

Which households appeared especially exposed to higher energy costs in April 2026?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260429.pdf#p10](../data/raw/minutes/fomcminutes20260429.pdf#page=10) | 2 | 16 | 1 |

### FOMC_092 - bm25 + cross_encoder (largest_loss)

Why did the September 2026 staff projection put growth above potential through 2028?

nDCG@10 : 1.000 → 0.301.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260916.pdf#p6](../data/raw/minutes/fomcminutes20260916.pdf#page=6) | 2 | 1 | 9 |

### FOMC_077 - bm25 + cross_encoder (largest_gain)

Apart from tariffs, what developments did policymakers see as risks to employment in July 2025?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20250730.pdf#p10](../data/raw/minutes/fomcminutes20250730.pdf#page=10) | 2 | 13 | 1 |

### FOMC_011 - dense + colbert (largest_loss)

In mid-2021, which supply-and-demand mechanisms did Federal Reserve staff associate with unusually large monthly price increases?

nDCG@10 : 1.000 → 0.315.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20210616.pdf#p8](../data/raw/minutes/fomcminutes20210616.pdf#page=8) | 2 | 1 | 8 |

### FOMC_070 - dense + colbert (largest_gain)

What supply-side developments helped businesses expand at the start of 2025?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20250129.pdf#p14](../data/raw/minutes/fomcminutes20250129.pdf#page=14) | 2 | 29 | 1 |

### FOMC_074 - dense + cross_encoder (largest_loss)

How could import duties encourage a company to charge more even if its own goods were exempt?

nDCG@10 : 0.818 → 0.307.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20250507.pdf#p10](../data/raw/minutes/fomcminutes20250507.pdf#page=10) | 2 | 7 | 12 |
| [fomcminutes20250618.pdf#p9](../data/raw/minutes/fomcminutes20250618.pdf#page=9) | 2 | 1 | 3 |

### FOMC_070 - dense + cross_encoder (largest_gain)

What supply-side developments helped businesses expand at the start of 2025?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20250129.pdf#p14](../data/raw/minutes/fomcminutes20250129.pdf#page=14) | 2 | 29 | 1 |

### FOMC_092 - hybrid_rrf + colbert (largest_loss)

Why did the September 2026 staff projection put growth above potential through 2028?

nDCG@10 : 1.000 → 0.500.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260916.pdf#p6](../data/raw/minutes/fomcminutes20260916.pdf#page=6) | 2 | 1 | 3 |

### FOMC_087 - hybrid_rrf + colbert (largest_gain)

What two sources of disinflation did participants discuss in April 2026?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260429.pdf#p9](../data/raw/minutes/fomcminutes20260429.pdf#page=9) | 2 | 12 | 1 |

### FOMC_092 - hybrid_rrf + cross_encoder (largest_loss)

Why did the September 2026 staff projection put growth above potential through 2028?

nDCG@10 : 1.000 → 0.301.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260916.pdf#p6](../data/raw/minutes/fomcminutes20260916.pdf#page=6) | 2 | 1 | 9 |

### FOMC_087 - hybrid_rrf + cross_encoder (largest_gain)

What two sources of disinflation did participants discuss in April 2026?

nDCG@10 : 0.000 → 1.000.

| Page silver | Grade | Rang initial | Rang après |
|---|---:|---:|---:|
| [fomcminutes20260429.pdf#p9](../data/raw/minutes/fomcminutes20260429.pdf#page=9) | 2 | 12 | 1 |

