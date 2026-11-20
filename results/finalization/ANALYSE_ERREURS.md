# Analyse des erreurs consolidée — 85 questions de développement

Les 1 020 observations correspondent aux mêmes 85 questions dans 12 configurations. Les catégories mesurent les références de pages silver, sans attribuer automatiquement une cause sémantique.

| Recherche | Reranker | Aucune page annotée | Couverture partielle | Toutes les pages annotées |
|---|---|---:|---:|---:|
| bm25 | none | 40 | 22 | 23 |
| bm25 | bm25 | 40 | 22 | 23 |
| bm25 | colbert | 31 | 21 | 33 |
| bm25 | cross_encoder | 30 | 25 | 30 |
| dense | none | 40 | 23 | 22 |
| dense | bm25 | 34 | 25 | 26 |
| dense | colbert | 29 | 25 | 31 |
| dense | cross_encoder | 31 | 24 | 30 |
| hybrid_rrf | none | 35 | 20 | 30 |
| hybrid_rrf | bm25 | 40 | 22 | 23 |
| hybrid_rrf | colbert | 28 | 26 | 31 |
| hybrid_rrf | cross_encoder | 32 | 24 | 29 |

## Résultats par type : système RRF + ColBERT

| Type | Effectif | Couverture moyenne | nDCG pages@6 |
|---|---:|---:|---:|
| explanatory | 21 | 0.595 | 0.408 |
| factual | 40 | 0.579 | 0.465 |
| multi_document | 3 | 0.333 | 0.412 |
| comparative | 21 | 0.313 | 0.229 |

Les moyennes sont recalculées sur les observations individuelles et concordent avec les tableaux existants à 10⁻¹². Le groupe multi-document ne comporte que trois questions : aucune généralisation robuste ne repose sur ce seul effectif.

## Trois cas relus dans les PDF

- **FOMC_004** : un chunk de la bonne réunion contient une réponse, mais sa page manque aux qrels. Un zéro silver ne prouve pas une absence de réponse.
- **FOMC_035** : ColBERT promeut un passage pertinent de janvier 2022, malgré une baisse du score silver. La génération reste partielle et cite aussi des réunions ultérieures.
- **FOMC_064** : une preuve déjà présente dans le contexte passe du quatrième au premier chunk ; la page passe du rang 7 au rang 1. L’amélioration de nDCG ne signifie pas ici découverte d’une nouvelle preuve.

[Textes, identifiants de chunks, classements et citations vérifiées](../audit_project/ANALYSE_QUALITATIVE_DEV.md). Les trois cas sont sélectionnés pour expliquer les mécanismes ; leur fréquence n’est pas une estimation du taux d’erreur.

Deux références supplémentaires sont proposées dans `data/evaluation/audit/dev_qrels_proposals.trec`, sans modification des qrels historiques ni recalcul opportuniste des scores. Les pages non jugées comptent zéro dans les métriques, sans preuve de non-pertinence.
